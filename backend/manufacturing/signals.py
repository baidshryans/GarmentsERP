from decimal import Decimal

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from inventory.models import RawMaterialInventory, RawMaterialTransaction, UnBarcodedDetails, UnBarcodedMain
from manufacturing.models import (
    KarigarGoldIssue, KarigarReceiveItem, KarigarReceiveItemDetails,
    KarigarStoneIssue, KarigarStoneReceive,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _update_raw_material(item, packet, purity, retail, pcs=0, ct=Decimal('0'), gw=Decimal('0')):
    """get_or_create an inventory row and adjust quantities."""
    rm, _ = RawMaterialInventory.objects.get_or_create(
        item=item, packet=packet, purity=purity, retail=retail,
        defaults={'pcs': 0, 'ct': Decimal('0'), 'gw': Decimal('0')},
    )
    rm.pcs += pcs
    rm.ct += ct
    rm.gw += gw
    rm.save()
    return rm


def _log_raw_txn(*, item, packet, purity, retail, trans_type, pcs=0, ct=Decimal('0'), gw=Decimal('0'),
                  rate=Decimal('0'), amt=Decimal('0'), billno=''):
    RawMaterialTransaction.objects.create(
        item=item, packet=packet, purity=purity, retail=retail,
        trans_type=trans_type, pcs=pcs, ct=ct, gw=gw,
        rate=rate, amt=amt, billno=billno,
    )


# ── Unbarcoded inventory from karigar receive (existing, kept as-is) ──────────

@receiver(post_save, sender=KarigarReceiveItem)
def create_unbarcoded_inventory(sender, instance, created, **kwargs):
    if created:
        unbarcoded_data = {
            "item": instance.item,
            "item_desc": str(instance.item),
            "pcs": instance.pcs,
            "gw": instance.gw,
            "nw": instance.nw,
            "purity": instance.purity,
            "value": None,
            "making_val": instance.making,
            "making_type": None,
            "other_chg": None,
            "design_code": None,
            "kr_code": None,
            "total_amount": 0,
            "size": None,
            "metal_color": None,
            "created_from": "KarigarReceiveItem",
            "customer_order": None,
            "created_by": "System",
            "stk_status": True,
            "voucher_no": None,
            "retail": instance.retail,
        }
        ubm = UnBarcodedMain.objects.create(**unbarcoded_data)
        for item in instance.ref_job_sl_no.issued_sample_items.all():
            item.next = ubm
            item.save()
        instance.unbarcoded_item = ubm
        instance.save()


@receiver(post_save, sender=KarigarReceiveItemDetails)
def create_unbarcoded_inventory_details(sender, instance, created, **kwargs):
    if created:
        UnBarcodedDetails.objects.create(
            main_item=instance.main_sl_no.unbarcoded_item,
            item=instance.item,
            pcs=instance.balance_pcs,
            gw=instance.balance_gw,
            ct=instance.balance_ct,
            rate=instance.rate,
            amt=instance.amt,
            packet=instance.packet,
        )


# ── Karigar gold issue → decrease raw material ────────────────────────────────

@receiver(post_save, sender=KarigarGoldIssue)
def reduce_raw_material_on_gold_issue(sender, instance, created, **kwargs):
    if not created:
        return
    _update_raw_material(
        item=instance.item, packet=None,
        purity=instance.metal_purity,
        retail=instance.header.retail,
        gw=-instance.item_gw,
    )
    _log_raw_txn(
        item=instance.item, packet=None,
        purity=instance.metal_purity,
        retail=instance.header.retail,
        trans_type='KR_GOLD_ISSUE',
        gw=-instance.item_gw,
        billno=instance.header.billno,
    )


@receiver(post_delete, sender=KarigarGoldIssue)
def reverse_raw_material_on_gold_issue_delete(sender, instance, **kwargs):
    _update_raw_material(
        item=instance.item, packet=None,
        purity=instance.metal_purity,
        retail=instance.header.retail,
        gw=instance.item_gw,
    )
    _log_raw_txn(
        item=instance.item, packet=None,
        purity=instance.metal_purity,
        retail=instance.header.retail,
        trans_type='KR_GOLD_ISSUE_DEL',
        gw=instance.item_gw,
        billno=instance.header.billno,
    )


# ── Karigar stone issue → decrease raw material ──────────────────────────────

@receiver(post_save, sender=KarigarStoneIssue)
def reduce_raw_material_on_stone_issue(sender, instance, created, **kwargs):
    if not created:
        return
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=None, retail=instance.header.retail,
        pcs=-instance.pcs, ct=-instance.ct, gw=-instance.gw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=None, retail=instance.header.retail,
        trans_type='KR_STONE_ISSUE',
        pcs=-instance.pcs, ct=-instance.ct, gw=-instance.gw,
        rate=instance.rate, amt=-instance.tot_val,
        billno=instance.header.billno,
    )


@receiver(post_delete, sender=KarigarStoneIssue)
def reverse_raw_material_on_stone_issue_delete(sender, instance, **kwargs):
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=None, retail=instance.header.retail,
        pcs=instance.pcs, ct=instance.ct, gw=instance.gw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=None, retail=instance.header.retail,
        trans_type='KR_STONE_ISSUE_DEL',
        pcs=instance.pcs, ct=instance.ct, gw=instance.gw,
        billno=instance.header.billno,
    )


# ── Karigar stone receive → increase raw material ────────────────────────────

@receiver(post_save, sender=KarigarStoneReceive)
def increase_raw_material_on_stone_receive(sender, instance, created, **kwargs):
    if not created:
        return
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=None, retail=instance.header.retail,
        pcs=instance.return_pcs, ct=instance.return_ct, gw=instance.return_gw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=None, retail=instance.header.retail,
        trans_type='KR_STONE_RETURN',
        pcs=instance.return_pcs, ct=instance.return_ct, gw=instance.return_gw,
        rate=instance.rate, amt=instance.tot_val or Decimal('0'),
        billno=instance.header.billno,
    )


@receiver(post_delete, sender=KarigarStoneReceive)
def reverse_raw_material_on_stone_receive_delete(sender, instance, **kwargs):
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=None, retail=instance.header.retail,
        pcs=-instance.return_pcs, ct=-instance.return_ct, gw=-instance.return_gw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=None, retail=instance.header.retail,
        trans_type='KR_STONE_RETURN_DEL',
        pcs=-instance.return_pcs, ct=-instance.return_ct, gw=-instance.return_gw,
        billno=instance.header.billno,
    )
