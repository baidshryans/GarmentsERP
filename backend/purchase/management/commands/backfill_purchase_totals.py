"""
Recompute cgst/sgst/igst, total_incl_gst, bill_value, and due_amt for
already-migrated PurchaseVoucher rows where totals were calculated incorrectly.

Root cause: the old ERP's sub_total (imported as item_total) already included
hallmark charges. The original _apply_gst pass then added hallmark a second time
when building the total, causing total_incl_gst and bill_value to be overstated
by the hallmark amount on every voucher that had hallmark charges.

Fix: use tds_taxable_value (bare SUM of item_value lines) as the GST base and
add charges exactly once.

Formulas applied:
  gst_base        = tds_taxable_value + hallmark + freight + add_chrg1 + add_chrg2 - discount
  cgst/sgst/igst  = gst_base × rate from HSN master
  total_incl_gst  = gst_base + cgst + sgst + igst        (excl. TCS and round-off)
  bill_value      = total_incl_gst + tcs_amt + round_off  (gross payable)
  due_amt         = bill_value - amount_already_paid
                    where amount_paid = old bill_value - old due_amt

Usage:
  python manage.py backfill_purchase_totals           # dry-run
  python manage.py backfill_purchase_totals --apply   # write to DB
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from purchase.models import PurchaseVoucher
from accounting.migration_utils import hsn_for_voucher_items, split_gst


class Command(BaseCommand):
    help = "Recompute totals on migrated PurchaseVoucher rows (fixes hallmark double-count)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Write changes to the database (default: dry-run).',
        )

    def handle(self, *args, **opts):
        apply = opts['apply']
        updated = skipped = errors = 0

        qs = PurchaseVoucher.objects.select_related('hsn').all()

        for pv in qs.iterator(chunk_size=200):
            try:
                old_bill   = Decimal(str(pv.bill_value or 0))
                old_due    = Decimal(str(pv.due_amt    or 0))
                amount_paid = max(old_bill - old_due, Decimal('0'))

                cgst = sgst = igst = Decimal('0')

                if pv.voucher_type != 'Customer' and pv.hsn:
                    gst_base = (
                        Decimal(str(pv.tds_taxable_value or 0))
                        + Decimal(str(pv.hallmark_charge or 0))
                        + Decimal(str(pv.freight_amt    or 0))
                        + Decimal(str(pv.add_chrg_amt1  or 0))
                        + Decimal(str(pv.add_chrg_amt2  or 0))
                        - Decimal(str(pv.discount_amt   or 0))
                    )
                    is_central = bool(pv.igst) and not (pv.cgst or pv.sgst)
                    cgst, sgst, igst = split_gst(gst_base, pv.hsn, is_central)
                else:
                    # Customer voucher or no HSN — no GST, base = charges only
                    gst_base = (
                        Decimal(str(pv.tds_taxable_value or 0))
                        + Decimal(str(pv.hallmark_charge or 0))
                        + Decimal(str(pv.freight_amt    or 0))
                        + Decimal(str(pv.add_chrg_amt1  or 0))
                        + Decimal(str(pv.add_chrg_amt2  or 0))
                        - Decimal(str(pv.discount_amt   or 0))
                    )

                total_incl_gst = gst_base + cgst + sgst + igst
                bill_value     = total_incl_gst + Decimal(str(pv.tcs_amt or 0)) + Decimal(str(pv.round_off or 0))
                due_amt        = max(bill_value - amount_paid, Decimal('0'))

                if apply:
                    PurchaseVoucher.objects.filter(pk=pv.pk).update(
                        cgst=cgst, sgst=sgst, igst=igst,
                        total_incl_gst=total_incl_gst,
                        bill_value=bill_value,
                        due_amt=due_amt,
                    )
                updated += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"voucher {pv.billno}: {exc}"))
                errors += 1

        mode = "APPLIED" if apply else "DRY-RUN"
        self.stdout.write(self.style.SUCCESS(
            f"[{mode}] updated={updated} skipped={skipped} errors={errors}"
        ))
        if not apply:
            self.stdout.write(self.style.WARNING("Re-run with --apply to persist changes."))
