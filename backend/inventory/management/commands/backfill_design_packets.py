"""
Backfill DesignDetails.packet from barcode lines.

Designs seeded before packet copying existed have stone lines with no packet
FK, which makes them invisible to the catalog stone-swap simulator. For each
packet-less DesignDetails line, look at the design's barcodes and copy the
packet from a BarcodeDetails line of the same item (preferring an exact ct
match). Idempotent; dry-run by default, --apply to write.
"""

from django.core.management.base import BaseCommand

from inventory.models import BarcodeDetails, DesignDetails


class Command(BaseCommand):
    help = "Copy packet FKs from barcode detail lines onto packet-less design detail lines."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")

    def handle(self, *args, **opts):
        apply = opts["apply"]
        filled = skipped = 0

        lines = (
            DesignDetails.objects.filter(packet__isnull=True)
            .select_related("design_no", "sub_item")
        )
        for dd in lines.iterator():
            match = (
                BarcodeDetails.objects.filter(
                    barcode__design=dd.design_no, item=dd.sub_item, packet__isnull=False,
                )
                .select_related("packet")
                .order_by("id")
            )
            bd = match.filter(ct=dd.ct).first() or match.first()
            if bd is None:
                skipped += 1
                continue
            filled += 1
            self.stdout.write(
                f"design {dd.design_no.design_no} [{dd.design_no_id}] line {dd.id} "
                f"({dd.sub_item.item_name}, {dd.ct} ct) → packet {bd.packet.pckt_no}"
            )
            if apply:
                dd.packet = bd.packet
                dd.save(update_fields=["packet"])

        mode = "APPLIED" if apply else "DRY RUN (use --apply to write)"
        self.stdout.write(self.style.SUCCESS(
            f"{mode}: {filled} lines filled, {skipped} lines with no matching barcode packet."
        ))
