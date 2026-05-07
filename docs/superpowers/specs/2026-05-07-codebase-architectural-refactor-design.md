# Codebase Architectural Refactor — Design Spec
**Date:** 2026-05-07  
**Project:** Jewel India ERP  
**Approach:** Structural Spine (Approach A)  
**Risk level:** Near-zero to Low (no logic changes, only organization)  
**Test coverage:** Manual testing only  
**Status:** Active development (not live production)

---

## Goal

Make the codebase look and feel like it was built by a single senior engineering team. A senior Django or React engineer opening any file should see clean structure, predictable patterns, and professional organization — not a mess of god files and copy-paste code.

No business logic is changed. All refactors are organizational.

---

## Constraints

- No automated test suite — manual testing is the only safety net
- Active development environment (not live production)
- Zero breaking changes required — all existing imports and URL routes must keep working
- Business logic, signals, and transaction handling are out of scope

---

## Phase 1 — Backend God-File Split

### Problem
`accounting/views.py` (3,254 lines) and `sales/views.py` (2,916 lines) are unnavigable god files. `purchase/serializer.py` (1,157 lines) has the same issue. A senior engineer cannot reason about file responsibility or safely make changes.

### Technique
Convert each god file into a Python package using the **barrel re-import pattern**. The original filename becomes a package directory with an `__init__.py` that re-imports everything from sub-modules. Django's URL routing imports continue to resolve without any change.

### Target files and proposed splits

**`accounting/views.py` → `accounting/views/`**
```
accounting/views/
  __init__.py      ← from .vouchers import *; from .ledger import *; etc.
  vouchers.py      ← JournalEntryViewSet, PaymentViewSet, ReceiptViewSet, ContraViewSet
  ledger.py        ← LedgerViewSet, ChartOfAccountsView, BalanceViews
  reports.py       ← TrialBalanceView, DayBookView, ProfitLossView, BalanceSheetView
  opening.py       ← OpeningBalanceViewSet
```

**`sales/views.py` → `sales/views/`**
```
sales/views/
  __init__.py      ← barrel re-import
  invoice.py       ← SalesInvoiceViewSet and related invoice views
  returns.py       ← SalesReturnViewSet and return-related views
  reports.py       ← sales reports, GST output, summaries
```

**`purchase/serializer.py` → `purchase/serializers/`**
```
purchase/serializers/
  __init__.py      ← barrel re-import
  voucher.py       ← PurchaseVoucherSerializer, PurchaseVoucherPostSerializer
  order.py         ← PurchaseOrderSerializer and related
  return_.py       ← PurchaseReturnSerializer and related
```

### Safety
- `__init__.py` barrel re-imports preserve all existing `from accounting.views import X` statements
- URL conf files are not touched
- No logic moves between files — only physical file reorganization

### Definition of done
- All apps start cleanly with `python manage.py check`
- All existing URL routes resolve correctly
- Each sub-module file has one clear domain of responsibility (no mixed concerns)

---

## Phase 2 — Frontend API Service Split

### Problem
`frontend/src/services/apiService.js` is 6,133 lines with 565 named exports. It is the single most jarring file in the frontend. Every API call for every domain lives in one flat, unsearchable list.

### Technique
**Domain module extraction with barrel re-export.** Each domain gets its own module under `services/api/`. The original `apiService.js` becomes a 15-line barrel that re-exports everything. All existing imports across the codebase keep working without any changes.

### Target structure
```
services/
  apiClient.js          ← unchanged (axios instance + interceptors)
  api/
    accounting.js       ← vouchers (journal, payment, receipt, contra), ledger, reports
    sales.js            ← invoices, returns, POS, quotations
    purchase.js         ← vouchers, orders, returns
    inventory.js        ← barcodes, stock journals, inter-retail transfers, RFID
    masters.js          ← items, purity, shape, color, retail, company, HSN, karigar
    contacts.js         ← customers, ledgers, CRM, whatsapp
    goldscheme.js       ← enrollments, payments, maturity, overdue
    goldrates.js        ← rates CRUD
    hr.js               ← employees, payroll, salary slips, leave, IT blocks
    fixedAssets.js      ← assets, depreciation suggestions, FA settings
    userauth.js         ← login, users, roles, permissions, system settings
    reports.js          ← closing stock, GST registers, carry forward, opening inventory
    vendorAnalytics.js  ← dashboard, stock ageing, design performance, comparisons
  apiService.js         ← BECOMES: export * from './api/accounting'; (×13 lines)
```

### Import compatibility
```js
// All existing imports keep working — no component changes needed:
import { fetchSalesInvoices } from "@/services/apiService";   // ✓ still works

// New code can import directly from domain module:
import { fetchSalesInvoices } from "@/services/api/sales";    // ✓ preferred going forward
```

### Definition of done
- All existing components build and run without import errors
- Each domain module is independently readable
- `apiService.js` is ≤ 20 lines (barrel only)
- No domain module exceeds 400 lines

---

## Phase 3 — Shared Frontend Component Library

### Problem
The same UI scaffolding — table with search + pagination, delete confirm dialog, page header with action button, add/edit form sheet — is copy-pasted 20+ times across Masters, GoldScheme, HR, and other module pages. Every copy looks slightly different.

### New shared components

Location: `frontend/src/components/common/`

#### `DataTable.jsx`
Standard ERP data table wrapping ShadCN Table + TanStack. Consistent: search input, column sorting, pagination controls, loading skeleton, empty state message.

```jsx
// Props
<DataTable
  columns={columns}
  data={data}
  isLoading={isLoading}
  searchPlaceholder="Search items..."
  filters={optionalFilterControls}    // optional
  onRowClick={handler}                // optional
/>
```

