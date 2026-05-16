"""
Consolidate per-salesperson "Commission Payable - <name>" ledgers into a single
"Sales Incentive" ledger per retail and repoint every SalesPersonMaster.ledger
at it.

Old per-name ledgers are left in place to preserve audit trail of any commission
journal vouchers already posted against them.
"""

from django.db import migrations


def consolidate_payable_ledgers(apps, schema_editor):
    SalesPersonMaster = apps.get_model('mastersconfig', 'SalesPersonMaster')
    RetailMaster      = apps.get_model('mastersconfig', 'RetailMaster')
    Ledger            = apps.get_model('contacts',      'Ledger')
    LedgerRole        = apps.get_model('contacts',      'LedgerRole')
    Account           = apps.get_model('accounting',    'Account')

    sc_group = Account.objects.filter(code='CL-SC').first()
    shared_name = "Sales Incentive"

    retails_with_sp = (
        RetailMaster.objects
        .filter(id__in=SalesPersonMaster.objects.values_list('retail_id', flat=True).distinct())
    )

    for retail in retails_with_sp:
        # Reuse if a "Sales Incentive" ledger already exists for this retail,
        # otherwise create one under Sundry Creditors with the SC role.
        shared = (
            Ledger.objects
            .filter(retail_code=retail, ac_name=shared_name)
            .first()
        )
        if not shared:
            shared = Ledger.objects.create(
                ac_name=shared_name,
                display_name=shared_name,
                ac_group=sc_group,
                retail_code=retail,
                is_system=True,
            )
            LedgerRole.objects.create(ledger=shared, role='SC', is_primary=True)

        SalesPersonMaster.objects.filter(retail=retail).update(ledger=shared)


def reverse_noop(apps, schema_editor):
    # Cannot reliably reconstruct per-name ledgers; leave the consolidated state.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('mastersconfig', '0007_companymaster_legal_name'),
        ('contacts',      '0001_initial'),
        ('accounting',    '0001_initial'),
    ]

    operations = [
        migrations.RunPython(consolidate_payable_ledgers, reverse_noop),
    ]
