# Sales Approval Return — Design Spec
**Date:** 2026-05-17  
**Status:** Approved

---

## Overview

Allow staff to record partial or full returns against an existing Sales Approval voucher. Individual items (barcodes) are marked as returned; their stock is restored so they can be re-issued or sold.

---

## Business Rules

- Returns are **per-item** (partial returns allowed — customer can return 2 of 5 pieces).
- A returned item **cannot be un-returned** (ret_status is a one-way flag).
- On return, the item's barcode is restored to stock (`stk_status=True`).
- Re-submitting an already-returned item ID is idempotent (no error, no duplicate effect).
- An approval where all items are already returned shows the Return button as disabled on the list.

---

## Architecture

### Backend

**New endpoint:** `POST /api/sale-approval/:id/return-items/`

- Custom `@action` on the existing `SalesApprovalViewset`.
- Request body: `{ "returned_item_ids": [1, 2, 3] }`
- Validates that each ID belongs to this approval.
- Sets `ret_status=True` on matching `SalesApprovalItem` records (skips already-returned ones).
- Sets `stk_status=True` on the associated `BarcodeMain` records.
- Returns the updated `SalesApproval` serialized response.
- Wrapped in `transaction.atomic()`.

No new model or migration needed — `SalesApprovalItem.ret_status` already exists.

### Frontend — Three pieces

1. **`SalesApprovalReturnForm.jsx`** — shared stateless component  
   - Props: `approval` (approval data), `onSave(newlyReturnedIds)`, `saving`  
   - Renders: approval header (bill no, date, customer) + item table with checkboxes  
   - Already-returned items: pre-checked, disabled, greyed  
   - "Save Returns" button disabled until at least one new item is selected

2. **`SalesApprovalList.jsx`** — gains a `RotateCcw` icon button per row  
   - Clicking sets `selectedApprovalId` state and opens a Sheet  
   - Button is disabled/greyed if all items on that row are already returned  
   - On sheet save-success: refetch the list, close sheet, show toast

3. **`SalesApprovalReturnPage.jsx`** — standalone page at `/sales/salesapproval/:id/return/`  
   - Fetches the approval by `id` param  
   - Renders `SalesApprovalReturnForm` full-page with a back-arrow header  
   - On save-success: navigate back to list, show toast

---

## Data Flow

```
User clicks Return (list row)
  → Sheet opens; fetch GET /api/sale-approval/:id/ → populate SalesApprovalReturnForm
  → User ticks newly-returned items → clicks Save
  → POST /api/sale-approval/:id/return-items/ { returned_item_ids: [...] }
  → Backend: mark ret_status=True, stk_status=True (atomic)
  → 200 OK → toast "Return recorded" → close sheet → refresh list
```

Same flow for the full page, except on success navigate to `/sales/salesapproval/list/`.

---

## UI Detail

### List row — Return button
- Icon: `RotateCcw` (lucide-react), alongside existing `SquarePen` and `Trash2`
- Disabled state: all items already have `ret_status=True`
- No tooltip needed — icon is self-explanatory in context

### Sheet / Page — Item table columns
| Column   | Notes |
|----------|-------|
| Barcode  | barcode string |
| Item     | item name |
| GW       | gross weight, 3 dp |
| Purity   | purity label |
| Amount   | Indian number format |
| Return ✓ | Checkbox — disabled + pre-ticked if already returned |

### Already-returned rows
- Row text: `text-muted-foreground` (greyed)
- Checkbox: checked + disabled

### Save button
- Label: "Save Returns"
- Disabled when no new item is selected
- Shows spinner while saving

---

## API Service

New function in `apiService.js`:
```js
export const returnSalesApprovalItems = (id, returnedItemIds) =>
  apiRequest(`sales/api/sale-approval/${id}/return-items/`, {
    method: "POST",
    body: JSON.stringify({ returned_item_ids: returnedItemIds }),
  });
```

---

## Routing

Add to the frontend router (wherever `/sales/salesapproval/add/` and `/:id` are registered):
```
/sales/salesapproval/:id/return/  →  SalesApprovalReturnPage
```

---

## Out of Scope

- Accounting entries on return (no journal entry created — this is a physical goods return only)
- Email/SMS notification to customer
- Un-returning an item (one-way flag by design)
- Printing a return receipt
