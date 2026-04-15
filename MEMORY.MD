# Jewel India ERP — Developer Memory File

> Maintained by Claude. Updated after each significant session.
> Last updated: 2026-04-14

---

## Project Overview

- **Name:** Jewel India ERP
- **Root path:** `D:/Jewel India ERP/`
- **Backend:** Django + Django REST Framework (`backend/`)
- **Frontend:** React + Tailwind CSS + shadcn/ui (`frontend/src/`)
- **DB:** PostgreSQL (accessed via Django ORM)
- **Auth:** Token-based (`X-RETAIL-ID` header identifies the retail branch per request)

---

## Project Structure

```
D:/Jewel India ERP/
├── backend/
│   ├── accounting/       — VoucherMain, JournalEntry, RCPT, PMNT, JRNL, CN, DN
│   ├── inventory/        — Barcode, StockJournal, StockTransfer, ClosingStockCal
│   ├── purchase/         — PurchaseVoucher, PurchaseReturn, signals
│   ├── sales/            — SalesVou, SaleReturn, SalesApproval
│   ├── mastersconfig/    — Item, RetailMaster, BillNumberSequence, FiscalYearMaster
│   ├── contacts/         — Ledger
│   ├── goldrates/        — PurityMaster
│   └── userauth/         — RetailBaseViewset (base for all retail-scoped viewsets)
└── frontend/src/
    ├── components/
    │   ├── manufacturing/purchases/  — PurchaseVoucherList.jsx
    │   └── Sales/                   — SalesVoucherList.jsx
    ├── table.jsx                    — Shared DataTable component
    └── components/ui/table.jsx      — Base Table primitives
```

---

## Key Domain Concepts

### Item Types
| Code | Meaning | Primary Qty for WAR |
|------|---------|-------------------|
| `M`  | Metal | `gw` (gross weight) — excluded from closing stock calc |
| `R`  | Raw material | `gw` |
| `S`  | Stone | `ct` (carat) |
| `O`  | Other | `gw` — excluded from closing stock calc |

### Voucher Prefixes (BillNumberSequence)
| Prefix | Model | Bill field |
|--------|-------|-----------|
| `SV` | `SalesVou` | `billno` |
| `SR` | `SaleReturn` | `billno` |
| `SA` | `SalesApproval` | `billno` |
| `PV` | `PurchaseVoucher` | `billno` |
| `PR` | `PurchaseReturn` | `billno` |
| `PO` | `PurchaseOrder` | `po_no` |
| `SJ` | `StockJournal` | `billno` |
| `RST` | `StockTransfer` | `billno` |
| `CN` / `DN` | `CreditDebitNote` | `note_no` |
| `JRNL` / `PMNT` / `RCPT` / `CONTRA` / etc. | `VoucherMain` | `voucher_no` |
| `GC` / `CG` | `CashGoldConversion` | `billno` |

### Purchase Voucher Structure
- `PurchaseVoucher` — header (date, party, totals)
- `PurchaseVoucherItems` — main items per voucher line (`is_finished`, `is_return` flags)
- `PurchaseVoucherDetails` — sub-components of a main item (stones, raw metal inside a piece)

**Critical rule:** Stone (S) and sub-component R items live **only** in `PurchaseVoucherDetails`, never as main items in `PurchaseVoucherItems`.

---

## Bill Number Sequencing (`accounting/utils.py`)

### How it works
- `BillNumberSequence` table: one row per `(retail, prefix, fiscal_year)`
- `get_next_bill_number(retail, prefix, fiscal_year)` — increments `last_number` atomically and returns formatted string
- `peek_next_bill_number(...)` — read-only preview, no DB write
- `_bootstrap_sequence_number(retail, prefix, fy)` — scans actual max from the relevant model on first use
- Bill format: `{retail_prefix}/{retail_code}/{fy_code}/{last_number:05d}`

### On delete — sequence rollback
`release_last_bill_number(retail, prefix, bill_no, fiscal_year)` added to `accounting/utils.py`.
- Extracts trailing number from bill_no with regex
- Uses `SELECT FOR UPDATE` on the sequence row
- Decrements `last_number` **only if** the deleted number == `last_number` (i.e. it was the last bill)
- Mid-sequence deletes have no effect

