"""
Redemption service — benefit calculation, scheme closure.
"""
from decimal import Decimal

from django.db import transaction


def get_applicable_benefits(enrollment):
    """
    Return the applicable benefits for the current enrollment state.
    Returns dict with gold and diamond benefits.
    """
    from goldscheme.services.enrollment import check_and_update_maturity
    check_and_update_maturity(enrollment)

    months = enrollment.months_completed
    gold_tier = enrollment.applicable_benefit
    diamond_tier = enrollment.applicable_diamond_benefit

    result = {
        'enrollment_no': enrollment.enrollment_no,
        'scheme': enrollment.scheme.name,
        'months_completed': months,
        'total_paid': float(enrollment.total_paid),
        'gold_accumulated_wt': float(enrollment.gold_accumulated_wt),
        'status': enrollment.status,
        'gold_benefit': None,
        'diamond_benefit': None,
    }

    if gold_tier:
        result['gold_benefit'] = {
            'lc_discount_pct': float(gold_tier.lc_discount_pct),
            'value_discount_pct': float(gold_tier.value_discount_pct),
            'tier': f"{gold_tier.min_months}-{gold_tier.max_months} months",
        }

    if diamond_tier:
        result['diamond_benefit'] = {
            'lc_discount_pct': float(diamond_tier.lc_discount_pct),
            'value_discount_pct': float(diamond_tier.value_discount_pct),
            'tier': f"{diamond_tier.min_months}-{diamond_tier.max_months} months",
        }

    return result


def redeem_enrollment(enrollment, sales_vou=None, lc_discount_amount=Decimal('0'),
                      value_discount_amount=Decimal('0')):
    """
    Mark an enrollment as REDEEMED, link it to a sales voucher.
    This is called when the customer purchases jewellery using their scheme balance.
    """
    if enrollment.status not in ('ACTIVE', 'MATURED'):
        raise ValueError(f"Cannot redeem: enrollment is {enrollment.status}.")

    if enrollment.total_paid <= 0:
        raise ValueError("Cannot redeem: no payments have been made.")

    with transaction.atomic():
        enrollment.status = 'REDEEMED'
        enrollment.redeemed_date = sales_vou.date1 if sales_vou else None
        enrollment.redeemed_sales_vou = sales_vou
        enrollment.lc_discount_applied = lc_discount_amount
        enrollment.value_discount_applied = value_discount_amount
        enrollment.save(update_fields=[
            'status', 'redeemed_date', 'redeemed_sales_vou',
            'lc_discount_applied', 'value_discount_applied', 'updated_at',
        ])

    return enrollment


def cancel_enrollment(enrollment, reason=''):
    """Cancel an enrollment. Payments remain recorded but no benefits apply."""
    if enrollment.status in ('REDEEMED',):
        raise ValueError("Cannot cancel: enrollment has already been redeemed.")

    with transaction.atomic():
        enrollment.status = 'CANCELLED'
        if reason:
            enrollment.remarks = f"{enrollment.remarks}\nCancelled: {reason}".strip()
        enrollment.save(update_fields=['status', 'remarks', 'updated_at'])

    return enrollment
