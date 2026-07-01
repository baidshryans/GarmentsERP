from decimal import Decimal

from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver

from inventory.models import RawMaterialInventory, RawMaterialTransaction, UnBarcodedDetails, UnBarcodedMain
from manufacturing.models import (
    KarigarGoldIssue, KarigarReceiveItem, KarigarReceiveItemDetails,
    KarigarStoneIssue, KarigarStoneReceive,
    RefinaryIssueDetail, RefinaryReceiveDetail,
    MeltingIssueDetail, MeltingReceiveDetail,
    SampleIssueItem,
    # Header / parent voucher models (for bill-number reclaim)
    RefinaryIssue, RefinaryReceive,
    MeltingIssue, MeltingReceive,
    HallmarkIssue, HallmarkReceive,
    RepairJobCard, SampleIssue,
    KarigarGoldIssueHeader, KarigarStoneIssueHeader, KarigarStoneReceiveHeader,
    KarigarIssue, KarigarReceive,
)
from purchase.models import PurchaseVoucherDetails


# ── helpers ────────────────────────────────────────────────────────────────────

def _update_raw_material(item, packet, purity, retail, pcs=0, ct=Decimal('0'), gw=Decimal('0')):
    """Adjust an inventory row's quantities; tolerates duplicate rows (NULL
    packet/purity bypass the unique_together) via get_or_merge."""
    rm = RawMaterialInventory.get_or_merge(item, packet, purity, retail)
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

@receiver(post_save, sender=KarigarReceiveItem,
          dispatch_uid='mfg_signals.create_unbarcoded_inventory')
def create_unbarcoded_inventory(sender, instance, created, **kwargs):
    if created and not instance.unbarcoded_item_id:
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
            "created_from": "KAR_REC",
            "customer_order": None,
            "created_by": "System",
            "stk_status": True,
            "voucher_no": None,
            "retail": instance.retail,
        }
        ubm = UnBarcodedMain.objects.create(**unbarcoded_data)
        if instance.ref_sample_issue_item_id:
            prev = instance.ref_sample_issue_item.piece
            prev.next = ubm
            prev.save(update_fields=['next'])
        instance.unbarcoded_item = ubm
        instance.save()


@receiver(post_delete, sender=KarigarReceiveItem,
          dispatch_uid='mfg_signals.delete_unbarcoded_inventory')
def delete_unbarcoded_inventory(sender, instance, **kwargs):
    """When a KarigarReceiveItem is deleted, also delete the UBM it created.
    Skip if a BarcodeMain already references the UBM (item was barcoded)."""
    ubm_id = instance.unbarcoded_item_id
    if not ubm_id:
        return
    from inventory.models import BarcodeMain
    if BarcodeMain.objects.filter(rec_item_id=instance.pk).exists():
        return
    UnBarcodedMain.objects.filter(pk=ubm_id).delete()


@receiver(post_save, sender=SampleIssueItem,
          dispatch_uid='mfg_signals.mark_piece_with_karigar')
def mark_piece_with_karigar(sender, instance, created, **kwargs):
    """When a piece is issued on a Sample Issue, mark it as currently with that karigar."""
    if created and instance.piece_id and instance.issue.karigar_ldgr_id:
        piece = instance.piece
        piece.kr_code = instance.issue.karigar_ldgr
        piece.save(update_fields=['kr_code'])


@receiver(post_delete, sender=SampleIssueItem,
          dispatch_uid='mfg_signals.unmark_piece_from_karigar')
def unmark_piece_from_karigar(sender, instance, **kwargs):
    """When a SampleIssueItem is removed (via update or SampleIssue delete), clear
    the piece's kr_code unless another live SampleIssueItem still references it."""
    if not instance.piece_id:
        return
    still_referenced = SampleIssueItem.objects.filter(
        piece_id=instance.piece_id
    ).exclude(pk=instance.pk).exists()
    if still_referenced:
        return
    try:
        piece = UnBarcodedMain.objects.get(pk=instance.piece_id)
    except UnBarcodedMain.DoesNotExist:
        return
    issue_karigar_id = getattr(instance.issue, 'karigar_ldgr_id', None) if instance.issue_id else None
    if issue_karigar_id is None or piece.kr_code_id == issue_karigar_id:
        piece.kr_code = None
        piece.save(update_fields=['kr_code'])


