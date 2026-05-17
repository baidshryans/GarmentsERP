# Sales Approval Return Document — Design Spec
**Date:** 2026-05-17  
**Status:** Approved

---

## Overview

A standalone `SalesApprovalReturn` (SAR) document type that records the physical return of items that were sent out on a Sales Approval. The return can optionally reference the original approval voucher (for items in the system) or be created independently (for carry-forward / manual cases). No accounting journal entries are created — this is a stock/inventory document only.

---

## Business Rules

- Bill number is auto-generated with prefix `SAR` (e.g. `SAR-001`), released on delete.
- The reference to the original `SalesApproval` is optional.
- Items can be entered three ways:
  1. **Linked from approval** — when a reference approval is selected, its items are pre-filled as checkboxes; user ticks which ones are being returned.
  2. **Barcode scan** — scan a barcode to append an item row (for standalone returns where barcodes exist in the system).
  3. **Manual entry** — add a blank row and fill in item, pcs, gw, purity, amount, sub-items (for carry-forward items with no barcode in the system).
- On save (atomic):
  - Items with a barcode → `BarcodeMain.stk_status = True`
  - Items with `approval_item` FK → `SalesApprovalItem.ret_status = True`
- Each `SalesApprovalReturnItem` has nested `SalesApprovalReturnItemDetails` (sub-item breakdown: stone/metal details), mirroring the approval item structure.
- F4 saves/updates the form.

---

## Data Model

### `SalesApprovalReturn` (header)

| Field | Type | Notes |
|-------|------|-------|
| `billno` | CharField(30) | Auto-generated, prefix `SAR` |
| `date1` | DateField | Date of return |
| `ref_approval` | FK → SalesApproval | null=True, blank=True — optional link |
| `narration` | CharField(100) | Optional notes, blank=True |
| `retail` | FK → RetailMaster | null=True, blank=True |
| `fiscal_year` | FK → FiscalYearMaster | null=True, blank=True |

DB table: `sales_vou_appr_return`

### `SalesApprovalReturnItem` (main item row)

| Field | Type | Notes |
|-------|------|-------|
| `billno` | FK → SalesApprovalReturn | CASCADE |
| `barcode` | FK → BarcodeMain | null=True, blank=True — present for scanned/linked items |
| `approval_item` | FK → SalesApprovalItem | null=True, blank=True — set when pre-filled from approval |
| `item` | FK → Item | PROTECT |
| `pcs` | IntegerField | |
| `gw` | DecimalField(10,3) | |
| `purity` | CharField(10) | Text label e.g. "18K" |
| `amount` | DecimalField(12,2) | |
| `retail` | FK → RetailMaster | null=True, blank=True |

DB table: `sales_vou_appr_return_main`

### `SalesApprovalReturnItemDetails` (sub-item breakdown)

| Field | Type | Notes |
|-------|------|-------|
| `billno` | FK → SalesApprovalReturn | null=True, CASCADE |
| `main_item` | FK → SalesApprovalReturnItem | CASCADE, related_name=`main_item_set` |
| `item` | FK → Item | PROTECT |
| `pcs` | IntegerField | |
| `ct` | DecimalField(10,3) | null=True, blank=True, default=0 |
| `gw` | DecimalField(10,3) | null=True, blank=True, default=0 |
| `metal_purity` | CharField(10) | null=True, blank=True |
| `rate` | DecimalField(10,3) | |
| `amount` | DecimalField(10,2) | |
| `packet` | FK → Packet | SET_NULL, null=True |
| `retail` | FK → RetailMaster | null=True, blank=True |

DB table: `sales_vou_appr_return_detail`

---

## Backend

### Files Changed

| Action | File |
|--------|------|
| Modify | `backend/sales/models.py` — add 3 new models |
| Create | `backend/sales/migrations/000X_sales_approval_return.py` |
| Modify | `backend/sales/serializers.py` — add 3 new serializers |
| Modify | `backend/sales/views/invoice.py` — add `SalesApprovalReturnViewset` |
| Modify | `backend/sales/urls.py` — register viewset + next_sar_no endpoint |
| Modify | `backend/accounting/utils.py` — register `SAR` prefix in bill number map |

### Bill Number

Add `SAR` to `get_next_bill_number`'s model map alongside `SA`:
```python
'SAR': (SalesApprovalReturn, 'billno'),
```

### Serializers

**`SalesApprovalReturnItemDetailsSerializer`**
- Fields: `id` (read_only=False, required=False), `item` (slug: short_code), `pcs`, `ct`, `gw`, `metal_purity`, `rate`, `amount`, `packet` (slug: pckt_no, allow_null=True)
- `ct` and `gw`: `required=False, allow_null=True, default=0`
- `validators = []` on Meta

