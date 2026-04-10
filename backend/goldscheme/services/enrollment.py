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
        # Lock the current gold rate for the scheme's accumulation purity
        purity = scheme.accumulation_purity
        if not purity:
            raise ValueError(
                "Cannot enroll in a LOCKED price scheme: accumulation purity is not configured on the scheme."
            )
        latest_rate = GoldRates.objects.filter(purity=purity).order_by('-date1').first()
        if not latest_rate or not latest_rate.rate:
            raise ValueError(
                f"Cannot enroll in a LOCKED price scheme: no gold rate found for purity '{purity}'. "
                f"Please ensure today's gold rate is entered before creating enrollments."
            )
        locked_rate = Decimal(str(latest_rate.rate))
        if locked_rate <= 0:
            raise ValueError(
                f"Cannot enroll in a LOCKED price scheme: gold rate for purity '{purity}' is zero or negative."
            )
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
    Uses select_for_update() to prevent race conditions on concurrent requests.
    """
    from goldscheme.models import SchemeEnrollment

    if enrollment.status == 'ACTIVE' and enrollment.is_matured:
        with transaction.atomic():
            locked = SchemeEnrollment.objects.select_for_update().get(pk=enrollment.pk)
            if locked.status == 'ACTIVE' and locked.is_matured:
                locked.status = 'MATURED'
                locked.save(update_fields=['status', 'updated_at'])
                # Refresh the original object so the caller sees the update
                enrollment.status = locked.status
    return enrollment
