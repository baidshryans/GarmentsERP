"""Tests for DesignPerformanceService, InventoryTurnoverService,
ItemPerformanceService, VendorDashboardService."""
from datetime import date
from django.test import TestCase
from unittest.mock import patch, MagicMock, PropertyMock

from vendor_analytics.services import (
    DesignPerformanceService,
    InventoryTurnoverService,
    ItemPerformanceService,
    VendorDashboardService,
)


# ─── DesignPerformanceService ─────────────────────────────────────────────────

class TestDesignPerformanceService(TestCase):

    def test_velocity_status_fast(self):
        """avg_days < 30 → 'fast'"""
        svc = DesignPerformanceService(retail_id=1, vendor_id=1)
        self.assertEqual(svc._velocity_status(29, 1), 'fast')
        self.assertEqual(svc._velocity_status(0, 5), 'fast')

    def test_velocity_status_slow(self):
        """30 <= avg_days <= 60 → 'slow'"""
        svc = DesignPerformanceService(retail_id=1, vendor_id=1)
        self.assertEqual(svc._velocity_status(30, 2), 'slow')
        self.assertEqual(svc._velocity_status(60, 2), 'slow')

    def test_velocity_status_dead_high_avg(self):
        """avg_days > 60 → 'dead'"""
        svc = DesignPerformanceService(retail_id=1, vendor_id=1)
        self.assertEqual(svc._velocity_status(61, 1), 'dead')
        self.assertEqual(svc._velocity_status(200, 3), 'dead')

    def test_velocity_status_dead_no_sold(self):
        """pcs_sold == 0 → 'dead' regardless of avg"""
        svc = DesignPerformanceService(retail_id=1, vendor_id=1)
        self.assertEqual(svc._velocity_status(0, 0), 'dead')
        self.assertEqual(svc._velocity_status(10, 0), 'dead')

    @patch('vendor_analytics.services.SalesVouItem')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_get_data_returns_correct_keys(self, MockBarcodeMain, MockSalesVouItem):
        MockBarcodeMain.objects.filter.return_value.select_related.return_value = []
        MockSalesVouItem.objects.filter.return_value.select_related.return_value = []
        svc = DesignPerformanceService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertIn('designs', result)
        self.assertIsInstance(result['designs'], list)

    @patch('vendor_analytics.services.SalesVouItem')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_get_data_groups_by_design_code(self, MockBarcodeMain, MockSalesVouItem):
        """Two barcodes with same design_code produce one design entry."""
        def make_barcode(barcode_id, design_code):
            b = MagicMock()
            b.barcode = barcode_id
            b.design_code = design_code
            b.item.item_name = 'Ring'
            b.item_id = 10
            b.total_amount = 1000
            b.pur_voucher.billno.date1 = date(2025, 1, 1)
            return b

        barcodes = [make_barcode('B001', 'D1'), make_barcode('B002', 'D1')]
        MockBarcodeMain.objects.filter.return_value.select_related.return_value = barcodes
        MockSalesVouItem.objects.filter.return_value.select_related.return_value = []

        svc = DesignPerformanceService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertEqual(len(result['designs']), 1)
        self.assertEqual(result['designs'][0]['pcs_purchased'], 2)

    @patch('vendor_analytics.services.SalesVouItem')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_get_data_sold_barcode_counted(self, MockBarcodeMain, MockSalesVouItem):
        """A barcode with a matching SalesVouItem is counted as sold."""
        b = MagicMock()
        b.barcode = 'B001'
        b.design_code = 'DX'
        b.item.item_name = 'Bangle'
        b.item_id = 20
        b.total_amount = 5000
        b.pur_voucher.billno.date1 = date(2025, 1, 1)

        svi = MagicMock()
        svi.barcode_id = 'B001'
        svi.bill.date1 = date(2025, 1, 15)  # 14 days → fast

        MockBarcodeMain.objects.filter.return_value.select_related.return_value = [b]
        MockSalesVouItem.objects.filter.return_value.select_related.return_value = [svi]

        svc = DesignPerformanceService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        d = result['designs'][0]
        self.assertEqual(d['pcs_sold'], 1)
        self.assertEqual(d['pcs_unsold'], 0)
        self.assertAlmostEqual(d['avg_days_to_sell'], 14.0)
        self.assertEqual(d['velocity_status'], 'fast')


