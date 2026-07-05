"""
FixedAsset creation should be able to attach to an EXISTING ledger already
sitting in a Fixed Assets account group, instead of always auto-creating a
brand-new ledger. See project discussion: user reclassifies ledgers into the
FA group ahead of asset-master creation, and the ledger's true purchase date
may differ from whatever date the GL entry was posted on.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from accounting.models import Account, FixedAsset
from contacts.models import Ledger
from mastersconfig.models import RetailMaster

User = get_user_model()

ASSETS_URL = "/accounting/api/fa/assets/"


def make_retail(code="R001", name="Store 1"):
    return RetailMaster.objects.create(
        retail_name=name,
        retail_code=code,
        address_line1="123 St",
        phone="9999",
    )


class FixedAssetLedgerLinkTests(TestCase):
    def setUp(self):
        call_command("setup_account_groups")
        self.retail = make_retail()
        self.fa_group = Account.objects.get(code="FA-FF")  # Furniture & Fixtures
        self.non_fa_group = Account.objects.get(code="FA-AD")  # Accum. Depreciation only

        self.existing_ledger = Ledger.objects.create(
            ac_name="Existing Showroom Furniture",
            display_name="Existing Showroom Furniture",
            ac_group=self.fa_group,
            retail_code=self.retail,
        )

        self.user = User.objects.create_user(
            username="admin", password="pass12345",
            is_staff=True, is_superuser=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_X_RETAIL_ID=self.retail.retail_code)

    def _payload(self, **overrides):
        payload = {
            "asset_code": "FA-001",
            "asset_name": "Showroom Furniture",
            "purchase_date": "2024-01-15",
            "purchase_cost": "50000.00",
            "residual_value": "0.00",
            "depreciation_method": "SLM",
            "rate_or_life": "10",
            "it_block_category": "FURN",
        }
        payload.update(overrides)
        return payload

    def test_create_with_existing_ledger_attaches_without_creating_new_one(self):
        ledger_count_before = Ledger.objects.count()

        response = self.client.post(
            ASSETS_URL,
            self._payload(asset_ledger=self.existing_ledger.id),
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.content)
        asset = FixedAsset.objects.get(asset_code="FA-001")
        self.assertEqual(asset.asset_ledger_id, self.existing_ledger.id)
        self.assertEqual(Ledger.objects.count(), ledger_count_before)

    def test_create_without_ledger_still_auto_creates_one(self):
        ledger_count_before = Ledger.objects.count()

        response = self.client.post(ASSETS_URL, self._payload(), format="json")

        self.assertEqual(response.status_code, 201, response.content)
        asset = FixedAsset.objects.get(asset_code="FA-001")
        self.assertIsNotNone(asset.asset_ledger_id)
        self.assertEqual(Ledger.objects.count(), ledger_count_before + 1)

    def test_create_with_ledger_outside_fa_groups_is_rejected(self):
        non_fa_ledger = Ledger.objects.create(
            ac_name="Random Non-FA Ledger",
            display_name="Random Non-FA Ledger",
            ac_group=self.non_fa_group,
            retail_code=self.retail,
        )

        response = self.client.post(
            ASSETS_URL,
            self._payload(asset_ledger=non_fa_ledger.id),
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.content)
