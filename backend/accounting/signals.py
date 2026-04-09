"""
Reversal integrity signals for the accounting module.

When a VoucherMain is deleted (or soft-cancelled via cancel_voucher), we must:

1. Walk its VoucherDetail rows and restore `due_amt` on any SalesVou /
   PurchaseVoucher that this voucher allocated against. Otherwise the
   outstanding balance on those invoices becomes permanently wrong.

2. Delete the ReferenceBills rows that point to this voucher so we don't
   leave orphaned allocation audit entries behind.

Only PMNT / RCPT / RCPT-SALE affect invoice due_amt today. JRNL will be added
in Phase 4 when credit-note adjustment is implemented.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import VoucherMain, ReferenceBills


@receiver(pre_delete, sender=VoucherMain)
def reverse_voucher_effects(sender, instance, **kwargs):
    """
    Restore invoice due_amt and clean ReferenceBills before the voucher is
    deleted. Runs in a transaction so partial failures roll back.
    """
    # A cancelled voucher was already reversed when it was cancelled — skip.
    if instance.status == 'cancelled':
        ReferenceBills.objects.filter(voucher=instance).delete()
        return

    vtype = (instance.voucher_type or '').strip().upper()
    if vtype not in ('PMNT', 'RCPT', 'RCPT-SALE', 'JRNL', 'CN', 'DN'):
        ReferenceBills.objects.filter(voucher=instance).delete()
        return

    # Lazy imports to avoid circular dependencies at module load time.
    from sales.models import SalesVou
    from purchase.models import PurchaseVoucher

    with transaction.atomic():
        for detail in instance.transactions.all():
            ref_bill_no = detail.ref_bill_no
            if not ref_bill_no:
                continue
            d_amt = Decimal(str(detail.debit or 0))
            c_amt = Decimal(str(detail.credit or 0))
            if vtype == 'PMNT':
                amt = d_amt + c_amt
                pv = PurchaseVoucher.objects.select_for_update().filter(
                    billno=ref_bill_no
                ).first()
                if pv and amt > 0:
                    pv.due_amt = (pv.due_amt or Decimal('0')) + amt
                    pv.save(update_fields=['due_amt'])
            elif vtype in ('RCPT', 'RCPT-SALE'):
                amt = d_amt + c_amt
                sv = SalesVou.objects.select_for_update().filter(
                    billno=ref_bill_no
                ).first()
                if sv and amt > 0:
                    sv.due_amt = (sv.due_amt or Decimal('0')) + amt
                    sv.save(update_fields=['due_amt'])
            elif vtype in ('JRNL', 'CN', 'DN'):
                # Mirror of the create-time logic: direction depends on side.
                sv = SalesVou.objects.select_for_update().filter(
                    billno=ref_bill_no, ldgr_id=detail.account_id
                ).first()
                pv = PurchaseVoucher.objects.select_for_update().filter(
                    billno=ref_bill_no, ldgr_id=detail.account_id
                ).first()
                if sv and c_amt > 0:
                    sv.due_amt = (sv.due_amt or Decimal('0')) + c_amt
                    sv.save(update_fields=['due_amt'])
                elif pv and d_amt > 0:
                    pv.due_amt = (pv.due_amt or Decimal('0')) + d_amt
                    pv.save(update_fields=['due_amt'])

        # Clean the allocation audit rows for this voucher.
        ReferenceBills.objects.filter(voucher=instance).delete()


def cancel_voucher(voucher, user=None):
    """
    Soft-cancel a posted voucher: reverse its ledger/invoice effects and
    mark it as cancelled without deleting rows. Preferred over hard delete
    for audit-traceable reversals.
    """
    if voucher.status == 'cancelled':
        return voucher
    # Run the same reversal logic as pre_delete
    reverse_voucher_effects(VoucherMain, voucher)
    voucher.status = 'cancelled'
    voucher.save(update_fields=['status'])
    return voucher