# ─── InventoryTurnoverService ─────────────────────────────────────────────────

class TestInventoryTurnoverService(TestCase):

    def test_get_data_returns_correct_keys(self):
        svc = InventoryTurnoverService(retail_id=1, vendor_id=1,
                                       from_date='2025-04-01', to_date='2025-03-31')
        with patch('vendor_analytics.services.BarcodeMain') as MB, \
             patch('vendor_analytics.services.PurchaseVoucherItems') as MPV, \
             patch('vendor_analytics.services.PurchaseReturnItems') as MPR, \
             patch('vendor_analytics.services.FiscalYearMaster') as MFY:
            # make aggregate calls return 0
            MB.objects.filter.return_value.aggregate.return_value = {'total_amount__sum': None}
            MPV.objects.filter.return_value.aggregate.return_value = {'item_value__sum': None}
            MPR.objects.filter.return_value.aggregate.return_value = {'item_value__sum': None}
            MFY.objects.all.return_value.order_by.return_value = []
            result = svc.get_data()

        self.assertIn('current_period', result)
        self.assertIn('monthly_trend', result)
        self.assertIn('yoy_comparison', result)
        cp = result['current_period']
        self.assertIn('turnover_ratio', cp)
        self.assertIn('days_inventory', cp)
        self.assertIn('cogs', cp)
        self.assertIn('avg_inventory', cp)

    def test_turnover_ratio_formula(self):
        """Known values: COGS=120, avg_inv=60 → ratio=2.0, days=182.5"""
        svc = InventoryTurnoverService(retail_id=1, vendor_id=1,
                                       from_date='2025-01-01', to_date='2025-12-31')
        # Directly test the formula method
        ratio, days = svc._compute_ratio(cogs=120.0, avg_inventory=60.0)
        self.assertAlmostEqual(ratio, 2.0)
        self.assertAlmostEqual(days, 182.5)

    def test_turnover_ratio_zero_inventory(self):
        svc = InventoryTurnoverService(retail_id=1, vendor_id=1)
        ratio, days = svc._compute_ratio(cogs=100.0, avg_inventory=0.0)
        self.assertEqual(ratio, 0.0)
        self.assertEqual(days, 0.0)

    def test_turnover_ratio_zero_cogs(self):
        svc = InventoryTurnoverService(retail_id=1, vendor_id=1)
        ratio, days = svc._compute_ratio(cogs=0.0, avg_inventory=50.0)
        self.assertAlmostEqual(ratio, 0.0)
        self.assertEqual(days, 0.0)

    def test_monthly_trend_length(self):
        """monthly_trend should return 12 entries when no from_date given."""
        svc = InventoryTurnoverService(retail_id=1, vendor_id=1)
        with patch('vendor_analytics.services.BarcodeMain') as MB, \
             patch('vendor_analytics.services.PurchaseVoucherItems') as MPV, \
             patch('vendor_analytics.services.PurchaseReturnItems') as MPR, \
             patch('vendor_analytics.services.FiscalYearMaster') as MFY:
            MB.objects.filter.return_value.aggregate.return_value = {'total_amount__sum': None}
            MPV.objects.filter.return_value.aggregate.return_value = {'item_value__sum': None}
            MPR.objects.filter.return_value.aggregate.return_value = {'item_value__sum': None}
            MFY.objects.all.return_value.order_by.return_value = []
            result = svc.get_data()

        self.assertEqual(len(result['monthly_trend']), 12)
        # Verify format YYYY-MM
        for entry in result['monthly_trend']:
            self.assertRegex(entry['month'], r'^\d{4}-\d{2}$')


# ─── ItemPerformanceService ───────────────────────────────────────────────────

