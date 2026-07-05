"""
FixedAsset.asset_code is now server-generated (format "FA-00001") instead of
user-entered — the frontend no longer collects it, and even if a client POSTs
one, the server value must win.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounting.fa_services import generate_next_asset_code
from accounting.models import FixedAsset
from contacts.models import Ledger
from mastersconfig.models import RetailMaster

User = get_user_model()

ASSETS_URL = "/accounting/api/fa/assets/"


def make_retail(code="R001"):
    return RetailMaster.objects.create(
        retail_name=f"Store {code}", retail_code=code,
        address_line1="123 St", phone="9999",
    )


class AssetCodeGenerationTests(TestCase):
    def setUp(self):
        self.retail = make_retail()

    def test_generate_next_asset_code_starts_at_00001(self):
        self.assertEqual(generate_next_asset_code(self.retail), "FA-00001")

    def test_generate_next_asset_code_increments(self):
        FixedAsset.objects.create(
            retail=self.retail, asset_code="FA-00001", asset_name="A",
            purchase_date="2024-01-01", purchase_cost="1000",
        )
        self.assertEqual(generate_next_asset_code(self.retail), "FA-00002")

    def test_generate_next_asset_code_scoped_per_retail(self):
        other_retail = make_retail("R002")
        FixedAsset.objects.create(
            retail=self.retail, asset_code="FA-00001", asset_name="A",
            purchase_date="2024-01-01", purchase_cost="1000",
        )
        self.assertEqual(generate_next_asset_code(other_retail), "FA-00001")


class AssetCodeApiTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.user = User.objects.create_user(
            username="admin", password="pass12345",
            is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_X_RETAIL_ID=self.retail.retail_code)

    def _payload(self, **overrides):
        payload = {
            "asset_name": "Test Asset",
            "purchase_date": "2024-01-15",
            "purchase_cost": "50000.00",
            "depreciation_method": "SLM",
            "rate_or_life": "10",
        }
        payload.update(overrides)
        return payload

    def test_create_auto_assigns_asset_code(self):
        response = self.client.post(ASSETS_URL, self._payload(), format="json")

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["asset_code"], "FA-00001")

    def test_client_supplied_asset_code_is_ignored(self):
        response = self.client.post(
            ASSETS_URL, self._payload(asset_code="HACKED-001"), format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["asset_code"], "FA-00001")
        self.assertFalse(FixedAsset.objects.filter(asset_code="HACKED-001").exists())

    def test_second_create_gets_next_code(self):
        self.client.post(ASSETS_URL, self._payload(), format="json")
        response = self.client.post(ASSETS_URL, self._payload(asset_name="Another"), format="json")

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.data["asset_code"], "FA-00002")
