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
