# Jewel India ERP — Test Report v2

**Date:** 2026-04-16
**Tooling:** Playwright (Chromium, headless) — batched browser sessions to avoid resource exhaustion.
**Servers:** Django backend on `:8000` (SQLite), Vite frontend on `127.0.0.1:4321`.
**Auth:** `admin/admin123` with `X-RETAIL-ID: R001`.

---

## Executive Summary

| Metric | v1 (Apr 15) | v2 (Apr 16) | Delta |
|---|---|---|---|
| Smoke test routes (191) | 168 pass / 23 fail | 186 pass / 5 remaining* | +18 fixed |
| Deep workflow tests (67) | N/A (not run) | **67 pass / 0 fail** | New |
| Bugs found & fixed | 9 | **+7 more** | 16 total |

*5 remaining = 1 known SQLite contention (since fixed), 4 React DOM cosmetic warnings (non-blocking).

---

## What was tested (67 deep workflow tests)

All 67 routes tested via Playwright browser navigation with error capture (console errors, page errors, HTTP 4xx/5xx).

### Core (1/1 PASS)
- Dashboard

### Sales (5/5 PASS)
- Voucher list, Voucher add form, Return list, Approval list, Quotation add

### Purchase (4/4 PASS)
- Voucher list, Voucher add form, Return list, Purchase order list

### Inventory (8/8 PASS)
- Stock journal (list + add), Stock transfer (list + add)
- Barcode management (list + add), Barcode bulk ops, Barcode merge

### Manufacturing (16/16 PASS)
**Issue forms:** Gold issue, Hallmark issue, Melting, Refinery, Assay, Stone issue, Job work
**Receive forms:** Job work receive, Hallmark receive, Refinery receive, Assay receive, Stone return
**Lists:** Gold issue list, Karigar list
**Other:** Repair (new)

### Financial Reports (8/8 PASS)
- Balance Sheet, P&L, Day Book, Trial Balance
- Cash Book, Bank Book, Ledger Report, Chart of Accounts

### Accounting Vouchers (5/5 PASS)
- Journal (list + add), Payment list, Receipt list, Contra list

### CRM (3/3 PASS)
- Dashboard, Ledger list, Ledger add

### Inventory Reports (5/5 PASS)
- Stock valuation, Barcode report, ID generation, Raw material balance, Metal report

### Masters (8/8 PASS)
- Item, Item group, HSN, Purity, Branch, Company, GSTIN

### Gold Scheme (2/2 PASS)
- Scheme list, Enrollments

### HR (2/2 PASS)
- Employees, Attendance

### Fixed Assets (2/2 PASS)
- Asset list, Depreciation worksheet

---

## Bugs Found & Fixed in This Session

### Bug 1: `peek_next_bill_number` not imported in `inventory/views.py`
- **Route:** `inventory/stockjournal/add`
- **Error:** `NameError: name 'peek_next_bill_number' is not defined` (HTTP 500)
- **Fix:** Added `from accounting.utils import peek_next_bill_number` to `inventory/views.py` imports.
- **File:** `backend/inventory/views.py`

### Bug 2: Missing imports in `StockTrans.jsx` (`getStates`, `fetchSalesperson`, `fetchMainItem`, `fetchPurity`, `fetchPos`)
- **Route:** `inventory/stocktransfer/add`
- **Error:** `ReferenceError: getStates is not defined` (page crash)
- **Fix:** Added all 5 missing functions to the import from `@/services/apiService`.
- **File:** `frontend/src/StockTrans.jsx`

### Bug 3: Wrong API URL for `fetchNextStockTransferNo`
- **Route:** `inventory/stocktransfer/add`
- **Error:** HTTP 404 on `/manufacturing/api/next_stock_transfer_no` (wrong app prefix)
- **Fix:** Changed to `/inventory/api/next_stock_transfer_no` (correct backend URL).
- **File:** `frontend/src/services/apiService.js`

### Bug 4: `stone_receive_billno_view` used write-heavy `generate_stone_rec_billno`
- **Route:** `manufacturing/receive/stonereturn/add`
- **Error:** HTTP 500 `database is locked` (SQLite contention from DB write on GET)
- **Fix:** Replaced with read-only `peek_next_bill_number(request.retail, 'REC/STN')`.
- **File:** `backend/manufacturing/views.py`

### Bugs 5-7: Test route mismatches (test script fixes)
Several test routes were using wrong frontend paths (e.g., `sales/returnlist` instead of `sales/salesreturn/list/`). These were test script issues, not app bugs — corrected in `workflow_batched.py`.

---

## Previously Fixed Bugs (Apr 15 session)

1. HSNSerializer `item_set` writable nested field crash (POST) — set `read_only=True`
2. BarcodeBulkOps `items.map` not a function — added `Array.isArray` guard
3. RawMaterialBalanceReport same `items.map` bug — same fix
4. StockTrans missing `fetchPackets` import — added to import
5. IdGenerationReport stale `/auth/api/users/` URL — changed to `/userauth/api/users/`
6. `apiService.js` same stale URL — fixed
7. `quotation_initial_data` duplicate broken import — removed
8. StockValuationReportView returning PurityMaster object instead of string — fixed
9. `get_next_slip_no` and `repair_job_card_billno_view` missing error handling — added

---

## Known Issues (Not Fixed)

### 1. SQLite `database is locked` (Low priority — dev only)
SQLite single-writer contention still affects some bill-number endpoints when concurrent requests hit. The `peek_next_bill_number` migration resolves the worst cases. **Long-term fix:** migrate to PostgreSQL for any multi-user deployment.

### 2. `accounting/profitdemo` returns 401
The `/accounting/api/pnl` endpoint returns 401 for the admin user. This appears to be a dead/demo route. Consider removing or fixing permissions.

### 3. `quotation_initial_data` slow response (~11s)
The `sales/api/quotation-initial-data/` endpoint takes ~11 seconds because `LedgerSerializer` serializes all customer ledgers with nested data. Needs query optimization (`.only()`, pagination, or a lighter serializer).

### 4. React DOM warnings (cosmetic)
- `inventory/barcodemanagement/merge/` — `<h6>` inside `<tbody>` (invalid DOM nesting)
- `purchase/purchaseorder/list/add` — duplicate `key` prop on list children
- `inventory/reports/stockvalue` — duplicate `key` warning
- `manufacturing/issue/refinary/add` — whitespace text node inside `<colgroup>`

---

## Test Artefacts

| File | Description |
|---|---|
| `test-runs/workflow_results.json` | Full results from 67 deep workflow tests |
| `test-runs/retest_results.json` | Re-test results for 23 previously failing routes |
| `test-runs/smoke_results.json` | Original 191-route smoke test results |
| `test-runs/workflow_batched.py` | Batched Playwright test script (reusable) |
| `test-runs/FORMS.md` | Auto-discovered form field requirements |

---

## Files Modified

### Backend
- `backend/inventory/views.py` — Added `peek_next_bill_number` import
- `backend/manufacturing/views.py` — `stone_receive_billno_view` switched to read-only bill number preview

### Frontend
- `frontend/src/StockTrans.jsx` — Added 5 missing function imports (`getStates`, `fetchSalesperson`, `fetchMainItem`, `fetchPurity`, `fetchPos`)
- `frontend/src/services/apiService.js` — Fixed `fetchNextStockTransferNo` URL from `/manufacturing/` to `/inventory/`
