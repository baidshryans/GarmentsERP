"""Tests for the legacy barcode transaction / split-merge import + op_stk reconcile."""
import datetime

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from goldrates.models import PurityMaster
from mastersconfig.models import RetailMaster, Item
from inventory.models import BarcodeMain, BarcodeTransaction, BarcodeSplitMerge
from inventory.legacy_barcode_import import (
    map_trans_type, parse_dt, parse_d, build_lookups,
    import_transactions, reconcile_op_stk, import_split_merge,
)


# ─── fixtures ─────────────────────────────────────────────────────────────────

def _retail(code="R001"):
    return RetailMaster.objects.create(
        retail_name=f"Store {code}", retail_code=code,
        address_line1="x", phone="1", bill_series=f"S-{code}")


def _item():
    return Item.objects.create(short_code="RNG", item_name="Ring",
                               item_type="M", uom="Gm", show_in_pcs_report=False)


def _purity(value="14"):
    return PurityMaster.objects.create(purity=value, gw_per=__import__("decimal").Decimal("0.585"))


def _barcode(code, item, retail, purity, **kw):
    return BarcodeMain.objects.create(barcode=code, item=item, retail=retail, purity=purity, **kw)


def _txn_row(id, barcode, tran_type, date1="2026-04-01", billno="x",
             user_id="Suhrid Santra", ip="192.168.0.10", rt_code="R001"):
    return {"id": id, "barcode": barcode, "tran_type": tran_type, "date1": date1,
            "billno": billno, "user_id": user_id, "ip": ip, "rt_code": rt_code}


def _sm_row(id, old_barcode, new_barcode, date1="2026-04-18", rt_code="R001"):
    return {"id": id, "old_barcode": old_barcode, "new_barcode": new_barcode,
            "date1": date1, "rt_code": rt_code}


# ─── Task 2: map_trans_type ───────────────────────────────────────────────────

class MapTransTypeTests(TestCase):
    def test_exact_codes_unchanged(self):
        for code in ("SALE", "SALE-RET", "TRF-RR-IN", "TRF-RR-OUT"):
            self.assertEqual(map_trans_type(code), (code, True))

    def test_renamed_codes(self):
        self.assertEqual(map_trans_type("SALE-APPR"), ("SALE-APP", True))
        self.assertEqual(map_trans_type("APPR-RET"), ("SALE-APP-RET", True))
        self.assertEqual(map_trans_type("BAR-SPLT"), ("BAR-SPLIT", True))
        self.assertEqual(map_trans_type("BAR-SPLT-CRT"), ("BAR-SPLIT-CRT", True))
        self.assertEqual(map_trans_type("NEW-BAR"), ("CREATE-PUR", True))
        self.assertEqual(map_trans_type("PR"), ("PURCHASE-RET", True))

    def test_history_only_codes_kept(self):
        for code in ("OP-STK", "EST", "ISS-ST"):
            self.assertEqual(map_trans_type(code), (code, True))

    def test_unknown_code_kept_and_flagged(self):
        self.assertEqual(map_trans_type("WAT"), ("WAT", False))

    def test_whitespace_stripped(self):
        self.assertEqual(map_trans_type("  SALE  "), ("SALE", True))


# ─── Task 3: date parsing ─────────────────────────────────────────────────────

class DateParsingTests(TestCase):
    def test_parse_dt_from_date_string(self):
        dt = parse_dt("2026-04-01")
        self.assertEqual((dt.year, dt.month, dt.day), (2026, 4, 1))
        self.assertFalse(timezone.is_naive(dt))

    def test_parse_dt_from_datetime_string(self):
        dt = parse_dt("2026-05-17 00:00:00")
        self.assertEqual((dt.year, dt.month, dt.day), (2026, 5, 17))
        self.assertFalse(timezone.is_naive(dt))

    def test_parse_dt_blank_falls_back_to_now(self):
        self.assertIsNotNone(parse_dt(""))
        self.assertIsNotNone(parse_dt(None))

    def test_parse_d_returns_date(self):
        self.assertEqual(parse_d("2026-04-18"), datetime.date(2026, 4, 18))

    def test_parse_d_from_datetime(self):
        self.assertEqual(parse_d("2026-06-06 00:00:00"), datetime.date(2026, 6, 6))


