"""
Tests: release_last_bill_number on post_delete for goldscheme voucher types.

SchemeEnrollment (SCHM-E) and SchemePayment (SCHM-P).

For each model:
  1. Create TWO vouchers via save_with_bill_number (numbers …00001, …00002).
  2. Delete the LATEST → assert peek returns …00002 (number freed).
  3. Create TWO; delete the FIRST (non-latest) → assert peek returns …00003
     and the delete succeeded without exception.
"""

import datetime

from django.test import TestCase

from accounting.utils import peek_next_bill_number, save_with_bill_number
from contacts.models import Ledger
from mastersconfig.models import FiscalYearMaster, RetailMaster

from .models import SchemeMaster, SchemeEnrollment, SchemePayment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_retail_and_fy(code: str):
    retail = RetailMaster.objects.create(
        retail_name=f"Test {code}",
        retail_code=code,
        phone="0000000000",
        address_line1="Test",
        bill_series=code,
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
# SchemeEnrollment (SCHM-E)
# ---------------------------------------------------------------------------

class SchemeEnrollmentReleaseOnDeleteTest(TestCase):
    PREFIX = "SCHM-E"

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("SERD")
        self.customer = _make_ledger("Customer SERD")
        self.scheme = SchemeMaster.objects.create(
            name="Test Scheme",
            scheme_code="TS-SERD",
            scheme_type="INSTALLMENT",
            gold_price_mode="CURRENT",
            tenure_months=11,
            min_amount=1000,
            is_active=True,
            retail=self.retail,
        )

    def _make(self, enrollment_no: str):
        inst = SchemeEnrollment(
            enrollment_no=enrollment_no,
            scheme=self.scheme,
            customer=self.customer,
            start_date=datetime.date(2025, 4, 1),
            maturity_date=datetime.date(2026, 3, 31),
            installment_amount=1000,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(
            inst, self.retail, self.PREFIX, field="enrollment_no", fy=self.fy
        )
        return inst

    def test_deleting_latest_frees_number(self):
        """Delete the last enrollment → peek returns its number again."""
        v1 = self._make("tmp1")
        v2 = self._make("tmp2")
        self.assertTrue(v2.enrollment_no.endswith("00002"), v2.enrollment_no)

        v2.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00002"),
            f"Expected next to end in 00002 after deleting latest, got {nxt!r}",
        )

    def test_deleting_non_latest_leaves_sequence_unchanged(self):
        """Delete the first enrollment (non-latest) → sequence not decremented."""
        v1 = self._make("tmp1")
        v2 = self._make("tmp2")
        self.assertTrue(v2.enrollment_no.endswith("00002"), v2.enrollment_no)

        v1.delete()  # non-latest delete must not raise and must not decrement

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00003"),
            f"Expected next to end in 00003 after deleting non-latest, got {nxt!r}",
        )


# ---------------------------------------------------------------------------
# SchemePayment (SCHM-P)
# ---------------------------------------------------------------------------

class SchemePaymentReleaseOnDeleteTest(TestCase):
    PREFIX = "SCHM-P"

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("SPRD")
        self.customer = _make_ledger("Customer SPRD")
        self.payment_ledger = _make_ledger("Cash SPRD")
        self.scheme = SchemeMaster.objects.create(
            name="Pay Scheme",
            scheme_code="PS-SPRD",
            scheme_type="INSTALLMENT",
            gold_price_mode="CURRENT",
            tenure_months=11,
            min_amount=1000,
            is_active=True,
            retail=self.retail,
        )
        # Create one enrollment to attach payments to
        self.enrollment = SchemeEnrollment.objects.create(
            enrollment_no="SCHM-E/SPRD/25-26/00001",
            scheme=self.scheme,
            customer=self.customer,
            start_date=datetime.date(2025, 4, 1),
            maturity_date=datetime.date(2026, 3, 31),
            installment_amount=1000,
            retail=self.retail,
            fiscal_year=self.fy,
        )

    def _make(self, tmp_no: str, inst_no: int):
        inst = SchemePayment(
            enrollment=self.enrollment,
            payment_no=tmp_no,
            date=datetime.date(2025, 4, inst_no),
            amount=1000,
            payment_mode="CASH",
            payment_ledger=self.payment_ledger,
            installment_number=inst_no,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        # Use save_with_bill_number to get a real sequence number.
        # The post_save signal (create_scheme_voucher) will fire but may fail
        # gracefully — that's expected in tests with no full accounting setup.
        save_with_bill_number(
            inst, self.retail, self.PREFIX, field="payment_no", fy=self.fy
        )
        return inst

    def test_deleting_latest_frees_number(self):
        """Delete the last payment → peek returns its number again."""
        v1 = self._make("tmp1", 1)
        v2 = self._make("tmp2", 2)
        self.assertTrue(v2.payment_no.endswith("00002"), v2.payment_no)

        v2.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00002"),
            f"Expected next to end in 00002 after deleting latest, got {nxt!r}",
        )

    def test_deleting_non_latest_leaves_sequence_unchanged(self):
        """Delete the first payment (non-latest) → sequence not decremented."""
        v1 = self._make("tmp1", 1)
        v2 = self._make("tmp2", 2)

        v1.delete()

        nxt = peek_next_bill_number(self.retail, self.PREFIX, self.fy)
        self.assertTrue(
            nxt.endswith("00003"),
            f"Expected next to end in 00003 after deleting non-latest, got {nxt!r}",
        )
