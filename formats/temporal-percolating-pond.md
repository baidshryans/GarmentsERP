# Jewel India ERP — Odoo-Style Plugin Architecture Assessment

## Context
The user wants to commercially license the ERP on a per-module basis (each module costs the end-client extra). They are asking whether the current Django monolith can support this, and if not, how hard it would be to convert to microservices without breaking the AI features.

---

## Current Architecture: Django Monolith (NOT Microservices)

The system is a **single Django monolith** with:
- 1 process, 1 SQLite database, 1 deployment unit
- 11 Django apps sharing the same database and ORM
- 70+ models with ~59 cross-app ForeignKey relationships
- 1 React SPA consuming all modules through a single API base URL

**It is NOT a microservices architecture.**

However, it is already well-structured in a way that makes **per-module licensing achievable without microservices**.

---

## Odoo-Style Plugin Architecture: Full Assessment

---

## Option A — Add Module Licensing to the Monolith (RECOMMENDED)

### Why This Works
The system already has all the plumbing needed:
- **`RetailMaster`** — every data row in every module is tagged to a retail/tenant
- **`Role → Permission`** model — per-model CRUD permission system exists
- **RetailMiddleware** — intercepts every API request and controls access
- Frontend shows a `/forbidden` page on 403 responses
- Backend returns 403 for unauthorized API calls

All that is missing is a **subscription/module license table** linked to `RetailMaster`.

### What Needs to Be Built

**1. New model: `RetailModuleLicense`** (in `mastersconfig/models.py`)
```python
class RetailModuleLicense(models.Model):
    retail = ForeignKey(RetailMaster, on_delete=CASCADE)
    module = CharField(max_length=50)  # "sales", "manufacturing", "inventory", etc.
    is_active = BooleanField(default=True)
    valid_until = DateField(null=True, blank=True)

    class Meta:
        unique_together = ('retail', 'module')
```

**2. Middleware enhancement** (in `mastersconfig/middleware.py`)
- After validating `request.retail`, check whether the requested URL's module is licensed
- Map URL prefixes to module names: `/sales/` → "sales", `/manufacturing/` → "manufacturing", etc.
- Return `HTTP 403 Forbidden` with a descriptive error if module is not licensed

**3. Modules that can be licensed independently:**
| Module Key | URL Prefix | Apps Covered |
|---|---|---|
| `sales` | `/sales/` | Sales vouchers, estimates, returns, approvals |
| `purchase` | `/purchase/` | Purchase vouchers, orders, returns |
| `manufacturing` | `/manufacturing/` | Karigar, hallmark, stone, refinery |
| `inventory` | `/inventory/` | Barcodes, stock transfers, designs |
| `accounting` | `/accounting/` | Vouchers, ledger, cash-gold |
| `reports` | (derived) | P&L, GST registers, metal reports |
| `ai` | `/ai/` | AI assistant, NL query |

**4. Frontend changes (minimal):**
- Fetch licensed modules on login, store in localStorage
- Conditionally hide sidebar nav items for unlicensed modules
- Backend already enforces via 403, so frontend is optional/cosmetic

**5. Admin UI or API** to manage licenses per retail client

### Effort Estimate
| Task | Time |
|---|---|
| RetailModuleLicense model + migration | 1 day |
| Middleware update + URL-to-module mapping | 1–2 days |
| Admin panel for license management | 1 day |
| Frontend sidebar conditional rendering | 1 day |
| Testing + edge cases | 2 days |
| **Total** | **~1–1.5 weeks** |

---

## Option B — Convert to True Microservices (NOT RECOMMENDED)

### Why It's Extremely Difficult

The apps are **tightly coupled at the database level**:

| Cross-App Dependency | Example |
|---|---|
| `inventory` ← `manufacturing` | `BarcodeMain.rec_item → KarigarReceiveItem` |
| `manufacturing` ← `sales` | `KarigarGoldIssue.ref_job → CustomerOrderItems` |
| `purchase` ← `inventory` | `PurchaseVoucherItems.barcode → BarcodeMain` |
| `sales` ← `accounting` | `SalesVou.ac_voucher → VoucherMain` |
| ALL apps ← `mastersconfig` | 59+ ForeignKeys to `RetailMaster`, `Item`, `Hsn` |
| ALL apps ← `contacts` | ForeignKeys to `Ledger` across every module |