@receiver(post_save, sender=KarigarReceiveItemDetails,
          dispatch_uid='mfg_signals.create_unbarcoded_inventory_details')
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

@receiver(post_save, sender=KarigarGoldIssue,
          dispatch_uid='mfg_signals.reduce_raw_material_on_gold_issue')
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


@receiver(post_delete, sender=KarigarGoldIssue,
          dispatch_uid='mfg_signals.reverse_raw_material_on_gold_issue_delete')
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

@receiver(post_save, sender=KarigarStoneIssue,
          dispatch_uid='mfg_signals.reduce_raw_material_on_stone_issue')
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


@receiver(post_delete, sender=KarigarStoneIssue,
          dispatch_uid='mfg_signals.reverse_raw_material_on_stone_issue_delete')
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

@receiver(post_save, sender=KarigarStoneReceive,
          dispatch_uid='mfg_signals.increase_raw_material_on_stone_receive')
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


@receiver(post_delete, sender=KarigarStoneReceive,
          dispatch_uid='mfg_signals.reverse_raw_material_on_stone_receive_delete')
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


# ── Refinery Issue/Receive detail → raw material ─────────────────────────────
# (Closes a pre-existing gap: refinery operations did not update stock.)

@receiver(post_save, sender=RefinaryIssueDetail,
          dispatch_uid='mfg_signals.on_refinary_issue_detail_save')
def on_refinary_issue_detail_save(sender, instance, created, **kwargs):
    if not created:
        return
    # Raw metal rows (item_type == "R") carry no pcs/ct — treat them as 0.
    pcs = instance.pcs or 0
    ct = instance.ct or Decimal('0')
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        pcs=-pcs, ct=-ct, gw=-instance.gw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        trans_type='REF_ISS',
        pcs=-pcs, ct=-ct, gw=-instance.gw,
        billno=instance.billno.billno,
    )


@receiver(post_delete, sender=RefinaryIssueDetail,
          dispatch_uid='mfg_signals.on_refinary_issue_detail_delete')
def on_refinary_issue_detail_delete(sender, instance, **kwargs):
    pcs = instance.pcs or 0
    ct = instance.ct or Decimal('0')
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        pcs=pcs, ct=ct, gw=instance.gw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        trans_type='REF_ISS_DEL',
        pcs=pcs, ct=ct, gw=instance.gw,
        billno=instance.billno.billno,
    )


@receiver(post_save, sender=RefinaryReceiveDetail,
          dispatch_uid='mfg_signals.on_refinary_receive_detail_save')
def on_refinary_receive_detail_save(sender, instance, created, **kwargs):
    if not created:
        return
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=instance.conv_purity, retail=instance.retail,
        gw=instance.conv_nw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=instance.conv_purity, retail=instance.retail,
        trans_type='REF_REC',
        gw=instance.conv_nw,
        billno=instance.billno.billno,
    )


@receiver(post_delete, sender=RefinaryReceiveDetail,
          dispatch_uid='mfg_signals.on_refinary_receive_detail_delete')
def on_refinary_receive_detail_delete(sender, instance, **kwargs):
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=instance.conv_purity, retail=instance.retail,
        gw=-instance.conv_nw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=instance.conv_purity, retail=instance.retail,
        trans_type='REF_REC_DEL',
        gw=-instance.conv_nw,
        billno=instance.billno.billno,
    )


# ── Melting Issue/Receive detail → raw material ──────────────────────────────

@receiver(post_save, sender=MeltingIssueDetail,
          dispatch_uid='mfg_signals.on_melting_issue_detail_save')
def on_melting_issue_detail_save(sender, instance, created, **kwargs):
    if not created:
        return
    # Raw metal rows (item_type == "R") carry no pcs/ct — treat them as 0.
    pcs = instance.pcs or 0
    ct = instance.ct or Decimal('0')
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        pcs=-pcs, ct=-ct, gw=-instance.gw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        trans_type='MELT_ISS',
        pcs=-pcs, ct=-ct, gw=-instance.gw,
        billno=instance.billno.billno,
    )