Hooked into `perform_destroy` / `destroy` on:
- `SalesVoucherViewset` (SV) — `sales/views.py`
- `SalesReturnViewset` (SR) — `sales/views.py`
- `SalesApprovalViewset` (SA) — `sales/views.py`
- `PurchaseVoucherViewset` (PV) — `purchase/views.py`
- `PurchaseReturnViewset` (PR) — `purchase/views.py`
- `JournalEntryViewSet` (prefix = `voucher_type`) — `accounting/views.py`
- `CreditDebitNoteViewSet` (prefix = `note_type`) — `accounting/views.py`
- `StockJournalViewSet` (SJ) — `inventory/views.py`
- `StockTransferViewset` (RST) — `inventory/views.py`

---

## Closing Stock Calculation (`inventory/views.py` — `ClosingStockCal`)

### Formula
```
total_in_qty   = opening_qty + purchase_qty - purchase_return_qty
total_in_value = opening_value + purchase_value - purchase_return_value
WAR            = total_in_value / total_in_qty   (if total_in_qty > 0)
closing_qty    = total_in_qty - sales_qty + sale_return_qty - refinery_issue_qty + refinery_receive_qty
closing_value  = closing_qty × WAR
```

### Items included
`Item.objects.exclude(item_type__in=['M', 'O'])` — processes R and S types only.

### `get_purchases()` — fixed bugs
1. **Date filter** was `date1__gte` on `PurchaseVoucherItems.date1` (nullable, often NULL).
   Fixed to: `billno__date1__gte` (date lives on the voucher header).
2. **S items missing** — stones are only sub-items in `PurchaseVoucherDetails`, never main items.
   The old `main_item__in=query` chained through an empty queryset → zero purchases for all stones.
   Fixed: query `PurchaseVoucherDetails` directly by `sub_item=item`.
3. **Missing `is_finished=False`** — finished goods were counted but signals skip them.

### `get_purchases()` — current logic
- Main items: `PurchaseVoucherItems.filter(item=item, is_return=False, is_finished=False)` with `billno__date1` date filter → captures `gw` and `item_value`
- Detail sub-items: `PurchaseVoucherDetails.filter(sub_item=item, main_item__is_finished=False, main_item__is_return=False)` → captures `sub_ct`, `sub_gw`, `value`
- **S items:** gw + amt come entirely from details
- **R items:** gw + amt = main item totals + detail sub-item totals (can appear in both places)

### `get_purchase_returns()` — fixed bug
Same `main_item__in=query` problem for S items. Fixed: query `PurchaseReturnDetails` directly by `sub_item=item`.

---

## Purchase Signals (`purchase/signals.py`)

| Signal | Trigger | Effect |
|--------|---------|--------|
| `increase_raw_material_on_purchase` | `post_save` on `PurchaseVoucherItems` (created, not finished) | Adds `gw` to `RawMaterialInventory`, logs `PURCHASE` txn |
| `adjust_raw_material_on_detail_save` | `post_save` on `PurchaseVoucherDetails` (main not finished) | Adds/adjusts `ct`+`gw` in inventory; handles item/purity change (reverse old, add new) |
| `reverse_raw_material_on_purchase_delete` | `pre_delete` on `PurchaseVoucherItems` | Reverses `gw` from inventory |
| `reverse_raw_material_on_purchase_detail_delete` | `pre_delete` on `PurchaseVoucherDetails` | Reverses `ct`+`gw` from inventory |
| `decrease_raw_material_on_purchase_return` | `post_save` on `PurchaseReturnItems` (created) | Decrements `gw` from inventory |

**Important:** `is_finished=True` main items are skipped by all signals. Details whose `main_item.is_finished=True` are also skipped.

---

## Accounting — RCPT-SALE Voucher (`sales/serializers.py`)

RCPT-SALE is auto-created alongside a sale voucher to record cash/bank receipts.

### Fixed bug
Previously created even when cash = 0, producing blank/zero-value vouchers.

### Current logic
```python
_rcpt_customer_credit = cash + sum(bank amounts) + old_gold_adjusted
if _rcpt_customer_credit > 0:
    _cash_lines = [cash debit line] if cash > 0 else []
    # build and save RCPT-SALE voucher
    rcpt_ref = ser.save()
else:
    rcpt_ref = None
sales_vou_instance.ac_rec_voucher = rcpt_ref
```
- Entire RCPT-SALE skipped when total receipt = 0
- Cash line item skipped when cash = 0 (even if other payment modes exist)

---

## Frontend Design System

