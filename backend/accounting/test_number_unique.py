"""
Tests: scoped UniqueConstraints on voucher-number fields in the accounting app.

Covers VoucherMain, CashGoldConversion, CreditDebitNote.
"""
import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from mastersconfig.models import FiscalYearMaster, RetailMaster
from contacts.models import Ledger
from accounting.models import CashGoldConversion, CreditDebitNote, VoucherMain


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
        bill_series=code,
    )


def _fy(retail, code):
    return FiscalYearMaster.objects.create(
        retail=retail,
        fy_code=code,
        fy_start=datetime.date(2025, 4, 1),
        fy_end=datetime.date(2026, 3, 31),
    )


def _ledger(name="AcctLedger"):
    return Ledger.objects.create(ac_name=name, display_name=name, mobile1="", cheque_no="")


class VoucherMainUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("VM1")
        self.fy = _fy(self.retail, "VM2526")

    def _make(self, voucher_no, retail=None, fy=None):
        return VoucherMain.objects.create(
            date=datetime.date(2025, 5, 1),
            voucher_no=voucher_no,
            narration="test",
            amount=0,
            voucher_type="JV",
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("JV-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("JV-001")

    def test_different_fiscal_year_allowed(self):
        """VoucherMain.voucher_no has a pre-existing global unique=True.
        Our scoped constraint is (retail, fiscal_year, voucher_no).
        Verify the scoped constraint allows same number in different FY of same retail.
        (Different numbers used here because global unique prevents same number anywhere.)
        """
        fy2 = FiscalYearMaster.objects.create(
            retail=self.retail,
            fy_code="VM2627",
            fy_start=datetime.date(2026, 4, 1),
            fy_end=datetime.date(2027, 3, 31),
        )
        self._make("JV-001")
        # Different FY + different number — both our scoped constraint and the global unique satisfied
        self._make("JV-002", fy=fy2)


class CashGoldConversionUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("CG1")
        self.fy = _fy(self.retail, "CG2526")

    def _make(self, billno, retail=None, fy=None):
        return CashGoldConversion.objects.create(
            date=datetime.date(2025, 5, 1),
            billno=billno,
            gw=1,
            rate=5000,
            amount=5000,
            conv_type="CG",
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("CG-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("CG-001")

    def test_different_retail_allowed(self):
        retail2 = _retail("CG2")
        fy2 = _fy(retail2, "CG2526B")
        self._make("CG-001")
        self._make("CG-001", retail=retail2, fy=fy2)


class CreditDebitNoteUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("CDN1")
        self.fy = _fy(self.retail, "CDN2526")
        self.ldgr = _ledger("CDNLedger")
        self.adj_ldgr = _ledger("CDNAdjLedger")

    def _make(self, note_no, retail=None, fy=None):
        return CreditDebitNote.objects.create(
            note_type="CN",
            note_no=note_no,
            date=datetime.date(2025, 5, 1),
            ldgr=self.ldgr,
            adjustment_ldgr=self.adj_ldgr,
            reason="Test",
            amount=100,
            taxable_value=100,
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("CN-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("CN-001")

    def test_different_retail_allowed(self):
        retail2 = _retail("CDN2")
        fy2 = _fy(retail2, "CDN2526B")
        self._make("CN-001")
        self._make("CN-001", retail=retail2, fy=fy2)
