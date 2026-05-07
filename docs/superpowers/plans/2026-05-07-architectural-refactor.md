# Jewel India ERP — Architectural Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganise the ERP codebase into a professionally structured, consistent, and navigable state without changing any business logic.

**Architecture:** Five phases executed in order. Phases 1, 2, and 3 are fully independent and can be parallelised. Phase 4 runs after Phase 1. Phase 5 runs last. All refactors use barrel re-import/re-export so zero existing import paths break.

**Tech Stack:** Django 4.x (backend), React 18 + Vite + ShadCN + TailwindCSS (frontend), Axios (`apiClient.js`), TanStack Table

**Spec:** `docs/superpowers/specs/2026-05-07-codebase-architectural-refactor-design.md`

---

## Safety Rules (read before touching any file)

- After every backend task: run `python manage.py check` from `backend/`. Zero errors required before commit.
- After every frontend task: run `npm run build` from `frontend/`. Zero build errors required before commit.
- No logic changes. Move code only. If you find a bug while moving, note it but do not fix it inline.
- Relative imports inside a Django app change depth when a `views.py` becomes a `views/` package: `from .models` → `from ..models`. Apply this everywhere.

---

## Phase 1 — Backend God-File Split

### Task 1.1: Convert `accounting/views.py` → `accounting/views/` package

**Files:**
- Create: `backend/accounting/views/__init__.py`
- Create: `backend/accounting/views/vouchers.py`
- Create: `backend/accounting/views/ledger.py`
- Create: `backend/accounting/views/reports.py`
- Create: `backend/accounting/views/bank.py`
- Create: `backend/accounting/views/fixed_assets.py`
- Delete: `backend/accounting/views.py` (after package created and verified)

- [ ] **Step 1: Read `accounting/views.py` lines 1–45 to capture the full import block**

```bash
sed -n '1,45p' backend/accounting/views.py
```

You will need this import block in every sub-module (copy it entirely to each file, then remove unused imports in Phase 5).

- [ ] **Step 2: Create `backend/accounting/views/` directory and `vouchers.py`**

`vouchers.py` receives these classes and functions (cut from `accounting/views.py`):

| Line | Name |
|------|------|
| 1157 | `account_tree` (FBV) |
| 1188 | `_voucher_source_document` (internal helper) |
| 1249 | `JournalEntryViewSet` — **keep this one** |
| ~~1251~~ | ~~`JournalEntryViewSet`~~ — **DELETE this duplicate** |
| 1336 | `initial_data_view` (FBV) |
| 1354 | `get_next_gc_no` (FBV) |
| 1361 | `get_next_vou_no` (FBV) |
| 1383 | `get_next_cg_no` (FBV) |
| 1390 | `VoucherAttachmentListCreate` |
| 1405 | `VoucherAttachmentDelete` |
| 1417 | `GoldCashConversionView` |
| 2694 | `CreditDebitNoteViewSet` |
| 2813 | `NextCNDNNumberView` |

Start `vouchers.py` with the full import block from Step 1, then adjust relative imports:

```python
# backend/accounting/views/vouchers.py
# — paste full import block here —
# Change all  `from .models`  →  `from ..models`
# Change all  `from .serializers`  →  `from ..serializers`
# Change all  `from .utils`  →  `from ..utils`
# Change all  `from .fine_gold_service`  →  `from ..fine_gold_service`
# Change all  `from accounting.utils`  →  `from ..utils`
```

- [ ] **Step 3: Create `ledger.py`**

`ledger.py` receives:

| Line | Name |
|------|------|
| 46 | `DueAdvanceReportSerializer` (inline serializer, only used in ledger reports) |
| 57 | `get_all_descendants` (helper) |
| 77 | `_can_view_combined` (helper) |
| 89 | `_get_retail_for_report` (helper) |
| 99 | `_get_retail_ids_for_report` (helper) |
| 1003 | `AccountViewSet` |
| 1047 | `LedgerOpenBalanceViewSet` |
| 1057 | `AccountAPIView` |
| 1433 | `AgedReceivablesView` |
| 1530 | `AdvanceRegisterView` |
| 1573 | `OutstandingBillsView` |
| 1633 | `cash_total_of_ledger` (FBV) |
| 1644 | `ledger_current_balance` (FBV) |
| 1689 | `LedgerStatementView` |
| 1963 | `OutstandingReportView` |

Apply same relative import adjustments as Step 2.

- [ ] **Step 4: Create `reports.py`**

`reports.py` receives:

| Line | Name |
|------|------|
| 150 | `calcuate_pnl` (helper — note: existing typo, do not fix) |
| 354 | `BankbookReportView` |
| 436 | `TrialBalanceReportView` |
| 560 | `_to_gold_grams` (helper) |
| 570 | `_attach_gold_grams` (helper) |
| 586 | `FineGoldRateBreakdownView` |
| 605 | `BalanceSheetAPIView` |
| 785 | `BsGroupLedgersView` |
| 854 | `ProfitLossAPIView` |
| 870 | `get_accounts_tree` (helper) |
| 946 | `DueAdvanceReportView` |
| 1079 | `CashbookReportView` |
| 1425 | `PurchaseVoucherView` |
| 1624 | `SaleVoucherView` |
| 1802 | `DayBookView` |
| 2045 | `PnlDrilldownView` |
| 2140 | `PnlGroupLedgersView` — **keep this one** |
| 2204 | `PnlLedgerTransactionsView` — **keep this one** |
| 2248 | `FinancialRatiosView` |
| 2544 | `_is_auditor` (helper) |
| 2555 | `AuditQueueView` |
| 2639 | `AuditMarkView` |
| ~~3157~~ | ~~`PnlGroupLedgersView`~~ — **DELETE this duplicate** |
| ~~3218~~ | ~~`PnlLedgerTransactionsView`~~ — **DELETE this duplicate** |

Apply same relative import adjustments.

- [ ] **Step 5: Create `bank.py`**

`bank.py` receives:

| Line | Name |
|------|------|
| 2427 | `BankStatementListCreate` |
| 2458 | `BankStatementDetail` |
| 2469 | `bank_statement_match` (FBV) |
| 2493 | `bank_book_for_recon` (FBV) |

Apply same relative import adjustments.

- [ ] **Step 6: Create `fixed_assets.py`**

`fixed_assets.py` receives:

| Line | Name |
|------|------|
| 2859 | `FixedAssetViewSet` |
| 2894 | `DepreciationSuggestionViewSet` |
| 2912 | `GenerateDepreciationSuggestionView` |
| 2979 | `UpdateSuggestionLineView` |
| 3020 | `ApproveDepreciationSuggestionView` |
| 3111 | `RejectDepreciationSuggestionView` |
| 3129 | `FASettingsView` |
| 3146 | `ITBlockRatesView` |

Apply same relative import adjustments.

- [ ] **Step 7: Create `__init__.py` barrel**

```python
# backend/accounting/views/__init__.py
from .vouchers import *
from .ledger import *
from .reports import *
from .bank import *
from .fixed_assets import *
```

- [ ] **Step 8: Delete the original `accounting/views.py`**

```bash
rm backend/accounting/views.py
```

- [ ] **Step 9: Verify**

```bash
cd backend && python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 10: Commit**

```bash
git add backend/accounting/views/
git commit -m "refactor(accounting): split views.py into views/ package with barrel __init__"
```

---

### Task 1.2: Convert `sales/views.py` → `sales/views/` package

**Files:**
- Create: `backend/sales/views/__init__.py`
- Create: `backend/sales/views/orders.py`
- Create: `backend/sales/views/invoice.py`
- Create: `backend/sales/views/returns.py`
- Create: `backend/sales/views/quotations.py`
- Create: `backend/sales/views/reports.py`
- Delete: `backend/sales/views.py`

- [ ] **Step 1: Read `sales/views.py` lines 1–44 to capture the import block**

```bash
sed -n '1,44p' backend/sales/views.py
```

- [ ] **Step 2: Create `orders.py`**

`sales/views` imports `from userauth import views` and uses `views.RetailBaseViewset`. After the split, each sub-file needs:

```python
from userauth import views as userauth_views
# then use: class X(userauth_views.RetailBaseViewset)
```

`orders.py` receives:

| Line | Name |
|------|------|
| 32 | `order_no_view` (FBV) |
| 45 | `CustomerOrderView` |
| 58 | `CustomerOrderViewset` |
| 210 | `CustomerOrderNumberView` |
| 217 | `RetrieveCustomerOrderView` |
| 225 | `get_customer_item_as_purchase_style` (FBV) |
| 237 | `pending_customer_order_items` (FBV) |
| 280 | `customer_order_timeline` (FBV) |
| 492 | `customer_order_delivery_overview` (FBV) |
| 553 | `customer_order_update_delivery` (FBV) |

- [ ] **Step 3: Create `invoice.py`**

`invoice.py` receives:

| Line | Name |
|------|------|
| 592 | `SalesVoucherViewset` |
| 691 | `GSTInputRegisterView` |
| 744 | `GSTOutputRegisterView` |
| 803 | `tcs_register` (FBV) |
| 845 | `gstr1_report` (FBV) |
| 999 | `gstr3b_report` (FBV) |
| 1086 | `DecimalEncoder` |
| 1093 | `GenerateJsonView` |
| 1343 | `SalesApprovalViewset` |
| 1434 | `get_next_sv_no` (FBV) |
| 1446 | `get_next_sr_no` (FBV) |
| 1458 | `get_next_sa_no` (FBV) |
| 1470 | `customer_cash_received_view` (FBV) |
| 1520 | `sale_voucher_initial_data` (FBV) |
| 1581 | `sale_return_initial_data` (FBV) |
| 1619 | `build_sub_item_text` (helper) |
| 1637 | `build_invoice_context` (helper) |
| 2025 | `EwayBillGenerateView` |
| 2193 | `EWayBillListView` |
| 2285 | `CustomerPurchaseHistoryView` |

- [ ] **Step 4: Create `returns.py`**

`returns.py` receives:

| Line | Name |
|------|------|
| 1334 | `get_sale_voucher_for_return` (FBV) |
| 1367 | `SalesReturnViewset` |
| 1834 | `sale_return_print_data` (FBV) |

- [ ] **Step 5: Create `quotations.py`**

`quotations.py` receives:

| Line | Name |
|------|------|
| 2544 | `QuotationViewset` and all quotation-related FBVs below it |

Read from line 2544 to end of file to identify all quotation FBVs.

- [ ] **Step 6: Create `__init__.py` barrel**

```python
# backend/sales/views/__init__.py
from .orders import *
from .invoice import *
from .returns import *
from .quotations import *
```

- [ ] **Step 7: Delete original `sales/views.py`, verify, commit**

```bash
rm backend/sales/views.py
cd backend && python manage.py check
git add backend/sales/views/
git commit -m "refactor(sales): split views.py into views/ package with barrel __init__"
```

Expected: `System check identified no issues (0 silenced).`

---

### Task 1.3: Convert `purchase/serializer.py` → `purchase/serializers/` package

**Files:**
- Create: `backend/purchase/serializers/__init__.py`
- Create: `backend/purchase/serializers/voucher.py`
- Create: `backend/purchase/serializers/order.py`
- Create: `backend/purchase/serializers/return_.py`
- Delete: `backend/purchase/serializer.py`

> Note: the existing file is `serializer.py` (singular). The new package is `serializers/` (plural). Check `purchase/views.py` and `purchase/urls.py` for the import statement and update it.

- [ ] **Step 1: Find the import statement in `purchase/views.py`**

```bash
grep -n "from.*serializer" backend/purchase/views.py | head -5
```

Note the exact import path. You will update it after creating the package.

- [ ] **Step 2: Create `voucher.py`**

`voucher.py` receives (from `purchase/serializer.py`):

| Line | Name |
|------|------|
| 18 | `PurchaseVoucherSerializer` |
| 340 | `PurchaseVoucherDetailsSerializer` |
| 391 | `PurchaseVoucherItemsSerializer` |
| 517 | `PurchaseVoucherPostSerializer` |
| 1112 | `PurchaseVoucherDetailsToReturnDetailsSerializer` |
| 1117 | `PurchaseVoucherItemToReturnSerializer` |
| 1125 | `PurchaseAttachmentSerializer` |
| 1144 | `PurchaseVoucherToReturnSerializer` |

- [ ] **Step 3: Create `order.py`**

`order.py` receives:

| Line | Name |
|------|------|
| 23 | `PurchaseOrderSerializer` |
| 28 | `PurchaseOrderItemsSerializer` |
| 965 | `PurchaseOrderItemsForPostSerializer` |
| 988 | `PurchaseOrderForPostSerializer` |

- [ ] **Step 4: Create `return_.py`**

`return_.py` receives:

| Line | Name |
|------|------|
| 63 | `PurchaseReturnDetailsSerializer` |
| 90 | `PurchaseReturnItemsSerializer` |
| 136 | `PurchaseReturnSerializer` |

- [ ] **Step 5: Create `__init__.py` barrel**

```python
# backend/purchase/serializers/__init__.py
from .voucher import *
from .order import *
from .return_ import *
```

- [ ] **Step 6: Update the import in `purchase/views.py`**

Change the old serializer import to point at the new package:

```python
# Old (whatever grep showed in Step 1):
from .serializer import PurchaseVoucherPostSerializer, ...
# or:
from purchase.serializer import ...