class TestItemPerformanceService(TestCase):

    @patch('vendor_analytics.services.PurchaseReturnItems')
    @patch('vendor_analytics.services.SalesVouItem')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_get_data_returns_correct_keys(self, MockBM, MockSVI, MockPRI):
        MockBM.objects.filter.return_value.select_related.return_value = []
        MockSVI.objects.filter.return_value.select_related.return_value = []
        MockPRI.objects.filter.return_value.values_list.return_value = []
        svc = ItemPerformanceService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertIn('items', result)
        self.assertIsInstance(result['items'], list)

    @patch('vendor_analytics.services.PurchaseReturnItems')
    @patch('vendor_analytics.services.SalesVouItem')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_get_data_groups_by_item(self, MockBM, MockSVI, MockPRI):
        """Two barcodes for same item_id → one item entry."""
        def make_barcode(bc_id):
            b = MagicMock()
            b.barcode = bc_id
            b.item_id = 5
            b.item.item_name = 'Chain'
            b.item.item_type = 'GOLD'
            b.gw = 10.0
            b.total_amount = 2000
            b.pur_voucher_id = bc_id + '_pv'
            return b

        barcodes = [make_barcode('B1'), make_barcode('B2')]
        MockBM.objects.filter.return_value.select_related.return_value = barcodes
        MockSVI.objects.filter.return_value.select_related.return_value = []
        MockPRI.objects.filter.return_value.values_list.return_value = []

        svc = ItemPerformanceService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['pcs_purchased'], 2)

    @patch('vendor_analytics.services.PurchaseReturnItems')
    @patch('vendor_analytics.services.SalesVouItem')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_margin_calculated_correctly(self, MockBM, MockSVI, MockPRI):
        """gross_margin = sale_value - purchase_cost (of sold items)."""
        b = MagicMock()
        b.barcode = 'X1'
        b.item_id = 7
        b.item.item_name = 'Earring'
        b.item.item_type = 'GOLD'
        b.gw = 5.0
        b.total_amount = 3000
        b.pur_voucher_id = 'PV1'

        svi = MagicMock()
        svi.barcode_id = 'X1'
        svi.gw = 4.8
        svi.item_value = 4000

        MockBM.objects.filter.return_value.select_related.return_value = [b]
        MockSVI.objects.filter.return_value.select_related.return_value = [svi]
        MockPRI.objects.filter.return_value.values_list.return_value = []

        svc = ItemPerformanceService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        item = result['items'][0]
        self.assertEqual(item['pcs_sold'], 1)
        self.assertAlmostEqual(item['sale_value'], 4000.0)
        self.assertAlmostEqual(item['purchase_cost'], 3000.0)
        self.assertAlmostEqual(item['gross_margin'], 1000.0)
        self.assertAlmostEqual(item['margin_pct'], 25.0)

    @patch('vendor_analytics.services.PurchaseReturnItems')
    @patch('vendor_analytics.services.SalesVouItem')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_returned_barcode_counted(self, MockBM, MockSVI, MockPRI):
        """A barcode whose pur_voucher_id appears in returned set → pcs_returned=1."""
        b = MagicMock()
        b.barcode = 'Y1'
        b.item_id = 9
        b.item.item_name = 'Necklace'
        b.item.item_type = 'GOLD'
        b.gw = 20.0
        b.total_amount = 8000
        b.pur_voucher_id = 'PV_RET'

        MockBM.objects.filter.return_value.select_related.return_value = [b]
        MockSVI.objects.filter.return_value.select_related.return_value = []
        MockPRI.objects.filter.return_value.values_list.return_value = ['PV_RET']

        svc = ItemPerformanceService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertEqual(result['items'][0]['pcs_returned'], 1)


# ─── VendorDashboardService ───────────────────────────────────────────────────