# ─── Task 4: build_lookups ────────────────────────────────────────────────────

class BuildLookupsTests(TestCase):
    def test_lookups_index_by_code_and_name(self):
        r = _retail("R001")
        it = _item()
        p = _purity()
        bm = _barcode("100A", it, r, p)
        U = get_user_model()
        u = U.objects.create_user(username="ssantra", first_name="Suhrid", last_name="Santra")
        barcodes, retails, users = build_lookups()
        self.assertEqual(barcodes["100A"].id, bm.id)
        self.assertEqual(retails["R001"].id, r.id)
        self.assertEqual(users["Suhrid Santra"].id, u.id)
        self.assertEqual(users["ssantra"].id, u.id)


# ─── Task 5: import_transactions ──────────────────────────────────────────────

class ImportTransactionsTests(TestCase):
    def setUp(self):
        self.r = _retail("R001")
        self.it = _item()
        self.p = _purity()
        self.bc = _barcode("100A", self.it, self.r, self.p)
        self.barcodes, self.retails, self.users = build_lookups()

    def _run(self, rows, apply=True):
        return import_transactions(rows, self.barcodes, self.retails, self.users, apply=apply)

    def test_creates_row_with_mapped_type_and_real_date(self):
        stats = self._run([_txn_row(1, "100A", "SALE-APPR", date1="2026-05-17")])
        self.assertEqual(stats["created"], 1)
        t = BarcodeTransaction.objects.get(legacy_key="1")
        self.assertEqual(t.trans_type, "SALE-APP")
        self.assertEqual(t.date.date().isoformat(), "2026-05-17")
        self.assertEqual(t.barcode_id, self.bc.id)
        self.assertEqual(t.retail_id, self.r.id)

    def test_idempotent(self):
        self._run([_txn_row(1, "100A", "SALE")])
        self._run([_txn_row(1, "100A", "SALE")])
        self.assertEqual(BarcodeTransaction.objects.filter(legacy_key="1").count(), 1)

    def test_unmatched_barcode_skipped_and_reported(self):
        stats = self._run([_txn_row(2, "NOPE", "SALE")])
        self.assertEqual(stats["created"], 0)
        self.assertIn("NOPE", stats["unmatched"])

    def test_unknown_code_kept_verbatim_and_flagged(self):
        stats = self._run([_txn_row(3, "100A", "WAT")])
        self.assertEqual(BarcodeTransaction.objects.get(legacy_key="3").trans_type, "WAT")
        self.assertIn("WAT", stats["unmapped"])

    def test_dry_run_writes_nothing(self):
        stats = self._run([_txn_row(4, "100A", "SALE")], apply=False)
        self.assertEqual(stats["created"], 1)
        self.assertFalse(BarcodeTransaction.objects.filter(legacy_key="4").exists())


# ─── Task 6: reconcile_op_stk ─────────────────────────────────────────────────

class ReconcileOpStkTests(TestCase):
    def setUp(self):
        self.r = _retail("R001")
        self.it = _item()
        self.p = _purity()
        self.op = _barcode("OPN", self.it, self.r, self.p, op_stk=True, op_retail=self.r)
        self.newbar = _barcode("NEW", self.it, self.r, self.p, op_stk=True, op_retail=self.r)
        self.untouched = _barcode("OTHER", self.it, self.r, self.p, op_stk=True)
        self.barcodes, self.retails, _ = build_lookups()

    def test_op_stk_true_only_for_op_stk_rows(self):
        rows = [
            _txn_row(1, "OPN", "OP-STK"),
            _txn_row(2, "NEW", "NEW-BAR"),
            _txn_row(3, "NEW", "SALE"),
        ]
        reconcile_op_stk(rows, self.barcodes, self.retails, apply=True)
        self.op.refresh_from_db(); self.newbar.refresh_from_db(); self.untouched.refresh_from_db()
        self.assertTrue(self.op.op_stk)
        self.assertFalse(self.newbar.op_stk)
        self.assertTrue(self.untouched.op_stk)

    def test_sets_op_retail_from_opstk_row(self):
        r2 = _retail("R002")
        self.barcodes, self.retails, _ = build_lookups()
        reconcile_op_stk([_txn_row(1, "OPN", "OP-STK", rt_code="R002")],
                         self.barcodes, self.retails, apply=True)
        self.op.refresh_from_db()
        self.assertEqual(self.op.op_retail_id, r2.id)


