"""
Backfill RawMaterialInventory for existing PurchaseVoucherDetails rows where
main_item_id is null (raw-material-only purchase vouchers).  These were not
covered by the original backfill_raw_material management command if the
vouchers were created after that command was last run.

Deduplication: skip any detail whose (item, packet, purity, retail, billno,
ct, gw, pcs) already has a matching PURCHASE transaction — that row was already
counted by a prior backfill.
"""
from decimal import Decimal
from django.db import migrations


def _d(v):
    return Decimal(str(v)) if v is not None else Decimal('0')


def backfill_purchase_details(apps, schema_editor):
    PVD = apps.get_model('purchase', 'PurchaseVoucherDetails')
    RMI = apps.get_model('inventory', 'RawMaterialInventory')
    RMT = apps.get_model('inventory', 'RawMaterialTransaction')

    for pvd in PVD.objects.filter(main_item__isnull=True).select_related(
        'sub_item', 'packet', 'metal_purity', 'billno', 'retail'
    ):
        if not pvd.sub_item:
            continue

        billno = pvd.billno.billno if pvd.billno else ''
        pcs = pvd.sub_pcs or 0
        ct = _d(pvd.sub_ct)
        gw = _d(pvd.sub_gw)

        already_logged = RMT.objects.filter(
            item=pvd.sub_item,
            packet=pvd.packet,
            purity=pvd.metal_purity,
            retail=pvd.retail,
            trans_type='PURCHASE',
            billno=billno,
            pcs=pcs,
            ct=ct,
            gw=gw,
        ).exists()
        if already_logged:
            continue

        rm, created = RMI.objects.get_or_create(
            item=pvd.sub_item,
            packet=pvd.packet,
            purity=pvd.metal_purity,
            retail=pvd.retail,
            defaults={'pcs': pcs, 'ct': ct, 'gw': gw},
        )
        if not created:
            rm.pcs += pcs
            rm.ct += ct
            rm.gw += gw
            rm.save()

        RMT.objects.create(
            item=pvd.sub_item,
            packet=pvd.packet,
            purity=pvd.metal_purity,
            retail=pvd.retail,
            trans_type='PURCHASE',
            pcs=pcs,
            ct=ct,
            gw=gw,
            rate=_d(pvd.rate),
            amt=_d(pvd.value),
            billno=billno,
        )


def reverse_backfill(apps, schema_editor):
    pass  # non-reversible; manual correction needed if rolled back


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0010_backfill_opening_inventory_to_raw_material'),
        ('purchase', '__first__'),
    ]

    operations = [
        migrations.RunPython(backfill_purchase_details, reverse_backfill),
    ]