# New:
from .serializers import PurchaseVoucherPostSerializer, ...
# or:
from purchase.serializers import ...
```

- [ ] **Step 7: Delete original, verify, commit**

```bash
rm backend/purchase/serializer.py
cd backend && python manage.py check
git add backend/purchase/serializers/ backend/purchase/views.py
git commit -m "refactor(purchase): split serializer.py into serializers/ package with barrel __init__"
```

Expected: `System check identified no issues (0 silenced).`

---

## Phase 2 — Frontend API Service Split

### Task 2.1: Create `_helpers.js` and domain module scaffold

**Files:**
- Create: `frontend/src/services/api/_helpers.js`
- Create: `frontend/src/services/api/` (directory with all domain `.js` files)

- [ ] **Step 1: Read the `_api` helper from `apiService.js`**

```bash
sed -n '365,375p' frontend/src/services/apiService.js
```

- [ ] **Step 2: Create `_helpers.js`**

```js
// frontend/src/services/api/_helpers.js
// Shared internal helpers for all domain API modules.
import apiClient from "../apiClient";

/**
 * Thin wrapper around apiClient that normalises responses to
 * { success: true, data } | { success: false, error }.
 * Use for simple GET/POST/PATCH/DELETE calls.
 */
export const _api = async (method, url, data) => {
  try {
    const r = await apiClient[method](url, data);
    return { success: true, data: r.data };
  } catch (e) {
    return { success: false, error: e.response?.data || e.message };
  }
};
```

- [ ] **Step 3: Commit scaffold**

```bash
git add frontend/src/services/api/
git commit -m "refactor(frontend): create services/api/ domain module scaffold + _helpers.js"
```

---

### Task 2.2: Create `userauth.js` and `contacts.js` domain modules

**Files:**
- Create: `frontend/src/services/api/userauth.js`
- Create: `frontend/src/services/api/contacts.js`

- [ ] **Step 1: Create `userauth.js`**

Open `apiService.js` and cut all functions in the table below into `userauth.js`. Each file starts with:

```js
// frontend/src/services/api/userauth.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions to move to `userauth.js` (search by name in `apiService.js`):

`loginAndSaveToken`, `getStates`, `getTypes`, `getRetails`, `fetchRetails`, `fetchStates`, `fetchUsers`, `createUser`, `updateUser`, `assignUserRetail`, `fetchRoles`, `createRole`, `updateRole`, `deleteRole`, `fetchRolePermissions`, `saveRolePermissions`, `fetchModules`, `assignUserRole`, `fetchSystemSettings`, `updateSystemSettings`, `backupDatabaseToPath`, `backupDatabaseDownload`, `fetchDashboardSummary`, `fetchAuditLog`, `reverseTransaction`, `restoreToPoint`, `getFiscalYears`, `createFiscalYear`, `setActiveFiscalYear`, `closeFiscalYear`, `reopenFiscalYear`, `getSetupStatus`, `seedStates`, `seedAccountGroups`, `seedTdsTcs`, `resetErp`, `setupRollback`, `syncUserRetails`, `seedSystemLedgers`, `getMySQLConfig`, `runMySQLSync`, `fetchGstins`, `createGstin`, `getNextGCno` (if it relates to userauth — otherwise keep in accounting)

- [ ] **Step 2: Create `contacts.js`**

```js
// frontend/src/services/api/contacts.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions to move to `contacts.js`:

`getLedgers`, `createLedger`, `createGC`, `getgcbillno`, `getcgbillno`, `updateLedger`, `addLedgerRole`, `removeLedgerRole`, `setPrimaryLedgerRole`, `getLedger`, `getLedgerList`, `fetchParentAccount`, `checkLedgerName`, `deleteLedger`, `fetchSalesperson`, `createSalesperson`, `updateSalesperson`, `deleteSalesperson`, `fetchCRMOccasions`, `fetchCRMSettings`, `updateCRMSettings`, `fetchCRMSendLog`, `triggerCRMTestSend`, `fetchLedgerTDSInfo`, `fetchCustomerPurchasesByLedger`, `fetchCustomerOrdersByLedger`

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: build succeeds (no errors). If errors, check that the moved functions still reference `apiClient` from the correct relative path `../apiClient`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/services/api/userauth.js frontend/src/services/api/contacts.js
git commit -m "refactor(frontend): extract userauth.js and contacts.js API modules"
```

---

### Task 2.3: Create `accounting.js`, `sales.js`, `purchase.js`

**Files:**
- Create: `frontend/src/services/api/accounting.js`
- Create: `frontend/src/services/api/sales.js`
- Create: `frontend/src/services/api/purchase.js`

- [ ] **Step 1: Create `accounting.js`**

