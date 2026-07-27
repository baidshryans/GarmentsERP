"""API-level tests for the B2B pricelist endpoint after tunch was folded in."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from goldrates.models import PurityMaster
from mastersconfig.models import B2BPricelist, Item

URL = "/mastersconfig/api/b2b-pricelist/"


class B2BPricelistAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.p22 = PurityMaster.objects.create(purity="22K", gw_per=Decimal("91.6"))
        cls.ring = Item.objects.create(
            short_code="RING", item_name="Ring", item_type="M", uom="Gm",
            show_in_pcs_report=False,
        )

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u1", password="p")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def post(self, making_entries, name="Tier A"):
        return self.client.post(
            URL, {"name": name, "making_entries": making_entries}, format="json")

    def test_mixed_making_types_save_together(self):
        """The old model forbade tunch alongside making rules — mixing is the point now."""
        r = self.post([
            {"purity": "22K", "item": "RING", "making_type": "per_gram",
             "making_value": "300", "min_making_grams": "5"},
            {"purity": "22K", "item": None, "making_type": "tunch",
             "making_value": "8", "min_making_grams": "5"},
            {"purity": None, "item": None, "making_type": "val", "making_value": "2000"},
        ])
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertNotIn("tunch_entries", body)
        self.assertEqual(len(body["making_entries"]), 3)
        self.assertEqual(B2BPricelist.objects.get(name="Tier A").making_entries.count(), 3)

    def test_min_making_grams_round_trips(self):
        r = self.post([{"purity": "22K", "item": None, "making_type": "per_gram",
                        "making_value": "300", "min_making_grams": "2.5"}])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Decimal(r.json()["making_entries"][0]["min_making_grams"]),
                         Decimal("2.500"))

    def test_min_making_grams_defaults_to_zero_when_omitted(self):
        r = self.post([{"purity": None, "item": None, "making_type": "per_gram",
                        "making_value": "300"}])
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(Decimal(r.json()["making_entries"][0]["min_making_grams"]),
                         Decimal("0"))

    # ── validation ────────────────────────────────────────────────────────────

    def test_flat_value_rejects_a_minimum(self):
        r = self.post([{"purity": None, "item": None, "making_type": "val",
                        "making_value": "2000", "min_making_grams": "5"}])
        self.assertEqual(r.status_code, 400)
        self.assertIn("min_making_grams", str(r.content))

    def test_percentage_rule_rejects_a_value_over_100(self):
        r = self.post([{"purity": None, "item": None, "making_type": "tunch",
                        "making_value": "150"}])
        self.assertEqual(r.status_code, 400)
        self.assertIn("making_value", str(r.content))

    def test_negative_making_value_rejected(self):
        r = self.post([{"purity": None, "item": None, "making_type": "per_gram",
                        "making_value": "-1"}])
        self.assertEqual(r.status_code, 400)

    def test_duplicate_purity_item_pair_rejected(self):
        r = self.post([
            {"purity": "22K", "item": "RING", "making_type": "per_gram", "making_value": "300"},
            {"purity": "22K", "item": "RING", "making_type": "val", "making_value": "2000"},
        ])
        self.assertEqual(r.status_code, 400)
        self.assertIn("Duplicate", str(r.content))

    def test_duplicate_default_rules_rejected(self):
        """NULLs are distinct to the DB index, so the serializer is the real guard."""
        r = self.post([
            {"purity": None, "item": None, "making_type": "per_gram", "making_value": "300"},
            {"purity": None, "item": None, "making_type": "val", "making_value": "2000"},
        ])
        self.assertEqual(r.status_code, 400)
        self.assertIn("Duplicate", str(r.content))

    def test_unknown_making_type_rejected(self):
        r = self.post([{"purity": None, "item": None, "making_type": "bogus",
                        "making_value": "1"}])
        self.assertEqual(r.status_code, 400)

    # ── update path ───────────────────────────────────────────────────────────

    def test_update_replaces_rules(self):
        created = self.post([{"purity": None, "item": None, "making_type": "per_gram",
                              "making_value": "300", "min_making_grams": "5"}]).json()
        r = self.client.put(
            f"{URL}{created['id']}/",
            {"name": "Tier A", "making_entries": [
                {"purity": None, "item": None, "making_type": "tunch",
                 "making_value": "8", "min_making_grams": "2"},
            ]},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        entries = r.json()["making_entries"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["making_type"], "tunch")
