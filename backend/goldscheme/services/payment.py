"""
Payment service — record installments, calculate gold accumulation, create accounting vouchers.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from django.db import transaction

from accounting.utils import get_next_bill_number
from goldrates.models import GoldRates


def validate_payment(enrollment, amount):
    """Validate a payment against enrollment rules."""
    errors = []
    scheme = enrollment.scheme

    if enrollment.status not in ('ACTIVE',):
        errors.append(f"Enrollment is {enrollment.status}, cannot accept payments.")

    if scheme.scheme_type == 'LUMPSUM' and enrollment.payments_made >= 1:
        errors.append("Lump-sum scheme only accepts a single payment.")

    if amount < scheme.min_amount:
        errors.append(f"Payment ₹{amount} is below minimum ₹{scheme.min_amount}.")

    if scheme.max_amount and amount > scheme.max_amount:
        errors.append(f"Payment ₹{amount} exceeds maximum ₹{scheme.max_amount}.")

    return errors


def calculate_gold_weight(amount, purity, rate_override=None):
    """
    Calculate gold weight in grams for an ACCUMULATION type payment.
    weight = amount / rate_per_gram
    """
    if rate_override:
        rate = rate_override
    else:
        latest = GoldRates.objects.filter(purity=purity).order_by('-date1').first()
        if not latest:
            return Decimal('0'), Decimal('0')
        rate = Decimal(str(latest.rate))

    if rate <= 0:
        return Decimal('0'), rate

    weight = (amount / rate).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
    return weight, rate


def record_payment(enrollment, amount, payment_mode, payment_ledger, payment_date=None, remarks=''):
    """
    Record a scheme payment:
    1. Validate
    2. For ACCUMULATION: calculate gold weight
    3. Create SchemePayment record
    4. Update enrollment totals
    5. Accounting voucher is created via signal (see signals.py)
    """
    from goldscheme.models import SchemePayment

    errors = validate_payment(enrollment, amount)
    if errors:
        raise ValueError("; ".join(errors))

    pay_date = payment_date or date.today()
    retail = enrollment.retail
    from mastersconfig.fy_validation import assert_date_in_active_fy
    assert_date_in_active_fy(retail, pay_date, field="date")
    fiscal_year = enrollment.fiscal_year or getattr(retail, 'active_fy', None)

    payment_no = get_next_bill_number(retail, "SCHM-P", fiscal_year)

    gold_rate = None
    gold_weight = None

    if enrollment.scheme.gold_price_mode == 'ACCUMULATED':
        purity = enrollment.scheme.accumulation_purity
        if not purity:
            raise ValueError(
                "Cannot record payment: accumulation purity is not configured on the scheme."
            )
        gold_weight, gold_rate = calculate_gold_weight(amount, purity)
        if not gold_rate or gold_rate <= 0:
            raise ValueError(
                f"Cannot record payment: no gold rate found for purity '{purity}'. "
                f"Please ensure today's gold rate is entered before accepting payments."
            )

    with transaction.atomic():
        # Lock the enrollment row to prevent race conditions on running totals
        from goldscheme.models import SchemeEnrollment
        locked_enrollment = SchemeEnrollment.objects.select_for_update().get(pk=enrollment.pk)

        if locked_enrollment.status not in ('ACTIVE',):
            raise ValueError(f"Enrollment is {locked_enrollment.status}, cannot accept payments.")

        payment = SchemePayment.objects.create(
            enrollment=locked_enrollment,
            payment_no=payment_no,
            date=pay_date,
            amount=amount,
            payment_mode=payment_mode,
            payment_ledger=payment_ledger,
            installment_number=locked_enrollment.next_installment_number,
            gold_rate_at_payment=gold_rate,
            gold_weight_added=gold_weight,
            retail=retail,
            fiscal_year=fiscal_year,
            remarks=remarks,
        )

        # Update enrollment running totals
        locked_enrollment.total_paid += amount
        locked_enrollment.payments_made += 1
        if gold_weight:
            locked_enrollment.gold_accumulated_wt += gold_weight
        locked_enrollment.save(update_fields=[
            'total_paid', 'payments_made', 'gold_accumulated_wt', 'updated_at'
        ])
        # Sync the caller's enrollment object
        enrollment.total_paid = locked_enrollment.total_paid
        enrollment.payments_made = locked_enrollment.payments_made
        enrollment.gold_accumulated_wt = locked_enrollment.gold_accumulated_wt

    return payment