```js
// frontend/src/services/api/accounting.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions: `getAccountGroup`, `getAccount`, `createAccount`, `updateAccount`, `deleteAccount`, `getChartOfAccounts`, `getOpeningBalances`, `createOpeningBalance`, `updateOpeningBalance`, `deleteOpeningBalance`, `fetchVoucherNoNext`, `createJournalEntry`, `fetchJournalEntryForEdit`, `updateJournalEntryForEdit`, `fetchtrial`, `fetchDuePayments`, `fetchDuePaymentsSale`, `fetchLedgerBalance`, `fetchLedgerStatement`, `fetchOutstandingBills`, `fetchAgedReceivables`, `fetchAdvanceRegister`, `fetchDayBook`, `fetchOutstandingReport`, `fetchBankBookReport`, `fetchCashBookReport`, `fetchBankStatements`, `createBankStatement`, `deleteBankStatement`, `matchBankStatement`, `fetchBankReconBookEntries`, `fetchCommissionReport`, `createCommissionJV`, `fetchCommissionLedgerConfig`, `setCommissionLedger`, `suggestAccounts`, `fetchGSTInputReport`, `fetchGSTOutputReport`, `fetchGSTR1Report`, `fetchGSTR3BReport`, `fetchTDSRegister`, `fetchTCSRegister`

- [ ] **Step 2: Create `sales.js`**

```js
// frontend/src/services/api/sales.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions: `fetchOrderNoNext`, `fetchSaleRetNext`, `fetchNextSaleNo`, `fetchNextSaleAppNo`, `fetchSaleVoucherInitialData`, `fetchSaleReturnInitialData`, `fetchDetailsforSaleReturn`, `fetchSalesVoucher`, `fetchSalesReturn`, `fetchSalesApproval`, `createSalesApproval`, `updateSalesApproval`, `fetchSalesApprovalById`, `createSalesReturn`, `updateSalesReturn`, `fetchSalesReturnById`, `fetchSaleReturnPrintData`, `createSalesVoucher`, `updateSalesVoucher`, `fetchSalesVoucherwithID`, `deleteSalesReturn`, `deleteSalesApproval`, `deleteSalesVoucher`, `deleteCustomerOrder`, `cancelCustomerOrder`, `fetchDeliveryOverview`, `updateOrderDeliveryStatus`, `fetchPendingCustomerOrderItems`, `fetchCustomerOrderTimeline`, `fetchCustomerOrderForEdit`, `updateCustomerOrderForEdit`, `createCustomerOrder`, `getCustomerItemAsPurchaseStyle`, `fetchCustomerCashReceived`, `updateEwayTransport`, `fetchNextQuotationNo`, `fetchQuotationInitialData`, `createQuotation`, `fetchQuotations`, `fetchQuotationById`, `updateQuotation`, `patchQuotation`, `deleteQuotation`, `fetchQuotationPrintData`, `duplicateQuotation`, `finalizeQuotation`

- [ ] **Step 3: Create `purchase.js`**

```js
// frontend/src/services/api/purchase.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions: `fetchPVNoNext`, `fetchPRNoNext`, `fetchPoNoNext`, `fetchPurchaseVoucher`, `fetchPurchaseOrder`, `fetchPurchaseRetun`, `fetchPurchaseApproval`, `fetchPos`, `updatePurchaseOrderForEdit`, `createPurchaseOrder`, `fetchPurchaseOrderForEdit`, `fetchPendingPOItemsByVendor`, `fetchDetailsForPurchaseReturn`, `createPurchaseReturn`, `updatePurchaseReturnForEdit`, `fetchPurchaseReturnForEdit`, `getPurchaseAttachments`, `uploadPurchaseAttachment`, `deletePurchaseAttachment`, `updatePurchaseVoucherForEdit`, `createPurchaseVoucher`, `fetchPurchaseReturnInitialData`, `deletePurchaseVoucher`, `deletePurchaseReturn`, `deletePurchaseOrder`, `fetchPurchaseVoucherForSample`, `fetchPurchaseVouchersForSample`, `fetchStockMatchingReport`

- [ ] **Step 4: Verify build and commit**

```bash
cd frontend && npm run build 2>&1 | tail -5
git add frontend/src/services/api/accounting.js frontend/src/services/api/sales.js frontend/src/services/api/purchase.js
git commit -m "refactor(frontend): extract accounting.js, sales.js, purchase.js API modules"
```

---

### Task 2.4: Create `inventory.js`, `manufacturing.js`, `masters.js`

**Files:**
- Create: `frontend/src/services/api/inventory.js`
- Create: `frontend/src/services/api/manufacturing.js`
- Create: `frontend/src/services/api/masters.js`

- [ ] **Step 1: Create `inventory.js`**

```js
// frontend/src/services/api/inventory.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions: `getClosingStockValuation`, `fetchInterRetailTransfers`, `fetchInterRetailTransfer`, `createInterRetailTransfer`, `updateInterRetailTransfer`, `deleteInterRetailTransfer`, `sendInterRetailTransfer`, `receiveInterRetailTransfer`, `cancelInterRetailTransfer`, `getNextInterRetailTransferNo`, `getClosingStockTxns`, `fetchStockJournal`, `fetchNextStockJournalNo`, `createStockJournal`, `fetchStockJournalForEdit`, `updateStockJournalForEdit`, `deleteStockJournal`, `fetchBarcodeDetail`, `fetchBarcodeForEdit`, `fetchBarcodeDetailOnly`, `updateBarcodeForEdit`, `splitBarcode`, `deleteBarcodeManagement`, `fetchUnbarcodedForPicker`, `fetchInTransitBarcodes`, `markStockTransferSent`, `markStockTransferReceived`, `deleteStockTransfer`, `fetchStockValuationReport`, `fetchIDGenerationReport`, `fetchIDGenerationReportAPI`, `getOpeningInventory`, `createOpeningInventory`, `updateOpeningInventory`, `deleteOpeningInventory`, `getOpeningInventoryById`, `fetchBarcodeStockReport`, `fetchBarcodeStockReportBarcodes`, `fetchItemWiseBarcode`, `fetchRfidTagList`, `assignRfidTag`, `submitRfidCount`, `fetchRfidSessions`, `fetchRfidSessionResults`, `fetchNextStockTransferNo`

- [ ] **Step 2: Create `manufacturing.js`**

