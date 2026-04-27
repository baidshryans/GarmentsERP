from datetime import date, timedelta
from django.test import TestCase
from unittest.mock import patch, MagicMock
from vendor_analytics.services import StockAgeingService


class TestStockAgeingBucket(TestCase):
    """Unit-test the pure _bucket() helper — no DB needed."""

    def test_bucket_0_30(self):
        self.assertEqual(StockAgeingService._bucket(0), '0_30')
        self.assertEqual(StockAgeingService._bucket(30), '0_30')

    def test_bucket_31_60(self):
        self.assertEqual(StockAgeingService._bucket(31), '31_60')
        self.assertEqual(StockAgeingService._bucket(60), '31_60')

    def test_bucket_61_90(self):
        self.assertEqual(StockAgeingService._bucket(61), '61_90')
        self.assertEqual(StockAgeingService._bucket(90), '61_90')

    def test_bucket_90_plus(self):
        self.assertEqual(StockAgeingService._bucket(91), '90_plus')
        self.assertEqual(StockAgeingService._bucket(200), '90_plus')


class TestStockAgeingGetData(TestCase):
    """Integration-style test: mock the queryset, verify summary structure."""

    @patch('vendor_analytics.services.BarcodeMain')
    def test_empty_returns_valid_structure(self, MockBarcodeMain):
        MockBarcodeMain.objects.filter.return_value.select_related.return_value = []
        svc = StockAgeingService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertIn('summary', result)
        self.assertIn('by_item', result)
        self.assertIn('by_barcode', result)
        self.assertIn('ageing_score', result['summary'])
