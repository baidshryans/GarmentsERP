"""Import the old ERP's barcode_wise_all_transaction / barcode_split / barcode_merge
into BarcodeTransaction / BarcodeSplitMerge, and reconcile BarcodeMain.op_stk.

Dry-run by default; pass --apply to persist. Source is either CSV files
(--txn-csv/--split-csv/--merge-csv) or the legacy DB (--from-db, via settings.LEGACY_DB).
"""
import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.legacy_barcode_import import (
    build_lookups, import_transactions, reconcile_op_stk, import_split_merge,
    mark_consumed_barcodes,
)


def load_csv(path):
    """Read a CSV into a list of dicts. utf-8-sig handles Excel's BOM; headers and
    values are stripped, missing values become ''."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for raw in reader:
            rows.append({
                (k.strip() if k else k): ((v or "").strip())
                for k, v in raw.items()
            })
        return rows


def load_from_db():
    """Read all three tables from the legacy MySQL DB (settings.LEGACY_DB)."""
    from django.conf import settings
    cfg = getattr(settings, "LEGACY_DB", None)
    if not cfg:
        raise CommandError("--from-db requires a LEGACY_DB dict in settings "
                           "(HOST, NAME, USER, PASSWORD, optional PORT).")
    try:
        import pymysql
    except ImportError:
        raise CommandError("--from-db requires pymysql. Run: pip install pymysql")
    conn = pymysql.connect(
        host=cfg["HOST"], user=cfg["USER"], password=cfg["PASSWORD"],
        database=cfg["NAME"], port=int(cfg.get("PORT", 3306)),
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM barcode_wise_all_transaction")
            txn = cur.fetchall()
            cur.execute("SELECT * FROM barcode_split")
            splits = cur.fetchall()
            cur.execute("SELECT * FROM barcode_merge")
            merges = cur.fetchall()
    finally:
        conn.close()
    return list(txn), list(splits), list(merges)


class Command(BaseCommand):
    help = "Import legacy barcode movement + split/merge tables; reconcile op_stk."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist (default: dry run).")
        parser.add_argument("--from-db", action="store_true", help="Read from settings.LEGACY_DB.")
        parser.add_argument("--txn-csv", default=None)
        parser.add_argument("--split-csv", default=None)
        parser.add_argument("--merge-csv", default=None)
        # Accepted for parity with the migration import endpoint (which passes
        # these to every importer); this command is already per-row resilient and
        # reports to stdout, so they are no-ops here.
        parser.add_argument("--continue-on-error", action="store_true")
        parser.add_argument("--report-dir", default=None)

    def handle(self, *args, **o):
        apply = o["apply"]
        if o["from_db"]:
            txn_rows, split_rows, merge_rows = load_from_db()
        elif o["txn_csv"] or o["split_csv"] or o["merge_csv"]:
            txn_rows = load_csv(o["txn_csv"]) if o["txn_csv"] else []
            split_rows = load_csv(o["split_csv"]) if o["split_csv"] else []
            merge_rows = load_csv(o["merge_csv"]) if o["merge_csv"] else []
        else:
            raise CommandError("Provide --from-db or at least one of "
                               "--txn-csv / --split-csv / --merge-csv.")

        barcodes, retails, users = build_lookups()
        mode = "APPLY" if apply else "DRY RUN"
        self.stdout.write(self.style.MIGRATE_HEADING(f"\nBarcode legacy import — {mode}\n"))

        with transaction.atomic():
            t = import_transactions(txn_rows, barcodes, retails, users, apply=apply)
            op = reconcile_op_stk(txn_rows, barcodes, retails, apply=apply)
            s = import_split_merge(split_rows, "Split", barcodes, retails, apply=apply)
            m = import_split_merge(merge_rows, "Merge", barcodes, retails, apply=apply)
            c = mark_consumed_barcodes(apply=apply)
            if not apply:
                transaction.set_rollback(True)

        self.stdout.write(f"  transactions: created={t['created']} existing={t['existing']} "
                          f"unmatched_barcodes={len(t['unmatched'])}")
        if t["unmapped"]:
            self.stdout.write(self.style.WARNING(f"  unmapped trans_types: {t['unmapped']}"))
        self.stdout.write(f"  per_type: {t['per_type']}")
        self.stdout.write(f"  op_stk: set_true={op['set_true']} set_false={op['set_false']} "
                          f"missing={op['missing']}")
        self.stdout.write(f"  splits: created={s['created']} skipped_both_missing="
                          f"{s['skipped_both_missing']}")
        self.stdout.write(f"  merges: created={m['created']} skipped_both_missing="
                          f"{m['skipped_both_missing']}")
        self.stdout.write(f"  consumed (#SPL/#MER) barcodes flagged out of stock: {c['consumed_marked']}")
        if not apply:
            self.stdout.write(self.style.NOTICE("\nDry run — re-run with --apply to persist."))
