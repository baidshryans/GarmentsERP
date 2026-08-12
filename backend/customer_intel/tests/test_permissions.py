"""
Access control for the Customer 360 endpoints.

These endpoints expose every customer's spend, contact details and buying
history. `RBACPermission` cannot protect them because they are queryset-less
APIViews, so they use `HasIntelAccess` instead — and if that wiring is ever
dropped they would silently fall back to being readable by any logged-in user.
That is exactly the regression these tests exist to catch.
"""

from datetime import date

from django.core.cache import cache
from django.test import TestCase, override_settings

from customer_intel.services.snapshot import SnapshotBuilder
from customer_intel.tests.factories import (
    make_customer,
    make_retail,
    make_sale,
    make_user,
)


@override_settings(ALLOWED_HOSTS=["*"])
class CustomerEndpointPermissionTests(TestCase):
    def setUp(self):
        # RetailMiddleware caches retail lookups and per-user access checks;
        # a stale entry from a previous test would mask a real regression.
        cache.clear()
        self.retail = make_retail()
        self.customer = make_customer(self.retail, "Priya Sharma",
                                      mobile="9800011122", email="p@example.com")
        make_sale(self.retail, self.customer, date(2026, 5, 1), mrp=150000)
        SnapshotBuilder(self.retail.id, today=date(2026, 6, 1)).run()

    def _client_for(self, user):
        from rest_framework.authtoken.models import Token

        token, _ = Token.objects.get_or_create(user=user)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {token.key}"
        self.client.defaults["HTTP_X_RETAIL_ID"] = self.retail.retail_code
        return self.client

    def test_anonymous_is_rejected(self):
        response = self.client.get(
            "/customer-intel/api/customers/",
            HTTP_X_RETAIL_ID=self.retail.retail_code,
        )
        self.assertIn(response.status_code, (401, 403))

    def test_authenticated_user_without_the_grant_is_forbidden(self):
        """A logged-in user with no customer_intel permission must not read it."""
        user = make_user("nobody", retail=self.retail, permissions=None)
        response = self._client_for(user).get("/customer-intel/api/customers/")
        self.assertEqual(response.status_code, 403)

    def test_user_with_the_grant_can_read(self):
        user = make_user("analyst", retail=self.retail, permissions=["can_get", "can_list"])
        response = self._client_for(user).get("/customer-intel/api/customers/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_profile_endpoint_is_gated_too(self):
        user = make_user("nobody2", retail=self.retail, permissions=None)
        response = self._client_for(user).get(
            f"/customer-intel/api/customers/{self.customer.id}/profile/"
        )
        self.assertEqual(response.status_code, 403)

    def test_timeline_endpoint_is_gated_too(self):
        user = make_user("nobody3", retail=self.retail, permissions=None)
        response = self._client_for(user).get(
            f"/customer-intel/api/customers/{self.customer.id}/timeline/"
        )
        self.assertEqual(response.status_code, 403)

    def test_note_endpoint_requires_write_permission(self):
        reader = make_user("reader", retail=self.retail, permissions=["can_get", "can_list"])
        response = self._client_for(reader).post(
            f"/customer-intel/api/customers/{self.customer.id}/note/",
            data={"body": "should not be allowed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_superuser_bypasses_the_grant(self):
        user = make_user("root", retail=self.retail, superuser=True)
        response = self._client_for(user).get("/customer-intel/api/customers/")
        self.assertEqual(response.status_code, 200)


@override_settings(ALLOWED_HOSTS=["*"])
class CustomerMaskingTests(TestCase):
    """
    PII masking must apply to this endpoint too. It exposes the same fields the
    ledger API protects, so a user denied customer data there must not be able
    to read the customer book here instead.
    """

    def setUp(self):
        # RetailMiddleware caches retail lookups and per-user access checks;
        # a stale entry from a previous test would mask a real regression.
        cache.clear()
        self.retail = make_retail()
        self.customer = make_customer(
            self.retail, "Anita Roy", mobile="9800011122", email="a@example.com",
        )
        make_sale(self.retail, self.customer, date(2026, 5, 1), mrp=150000)
        SnapshotBuilder(self.retail.id, today=date(2026, 6, 1)).run()

    def _get_first_row(self, user):
        from rest_framework.authtoken.models import Token

        token, _ = Token.objects.get_or_create(user=user)
        response = self.client.get(
            "/customer-intel/api/customers/",
            HTTP_AUTHORIZATION=f"Token {token.key}",
            HTTP_X_RETAIL_ID=self.retail.retail_code,
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["results"][0]

    def test_user_without_customer_data_sees_masked_identity(self):
        user = make_user("masked", retail=self.retail, permissions=["can_get", "can_list"],
                         can_view_customer_data=False)
        row = self._get_first_row(user)

        self.assertEqual(row["ac_name"], "****")
        self.assertEqual(row["mobile1"], "****")
        self.assertEqual(row["email"], "****")

    def test_user_without_customer_data_still_sees_the_analytics(self):
        """Masking hides who they are, not how the business is doing."""
        user = make_user("masked2", retail=self.retail, permissions=["can_get", "can_list"],
                         can_view_customer_data=False)
        row = self._get_first_row(user)

        self.assertEqual(row["purchase_count_all"], 1)
        self.assertIsNotNone(row["rfm_segment"])

    def test_privileged_user_sees_real_identity(self):
        user = make_user("full", retail=self.retail, permissions=["can_get", "can_list"],
                         can_view_customer_data=True)
        row = self._get_first_row(user)

        self.assertEqual(row["ac_name"], "Anita Roy")
        self.assertEqual(row["mobile1"], "9800011122")
