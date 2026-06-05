"""
One-shot back-fill for sales-inline customer PurchaseVoucher rows where
branch_ref / gstin_ref were never persisted.

Affected rows: PurchaseVoucher with source='sales_inline' AND
              (branch_ref_id IS NULL OR gstin_ref_id IS NULL).

For each affected PV we copy branch_ref / gstin_ref from the parent SalesVou
(found via the SaleOldGoldAdjustment bridge). If the sale also has no
branch_ref / gstin_ref, we fall back to the PV's retail.branch / retail.gstin.

Usage from backend/ directory:
    python _backfill_inline_pv_branch_gstin.py            # dry-run (default)
    python _backfill_inline_pv_branch_gstin.py --commit   # apply changes
"""

import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jewel_test.settings")
django.setup()

from django.db import transaction
from django.db.models import Q

from purchase.models import PurchaseVoucher
from sales.models import SaleOldGoldAdjustment


def main():
    commit = "--commit" in sys.argv

    qs = PurchaseVoucher.objects.filter(source="sales_inline").filter(
        Q(branch_ref__isnull=True) | Q(gstin_ref__isnull=True)
    )
    total = qs.count()
    print(f"Found {total} sales-inline PV rows with missing branch_ref / gstin_ref.")
    if total == 0:
        return

    fixed_branch = 0
    fixed_gstin = 0
    skipped = 0
    sample = []

    with transaction.atomic():
        for pv in qs.select_related("retail", "branch_ref", "gstin_ref"):
            adj = SaleOldGoldAdjustment.objects.filter(purchase=pv).select_related(
                "sale", "sale__branch_ref", "sale__gstin_ref"
            ).first()
            sale = adj.sale if adj else None

            new_branch = pv.branch_ref
            new_gstin = pv.gstin_ref

            if new_branch is None:
                new_branch = (
                    getattr(sale, "branch_ref", None)
                    or getattr(pv.retail, "branch", None)
                )
            if new_gstin is None:
                new_gstin = (
                    getattr(sale, "gstin_ref", None)
                    or getattr(pv.retail, "gstin", None)
                )

            changed_fields = []
            if pv.branch_ref_id != getattr(new_branch, "id", None):
                pv.branch_ref = new_branch
                changed_fields.append("branch_ref")
            if pv.gstin_ref_id != getattr(new_gstin, "id", None):
                pv.gstin_ref = new_gstin
                changed_fields.append("gstin_ref")

            if not changed_fields:
                skipped += 1
                continue

            if "branch_ref" in changed_fields:
                fixed_branch += 1
            if "gstin_ref" in changed_fields:
                fixed_gstin += 1

            if len(sample) < 8:
                sample.append(
                    f"  PV {pv.billno or pv.pk}: "
                    f"branch={getattr(new_branch, 'name', new_branch)}, "
                    f"gstin={getattr(new_gstin, 'gstin', new_gstin)} "
                    f"[from sale {sale.billno if sale else 'n/a'}]"
                )

            if commit:
                pv.save(update_fields=changed_fields)

        print()
        print("Sample fixes:")
        for s in sample:
            print(s)

        print()
        print(f"  branch_ref to update: {fixed_branch}")
        print(f"  gstin_ref  to update: {fixed_gstin}")
        print(f"  no-op rows (no source available): {skipped}")

        if not commit:
            print()
            print("DRY-RUN — no changes saved. Re-run with --commit to apply.")
            transaction.set_rollback(True)
        else:
            print()
            print("COMMITTED.")


if __name__ == "__main__":
    main()
