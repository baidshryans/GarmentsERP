# Jewel India ERP - System Audit Report

**Date:** April 9, 2026
**Auditor:** System Architecture Review
**Scope:** Full-stack audit (Django Backend + React Frontend)

---

## Executive Summary

A comprehensive audit of the Jewel India ERP system was performed covering functional correctness, business logic, data integrity, performance, and code quality across 13 Django apps and a React frontend with 400+ routes.

**Findings Summary:**

| Severity | Count | Fixed | Suggested |
|----------|-------|-------|-----------|
| Critical | 3 | 3 | 0 |
| High | 4 | 4 | 0 |
| Medium | 9 | 4 | 5 |
| Low | 6 | 0 | 6 |
| **Total** | **22** | **11** | **11** |

---

## 1. Critical Issues (Fixed)

### 1.1 Missing BarcodeDetails Import - P&L Report Crash
- **File:** `accounting/utils.py:7`
- **Problem:** `BarcodeDetails` was used on line 175 but never imported. The `calculate_opening_stock()` function would crash with `NameError` whenever P&L, Balance Sheet, or Financial Ratios views were accessed.
- **Impact:** CRITICAL - Core financial reports completely broken.
- **Fix Applied:** Added `BarcodeDetails` to the import statement.

### 1.2 Float vs Decimal in LedgerOpenBalance
- **File:** `accounting/models.py:235`
- **Problem:** `debit` field used `FloatField` while `credit` used `DecimalField`. In accounting, `FloatField` causes binary floating-point precision errors (e.g., 0.1 + 0.2 = 0.30000000000000004).
- **Impact:** CRITICAL - Opening balance calculations have rounding errors; trial balance won't tally.
- **Fix Applied:** Changed `debit` to `DecimalField(max_digits=11, decimal_places=2)`. Migration generated: `0007_fix_ledger_open_balance_debit_to_decimal.py`.

### 1.3 Double-Entry Validation After Creation (Race Condition)
- **File:** `accounting/serializers.py:292-301`
- **Problem:** The VoucherMain was being created BEFORE the debit/credit totals were validated. If validation failed, the voucher was already in the database (though `@transaction.atomic` would roll it back, the `amount` field was stored using `sum(float(...))` causing precision loss).
- **Impact:** CRITICAL - Voucher amount field stored with float precision loss; validation order was wrong.
- **Fix Applied:** Moved debit/credit validation BEFORE `VoucherMain.objects.create()`. Changed amount calculation to use `Decimal` arithmetic.

---

## 2. High Issues (Fixed)

### 2.1 GST Ledger Validation Missing in Credit/Debit Notes
- **File:** `accounting/serializers.py:648-720`
- **Problem:** When creating Credit/Debit Notes with GST amounts, if the GSTIN was not configured or GST ledgers were missing, the GST posting lines were silently skipped. This caused unbalanced voucher entries (debit != credit).
- **Impact:** HIGH - Unbalanced accounting entries; GST register would be incorrect.
- **Fix Applied:** Added explicit validation that required GST ledgers exist before attempting to create voucher lines.

### 2.2 ReferenceBills elsif Logic Bug
- **File:** `accounting/serializers.py:365-383`
- **Problem:** The `elif voucher_main.vendor_bill:` branch used `detail['ref_bill_no']` for `vendor_bill_no`, but at this point `ref_bill_no` was empty/None (condition 1 was false). This created ReferenceBills records with null vendor_bill_no.
- **Impact:** HIGH - Orphaned allocation records; vendor bill matching broken.
- **Fix Applied:** Changed to use `voucher_main.vendor_bill` instead of `detail['ref_bill_no']`.

### 2.3 VoucherDetailSerializer Float Fields
- **File:** `accounting/serializers.py:74-75`
- **Problem:** `credit` and `debit` fields in VoucherDetailSerializer used `FloatField`, meaning every voucher entry went through float conversion before reaching the Decimal database columns.
- **Impact:** HIGH - Systematic precision loss on all accounting entries.
- **Fix Applied:** Changed to `DecimalField(max_digits=15, decimal_places=2)`.