To convert to microservices you would need to:
1. Break every cross-app FK into an API call or event message
2. Introduce a message broker (Kafka/RabbitMQ) for async consistency
3. Give each service its own database (no shared SQLite)
4. Build an API Gateway for routing
5. Handle distributed transactions (2-phase commit or sagas) where a single sale currently touches: Sales, Accounting, Inventory, Manufacturing
6. Migrate off SQLite to PostgreSQL (SQLite doesn't support multi-process)

### Effort Estimate
- **Team of 3 developers: 8–12 months**
- Risk: Very high — the jewellery domain logic is deeply intertwined (a single Sale voucher affects Sales, Ledger/Accounting, Inventory/Barcode, and optionally Manufacturing)

### AI Features Impact
The `ai_layer` app is the **most loosely coupled** — it only logs queries and calls OpenAI. It would be the **easiest to extract** as a standalone microservice. However, it currently reads from the same database to generate context — extracting it would require an internal data API.

---

## Recommendation

**Do Option A.** The monolith with module-level licensing gives you:
- ✅ Per-module pricing in ~1.5 weeks of work
- ✅ No data migration or deployment changes
- ✅ AI features untouched
- ✅ Single deployment = cheaper hosting for clients
- ✅ Consistent retail/tenant isolation already working

Microservices are only worthwhile if:
- Different modules need to **scale independently** under very different loads
- Different teams need to **deploy independently**
- Clients want to **self-host only specific modules**

For a jewelry ERP sold to SME clients, a well-licensed monolith is the correct architecture.

---

## Critical Files to Modify (Option A)

- `backend/mastersconfig/models.py` — Add `RetailModuleLicense` model
- `backend/mastersconfig/middleware.py` — Add module license check after retail validation
- `backend/mastersconfig/admin.py` — Register `RetailModuleLicense` in Django admin
- `backend/mastersconfig/migrations/` — New migration for the model
- `frontend/src/components/AppSidebar.jsx` — Conditionally hide unlicensed module nav items
- `frontend/src/services/apiService.js` — Add `fetchLicensedModules()` function
- `frontend/src/App.jsx` — Pass licensed modules to sidebar, optionally block routes

---

---

---

## Odoo-Style Plugin Architecture: What It Actually Means & How Hard It Is

### How Odoo's Module System Works (the model we're copying)
Odoo loads **all app code** into Python at startup — it doesn't dynamically install/uninstall Python packages. What changes per client is:
1. Which modules are listed as "installed" in the database
2. Which menus and routes are visible in the UI
3. Which API endpoints are accessible (middleware gates them)
4. Which data is pre-loaded (ledgers, item groups, sequences, etc.)

This is exactly how your current system should be extended. No dynamic Python imports needed.

---

### Backend: What Needs to Change

**What's already there (no change needed):**
- ✅ `RetailMaster` as the tenant anchor — every model in every app already has a `retail` FK
- ✅ `RetailMiddleware` — intercepts every API request, attaches `request.retail`
- ✅ `Role/Permission` system — per-model CRUD permissions exist
- ✅ Each app has its own `urls.py` and `apps.py` — clean boundaries already exist
- ✅ `EXTERNAL_APPS` is already split from core `INSTALLED_APPS` in `settings.py`

**What needs to be added:**

**1. `RetailModuleLicense` model** (~2 hours)
```python
# mastersconfig/models.py
class RetailModuleLicense(models.Model):
    retail = ForeignKey(RetailMaster, on_delete=CASCADE)
    module = CharField(max_length=50)   # "sales", "manufacturing", "inventory", etc.
    is_active = BooleanField(default=True)
    valid_until = DateField(null=True, blank=True)
    installed_at = DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('retail', 'module')
```

**2. Module manifest in each app** (~3 hours total for all apps)
A simple `module_info.py` in each app:
```python
# sales/module_info.py
MODULE_INFO = {
    "name": "sales",
    "label": "Sales",
    "depends": ["contacts", "mastersconfig", "goldrates"],
    "url_prefix": "sales/",
    "icon": "ShoppingCart",
    "description": "Sales vouchers, customer orders, estimates, returns",
}
```

**3. Middleware module check** (~3 hours)
Extend `RetailMiddleware` to:
- After setting `request.retail`, load enabled modules from DB (cached 5 min)
- Attach `request.enabled_modules` list
- For non-GET requests, check if the URL's app is in `request.enabled_modules`
- Return `HTTP 403 {"error": "module_not_licensed", "module": "manufacturing"}` if not

**4. New API endpoint: `GET /mastersconfig/api/my-modules/`** (~2 hours)
Returns list of licensed modules for the current retail:
```json
{"modules": ["sales", "purchase", "inventory", "accounting", "ai"]}
```
Called once on login, result stored in localStorage.

**Total backend effort: ~1.5 days**

---

### Frontend: What Needs to Change

**What's already there (minimal change needed):**
- ✅ Sidebar is **fully data-driven** (`navMain0`, `navMain`, `navMain2`... arrays) — best-case scenario
- ✅ Routes are defined as a **flat array of objects** (`appRoutes`) in App.jsx — easy to filter
- ✅ `ProtectedRoute` component exists — just needs a `requiredModule` parameter added
- ✅ `apiClient.js` has response interceptor that handles 403 — already redirects to `/forbidden`

**What needs to be added:**

**1. `fetchLicensedModules()` on login** (~2 hours)
After login, call `/mastersconfig/api/my-modules/` and store in `localStorage.enabledModules`.

**2. Annotate every route with its module** (~3 hours)
```javascript
// Current:
{ path: "/sales/voucher", heading: "Sales Voucher", component: <SalesVoucherAdd /> }

// After:
{ path: "/sales/voucher", heading: "Sales Voucher", component: <SalesVoucherAdd />, module: "sales" }
```
125+ routes, ~30 min of annotation.

**3. Filter `appRoutes` by enabled modules** (~1 hour)
```javascript
const enabledModules = JSON.parse(localStorage.getItem('enabledModules') || '[]');
const visibleRoutes = appRoutes.filter(r => !r.module || enabledModules.includes(r.module));
```

**4. Extend `ProtectedRoute`** (~1 hour)
```javascript
const ProtectedRoute = ({ element, requiredModule }) => {
  if (!hasBaseUrl()) return <Navigate to="/config" />;
  if (!isAuthenticate()) return <Navigate to="/login" />;
  if (requiredModule && !enabledModules.includes(requiredModule)) return <Navigate to="/forbidden" />;
  return element;
};
```

**5. Sidebar: annotate and filter nav items** (~3 hours)
Each nav section already maps to a module — tag them:
```javascript
// navMain2 = Sales module
const data = {
  navMain2: moduleEnabled("sales") ? [...salesNavItems] : [],
  navMain: moduleEnabled("manufacturing") ? [...manufacturingNavItems] : [],
  // etc.
}
```

**6. "Module Store" page (optional but nice)** (~1 day)
A page showing all available modules, which are enabled, and a contact-to-upgrade CTA. This is the Odoo "Apps" page equivalent.

**Total frontend effort: ~2 days**

---

### Module Dependency Map (what "depends on" what)

| Module | Always Installed | Depends On |
|---|---|---|
| `contacts` | ✅ Core | — |
| `mastersconfig` | ✅ Core | `contacts` |
| `goldrates` | ✅ Core | — |
| `userauth` | ✅ Core | — |
| `accounting` | ✅ Core | `contacts`, `mastersconfig` |
| `sales` | Optional | `contacts`, `mastersconfig`, `goldrates`, `accounting` |
| `purchase` | Optional | `contacts`, `mastersconfig`, `goldrates`, `accounting` |
| `inventory` | Optional | `mastersconfig`, `accounting` |
| `manufacturing` | Optional | `inventory`, `sales`, `purchase` |
| `ai_layer` | Optional | — |

Core modules (4) are always licensed. Billable modules (6): sales, purchase, inventory, manufacturing, ai_layer, and reports (derived from accounting + others).

---

### Total Effort Summary

| Area | Work | Time |
|---|---|---|
| `RetailModuleLicense` model + migration | Backend | 2 hrs |
| Module manifests in each app | Backend | 3 hrs |
| Middleware module check + caching | Backend | 3 hrs |
| `/my-modules/` API endpoint | Backend | 2 hrs |
| Admin panel (manage licenses per client) | Backend | 3 hrs |
| Route annotation + filtering | Frontend | 4 hrs |
| Sidebar filtering | Frontend | 3 hrs |
| Login flow: fetch + store modules | Frontend | 2 hrs |
| ProtectedRoute enhancement | Frontend | 1 hr |
| Module Store page (optional) | Frontend | 1 day |
| Testing all combinations | Both | 1 day |
| **Total (without Module Store)** | | **~3.5 days** |
| **Total (with Module Store)** | | **~5 days** |

### Comparison: Simple Licensing vs Full Plugin Architecture

| Feature | Simple Licensing (1.5 weeks) | Plugin Architecture (5 days) |
|---|---|---|
| Per-module pricing | ✅ | ✅ |
| Backend API enforcement | ✅ | ✅ |
| Sidebar hides locked modules | ✅ | ✅ |
| Module dependency tracking | ❌ | ✅ |
| Module metadata / manifests | ❌ | ✅ |
| "Module Store" page | ❌ | ✅ |
| Route-level access control | ❌ | ✅ |
| Third-party extensibility | ❌ | Foundation laid ✅ |

**Plugin architecture is actually faster** (5 days vs 1.5 weeks) because the manifest/dependency approach forces a cleaner implementation than ad-hoc middleware rules.

---

## Long-Term Vision: Monolith vs Microservices for a Commercial ERP

### What the Industry Actually Does

The most successful commercial ERP products in the world — **SAP, Oracle, Odoo, ERPNext, Tally, QuickBooks** — are all monoliths or modular monoliths. None of them are microservices. This is deliberate, not an oversight.

Microservices became a trend at companies like Netflix, Amazon, and Uber who had **10,000+ engineers** and needed independent deployment pipelines. For a B2B ERP, the constraints are completely different.

### For a Jewelry ERP, Long-Term the Right Evolution Is:

**Stage 1 (Now — ~6 months):**
- Add module licensing to the monolith ✅ (1.5 weeks)
- This enables per-module commercial pricing immediately

**Stage 2 (6–18 months) — "Production-Ready SaaS":**
- Migrate SQLite → **PostgreSQL** (required for any multi-user SaaS; SQLite doesn't support concurrent writes at scale)
- Add **Redis** for caching instead of LocMemCache (works across multiple server processes)
- This alone enables you to host 100s of clients on one server reliably

**Stage 3 (18–36 months) — "Modular Monolith with Clean Boundaries":**
- Enforce strict module boundaries in the codebase (no cross-app ORM imports — use service layer APIs)
- Add a **plugin/extension architecture** so third parties (accounting firms, hardware vendors) can add modules
- This is what Odoo does — it's a monolith where you install/uninstall modules per client

**Stage 4 (Only if you reach 1,000+ concurrent tenants):**
- Extract the **AI service** as a standalone microservice (it's already the most isolated)
- Consider separating the **"platform core"** (auth + retail master + gold rates) from domain modules
- This is SOA (Service-Oriented Architecture) — a middle ground, not full microservices

### Honest Answer

The architecture you have today, with module licensing added, is **good enough for a commercially successful ERP product** selling to hundreds of jewelry businesses. The only thing that will break it before microservices become relevant is the **SQLite → PostgreSQL migration**, which should happen before you launch as SaaS to multiple clients.

Microservices would only make sense if:
- You need different teams to deploy Sales vs Manufacturing independently
- You need to scale the AI service to millions of queries per day (independent of ERP usage)
- You want to allow third-party cloud providers to host only specific modules

None of these are likely scenarios for a jewelry ERP in the foreseeable future.

---

## Verification
1. Create a RetailMaster with only "sales" licensed
2. Attempt to access `/manufacturing/` API → should get `HTTP 403`
3. Attempt to access `/sales/` API → should succeed
4. Frontend sidebar should hide Manufacturing nav items
5. Existing retail with all modules licensed continues to work normally
