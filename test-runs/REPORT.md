# Jewel India ERP — Smoke Test Report
**Date:** 2026-04-15
**Tooling:** Playwright (chromium, headless) → 191 static routes navigated as `admin`.
**Servers:** Django backend on `:8000` (SQLite), Vite frontend on `127.0.0.1:4321`.
**Result:** **168 PASS / 23 FAIL** (87.96% pass).

> Per-route logs: `test-runs/smoke_log.txt`
> Raw JSON: `test-runs/smoke_results.json`
> Failure screenshots: `test-runs/screenshots/*.png`

---

## Summary by category

| Category | Count | Severity | Notes |
|---|---|---|---|
| `database is locked` (SQLite) | 12 | 🔴 High | Every voucher "next number" endpoint fails under concurrent reads. Root cause: SQLite + write contention. |
| HTTP 500 (backend exception) | 4 | 🔴 High | Real server-side bugs. |
| HTTP 404 (missing endpoint) | 1 | 🟠 Med | Frontend calls a route that doesn't exist. |
| HTTP 401 (auth) | 1 | 🟠 Med | Token not being sent or scope wrong. |
| JS reference / type errors | 3 | 🔴 High | `items.map is not a function`, `fetchPackets is not defined`. |
| React DOM-nesting / key warnings | 2 | 🟡 Low | Cosmetic; non-blocking. |

---

## Critical: SQLite "database is locked" (12 routes)

The next-document-number endpoints raise `OperationalError: database is locked` whenever multiple requests touch them around the same time. SQLite serialises writers; opening a `/add` page issues several parallel API calls and at least one collides.

Affected endpoints:
- `inventory/api/next_stock_journal_no`
- `manufacturing/api/next_assay_iss_no`
- `manufacturing/api/karigar-gold-issue/bill-no`
- `manufacturing/api/next_hmis_no`
- `manufacturing/api/next_melt_iss_no`
- `manufacturing/api/next_ref_iss_no`
- `manufacturing/api/next-stone-bill-no/`
- `manufacturing/api/next_assay_rec_no`
- `manufacturing/api/next_hmrec_no`
- `manufacturing/api/karigar-receive-slip-no/`
- `manufacturing/api/next_ref_rec_no`
- (plus `stonereturn/add`)

**Fixes (in priority order):**
1. Wrap each "next number" view in a `transaction.atomic()` + `select_for_update()` (or use `SQLITE_BUSY_TIMEOUT`).
2. In `settings.py` → `DATABASES['default']['OPTIONS'] = {'timeout': 20}` for SQLite to retry instead of failing instantly.
3. Long term: move dev/prod off SQLite (Postgres/MySQL) for any multi-user ERP — SQLite single-writer will keep biting.

---

## Critical: Backend HTTP 500s

| Route | Endpoint | Notes |
|---|---|---|
| `inventory/reports/stockvalue` | `inventory/api/stock-valuation-report/` | 500 on bare GET. Check view logs. |
| `manufacturing/issue/jobwork/add` | `manufacturing/api/next-slip-no/` | Likely the same SQLite issue, different code path. |
| `manufacturing/repair/new` | `manufacturing/api/repair-job-card-no/` | 500. |
| `sales/quotation/add/` | `sales/api/quotation-initial-data/` | 500 on a form-init aggregate endpoint. |

**Action:** Run with `DEBUG=True` and reproduce each — the response body already contains a Django traceback (visible in console logs). Quick win to fix.

---

## Critical: Frontend JS errors

| Route | Error | Likely cause |
|---|---|---|
| `inventory/barcode-bulk` | `items.map is not a function` (×3) in `BarcodeBulkOps.jsx:144` | API returned `{}` or paginated `{results:[…]}` instead of an array. Add `Array.isArray(data) ? data : data.results || []`. |
| `inventory/reports/raw-material` | Same `items.map` in `RawMaterialBalanceReport.jsx:66` | Same fix. |
| `inventory/stocktransfer/add` | `fetchPackets is not defined` | Function referenced but never declared/imported. |

