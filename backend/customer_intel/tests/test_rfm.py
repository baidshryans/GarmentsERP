"""RFM scoring, cadence inference and the confidence gate."""

from datetime import date, timedelta

from django.test import SimpleTestCase

from customer_intel.services import rfm


class ConfidenceTests(SimpleTestCase):
    """
    The confidence gate is what keeps this feature honest on a thin dataset.
    In the live database 94% of buyers have exactly one purchase, so 'low' must
    be the answer for them and callers must then suppress cadence entirely.
    """

    def test_no_purchases_is_none(self):
        level, reason = rfm.confidence_for(0, 0)
        self.assertEqual(level, "none")
        self.assertIn("No purchase history", reason)

    def test_single_purchase_is_low_and_says_why(self):
        level, reason = rfm.confidence_for(1, 20)
        self.assertEqual(level, "low")
        self.assertIn("1 purchase", reason)
        self.assertIn("not enough", reason)

    def test_two_to_three_purchases_is_medium(self):
        self.assertEqual(rfm.confidence_for(2, 60)[0], "medium")
        self.assertEqual(rfm.confidence_for(3, 200)[0], "medium")

    def test_four_or_more_is_high(self):
        level, reason = rfm.confidence_for(4, 365)
        self.assertEqual(level, "high")
        self.assertIn("4 purchases", reason)
        self.assertIn("12 months", reason)


class CadenceTests(SimpleTestCase):
    def test_no_dates_yields_nothing(self):
        self.assertEqual(rfm.cadence_for([]), (None, None, "none"))

    def test_single_purchase_falls_back_to_cohort(self):
        median, _mean, basis = rfm.cadence_for([date(2026, 1, 1)], cohort_median_gap=200)
        self.assertEqual(basis, "cohort")
        self.assertEqual(median, 200)

    def test_single_purchase_without_cohort_is_uncomputable(self):
        self.assertEqual(rfm.cadence_for([date(2026, 1, 1)]), (None, None, "none"))

    def test_two_purchases_blend_with_cohort(self):
        # one 100-day gap of their own, blended 50/50 with a 300-day cohort
        dates = [date(2026, 1, 1), date(2026, 4, 11)]
        median, _mean, basis = rfm.cadence_for(dates, cohort_median_gap=300)
        self.assertEqual(basis, "blended")
        self.assertEqual(median, 200)

    def test_four_purchases_use_own_gaps(self):
        start = date(2020, 1, 1)
        dates = [start + timedelta(days=90 * i) for i in range(5)]
        median, _mean, basis = rfm.cadence_for(dates)
        self.assertEqual(basis, "own")
        self.assertEqual(median, 90)

    def test_gap_is_clamped_at_the_floor(self):
        """Two purchases in one week is not a 4-day buying cycle."""
        start = date(2026, 1, 1)
        dates = [start + timedelta(days=4 * i) for i in range(5)]
        median, _mean, _basis = rfm.cadence_for(dates)
        self.assertEqual(median, rfm.MIN_GAP_DAYS)

    def test_gap_is_clamped_at_the_ceiling(self):
        """A single six-year gap must not park someone in 'healthy' forever."""
        dates = [date(2010, 1, 1), date(2016, 1, 1), date(2022, 1, 1),
                 date(2028, 1, 1)]
        median, _mean, _basis = rfm.cadence_for(dates)
        self.assertEqual(median, rfm.MAX_GAP_DAYS)


class LapseTests(SimpleTestCase):
    def test_never_purchased(self):
        self.assertEqual(rfm.lapse_for(None, 100), (None, "never"))

    def test_bands(self):
        self.assertEqual(rfm.lapse_for(50, 100)[1], "healthy")   # 0.5
        self.assertEqual(rfm.lapse_for(100, 100)[1], "due")      # 1.0
        self.assertEqual(rfm.lapse_for(200, 100)[1], "at_risk")  # 2.0
        self.assertEqual(rfm.lapse_for(300, 100)[1], "lapsed")   # 3.0

    def test_next_expected_is_last_plus_gap(self):
        self.assertEqual(
            rfm.next_expected(date(2026, 1, 1), 90), date(2026, 4, 1),
        )


