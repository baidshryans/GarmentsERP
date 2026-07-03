"""
Tests: scoped UniqueConstraints on voucher-number fields in the inventory app.

Covers StockTransfer and StockJournal.
"""
import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from mastersconfig.models import FiscalYearMaster, RetailMaster
from inventory.models import StockJournal, StockTransfer


def _retail(code):
    return RetailMaster.objects.create(
        retail_name=f"Retail {code}",
        retail_code=code,
        address_line1="A",
        address_line2="",
        address_line3="",
        city="City",
        pincode="000000",
        phone="0",
    )


def _fy(retail, code):
    # active FY is company-global now; `retail` arg kept for call-site clarity.
    return FiscalYearMaster.objects.create(
        fy_code=code,
        fy_start=datetime.date(2025, 4, 1),
        fy_end=datetime.date(2026, 3, 31),
    )


class StockJournalUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("SJ1")
        self.fy = _fy(self.retail, "SJ2526")

    def _make(self, billno, retail=None, fy=None):
        return StockJournal.objects.create(
            date1=datetime.date(2025, 5, 1),
            billno=billno,
            remarks="",
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("SJ-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("SJ-001")

    def test_different_retail_allowed(self):
        retail2 = _retail("SJ2")
        fy2 = _fy(retail2, "SJ2526B")
        self._make("SJ-001")
        self._make("SJ-001", retail=retail2, fy=fy2)


class StockTransferUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("ST1")
        self.fy = _fy(self.retail, "ST2526")

    def _make(self, billno, retail=None, fy=None):
        return StockTransfer.objects.create(
            date1=datetime.date(2025, 5, 1),
            billno=billno,
            sent_status=False,
            rec_status=False,
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("ST-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("ST-001")

    def test_different_retail_allowed(self):
        retail2 = _retail("ST2")
        fy2 = _fy(retail2, "ST2526B")
        self._make("ST-001")
        self._make("ST-001", retail=retail2, fy=fy2)
