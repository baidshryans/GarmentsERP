"""Locations are found by kind (owner, 19 Oct 2026): "Main Godown" becomes "Godown" and "Dispatch" becomes
"Ready Goods", unless the factory already has a location of that name."""
from django.db import migrations

RENAMES = (("Main Godown", "Godown"), ("Dispatch", "Ready Goods"))


def rename(apps, schema_editor):
    Location = apps.get_model("core", "Location")
    for old, new in RENAMES:
        for loc in Location.objects.filter(name=old):
            if not Location.objects.filter(factory_id=loc.factory_id, name=new).exists():
                loc.name = new
                loc.save(update_fields=["name"])


def rename_back(apps, schema_editor):
    Location = apps.get_model("core", "Location")
    for old, new in RENAMES:
        for loc in Location.objects.filter(name=new):
            if not Location.objects.filter(factory_id=loc.factory_id, name=old).exists():
                loc.name = old
                loc.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [("core", "0007_cutting_variance_label")]

    operations = [migrations.RunPython(rename, rename_back)]
