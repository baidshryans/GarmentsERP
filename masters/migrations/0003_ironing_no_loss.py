from django.db import migrations


def set_ironing(apps, schema_editor):
    apps.get_model("masters", "Process").objects.filter(code="IRON").update(no_loss=True)


class Migration(migrations.Migration):
    dependencies = [("masters", "0002_process_no_loss")]
    operations = [migrations.RunPython(set_ironing, migrations.RunPython.noop)]
