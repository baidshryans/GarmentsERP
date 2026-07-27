"""compute_design_price with a B2B pricelist attached — one case per making type."""

from decimal import Decimal

from django.test import TestCase

from goldrates.models import PurityMaster, GoldRates
from inventory.catalog_pricing import compute_design_price
from inventory.models import DesignMain, DesignDetails
from mastersconfig.models import B2BPricelist, B2BPricelistMaking, Item


class B2BCatalogPricingTests(TestCase):
    """Design: 3 g net weight of 22K gold, no stones, stored making ₹2000.

    22K rate 6412 ⇒ pure rate 7000, so the plain gold value is 3 × 6412 = 19236.
    """

    @classmethod
    def setUpTestData(cls):
        cls.gold = Item.objects.create(
            short_code="G22", item_name="Gold 22K", item_type="M", uom="Gm",
            show_in_pcs_report=False,
        )
        cls.purity = PurityMaster.objects.create(purity="22K", gw_per=Decimal("91.6"))
        GoldRates.objects.create(purity=cls.purity, rate=6412, selling_rate=6412)

        cls.design = DesignMain.objects.create(
            design_no="RING/B2B", item=cls.gold, item_desc="Ring", pcs=1,
            gw=Decimal("3"), nw=Decimal("3"), making=Decimal("2000"),
            making_type="fixed", making_rate=Decimal("0"),
        )
        DesignDetails.objects.create(
            design_no=cls.design, sub_item=cls.gold, metal_purity=cls.purity,
            pcs=1, ct=Decimal("0"), rate=0, amt=0,
        )

    def pricelist(self, making_type, making_value, min_grams=0, purity=None, item=None):
        pl = B2BPricelist.objects.create(name=f"PL-{making_type}-{min_grams}")
        B2BPricelistMaking.objects.create(
            pricelist=pl, purity=purity, item=item,
            making_type=making_type, making_value=Decimal(str(making_value)),
            min_making_grams=Decimal(str(min_grams)),
        )
        return B2BPricelist.objects.prefetch_related("making_entries").get(pk=pl.pk)

    # ── the gold-rate regression this change also fixes ────────────────────────

    def test_plain_retail_gold_value_is_weight_times_purity_rate(self):
        """GoldRates is stored per purity, so no second gw_per multiplication."""
        res = compute_design_price(self.design)
        self.assertAlmostEqual(res["gold_value"], 3 * 6412, places=2)
        self.assertAlmostEqual(res["making_value"], 2000, places=2)

    # ── one case per making type ──────────────────────────────────────────────

    def test_per_gram_below_minimum_is_floored(self):
        res = compute_design_price(self.design, b2b_pricelist=self.pricelist("per_gram", 300, 5))
        self.assertAlmostEqual(res["making_value"], 1500, places=2)   # 300 × 5, not 300 × 3
        self.assertAlmostEqual(res["gold_value"], 3 * 6412, places=2)

    def test_flat_value_overrides_and_ignores_the_minimum(self):
        res = compute_design_price(self.design, b2b_pricelist=self.pricelist("val", 2500))
        self.assertAlmostEqual(res["making_value"], 2500, places=2)
        self.assertAlmostEqual(res["gold_value"], 3 * 6412, places=2)

    def test_tunch_moves_the_gold_rate_and_zeroes_making(self):
        res = compute_design_price(self.design, b2b_pricelist=self.pricelist("tunch", 8, 5))
        # 3g × 91.6% + 5g × 8% = 2.748 + 0.4 = 3.148 fine grams @ 7000
        self.assertAlmostEqual(res["gold_value"], 3.148 * 7000, places=2)
        self.assertAlmostEqual(res["making_value"], 0, places=2)
        # effective tunch % is expressed over the ACTUAL weight, so the gold line
        # still satisfies amount == weight × rate
        gold_line = next(c for c in res["component_lines"] if c["kind"] == "gold")
        self.assertAlmostEqual(gold_line["tunch"], 104.933333, places=4)
        self.assertAlmostEqual(gold_line["amount"], gold_line["weight_gm"] * gold_line["rate"],
                               places=1)

    def test_per_nw_uses_the_floored_weight(self):
        res = compute_design_price(self.design, b2b_pricelist=self.pricelist("per_nw", 12, 5))
        expected = 0.12 * (5 * 0.916 * 7000)
        self.assertAlmostEqual(res["making_value"], expected, places=2)
        self.assertAlmostEqual(res["gold_value"], 3 * 6412, places=2)

    # ── fallbacks ─────────────────────────────────────────────────────────────

    def test_pricelist_with_no_matching_rule_falls_back_to_stored_making(self):
        other_purity = PurityMaster.objects.create(purity="18K", gw_per=Decimal("75"))
        pl = self.pricelist("per_gram", 300, 5, purity=other_purity)
        res = compute_design_price(self.design, b2b_pricelist=pl)
        self.assertAlmostEqual(res["making_value"], 2000, places=2)

    def test_item_specific_rule_beats_the_default_rule(self):
        pl = B2BPricelist.objects.create(name="PL-priority")
        B2BPricelistMaking.objects.create(
            pricelist=pl, purity=None, item=None,
            making_type="per_gram", making_value=Decimal("100"),
            min_making_grams=Decimal("0"),
        )
        B2BPricelistMaking.objects.create(
            pricelist=pl, purity=self.purity, item=self.gold,
            making_type="per_gram", making_value=Decimal("300"),
            min_making_grams=Decimal("0"),
        )
        pl = B2BPricelist.objects.prefetch_related("making_entries").get(pk=pl.pk)
        res = compute_design_price(self.design, b2b_pricelist=pl)
        self.assertAlmostEqual(res["making_value"], 900, places=2)   # 300 × 3, not 100 × 3
