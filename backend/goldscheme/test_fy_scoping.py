"""Scheme enrollments must NOT be fiscal-year-scoped.

Unlike dated transaction registers, a SchemeEnrollment starts in one fiscal
year and matures in the next, so it must stay visible in the enrollment list
even after the active FY rolls over. `SchemeEnrollmentViewSet` opts out of the
base `RetailBaseViewset` FY scoping via `fy_scoped = False`; this test guards
that behavior.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from mastersconfig.models import RetailMaster, FiscalYearMaster
from contacts.models import Ledger
from goldscheme.models import SchemeMaster, SchemeEnrollment

User = get_user_model()

LIST_URL = "/goldscheme/api/enrollments/"


class SchemeEnrollmentCrossYearTests(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(
            retail_name="Store 1",
            retail_code="R001",
            address_line1="123 St",
            phone="9999",
        )
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

        self.customer = Ledger.objects.create(
            ac_name="Scheme Customer",
            display_name="Scheme Customer",
            retail_code=self.retail,
        )
        self.scheme = SchemeMaster.objects.create(
            retail=self.retail,
            name="11+1 Gold Plan",
            scheme_code="GP01",
            scheme_type="INSTALLMENT",
            gold_price_mode="CURRENT",
            tenure_months=12,
        )
        # Enrollment created under FY 25-26 — should still surface under 26-27.
        self.enrollment = SchemeEnrollment.objects.create(
            retail=self.retail,
            fiscal_year=self.fy_25_26,
            scheme=self.scheme,
            customer=self.customer,
            enrollment_no="ENR/25/001",
            start_date=datetime.date(2025, 6, 1),
            maturity_date=datetime.date(2026, 6, 1),
            installment_amount=5000,
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

    def test_old_fy_enrollment_visible_in_new_fy(self):
        # Roll the active FY forward to 26-27; the 25-26 enrollment must remain.
        self._set_active_fy(self.fy_26_27)
        resp = self.client.get(LIST_URL, HTTP_X_RETAIL_ID=self.retail.retail_code)
        self.assertEqual(resp.status_code, 200)
        enrollment_nos = {row["enrollment_no"] for row in resp.json()["results"]}
        self.assertIn("ENR/25/001", enrollment_nos)
