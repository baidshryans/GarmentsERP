from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import SalesVou, SaleReturn, SalesApprovalItem, SalesApprovalReturnItem


@receiver(pre_delete, sender=SalesVou)
def on_sales_vou_delete(sender, instance, **kwargs):
    """
    When a SalesVou is deleted:
    1. Restore stk_status=True on every barcode that was sold in this voucher.
    2. Delete the linked accounting VoucherMain entries (ac_voucher and
       ac_rec_voucher).  VoucherDetail rows cascade automatically from VoucherMain.
    """
    # ── 1. Restore barcode stock status ──────────────────────────────────────
    from inventory.models import BarcodeMain

    barcode_ids = list(
        instance.salesvouitem_set
        .exclude(barcode__isnull=True)
        .values_list('barcode_id', flat=True)
        .distinct()
    )
    if barcode_ids:
        BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=True)

    # ── 2. Delete linked accounting vouchers ─────────────────────────────────
    # Collect IDs before the FK becomes NULL on SalesVou deletion.
    voucher_ids = [
        v for v in [
            instance.ac_voucher_id,
            instance.ac_rec_voucher_id,
        ]
        if v is not None
    ]
    if voucher_ids:
        from accounting.models import VoucherMain
        VoucherMain.objects.filter(id__in=voucher_ids).delete()


@receiver(pre_delete, sender=SaleReturn)
def on_sale_return_delete(sender, instance, **kwargs):
    """
    When a SaleReturn is deleted (only permitted when ac_voucher is not posted):
    1. Take the returned barcodes back out of stock (stk_status=False) — they
       were put back in stock when the return was created; deleting the return
       reverses that.
    2. Delete the linked accounting voucher if it exists.
    """
    from inventory.models import BarcodeMain

    barcode_ids = list(
        instance.salereturnitem_set
        .exclude(barcode__isnull=True)
        .values_list('barcode_id', flat=True)
        .distinct()
    )
    if barcode_ids:
        BarcodeMain.objects.filter(id__in=barcode_ids).update(stk_status=False)

    if instance.ac_voucher_id:
        from accounting.models import VoucherMain
        VoucherMain.objects.filter(id=instance.ac_voucher_id).delete()

    if instance.sales_voucher_ref_id:
        from decimal import Decimal
        sv = instance.sales_voucher_ref
        return_total = Decimal(str(instance.total_bill_value))
        sv.due_amt = sv.due_amt + return_total
        sv.save(update_fields=['due_amt'])


@receiver(pre_delete, sender=SalesApprovalItem)
def on_sales_approval_item_delete(sender, instance, **kwargs):
    """
    When a SalesApprovalItem is deleted (item removed by an edit, or the
    parent SalesApproval is being deleted and items cascade), restore the
    barcode's stk_status to True. Items with ret_status=True already had
    their barcode put back in stock when the return was recorded, so
    setting True again is idempotent and safe.
    """
    if instance.barcode_id:
        from inventory.models import BarcodeMain
        BarcodeMain.objects.filter(id=instance.barcode_id).update(stk_status=True)


@receiver(pre_delete, sender=SalesApprovalReturnItem)
def on_sales_approval_return_item_delete(sender, instance, **kwargs):
    if instance.barcode_id:
        from inventory.models import BarcodeMain
        BarcodeMain.objects.filter(id=instance.barcode_id).update(stk_status=False)
    if instance.approval_item_id:
        SalesApprovalItem.objects.filter(id=instance.approval_item_id).update(ret_status=False)