# ─── Task 7: import_split_merge ───────────────────────────────────────────────

class ImportSplitMergeTests(TestCase):
    def setUp(self):
        self.r = _retail("R001")
        self.it = _item()
        self.p = _purity()
        self.child = _barcode("100A", self.it, self.r, self.p)
        self.barcodes, self.retails, _ = build_lookups()

    def _run(self, rows, kind="Split", apply=True):
        return import_split_merge(rows, kind, self.barcodes, self.retails, apply=apply)

    def test_split_links_child_parent_null_when_absent(self):
        stats = self._run([_sm_row(1, "100", "100A", date1="2026-04-18")])
        self.assertEqual(stats["created"], 1)
        sm = BarcodeSplitMerge.objects.get(legacy_key="split:1")
        self.assertEqual(sm.transaction_type, "Split")
        self.assertIsNone(sm.old_barcode_id)
        self.assertEqual(sm.new_barcode_id, self.child.id)
        self.assertEqual(sm.date1.isoformat(), "2026-04-18")

    def test_skips_when_both_missing(self):
        stats = self._run([_sm_row(2, "X", "Y")])
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["skipped_both_missing"], 1)

    def test_idempotent(self):
        self._run([_sm_row(1, "100", "100A")])
        self._run([_sm_row(1, "100", "100A")])
        self.assertEqual(BarcodeSplitMerge.objects.filter(legacy_key="split:1").count(), 1)

    def test_merge_kind_uses_merge_prefix(self):
        self._run([_sm_row(1, "100", "100A")], kind="Merge")
        self.assertTrue(BarcodeSplitMerge.objects.filter(legacy_key="merge:1",
                                                         transaction_type="Merge").exists())


# ─── Task 8: management command (CSV) ─────────────────────────────────────────

import csv
import os
import tempfile
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError


def _write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


class CommandCsvTests(TestCase):
    def setUp(self):
        self.r = _retail("R001")
        self.it = _item()
        self.p = _purity()
        self.bc = _barcode("100A", self.it, self.r, self.p, op_stk=True, op_retail=self.r)
        self.tmp = tempfile.mkdtemp()

    def _txn_csv(self):
        p = os.path.join(self.tmp, "txn.csv")
        _write_csv(p, ["id", "date1", "barcode", "billno", "tran_type", "user_id",
                       "ip", "rt_code"],
                   [_txn_row(1, "100A", "SALE", date1="2026-05-01")])
        return p

    def test_dry_run_writes_nothing(self):
        out = StringIO()
        call_command("import_barcode_transactions", "--txn-csv", self._txn_csv(), stdout=out)
        self.assertEqual(BarcodeTransaction.objects.count(), 0)
        self.assertIn("DRY RUN", out.getvalue())

    def test_apply_creates_rows(self):
        out = StringIO()
        call_command("import_barcode_transactions", "--txn-csv", self._txn_csv(),
                     "--apply", stdout=out)
        self.assertEqual(BarcodeTransaction.objects.filter(legacy_key="1").count(), 1)

    def test_requires_a_source(self):
        with self.assertRaises(CommandError):
            call_command("import_barcode_transactions")

    def test_accepts_migration_endpoint_kwargs(self):
        # MigrationImportView always passes apply/continue_on_error/report_dir.
        out = StringIO()
        call_command("import_barcode_transactions", txn_csv=self._txn_csv(),
                     apply=True, continue_on_error=True, report_dir=self.tmp, stdout=out)
        self.assertEqual(BarcodeTransaction.objects.filter(legacy_key="1").count(), 1)


