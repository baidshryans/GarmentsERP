"""
Tests: release_last_bill_number on post_delete for manufacturing voucher types.

For each representative model we:
  1. Create TWO vouchers via save_with_bill_number (numbers …00001, …00002).
  2. Delete the LATEST (…00002).
  3. Assert peek_next_bill_number returns …00002 again (number was freed).

  1. Create TWO vouchers.
  2. Delete the FIRST (…00001, non-latest).
  3. Assert peek returns …00003 (sequence unchanged, delete succeeded).

Covered models:
  RefinaryIssue    (REF/ISS)
  KarigarGoldIssueHeader (IV/GL)  -- representative Karigar voucher
  SampleIssue      (IS)
  MeltingReceive   (MLT/REC)
  KarigarReceive   (RS)
"""

import datetime

from django.test import TestCase

from accounting.utils import peek_next_bill_number, save_with_bill_number
from contacts.models import Ledger
from mastersconfig.models import FiscalYearMaster, RetailMaster, SystemSettings
from manufacturing.models import (
    KarigarGoldIssueHeader,
    KarigarReceive,
    MeltingReceive,
    RefinaryIssue,
    SampleIssue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_retail_and_fy(code: str):
    retail = RetailMaster.objects.create(
        retail_name=f"Test {code}",
        retail_code=code,
        phone="0000000000",
        address_line1="Test",
    )
    fy = FiscalYearMaster.objects.create(
        fy_code="25-26",
        fy_start=datetime.date(2025, 4, 1),
        fy_end=datetime.date(2026, 3, 31),
    )
    SystemSettings.set_company_active_fy(fy)
    return retail, fy


def _make_ledger(name: str):
    return Ledger.objects.create(
        ac_name=name,
        display_name=name,
        b2b=False,
        tds_applicable=False,
        is_system=False,
    )


# ---------------------------------------------------------------------------
# RefinaryIssue (REF/ISS)
# ---------------------------------------------------------------------------

class RefinaryIssueReleaseOnDeleteTest(TestCase):
    PREFIX = "REF/ISS"

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("RIRD")
        self.ldgr = _make_ledger("Ref Vendor RIRD")

    def _make(self):
        inst = RefinaryIssue(
            date1=datetime.date(2025, 4, 1),
            ldgr=self.ldgr,
            retail=self.retail,
            fiscal_year=self.fy,
            rec_status=False,
        )
        save_with_bill_number(inst, self.retail, self.PREFIX, field="billno", fy=self.fy)
        return inst

    def test_deleting_latest_frees_number(self):
        """Delete the last voucher → peek returns its number again."""
        v1 = self._make()
        v2 = self._make()
        self.assertTrue(v2.billno.endswith("00002"))

        v2.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00002"),
            f"Expected next to end in 00002 after deleting latest, got {nxt!r}",
        )

    def test_deleting_non_latest_leaves_sequence_unchanged(self):
        """Delete the first voucher (non-latest) → sequence not decremented."""
        v1 = self._make()
        v2 = self._make()
        self.assertTrue(v2.billno.endswith("00002"))

        v1.delete()  # non-latest — must not raise, must not decrement

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00003"),
            f"Expected next to end in 00003 after deleting non-latest, got {nxt!r}",
        )


# ---------------------------------------------------------------------------
# KarigarGoldIssueHeader (IV/GL) — representative Karigar voucher
# ---------------------------------------------------------------------------

class KarigarGoldIssueReleaseOnDeleteTest(TestCase):
    PREFIX = "IV/GL"

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("KGRD")
        self.karigar = _make_ledger("Karigar KGRD")

    def _make(self):
        inst = KarigarGoldIssueHeader(
            billno="",
            date1=datetime.date(2025, 4, 1),
            slip_type="JO",
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(inst, self.retail, self.PREFIX, field="billno", fy=self.fy)
        return inst

    def test_deleting_latest_frees_number(self):
        v1 = self._make()
        v2 = self._make()
        self.assertTrue(v2.billno.endswith("00002"))

        v2.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00002"),
            f"Expected next to end in 00002, got {nxt!r}",
        )

    def test_deleting_non_latest_leaves_sequence_unchanged(self):
        v1 = self._make()
        v2 = self._make()

        v1.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00003"),
            f"Expected next to end in 00003, got {nxt!r}",
        )


# ---------------------------------------------------------------------------
# SampleIssue (IS)
# ---------------------------------------------------------------------------

class SampleIssueReleaseOnDeleteTest(TestCase):
    PREFIX = "IS"

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("SIRD")
        self.karigar = _make_ledger("Sample Karigar SIRD")

    def _make(self):
        inst = SampleIssue(
            billno="",
            date1=datetime.date(2025, 4, 1),
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(inst, self.retail, self.PREFIX, field="billno", fy=self.fy)
        return inst

    def test_deleting_latest_frees_number(self):
        v1 = self._make()
        v2 = self._make()
        self.assertTrue(v2.billno.endswith("00002"))

        v2.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00002"),
            f"Expected next to end in 00002, got {nxt!r}",
        )

    def test_deleting_non_latest_leaves_sequence_unchanged(self):
        v1 = self._make()
        v2 = self._make()

        v1.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00003"),
            f"Expected next to end in 00003, got {nxt!r}",
        )


# ---------------------------------------------------------------------------
# MeltingReceive (MLT/REC)
# ---------------------------------------------------------------------------

class MeltingReceiveReleaseOnDeleteTest(TestCase):
    PREFIX = "MLT/REC"

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("MRRD")
        self.ldgr = _make_ledger("Melting Vendor MRRD")

    def _make(self):
        inst = MeltingReceive(
            billno="",
            date1=datetime.date(2025, 4, 1),
            ldgr=self.ldgr,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(inst, self.retail, self.PREFIX, field="billno", fy=self.fy)
        return inst

    def test_deleting_latest_frees_number(self):
        v1 = self._make()
        v2 = self._make()
        self.assertTrue(v2.billno.endswith("00002"))

        v2.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00002"),
            f"Expected next to end in 00002, got {nxt!r}",
        )

    def test_deleting_non_latest_leaves_sequence_unchanged(self):
        v1 = self._make()
        v2 = self._make()

        v1.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00003"),
            f"Expected next to end in 00003, got {nxt!r}",
        )


# ---------------------------------------------------------------------------
# KarigarReceive (RS)
# ---------------------------------------------------------------------------

class KarigarReceiveReleaseOnDeleteTest(TestCase):
    PREFIX = "RS"

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("KRRD")
        self.karigar = _make_ledger("KR Karigar KRRD")

    def _make(self):
        inst = KarigarReceive(
            receive_slip_no="",
            date1=datetime.date(2025, 4, 1),
            karigar_ldgr=self.karigar,
            place_of_supply="Maharashtra",
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(inst, self.retail, self.PREFIX, field="receive_slip_no", fy=self.fy)
        return inst

    def test_deleting_latest_frees_number(self):
        v1 = self._make()
        v2 = self._make()
        self.assertTrue(v2.receive_slip_no.endswith("00002"))

        v2.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00002"),
            f"Expected next to end in 00002, got {nxt!r}",
        )

    def test_deleting_non_latest_leaves_sequence_unchanged(self):
        v1 = self._make()
        v2 = self._make()

        v1.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00003"),
            f"Expected next to end in 00003, got {nxt!r}",
        )