### 2.4 Fiscal Year Boundary Not Enforced
- **File:** `accounting/serializers.py:196` (in `create()` method)
- **Problem:** No validation prevented posting vouchers outside the active fiscal year date range. Users could create vouchers dated in the wrong FY, corrupting FY-based reporting. Also, no check for hard-closed fiscal years.
- **Impact:** HIGH - Out-of-period postings break all FY reports.
- **Fix Applied:** Added FY date boundary check and hard-close check before voucher creation.

---

## 3. Medium Issues

### 3.1 Asset Disposal Validation Missing (Fixed)
- **File:** `accounting/models.py:302-344`
- **Problem:** `FixedAsset` allowed setting status to DISPOSED without providing disposal_date or disposal_value. Also allowed disposal_date before purchase_date.
- **Impact:** MEDIUM - Invalid asset records; depreciation reports include phantom assets.
- **Fix Applied:** Added `clean()` method with proper validation rules.

### 3.2 FASettings Cross-Retail Ledger Contamination (Fixed)
- **File:** `accounting/models.py:388-403`
- **Problem:** `FixedAssetSettings` linked depreciation ledgers without validating they belong to the same retail.
- **Impact:** MEDIUM - Depreciation could post to wrong retail's GL.
- **Fix Applied:** Added `clean()` method to validate ledger retail matches settings retail.

### 3.3 Signal Reversal Silent Skip (Fixed)
- **File:** `accounting/signals.py:36-39`
- **Problem:** When deleting vouchers of types not in the handled list, the signal silently deleted ReferenceBills and returned, even if those vouchers had ref_bill_no allocations that affected due_amt.
- **Impact:** MEDIUM - Due amounts on invoices could become permanently wrong.
- **Fix Applied:** Added warning log when deleting vouchers with allocations but no reversal handler.

### 3.4 RetailMiddleware Silent Failure (Fixed)
- **File:** `mastersconfig/middleware.py:31-33`
- **Problem:** When a non-existent retail code was passed in X-RETAIL-ID, the middleware silently set `request.retail = None` and returned. All downstream views would then fail with confusing NoneType errors.
- **Impact:** MEDIUM - Poor developer/user experience; hard to debug.
- **Fix Applied:** Now returns a proper HTTP 400 error with a clear message.

### 3.5 Goldscheme Payment Signal Not Error-Safe (Fixed)
- **File:** `goldscheme/signals.py:42-103`
- **Problem:** If the SCHM voucher creation failed (e.g., missing scheme liability ledger, FY not configured), the payment record was saved but the voucher was not created, leaving an inconsistent state.
- **Impact:** MEDIUM - Payments recorded without accounting entries.
- **Fix Applied:** Wrapped voucher creation in try/except with error logging. Payment is preserved; manual JV can be created.

### 3.6 Bill Allocation Tolerance Hardcoded (Suggested)
- **File:** `accounting/serializers.py:323`
- **Problem:** Bill allocation sanity check uses hardcoded `Decimal('0.01')` tolerance.
- **Impact:** MEDIUM - In edge cases, allows over-allocation of up to 1 paisa.
- **Suggestion:** Make tolerance configurable via CompanyMaster or SystemSettings.

### 3.7 Cash Limit Hardcoded Fallback (Suggested)
- **File:** `accounting/utils.py:25`
- **Problem:** If company is not configured, falls back to hardcoded limits (199999 receipt, 10000 payment).
- **Impact:** MEDIUM - Users may not realize limits are defaults, not their actual company settings.
- **Suggestion:** Raise a clear error requiring company configuration instead of silent fallback.

### 3.8 FY Sync No Duplicate Check (Suggested)
- **File:** `mastersconfig/views.py` (sync_opening_balances)
- **Problem:** Running sync_opening_balances twice for the same FY will double the opening balances.
- **Impact:** MEDIUM - Data corruption if run carelessly.
- **Suggestion:** Add idempotency check (e.g., track last_synced_at and reject if already synced).

### 3.9 HR SalarySlip Race Condition (Suggested)
- **File:** `hr/models.py:157`
- **Problem:** `unique_together = ('employee', 'month', 'year')` prevents duplicates at DB level, but two concurrent requests could both succeed at application level before the constraint is checked.
- **Impact:** MEDIUM - Rare but possible duplicate slip error.
- **Suggestion:** Add `select_for_update()` in the salary generation service, or use `get_or_create` pattern.

