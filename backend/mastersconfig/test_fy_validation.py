"""Tests for the active-fiscal-year date guard helper."""

import datetime

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from mastersconfig.models import RetailMaster, FiscalYearMaster, SystemSettings
from mastersconfig.fy_validation import assert_date_in_active_fy


def make_retail(code="R001", name="Store 1"):
    return RetailMaster.objects.create(
        retail_name=name,
        retail_code=code,
        address_line1="123 St",
        phone="9999",
    )


class AssertDateInActiveFyTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.fy = FiscalYearMaster.objects.create(
            fy_code="25-26",
            fy_start=datetime.date(2025, 4, 1),
            fy_end=datetime.date(2026, 3, 31),
        )
        SystemSettings.set_company_active_fy(self.fy)

    def test_date_inside_fy_no_error(self):
        # Should not raise.
        assert_date_in_active_fy(self.retail, datetime.date(2025, 6, 1))

    def test_date_on_boundaries_no_error(self):
        assert_date_in_active_fy(self.retail, datetime.date(2025, 4, 1))
        assert_date_in_active_fy(self.retail, datetime.date(2026, 3, 31))

    def test_date_before_fy_start_raises(self):
        with self.assertRaises(ValidationError):
            assert_date_in_active_fy(self.retail, datetime.date(2025, 3, 31))

    def test_date_after_fy_end_raises(self):
        with self.assertRaises(ValidationError):
            assert_date_in_active_fy(self.retail, datetime.date(2026, 4, 1))

    def test_none_date_no_error(self):
        assert_date_in_active_fy(self.retail, None)

    def test_retail_without_active_fy_no_error(self):
        # Under the company-global model the active FY is a single company-wide
        # value. When it is cleared, every retail sees no active FY, so the
        # date guard is a no-op for any retail.
        SystemSettings.set_company_active_fy(None)
        retail2 = make_retail(code="R002", name="Store 2")
        assert_date_in_active_fy(retail2, datetime.date(2099, 1, 1))

    def test_none_retail_no_error(self):
        assert_date_in_active_fy(None, datetime.date(2099, 1, 1))

    def test_custom_field_in_error(self):
        with self.assertRaises(ValidationError) as ctx:
            assert_date_in_active_fy(
                self.retail, datetime.date(2099, 1, 1), field="date"
            )
        self.assertIn("date", ctx.exception.detail)