# ─── Reset scope (Clear migrated data) ────────────────────────────────────────

from rest_framework.test import APIRequestFactory, force_authenticate
from accounting.views.migration import MigrationResetView


class ResetScopeTests(TestCase):
    def setUp(self):
        self.r = _retail("R001")
        self.it = _item()
        self.p = _purity()
        self.bc = _barcode("100A", self.it, self.r, self.p)
        # one legacy-imported txn + one live txn
        self.legacy_txn = BarcodeTransaction.objects.create(
            barcode=self.bc, billno="x", trans_type="SALE", ip_address="0.0.0.0",
            retail=self.r, legacy_key="1")
        self.live_txn = BarcodeTransaction.objects.create(
            barcode=self.bc, billno="y", trans_type="SALE", ip_address="0.0.0.0",
            retail=self.r)  # legacy_key stays NULL
        self.legacy_sm = BarcodeSplitMerge.objects.create(
            transaction_type="Split", new_barcode=self.bc, retail=self.r, legacy_key="split:1")
        self.live_sm = BarcodeSplitMerge.objects.create(
            transaction_type="Split", new_barcode=self.bc, retail=self.r)

    def _reset(self, apply):
        rf = APIRequestFactory()
        U = get_user_model()
        user = U.objects.create_user(username="admin", password="x", is_staff=True, is_superuser=True)
        req = rf.post("/x", {"scope": ["barcode_transactions"]}, format="json")
        force_authenticate(req, user=user)
        return MigrationResetView.as_view()(req)

    def test_dry_run_deletes_nothing(self):
        resp = self._reset(apply=False)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(BarcodeTransaction.objects.count(), 2)
        self.assertEqual(BarcodeSplitMerge.objects.count(), 2)

    def test_apply_deletes_only_legacy_rows(self):
        # the view reads ?apply=true from query params
        rf = APIRequestFactory()
        U = get_user_model()
        user = U.objects.create_user(username="admin2", password="x", is_staff=True, is_superuser=True)
        req = rf.post("/x?apply=true", {"scope": ["barcode_transactions"]}, format="json")
        force_authenticate(req, user=user)
        resp = MigrationResetView.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(BarcodeTransaction.objects.filter(legacy_key="1").exists())
        self.assertTrue(BarcodeTransaction.objects.filter(pk=self.live_txn.pk).exists())
        self.assertFalse(BarcodeSplitMerge.objects.filter(legacy_key="split:1").exists())
        self.assertTrue(BarcodeSplitMerge.objects.filter(pk=self.live_sm.pk).exists())


# ─── Stock report: NULL split-parent must not zero the report ──────────────────

from inventory.views import StockReportView


class StockReportNullSplitParentTests(TestCase):
    def test_null_old_barcode_does_not_zero_report(self):
        r = _retail("R001")
        it = _item()
        p = _purity()
        _barcode("OPN", it, r, p, op_stk=True, op_retail=r, pcs=1)
        # A split whose parent barcode was consumed -> old_barcode is NULL. This
        # used to poison the report's NOT IN (...) subqueries (SQL three-valued
        # logic) and zero every item.
        BarcodeSplitMerge.objects.create(
            transaction_type="Split", old_barcode=None, new_barcode=None, retail=r)
        U = get_user_model()
        user = U.objects.create_user(username="rep", password="x", is_superuser=True, is_staff=True)
        rf = APIRequestFactory()
        # far-future as_on so the (auto_now_add) created_date is always <= as_on
        req = rf.get("/x", {"as_on_date": "2099-01-01"})
        force_authenticate(req, user=user)
        req.retail = r
        resp = StockReportView.as_view()(req)
        self.assertTrue(any(row.get("stock_count", 0) > 0 for row in resp.data),
                        "report was zeroed by a NULL-parent split record")
