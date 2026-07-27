"""Parity suite for the B2B making/tunch math.

The same table is mirrored in `frontend/src/lib/b2bPricing.test.js` using the
same numbers.  If the two implementations ever drift, one of these suites fails
instead of a customer being mis-billed.
"""

from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from mastersconfig.b2b_pricing import (
    find_b2b_making_rule, pure_rate_from_purity_rate, resolve_b2b_making,
)

BASE_22K = Decimal("91.6")
PURE_RATE = Decimal("7000")


def rule(making_type, making_value, min_making_grams=0):
    return SimpleNamespace(
        making_type=making_type,
        making_value=Decimal(str(making_value)),
        min_making_grams=Decimal(str(min_making_grams)),
    )


def resolve(r, weight, base=BASE_22K, pure=PURE_RATE):
    return resolve_b2b_making(r, weight=Decimal(str(weight)),
                              base_purity_pct=base, pure_gold_rate=pure)


class ResolveB2BMakingTests(SimpleTestCase):

    def test_per_gram_above_minimum_uses_actual_weight(self):
        res = resolve(rule("per_gram", 300, 5), 8)
        self.assertEqual(res["making_value"], Decimal("2400"))
        self.assertEqual(res["eff_weight"], Decimal("8"))

    def test_per_gram_below_minimum_is_floored(self):
        res = resolve(rule("per_gram", 300, 5), 3)
        self.assertEqual(res["making_value"], Decimal("1500"))   # not 900
        self.assertEqual(res["eff_weight"], Decimal("5"))

    def test_flat_value_ignores_the_minimum(self):
        res = resolve(rule("val", 2000, 5), 3)
        self.assertEqual(res["making_value"], Decimal("2000"))
        self.assertEqual(res["eff_weight"], Decimal("3"))
        self.assertEqual(res["eff_tunch_pct"], BASE_22K)

    def test_tunch_above_minimum(self):
        res = resolve(rule("tunch", 8, 5), 10)
        self.assertEqual(res["eff_tunch_pct"], Decimal("99.6"))
        self.assertEqual(res["fine_wt"], Decimal("9.96"))
        self.assertEqual(res["making_value"], Decimal("0"))

    def test_tunch_below_minimum_floors_only_the_markup(self):
        # 2g × 91.6% + 5g × 8% = 1.832 + 0.4 = 2.232 fine grams
        res = resolve(rule("tunch", 8, 5), 2)
        self.assertEqual(res["fine_wt"], Decimal("2.232"))
        self.assertEqual(res["eff_tunch_pct"], Decimal("111.6"))
        self.assertEqual(res["making_value"], Decimal("0"))

    def test_tunch_preserves_gold_value_equals_weight_times_rate(self):
        for weight in ("0.5", "2", "3", "10"):
            res = resolve(rule("tunch", 8, 5), weight)
            self.assertAlmostEqual(
                float(res["gold_value"]),
                float(Decimal(weight) * res["gold_rate"]),
                places=9,
                msg=f"invariant broken at weight={weight}",
            )

    def test_per_nw_below_minimum_uses_the_floored_weight(self):
        res = resolve(rule("per_nw", 12, 5), 2)
        expected = Decimal("12") / 100 * (Decimal("5") * BASE_22K / 100 * PURE_RATE)
        self.assertEqual(res["making_value"], expected)
        # the gold line itself is untouched — only the making basis is floored
        self.assertEqual(res["eff_tunch_pct"], BASE_22K)

    def test_zero_weight_charges_nothing_except_flat_value(self):
        for mtype in ("per_gram", "per_nw", "tunch"):
            self.assertEqual(resolve(rule(mtype, 300, 5), 0)["making_value"], Decimal("0"),
                             msg=f"{mtype} charged on a zero-weight line")
        self.assertEqual(resolve(rule("val", 2000), 0)["making_value"], Decimal("2000"))

    def test_zero_base_purity_does_not_raise(self):
        # purity_master has live rows with gw_per = 0 ("22", "18", "MIX")
        res = resolve(rule("tunch", 8, 5), 3, base=Decimal("0"))
        self.assertEqual(res["gold_value"], Decimal("0") + res["fine_wt"] * PURE_RATE)
        self.assertEqual(pure_rate_from_purity_rate(6400, Decimal("0")), Decimal("0"))

    def test_no_rule_returns_plain_purity_figures(self):
        res = resolve(None, 10)
        self.assertIsNone(res["making_value"])
        self.assertEqual(res["eff_tunch_pct"], BASE_22K)
        self.assertEqual(res["fine_wt"], Decimal("9.16"))

    def test_unknown_making_type_behaves_as_no_rule(self):
        res = resolve(rule("bogus", 300, 5), 3)
        self.assertIsNone(res["making_value"])
        self.assertEqual(res["eff_tunch_pct"], BASE_22K)

    def test_pure_rate_from_purity_rate(self):
        # a 22K rate of 6412 implies a pure rate of 7000
        self.assertAlmostEqual(
            float(pure_rate_from_purity_rate(Decimal("6412"), BASE_22K)), 7000.0, places=6)


class FindB2BMakingRuleTests(SimpleTestCase):
    """Rule matching priority: (purity,item) > (purity,·) > (·,item) > (·,·)."""

    def setUp(self):
        def entry(purity_id, item_id, tag):
            return SimpleNamespace(purity_id=purity_id, item_id=item_id, making_type=tag,
                                   making_value=Decimal("1"), min_making_grams=Decimal("0"))
        self.both = entry(4, 9, "both")
        self.purity_only = entry(4, None, "purity_only")
        self.item_only = entry(None, 9, "item_only")
        self.default = entry(None, None, "default")

    def pricelist(self, *entries):
        return SimpleNamespace(
            making_entries=SimpleNamespace(all=lambda: list(entries)))

    def test_none_pricelist(self):
        self.assertIsNone(find_b2b_making_rule(None, purity=4, item=9))

    def test_most_specific_wins(self):
        pl = self.pricelist(self.default, self.item_only, self.purity_only, self.both)
        self.assertIs(find_b2b_making_rule(pl, purity=4, item=9), self.both)

    def test_falls_back_to_purity_only(self):
        pl = self.pricelist(self.default, self.item_only, self.purity_only)
        self.assertIs(find_b2b_making_rule(pl, purity=4, item=9), self.purity_only)

    def test_falls_back_to_item_only(self):
        pl = self.pricelist(self.default, self.item_only)
        self.assertIs(find_b2b_making_rule(pl, purity=4, item=9), self.item_only)

    def test_falls_back_to_default(self):
        pl = self.pricelist(self.default)
        self.assertIs(find_b2b_making_rule(pl, purity=4, item=9), self.default)

    def test_unmatched_purity_still_reaches_the_default(self):
        pl = self.pricelist(self.purity_only, self.default)
        self.assertIs(find_b2b_making_rule(pl, purity=99, item=None), self.default)

    def test_no_match_returns_none(self):
        pl = self.pricelist(self.purity_only)
        self.assertIsNone(find_b2b_making_rule(pl, purity=99, item=None))
