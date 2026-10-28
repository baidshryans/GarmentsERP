"""
Optimistic-lock tests for editing a sales voucher.

The edit form echoes back the `updated_at` it loaded. SalesVoucherViewset
._claim_version must accept a current token, reject a stale one with 409, and
skip the check when no token is sent.
"""

import datetime

from django.test import TestCase
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from contacts.models import Ledger
from mastersconfig.models import FiscalYearMaster, RetailMaster, SalesPersonMaster

from .models import SalesVou
from .serializers import SalesVouSerializer
from .views.invoice import SalesVoucherViewset


class SalesVoucherEditConflictTest(TestCase):
    def setUp(self):
        retail = RetailMaster.objects.create(
            retail_name="Lock Retail", retail_code="LOCK",
            phone="0000000000", address_line1="Test",
        )
        fy = FiscalYearMaster.objects.create(
            fy_code="25-26", fy_start=datetime.date(2025, 4, 1), fy_end=datetime.date(2026, 3, 31),
        )
        ledger = Ledger.objects.create(
            ac_name="Lock Customer", display_name="Lock Customer",
            b2b=False, tds_applicable=False, is_system=False,
        )
        person = SalesPersonMaster.objects.create(salesperson_name="Seller", retail=retail)
        self.fy = fy
        self.vou = SalesVou.objects.create(
            date1=datetime.date(2025, 6, 1), billno="LOCK-1", ldgr=ledger,
            sales_person=person, place_of_supply="WB", retail=retail, fiscal_year=fy,
        )

    def _claim(self, payload):
        request = APIRequestFactory().put("/", payload, format="json")
        view = SalesVoucherViewset()
        view.request = Request(request, parsers=[JSONParser()])
        view._claim_version(self.vou)

    def test_serializer_exposes_updated_at(self):
        self.assertIsNotNone(self.vou.updated_at)
        self.assertEqual(SalesVouSerializer.Meta.fields.count("updated_at"), 1)

    def test_current_token_is_accepted_and_bumped(self):
        before = self.vou.updated_at
        self._claim({"updated_at": before.isoformat()})
        self.vou.refresh_from_db()
        self.assertGreater(self.vou.updated_at, before)

    def test_stale_token_is_rejected_with_409(self):
        stale = self.vou.updated_at.isoformat()
        self._claim({"updated_at": stale})  # first editor wins
        with self.assertRaises(APIException) as ctx:
            self._claim({"updated_at": stale})  # second editor still holds the old token
        self.assertEqual(ctx.exception.status_code, 409)

    def test_missing_token_skips_the_check(self):
        before = self.vou.updated_at
        self._claim({})
        self.vou.refresh_from_db()
        self.assertEqual(self.vou.updated_at, before)

    def test_save_bumps_updated_at(self):
        before = self.vou.updated_at
        self.vou.remarks = "changed"
        self.vou.save()
        self.assertGreater(self.vou.updated_at, before)


class SalesVoucherFiscalYearLockTest(TestCase):
    """An old bill opened by direct URL must not be editable once its year is closed."""

    def setUp(self):
        self.fy = FiscalYearMaster.objects.create(
            fy_code="24-25", fy_start=datetime.date(2024, 4, 1), fy_end=datetime.date(2025, 3, 31),
        )

    def test_open_year_allows_change(self):
        SalesVoucherViewset._check_fy_unlocked(self.fy, "edited")

    def test_soft_closed_year_blocks_sales_voucher(self):
        self.fy.is_closed = True
        with self.assertRaises(ValidationError):
            SalesVoucherViewset._check_fy_unlocked(self.fy, "edited")

    def test_hard_closed_year_blocks_sales_voucher(self):
        self.fy.is_closed = True
        self.fy.is_hard_closed = True
        with self.assertRaises(ValidationError):
            SalesVoucherViewset._check_fy_unlocked(self.fy, "deleted")

    def test_journal_still_allowed_in_soft_closed_year(self):
        from mastersconfig.fy_utils import check_fy_allows_change
        self.fy.is_closed = True
        check_fy_allows_change(self.fy, "JRNL", "edited")

    def test_bill_without_a_fiscal_year_is_not_blocked(self):
        SalesVoucherViewset._check_fy_unlocked(None, "edited")
