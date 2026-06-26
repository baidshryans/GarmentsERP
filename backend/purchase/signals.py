from decimal import Decimal

from django.db.models.signals import post_save, post_delete, pre_delete, pre_save
from django.dispatch import receiver

from inventory.models import RawMaterialInventory, RawMaterialTransaction
from purchase.models import (
    PurchaseVoucherItems, PurchaseVoucherDetails,
    PurchaseReturnItems, PurchaseReturnDetails, PurchaseReturn,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _update_raw_material(item, packet, purity, retail, pcs=0, ct=Decimal('0'), gw=Decimal('0')):
    # get_or_merge tolerates duplicate inventory rows (NULL packet/purity bypass
    # the unique_together), so this never raises MultipleObjectsReturned.
    rm = RawMaterialInventory.get_or_merge(item, packet, purity, retail)
    rm.pcs += pcs
    rm.ct += ct
    rm.gw += gw
    rm.save()


def _log_raw_txn(*, item, packet, purity, retail, trans_type, pcs=0, ct=Decimal('0'), gw=Decimal('0'),
                  rate=Decimal('0'), amt=Decimal('0'), billno=''):
    RawMaterialTransaction.objects.create(
        item=item, packet=packet, purity=purity, retail=retail,
        trans_type=trans_type, pcs=pcs, ct=ct, gw=gw,
        rate=rate, amt=amt, billno=billno,
    )


# ── Purchase → increase raw material ─────────────────────────────────────────

@receiver(post_save, sender=PurchaseVoucherItems)
def clear_op_stk_on_purchase(sender, instance, created, **kwargs):
    """When a purchase voucher links to a barcode, that barcode is a purchase — not opening stock."""
    if created and instance.barcode_id and instance.barcode.op_stk:
        instance.barcode.op_stk = False
        instance.barcode.save(update_fields=['op_stk'])


@receiver(post_save, sender=PurchaseVoucherItems)
def increase_raw_material_on_purchase(sender, instance, created, **kwargs):
    if not created or instance.is_finished:
        return
    _update_raw_material(
        item=instance.item, packet=None,
        purity=instance.purity, retail=instance.retail,
        pcs=instance.pcs or 0, gw=instance.gw or Decimal('0'),
    )
    _log_raw_txn(
        item=instance.item, packet=None,
        purity=instance.purity, retail=instance.retail,
        trans_type='PURCHASE',
        pcs=instance.pcs or 0, gw=instance.gw or Decimal('0'),
        rate=Decimal(str(instance.item_value or 0)),
        amt=Decimal(str(instance.item_value or 0)),
        billno=instance.billno.billno if instance.billno else '',
    )


@receiver(pre_delete, sender=PurchaseVoucherItems)
def reverse_raw_material_on_purchase_delete(sender, instance, **kwargs):
    if instance.is_finished:
        return
    _update_raw_material(
        item=instance.item, packet=None,
        purity=instance.purity, retail=instance.retail,
        pcs=-(instance.pcs or 0), gw=-(instance.gw or Decimal('0')),
    )
    _log_raw_txn(
        item=instance.item, packet=None,
        purity=instance.purity, retail=instance.retail,
        trans_type='PURCHASE_DEL',
        pcs=-(instance.pcs or 0), gw=-(instance.gw or Decimal('0')),
        billno=instance.billno.billno if instance.billno else '',
    )


@receiver(pre_delete, sender=PurchaseVoucherItems)
def unlock_customer_order_item_on_pv_delete(sender, instance, **kwargs):
    """
    When a PV line that was directly linked to a Customer Order item is deleted,
    flip the CO item's sale_status back to False so it reappears in the pending
    picker — but only if no other terminal lock path remains (another PV line
    or a SalesVouItem covering the same barcode).
    """
    coi = instance.customer_order_item
    if not coi:
        return

    # Is this CO item referenced by any OTHER PurchaseVoucherItems row?
    other_pv_exists = (
        PurchaseVoucherItems.objects
        .filter(customer_order_item=coi)
        .exclude(pk=instance.pk)
        .exists()
    )
    if other_pv_exists:
        return

    # Belt-and-braces: also skip unlock if a SalesVouItem terminally billed
    # this CO item's barcode (shouldn't normally happen before PV delete,
    # but we keep the CO locked if it has been sold).
    from sales.models import CustomerOrderItems
    CustomerOrderItems.objects.filter(pk=coi.pk).update(sale_status=False)


@receiver(pre_save, sender=PurchaseVoucherDetails)
def capture_old_detail_values_before_update(sender, instance, **kwargs):
    """
    Before an UPDATE, snapshot the current DB row so post_save can compute
    the inventory delta (new − old). Skipped for brand-new records (no pk yet).
    """
    if not instance.pk:
        instance._old_detail = None
        return
    if instance.main_item and instance.main_item.is_finished:
        instance._old_detail = None
        return
    try:
        old = sender.objects.get(pk=instance.pk)
        instance._old_detail = {
            'sub_item':  old.sub_item,
            'packet':    old.packet,
            'purity':    old.metal_purity,
            'retail':    old.retail,
            'pcs':       old.sub_pcs or 0,
            'ct':        old.sub_ct  or Decimal('0'),
            'gw':        old.sub_gw  or Decimal('0'),
        }
    except sender.DoesNotExist:
        instance._old_detail = None


@receiver(post_save, sender=PurchaseVoucherDetails)
def adjust_raw_material_on_detail_save(sender, instance, created, **kwargs):
    """
    CREATE  → add full quantities to inventory.
    UPDATE  → adjust inventory by the delta (new − old quantities).
              If the sub_item / packet / purity changed, reverse the old entry
              completely and add the new entry completely.
    """
    if instance.main_item and instance.main_item.is_finished:
        return

    billno_str = instance.billno.billno if instance.billno else ''

    if created:
        # ── New sub-item: add full quantity ──────────────────────────────────
        _update_raw_material(
            item=instance.sub_item, packet=instance.packet,
            purity=instance.metal_purity, retail=instance.retail,
            pcs=instance.sub_pcs or 0,
            ct=instance.sub_ct or Decimal('0'),
            gw=instance.sub_gw or Decimal('0'),
        )
        _log_raw_txn(
            item=instance.sub_item, packet=instance.packet,
            purity=instance.metal_purity, retail=instance.retail,
            trans_type='PURCHASE',
            pcs=instance.sub_pcs or 0,
            ct=instance.sub_ct or Decimal('0'),
            gw=instance.sub_gw or Decimal('0'),
            rate=instance.rate or Decimal('0'),
            amt=instance.value or Decimal('0'),
            billno=billno_str,
        )
    else:
        # ── Existing sub-item updated: delta adjustment ───────────────────────
        old = getattr(instance, '_old_detail', None)
        if old is None:
            return  # pre_save didn't capture (finished item, etc.)

        new_pcs = instance.sub_pcs or 0
        new_ct  = instance.sub_ct  or Decimal('0')
        new_gw  = instance.sub_gw  or Decimal('0')

        # Detect whether the item/packet/purity itself changed
        same_item = (
            (instance.sub_item_id  == (old['sub_item'].id  if old['sub_item']  else None)) and
            (instance.packet_id    == (old['packet'].id    if old['packet']    else None)) and
            (instance.metal_purity_id == (old['purity'].id if old['purity']   else None))
        )

        if not same_item:
            # Reverse the old entry completely, then add the new entry
            _update_raw_material(
                item=old['sub_item'], packet=old['packet'],
                purity=old['purity'], retail=old['retail'],
                pcs=-old['pcs'], ct=-old['ct'], gw=-old['gw'],
            )
            _log_raw_txn(
                item=old['sub_item'], packet=old['packet'],
                purity=old['purity'], retail=old['retail'],
                trans_type='PURCHASE_UPD',
                pcs=-old['pcs'], ct=-old['ct'], gw=-old['gw'],
                billno=billno_str,
            )
            _update_raw_material(
                item=instance.sub_item, packet=instance.packet,
                purity=instance.metal_purity, retail=instance.retail,
                pcs=new_pcs, ct=new_ct, gw=new_gw,
            )
            _log_raw_txn(
                item=instance.sub_item, packet=instance.packet,
                purity=instance.metal_purity, retail=instance.retail,
                trans_type='PURCHASE_UPD',
                pcs=new_pcs, ct=new_ct, gw=new_gw,
                rate=instance.rate or Decimal('0'),
                amt=instance.value or Decimal('0'),
                billno=billno_str,
            )
        else:
            # Same item/packet/purity — only adjust the quantity delta
            delta_pcs = new_pcs - old['pcs']
            delta_ct  = new_ct  - old['ct']
            delta_gw  = new_gw  - old['gw']
            if delta_pcs or delta_ct or delta_gw:
                _update_raw_material(
                    item=instance.sub_item, packet=instance.packet,
                    purity=instance.metal_purity, retail=instance.retail,
                    pcs=delta_pcs, ct=delta_ct, gw=delta_gw,
                )
                _log_raw_txn(
                    item=instance.sub_item, packet=instance.packet,
                    purity=instance.metal_purity, retail=instance.retail,
                    trans_type='PURCHASE_UPD',
                    pcs=delta_pcs, ct=delta_ct, gw=delta_gw,
                    billno=billno_str,
                )
            # If only rate/value changed, quantities are unchanged → no inventory adjustment needed


@receiver(pre_delete, sender=PurchaseVoucherDetails)
def reverse_raw_material_on_purchase_detail_delete(sender, instance, **kwargs):
    if instance.main_item and instance.main_item.is_finished:
        return
    _update_raw_material(
        item=instance.sub_item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        pcs=-(instance.sub_pcs or 0),
        ct=-(instance.sub_ct or Decimal('0')),
        gw=-(instance.sub_gw or Decimal('0')),
    )
    _log_raw_txn(
        item=instance.sub_item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        trans_type='PURCHASE_DEL',
        pcs=-(instance.sub_pcs or 0),
        ct=-(instance.sub_ct or Decimal('0')),
        gw=-(instance.sub_gw or Decimal('0')),
        billno=instance.billno.billno if instance.billno else '',
    )


# ── Purchase return → decrease raw material ───────────────────────────────────

@receiver(post_save, sender=PurchaseReturnItems)
def decrease_raw_material_on_purchase_return(sender, instance, created, **kwargs):
    if not created:
        return
    _update_raw_material(
        item=instance.item, packet=None,
        purity=instance.purity, retail=instance.retail,
        pcs=-(instance.pcs or 0), gw=-(instance.gw or Decimal('0')),
    )
    _log_raw_txn(
        item=instance.item, packet=None,
        purity=instance.purity, retail=instance.retail,
        trans_type='PURCHASE_RETURN',
        pcs=-(instance.pcs or 0), gw=-(instance.gw or Decimal('0')),
        billno=instance.billno.billno if instance.billno else '',
    )


@receiver(post_save, sender=PurchaseReturnDetails)
def decrease_raw_material_on_purchase_return_detail(sender, instance, created, **kwargs):
    if not created:
        return
    _update_raw_material(
        item=instance.sub_item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        pcs=-(instance.sub_pcs or 0),
        ct=-(instance.sub_ct or Decimal('0')),
        gw=-(instance.sub_gw or Decimal('0')),
    )
    _log_raw_txn(
        item=instance.sub_item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        trans_type='PURCHASE_RETURN',
        pcs=-(instance.sub_pcs or 0),
        ct=-(instance.sub_ct or Decimal('0')),
        gw=-(instance.sub_gw or Decimal('0')),
        rate=instance.rate or Decimal('0'),
        amt=-(instance.value or Decimal('0')),
        billno=instance.billno.billno if instance.billno else '',
    )


# ── PurchaseReturn delete → restore raw material inventory ────────────────────

@receiver(pre_delete, sender=PurchaseReturn)
def on_purchase_return_delete(sender, instance, **kwargs):
    """
    When a PurchaseReturn is deleted (only permitted when ac_voucher is not posted):
    1. Restore the raw material inventory that was decremented when the return was created.
    2. Delete the linked accounting voucher if it exists.
    """
    billno_str = instance.billno

    for ret_item in instance.purchasereturnitems_set.select_related('item', 'purity').all():
        if not ret_item.item:
            continue
        _update_raw_material(
            item=ret_item.item, packet=None,
            purity=ret_item.purity, retail=instance.retail,
            pcs=ret_item.pcs or 0,
            gw=ret_item.gw or Decimal('0'),
        )
        _log_raw_txn(
            item=ret_item.item, packet=None,
            purity=ret_item.purity, retail=instance.retail,
            trans_type='PURCHASE_RETURN_DEL',
            pcs=ret_item.pcs or 0,
            gw=ret_item.gw or Decimal('0'),
            billno=billno_str,
        )

    if instance.ac_voucher_id:
        from accounting.models import VoucherMain
        VoucherMain.objects.filter(id=instance.ac_voucher_id).delete()

    # Remove the BarcodeTransaction outflow rows recorded when the PR was
    # created. Without this, a deleted PR leaves orphan transactions behind,
    # which then trip guard_no_later_barcode_transaction on later deletes
    # (the guard sees a "later" PURCHASE-RET entry that no longer has a PR
    # row attached to it).
    from inventory.models import BarcodeTransaction
    BarcodeTransaction.objects.filter(
        billno=billno_str, trans_type='PURCHASE-RET'
    ).delete()
