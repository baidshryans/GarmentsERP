"""Tests for automatic fiscal-year scoping of transaction list endpoints.

The active fiscal year lives on `retail.active_fy`. List endpoints served by
`RetailBaseViewset` should return only the active FY's rows unless `?all_fy=1`
is passed. Exercised through the customer-order list endpoint.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from mastersconfig.models import RetailMaster, FiscalYearMaster
from sales.models import CustomerOrder

User = get_user_model()

LIST_URL = "/sales/api/customer-orders-vs/"


def make_retail(code="R001", name="Store 1"):
    return RetailMaster.objects.create(
        retail_name=name,
        retail_code=code,
        address_line1="123 St",
        phone="9999",
        bill_series=f"S-{code}",
    )


class FiscalYearScopingTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.fy_25_26 = FiscalYearMaster.objects.create(
            retail=self.retail,
            fy_code="25-26",
            fy_start=datetime.date(2025, 4, 1),
            fy_end=datetime.date(2026, 3, 31),
        )
        self.fy_26_27 = FiscalYearMaster.objects.create(
            retail=self.retail,
            fy_code="26-27",
            fy_start=datetime.date(2026, 4, 1),
            fy_end=datetime.date(2027, 3, 31),
        )
        self.order_25 = CustomerOrder.objects.create(
            retail=self.retail, fiscal_year=self.fy_25_26, order_no="C/25",
            date1=datetime.date(2025, 6, 1),
        )
        self.order_26 = CustomerOrder.objects.create(
            retail=self.retail, fiscal_year=self.fy_26_27, order_no="C/26",
            date1=datetime.date(2026, 6, 1),
        )

        # Staff + superuser: passes middleware access check AND RBAC permission.
        self.user = User.objects.create_user(
            username="admin", password="pass12345",
            is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _set_active_fy(self, fy):
        self.retail.active_fy = fy
        self.retail.save(update_fields=["active_fy"])
        cache.clear()  # drop the middleware's cached RetailMaster

    def _order_nos(self, response):
        return {row["order_no"] for row in response.json()["results"]}

    def test_list_scoped_to_active_fy(self):
        self._set_active_fy(self.fy_26_27)
        resp = self.client.get(LIST_URL, HTTP_X_RETAIL_ID=self.retail.retail_code)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._order_nos(resp), {"C/26"})

    def test_all_fy_param_returns_all_years(self):
        self._set_active_fy(self.fy_26_27)
        resp = self.client.get(
            LIST_URL, {"all_fy": "1"}, HTTP_X_RETAIL_ID=self.retail.retail_code,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._order_nos(resp), {"C/25", "C/26"})

    def test_switching_active_fy_changes_results(self):
        self._set_active_fy(self.fy_25_26)
        resp = self.client.get(LIST_URL, HTTP_X_RETAIL_ID=self.retail.retail_code)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._order_nos(resp), {"C/25"})