```js
// frontend/src/services/api/manufacturing.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions: `createKarigarIssue`, `createKarigarStoneIssue`, `fetchStoneIssueForEdit`, `updateKarigarStoneIssue`, `createKarigarGoldIssue`, `FetchKarigarGoldIssueBill`, `createSampleIssue`, `updateSampleIssue`, `fetchSampleIssues`, `fetchSampleIssueForEdit`, `deleteSampleIssue`, `fetchSampleIssueNextBillno`, `fetchKarigarReceiveSlipForSample`, `fetchKarigarReceiveSlipsForSample`, `fetchBarcodeForSample`, `fetchKarigarReceiveForSamplePicker`, `fetchSampleIssueInitialData`, `fetchKarigarStoneIssueReport`, `fetchKarigarStoneRecReport`, `fetchKarigarReceiveReport`, `fetchHallMarkIssueReport`, `fetchPurchaseFinished`, `fetchReceivedFinished`, `fetchJobStatusReport`, `fetchStockTransfer`, `fetchSubcontractorLedger`, `fetchSlipNoNext`, `fetchReceiveItemsForBarcode`, `fetchPurhcaseItemsForBarcode`, `fetchOrderItem`, `deleteJobWorkIssue`, `deleteGoldIssue`, `deleteStoneIssue`, `deleteHallmarkIssue`, `deleteRefineryIssue`, `deleteMeltingIssue`, `deleteAssayIssue`, `deleteJobWorkReceive`, `deleteStoneReceive`, `deleteHallmarkReceive`, `deleteRefineryReceive`, `deleteMeltingReceive`, `deleteAssayReceive`, `fetchSplitBarcodeReport`, `fetchMergeBarcodeReport`, `fetchArtisanDataAPI`, `fetchItemDataAPI`, `fetchUserDataAPI`, `fetchStoneWorkOrderReportAPI`, `fetchGroupDataAPI`, `fetchShapeDataAPI`, `fetchPacketWiseStoneReportAPI`, `fetchPacketDataAPI`

> Note: `fetchPurhcaseItemsForBarcode` contains a deliberate typo (existing bug). Move it as-is — do not rename.

- [ ] **Step 3: Create `masters.js`**

```js
// frontend/src/services/api/masters.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions: `fetchMainItem`, `fetchShape`, `fetchGroup`, `fetchPurity`, `createPurity`, `updatePurity`, `deletePurity`, `fetchHSNs`, `createHsn`, `updateHsn`, `deleteHsn`, `fetchMainItemsForHSN`, `fetchColors`, `createColor`, `updateColor`, `deleteColor`, `fetchShapes`, `createShape`, `updateShape`, `deleteShape`, `fetchItems`, `createItem`, `updateItem`, `deleteItem`, `fetchItemGroups`, `createItemGroup`, `updateItemGroup`, `deleteItemGroup`, `fetchPacketGroups`, `createPacketGroup`, `updatePacketGroup`, `deletePacketGroup`, `createPacket`, `updatePacket`, `deletePacket`, `fetchKarigarMaking`, `createKarigarMaking`, `updateKarigarMaking`, `deleteKarigarMaking`, `fetchCompanies`, `createCompany`, `updateCompany`, `deleteCompany`, `fetchBranches`, `createBranch`, `updateBranch`, `deleteBranch`, `fetchBranchAnalytics`, `fetchRetailAnalytics`, `fetchTDSSections`, `createTDSSection`, `updateTDSSection`, `deleteTDSSection`, `fetchTCSSections`, `createTCSSection`, `updateTCSSection`, `deleteTCSSection`, `fetchExhibitions`, `createExhibition`, `updateExhibition`, `deleteExhibition`, `activateExhibition`, `deactivateExhibition`, `fetchB2BPricelists`, `getB2BPricelist`, `createB2BPricelist`, `updateB2BPricelist`, `deleteB2BPricelist`, `fetchB2BPricelistForLedger`, `fetchRetailDiscountPricelists`, `createRetailDiscountPricelist`, `updateRetailDiscountPricelist`, `deleteRetailDiscountPricelist`, `fetchRetailDiscountPricelistForLedger`, `fetchActiveOffer`, `fetchSalesOffers`, `createSalesOffer`, `updateSalesOffer`, `deleteSalesOffer`, `downloadLedgerTemplate`, `uploadLedgerCSV`, `uploadHSNCSV`, `uploadItemGroupCSV`, `uploadItemCSV`, `uploadPacketGroupCSV`, `uploadPacketCSV`, `uploadKarigarMakingCSV`, `fetchLedgerTDSInfo` (if not moved to contacts)

- [ ] **Step 4: Verify build and commit**

```bash
cd frontend && npm run build 2>&1 | tail -5
git add frontend/src/services/api/inventory.js frontend/src/services/api/manufacturing.js frontend/src/services/api/masters.js
git commit -m "refactor(frontend): extract inventory.js, manufacturing.js, masters.js API modules"
```

---

### Task 2.5: Create remaining domain modules + convert `apiService.js` to barrel

**Files:**
- Create: `frontend/src/services/api/goldscheme.js`
- Create: `frontend/src/services/api/goldrates.js`
- Create: `frontend/src/services/api/hr.js`
- Create: `frontend/src/services/api/fixedAssets.js`
- Create: `frontend/src/services/api/carryforward.js`
- Create: `frontend/src/services/api/vendorAnalytics.js`
- Create: `frontend/src/services/api/ai.js`
- Modify: `frontend/src/services/apiService.js` (convert to barrel)

- [ ] **Step 1: Create `goldscheme.js`**

```js
// frontend/src/services/api/goldscheme.js
import apiClient from "../apiClient";
import { _api } from "./_helpers";
```

Functions: `fetchSchemes`, `createScheme`, `updateScheme`, `deleteScheme`, `fetchSchemeEnrollments`, `fetchSchemeEnrollment`, `createSchemeEnrollment`, `schemeEnrollmentPay`, `fetchSchemeStatement`, `fetchSchemeBenefit`, `redeemSchemeEnrollment`, `cancelSchemeEnrollment`, `fetchSchemeSummary`, `fetchMaturityCalendar`, `fetchOverduePayments`

- [ ] **Step 2: Create `goldrates.js`**

```js
// frontend/src/services/api/goldrates.js
import apiClient from "../apiClient";
```

Functions: `getGoldRate` and any other gold-rate fetching functions found in `apiService.js` (search for `/goldrates/`).

- [ ] **Step 3: Create `hr.js`**

```js
// frontend/src/services/api/hr.js
import apiClient from "../apiClient";
```

Functions: `fetchEmployees`, `createEmployeeWithUser`, `updateEmployee`, `fetchSalaryStructures`, `createSalaryStructure`, `fetchDeductionConfig`, `saveDeductionConfig`, `fetchSalarySlips`, `generatePayslip`, `bulkGeneratePayslip`, `approvePayslip`, `fetchHRSettings`, `saveHRSettings`, `fetchLeaveBalances`, `fetchITBlockRates`, `seedHRLedgers`, `getHRSettings`, `getPendingCheques`, `depositCheque`

- [ ] **Step 4: Create `fixedAssets.js`**

```js
// frontend/src/services/api/fixedAssets.js
import apiClient from "../apiClient";
```

Functions: `fetchFixedAssets`, `createFixedAsset`, `updateFixedAsset`, `fetchDepreciationSuggestions`, `generateDepreciationSuggestion`, `updateSuggestionLine`, `approveDepreciationSuggestion`, `rejectDepreciationSuggestion`, `fetchFASettings`, `saveFASettings`

- [ ] **Step 5: Create `carryforward.js`**

```js
// frontend/src/services/api/carryforward.js
import apiClient from "../apiClient";
```

