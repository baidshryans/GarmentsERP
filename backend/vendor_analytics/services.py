"""Vendor analytics query services."""
from datetime import date
from django.db.models import Sum

from inventory.models import BarcodeMain, BarcodeTransaction
from purchase.models import (
    PurchaseVoucher, PurchaseVoucherItems,
    PurchaseReturn, PurchaseReturnItems,
)
from sales.models import SalesVouItem
from mastersconfig.models import FiscalYearMaster


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_date(val):
    """Parse ISO date string → date, or return None."""
    if not val:
        return None
    if isinstance(val, date):
        return val
    from datetime import datetime
    return datetime.strptime(str(val), '%Y-%m-%d').date()


# ─── Stock Ageing ─────────────────────────────────────────────────────────────

class StockAgeingService:
    """
    Returns in-stock vendor barcodes bucketed by age since purchase date.
    Three levels: summary totals, per-item breakdown, per-barcode list.
    """

    def __init__(self, retail_id, vendor_id, from_date=None, to_date=None,
                 item_type=None, purity_id=None, design_code=None):
        self.retail_id = retail_id
        self.vendor_id = vendor_id
        self.from_date = _parse_date(from_date)
        self.to_date = _parse_date(to_date)
        self.item_type = item_type or None
        self.purity_id = int(purity_id) if purity_id else None
        self.design_code = design_code or None
        self.today = date.today()

    def _base_qs(self):
        qs = BarcodeMain.objects.filter(
            pur_voucher__isnull=False,
            pur_voucher__billno__ldgr_id=self.vendor_id,
            stk_status=True,
            retail_id=self.retail_id,
        ).select_related('item', 'pur_voucher__billno')
        if self.from_date:
            qs = qs.filter(pur_voucher__billno__date1__gte=self.from_date)
        if self.to_date:
            qs = qs.filter(pur_voucher__billno__date1__lte=self.to_date)
        if self.item_type:
            qs = qs.filter(item__item_type=self.item_type)
        if self.purity_id:
            qs = qs.filter(purity_id=self.purity_id)
        if self.design_code:
            qs = qs.filter(design_code=self.design_code)
        return qs

    @staticmethod
    def _bucket(age_days):
        if age_days <= 30:
            return '0_30'
        if age_days <= 60:
            return '31_60'
        if age_days <= 90:
            return '61_90'
        return '90_plus'

    def get_data(self):
        summary = {
            '0_30': 0, '31_60': 0, '61_90': 0, '90_plus': 0,
            'total_value': 0.0, 'ageing_score': 0.0,
        }
        by_item = {}
        by_barcode = []

        for b in self._base_qs():
            purchase_date = b.pur_voucher.billno.date1
            age_days = max(0, (self.today - purchase_date).days)
            bucket = self._bucket(age_days)
            value = float(b.total_amount or 0)

            summary[bucket] += 1
            summary['total_value'] += value

            iid = b.item_id
            if iid not in by_item:
                by_item[iid] = {
                    'item_id': iid,
                    'item_name': b.item.item_name,
                    '0_30': 0, '31_60': 0, '61_90': 0, '90_plus': 0,
                    'value': 0.0,
                }
            by_item[iid][bucket] += 1
            by_item[iid]['value'] += value

            by_barcode.append({
                'barcode': b.barcode,
                'item': b.item.item_name,
                'design_code': b.design_code or '',
                'purchase_date': purchase_date.isoformat(),
                'age_days': age_days,
                'gw': float(b.gw or 0),
                'value': value,
            })

        total_val = summary['total_value'] or 1.0
        aged_val = sum(bc['value'] for bc in by_barcode if bc['age_days'] > 60)
        summary['ageing_score'] = round(aged_val / total_val * 100, 1)

        return {
            'summary': summary,
            'by_item': list(by_item.values()),
            'by_barcode': sorted(by_barcode, key=lambda x: -x['age_days']),
        }


# ─── Design Performance ───────────────────────────────────────────────────────

