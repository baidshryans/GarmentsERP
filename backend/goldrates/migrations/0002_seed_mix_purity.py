from django.db import migrations


def seed_mix_purity(apps, schema_editor):
    PurityMaster = apps.get_model('goldrates', 'PurityMaster')
    PurityMaster.objects.get_or_create(purity='Mix', defaults={'gw_per': 0})


def remove_mix_purity(apps, schema_editor):
    PurityMaster = apps.get_model('goldrates', 'PurityMaster')
    PurityMaster.objects.filter(purity='Mix', gw_per=0).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('goldrates', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_mix_purity, remove_mix_purity),
    ]
