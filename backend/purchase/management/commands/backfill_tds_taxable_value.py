"""
Backfill PurchaseVoucher.tds_taxable_value for already-migrated vouchers.

tds_taxable_value = SUM(PurchaseVoucherItems.item_value) for that voucher.
This is the bare line-item sum (excluding hallmark, freight, discount) and is
what the printed voucher shows as "Subtotal".

The migration import originally left this field at its default of 0. Run this
once after import to fix existing rows.

Usage:
  python manage.py backfill_tds_taxable_value           # dry-run (shows counts)
  python manage.py backfill_tds_taxable_value --apply   # write to DB
"""
from django.core.management.base import BaseCommand
from django.db.models import Sum
from purchase.models import PurchaseVoucher, PurchaseVoucherItems
from decimal import Decimal


class Command(BaseCommand):
    help = "Backfill tds_taxable_value on PurchaseVoucher rows where it is 0."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Write changes to the database (default: dry-run).',
        )

    def handle(self, *args, **opts):
        apply = opts['apply']

        # Aggregate item_value per voucher in one query.
        item_sums = dict(
            PurchaseVoucherItems.objects
            .values('billno_id')
            .annotate(total=Sum('item_value'))
            .values_list('billno_id', 'total')
        )

        qs = PurchaseVoucher.objects.filter(tds_taxable_value=0)
        total = qs.count()
        updated = 0

        for pv in qs.iterator(chunk_size=500):
            new_val = item_sums.get(pv.pk) or Decimal('0')
            if new_val == 0:
                continue  # no items at all — leave as 0
            if apply:
                PurchaseVoucher.objects.filter(pk=pv.pk).update(tds_taxable_value=new_val)
            updated += 1

        mode = "APPLIED" if apply else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] {updated}/{total} vouchers updated with tds_taxable_value."
        ))
        if not apply:
            self.stdout.write(self.style.WARNING(
                "Re-run with --apply to persist changes."
            ))