Functions: `carryForwardPreview`, `carryForwardExecute`, `getCarryForwardLog`

- [ ] **Step 6: Create `vendorAnalytics.js`**

```js
// frontend/src/services/api/vendorAnalytics.js
import apiClient from "../apiClient";
```

Functions: `fetchVendorDashboard`, `fetchVendorStockAgeing`, `fetchVendorDesignPerformance`, `fetchVendorInventoryTurnover`, `fetchVendorItemPerformance`, `fetchVendorComparison`

- [ ] **Step 7: Create `ai.js`**

```js
// frontend/src/services/api/ai.js
import apiClient from "../apiClient";
```

Functions: `askAIQuery`, `parseInvoice`

- [ ] **Step 8: Convert `apiService.js` to a barrel**

After all domain modules are created, verify the original `apiService.js` now has no remaining `export` statements that haven't been moved. Then replace its entire content:

```js
// frontend/src/services/apiService.js
// ─────────────────────────────────────────────────────────────────────────────
// Barrel re-export — imports all domain API modules so existing code that
// imports from "@/services/apiService" continues to work without changes.
// New code should import directly from the domain module:
//   import { createSalesVoucher } from "@/services/api/sales"
// ─────────────────────────────────────────────────────────────────────────────
export * from "./api/userauth";
export * from "./api/contacts";
export * from "./api/accounting";
export * from "./api/sales";
export * from "./api/purchase";
export * from "./api/inventory";
export * from "./api/manufacturing";
export * from "./api/masters";
export * from "./api/goldscheme";
export * from "./api/goldrates";
export * from "./api/hr";
export * from "./api/fixedAssets";
export * from "./api/carryforward";
export * from "./api/vendorAnalytics";
export * from "./api/ai";
```

- [ ] **Step 9: Final build verification**

```bash
cd frontend && npm run build 2>&1 | tail -10
```

Expected: zero errors. If there are "duplicate export" errors, a function was accidentally left in `apiService.js` AND in a domain module — remove it from whichever location is wrong.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/services/
git commit -m "refactor(frontend): split apiService.js into 14 domain modules, barrel re-export"
```

---

## Phase 3 — Shared Frontend Component Library

### Task 3.1: Create `ConfirmDialog` component

**Files:**
- Create: `frontend/src/components/common/ConfirmDialog.jsx`

> The ShadCN `alert.jsx` component already exists in `components/ui/`. This task wraps it.

- [ ] **Step 1: Create the component**

```jsx
// frontend/src/components/common/ConfirmDialog.jsx
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

/**
 * Reusable confirmation dialog for destructive actions.
 * Replaces window.confirm() throughout the ERP.
 *
 * @example
 * <ConfirmDialog
 *   open={!!deleteId}
 *   title="Delete Color"
 *   description="This color will be permanently removed."
 *   onConfirm={handleDelete}
 *   onCancel={() => setDeleteId(null)}
 * />
 */
