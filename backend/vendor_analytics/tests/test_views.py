"""Tests for vendor analytics API views."""
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient

User = get_user_model()

# Base URL prefix (no host needed with APIClient)
DASHBOARD_URL = '/vendor-analytics/api/vendor-dashboard/'
STOCK_AGEING_URL = '/vendor-analytics/api/stock-ageing/'
DESIGN_PERF_URL = '/vendor-analytics/api/design-performance/'
INV_TURNOVER_URL = '/vendor-analytics/api/inventory-turnover/'
ITEM_PERF_URL = '/vendor-analytics/api/item-performance/'


def _make_user():
    """Create a minimal authenticated user."""
    return User.objects.create_user(username='testvendor', password='pass123')


def _make_retail():
    """Return a simple mock retail object with id=1."""
    retail = MagicMock()
    retail.id = 1
    return retail


# ─── VendorDashboardView ──────────────────────────────────────────────────────

class TestVendorDashboardView(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.retail = _make_retail()

    def test_missing_vendor_id_returns_400(self):
        """GET without vendor_id should return 400."""
        self.client.force_authenticate(user=self.user)
        # Attach retail to request via force_authenticate won't set request.retail;
        # patch the view helper instead.
        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(DASHBOARD_URL)
        self.assertEqual(response.status_code, 400)
        self.assertIn('vendor_id', response.data.get('error', ''))

    def test_unauthenticated_returns_401(self):
        """Unauthenticated request should be rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.get(DASHBOARD_URL, {'vendor_id': '10'})
        self.assertIn(response.status_code, [401, 403])

    @patch('vendor_analytics.views.VendorDashboardService')
    def test_returns_200_with_service_data(self, MockService):
        """GET with valid params returns 200 and service data."""
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {'summary': 'ok'}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(DASHBOARD_URL, {'vendor_id': '42'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'summary': 'ok'})

    @patch('vendor_analytics.views.VendorDashboardService')
    def test_service_receives_correct_params(self, MockService):
        """Service is instantiated with retail_id, vendor_id and optional params."""
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=7):
            self.client.get(
                DASHBOARD_URL,
                {'vendor_id': '99', 'from_date': '2025-01-01', 'to_date': '2025-12-31'},
            )

        MockService.assert_called_once_with(
            7, '99',
            from_date='2025-01-01',
            to_date='2025-12-31',
            item_type=None,
            purity_id=None,
            design_code=None,
        )

    @patch('vendor_analytics.views.VendorDashboardService')
    def test_service_exception_returns_500(self, MockService):
        """If the service raises, the view returns 500."""
        MockService.return_value.get_data.side_effect = RuntimeError('db down')

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(DASHBOARD_URL, {'vendor_id': '5'})

        self.assertEqual(response.status_code, 500)
        self.assertIn('db down', response.data.get('error', ''))


# ─── StockAgeingView ──────────────────────────────────────────────────────────

class TestStockAgeingView(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_missing_vendor_id_returns_400(self):
        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(STOCK_AGEING_URL)
        self.assertEqual(response.status_code, 400)
        self.assertIn('vendor_id', response.data.get('error', ''))

    @patch('vendor_analytics.views.StockAgeingService')
    def test_returns_200_with_service_data(self, MockService):
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {'buckets': []}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(STOCK_AGEING_URL, {'vendor_id': '10'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'buckets': []})

    @patch('vendor_analytics.views.StockAgeingService')
    def test_service_receives_correct_params(self, MockService):
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=3):
            self.client.get(STOCK_AGEING_URL, {'vendor_id': '20', 'item_type': 'GOLD'})

        MockService.assert_called_once_with(
            3, '20',
            from_date=None,
            to_date=None,
            item_type='GOLD',
            purity_id=None,
            design_code=None,
        )

    @patch('vendor_analytics.views.StockAgeingService')
    def test_service_exception_returns_500(self, MockService):
        MockService.return_value.get_data.side_effect = ValueError('bad query')

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(STOCK_AGEING_URL, {'vendor_id': '5'})

        self.assertEqual(response.status_code, 500)
        self.assertIn('bad query', response.data.get('error', ''))


# ─── DesignPerformanceView ────────────────────────────────────────────────────

class TestDesignPerformanceView(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_missing_vendor_id_returns_400(self):
        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(DESIGN_PERF_URL)
        self.assertEqual(response.status_code, 400)
        self.assertIn('vendor_id', response.data.get('error', ''))

    @patch('vendor_analytics.views.DesignPerformanceService')
    def test_returns_200_with_service_data(self, MockService):
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {'designs': []}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(DESIGN_PERF_URL, {'vendor_id': '15'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'designs': []})

    @patch('vendor_analytics.views.DesignPerformanceService')
    def test_service_receives_correct_params(self, MockService):
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=5):
            self.client.get(
                DESIGN_PERF_URL,
                {'vendor_id': '77', 'purity_id': '2', 'design_code': 'RING-01'},
            )

        MockService.assert_called_once_with(
            5, '77',
            from_date=None,
            to_date=None,
            item_type=None,
            purity_id='2',
            design_code='RING-01',
        )

    @patch('vendor_analytics.views.DesignPerformanceService')
    def test_service_exception_returns_500(self, MockService):
        MockService.return_value.get_data.side_effect = Exception('fail')

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(DESIGN_PERF_URL, {'vendor_id': '5'})

        self.assertEqual(response.status_code, 500)


# ─── InventoryTurnoverView ────────────────────────────────────────────────────

class TestInventoryTurnoverView(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_missing_vendor_id_returns_400(self):
        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(INV_TURNOVER_URL)
        self.assertEqual(response.status_code, 400)

    @patch('vendor_analytics.views.InventoryTurnoverService')
    def test_returns_200_with_service_data(self, MockService):
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {'turnover': 3.5}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(INV_TURNOVER_URL, {'vendor_id': '8'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'turnover': 3.5})

    @patch('vendor_analytics.views.InventoryTurnoverService')
    def test_service_exception_returns_500(self, MockService):
        MockService.return_value.get_data.side_effect = Exception('turnover fail')

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(INV_TURNOVER_URL, {'vendor_id': '9'})

        self.assertEqual(response.status_code, 500)
        self.assertIn('turnover fail', response.data.get('error', ''))


# ─── ItemPerformanceView ──────────────────────────────────────────────────────

class TestItemPerformanceView(APITestCase):

    def setUp(self):
        self.user = _make_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_missing_vendor_id_returns_400(self):
        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(ITEM_PERF_URL)
        self.assertEqual(response.status_code, 400)

    @patch('vendor_analytics.views.ItemPerformanceService')
    def test_returns_200_with_service_data(self, MockService):
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {'items': [{'sku': 'A1'}]}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(ITEM_PERF_URL, {'vendor_id': '33'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'items': [{'sku': 'A1'}]})

    @patch('vendor_analytics.views.ItemPerformanceService')
    def test_service_receives_correct_params(self, MockService):
        mock_instance = MagicMock()
        mock_instance.get_data.return_value = {}
        MockService.return_value = mock_instance

        with patch('vendor_analytics.views._get_retail_id', return_value=2):
            self.client.get(
                ITEM_PERF_URL,
                {'vendor_id': '55', 'from_date': '2024-04-01', 'to_date': '2025-03-31'},
            )

        MockService.assert_called_once_with(
            2, '55',
            from_date='2024-04-01',
            to_date='2025-03-31',
            item_type=None,
            purity_id=None,
            design_code=None,
        )

    @patch('vendor_analytics.views.ItemPerformanceService')
    def test_service_exception_returns_500(self, MockService):
        MockService.return_value.get_data.side_effect = Exception('item fail')

        with patch('vendor_analytics.views._get_retail_id', return_value=1):
            response = self.client.get(ITEM_PERF_URL, {'vendor_id': '5'})

        self.assertEqual(response.status_code, 500)
        self.assertIn('item fail', response.data.get('error', ''))


# ─── _get_retail_id helper ────────────────────────────────────────────────────

class TestGetRetailIdHelper(APITestCase):
    """Unit-test the _get_retail_id helper directly."""

    def test_raises_when_retail_missing(self):
        from vendor_analytics.views import _get_retail_id
        req = MagicMock()
        req.retail = None
        with self.assertRaises(ValueError):
            _get_retail_id(req)

    def test_returns_retail_id(self):
        from vendor_analytics.views import _get_retail_id
        req = MagicMock()
        req.retail = MagicMock()
        req.retail.id = 42
        result = _get_retail_id(req)
        self.assertEqual(result, 42)
