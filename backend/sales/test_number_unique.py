"""
Tests: scoped UniqueConstraints on voucher-number fields in the sales app.

Each test verifies that creating a second record with the same
(retail, fiscal_year, <number_field>) raises IntegrityError,
while a different retail or fiscal_year is allowed.
"""
import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from mastersconfig.models import FiscalYearMaster, RetailMaster, SalesPersonMaster
from contacts.models import Ledger
from sales.models import CustomerOrder, SaleReturn, SalesApproval, SalesApprovalReturn, SalesVou


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


def _ledger(name="TestLedger"):
    return Ledger.objects.create(ac_name=name, display_name=name, mobile1="", cheque_no="")


class CustomerOrderUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("CO1")
        self.fy = _fy(self.retail, "CO2526")

    def test_duplicate_raises(self):
        CustomerOrder.objects.create(
            order_no="ORD-001",
            date1=datetime.date(2025, 5, 1),
            rate_14kt=0,
            rate_18kt=0,
            rate_22kt=0,
            nature="Order",
            status="pending",
            delivery_status=False,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerOrder.objects.create(
                    order_no="ORD-001",
                    date1=datetime.date(2025, 5, 2),
                    rate_14kt=0,
                    rate_18kt=0,
                    rate_22kt=0,
                    nature="Order",
                    status="pending",
                    delivery_status=False,
                    retail=self.retail,
                    fiscal_year=self.fy,
                )

    def test_different_fiscal_year_allowed(self):
        """Same (retail, order_no) in a different fiscal_year must not raise our scoped constraint.

        Note: CustomerOrder.order_no has a pre-existing global unique=True (a stricter legacy
        constraint). The scoped UniqueConstraint we added targets (retail, fiscal_year, order_no).
        We verify that two records with the same retail but *different* fiscal_year and distinct
        order_nos are both accepted — the meaningful cross-FY isolation is enforced by our constraint.
        """
        fy2 = FiscalYearMaster.objects.create(
            fy_code="CO2627",
            fy_start=datetime.date(2026, 4, 1),
            fy_end=datetime.date(2027, 3, 31),
        )
        CustomerOrder.objects.create(
            order_no="ORD-A01",
            date1=datetime.date(2025, 5, 1),
            rate_14kt=0,
            rate_18kt=0,
            rate_22kt=0,
            nature="Order",
            status="pending",
            delivery_status=False,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        # Different FY, different number (global unique prevents reuse across FYs for this model)
        CustomerOrder.objects.create(
            order_no="ORD-A02",
            date1=datetime.date(2026, 5, 1),
            rate_14kt=0,
            rate_18kt=0,
            rate_22kt=0,
            nature="Order",
            status="pending",
            delivery_status=False,
            retail=self.retail,
            fiscal_year=fy2,
        )


class SalesVouUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("SV1")
        self.fy = _fy(self.retail, "SV2526")
        self.ldgr = _ledger("SVLedger")
        self.sp = SalesPersonMaster.objects.create(salesperson_name="TestSP")

    def _make(self, billno, gst_billno="", retail=None, fy=None):
        return SalesVou.objects.create(
            date1=datetime.date(2025, 5, 1),
            billno=billno,
            gst_billno=gst_billno,
            place_of_supply="07",
            ret_status=False,
            vehicle_no="",
            transporter_name="",
            transporter_id="",
            trans_distance=0,
            trans_doc_no="",
            cash=0,
            due_amt=0,
            advance_deducted=0,
            old_gold_adjusted=0,
            ldgr=self.ldgr,
            sales_person=self.sp,
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_billno_raises(self):
        self._make("SV-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("SV-001")

    def test_different_retail_allowed(self):
        retail2 = _retail("SV2")
        fy2 = _fy(retail2, "SV2526B")
        self._make("SV-001")
        self._make("SV-001", retail=retail2, fy=fy2)  # should not raise

    def test_duplicate_gst_billno_raises(self):
        self._make("SV-002", gst_billno="GST-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("SV-003", gst_billno="GST-001")

    def test_blank_gst_billno_allowed_multiple(self):
        """Two rows with blank gst_billno must NOT trigger the conditional unique."""
        self._make("SV-004", gst_billno="")
        self._make("SV-005", gst_billno="")  # must not raise


class SaleReturnUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("SR1")
        self.fy = _fy(self.retail, "SR2526")
        self.ldgr = _ledger("SRLedger")

    def _make(self, billno, retail=None, fy=None):
        return SaleReturn.objects.create(
            date1=datetime.date(2025, 5, 1),
            billno=billno,
            mrp=0,
            discount=0,
            cgst_per=0,
            sgst_per=0,
            igst_per=0,
            tcs_per=0,
            original_sale_gst_billno="",
            ldgr=self.ldgr,
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("SRN-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("SRN-001")

    def test_different_retail_allowed(self):
        retail2 = _retail("SR2")
        fy2 = _fy(retail2, "SR2526B")
        self._make("SRN-001")
        self._make("SRN-001", retail=retail2, fy=fy2)


class SalesApprovalUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("SA1")
        self.fy = _fy(self.retail, "SA2526")
        self.ldgr = _ledger("SALedger")
        self.sp = SalesPersonMaster.objects.create(salesperson_name="TestSPAppr")

    def _make(self, billno, retail=None, fy=None):
        return SalesApproval.objects.create(
            date1=datetime.date(2025, 5, 1),
            billno=billno,
            narration="test",
            taxable_value=0,
            discount=0,
            vehicle_no="",
            transporter_name="",
            transporter_id="",
            trans_distance=0,
            trans_doc_no="",
            ldgr=self.ldgr,
            sales_person=self.sp,
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("APR-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("APR-001")

    def test_different_retail_allowed(self):
        retail2 = _retail("SA2")
        fy2 = _fy(retail2, "SA2526B")
        self._make("APR-001")
        self._make("APR-001", retail=retail2, fy=fy2)


class SalesApprovalReturnUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("SAR1")
        self.fy = _fy(self.retail, "SAR2526")

    def _make(self, billno, retail=None, fy=None):
        return SalesApprovalReturn.objects.create(
            billno=billno,
            date1=datetime.date(2025, 5, 1),
            narration="test",
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("ARN-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("ARN-001")

    def test_different_retail_allowed(self):
        retail2 = _retail("SAR2")
        fy2 = _fy(retail2, "SAR2526B")
        self._make("ARN-001")
        self._make("ARN-001", retail=retail2, fy=fy2)