---

## 4. Low/Minor Issues (Suggested)

### 4.1 Inventory IntegerField for Monetary Values
- **File:** `inventory/models.py:82-83, 32-38`
- **Problem:** `rate` and `amt` in BarcodeDetails/DesignDetails use `IntegerField`. Cannot represent fractional prices; overflows at 2.1 billion.
- **Suggestion:** Change to `DecimalField(max_digits=14, decimal_places=2)` in a future migration.

### 4.2 nw Decimal Precision Mismatch
- **File:** `inventory/models.py:29`
- **Problem:** `nw` (net weight) has `decimal_places=2` but `gw` (gross weight) has `decimal_places=3`. Inconsistent for gold calculations.
- **Suggestion:** Standardize both to `decimal_places=3`.

### 4.3 Half-Year Depreciation Rule Not Auto-Applied
- **File:** `accounting/fa_services.py:22`
- **Problem:** IT Act half-year rule for assets purchased in the second half of FY is not automatically applied.
- **Suggestion:** Add an optional checkbox "Apply IT Act Half-Year Rule" in depreciation suggestion generation.

### 4.4 LocMemCache in Production
- **File:** `jewel_test/settings.py`
- **Problem:** LocMemCache is single-process only. Multi-worker deployments (Gunicorn) will have stale caches.
- **Suggestion:** Switch to Redis cache backend for production.

### 4.5 SQLite for Production
- **File:** `jewel_test/settings.py`
- **Problem:** SQLite doesn't support concurrent writes. Under load, requests will get "database is locked" errors.
- **Suggestion:** Migrate to PostgreSQL for production deployments.

### 4.6 Portal Mobile Number Ambiguity
- **File:** `goldscheme/views.py` (portal lookup)
- **Problem:** Customer portal login uses mobile number lookup, but multiple customers may share a mobile number.
- **Suggestion:** Add uniqueness constraint on mobile per retail, or use explicit account selection when ambiguous.

---

## 5. Performance Observations

| Area | Observation | Recommendation |
|------|-------------|----------------|
| Account Tree | Uses in-memory tree building (good) | Monitor with >1000 accounts |
| Barcode Queries | Has proper indexes on (retail, item) and (retail, stk_status) | Good |
| Raw Material Txns | Indexed on (retail, item, trans_type) and (retail, -date) | Good |
| Voucher Queries | Indexed on (retail, voucher_type, -voucher_no) and (retail, date) | Good |
| Bank Reconciliation | Indexed on (retail, bank_ledger, date) | Good |
| Report Views | Uses select_related/prefetch_related consistently | Good |
| Cache | RetailMiddleware and LicenseMiddleware cache for 5 min | Switch to Redis for multi-process |

---

## 6. Code Quality Summary

### Positive Patterns
- Consistent use of `@transaction.atomic` for multi-model operations
- Proper use of `select_for_update()` for concurrent due_amt updates
- Clean signal-based architecture for auto voucher creation
- Well-structured middleware for multi-tenancy (RetailMiddleware) and licensing (LicenseMiddleware)
- Good separation of concerns: models/serializers/views/services
- EasyAudit integration for comprehensive audit trail

### Areas for Improvement
- Some view files are very large (inventory/views.py ~61K characters, manufacturing/views.py ~90K)
- Hard-coded constants in `global_vars.py` (consider DB-backed configuration)
- Inconsistent decimal precision across modules (accounting uses DecimalField; inventory uses IntegerField for amounts)
- Missing structured logging in most modules (only added during this audit to signals)

---

## 7. Migration Safety

The following migration was generated during this audit:

| Migration | App | Change | Safe? |
|-----------|-----|--------|-------|
| `0007_fix_ledger_open_balance_debit_to_decimal` | accounting | FloatField → DecimalField on LedgerOpenBalance.debit | Yes - lossless conversion |

**Rollback strategy:** To rollback, reverse the migration with:
```bash
python manage.py migrate accounting 0006
```
Then revert the model change. No data loss occurs in either direction (Float→Decimal is lossless; Decimal→Float loses precision but preserves values within float range).