export function ConfirmDialog({
  open,
  onConfirm,
  onCancel,
  title = "Are you sure?",
  description = "This action cannot be undone.",
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  variant = "destructive",
}) {
  return (
    <AlertDialog open={open} onOpenChange={(v) => { if (!v) onCancel() }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={onCancel}>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className={
              variant === "destructive"
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                : ""
            }
          >
            {confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/common/ConfirmDialog.jsx
git commit -m "feat(ui): add ConfirmDialog shared component replacing window.confirm"
```

---

### Task 3.2: Enhance `table.jsx` with `isLoading` and empty state

**Files:**
- Modify: `frontend/src/table.jsx`

The current `table.jsx` has no `isLoading` or empty-state handling. Components manage these inline with repeated skeleton code.

- [ ] **Step 1: Read current `table.jsx`**

```bash
cat frontend/src/table.jsx
```

- [ ] **Step 2: Add `Skeleton` import and `isLoading` / `emptyMessage` props**

The updated signature and loading/empty handling:

```jsx
// Add to imports:
import { Skeleton } from "@/components/ui/skeleton"

// Update function signature:
export function DataTable({
  columns,
  data,
  rowClick = () => {},
  isLoading = false,
  emptyMessage = "No records found.",
}) {
  // Add before the table return:
  if (isLoading) {
    return (
      <div className="flex flex-col gap-2">
        {[...Array(5)].map((_, i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    )
  }

  // Inside TableBody, replace the existing empty check with:
  // {table.getRowModel().rows?.length ? (
  //   ... existing row rendering ...
  // ) : (
  //   <TableRow>
  //     <TableCell
  //       colSpan={columns.length}
  //       className="text-center py-10 text-sm text-muted-foreground"
  //     >
  //       {emptyMessage}
  //     </TableCell>
  //   </TableRow>
  // )}
```

Apply these changes to `table.jsx` without touching any other logic in the file.

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/table.jsx
git commit -m "feat(ui): add isLoading skeleton and emptyMessage to DataTable"
```

---

### Task 3.3: Create `parseApiError` utility

**Files:**
- Modify: `frontend/src/lib/utils.js`

The pattern `typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : res.error` appears in ~20+ components. Extract it once.

- [ ] **Step 1: Read current `lib/utils.js`**

```bash
cat frontend/src/lib/utils.js
```

- [ ] **Step 2: Append `parseApiError` to `utils.js`**

Add after the existing content:

```js
/**
 * Normalises API error responses to a human-readable string.
 * Handles both DRF field-level errors (objects) and plain string errors.
 *
 * @param {object|string|null} error - The error from { success, error } API response
 * @returns {string}
 *
 * @example
 * const msg = parseApiError(res.error)
 * toast({ title: "Error", description: msg, variant: "destructive" })
 */
export function parseApiError(error) {
  if (error === null || error === undefined) {
    return "An unexpected error occurred."
  }
  if (typeof error === "object") {
    return Object.values(error).flat().join(", ")
  }
  return String(error)
}
```

- [ ] **Step 3: Verify build and commit**

```bash
cd frontend && npm run build 2>&1 | tail -5
git add frontend/src/lib/utils.js
git commit -m "feat(utils): add parseApiError helper to standardise error toast messages"
```

---

### Task 3.4: Migrate `ColorMasterPage` and `PurityMasterPage` as reference implementations

**Files:**
- Modify: `frontend/src/components/Masters/ColorMasterPage.jsx`
- Modify: `frontend/src/components/Masters/PurityMasterPage.jsx`

These are the simplest master pages. Migrating them proves the shared components work and provides a reference pattern for future migrations.

- [ ] **Step 1: Update `ColorMasterPage.jsx`**

Replace `window.confirm` delete with `ConfirmDialog`. Replace inline skeleton with `isLoading` prop on `DataTable`. Replace inline error message construction with `parseApiError`.

Full updated file:

```jsx
import { useState, useEffect } from "react"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { DataTable } from "@/table"
import { SquarePen, Trash2, Plus, X, Check } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { useF4Submit } from "@/hooks/useF4Submit"
import { fetchColors, createColor, updateColor, deleteColor } from "@/services/apiService"
import { ConfirmDialog } from "@/components/common/ConfirmDialog"
import { parseApiError } from "@/lib/utils"

const emptyForm = { color_name: "" }

export default function ColorMasterPage() {
  const { toast } = useToast()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(emptyForm)
  const [submitting, setSubmitting] = useState(false)
  const [deleteId, setDeleteId] = useState(null)

  const load = async () => {
    setLoading(true)
    const res = await fetchColors()
    if (res.success) {
      const d = res.data
      setRows(Array.isArray(d) ? d : d?.results ?? [])
    }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const handleChange = (e) =>
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.color_name.trim()) return
    setSubmitting(true)
    const payload = { color_name: form.color_name.trim() }
    const res = editingId
      ? await updateColor(editingId, payload)
      : await createColor(payload)
    if (res.success) {
      toast({ title: editingId ? "Color updated" : "Color added" })
      reset()
      load()
    } else {
      toast({ title: "Error", description: parseApiError(res.error), variant: "destructive" })
    }
    setSubmitting(false)
  }

  useF4Submit(handleSubmit)

  const handleEdit = (row) => {
    setForm({ color_name: row.color_name })
    setEditingId(row.id)
    setShowForm(true)
  }

  const handleDelete = async () => {
    const res = await deleteColor(deleteId)
    if (res.success) {
      toast({ title: "Color deleted" })
      load()
    } else {
      toast({ title: "Error", description: parseApiError(res.error), variant: "destructive" })
    }
    setDeleteId(null)
  }

  const reset = () => {
    setShowForm(false)
    setEditingId(null)
    setForm(emptyForm)
  }

  const columns = [
    {
      header: "Action",
      cell: ({ row }) => (
        <div className="flex gap-3">
          <button onClick={() => handleEdit(row.original)} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="size-4" />
          </button>
          <button onClick={() => setDeleteId(row.original.id)} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", cell: ({ row }) => row.index + 1 },
    { header: "Color Name", accessorKey: "color_name" },
  ]

  return (
    <div className="p-4 flex flex-col gap-4">
      <ConfirmDialog
        open={!!deleteId}
        title="Delete Color"
        description="This color will be permanently removed."
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
      />

      {!showForm && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add Color
          </Button>
        </div>
      )}

      {showForm && (
        <div className="rounded-lg border border-border bg-muted/30 p-4">
          <h3 className="text-sm font-semibold mb-3">
            {editingId ? "Edit Color" : "Add Color"}
          </h3>
          <form onSubmit={handleSubmit}>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Color Name *</Label>
                <Input
                  name="color_name"
                  value={form.color_name}
                  onChange={handleChange}
                  placeholder="e.g. White, Yellow, Rose"
                  className="h-9 w-48"
                  autoFocus
                  maxLength={50}
                />
              </div>
              <Button type="submit" size="sm" className="h-9" disabled={submitting || !form.color_name.trim()}>
                <Check className="size-4 mr-1" />
                {editingId ? "Update" : "Save"}
              </Button>
              <Button type="button" variant="outline" size="sm" className="h-9" onClick={reset}>
                <X className="size-4 mr-1" />
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      <DataTable
        columns={columns}
        data={rows}
        isLoading={loading}
        emptyMessage="No colors found. Add one above."
      />
    </div>
  )
}
```

- [ ] **Step 2: Update `PurityMasterPage.jsx` with the same pattern**

Apply identical changes:
1. Add `import { ConfirmDialog } from "@/components/common/ConfirmDialog"`
2. Add `import { parseApiError } from "@/lib/utils"`
3. Replace `const [loading, ...]` + skeleton JSX with `isLoading={loading}` on `DataTable`
4. Replace `window.confirm(...)` delete with `const [deleteId, setDeleteId] = useState(null)` + `ConfirmDialog`
5. Replace inline error message construction with `parseApiError(res.error)`
6. Remove `import { Skeleton } from "@/components/ui/skeleton"` (no longer needed)

- [ ] **Step 3: Verify build**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Masters/ColorMasterPage.jsx frontend/src/components/Masters/PurityMasterPage.jsx
git commit -m "refactor(masters): migrate Color and Purity pages to shared ConfirmDialog + parseApiError"
```

---

## Phase 4 — Backend Base Class Audit & Duplicate Fix

### Task 4.1: Fix duplicate class definitions in accounting views

> Run after Task 1.1 is complete. The duplicate classes will have been split into separate files, making them easier to identify.

**Files:**
- Modify: `backend/accounting/views/vouchers.py` (JournalEntryViewSet duplicate)
- Modify: `backend/accounting/views/reports.py` (PnlGroupLedgersView + PnlLedgerTransactionsView duplicates)

- [ ] **Step 1: Verify duplicates were removed during Task 1.1**

```bash
grep -n "class JournalEntryViewSet" backend/accounting/views/vouchers.py
grep -n "class PnlGroupLedgersView" backend/accounting/views/reports.py
grep -n "class PnlLedgerTransactionsView" backend/accounting/views/reports.py
```

Expected: exactly one match per class. If two matches are found, compare the two implementations and delete the less complete one.

- [ ] **Step 2: Verify no remaining duplicates across the entire backend**

```bash
grep -rn "^class " backend/ --include="*.py" | grep -v migrations | grep -v __pycache__ | awk -F: '{print $3}' | sort | uniq -d
```

Expected: no output (no duplicate class names). If any duplicates are shown, investigate and resolve.

- [ ] **Step 3: Run check and commit**

```bash
cd backend && python manage.py check
git add backend/accounting/views/
git commit -m "fix(accounting): remove duplicate JournalEntryViewSet and PnlGroup view classes"
```

---

### Task 4.2: Audit viewsets not using `RetailBaseViewset`

**Files:**
- Modify: any viewsets found in audit

- [ ] **Step 1: Find viewsets that should use `RetailBaseViewset` but don't**

```bash
grep -rn "class.*ViewSet\|class.*Viewset" backend/ --include="*.py" | grep -v migrations | grep -v __pycache__ | grep -v "RetailBaseViewset\|RetailBaseViewSet\|ModelViewSet\|ReadOnlyModelViewSet\|GenericViewSet\|viewsets.ViewSet"
```

For each result: determine whether that viewset handles retail-scoped data (data that should be filtered by `request.retail`). If yes, it should inherit from `RetailBaseViewset`.

- [ ] **Step 2: For each viewset that should use `RetailBaseViewset`, update its base class**

Example fix (one-line change per viewset):

```python
# Before:
class SomeViewSet(ModelViewSet):

# After:
class SomeViewSet(RetailBaseViewset):
```

Ensure `RetailBaseViewset` is imported at the top of each file:

```python
from userauth.views import RetailBaseViewset
```

- [ ] **Step 3: Verify and commit**

```bash
cd backend && python manage.py check
git add -u
git commit -m "refactor(backend): standardise retail-scoped viewsets to use RetailBaseViewset"
```

---

## Phase 5 — Dead Code & Import Cleanup

### Task 5.1: Clean backend files touched in Phases 1 and 4

**Files:** All files in `backend/accounting/views/`, `backend/sales/views/`, `backend/purchase/serializers/`, and any files modified in Phase 4.

- [ ] **Step 1: Remove unused imports from each sub-module**

For each file created in Phase 1, run:

```bash
# Install autoflake if not present:
pip install autoflake

# Check what would be removed (dry run):
autoflake --remove-all-unused-imports --check backend/accounting/views/vouchers.py

# Apply:
autoflake --remove-all-unused-imports --in-place backend/accounting/views/vouchers.py
```

Repeat for every sub-module file. After each file, run `python manage.py check` to confirm nothing broke.

- [ ] **Step 2: Remove commented-out code blocks**

Open each sub-module file and manually remove any blocks of commented-out code (lines starting with `#` that contain old code, not documentation). Leave genuine documentation comments.

- [ ] **Step 3: Standardise import ordering in each file**

Import ordering standard for this project:

```python
# 1. stdlib
import json
from datetime import date, datetime

# 2. Django
from django.db import transaction
from django.http import JsonResponse

# 3. DRF / third-party
from rest_framework import status
from rest_framework.response import Response

# 4. Local app imports
from contacts.models import Ledger
from userauth.views import RetailBaseViewset

# 5. Relative imports (current app)
from ..models import VoucherMain
from ..serializers import JournalEntrySerializer
```

- [ ] **Step 4: Verify and commit**

```bash
cd backend && python manage.py check
git add backend/accounting/views/ backend/sales/views/ backend/purchase/serializers/
git commit -m "chore(backend): remove unused imports and dead code from split view/serializer modules"
```

---

### Task 5.2: Clean frontend files touched in Phases 2 and 3

**Files:** All files in `frontend/src/services/api/`, `frontend/src/components/Masters/ColorMasterPage.jsx`, `frontend/src/components/Masters/PurityMasterPage.jsx`

- [ ] **Step 1: Remove unused imports from all domain API modules**

For each file in `services/api/`, open it and verify every import (`apiClient`, `_api`) is actually used. Remove any that are not.

- [ ] **Step 2: Scan for `console.log` statements in touched files**

```bash
grep -rn "console\.log" frontend/src/services/api/ frontend/src/components/Masters/ColorMasterPage.jsx frontend/src/components/Masters/PurityMasterPage.jsx
```

Remove any found.

- [ ] **Step 3: Standardise import ordering in touched frontend files**

Import ordering standard for this project:

```js
// 1. React
import { useState, useEffect } from "react"

// 2. Third-party libraries
import { useNavigate } from "react-router-dom"

// 3. ShadCN UI components
import { Button } from "@/components/ui/button"

// 4. Shared ERP components
import { ConfirmDialog } from "@/components/common/ConfirmDialog"

// 5. Services / API
import { fetchColors } from "@/services/apiService"
// (or from domain module: import { fetchColors } from "@/services/api/masters")

// 6. Hooks / utilities
import { useToast } from "@/hooks/use-toast"
import { parseApiError } from "@/lib/utils"
```

- [ ] **Step 4: Verify build and commit**

```bash
cd frontend && npm run build 2>&1 | tail -5
git add frontend/src/services/api/ frontend/src/components/Masters/
git commit -m "chore(frontend): remove unused imports, standardise import ordering in touched files"
```

---

### Task 5.3: Orphaned file audit at `frontend/src/` root

**Files:** Review-only (no changes without confirmation)

Several `.jsx` files live at `frontend/src/` root rather than inside `components/`. Some may be unrouted.

- [ ] **Step 1: List root-level JSX files**

```bash
ls frontend/src/*.jsx frontend/src/*.js 2>/dev/null | grep -v "main\|App\|index"
```

- [ ] **Step 2: Check which are imported or routed**

```bash
# For each file found above, check if it's imported anywhere:
grep -rn "from.*src/Utils\|from.*src/table\|from.*src/dashboard" frontend/src/ --include="*.jsx" --include="*.js" | grep -v "node_modules"
```

Also check `App.jsx` for route registrations.

- [ ] **Step 3: Report findings**

Do not delete any file. Report to the user which files appear to be orphaned (not imported and not routed). The user will confirm before any deletion.

- [ ] **Step 4: Commit the audit report**

Create `docs/orphaned-files-audit-2026-05-07.md` listing each root-level file and its import status. Commit it for reference.

```bash
git add docs/orphaned-files-audit-2026-05-07.md
git commit -m "docs: orphaned frontend file audit results"
```

---

## Self-Review Checklist

- [x] Every backend task ends with `python manage.py check`
- [x] Every frontend task ends with `npm run build`
- [x] Barrel `__init__.py` / `apiService.js` barrel documented with exact content
- [x] Duplicate class removals explicitly called out (JournalEntryViewSet ×2, PnlGroupLedgersView ×2, PnlLedgerTransactionsView ×2)
- [x] `fetchPurhcaseItemsForBarcode` typo preserved — do not rename
- [x] Relative import depth change documented (`from .models` → `from ..models`)
- [x] Phase 4 depends on Phase 1 — noted in task header
- [x] Phase 5 runs last — noted in plan header
- [x] No business logic changes in any task
- [x] No forced mass-migration of existing components (only ColorMaster + PurityMaster as reference implementations)
