"""Backfill: rewrite document-linked accounting voucher numbers to use the
source document's billno instead of the legacy PURC-SC/SALE/PURC-RET/SALE-RET
sequence numbers.

Going forward (see JournalEntrySerializer) the accounting JV reuses the
purchase/sale/return billno directly. This migration aligns existing rows so
the P&L drilldown and ledger reports stop showing "PURC-SC/R001/..." for
purchases that the user knows as "PV/V/R001/...".
"""

from django.db import migrations


def rewrite_voucher_numbers(apps, schema_editor):
    VoucherMain      = apps.get_model('accounting', 'VoucherMain')
    PurchaseVoucher  = apps.get_model('purchase',   'PurchaseVoucher')

    # Purchase main JVs → use PurchaseVoucher.billno
    for pv in PurchaseVoucher.objects.exclude(ac_voucher__isnull=True).select_related('ac_voucher'):
        jv = pv.ac_voucher
        if jv and jv.voucher_no != pv.billno:
            # Guard against collisions (shouldn't happen — purchase billno is unique)
            if not VoucherMain.objects.exclude(id=jv.id).filter(voucher_no=pv.billno).exists():
                jv.voucher_no = pv.billno
                jv.save(update_fields=['voucher_no'])

    # Purchase TDS JVs → use "<billno>/TDS"
    for pv in PurchaseVoucher.objects.exclude(tds_ac_voucher__isnull=True).select_related('tds_ac_voucher'):
        jv = pv.tds_ac_voucher
        target = f"{pv.billno}/TDS"
        if jv and jv.voucher_no != target:
            if not VoucherMain.objects.exclude(id=jv.id).filter(voucher_no=target).exists():
                jv.voucher_no = target
                jv.save(update_fields=['voucher_no'])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0006_historicalvoucherdetail_historicalvouchermain'),
        ('purchase',   '0001_initial'),
    ]

    operations = [
        migrations.RunPython(rewrite_voucher_numbers, reverse_noop),
    ]