class DesignPerformanceService:
    """
    Analyses sell-through velocity per design code for a vendor.
    Returns purchase vs sold counts, average days to sell, and velocity status.
    """

    def __init__(self, retail_id, vendor_id, from_date=None, to_date=None,
                 item_type=None, purity_id=None, design_code=None):
        self.retail_id = retail_id
        self.vendor_id = vendor_id
        self.from_date = _parse_date(from_date)
        self.to_date = _parse_date(to_date)
        self.item_type = item_type or None
        self.purity_id = int(purity_id) if purity_id else None
        self.design_code = design_code or None

    @staticmethod
    def _velocity_status(avg_days, pcs_sold):
        if pcs_sold == 0:
            return 'dead'
        if avg_days < 30:
            return 'fast'
        if avg_days <= 60:
            return 'slow'
        return 'dead'

    def _base_qs(self):
        qs = BarcodeMain.objects.filter(
            pur_voucher__isnull=False,
            pur_voucher__billno__ldgr_id=self.vendor_id,
            retail_id=self.retail_id,
        ).select_related('item', 'pur_voucher__billno')
        if self.from_date:
            qs = qs.filter(pur_voucher__billno__date1__gte=self.from_date)
        if self.to_date:
            qs = qs.filter(pur_voucher__billno__date1__lte=self.to_date)
        if self.item_type:
            qs = qs.filter(item__item_type=self.item_type)
        if self.purity_id:
            qs = qs.filter(purity_id=self.purity_id)
        if self.design_code:
            qs = qs.filter(design_code=self.design_code)
        return qs

    def get_data(self):
        barcodes = list(self._base_qs())
        barcode_pks = [b.id for b in barcodes]

        # Build sold map: BarcodeMain.id -> sale_date
        sold_map = {}
        for svi in SalesVouItem.objects.filter(
            barcode_id__in=barcode_pks
        ).select_related('billno'):
            if svi.billno_id and svi.billno.date1:
                sold_map[svi.barcode_id] = svi.billno.date1

        by_design = {}
        for b in barcodes:
            dc = b.design_code or ''
            if dc not in by_design:
                by_design[dc] = {
                    'design_code': dc,
                    'item_name': b.item.item_name,
                    'pcs_purchased': 0,
                    'pcs_sold': 0,
                    'total_value': 0.0,
                    '_days_list': [],
                }
            entry = by_design[dc]
            entry['pcs_purchased'] += 1
            entry['total_value'] += float(b.total_amount or 0)

            if b.id in sold_map:
                sale_date = sold_map[b.id]
                purchase_date = b.pur_voucher.billno.date1
                days = max(0, (sale_date - purchase_date).days)
                entry['pcs_sold'] += 1
                entry['_days_list'].append(days)

        designs = []
        for entry in by_design.values():
            days_list = entry.pop('_days_list')
            pcs_sold = entry['pcs_sold']
            avg_days = (sum(days_list) / len(days_list)) if days_list else 0.0
            entry['pcs_unsold'] = entry['pcs_purchased'] - pcs_sold
            entry['avg_days_to_sell'] = round(avg_days, 2)
            entry['velocity_status'] = self._velocity_status(avg_days, pcs_sold)
            designs.append(entry)

        return {'designs': designs}


# ─── Inventory Turnover ───────────────────────────────────────────────────────

