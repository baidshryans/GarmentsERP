"""Fine-gold (24K) rate derivation for the gold-weight balance sheet.

Computes a single ₹/g-of-pure-gold scalar by aggregating the retail's gold
flows from FY start through end_date and folding purity directly into the
rate:

    fine_gold_rate = Σ(value_i) / Σ(gw_i × gw_per_i / 100)

This collapses weighted-average rate × (1 / weighted-average purity) into a
single division, matching what the user asked for without needing the two
intermediates.
"""

from datetime import date, datetime
from decimal import Decimal

from inventory.models import (
    InterRetailTransferItem,
    InterRetailTransferVoucher,
    OpeningInventory,
)
from purchase.models import PurchaseVoucherItems
from mastersconfig.models import FiscalYearMaster


def _to_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.strptime(str(value), "%Y-%m-%d").date()


class FineGoldRateService:
    """Compute fine-gold rate (₹/g of 24K) for a retail scope and end_date."""

    def __init__(self, retail_ids, end_date):
        # retail_ids: None (all retails, admin combined) | list[int]
        # end_date: date or 'YYYY-MM-DD' string
        self.retail_ids = retail_ids
        self.end_date = _to_date(end_date)
        self.fy_start = self._resolve_fy_start()

    def _resolve_fy_start(self):
        """Find the FY that contains end_date and return its fy_start."""
        qs = FiscalYearMaster.objects.filter(
            fy_start__lte=self.end_date, fy_end__gte=self.end_date
        )
        if self.retail_ids:
            qs = qs.filter(retail_id__in=self.retail_ids)
        # Earliest fy_start among matching retails (combined view).
        fy = qs.order_by("fy_start").first()
        if fy:
            return fy.fy_start
        # Fallback: derive Indian FY start from end_date (April 1).
        y = self.end_date.year
        return date(y if self.end_date.month >= 4 else y - 1, 4, 1)

    def _opening_stock_contribution(self, collect_rows=False):
        """Opening physical inventory: gw × Item.op_wtd_avg_rate, fine = gw × gw_per/100."""
        qs = OpeningInventory.objects.select_related("item", "purity").filter(
            gw__gt=0, purity__isnull=False
        )
        if self.retail_ids:
            qs = qs.filter(retail_id__in=self.retail_ids)

        total_value = Decimal("0")
        total_fine = Decimal("0")
        rows = []
        for row in qs:
            gw_per = Decimal(str(row.purity.gw_per or 0))
            if gw_per <= 0:
                continue
            gw = Decimal(str(row.gw or 0))
            rate = Decimal(str(getattr(row.item, "op_wtd_avg_rate", 0) or 0))
            value = gw * rate
            fine = gw * gw_per / Decimal("100")
            total_value += value
            total_fine += fine
            if collect_rows:
                rows.append({
                    "label": getattr(row.item, "item_name", "—"),
                    "purity": row.purity.purity,
                    "gw_per": gw_per,
                    "gw": gw,
                    "rate": rate,
                    "value": value,
                    "fine_grams": fine,
                })
        if collect_rows:
            return total_value, total_fine, rows
        return total_value, total_fine

    def _purchases_contribution(self, collect_rows=False):
        """PurchaseVoucherItems within [fy_start, end_date]: value=item_value, fine=gw×gw_per/100."""
        qs = PurchaseVoucherItems.objects.select_related("purity", "billno", "item").filter(
            billno__date1__gte=self.fy_start,
            billno__date1__lte=self.end_date,
            gw__gt=0,
            purity__isnull=False,
            item_value__isnull=False,
        )
        if self.retail_ids:
            qs = qs.filter(retail_id__in=self.retail_ids)

        total_value = Decimal("0")
        total_fine = Decimal("0")
        rows = []
        if collect_rows:
            for r in qs.values(
                "gw", "item_value", "purity__gw_per", "purity__purity",
                "item__item_name", "billno__billno", "billno__date1",
            ):
                gw_per = Decimal(str(r["purity__gw_per"] or 0))
                if gw_per <= 0:
                    continue
                gw = Decimal(str(r["gw"] or 0))
                value = Decimal(str(r["item_value"] or 0))
                fine = gw * gw_per / Decimal("100")
                total_value += value
                total_fine += fine
                rows.append({
                    "label": r["item__item_name"] or "—",
                    "ref": str(r["billno__billno"] or "") or None,
                    "date": r["billno__date1"].isoformat() if r["billno__date1"] else None,
                    "purity": r["purity__purity"],
                    "gw_per": gw_per,
                    "gw": gw,
                    "rate": (value / gw) if gw else Decimal("0"),
                    "value": value,
                    "fine_grams": fine,
                })
            return total_value, total_fine, rows

        for row in qs.values("gw", "item_value", "purity__gw_per"):
            gw_per = Decimal(str(row["purity__gw_per"] or 0))
            if gw_per <= 0:
                continue
            gw = Decimal(str(row["gw"] or 0))
            value = Decimal(str(row["item_value"] or 0))
            total_value += value
            total_fine += gw * gw_per / Decimal("100")
        return total_value, total_fine

    def _transfers_in_contribution(self, collect_rows=False):
        """Inter-retail transfers received within FY window: value=transfer_value, fine=qty_gw×gw_per/100."""
        empty = (Decimal("0"), Decimal("0"), []) if collect_rows else (Decimal("0"), Decimal("0"))
        if not self.retail_ids:
            # Combined view — transfers within the org net to zero. Skip.
            return empty

        qs = InterRetailTransferItem.objects.select_related("purity", "voucher", "item").filter(
            voucher__to_retail_id__in=self.retail_ids,
            voucher__transfer_date__gte=self.fy_start,
            voucher__transfer_date__lte=self.end_date,
            voucher__status=InterRetailTransferVoucher.STATUS_RECEIVED,
            qty_gw__gt=0,
            purity__isnull=False,
        )

        total_value = Decimal("0")
        total_fine = Decimal("0")
        rows = []
        if collect_rows:
            for r in qs.values(
                "qty_gw", "transfer_value", "purity__gw_per", "purity__purity",
                "item__item_name", "voucher__voucher_no", "voucher__transfer_date",
            ):
                gw_per = Decimal(str(r["purity__gw_per"] or 0))
                if gw_per <= 0:
                    continue
                gw = Decimal(str(r["qty_gw"] or 0))
                value = Decimal(str(r["transfer_value"] or 0))
                fine = gw * gw_per / Decimal("100")
                total_value += value
                total_fine += fine
                rows.append({
                    "label": r["item__item_name"] or "—",
                    "ref": r["voucher__voucher_no"],
                    "date": r["voucher__transfer_date"].isoformat() if r["voucher__transfer_date"] else None,
                    "purity": r["purity__purity"],
                    "gw_per": gw_per,
                    "gw": gw,
                    "rate": (value / gw) if gw else Decimal("0"),
                    "value": value,
                    "fine_grams": fine,
                })
            return total_value, total_fine, rows

        for row in qs.values("qty_gw", "transfer_value", "purity__gw_per"):
            gw_per = Decimal(str(row["purity__gw_per"] or 0))
            if gw_per <= 0:
                continue
            gw = Decimal(str(row["qty_gw"] or 0))
            value = Decimal(str(row["transfer_value"] or 0))
            total_value += value
            total_fine += gw * gw_per / Decimal("100")
        return total_value, total_fine

    def compute(self):
        """Return Decimal ₹/g of fine gold, or None if no gold flow."""
        sources = [
            self._opening_stock_contribution(),
            self._purchases_contribution(),
            self._transfers_in_contribution(),
        ]
        total_value = sum((v for v, _ in sources), Decimal("0"))
        total_fine = sum((f for _, f in sources), Decimal("0"))
        if total_fine <= 0 or total_value <= 0:
            return None
        return total_value / total_fine

    def breakdown(self):
        """Return per-source rows + totals for audit/transparency in the UI.

        Shape:
          {
            "fy_start": "2026-04-01", "end_date": "2026-04-27",
            "fine_gold_rate": Decimal | None,
            "total_value": Decimal, "total_fine_grams": Decimal,
            "sources": [
              {"key": "opening_stock", "label": "Opening Stock",
               "total_value": ..., "total_fine_grams": ..., "rows": [...]},
              {"key": "purchases", ...},
              {"key": "transfers_in", ...},
            ]
          }
        """
        op_v, op_f, op_rows = self._opening_stock_contribution(collect_rows=True)
        pu_v, pu_f, pu_rows = self._purchases_contribution(collect_rows=True)
        tr_v, tr_f, tr_rows = self._transfers_in_contribution(collect_rows=True)
        total_value = op_v + pu_v + tr_v
        total_fine = op_f + pu_f + tr_f
        rate = (total_value / total_fine) if total_fine > 0 else None
        return {
            "fy_start": self.fy_start.isoformat(),
            "end_date": self.end_date.isoformat(),
            "fine_gold_rate": rate,
            "total_value": total_value,
            "total_fine_grams": total_fine,
            "sources": [
                {"key": "opening_stock", "label": "Opening Stock",
                 "total_value": op_v, "total_fine_grams": op_f, "rows": op_rows},
                {"key": "purchases", "label": "Purchases (FY)",
                 "total_value": pu_v, "total_fine_grams": pu_f, "rows": pu_rows},
                {"key": "transfers_in", "label": "Transfers In (FY)",
                 "total_value": tr_v, "total_fine_grams": tr_f, "rows": tr_rows},
            ],
        }