#### `ConfirmDialog.jsx`
Delete/irreversible-action confirmation modal used universally instead of inline AlertDialog implementations.

```jsx
<ConfirmDialog
  open={open}
  title="Delete Item"
  description="This action cannot be undone."
  confirmLabel="Delete"          // default
  variant="destructive"          // default
  onConfirm={handleDelete}
  onCancel={() => setOpen(false)}
/>
```

#### `PageHeader.jsx`
Consistent page title + optional action button row used at the top of every list/master page.

```jsx
<PageHeader
  title="Item Master"
  subtitle="Manage your inventory items"   // optional
  action={<Button onClick={openForm}>Add Item</Button>}  // optional
/>
```

#### `FormSheet.jsx`
Standardized ShadCN Sheet wrapper for add/edit forms — consistent header, scrollable content area, sticky footer with Save/Cancel buttons.

```jsx
<FormSheet
  open={open}
  onClose={handleClose}
  title="Add Item"
  onSubmit={handleSubmit}
  isSubmitting={isSubmitting}
>
  {/* form fields */}
</FormSheet>
```

### Migration strategy
- No forced mass-migration of existing components
- The 3–4 most duplicated Masters pages are migrated as part of this phase to demonstrate the pattern and validate the components
- All future development uses shared components by default
- Existing components are migrated opportunistically when touched for feature work

### Definition of done
- All 4 components exist in `components/common/` with consistent prop APIs
- At least 3 Masters pages migrated as reference implementations
- Each shared component handles loading, empty, and error states

---

## Phase 4 — Backend Base Class Audit & Duplicate Fix

### Problem
1. `RetailBaseViewset` already exists in `mastersconfig` but is inconsistently applied — some viewsets bypass it and reimplement retail scoping manually.
2. `JournalEntryViewSet` is defined twice in `accounting/views.py` (lines ~1249 and ~1251). The second definition silently overrides the first — a genuine bug.
3. Serializer error responses have inconsistent shapes across apps, making frontend error handling unpredictable.

### Fixes

**1. RetailBaseViewset audit**
- Identify all viewsets that should inherit from `RetailBaseViewset` but do not
- Migrate them — this is a one-line change per viewset (`class X(RetailBaseViewSet)`)
- No logic changes; the base class already implements the correct behavior

**2. JournalEntryViewSet duplicate**
- Remove the duplicate class during the Phase 1 god-file split
- Verify which version contains the correct, complete implementation before deleting

**3. Serializer error standardization**
- Audit serializers in `accounting` and `purchase` for inconsistent error response shapes
- Document the existing dominant pattern (most common shape already in the codebase)
- Add a note to `common/serializers.py` establishing the standard pattern for future serializers
- Full enforcement is a follow-on effort; this phase establishes the documented standard

### Out of scope
Business logic, signals, managers, transaction handling, custom querysets.

### Definition of done
- Zero duplicate class definitions in the codebase
- All viewsets that use retail-scoped data inherit from `RetailBaseViewset`
- `python manage.py check` passes cleanly

---

## Phase 5 — Dead Code & Import Cleanup

### Problem
Accumulated development leaves unused imports, debug `console.log` statements, commented-out code blocks, and inconsistent import ordering visible in every file. These are low-effort, high-signal improvements.

### Backend cleanup (applied to every file touched in Phases 1–4)
- Remove unused imports
- Remove commented-out code blocks
- Standardize import ordering: `stdlib → Django → third-party → local app`
- Remove any `print()` debug statements

### Frontend cleanup (applied to every file touched in Phases 2–3)
- Remove unused imports (React, icons, hooks, components)
- Remove `console.log` debug statements
- Standardize import ordering: `React → third-party → ShadCN/ui → services → local components`
- Identify and flag orphaned `.jsx` files at `src/` root that are no longer routed or imported

### Orphaned file audit
A targeted review of files at `frontend/src/` root level (not inside `components/`) to identify any that are no longer imported anywhere. Flag for user confirmation before deletion.

### Scope limit
Cleanup is applied to every touched file, plus a targeted pass on the largest and most visible files. This is not a full lint sweep of every file in the project.

### Definition of done
- No unused imports in any file touched during this refactor
- No `console.log` or `print()` debug statements in touched files
- Import ordering is consistent in all touched files

---

## Implementation Order

Phases are ordered by safety and dependency:

| Phase | Dependency | Why this order |
|---|---|---|
| 1 — Backend god-file split | None | Pure reorganization, zero risk, unblocks Phase 4 |
| 2 — Frontend API split | None | Pure reorganization, zero risk, can run in parallel with Phase 1 |
| 3 — Shared component library | None | Independent; can run in parallel with Phases 1–2 |
| 4 — Backend base class audit | Phase 1 (cleaner files to work in) | Small targeted changes |
| 5 — Dead code cleanup | Phases 1–4 | Applied throughout, finalized last |

---

## What is Explicitly Out of Scope

- Business logic changes
- Database query optimization (N+1, select_related)
- Performance profiling or caching
- Full test suite creation
- Global migration of all existing components to shared library
- React Query / data fetching pattern migration
- State management refactoring beyond what's touched in Phase 3

These are valid follow-on efforts but are excluded from this refactor to keep the risk surface small and the scope deliverable.

---

## Success Criteria

A senior Django or React engineer can:
1. Open any backend app and understand file responsibility in under 10 seconds
2. Find any API function in under 5 seconds by navigating to the correct domain module
3. Add a new master page using shared components without writing boilerplate
4. Read any touched file without seeing unused imports, debug logs, or dead code

The codebase feels like it was designed with intention.
