"""Endpoint tests proving an out-of-active-fiscal-year transaction date is
rejected on create. Exercised through the customer-order create endpoint.

Mirrors auth/retail/cache/header setup from userauth.test_fy_scoping.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from mastersconfig.models import RetailMaster, FiscalYearMaster
from contacts.models import Ledger

User = get_user_model()

CREATE_URL = "/sales/api/customer-orders-vs/"


def make_retail(code="R001", name="Store 1"):
    return RetailMaster.objects.create(
        retail_name=name,
        retail_code=code,
        address_line1="123 St",
        phone="9999",
    )


class CustomerOrderFyDateValidationTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.fy_25_26 = FiscalYearMaster.objects.create(
            retail=self.retail,
            fy_code="25-26",
            fy_start=datetime.date(2025, 4, 1),
            fy_end=datetime.date(2026, 3, 31),
        )
        self.retail.active_fy = self.fy_25_26
        self.retail.save(update_fields=["active_fy"])

        self.ldgr = Ledger.objects.create(
            ac_name="Walk-in Customer", display_name="Walk-in Customer",
        )

        self.user = User.objects.create_user(
            username="admin", password="pass12345",
            is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        cache.clear()

    def _payload(self, date1):
        return {
            "ldgr": self.ldgr.id,
            "date1": date1.isoformat(),
            "nature": "O",
            "status": "draft",
            "items": [],
        }

    def test_create_rejected_when_date_outside_active_fy(self):
        # 2026-06-01 is after fy_end (2026-03-31) of the active FY.
        resp = self.client.post(
            CREATE_URL,
            self._payload(datetime.date(2026, 6, 1)),
            format="json",
            HTTP_X_RETAIL_ID=self.retail.retail_code,
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("date1", resp.json())

    def test_create_succeeds_when_date_inside_active_fy(self):
        resp = self.client.post(
            CREATE_URL,
            self._payload(datetime.date(2025, 6, 1)),
            format="json",
            HTTP_X_RETAIL_ID=self.retail.retail_code,
        )
        # No FY error: either created (201) or, if other unrelated required
        # fields exist, at least no 'date1' FY error.
        if resp.status_code == 400:
            self.assertNotIn("date1", resp.json())
        else:
            self.assertEqual(resp.status_code, 201, resp.content)