@receiver(post_delete, sender=MeltingIssueDetail,
          dispatch_uid='mfg_signals.on_melting_issue_detail_delete')
def on_melting_issue_detail_delete(sender, instance, **kwargs):
    pcs = instance.pcs or 0
    ct = instance.ct or Decimal('0')
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        pcs=pcs, ct=ct, gw=instance.gw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        trans_type='MELT_ISS_DEL',
        pcs=pcs, ct=ct, gw=instance.gw,
        billno=instance.billno.billno,
    )


@receiver(post_save, sender=MeltingReceiveDetail,
          dispatch_uid='mfg_signals.on_melting_receive_detail_save')
def on_melting_receive_detail_save(sender, instance, created, **kwargs):
    if not created:
        return
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=instance.conv_purity, retail=instance.retail,
        gw=instance.conv_nw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=instance.conv_purity, retail=instance.retail,
        trans_type='MELT_REC',
        gw=instance.conv_nw,
        billno=instance.billno.billno,
    )


@receiver(post_delete, sender=MeltingReceiveDetail,
          dispatch_uid='mfg_signals.on_melting_receive_detail_delete')
def on_melting_receive_detail_delete(sender, instance, **kwargs):
    _update_raw_material(
        item=instance.item, packet=instance.packet,
        purity=instance.conv_purity, retail=instance.retail,
        gw=-instance.conv_nw,
    )
    _log_raw_txn(
        item=instance.item, packet=instance.packet,
        purity=instance.conv_purity, retail=instance.retail,
        trans_type='MELT_REC_DEL',
        gw=-instance.conv_nw,
        billno=instance.billno.billno,
    )


# ── Issue delete → cascade to only-source receive slips ──────────────────────
# Deleting an issue removes any receive slip that drew ONLY from it (header +
# all rows). Receives that also draw from other issues keep their header and
# their other-issue rows.
#
# The existing issue_no=CASCADE already deletes the receive DETAIL rows linked
# to this issue (reversing stock via their post_delete). We must NOT delete
# those rows again here (that would double-reverse stock and re-fire signals on
# a header that's already gone). So: stash the affected receive ids before the
# cascade runs, then in post_delete drop any header the cascade left empty.

@receiver(pre_delete, sender=MeltingIssue,
          dispatch_uid='mfg_signals.melting_issue_stash_receives')
def on_melting_issue_predelete(sender, instance, **kwargs):
    instance._cascade_receive_ids = list(
        MeltingReceive.objects
        .filter(meltingreceivedetail__issue_no=instance)
        .values_list('id', flat=True).distinct()
    )


@receiver(post_delete, sender=MeltingIssue,
          dispatch_uid='mfg_signals.melting_issue_cleanup_receives')
def on_melting_issue_postdelete(sender, instance, **kwargs):
    for rid in getattr(instance, '_cascade_receive_ids', []):
        receive = MeltingReceive.objects.filter(id=rid).first()
        if receive and not receive.meltingreceivedetail_set.exists():
            receive.delete()


# ── Raw material purchases (sub-item details with no main item) ────────────────

@receiver(post_save, sender=PurchaseVoucherDetails,
          dispatch_uid='mfg_signals.add_raw_material_on_purchase_detail_save')
