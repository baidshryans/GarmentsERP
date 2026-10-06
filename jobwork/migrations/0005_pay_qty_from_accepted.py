from django.db import migrations
from django.db.models import F


def fill(apps, schema_editor):
    """Every QC result so far was paid on accepted pieces."""
    apps.get_model("jobwork", "QcResult").objects.update(pay_qty=F("accepted"))
    apps.get_model("jobwork", "HistoricalQcResult").objects.update(pay_qty=F("accepted"))


class Migration(migrations.Migration):
    dependencies = [("jobwork", "0004_pay_basis")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