class TestVendorDashboardService(TestCase):

    def _make_mock_design(self, design_code, pcs_sold, avg_days):
        return {
            'design_code': design_code,
            'pcs_sold': pcs_sold,
            'avg_days_to_sell': avg_days,
            'velocity_status': 'fast',
            'pcs_purchased': pcs_sold + 1,
            'pcs_unsold': 1,
            'item_name': 'Ring',
            'total_value': 10000.0,
        }

    @patch('vendor_analytics.services.DesignPerformanceService')
    @patch('vendor_analytics.services.InventoryTurnoverService')
    @patch('vendor_analytics.services.StockAgeingService')
    @patch('vendor_analytics.services.PurchaseVoucherItems')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_get_data_returns_correct_keys(self, MockBM, MockPVI,
                                           MockSAS, MockITS, MockDPS):
        # BarcodeMain aggregates
        MockBM.objects.filter.return_value.aggregate.return_value = {'total_amount__sum': 50000}
        MockBM.objects.filter.return_value.count.return_value = 10

        # PurchaseVoucherItems aggregate
        MockPVI.objects.filter.return_value.aggregate.return_value = {'item_value__sum': 80000}

        # StockAgeingService
        ageing_inst = MagicMock()
        ageing_inst.get_data.return_value = {
            'summary': {'ageing_score': 35.0, '0_30': 5, '31_60': 3, '61_90': 1, '90_plus': 1,
                        'total_value': 50000.0}
        }
        MockSAS.return_value = ageing_inst

        # InventoryTurnoverService
        turnover_inst = MagicMock()
        turnover_inst.get_data.return_value = {
            'current_period': {'turnover_ratio': 2.5, 'days_inventory': 146.0,
                               'cogs': 100000.0, 'avg_inventory': 40000.0},
            'monthly_trend': [],
            'yoy_comparison': [],
        }
        MockITS.return_value = turnover_inst

        # DesignPerformanceService
        design_inst = MagicMock()
        design_inst.get_data.return_value = {
            'designs': [
                self._make_mock_design('D1', 3, 20.0),
                self._make_mock_design('D2', 1, 45.0),
            ]
        }
        MockDPS.return_value = design_inst

        svc = VendorDashboardService(retail_id=1, vendor_id=1)
        result = svc.get_data()

        # Top-level keys
        self.assertIn('vendor', result)
        self.assertIn('financial', result)
        self.assertIn('inventory', result)
        self.assertIn('performance', result)
        self.assertIn('monthly_purchase_trend', result)
        self.assertIn('top_designs', result)

        # financial sub-keys
        fin = result['financial']
        self.assertIn('total_purchases', fin)
        self.assertIn('outstanding_payable', fin)
        self.assertIn('avg_payment_days', fin)

        # inventory sub-keys
        inv = result['inventory']
        self.assertIn('total_stock_value', inv)
        self.assertIn('ageing_score', inv)
        self.assertIn('turnover_ratio', inv)

        # performance sub-keys
        perf = result['performance']
        self.assertIn('best_design', perf)
        self.assertIn('sell_through_pct', perf)
        self.assertIn('avg_days_to_sell', perf)

    @patch('vendor_analytics.services.DesignPerformanceService')
    @patch('vendor_analytics.services.InventoryTurnoverService')
    @patch('vendor_analytics.services.StockAgeingService')
    @patch('vendor_analytics.services.PurchaseVoucherItems')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_best_design_lowest_avg_days(self, MockBM, MockPVI, MockSAS, MockITS, MockDPS):
        """best_design is the design_code with the lowest avg_days_to_sell where pcs_sold>0."""
        MockBM.objects.filter.return_value.aggregate.return_value = {'total_amount__sum': None}
        MockBM.objects.filter.return_value.count.return_value = 0
        MockPVI.objects.filter.return_value.aggregate.return_value = {'item_value__sum': None}

        ageing_inst = MagicMock()
        ageing_inst.get_data.return_value = {'summary': {'ageing_score': 0.0}}
        MockSAS.return_value = ageing_inst

        turnover_inst = MagicMock()
        turnover_inst.get_data.return_value = {
            'current_period': {'turnover_ratio': 0.0, 'days_inventory': 0.0,
                               'cogs': 0.0, 'avg_inventory': 0.0},
            'monthly_trend': [], 'yoy_comparison': [],
        }
        MockITS.return_value = turnover_inst

        design_inst = MagicMock()
        design_inst.get_data.return_value = {
            'designs': [
                self._make_mock_design('SLOW', 2, 55.0),
                self._make_mock_design('FAST', 3, 10.0),  # best
                self._make_mock_design('DEAD', 0, 0.0),
            ]
        }
        MockDPS.return_value = design_inst

        svc = VendorDashboardService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertEqual(result['performance']['best_design'], 'FAST')

    @patch('vendor_analytics.services.DesignPerformanceService')
    @patch('vendor_analytics.services.InventoryTurnoverService')
    @patch('vendor_analytics.services.StockAgeingService')
    @patch('vendor_analytics.services.PurchaseVoucherItems')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_top_designs_max_5(self, MockBM, MockPVI, MockSAS, MockITS, MockDPS):
        """top_designs returns at most 5 entries, sorted by pcs_sold desc."""
        MockBM.objects.filter.return_value.aggregate.return_value = {'total_amount__sum': None}
        MockBM.objects.filter.return_value.count.return_value = 0
        MockPVI.objects.filter.return_value.aggregate.return_value = {'item_value__sum': None}

        ageing_inst = MagicMock()
        ageing_inst.get_data.return_value = {'summary': {'ageing_score': 0.0}}
        MockSAS.return_value = ageing_inst

        turnover_inst = MagicMock()
        turnover_inst.get_data.return_value = {
            'current_period': {'turnover_ratio': 0.0, 'days_inventory': 0.0,
                               'cogs': 0.0, 'avg_inventory': 0.0},
            'monthly_trend': [], 'yoy_comparison': [],
        }
        MockITS.return_value = turnover_inst

        designs = [self._make_mock_design(f'D{i}', i, 20.0) for i in range(8)]
        design_inst = MagicMock()
        design_inst.get_data.return_value = {'designs': designs}
        MockDPS.return_value = design_inst

        svc = VendorDashboardService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertLessEqual(len(result['top_designs']), 5)
        # Should be top 5 by pcs_sold descending
        sold_counts = [d['sold_pcs'] for d in result['top_designs']]
        self.assertEqual(sold_counts, sorted(sold_counts, reverse=True))

    @patch('vendor_analytics.services.DesignPerformanceService')
    @patch('vendor_analytics.services.InventoryTurnoverService')
    @patch('vendor_analytics.services.StockAgeingService')
    @patch('vendor_analytics.services.PurchaseVoucherItems')
    @patch('vendor_analytics.services.BarcodeMain')
    def test_monthly_purchase_trend_has_12_months(self, MockBM, MockPVI,
                                                   MockSAS, MockITS, MockDPS):
        """monthly_purchase_trend always has 12 month entries."""
        MockBM.objects.filter.return_value.aggregate.return_value = {'total_amount__sum': None}
        MockBM.objects.filter.return_value.count.return_value = 0
        MockPVI.objects.filter.return_value.aggregate.return_value = {'item_value__sum': None}

        ageing_inst = MagicMock()
        ageing_inst.get_data.return_value = {'summary': {'ageing_score': 0.0}}
        MockSAS.return_value = ageing_inst

        turnover_inst = MagicMock()
        turnover_inst.get_data.return_value = {
            'current_period': {'turnover_ratio': 0.0, 'days_inventory': 0.0,
                               'cogs': 0.0, 'avg_inventory': 0.0},
            'monthly_trend': [], 'yoy_comparison': [],
        }
        MockITS.return_value = turnover_inst

        design_inst = MagicMock()
        design_inst.get_data.return_value = {'designs': []}
        MockDPS.return_value = design_inst

        svc = VendorDashboardService(retail_id=1, vendor_id=1)
        result = svc.get_data()
        self.assertEqual(len(result['monthly_purchase_trend']), 12)
        for entry in result['monthly_purchase_trend']:
            self.assertIn('month', entry)
            self.assertIn('value', entry)
