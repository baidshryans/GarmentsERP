"""
Tests: release_last_bill_number on post_delete for Quotation (QT).

1. Create TWO quotations via save_with_bill_number (numbers …00001, …00002).
2. Delete the LATEST → assert peek_next_bill_number returns …00002 again.
3. Create TWO; delete the FIRST (non-latest) → assert peek returns …00003
   and the delete succeeded without exception.
"""

import datetime

from django.test import TestCase

from accounting.utils import peek_next_bill_number, save_with_bill_number
from contacts.models import Ledger
from mastersconfig.models import FiscalYearMaster, RetailMaster

from .models import Quotation


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
        retail=retail,
        fy_code="25-26",
        fy_start=datetime.date(2025, 4, 1),
        fy_end=datetime.date(2026, 3, 31),
    )
    retail.active_fy = fy
    retail.save(update_fields=["active_fy"])
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
# Quotation (QT)
# ---------------------------------------------------------------------------

class QuotationReleaseOnDeleteTest(TestCase):
    PREFIX = "QT"

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("QTRD")
        self.customer = _make_ledger("Customer QTRD")

    def _make(self):
        inst = Quotation(
            quotation_no="",
            date1=datetime.date(2025, 4, 1),
            party_name="Walk-in",
            status="draft",
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(
            inst, self.retail, self.PREFIX, field="quotation_no", fy=self.fy
        )
        return inst

    def test_deleting_latest_frees_number(self):
        """Delete the last quotation → peek returns its number again."""
        v1 = self._make()
        v2 = self._make()
        self.assertTrue(
            v2.quotation_no.endswith("00002"),
            f"Second quotation should end in 00002, got {v2.quotation_no!r}",
        )

        v2.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00002"),
            f"Expected next to end in 00002 after deleting latest, got {nxt!r}",
        )

    def test_deleting_non_latest_leaves_sequence_unchanged(self):
        """Delete the first quotation (non-latest) → sequence not decremented."""
        v1 = self._make()
        v2 = self._make()
        self.assertTrue(v2.quotation_no.endswith("00002"), v2.quotation_no)

        v1.delete()  # non-latest — must not raise, must not decrement

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00003"),
            f"Expected next to end in 00003 after deleting non-latest, got {nxt!r}",
        )
