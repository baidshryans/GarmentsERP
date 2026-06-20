"""
Seed / repair the Design tables from existing barcodes so the catalog has a
permanent, design-driven base (a design stays available even when no physical
barcode is in stock).

Design identity is **(item, design_no)** — company-global, NOT scoped by retail.
A bracelet `/1` and a ring `/1` are different designs.

What it does:
  1. De-dup: collapse any DesignMain rows that share the same (item, design_no)
     (legacy per-retail seeding created these) — keep the lowest-id canonical,
     relink its duplicates' barcodes, delete the empty duplicates (skipped if a
     duplicate has images, which can't be auto-merged).
  2. For each distinct (item, design_code) on BarcodeMain, get-or-create the
     DesignMain (building DesignDetails from a representative barcode) and link
     every barcode in the group to it — including barcodes currently linked to
     the wrong design.

Idempotent: re-running creates nothing new and relinks nothing.

Usage:
    python manage.py seed_designs                 # dry-run (no writes)
    python manage.py seed_designs --apply         # write to DB
    python manage.py seed_designs --apply --retail 3   # only scan one branch's barcodes
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models import Count

from inventory.models import BarcodeMain, DesignMain
from inventory.design_linking import get_or_create_design_for_barcode


class Command(BaseCommand):
    help = "Create/repair DesignMain from existing barcodes (identity = item + design_no) and link barcodes."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Actually write to the DB. Without this flag the command is a dry-run.")
        parser.add_argument("--retail", type=int, default=None,
                            help="Optional retail id to limit which barcodes are scanned (not the design key).")

    def handle(self, *args, **opts):
        apply_changes = opts["apply"]
        retail_id = opts["retail"]

        qs = (
            BarcodeMain.objects
            .exclude(design_code="")
            .exclude(design_code__isnull=True)
            .select_related("item", "purity", "kr_code", "retail")
        )
        if retail_id is not None:
            qs = qs.filter(retail_id=retail_id)

        # Group barcodes by (item, design_code) — retail plays no part in identity.
        groups = defaultdict(list)
        skipped_no_item = 0
        for bc in qs:
            if bc.item_id is None:
                skipped_no_item += 1
                continue
            groups[(bc.item_id, bc.design_code.strip())].append(bc)

        dupes_removed = 0
        created_designs = 0
        relinked = 0

        # ── 1. De-dup existing DesignMain by (item, design_no) ──────────────────
        if apply_changes:
            dup_keys = (
                DesignMain.objects.values("item_id", "design_no")
                .annotate(c=Count("id")).filter(c__gt=1)
            )
            for k in dup_keys:
                rows = list(
                    DesignMain.objects.filter(item_id=k["item_id"], design_no=k["design_no"]).order_by("id")
                )
                canonical = rows[0]
                for dup in rows[1:]:
                    if dup.images.exists():
                        self.stdout.write(
                            f"  SKIP merge design_no={dup.design_no!r} item={dup.item_id}: duplicate has images."
                        )
                        continue
                    relinked += BarcodeMain.objects.filter(design=dup).update(design=canonical)
                    dup.delete()   # cascades DesignDetails of the empty duplicate
                    dupes_removed += 1
        else:
            dupes_removed = sum(
                k["c"] - 1
                for k in DesignMain.objects.values("item_id", "design_no")
                .annotate(c=Count("id")).filter(c__gt=1)
            )

        # ── 2. Create missing designs + (re)link barcodes ───────────────────────
        for (item_id, code), bcs in groups.items():
            if not code:
                continue
            existed = DesignMain.objects.filter(item_id=item_id, design_no=code).exists()

            if apply_changes:
                design = get_or_create_design_for_barcode(bcs[0])
                if design is None:
                    continue
                if not existed:
                    created_designs += 1
                ids = [b.id for b in bcs]
                relinked += BarcodeMain.objects.filter(id__in=ids).exclude(design=design).update(design=design)
            else:
                if not existed:
                    created_designs += 1
                design = DesignMain.objects.filter(item_id=item_id, design_no=code).first()
                did = design.id if design else None
                relinked += sum(1 for b in bcs if b.design_id != did)

        mode = "APPLIED" if apply_changes else "DRY-RUN (no writes)"
        self.stdout.write(self.style.SUCCESS(
            f"\n[{mode}] (item, design_no) groups: {len(groups)} | "
            f"duplicate designs {'removed' if apply_changes else 'to remove'}: {dupes_removed} | "
            f"designs {'created' if apply_changes else 'to create'}: {created_designs} | "
            f"barcodes {'relinked' if apply_changes else 'to relink'}: {relinked} | "
            f"skipped (no item): {skipped_no_item}"
        ))
        if not apply_changes:
            self.stdout.write("Re-run with --apply to write these changes.")