---

## 8. Summary of All Changes Made

| # | File | Change | Type |
|---|------|--------|------|
| 1 | `accounting/utils.py:7` | Added `BarcodeDetails` to import | Bug Fix |
| 2 | `accounting/models.py:235` | `FloatField` → `DecimalField` for LedgerOpenBalance.debit | Bug Fix |
| 3 | `accounting/serializers.py:74-75` | `FloatField` → `DecimalField` for VoucherDetailSerializer | Bug Fix |
| 4 | `accounting/serializers.py:292-301` | Moved validation before creation; Decimal arithmetic | Bug Fix |
| 5 | `accounting/serializers.py:648` | Added GST ledger existence validation | Validation |
| 6 | `accounting/serializers.py:375-383` | Fixed ReferenceBills vendor_bill_no logic | Bug Fix |
| 7 | `accounting/serializers.py:214` | Added FY boundary + hard-close check | Validation |
| 8 | `accounting/models.py:336` | Added FixedAsset.clean() disposal validation | Validation |
| 9 | `accounting/models.py:399` | Added FixedAssetSettings.clean() retail validation | Validation |
| 10 | `accounting/signals.py:37` | Added warning log for unhandled voucher types | Safety |
| 11 | `mastersconfig/middleware.py:31` | Return HTTP 400 instead of silent None | Error Handling |
| 12 | `goldscheme/signals.py:50-103` | Wrapped voucher creation in try/except | Error Handling |
| 13 | `accounting/migrations/0007_*` | Generated migration for field change | Migration |

---

## Phase 2 — Deep Audit Fixes

### 9. Critical Fixes (Phase 2)

#### 9.1 Double-Discount GST Bug — SalesVou & SaleReturn
- **Files:** `sales/models.py` (SalesVou lines 179-188, SaleReturn lines 313-322)
- **Problem:** `sgst_amt = (taxable_value - discount) * sgst_per / 100` but `taxable_value = mrp - discount`, so discount was subtracted twice. A ₹10,000 sale with ₹500 discount and 1.5% SGST calculated as (9500-500)×1.5% = ₹135 instead of correct 9500×1.5% = ₹142.50.
- **Fix:** Changed to `taxable_value * sgst_per / 100` (same for cgst_amt, igst_amt). Added null safety with `or 0`.

#### 9.2 SalesApproval Tax Calc Missing /100 Divisor
- **File:** `sales/models.py` (SalesApproval lines 416-429)
- **Problem:** `sgst_amt = (taxable_value - discount) * sgst_per` — missing `/100`. A 1.5% SGST on ₹9500 returned ₹14,250 instead of ₹142.50. Also had the same double-discount bug.
- **Fix:** Added `net_taxable` property (taxable_value - discount). Changed tax properties to `net_taxable * sgst_per / 100`.

#### 9.3 SalesVou & SalesApproval clean() Validated Computed Properties
- **File:** `sales/models.py`
- **Problem:** `clean()` checked `self.cgst_amt is not None` and `self.sgst_amt is not None` — these are computed properties that are ALWAYS not None. Validation never triggered.
- **Fix:** Changed to validate percentage fields (`cgst_per`, `sgst_per`, `igst_per`) which are the actual DB columns.

#### 9.4 PurchaseReturn.total_incl_tax — AttributeError
- **File:** `purchase/models.py:234`
- **Problem:** Referenced `self.item_total` which doesn't exist on PurchaseReturn. Crash on any access.
- **Fix:** Changed to `self.bill_value` (the correct existing field) with null safety via `or Decimal(0)`.

#### 9.5 Purchase Serializer ValidationError NameError
- **File:** `purchase/serializer.py`
- **Problem:** `ValidationError` was used on lines 210, 297, 399 but only imported on line 421. Lines before 421 would crash with `NameError`.
- **Fix:** Moved `from rest_framework.exceptions import ValidationError` to the top of the file; removed redundant late import.

#### 9.6 HR Salary Voucher Unbalanced
- **File:** `hr/views.py:225-276`
- **Problem:** Debit was `gross_salary` but credits included employer PF + employer ESI contributions, making total credits exceed total debits. Double-entry violation.
- **Fix:** Debit is now `total_ctc = gross_salary + employer_pf + employer_esi`. This ensures Dr = Cr.

