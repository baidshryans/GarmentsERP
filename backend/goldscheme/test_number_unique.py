"""
Tests: scoped UniqueConstraints on voucher-number fields in the goldscheme app.

Covers SchemeEnrollment and SchemePayment.
"""
import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from mastersconfig.models import FiscalYearMaster, RetailMaster
from contacts.models import Ledger
from goldscheme.models import SchemeEnrollment, SchemePayment, SchemeMaster


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


def _ledger(name):
    return Ledger.objects.create(ac_name=name, display_name=name, mobile1="", cheque_no="")


def _scheme(retail, code):
    return SchemeMaster.objects.create(
        name=f"Scheme {code}",
        scheme_code=code,
        scheme_type="monthly",
        gold_price_mode="market",
        description="",
        terms_conditions="",
        retail=retail,
    )


class SchemeEnrollmentUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("SE1")
        self.fy = _fy(self.retail, "SE2526")
        self.customer = _ledger("SECustomer")
        self.scheme = _scheme(self.retail, "SCH1")

    def _make(self, enrollment_no, retail=None, fy=None):
        return SchemeEnrollment.objects.create(
            enrollment_no=enrollment_no,
            scheme=self.scheme,
            customer=self.customer,
            start_date=datetime.date(2025, 4, 1),
            maturity_date=datetime.date(2026, 3, 31),
            installment_amount=1000,
            total_paid=0,
            gold_accumulated_wt=0,
            payments_made=0,
            status="active",
            lc_discount_applied=False,
            value_discount_applied=False,
            remarks="",
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
        )

    def test_duplicate_raises(self):
        self._make("ENR-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("ENR-001")

    def test_different_fiscal_year_allowed(self):
        """SchemeEnrollment.enrollment_no has a pre-existing global unique=True.
        Our scoped constraint is (retail, fiscal_year, enrollment_no).
        Verify two records with same retail but different FY and distinct enrollment_nos are allowed.
        """
        fy2 = FiscalYearMaster.objects.create(
            fy_code="SE2627",
            fy_start=datetime.date(2026, 4, 1),
            fy_end=datetime.date(2027, 3, 31),
        )
        self._make("ENR-001")
        # Different FY + different number (global unique prevents ENR-001 reuse)
        SchemeEnrollment.objects.create(
            enrollment_no="ENR-002",
            scheme=self.scheme,
            customer=self.customer,
            start_date=datetime.date(2026, 4, 1),
            maturity_date=datetime.date(2027, 3, 31),
            installment_amount=1000,
            total_paid=0,
            gold_accumulated_wt=0,
            payments_made=0,
            status="active",
            lc_discount_applied=False,
            value_discount_applied=False,
            remarks="",
            retail=self.retail,
            fiscal_year=fy2,
        )


class SchemePaymentUniqueTest(TestCase):
    def setUp(self):
        self.retail = _retail("SP1")
        self.fy = _fy(self.retail, "SP2526")
        self.customer = _ledger("SPCustomer")
        self.payment_ledger = _ledger("SPPaymentLedger")
        self.scheme = _scheme(self.retail, "SCHP1")
        self.enrollment = SchemeEnrollment.objects.create(
            enrollment_no="ENR-PAY-001",
            scheme=self.scheme,
            customer=self.customer,
            start_date=datetime.date(2025, 4, 1),
            maturity_date=datetime.date(2026, 3, 31),
            installment_amount=1000,
            total_paid=0,
            gold_accumulated_wt=0,
            payments_made=0,
            status="active",
            lc_discount_applied=False,
            value_discount_applied=False,
            remarks="",
            retail=self.retail,
            fiscal_year=self.fy,
        )

    def _make(self, payment_no, retail=None, fy=None):
        return SchemePayment.objects.create(
            enrollment=self.enrollment,
            payment_no=payment_no,
            date=datetime.date(2025, 5, 1),
            amount=1000,
            payment_mode="cash",
            payment_ledger=self.payment_ledger,
            installment_number=1,
            retail=retail or self.retail,
            fiscal_year=fy or self.fy,
            remarks="",
        )

    def test_duplicate_raises(self):
        self._make("PAY-001")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("PAY-001")

    def test_different_fiscal_year_allowed(self):
        """SchemePayment.payment_no has a pre-existing global unique=True.
        Our scoped constraint is (retail, fiscal_year, payment_no).
        Verify two records with same retail but different FY and distinct payment_nos are allowed.
        """
        fy2 = FiscalYearMaster.objects.create(
            fy_code="SP2627",
            fy_start=datetime.date(2026, 4, 1),
            fy_end=datetime.date(2027, 3, 31),
        )
        self._make("PAY-001")
        # Different FY + different number (global unique prevents PAY-001 reuse)
        SchemePayment.objects.create(
            enrollment=self.enrollment,
            payment_no="PAY-002",
            date=datetime.date(2026, 5, 1),
            amount=1000,
            payment_mode="cash",
            payment_ledger=self.payment_ledger,
            installment_number=2,
            retail=self.retail,
            fiscal_year=fy2,
            remarks="",
        )
