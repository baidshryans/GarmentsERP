"""Hard-remove the per-salesperson payable ledger FK.

All salespersons share a single 'Sales Incentive' ledger per retail
(resolved via ledger_utils.get_or_create_shared_incentive_ledger). The
column is dropped here.

Also deletes legacy 'Commission Payable - <name>' ledgers that no longer
have any salesperson or voucher detail referencing them.
"""

from django.db import migrations, models


def delete_orphan_legacy_ledgers(apps, schema_editor):
    Ledger = apps.get_model('contacts', 'Ledger')
    VoucherDetail = apps.get_model('accounting', 'VoucherDetail')

    legacy = Ledger.objects.filter(ac_name__startswith='Commission Payable - ')
    in_use = set(
        VoucherDetail.objects.filter(account__in=legacy).values_list('account_id', flat=True).distinct()
    )
    legacy.exclude(id__in=in_use).delete()


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('mastersconfig', '0008_consolidate_salesperson_payable_ledger'),
    ]

    operations = [
        migrations.RunPython(delete_orphan_legacy_ledgers, reverse_noop),
        migrations.RemoveField(
            model_name='salespersonmaster',
            name='ledger',
        ),
    ]