**`SalesApprovalReturnItemSerializer`**
- Fields: `id`, `barcode` (slug: barcode, allow_null=True, required=False), `approval_item` (PrimaryKeyRelatedField, allow_null=True, required=False), `item` (slug: short_code), `pcs`, `gw`, `purity` (CharField, allow_blank=True, allow_null=True), `amount`, `main_item_set` (nested, many=True)
- `validators = []` on Meta

**`SalesApprovalReturnSerializer`**
- Fields: `id`, `billno`, `date1`, `ref_approval` (PrimaryKeyRelatedField, allow_null=True, required=False), `narration`, `retail`, `fiscal_year`, `items` (nested SalesApprovalReturnItemSerializer, many=True)
- `create()`: atomic — generate SAR bill number, create header, create items + details, set `stk_status=True` on barcodes, set `ret_status=True` on linked approval items
- `update()`: atomic — update header fields, recreate items via `create_or_update_nested`

### Viewset

`SalesApprovalReturnViewset(RetailBaseViewset)`:
- `queryset`: select_related `ref_approval`, `retail`; prefetch_related `items__main_item_set`
- `serializer_class`: `SalesApprovalReturnSerializer`
- `search_fields`: `['billno', 'ref_approval__billno']`
- `ordering`: `['-date1', '-id']`
- `perform_destroy`: releases SAR bill number via `release_last_bill_number`

### URL Endpoints

```
router.register(r'sale-approval-return', views.SalesApprovalReturnViewset)

GET  /api/next_sar_no  →  get_next_sar_no view
```

---

## Frontend

### Files Changed

| Action | File |
|--------|------|
| Create | `frontend/src/components/Sales/SalesApprovalReturnList.jsx` |
| Create | `frontend/src/components/Sales/SalesApprovalReturnAdd.jsx` |
| Modify | `frontend/src/services/api/sales.js` — add 6 API functions |
| Modify | `frontend/src/App.jsx` — add lazy imports + 3 routes |
| Modify | `frontend/src/config/navData.js` — add "Approval Return" nav entry |

### API Functions (sales.js)

```js
fetchNextSARNo()                           // GET /api/next_sar_no
fetchSalesApprovalReturns({search, page, ordering})  // GET /api/sale-approval-return/
fetchSalesApprovalReturnById(id)           // GET /api/sale-approval-return/:id/
createSalesApprovalReturn(data)            // POST /api/sale-approval-return/
updateSalesApprovalReturn(data, id)        // PUT /api/sale-approval-return/:id/
deleteSalesApprovalReturn(id, toast)       // DELETE /api/sale-approval-return/:id/
```

### Routes (App.jsx)

```js
/sales/salesapprovalreturn/list/   →  SalesApprovalReturnList
/sales/salesapprovalreturn/add/    →  SalesApprovalReturnAdd
/sales/salesapprovalreturn/:id     →  SalesApprovalReturnAdd (edit mode)
```

### Navbar (navData.js)

Add between "Sales Approval" and "E-Way Bills":
```js
{ title: "Approval Return", url: "/sales/salesapprovalreturn/list/", icon: PackageXIcon },
```

### List Page (`SalesApprovalReturnList.jsx`)

Follows `SalesApprovalList` pattern:
- Columns: Date, Bill No, Ref Approval, Items (count), Action (Edit + Delete)
- Search by bill no / ref approval bill no
- Sort by date / bill no
- "Add New" button → `/sales/salesapprovalreturn/add/`

### Add/Edit Form (`SalesApprovalReturnAdd.jsx`)

**Header section:**
- Bill No (auto, read-only display)
- Date (date picker, defaults today)
- Reference Approval (optional text search → fetches approval → pre-fills items)
- Narration (optional)

**Items section (three entry modes):**

1. **From linked approval** — when ref approval is selected, show approval items as checkboxable rows (barcode, item name, gw, purity, amount). Ticking a row appends it to the items table with its `main_item_set` carried across. Un-ticking removes it.

2. **Barcode scan** — barcode input field (blur triggers `fetchBarcodeDetail`). Appends a new item row with pre-filled sub-items. Clears field after scan.

3. **Manual add** — "+ Add Row" button appends a blank item row. Staff fills item (slug search), pcs, gw, purity, amount. Sub-item rows can be added inline.

**Items table columns:** Barcode | Item | Pcs | GW | Purity | Amount | Sub-items toggle | Remove

**Sub-item rows (collapsible per main item):** Item | Pcs | Ct | GW | Metal Purity | Rate | Amount | Packet

**Footer:** Narration | Save (F4) | Cancel

---

## Out of Scope

- Accounting journal entries (no ledger impact)
- GST calculation on the return document
- Printing a return receipt
- Editing `ret_status` back to False (one-way flag)
