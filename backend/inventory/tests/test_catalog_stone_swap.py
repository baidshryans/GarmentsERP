from decimal import Decimal

from django.test import TestCase

from goldrates.models import PurityMaster, GoldRates
from mastersconfig.models import Item, Packet, PacketGroup
from inventory.models import DesignMain, DesignDetails


def make_item(code, name, item_type, uom):
    return Item.objects.create(
        short_code=code, item_name=name, item_type=item_type, uom=uom,
        show_in_pcs_report=False,
    )


def make_packet(no, stone_item, sieve_min, sieve_max, rate_retail=1000, rate_ws=800):
    return Packet.objects.create(
        pckt_no=no, stone_item_id=stone_item,
        sieve_min=sieve_min, sieve_max=sieve_max,
        is_solitaire=False, is_customer_stone=False,
        rate_for_retail=rate_retail, rate_for_wholesale=rate_ws,
    )


class BaseData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gold = make_item("G18", "Gold 18K", "M", "Gm")
        cls.diamond = make_item("DIA", "Diamond", "S", "Ct")
        cls.lgd = make_item("LGD", "Lab Grown Diamond", "S", "Ct")
        cls.purity = PurityMaster.objects.create(purity="18", gw_per=Decimal("75"))
        GoldRates.objects.create(purity=cls.purity, rate=6000, selling_rate=6000)

        cls.grp = PacketGroup.objects.create(packet_group_name="DEF")
        cls.dia_pkt = make_packet("D1", cls.diamond, "1.0", "1.5", rate_retail=10000)
        cls.lgd_pkt = make_packet("L1", cls.lgd, "1.2", "2.0", rate_retail=3000)

        cls.design = DesignMain.objects.create(
            design_no="RING/1", item=cls.gold, item_desc="Ring", pcs=1,
            gw=Decimal("10"), nw=Decimal("9"), making=Decimal("2000"),
            making_type="fixed", making_rate=Decimal("0"),
        )
        DesignDetails.objects.create(
            design_no=cls.design, sub_item=cls.gold, metal_purity=cls.purity,
            pcs=1, ct=Decimal("0"), rate=0, amt=0,
        )
        cls.stone_line = DesignDetails.objects.create(
            design_no=cls.design, sub_item=cls.diamond, metal_purity=cls.purity,
            packet=cls.dia_pkt, pcs=4, ct=Decimal("2"), rate=10000, amt=20000,
        )
        cls.plain_line = DesignDetails.objects.create(
            design_no=cls.design, sub_item=cls.gold, metal_purity=cls.purity,
            pcs=1, ct=Decimal("0"), rate=0, amt=500,
        )


class ComputeDesignPriceOverrideTests(BaseData):
    def test_no_overrides_is_unchanged(self):
        from inventory.catalog_pricing import compute_design_price
        base = compute_design_price(self.design)
        again = compute_design_price(self.design, line_overrides={})
        self.assertEqual(base["total_price"], again["total_price"])
        self.assertEqual(base["stone_total"], again["stone_total"])

    def test_override_reprices_stone_line(self):
        from inventory.catalog_pricing import compute_design_price
        base = compute_design_price(self.design)
        sim = compute_design_price(self.design, line_overrides={
            self.stone_line.id: {"rate": Decimal("3000"), "packet": self.lgd_pkt},
        })
        # amt goes 20000 → 3000 × 2ct = 6000; delta on taxable = -14000, +3% GST
        expected_delta = Decimal("-14000") * Decimal("1.03")
        self.assertAlmostEqual(
            sim["total_price"] - base["total_price"], float(expected_delta), places=2)
        line = next(c for c in sim["component_lines"] if c.get("overridden"))
        self.assertIn("Lab Grown Diamond", line["name"])
        self.assertIn("L1", line["name"])
        # gold and making untouched
        self.assertEqual(sim["gold_value"], base["gold_value"])
        self.assertEqual(sim["making_value"], base["making_value"])

    def test_override_without_packet_uses_manual_rate(self):
        from inventory.catalog_pricing import compute_design_price
        sim = compute_design_price(self.design, line_overrides={
            self.stone_line.id: {"rate": Decimal("5000"), "packet": None},
        })
        line = next(c for c in sim["component_lines"] if c.get("overridden"))
        self.assertEqual(line["amount"], 10000.0)  # 5000 × 2 ct


class SwapCandidatesTests(BaseData):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        self.user = get_user_model().objects.create_user(username="u1", password="p")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def get(self, packet_id):
        r = self.client.get(f"/inventory/api/catalog/swap-candidates/?packet={packet_id}")
        self.assertEqual(r.status_code, 200)
        return [c["pckt_no"] for c in r.json()["candidates"]]

    def test_overlapping_sieve_matches(self):
        # dia 1.0–1.5 vs lgd 1.2–2.0 overlap both ways
        self.assertIn("L1", self.get(self.dia_pkt.id))
        self.assertIn("D1", self.get(self.lgd_pkt.id))

    def test_non_overlapping_excluded(self):
        far = make_packet("L2", self.lgd, "2.5", "3.0")
        self.assertNotIn("L2", self.get(self.dia_pkt.id))
        self.assertNotIn("D1", self.get(far.id))

    def test_blank_bound_is_open(self):
        open_pkt = make_packet("L3", self.lgd, "", "1.1")  # min open, max 1.1 ≥ 1.0
        self.assertIn("L3", self.get(self.dia_pkt.id))

    def test_unparseable_candidate_excluded(self):
        make_packet("L4", self.lgd, "small", "big")
        self.assertNotIn("L4", self.get(self.dia_pkt.id))

    def test_unparseable_source_falls_back_to_exact_match(self):
        src = make_packet("T1", self.diamond, "abc", "xyz")
        twin = make_packet("T2", self.lgd, "abc", "xyz")
        names = self.get(src.id)
        self.assertIn("T2", names)
        self.assertNotIn("D1", names)

    def test_missing_packet_param_400(self):
        r = self.client.get("/inventory/api/catalog/swap-candidates/")
        self.assertEqual(r.status_code, 400)


class SimulateEndpointTests(BaseData):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient
        self.user = get_user_model().objects.create_user(username="u1", password="p")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def post(self, overrides):
        return self.client.post(
            f"/inventory/api/catalog/{self.design.id}/simulate/",
            {"tier": "retail", "pricelist": None, "overrides": overrides},
            format="json",
        )

    def test_simulate_returns_original_simulated_and_delta(self):
        r = self.post([{"detail_id": self.stone_line.id, "packet_id": self.lgd_pkt.id, "rate": 3000}])
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertAlmostEqual(
            body["delta"],
            round(body["simulated"]["total_price"] - body["original"]["total_price"], 2),
            places=2,
        )
        self.assertLess(body["simulated"]["total_price"], body["original"]["total_price"])

    def test_rejects_override_on_non_packet_line(self):
        r = self.post([{"detail_id": self.plain_line.id, "packet_id": None, "rate": 100}])
        self.assertEqual(r.status_code, 400)
        self.assertIn("not a swappable", r.json()["error"])

    def test_rejects_bad_rate(self):
        r = self.post([{"detail_id": self.stone_line.id, "packet_id": None, "rate": "abc"}])
        self.assertEqual(r.status_code, 400)

    def test_unknown_design_404(self):
        r = self.client.post("/inventory/api/catalog/999999/simulate/", {"overrides": []}, format="json")
        self.assertEqual(r.status_code, 404)
