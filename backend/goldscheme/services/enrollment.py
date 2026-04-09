"""
Enrollment service — validation, creation, maturity handling.
"""
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction

from accounting.utils import get_next_bill_number
from goldrates.models import GoldRates


def validate_enrollment(scheme, amount):
    """Validate installment amount against scheme constraints."""
    errors = []
    if amount < scheme.min_amount:
        errors.append(f"Amount ₹{amount} is below minimum ₹{scheme.min_amount}.")
    if scheme.max_amount and amount > scheme.max_amount:
        errors.append(f"Amount ₹{amount} exceeds maximum ₹{scheme.max_amount}.")
    if not scheme.is_active:
        errors.append("This scheme is no longer active for new enrollments.")
    return errors


def create_enrollment(scheme, customer, amount, retail, fiscal_year=None, salesperson=None, remarks='', start_date=None):
    """
    Create a new SchemeEnrollment with auto-generated enrollment number.
    For LOCKED price mode, captures the current gold rate.
    """
    from goldscheme.models import SchemeEnrollment

    errors = validate_enrollment(scheme, amount)
    if errors:
        raise ValueError("; ".join(errors))

    start = start_date or date.today()
    maturity = start + relativedelta(months=scheme.tenure_months)

    enrollment_no = get_next_bill_number(retail, "SCHM-E", fiscal_year)

    locked_rate = None
    locked_purity = None
    if scheme.gold_price_mode == 'LOCKED':
        # Lock the current gold rate for the scheme's accumulation purity (or default 22K)
        purity = scheme.accumulation_purity
        if purity:
            latest_rate = GoldRates.objects.filter(purity=purity).order_by('-date1').first()
            if latest_rate:
                locked_rate = Decimal(str(latest_rate.rate))
                locked_purity = purity

    with transaction.atomic():
        enrollment = SchemeEnrollment.objects.create(
            enrollment_no=enrollment_no,
            scheme=scheme,
            customer=customer,
            start_date=start,
            maturity_date=maturity,
            installment_amount=amount,
            locked_gold_rate=locked_rate,
            locked_purity=locked_purity,
            retail=retail,
            fiscal_year=fiscal_year or getattr(retail, 'active_fy', None),
            salesperson=salesperson,
            remarks=remarks,
        )

    return enrollment


def check_and_update_maturity(enrollment):
    """
    If the enrollment has reached maturity date and is still ACTIVE, update status to MATURED.
    """
    if enrollment.status == 'ACTIVE' and enrollment.is_matured:
        enrollment.status = 'MATURED'
        enrollment.save(update_fields=['status', 'updated_at'])
    return enrollment