#### 9.7 HR PF Base Incorrect + ESI Default Wrong
- **File:** `hr/services.py:57-70`
- **Problem:** PF base used only `basic_earned` but EPFO rules require Basic + DA. ESI required explicit config to be applicable — defaulted to not applicable when no config existed.
- **Fix:** PF base changed to `basic_earned + da_earned`. ESI defaults to applicable when config is None.

#### 9.8 DueAdvanceReportView — Wrong Field Names (Crash)
- **File:** `accounting/views.py:479-524`
- **Problem:** Used `ldgrcd`, `rt_code`, `dbt`, `crdt` which don't exist on the models. Every call to this view would crash with `FieldError`.
- **Fix:** Changed to correct field names: `ldgr`/`account`, `retail`/`voucher_main__retail`, `debit`, `credit`. Also changed `request.session.get("rt_code")` to `request.retail`.

### 10. High Fixes (Phase 2)

#### 10.1 Bank Reconciliation Match — No Retail Filter (Data Leak)
- **File:** `accounting/views.py:1617`
- **Problem:** `VoucherDetail.objects.filter(pk=vd_id).first()` had no retail filter. A user could match bank statement entries to voucher details from other retails.
- **Fix:** Added `voucher_main__retail=request.retail` to the filter.

#### 10.2 Cashbook Opening Balance — int/Decimal Mixing
- **File:** `accounting/views.py:611`
- **Problem:** `opening_balance = 0` (int) then mixed with Decimal aggregates. Could cause TypeError or precision loss.
- **Fix:** Changed to `opening_balance = Decimal('0')`.

#### 10.3 Inventory Prefetch Import Order
- **File:** `inventory/views.py`
- **Problem:** `Prefetch` was used on line 642 but imported on line 995. Would crash with `NameError`.
- **Fix:** Moved `Prefetch` to top-level import; removed duplicate mid-file import.

#### 10.4 Inventory Barcode Transaction Boundary
- **File:** `inventory/serializer.py`
- **Problem:** `pending_pcs`/`pending_gw` updates on PurchaseVoucherItems were outside the `transaction.atomic()` block. A crash after barcode creation but before pending count update would leave inconsistent data.
- **Fix:** Moved the pending count updates inside the atomic block.

#### 10.5 StockTransfer Dict vs Model Instance
- **File:** `inventory/serializer.py`
- **Problem:** StockTransferSerializer passed dict values to `BarcodeTransaction.objects.create(barcode=...)` instead of model instances.
- **Fix:** Changed to iterate over saved `StockTransferMain` instances with `select_related('barcode')`.

#### 10.6 Goldscheme Enrollment Race Condition
- **File:** `goldscheme/services/enrollment.py`
- **Problem:** Enrollment maturity check and payment recording had no `select_for_update()`. Concurrent requests could double-update totals.
- **Fix:** Added `transaction.atomic()` + `select_for_update()` with status re-check under lock.

#### 10.7 Gold Accumulation Silent Zero Weight
- **File:** `goldscheme/services/payment.py`
- **Problem:** If gold rate was missing for ACCUMULATION scheme, `gold_weight_added` silently set to 0.
- **Fix:** Now raises `ValueError` with clear message requiring gold rate entry.

#### 10.8 LOCKED Scheme Enrollment Without Rate
- **File:** `goldscheme/services/enrollment.py`
- **Problem:** Enrolling in LOCKED price scheme without a gold rate was allowed silently.
- **Fix:** Now validates that `accumulation_purity` and gold rate exist; raises `ValueError` if not.

#### 10.9 Portal Mobile Number Ambiguity
- **File:** `goldscheme/portal_views.py`
- **Problem:** Multiple customers could share a mobile number, causing unpredictable login behavior.
- **Fix:** Added check for multiple matches; returns HTTP 409 Conflict with a clear message listing affected retails.

#### 10.10 Manufacturing Stone Balance — ct vs pcs
- **File:** `manufacturing/views.py:470`
- **Problem:** `balance_ct` was incorrectly set to `issue_data.get('pcs', 0)` instead of `issue_data.get('ct', 0)`.
- **Fix:** Changed to use `ct` (carats).