---

## HTTP 404 / 401

- `inventory/reports/idgen` → `GET /auth/api/users/?page_size=500` returns **404**. Endpoint moved or renamed (probably should be `userauth/api/users/`).
- `accounting/profitdemo` → `accounting/api/pnl` returns **401**. Either the endpoint expects a permission this admin lacks, or token is not attached for this specific call. (Dead/demo route — consider deleting.)

---

## React warnings (low severity)

- `inventory/barcodemanagement/merge/` — `<h6>` rendered inside `<tbody>` (invalid HTML).
- `purchase/purchaseorder/list/add` — duplicate `key` prop on list children.
- `inventory/reports/stockvalue` — duplicate `key` warning.

---

## Routes covered

All 191 static routes from `App.jsx` were exercised. Parameterised routes (`:id`, `*`) were skipped — they require valid IDs from the dev DB.

The **168 passing routes** rendered without console errors, page errors, or 4xx/5xx API responses. That includes the entire CRM, masters, sales (list + add for vouchers/returns/approvals), HR, fixed assets, gold scheme, accounting reports/vouchers, and most of inventory/manufacturing list pages.

---

## Form requirements (auto-discovered)

Inspected 34 `/add` forms. Full per-field detail in `test-runs/FORMS.md`; manifest at `forms_manifest.json`. Highlights of what's needed before deep workflow tests can run end-to-end:

| Route | Required inputs | Selects (need pre-existing master data) |
|---|---:|---:|
| `crm/ledger/add` | 2 | **15** (Account Group, State, City, Salutation, b2b pricelist, retail pricelist…) |
| `purchase/add/` (voucher) | 2 | 11 (Supplier, GSTIN, Item, HSN, Tax, Warehouse…) |
| `sales/add/` | 0 | 11 (Customer, Item, Tax, Salesperson, Counter…) |
| `manufacturing/issue/goldissue/add` | 1 | 7 (Karigar, Metal, Purity, Item…) |
| `purchase/purchaseorder/list/add` | 1 | 7 |
| `inventory/barcodemanagement/list/add/` | 0 | 7 (Item, Design, Metal, Supplier, Branch…) |

Most forms have **0–2 required text fields** but **3–15 dependent selects** that resolve against existing master data (customers, items, karigars, account groups). To deep-test these unattended, I need either a seed list of known-good IDs, or permission to create fixture masters first.

## Deep workflow tests — executed via API

Auth: `POST /userauth/api-token-auth/` with `admin/admin123` → Token.
**Critical:** every subsequent request requires header `X-RETAIL-ID: R001` (retail code, not branch code) — middleware in `mastersconfig/middleware.py` returns empty querysets when absent, causing "phantom record" behavior (POST succeeds but subsequent GET/PATCH/DELETE return 404). Worth documenting prominently for API consumers.

### ✅ Customer Ledger — full CRUD PASS
- `POST /contacts/api/ledger/` → 201, id=900
- `POST /contacts/api/ledger/900/roles/` (assign CO) → 200
- `GET /contacts/api/ledger/900/` → 200 (correct data)
- `PATCH /contacts/api/ledger/900/` (update city/email) → 200 (persisted)
- `DELETE /contacts/api/ledger/900/` → 204
- `GET /contacts/api/ledger/900/` → 404 (confirmed gone)

### ✅ Journal Entry — create + verify PASS, delete blocked by design
- `GET /accounting/api/vou-no/JRNL/` → `JRNL/R001/26-27/00001`
- `POST /accounting/api/journal/` with 2 balanced transactions → `{"success":true}` (id=13)
- `GET /accounting/api/journal/?search=E2E01` → record found, 2 detail rows
- `GET /accounting/api/day-book/?from_date=2026-04-15&to_date=2026-04-15` → voucher appears
- `DELETE /accounting/api/journal/13/` → 400 `"cannot be deleted while posted — cancel first"` (expected behavior, not a bug)

