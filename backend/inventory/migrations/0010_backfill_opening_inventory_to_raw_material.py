from decimal import Decimal
from django.db import migrations


def backfill_opening_to_raw_material(apps, schema_editor):
    OpeningInventory = apps.get_model('inventory', 'OpeningInventory')
    RawMaterialInventory = apps.get_model('inventory', 'RawMaterialInventory')

    for entry in OpeningInventory.objects.all():
        rm, created = RawMaterialInventory.objects.get_or_create(
            item=entry.item,
            packet=entry.packet,
            purity=entry.purity,
            retail=entry.retail,
            defaults={
                'pcs': entry.pcs,
                'ct': Decimal(str(entry.ct)),
                'gw': Decimal(str(entry.gw)),
            },
        )
        if not created:
            rm.pcs += entry.pcs
            rm.ct += Decimal(str(entry.ct))
            rm.gw += Decimal(str(entry.gw))
            rm.save()


def reverse_backfill(apps, schema_editor):
    OpeningInventory = apps.get_model('inventory', 'OpeningInventory')
    RawMaterialInventory = apps.get_model('inventory', 'RawMaterialInventory')

    for entry in OpeningInventory.objects.all():
        try:
            rm = RawMaterialInventory.objects.get(
                item=entry.item,
                packet=entry.packet,
                purity=entry.purity,
                retail=entry.retail,
            )
            rm.pcs -= entry.pcs
            rm.ct -= Decimal(str(entry.ct))
            rm.gw -= Decimal(str(entry.gw))
            rm.save()
        except RawMaterialInventory.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0009_openinginventory_ldgr_nullable'),
    ]

    operations = [
        migrations.RunPython(backfill_opening_to_raw_material, reverse_backfill),
    ]
