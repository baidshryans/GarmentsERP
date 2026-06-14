"""
Redemption service — benefit calculation, scheme closure.
"""
from datetime import date
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

        # Settlement JV: clear the scheme float against the customer's trade ledger.
        if enrollment.liability_ledger_id and enrollment.total_paid > 0:
            from global_vars import VoucherType
            from accounting.models import VoucherMain, VoucherDetail
            from accounting.utils import generate_voucher_no

            retail = enrollment.retail
            fiscal_year = enrollment.fiscal_year or getattr(retail, 'active_fy', None)
            vno = generate_voucher_no(VoucherType.scheme_redeem, retail, fiscal_year)
            narr = (f"Scheme redemption {enrollment.enrollment_no} — "
                    f"{enrollment.customer.ac_name}")[:150]
            voucher = VoucherMain.objects.create(
                date=enrollment.redeemed_date or (sales_vou.date1 if sales_vou else None) or date.today(),
                voucher_no=vno, narration=narr, amount=enrollment.total_paid,
                voucher_type=VoucherType.scheme_redeem, retail=retail, fiscal_year=fiscal_year,
            )
            VoucherDetail.objects.create(
                voucher_main=voucher, voucher_no=vno, voucher_type=VoucherType.scheme_redeem,
                account=enrollment.liability_ledger, debit=enrollment.total_paid, credit=0,
            )
            VoucherDetail.objects.create(
                voucher_main=voucher, voucher_no=vno, voucher_type=VoucherType.scheme_redeem,
                account=enrollment.customer, debit=0, credit=enrollment.total_paid,
            )

    return enrollment


def cancel_enrollment(enrollment, reason='', settlement_mode=None, refund_ledger=None):
    """
    Cancel an enrollment and settle the scheme balance the operator's chosen way.

    settlement_mode:
        'REFUND'   → Dr scheme sub-ledger / Cr refund_ledger (cash/bank). refund_ledger required.
        'TRANSFER' → Dr scheme sub-ledger / Cr customer trade ledger (becomes a usable credit).
        None       → no accounting entry (only valid when there is no balance to settle).

    Forfeiture is intentionally not supported — retaining a customer's scheme
    deposits is not permitted, so a cancelled scheme must always be refunded or
    transferred back to the customer.

    The JV clears the per-enrollment scheme sub-ledger to zero.
    """
    if enrollment.status in ('REDEEMED',):
        raise ValueError("Cannot cancel: enrollment has already been redeemed.")

    has_balance = bool(enrollment.liability_ledger_id) and enrollment.total_paid > 0

    if has_balance:
        if settlement_mode not in ('REFUND', 'TRANSFER'):
            raise ValueError(
                "A settlement mode (REFUND or TRANSFER) is required because "
                "the customer has paid into this scheme."
            )
        if settlement_mode == 'REFUND' and refund_ledger is None:
            raise ValueError("A cash/bank account is required to refund the customer.")

    with transaction.atomic():
        enrollment.status = 'CANCELLED'
        if reason:
            enrollment.remarks = f"{enrollment.remarks}\nCancelled: {reason}".strip()
        enrollment.save(update_fields=['status', 'remarks', 'updated_at'])

        if has_balance:
            from global_vars import VoucherType
            from accounting.models import VoucherMain, VoucherDetail
            from accounting.utils import generate_voucher_no

            retail = enrollment.retail
            fiscal_year = enrollment.fiscal_year or getattr(retail, 'active_fy', None)
            amount = enrollment.total_paid

            if settlement_mode == 'REFUND':
                credit_account = refund_ledger
                label = 'refund'
            else:  # TRANSFER
                credit_account = enrollment.customer
                label = 'transfer to customer'

            vno = generate_voucher_no(VoucherType.scheme_cancel, retail, fiscal_year)
            narr = (f"Scheme cancellation {enrollment.enrollment_no} ({label}) — "
                    f"{enrollment.customer.ac_name}")[:150]
            voucher = VoucherMain.objects.create(
                date=date.today(), voucher_no=vno, narration=narr, amount=amount,
                voucher_type=VoucherType.scheme_cancel, retail=retail, fiscal_year=fiscal_year,
            )
            # Dr scheme sub-ledger (clear the liability)
            VoucherDetail.objects.create(
                voucher_main=voucher, voucher_no=vno, voucher_type=VoucherType.scheme_cancel,
                account=enrollment.liability_ledger, debit=amount, credit=0,
            )
            # Cr the chosen destination
            VoucherDetail.objects.create(
                voucher_main=voucher, voucher_no=vno, voucher_type=VoucherType.scheme_cancel,
                account=credit_account, debit=0, credit=amount,
            )

    return enrollment
