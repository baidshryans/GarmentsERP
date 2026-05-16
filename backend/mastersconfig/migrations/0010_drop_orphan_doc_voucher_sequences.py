"""Drop BillNumberSequence rows for prefixes that no longer increment.

Document-linked accounting voucher types (PURC-SC / SALE / PURC-RET / SALE-RET)
now reuse the source document's billno as their voucher_no, so their own
sequences are never advanced. The rows are harmless but stale — delete them
for clarity.
"""

from django.db import migrations


DEAD_PREFIXES = ['PURC-SC', 'SALE', 'PURC-RET', 'SALE-RET']


def delete_orphan_sequences(apps, schema_editor):
    BillNumberSequence = apps.get_model('mastersconfig', 'BillNumberSequence')
    BillNumberSequence.objects.filter(prefix__in=DEAD_PREFIXES).delete()


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('mastersconfig', '0009_remove_salespersonmaster_ledger'),
    ]

    operations = [
        migrations.RunPython(delete_orphan_sequences, reverse_noop),
    ]
