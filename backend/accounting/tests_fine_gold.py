"""Unit tests for FineGoldRateService.

Tests focus on the math: given known (gw, purity, value) tuples, the service
should return Σ(value) / Σ(gw × gw_per/100). Data-source queries are patched
so no DB is needed.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.test import SimpleTestCase

from accounting.fine_gold_service import FineGoldRateService


def _stub_purchases(rows):
    """Patch _purchases_contribution to return the given accumulated tuple."""
    total_value = Decimal("0")
    total_fine = Decimal("0")
    for gw, purity_pct, value in rows:
        total_value += Decimal(str(value))
        total_fine += Decimal(str(gw)) * Decimal(str(purity_pct)) / Decimal("100")
    return total_value, total_fine


class TestFineGoldRateMath(SimpleTestCase):
    """Patch the three contribution methods to inject known gold flows."""

    def _make_service(self, opening=None, purchases=None, transfers=None):
        svc = FineGoldRateService.__new__(FineGoldRateService)
        svc.retail_ids = [1]
        svc.end_date = date(2026, 4, 27)
        svc.fy_start = date(2026, 4, 1)
        svc._opening_stock_contribution = lambda: opening or (Decimal("0"), Decimal("0"))
        svc._purchases_contribution = lambda: purchases or (Decimal("0"), Decimal("0"))
        svc._transfers_in_contribution = lambda: transfers or (Decimal("0"), Decimal("0"))
        return svc

    def test_user_example_22k_and_18k_mix(self):
        """100g @ 22K @ ₹6000/g + 50g @ 18K @ ₹5000/g
        Expected ≈ 850000 / 129.16 ≈ ₹6580.5/g."""
        purchases = _stub_purchases([
            (Decimal("100"), Decimal("91.66"), Decimal("600000")),  # 100×6000
            (Decimal("50"), Decimal("75.00"), Decimal("250000")),   # 50×5000
        ])
        svc = self._make_service(purchases=purchases)
        rate = svc.compute()
        self.assertIsNotNone(rate)
        # Σvalue = 850000, Σfine = 100*0.9166 + 50*0.75 = 91.66 + 37.5 = 129.16
        expected = Decimal("850000") / Decimal("129.16")
        self.assertAlmostEqual(float(rate), float(expected), places=2)
        self.assertAlmostEqual(float(rate), 6580.985, places=1)

    def test_empty_returns_none(self):
        svc = self._make_service()
        self.assertIsNone(svc.compute())

    def test_zero_fine_grams_returns_none(self):
        """All purity rows = 0% → Σfine = 0 → None (no divide-by-zero)."""
        purchases = (Decimal("100000"), Decimal("0"))
        svc = self._make_service(purchases=purchases)
        self.assertIsNone(svc.compute())

    def test_aggregates_across_sources(self):
        """Opening + purchases + transfers all roll up into one rate."""
        opening = (Decimal("1000"), Decimal("0.5"))      # ₹1000 over 0.5 fine g
        purchases = (Decimal("3000"), Decimal("1.5"))    # ₹3000 over 1.5 fine g
        transfers = (Decimal("500"), Decimal("0.25"))    # ₹500 over 0.25 fine g
        svc = self._make_service(opening=opening, purchases=purchases, transfers=transfers)
        rate = svc.compute()
        # Σ = 4500 / 2.25 = 2000
        self.assertEqual(rate, Decimal("2000"))


class TestFineGoldRateFYResolution(SimpleTestCase):
    """FY start must resolve correctly from end_date even without DB FY rows."""

    @patch("accounting.fine_gold_service.FiscalYearMaster")
    def test_fallback_to_april_first(self, mock_fy):
        # No FY row matches → fallback derives Indian FY April 1.
        # Service chains: FYM.objects.filter(...).filter(...).order_by(...).first()
        chain = mock_fy.objects.filter.return_value
        chain.filter.return_value.order_by.return_value.first.return_value = None
        chain.order_by.return_value.first.return_value = None
        svc = FineGoldRateService.__new__(FineGoldRateService)
        svc.retail_ids = [1]
        svc.end_date = date(2026, 5, 15)
        svc.fy_start = svc._resolve_fy_start()
        self.assertEqual(svc.fy_start, date(2026, 4, 1))

        svc.end_date = date(2026, 2, 15)
        svc.fy_start = svc._resolve_fy_start()
        self.assertEqual(svc.fy_start, date(2025, 4, 1))