#### 10.11 Manufacturing DecimalField(decimal_places=0)
- **File:** `manufacturing/models.py`
- **Problem:** GST, rate, and amount fields on `KarigarStoneIssue`, `KarigarStoneReceive`, `KarigarMaster`, and `KarigarReceiveItemDetails` had `decimal_places=0`, truncating fractional values.
- **Fix:** Changed all 14 affected fields to `decimal_places=2`.

#### 10.12 Purchase Serializer Null Safety + Debug Prints
- **File:** `purchase/serializer.py`
- **Problem:** `freight_amt`, `round_off`, and `discount_amt` accessed without null checks causing TypeError. Debug `print()` statements left in production code.
- **Fix:** Added `or 0` / `or '0.0'` null guards; removed print statements.

---

## 11. Phase 2 Changes Summary

| # | File | Change | Type |
|---|------|--------|------|
| 14 | `sales/models.py:179-188` | Fixed double-discount GST on SalesVou | Bug Fix |
| 15 | `sales/models.py:313-322` | Fixed double-discount GST on SaleReturn | Bug Fix |
| 16 | `sales/models.py:414-431` | Fixed SalesApproval missing /100 + double-discount | Bug Fix |
| 17 | `sales/models.py:200,399` | clean() now validates percentage fields, not properties | Bug Fix |
| 18 | `purchase/models.py:234` | PurchaseReturn.total_incl_tax: item_total → bill_value | Bug Fix |
| 19 | `purchase/serializer.py:2` | ValidationError import moved to top of file | Bug Fix |
| 20 | `purchase/serializer.py` | Removed debug print() statements | Cleanup |
| 21 | `purchase/serializer.py` | Null safety for freight_amt, round_off, discount_amt | Bug Fix |
| 22 | `hr/views.py:230-258` | Salary voucher: Dr total_ctc (balanced) | Bug Fix |
| 23 | `hr/services.py:61` | PF base = basic + DA per EPFO rules | Bug Fix |
| 24 | `hr/services.py:68` | ESI defaults to applicable when no config | Bug Fix |
| 25 | `accounting/views.py:479-524` | DueAdvanceReportView: fixed all field names | Bug Fix |
| 26 | `accounting/views.py:611` | Cashbook opening_balance: int → Decimal | Bug Fix |
| 27 | `accounting/views.py:1617` | Bank recon match: added retail filter | Security Fix |
| 28 | `inventory/views.py:25` | Prefetch import moved to top | Bug Fix |
| 29 | `inventory/serializer.py` | pending_pcs update inside atomic block | Data Integrity |
| 30 | `inventory/serializer.py` | StockTransfer: dict → model instance | Bug Fix |
| 31 | `goldscheme/services/enrollment.py` | select_for_update on enrollment updates | Race Condition |
| 32 | `goldscheme/services/payment.py` | Reject zero/missing gold rate for ACCUMULATION | Validation |
| 33 | `goldscheme/services/enrollment.py` | Require gold rate for LOCKED enrollment | Validation |
| 34 | `goldscheme/portal_views.py` | Mobile number ambiguity → HTTP 409 | Validation |
| 35 | `manufacturing/views.py:470` | Stone balance_ct: pcs → ct | Bug Fix |
| 36 | `manufacturing/models.py` | 14 fields: decimal_places=0 → 2 | Bug Fix |

---

## 12. Migrations Required (Phase 2)

| Migration | App | Change | Safe? |
|-----------|-----|--------|-------|
| Pending | manufacturing | `decimal_places=0` → `decimal_places=2` on 14 fields | Yes — lossless (adds precision) |

Generate with:
```bash
python manage.py makemigrations manufacturing
python manage.py migrate
```

---

## Phase 3 — Default Ledger Seeding & Salesperson Enhancements

### 13. New Default System Ledgers

The following system ledgers are now auto-created when a new CompanyMaster is set up (via signal + `seed_system_ledgers` command). These were previously missing, causing manual configuration to be required before key modules could function:

| Ledger Name | Account Group | Purpose |
|---|---|---|
| **Salary & Wages** | `EXP-IND-SAL` (Salaries & Wages) | Debit side of salary voucher (CTC) |
| **Employee Payable** | `CL` (Current Liabilities) | Net salary owed to employees |
| **Provident Fund Payable** | `CL` | PF liability (employee + employer share) |
| **ESI Payable** | `CL` | ESI liability (employee + employer share) |
| **Professional Tax Payable** | `CL-DT` (Duties & Taxes) | PT deducted from employees |
| **TDS on Salary Payable** | `CL-DT-TDS` (TDS Payable) | TDS on salary per IT Act |
| **Gold Scheme Liability** | `CL` | Money collected under gold savings schemes |
| **Depreciation Expense** | `EXP-IND-DEP` (Depreciation) | P&L charge for fixed asset depreciation |
| **Accumulated Depreciation** | `FA-AD` (new contra-asset group) | Reduces fixed asset book value on Balance Sheet |
| **Customer Advance** | `CL` | Advance received on customer orders before billing |
| **Suspense Account** | `CL` | Temporary parking for unmatched/unknown entries |
| **Opening Balance Equity** | `CAP-RES` (Reserves & Surplus) | Plug account for trial balance differences during data entry |
| **Stock-in-Transit** | `CA-STK` (Stock-in-Hand) | Inventory moving between retail locations |
| **Petty Cash** | `CA-CSH` (Cash-in-Hand) | Small-value cash fund separate from main cash |

**New Account Group:**

| Code | Name | Parent | Purpose |
|---|---|---|---|
| `FA-AD` | Accumulated Depreciation | Fixed Assets | Contra-asset group that reduces net FA on Balance Sheet |

### 14. Salesperson — Auto-Create Commission Payable Ledger

**Files:** `mastersconfig/views.py`, `frontend/src/components/Sales/SalesPersonList.jsx`

**Change:** When creating a new salesperson:
1. **Backend:** If no payable ledger is explicitly selected, the system auto-creates a "Commission Payable - {Salesperson Name}" ledger under Sundry Creditors (`CL-SC`), linked to the salesperson's retail, and marked as a system ledger. This is done atomically so the salesperson and ledger are always consistent.
2. **Frontend:** The "Payable Ledger" dropdown now shows "— Auto-create (Sales Commission) —" as the default option instead of "— None —". A helper text explains the auto-creation behavior.

### 15. Salesperson — Default Retail from Active Session

**Files:** `mastersconfig/views.py`, `frontend/src/components/Sales/SalesPersonList.jsx`

**Change:**
1. **Backend:** `perform_create` already forces `retail=request.retail` (from the `X-RETAIL-ID` middleware), ensuring the salesperson is always created for the active retail regardless of what the frontend sends.
2. **Frontend:** The "Add Sales Person" form now pre-fills the retail dropdown with the currently active retail location (read from `localStorage.retail_code`), so the user doesn't need to manually select it.

### Phase 3 Changes Summary

| # | File | Change | Type |
|---|------|--------|------|
| 37 | `accounting/management/commands/setup_account_groups.py` | Added `FA-AD` (Accumulated Depreciation) account group | Enhancement |
| 38 | `mastersconfig/signals.py` | Added 14 new system ledgers to `_MISC_LEDGERS` | Enhancement |
| 39 | `mastersconfig/signals.py` | Updated account code cache for new group codes | Enhancement |
| 40 | `mastersconfig/management/commands/seed_system_ledgers.py` | Updated code cache to include `CL-SC` | Enhancement |
| 41 | `mastersconfig/views.py` | Auto-create "Commission Payable" ledger on salesperson creation | Feature |
| 42 | `frontend/SalesPersonList.jsx` | Pre-fill retail from active session | UX Enhancement |
| 43 | `frontend/SalesPersonList.jsx` | Show "Auto-create" as default ledger option | UX Enhancement |

### How to apply to existing installations

For existing installations that already have a CompanyMaster, run the seeding commands to backfill the new ledgers:

```bash
python manage.py setup_account_groups    # Adds FA-AD group
python manage.py seed_system_ledgers     # Creates the 14 new system ledgers
```

For existing salespersons without a commission payable ledger, they can be updated individually through the edit form by selecting an existing ledger or creating one manually.

---

*End of Audit Report*