class InventoryTurnoverService:
    """
    Computes inventory turnover ratio and days-inventory-outstanding for a vendor.
    Provides current-period metrics, 12-month trend, and year-over-year comparison.
    """

    def __init__(self, retail_id, vendor_id, from_date=None, to_date=None,
                 item_type=None, purity_id=None, design_code=None):
        self.retail_id = retail_id
        self.vendor_id = vendor_id
        self.from_date = _parse_date(from_date)
        self.to_date = _parse_date(to_date)
        self.item_type = item_type or None
        self.purity_id = int(purity_id) if purity_id else None
        self.design_code = design_code or None

    @staticmethod
    def _compute_ratio(cogs, avg_inventory):
        if avg_inventory <= 0:
            return 0.0, 0.0
        ratio = cogs / avg_inventory
        days = (365.0 / ratio) if ratio > 0 else 0.0
        return round(ratio, 4), round(days, 2)

    def _inv_value_before(self, cutoff_date):
        """Sum of total_amount for vendor barcodes created before cutoff_date (opening stock proxy)."""
        if not cutoff_date:
            return 0.0
        val = BarcodeMain.objects.filter(
            pur_voucher__isnull=False,
            pur_voucher__billno__ldgr_id=self.vendor_id,
            retail_id=self.retail_id,
            created_date__lt=cutoff_date,
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        return float(val)

    def _inv_value_in_stock_at(self, cutoff_date):
        """Sum of total_amount for vendor barcodes created on or before cutoff_date still in stock."""
        val = BarcodeMain.objects.filter(
            pur_voucher__isnull=False,
            pur_voucher__billno__ldgr_id=self.vendor_id,
            retail_id=self.retail_id,
            stk_status=True,
            created_date__lte=cutoff_date,
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        return float(val)

    def _purchases_in_range(self, from_date, to_date):
        qs = PurchaseVoucherItems.objects.filter(
            billno__ldgr_id=self.vendor_id,
            billno__retail_id=self.retail_id,
            billno__date1__range=[from_date, to_date],
        )
        return float(qs.aggregate(Sum('item_value'))['item_value__sum'] or 0)

    def _returns_in_range(self, from_date, to_date):
        qs = PurchaseReturn.objects.filter(
            ldgr_id=self.vendor_id,
            retail_id=self.retail_id,
            date1__range=[from_date, to_date],
        )
        return float(qs.aggregate(Sum('bill_value'))['bill_value__sum'] or 0)

    def _period_metrics(self, from_date, to_date):
        opening = self._inv_value_before(from_date)
        closing = self._inv_value_in_stock_at(to_date)
        purchases = self._purchases_in_range(from_date, to_date)
        returns = self._returns_in_range(from_date, to_date)
        cogs = max(0.0, opening + purchases - returns - closing)
        avg_inv = (opening + closing) / 2.0
        ratio, days = self._compute_ratio(cogs, avg_inv)
        return {
            'turnover_ratio': ratio,
            'days_inventory': days,
            'cogs': round(cogs, 2),
            'avg_inventory': round(avg_inv, 2),
        }

    def _months_in_range(self, from_date, to_date):
        """Yield (year, month) for every month that starts within [from_date, to_date]."""
        year, month = from_date.year, from_date.month
        end_year, end_month = to_date.year, to_date.month
        while (year, month) <= (end_year, end_month):
            yield year, month
            month += 1
            if month > 12:
                month = 1
                year += 1

    def _last_12_months(self):
        import calendar
        from datetime import date as _date
        today = _date.today()
        months = []
        year, month = today.year, today.month
        for _ in range(12):
            month -= 1
            if month == 0:
                month = 12
                year -= 1
            months.append((year, month))
        months.reverse()
        return months

    def get_data(self):
        # Current period
        from_date = self.from_date
        to_date = self.to_date
        if from_date and to_date:
            current = self._period_metrics(from_date, to_date)
        else:
            # Default: current financial year (April 1) to today
            today = date.today()
            fy_year = today.year if today.month >= 4 else today.year - 1
            from_date = date(fy_year, 4, 1)
            to_date = today
            current = self._period_metrics(from_date, to_date)

        # Monthly trend — months within the selected date range
        import calendar
        monthly_trend = []
        for year, month in self._months_in_range(from_date, to_date):
            last_day = calendar.monthrange(year, month)[1]
            m_from = date(year, month, 1)
            m_to = date(year, month, last_day)
            m = self._period_metrics(m_from, m_to)
            monthly_trend.append({
                'month': f'{year:04d}-{month:02d}',
                'turnover_ratio': m['turnover_ratio'],
                'days_inventory': m['days_inventory'],
            })

        # YoY comparison
        yoy = []
        for fy in FiscalYearMaster.objects.filter(retail_id=self.retail_id).order_by('fy_start'):
            m = self._period_metrics(fy.fy_start, fy.fy_end)
            yoy.append({
                'fy': fy.fy_code,
                'turnover_ratio': m['turnover_ratio'],
                'days_inventory': m['days_inventory'],
            })

        return {
            'current_period': current,
            'monthly_trend': monthly_trend,
            'yoy_comparison': yoy,
        }


# ─── Item Performance ─────────────────────────────────────────────────────────

class ItemPerformanceService:
    """
    Per-item breakdown of weight loss, gross margin, and sell-through for a vendor.
    """

    def __init__(self, retail_id, vendor_id, from_date=None, to_date=None,
                 item_type=None, purity_id=None, design_code=None):
        self.retail_id = retail_id
        self.vendor_id = vendor_id
        self.from_date = _parse_date(from_date)
        self.to_date = _parse_date(to_date)
        self.item_type = item_type or None
        self.purity_id = int(purity_id) if purity_id else None
        self.design_code = design_code or None

    def _base_qs(self):
        qs = BarcodeMain.objects.filter(
            pur_voucher__isnull=False,
            pur_voucher__billno__ldgr_id=self.vendor_id,
            retail_id=self.retail_id,
        ).select_related('item', 'pur_voucher', 'pur_voucher__billno')
        if self.from_date:
            qs = qs.filter(pur_voucher__billno__date1__gte=self.from_date)
        if self.to_date:
            qs = qs.filter(pur_voucher__billno__date1__lte=self.to_date)
        if self.item_type:
            qs = qs.filter(item__item_type=self.item_type)
        if self.purity_id:
            qs = qs.filter(purity_id=self.purity_id)
        if self.design_code:
            qs = qs.filter(design_code=self.design_code)
        return qs

    def get_data(self):
        barcodes = list(self._base_qs())
        barcode_pks = [b.id for b in barcodes]

        # Sales map: BarcodeMain.id -> {gw, sale_value}
        sales_map = {}
        for svi in SalesVouItem.objects.filter(
            barcode_id__in=barcode_pks
        ).select_related():
            sales_map[svi.barcode_id] = {
                'gw': float(svi.gw or 0),
                'sale_value': float(svi.amount or 0),
            }

        # Returns map: set of PurchaseVoucher IDs that have a purchase return
        pv_ids = set(b.pur_voucher.billno_id for b in barcodes if b.pur_voucher_id)
        returned_pv_ids = set(
            PurchaseReturn.objects.filter(purchase_voucher_ref_id__in=pv_ids)
            .values_list('purchase_voucher_ref_id', flat=True)
        )

        by_item = {}
        for b in barcodes:
            iid = b.item_id
            if iid not in by_item:
                by_item[iid] = {
                    'item_id': iid,
                    'item_name': b.item.item_name,
                    'item_type': b.item.item_type,
                    'gw_purchased': 0.0,
                    'gw_sold': 0.0,
                    'purchase_cost': 0.0,   # cost of sold items
                    'sale_value': 0.0,
                    'pcs_purchased': 0,
                    'pcs_returned': 0,
                    'pcs_sold': 0,
                }
            entry = by_item[iid]
            entry['pcs_purchased'] += 1
            entry['gw_purchased'] += float(b.gw or 0)

            if b.pur_voucher_id and b.pur_voucher.billno_id in returned_pv_ids:
                entry['pcs_returned'] += 1

            if b.id in sales_map:
                s = sales_map[b.id]
                entry['pcs_sold'] += 1
                entry['gw_sold'] += s['gw']
                entry['sale_value'] += s['sale_value']
                entry['purchase_cost'] += float(b.total_amount or 0)

        items = []
        for entry in by_item.values():
            gw_p = entry['gw_purchased']
            gw_s = entry['gw_sold']
            sv = entry['sale_value']
            pc = entry['purchase_cost']
            entry['weight_loss_gm'] = round(gw_p - gw_s, 4)
            entry['weight_loss_pct'] = round((gw_p - gw_s) / gw_p * 100, 2) if gw_p else 0.0
            entry['gross_margin'] = round(sv - pc, 2)
            entry['margin_pct'] = round((sv - pc) / sv * 100, 2) if sv else 0.0
            entry['gw_purchased'] = round(gw_p, 4)
            entry['gw_sold'] = round(gw_s, 4)
            entry['purchase_cost'] = round(pc, 2)
            entry['sale_value'] = round(sv, 2)
            items.append(entry)

        return {'items': items}


# ─── Vendor Dashboard ─────────────────────────────────────────────────────────

class VendorDashboardService:
    """
    Aggregated vendor dashboard combining financial, inventory, and performance KPIs.
    Delegates sub-computations to the other vendor analytics services.
    """

    def __init__(self, retail_id, vendor_id, from_date=None, to_date=None,
                 item_type=None, purity_id=None, design_code=None):
        self.retail_id = retail_id
        self.vendor_id = vendor_id
        self.from_date = _parse_date(from_date)
        self.to_date = _parse_date(to_date)
        self.item_type = item_type or None
        self.purity_id = int(purity_id) if purity_id else None
        self.design_code = design_code or None

    def _vendor_name(self):
        try:
            from contacts.models import Ledger
            return Ledger.objects.get(pk=self.vendor_id).ac_name
        except Exception:
            return f"Vendor {self.vendor_id}"

    def _monthly_purchase_trend(self):
        import calendar
        today = date.today()
        months = []
        year, month = today.year, today.month
        for _ in range(12):
            month -= 1
            if month == 0:
                month = 12
                year -= 1
            months.append((year, month))
        months.reverse()

        trend = []
        for yr, mo in months:
            last_day = calendar.monthrange(yr, mo)[1]
            m_from = date(yr, mo, 1)
            m_to = date(yr, mo, last_day)
            val = PurchaseVoucherItems.objects.filter(
                billno__ldgr_id=self.vendor_id,
                billno__date1__range=[m_from, m_to],
            ).aggregate(Sum('item_value'))['item_value__sum'] or 0
            trend.append({'month': f'{yr:04d}-{mo:02d}', 'value': float(val)})
        return trend

    def get_data(self):
        # Financial
        pv_qs = PurchaseVoucherItems.objects.filter(
            billno__ldgr_id=self.vendor_id,
        )
        if self.from_date:
            pv_qs = pv_qs.filter(billno__date1__gte=self.from_date)
        if self.to_date:
            pv_qs = pv_qs.filter(billno__date1__lte=self.to_date)
        total_purchases = float(
            pv_qs.aggregate(Sum('item_value'))['item_value__sum'] or 0
        )

        # Inventory
        total_stock_value = float(
            BarcodeMain.objects.filter(
                pur_voucher__isnull=False,
                pur_voucher__billno__ldgr_id=self.vendor_id,
                stk_status=True,
                retail_id=self.retail_id,
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        )

        # Sell-through
        bm_base = BarcodeMain.objects.filter(
            pur_voucher__isnull=False,
            pur_voucher__billno__ldgr_id=self.vendor_id,
            retail_id=self.retail_id,
        )
        total_barcodes = bm_base.count()
        sold_barcodes = bm_base.filter(stk_status=False).count()
        sell_through_pct = (
            round(sold_barcodes / total_barcodes * 100, 2) if total_barcodes else 0.0
        )

        # Delegate to sub-services
        ageing_data = StockAgeingService(
            self.retail_id, self.vendor_id, self.from_date, self.to_date,
            item_type=self.item_type, purity_id=self.purity_id, design_code=self.design_code,
        ).get_data()
        turnover_data = InventoryTurnoverService(
            self.retail_id, self.vendor_id, self.from_date, self.to_date,
            item_type=self.item_type, purity_id=self.purity_id, design_code=self.design_code,
        ).get_data()
        design_data = DesignPerformanceService(
            self.retail_id, self.vendor_id, self.from_date, self.to_date,
            item_type=self.item_type, purity_id=self.purity_id, design_code=self.design_code,
        ).get_data()

        designs = design_data['designs']

        # Best design: lowest avg_days_to_sell where pcs_sold > 0
        sold_designs = [d for d in designs if d['pcs_sold'] > 0]
        best_design = (
            min(sold_designs, key=lambda d: d['avg_days_to_sell'])['design_code']
            if sold_designs else ''
        )

        # Overall avg_days_to_sell — weighted mean across all sold designs
        total_sold = sum(d['pcs_sold'] for d in designs)
        if total_sold:
            weighted_days = sum(
                d['avg_days_to_sell'] * d['pcs_sold'] for d in designs
            )
            avg_days_to_sell = round(weighted_days / total_sold, 2)
        else:
            avg_days_to_sell = 0.0

        # Top 5 designs by pcs_sold
        top_designs = sorted(designs, key=lambda d: -d['pcs_sold'])[:5]
        top_designs_out = [
            {
                'design_code': d['design_code'],
                'sold_pcs': d['pcs_sold'],
                'avg_days': d['avg_days_to_sell'],
            }
            for d in top_designs
        ]

        return {
            'vendor': {
                'id': self.vendor_id,
                'name': self._vendor_name(),
            },
            'financial': {
                'total_purchases': round(total_purchases, 2),
                'outstanding_payable': 0.0,
                'avg_payment_days': 0.0,
            },
            'inventory': {
                'total_stock_value': round(total_stock_value, 2),
                'ageing_score': ageing_data['summary'].get('ageing_score', 0.0),
                'turnover_ratio': turnover_data['current_period']['turnover_ratio'],
            },
            'performance': {
                'best_design': best_design,
                'sell_through_pct': sell_through_pct,
                'avg_days_to_sell': avg_days_to_sell,
            },
            'monthly_purchase_trend': self._monthly_purchase_trend(),
            'top_designs': top_designs_out,
        }


# ─── Vendor Comparison ────────────────────────────────────────────────────────

class VendorComparisonService:
    """
    Compare multiple vendors (or all vendors) across the same KPIs used in
    the Vendor Dashboard: purchases, stock value, sell-through, avg days to sell.

    vendor_ids: list[int] | None — None means all vendors with any purchases.
    """

    def __init__(self, retail_id, vendor_ids=None, from_date=None, to_date=None,
                 item_type=None, purity_id=None, design_code=None):
        self.retail_id   = int(retail_id)
        self.vendor_ids  = [int(v) for v in vendor_ids] if vendor_ids else None
        self.from_date   = _parse_date(from_date)
        self.to_date     = _parse_date(to_date)
        self.item_type   = item_type or None
        self.purity_id   = int(purity_id) if purity_id else None
        self.design_code = design_code or None

    # ── shared filter builders ────────────────────────────────────────────────

    def _pv_filters(self):
        """Filters for PurchaseVoucherItems."""
        f = {'billno__retail_id': self.retail_id}
        if self.vendor_ids:
            f['billno__ldgr_id__in'] = self.vendor_ids
        if self.from_date:
            f['billno__date1__gte'] = self.from_date
        if self.to_date:
            f['billno__date1__lte'] = self.to_date
        return f

    def _bm_filters(self, **extra):
        """Filters for BarcodeMain (vendor scope, no date filter on barcode side)."""
        f = {'pur_voucher__isnull': False, 'retail_id': self.retail_id}
        if self.vendor_ids:
            f['pur_voucher__billno__ldgr_id__in'] = self.vendor_ids
        if self.item_type:
            f['item__item_type'] = self.item_type
        if self.purity_id:
            f['purity_id'] = self.purity_id
        if self.design_code:
            f['design_code'] = self.design_code
        f.update(extra)
        return f

    # ── metrics ──────────────────────────────────────────────────────────────

    def _purchase_totals(self):
        """total_purchases per vendor, respecting date filter."""
        from django.db.models import Sum
        rows = (
            PurchaseVoucherItems.objects
            .filter(**self._pv_filters())
            .values('billno__ldgr_id')
            .annotate(total=Sum('item_value'))
        )
        return {r['billno__ldgr_id']: float(r['total'] or 0) for r in rows}

    def _stock_totals(self):
        """Current stock value per vendor (no date filter on barcodes)."""
        from django.db.models import Sum
        rows = (
            BarcodeMain.objects
            .filter(**self._bm_filters(stk_status=True))
            .values('pur_voucher__billno__ldgr_id')
            .annotate(val=Sum('total_amount'))
        )
        return {r['pur_voucher__billno__ldgr_id']: float(r['val'] or 0) for r in rows}

    def _sell_through(self):
        """total_pcs and sell_through_pct per vendor."""
        from django.db.models import Count, Q
        rows = (
            BarcodeMain.objects
            .filter(**self._bm_filters())
            .values('pur_voucher__billno__ldgr_id')
            .annotate(
                total_pcs=Count('id'),
                sold_pcs=Count('id', filter=Q(stk_status=False)),
            )
        )
        result = {}
        for r in rows:
            ldgr = r['pur_voucher__billno__ldgr_id']
            total = r['total_pcs']
            sold  = r['sold_pcs']
            result[ldgr] = {
                'total_pcs':       total,
                'sold_pcs':        sold,
                'sell_through_pct': round(sold / total * 100, 1) if total else 0.0,
            }
        return result

    def _avg_days_to_sell(self, sold_barcode_ids):
        """
        avg_days_to_sell per vendor.
        sold_barcode_ids: dict[bm_id -> {ldgr_id, created_date}]
        """
        if not sold_barcode_ids:
            return {}
        vendor_days = {}
        for svi in (
            SalesVouItem.objects
            .filter(barcode_id__in=list(sold_barcode_ids.keys()))
            .select_related('billno')
            .values('barcode_id', 'billno__date1')
        ):
            bc = sold_barcode_ids.get(svi['barcode_id'])
            sale_date = svi['billno__date1']
            if bc and sale_date and bc['created_date']:
                days = max(0, (sale_date - bc['created_date']).days)
                vendor_days.setdefault(bc['ldgr_id'], []).append(days)
        return {
            ldgr: round(sum(dl) / len(dl), 1)
            for ldgr, dl in vendor_days.items()
        }

    # ── main ─────────────────────────────────────────────────────────────────

    def get_data(self):
        from contacts.models import Ledger

        purchase_map  = self._purchase_totals()
        stock_map     = self._stock_totals()
        sell_map      = self._sell_through()

        # Collect sold barcode metadata for avg-days calculation
        sold_bm = (
            BarcodeMain.objects
            .filter(**self._bm_filters(stk_status=False))
            .values('id', 'pur_voucher__billno__ldgr_id', 'created_date')
        )
        sold_barcode_ids = {
            r['id']: {
                'ldgr_id':      r['pur_voucher__billno__ldgr_id'],
                'created_date': r['created_date'],
            }
            for r in sold_bm
        }
        avg_days_map = self._avg_days_to_sell(sold_barcode_ids)

        # Union of all vendor IDs that appear in any metric
        all_ldgr_ids = (
            set(purchase_map) | set(stock_map) | set(sell_map)
        )
        if self.vendor_ids:
            all_ldgr_ids &= set(self.vendor_ids)

        # Fetch names in one query
        name_map = {
            l.id: l.ac_name
            for l in Ledger.objects.filter(id__in=all_ldgr_ids)
        }

        vendors = []
        for ldgr_id in all_ldgr_ids:
            st = sell_map.get(ldgr_id, {})
            vendors.append({
                'vendor_id':        ldgr_id,
                'vendor_name':      name_map.get(ldgr_id, f'Vendor {ldgr_id}'),
                'total_purchases':  purchase_map.get(ldgr_id, 0.0),
                'total_stock_value': stock_map.get(ldgr_id, 0.0),
                'total_pcs':        st.get('total_pcs', 0),
                'sold_pcs':         st.get('sold_pcs', 0),
                'sell_through_pct': st.get('sell_through_pct', 0.0),
                'avg_days_to_sell': avg_days_map.get(ldgr_id, 0.0),
            })

        vendors.sort(key=lambda v: -v['total_purchases'])
        return {'vendors': vendors}