def add_raw_material_on_purchase_detail_save(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.main_item_id is not None:
        return  # detail belongs to a finished-goods purchase, not raw material
    if not instance.sub_item:
        return
    pcs = instance.sub_pcs or 0
    ct = Decimal(str(instance.sub_ct or 0))
    gw = Decimal(str(instance.sub_gw or 0))
    _update_raw_material(
        item=instance.sub_item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        pcs=pcs, ct=ct, gw=gw,
    )
    _log_raw_txn(
        item=instance.sub_item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        trans_type='PURCHASE', pcs=pcs, ct=ct, gw=gw,
        rate=Decimal(str(instance.rate or 0)),
        amt=Decimal(str(instance.value or 0)),
        billno=instance.billno.billno if instance.billno else '',
    )


@receiver(post_delete, sender=PurchaseVoucherDetails,
          dispatch_uid='mfg_signals.reverse_raw_material_on_purchase_detail_delete')
def reverse_raw_material_on_purchase_detail_delete(sender, instance, **kwargs):
    if instance.main_item_id is not None:
        return
    if not instance.sub_item:
        return
    pcs = instance.sub_pcs or 0
    ct = Decimal(str(instance.sub_ct or 0))
    gw = Decimal(str(instance.sub_gw or 0))
    _update_raw_material(
        item=instance.sub_item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        pcs=-pcs, ct=-ct, gw=-gw,
    )
    _log_raw_txn(
        item=instance.sub_item, packet=instance.packet,
        purity=instance.metal_purity, retail=instance.retail,
        trans_type='PURCHASE_RETURN', pcs=-pcs, ct=-ct, gw=-gw,
        rate=Decimal(str(instance.rate or 0)),
        amt=Decimal(str(instance.value or 0)),
        billno=instance.billno.billno if instance.billno else '',
    )


# ── Bill-number reclaim on parent-voucher delete ─────────────────────────────
# Each receiver below calls release_last_bill_number so that deleting the
# MOST RECENT voucher in a series frees its number for the next entry.
# Mid-sequence deletes are safe no-ops (release_last_bill_number checks
# that the trailing integer matches last_number before decrementing).

from accounting.utils import release_last_bill_number  # noqa: E402


@receiver(post_delete, sender=RefinaryIssue, dispatch_uid='mfg_signals.release_refissue')
def _release_refissue(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'REF/ISS', instance.billno, instance.fiscal_year)


@receiver(post_delete, sender=RefinaryReceive, dispatch_uid='mfg_signals.release_refreceive')
def _release_refreceive(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'REF/REC', instance.billno, instance.fiscal_year)


@receiver(post_delete, sender=MeltingIssue, dispatch_uid='mfg_signals.release_meltissue')
def _release_meltissue(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'MLT/ISS', instance.billno, instance.fiscal_year)


@receiver(post_delete, sender=MeltingReceive, dispatch_uid='mfg_signals.release_meltreceive')
def _release_meltreceive(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'MLT/REC', instance.billno, instance.fiscal_year)


@receiver(post_delete, sender=HallmarkIssue, dispatch_uid='mfg_signals.release_hmkissue')
def _release_hmkissue(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'HMIS', instance.issue_slip_no, instance.fiscal_year)


@receiver(post_delete, sender=HallmarkReceive, dispatch_uid='mfg_signals.release_hmkreceive')
def _release_hmkreceive(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'HM/RE', instance.receive_slip_no, instance.fiscal_year)


@receiver(post_delete, sender=RepairJobCard, dispatch_uid='mfg_signals.release_rjc')
def _release_rjc(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'RJC', instance.rjc_no, instance.fiscal_year)


@receiver(post_delete, sender=SampleIssue, dispatch_uid='mfg_signals.release_sampleissue')
def _release_sampleissue(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'IS', instance.billno, instance.fiscal_year)


@receiver(post_delete, sender=KarigarGoldIssueHeader, dispatch_uid='mfg_signals.release_krgoldissue')
def _release_krgoldissue(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'IV/GL', instance.billno, instance.fiscal_year)


@receiver(post_delete, sender=KarigarStoneIssueHeader, dispatch_uid='mfg_signals.release_krstoneissue')
def _release_krstoneissue(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'IV/STN', instance.billno, instance.fiscal_year)


@receiver(post_delete, sender=KarigarStoneReceiveHeader, dispatch_uid='mfg_signals.release_krstonereceive')
def _release_krstonereceive(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'REC/STN', instance.billno, instance.fiscal_year)


@receiver(post_delete, sender=KarigarIssue, dispatch_uid='mfg_signals.release_krissue')
def _release_krissue(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'IV', instance.issue_slip_no, instance.fiscal_year)


@receiver(post_delete, sender=KarigarReceive, dispatch_uid='mfg_signals.release_krreceive')
def _release_krreceive(sender, instance, **kwargs):
    if getattr(instance, 'retail_id', None):
        release_last_bill_number(instance.retail, 'RS', instance.receive_slip_no, instance.fiscal_year)