class SegmentLabelTests(SimpleTestCase):
    """Every label must be reachable — an unreachable branch is a silent bug."""

    def test_all_eleven_labels_are_reachable(self):
        cases = {
            (5, 5, 5): "champion",
            (1, 5, 5): "cant_lose",
            (4, 4, 1): "loyal",
            (2, 3, 1): "at_risk",
            (1, 1, 1): "lost",
            (2, 2, 2): "hibernating",
            (5, 1, 3): "new",
            (5, 2, 3): "promising",
            (3, 3, 3): "potential_loyalist",
            (3, 1, 3): "needs_attention",
            # Recent-ish, bought once, but high value — matches no earlier
            # predicate and falls through to the catch-all.
            (2, 1, 5): "about_to_sleep",
        }
        for (r, f, m), expected in cases.items():
            with self.subTest(rfm=(r, f, m)):
                self.assertEqual(rfm.segment_for(r, f, m), expected)

    def test_every_map_label_is_produced_by_some_cell(self):
        produced = {
            rfm.segment_for(r, f, m)
            for r in range(1, 6) for f in range(1, 6) for m in range(1, 6)
        }
        declared = {label for _pred, label in rfm.RFM_SEGMENT_MAP} | {"about_to_sleep"}
        self.assertEqual(produced, declared)


class CohortScorerTests(SimpleTestCase):
    def test_falls_back_to_absolute_when_repeat_buyers_are_scarce(self):
        """
        This is the live situation: a large cohort where almost nobody has
        bought twice. Quintiles on frequency would be meaningless.
        """
        scorer = rfm.CohortScorer(
            recencies=list(range(200)),
            frequencies=[1] * 195 + [2] * 5,
            monetaries=[i * 1000 for i in range(200)],
        )
        self.assertEqual(scorer.basis, "absolute")

    def test_uses_quintiles_when_the_population_supports_them(self):
        scorer = rfm.CohortScorer(
            recencies=list(range(200)),
            frequencies=[(i % 9) + 1 for i in range(200)],
            monetaries=[i * 1000 for i in range(200)],
        )
        self.assertEqual(scorer.basis, "quintile")

    def test_small_cohort_uses_absolute_bands(self):
        scorer = rfm.CohortScorer([10, 20], [1, 2], [1000, 2000])
        self.assertEqual(scorer.basis, "absolute")

    def test_identical_values_receive_identical_scores(self):
        """Ties must not be split by sort position."""
        scorer = rfm.CohortScorer(
            recencies=[100] * 200,
            frequencies=[(i % 9) + 1 for i in range(200)],
            monetaries=[500_000] * 200,
        )
        first = scorer.score(100, 3, 500_000)
        second = scorer.score(100, 3, 500_000)
        self.assertEqual(first, second)

    def test_absolute_recency_bands(self):
        scorer = rfm.CohortScorer([], [], [])
        self.assertEqual(scorer.score(30, 1, 0)[0], 5)
        self.assertEqual(scorer.score(120, 1, 0)[0], 4)
        self.assertEqual(scorer.score(300, 1, 0)[0], 3)
        self.assertEqual(scorer.score(600, 1, 0)[0], 2)
        self.assertEqual(scorer.score(2000, 1, 0)[0], 1)

    def test_never_purchased_scores_lowest_recency(self):
        scorer = rfm.CohortScorer([], [], [])
        self.assertEqual(scorer.score(None, 0, 0), (1, 1, 1))


class EngagementScoreTests(SimpleTestCase):
    def test_components_are_itemised_and_capped(self):
        score, detail = rfm.engagement_for(
            catalog_opens_90d=2, design_views_90d=5, inbound_replies_90d=1,
            scheme_active=True, pending_order=True,
        )
        self.assertEqual(score, 100)
        self.assertEqual(len(detail["components"]), 5)

    def test_no_signals_scores_zero(self):
        score, detail = rfm.engagement_for()
        self.assertEqual(score, 0)
        self.assertEqual(detail["components"], [])

    def test_partial_signals_are_explainable(self):
        score, detail = rfm.engagement_for(catalog_opens_90d=1, scheme_active=True)
        self.assertEqual(score, 45)
        self.assertEqual(
            {c["key"] for c in detail["components"]},
            {"catalog_opened", "scheme_active"},
        )
