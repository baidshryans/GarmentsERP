from django.db import migrations


def add_scheme_advances_group(apps, schema_editor):
    Account = apps.get_model('accounting', 'Account')
    parent = Account.objects.filter(code='CL').first()
    Account.objects.get_or_create(
        code='CL-SCH',
        defaults={'name': 'Scheme Advances', 'parent': parent, 'can_be_deleted': False},
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0005_fixedasset_last_depreciation_through'),
    ]
    operations = [migrations.RunPython(add_scheme_advances_group, noop)]