### DataTable (shared — `src/table.jsx`)
All list tables use this. Key classes:
- Header row: `bg-muted/50 hover:bg-muted/50`
- Header cell: `text-xs font-semibold uppercase tracking-wider text-muted-foreground h-10 px-4`
- Data row hover: `hover:bg-accent/40`
- Alternating rows: `bg-muted/20` on odd rows
- Wrapper: `rounded-lg border border-border overflow-hidden`
- Cell padding: `px-4 py-2.5 text-sm`

### Panel headers (detail/sub-panels)
- No gradients — use `bg-background border-b`
- Title: `text-xs font-semibold uppercase tracking-wider text-muted-foreground`
- Close button: `hover:bg-muted` with `text-muted-foreground` icon

### Purchase Details Panel (`PurchaseVoucherList.jsx`)
Displayed as a resizable bottom panel when a row is clicked.

Columns shown: **Sl, Date, Packet, Item, Pcs, Ct, Gw, Purity, Fine Wt, Rate, Making, Value, Action**
Columns intentionally hidden: Size, Loss, Tunch, Remarks

- Main item rows: `hover:bg-accent/40`, alternating `bg-muted/20`
- Sub-detail rows: `bg-muted/10 hover:bg-muted/30 border-l-2 border-l-border` (visual nesting)
- "Create Barcode" button disabled when `item.pending_gw <= 0`

---

## Retail Scoping

Every model has a `retail` FK to `RetailMaster`. The middleware sets `request.retail` from the `X-RETAIL-ID` header. `RetailBaseViewset.get_queryset()` automatically filters by `retail=request.retail`.

---

## Sale Voucher — Sub-item Rates (`sales/serializers.py`)

### `SalesVouItemDetailsSerializer`
- `rate` field: `DecimalField(max_digits=10, decimal_places=3)` on `SalesVouItemDetails` — stores the sale rate entered by the user.
- `uom` and `item_type` added as **read-only** fields (`source='item.uom'` / `source='item.item_type'`) so the frontend recalc formula (`uom === 'Ct' ? ct * rate : gw * rate`) works correctly in **edit mode** (these fields are absent from the edit-mode GET response otherwise).

### `SalesVouItemSerializer.to_representation` — critical fix
**Bug (fixed 2026-04-14):** The override used `instance.purity` to convert purity PK → slug string. During `SalesVouSerializer.update`, `create_or_update_nested` calls `SalesVouItemSerializer(detail_data, many=True).data` where `detail_data` is a list of plain Python dicts from `validated_data`. Accessing `.purity` on a dict raises `AttributeError`, aborting the entire atomic transaction. Result: user-edited rates were never persisted — they always reverted to the original (purchase) rates on every reload.

**Fix:** Use `rep.get('purity')` (already serialized by `super().to_representation`) instead of `instance.purity`:
```python
try:
    purity_pk = int(rep.get('purity') or 0)
except (ValueError, TypeError):
    purity_pk = 0
if purity_pk > 0:
    try:
        rep['purity'] = PurityMaster.objects.get(pk=purity_pk).purity
    except PurityMaster.DoesNotExist:
        rep['purity'] = str(purity_pk)
```

### `SalesVouItemSerializer.create` — wrong signature fix
**Bug (fixed 2026-04-14):** DRF calls `create(validated_data)` with one arg, but the method was declared as `create(self, instance, validated_data)` — making `validated_data` the `instance` param and raising `TypeError` for any new barcode item added during an edit.

**Fix:** Corrected to `create(self, validated_data)` with `SalesVouItem.objects.create(**validated_data)`.

---

## Common Gotchas

1. **`PurchaseVoucherItems.date1` is nullable** — the actual date is on the voucher header (`billno.date1`). Always traverse the FK for date filtering.
2. **Stone items are never main items** — they only appear in `PurchaseVoucherDetails.sub_item`. Any query on `PurchaseVoucherItems` for a Stone item will return empty.
3. **`is_finished=True` items** — signals skip them, so closing stock queries must also exclude them.
4. **BillNumberSequence bootstraps on first use** — deleting the sequence row is safe; it will re-read the max from existing bills. Use this to reset numbering after clearing test data.
5. **RCPT-SALE prefix** — stored in `BillNumberSequence` as the `voucher_type` string (e.g. `'RCPT-SALE'`). When releasing on delete, `JournalEntryViewSet` uses `instance.voucher_type` directly as the prefix.
6. **`SalesVouItemSerializer.to_representation` must use `rep` not `instance`** — `instance` can be a plain dict (during update re-serialization). Never access instance attributes on fields that may be dict-sourced.
