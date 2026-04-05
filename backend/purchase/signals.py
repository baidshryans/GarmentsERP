from decimal import Decimal

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from inventory.models import RawMaterialInventory, RawMaterialTransaction
from purchase.models import PurchaseVoucherItems, PurchaseVoucherDetails, PurchaseReturnItems, PurchaseReturnDetails


# ── helpers ────────────────────────────────────────────────────────────────────

def _update_raw_material(item, packet, purity, retail, pcs=0, ct=Decimal('0'), gw=Decimal('0')):
    rm, _ = RawMaterialInventory.objects.get_or_create(
        item=item, packet=packet, purity=purity, retail=retail,
        defaults={'pcs': 0, 'ct': Decimal('0'), 'gw': Decimal('0')},
    )
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


@receiver(post_delete, sender=PurchaseVoucherItems)
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


@receiver(post_save, sender=PurchaseVoucherDetails)
def increase_raw_material_on_purchase_detail(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.main_item and instance.main_item.is_finished:
        return
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
        billno=instance.billno.billno if instance.billno else '',
    )


@receiver(post_delete, sender=PurchaseVoucherDetails)
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