### 🔴 HSN Master — POST crashes (backend bug)
- `POST /mastersconfig/api/hsn/` with valid payload raises `AssertionError`:
  > The `.create()` method does not support writable nested fields by default. Write an explicit `.create()` method for serializer `mastersconfig.serializers.HSNSerializer`, or set `read_only=True` on nested serializer fields.
- **Fix:** in `HSNSerializer`, either set `item_set = ItemSerializer(many=True, read_only=True)` or add an explicit `create()` that pops `item_set`, creates the HSN, then sets the M2M.

### 🔴 Item Master — POST crashes (same bug)
- `POST /mastersconfig/api/item/` with all required fields raises the same `AssertionError` (writable nested serializer without `.create()`). Affects `ItemSerializer` in `mastersconfig/serializers.py`.

### ✅ Other masters — full CRUD PASS
Verified Create → Get → Update → Delete cycles on:
- **Branch Master** (`/mastersconfig/api/branch/`)
- **Shape Master** (`/mastersconfig/api/shape/`)
- **Color Master** (`/mastersconfig/api/color/`) — rejects `color_code` field (silently ignored)
- **Item Group** (`/mastersconfig/api/item_group/`)
- **Packet Group** (`/mastersconfig/api/packet_group/`)
- **Salesperson Master** (`/mastersconfig/api/salesperson/`) — auto-creates commission ledger, good feature
- **GSTIN Master** (`/mastersconfig/api/gstin/`) — auto-creates 6 GST ledgers (Input/Output CGST/SGST/IGST)
- **TDS Section** (`/mastersconfig/api/tds-section/`)
- **Account Group** (`/accounting/api/accounts/`) — tree hierarchy works
- **Company Master** (`/mastersconfig/api/company/`) — auto-creates discount/round-off/hallmark ledgers
- **Fiscal Year** (`/mastersconfig/api/fiscal-years/`) — DELETE not exposed (only set-active/close/reopen actions), by design
- **Fixed Asset** (`/accounting/api/fa/assets/`) — computes `current_wdv`, depreciation method display
- **Role** (`/userauth/api/roles/`)
- **HR Employee** (`/hr/api/employees/`) — requires `user` FK and `retail`

### 🟠 Field-name mismatches (frontend/docs vs. backend)
Several fields that felt "natural" got rejected; correct names were discovered by trial:
| Endpoint | Wrong | Correct |
|---|---|---|
| `/mastersconfig/api/gstin/` | `gstin_no`, `trade_name` | `gstin`, `legal_name` |
| `/mastersconfig/api/salesperson/` | `sales_person_name`, `mobile` | `salesperson_name`, `mobile_no` |
| `/mastersconfig/api/fiscal-years/` | `code`, `start_date`, `end_date` | `fy_code`, `fy_start`, `fy_end` |
| `/mastersconfig/api/tcs-section/` | `default_rate` | `rate_individual`, `rate_company`, `rate` all required (ambiguous) |

Not bugs per se, but API consistency is poor — `gstin` vs `gstin_no`, `fy_start` vs `start_date`, etc. Consider unifying or documenting in a shared schema.

### ✅ Journal cancel → delete workflow PASS
Re-ran with proper cancel step: `POST /accounting/api/journal/13/cancel/` → status `cancelled` → `DELETE` returns 204. Clean two-step lifecycle works. **Dev DB is now clean.**

### Not tested (scope too large for unattended run)
- **Sales Voucher, Purchase Voucher** — payloads are ~100 nested fields (line items, tax breakup, party details, payment modes). Valid creation requires curating a consistent dataset (matched HSN↔item↔tax↔ledger). Happy to run these next if you point at one voucher you're OK mutating.

---

## Test artefact left in dev DB

- `JournalEntry id=13`, voucher_no `JRNL/R001/26-27/E2E01`, 2 lines of ₹100 between `R001_Cash` and `19AACFJ4832H1ZB_Input_CGST`. Cancel then delete to clean up, or leave it as an audit marker.
