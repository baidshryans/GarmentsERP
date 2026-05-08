"""
One-time backfill: insert the missing gold/metal sub-item row in
`barcode_details` for every BarcodeMain that has a NW > 0 but no row
with packet IS NULL (the gold line).

Background:
    The barcode-create form skipped the gold line when
    pvGoldItemRef.current was null (manual barcodes / certain prefill
    paths). The frontend bug is now fixed — this command repairs the
    rows that were saved before the fix.

Usage:
    python manage.py backfill_barcode_gold_line           # dry-run
    python manage.py backfill_barcode_gold_line --apply   # write to DB
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import BarcodeMain, BarcodeDetails, Item


class Command(BaseCommand):
    help = "Backfill the missing gold sub-item row in barcode_details for existing barcodes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually write the rows. Without this flag the command runs as a dry-run.",
        )
        parser.add_argument(
            "--barcode",
            type=str,
            default=None,
            help="Optional single barcode to backfill (e.g. 6325751665891).",
        )

    def handle(self, *args, **opts):
        apply_changes = opts["apply"]
        single = opts.get("barcode")

        try:
            gold_item = Item.objects.get(short_code="Gold")
        except Item.DoesNotExist:
            raise CommandError("No Item with short_code='Gold' found.")

        qs = BarcodeMain.objects.select_related("item", "purity").all()
        if single:
            qs = qs.filter(barcode=single)

        to_create = []
        skipped_no_purity = 0
        skipped_zero_nw = 0
        skipped_already_has = 0

        for bm in qs:
            if BarcodeDetails.objects.filter(barcode=bm, packet__isnull=True).exists():
                skipped_already_has += 1
                continue
            if bm.nw is None or bm.nw <= 0:
                skipped_zero_nw += 1
                continue
            if bm.purity_id is None:
                skipped_no_purity += 1
                continue

            to_create.append(
                BarcodeDetails(
                    barcode=bm,
                    packet=None,
                    item=gold_item,
                    purity=bm.purity,
                    pcs=0,
                    ct=0,
                    gw=bm.nw,
                    rate=0,
                    amt=0,
                )
            )

        self.stdout.write(self.style.NOTICE(
            f"Scanned {qs.count()} barcodes. "
            f"To create: {len(to_create)}. "
            f"Already had gold line: {skipped_already_has}. "
            f"Skipped (no purity): {skipped_no_purity}. "
            f"Skipped (nw<=0): {skipped_zero_nw}."
        ))

        if not to_create:
            self.stdout.write(self.style.SUCCESS("Nothing to do."))
            return

        for d in to_create[:10]:
            self.stdout.write(
                f"  + {d.barcode.barcode}  item={d.item.short_code}  "
                f"purity={d.purity.purity}  gw={d.gw}"
            )
        if len(to_create) > 10:
            self.stdout.write(f"  ... and {len(to_create) - 10} more")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("Dry-run. Re-run with --apply to write."))
            return

        with transaction.atomic():
            BarcodeDetails.objects.bulk_create(to_create)

        self.stdout.write(self.style.SUCCESS(f"Inserted {len(to_create)} gold sub-item rows."))
