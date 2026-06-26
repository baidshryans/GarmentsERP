# Permission-Based Dashboard Quick Links & Navigation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hide dashboard Quick Action / Report tiles and sidebar + top-menu nav items that the logged-in user has no RBAC permission to access.

**Architecture:** A new authenticated backend endpoint returns the user's effective `module → verb` permission map (mirroring `RBACPermission` semantics, including inline-child inheritance). A `PermissionContext` (a clone of the existing `LicenseContext` pattern) fetches and caches it and exposes a pure `canAccess(module, verb)` predicate. Dashboard tiles and nav items carry optional `module`/`perm` tags; tagged items are filtered through `canAccess`, untagged items always show (and remain backend-protected via the existing 403→Forbidden flow).

**Tech Stack:** Django REST Framework (backend), React + React Query + Vite/Vitest (frontend), lucide-react icons, shadcn sidebar.

**Spec:** `docs/superpowers/specs/2026-06-26-permission-based-dashboard-and-nav-design.md`

**Verified label facts (do not deviate without re-checking ContentType rows):**
- Sales Voucher / Estimate → `sales.salesvou`
- Purchase Voucher → `purchase.purchasevoucher`
- Job Work Issue → `manufacturing.jobworkissue`
- Accounting Voucher / accounting reports → `accounting.vouchermain`
- Barcode Management / inventory reports → `inventory.barcodemain` (the model class is `BarcodeMain`; **not** `inventory.barcode`)

---

## File Structure

| File | Responsibility | Action |
|------|----------------|--------|
| `backend/userauth/views.py` | Add `my_permissions` view | Modify |
| `backend/userauth/urls.py` | Route `api/my-permissions/` | Modify |
| `backend/userauth/tests.py` | Endpoint tests | Modify |
| `frontend/src/contexts/queryKeys.js` | Add `PERMISSIONS_KEY` | Modify |
| `frontend/src/lib/permissions.js` | Pure helpers: `makeCanAccess`, `filterNavItems` | Create |
| `frontend/src/lib/permissions.test.js` | Unit tests for the pure helpers | Create |
| `frontend/src/contexts/PermissionContext.jsx` | Provider + `usePermissions()` | Create |
| `frontend/src/main.jsx` | Mount `PermissionProvider` | Modify |
| `frontend/src/components/Dashboard/Dashboard.jsx` | Tile configs + filtering | Modify |
| `frontend/src/components/app-sidebar.jsx` | Filter nav items by permission | Modify |
| `frontend/src/components/top-menu/TopMenuBar.jsx` | Same filter for top-menu layout | Modify |

---

## Task 1: Backend `/my-permissions/` endpoint

**Files:**
- Modify: `backend/userauth/views.py` (add view near other `@api_view` functions, e.g. after `list_modules`)
- Modify: `backend/userauth/urls.py`
- Test: `backend/userauth/tests.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/userauth/tests.py` (add imports at top of file if missing):

```python
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from userauth.models import Role, Permission, UserRole
from sales.models import SalesVou

User = get_user_model()
MY_PERMS_URL = "/userauth/api/my-permissions/"


class MyPermissionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_superuser_returns_is_superuser_true(self):
        su = User.objects.create_superuser("admin_mp", "a@a.com", "pw")
        self.client.force_authenticate(su)
        res = self.client.get(MY_PERMS_URL)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_superuser"])
        self.assertEqual(res.data["modules"], {})

    def test_user_without_role_returns_empty_modules(self):
        u = User.objects.create_user("norole", "n@n.com", "pw")
        self.client.force_authenticate(u)
        res = self.client.get(MY_PERMS_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {"is_superuser": False, "modules": {}})

    def test_partial_permissions_reflected(self):
        u = User.objects.create_user("cashier", "c@c.com", "pw")
        role = Role.objects.create(name="Cashier")
        ct = ContentType.objects.get_for_model(SalesVou)
        Permission.objects.create(
            role=role, module=ct,
            can_list=True, can_get=True, can_post=False,
            can_put=False, can_patch=False, can_delete=False,
        )
        UserRole.objects.create(user=u, role=role)
        self.client.force_authenticate(u)
        res = self.client.get(MY_PERMS_URL)
        mods = res.data["modules"]
        self.assertTrue(mods["sales.salesvou"]["list"])
        self.assertFalse(mods["sales.salesvou"]["post"])

    def test_inline_child_inherits_parent_verbs(self):
        u = User.objects.create_user("inlineu", "i@i.com", "pw")
        role = Role.objects.create(name="SalesRole")
        ct = ContentType.objects.get_for_model(SalesVou)
        Permission.objects.create(
            role=role, module=ct,
            can_list=True, can_get=True, can_post=True,
            can_put=True, can_patch=True, can_delete=True,
        )
        UserRole.objects.create(user=u, role=role)
        self.client.force_authenticate(u)
        res = self.client.get(MY_PERMS_URL)
        # sales.salesvouitem inherits sales.salesvou per INLINE_MODEL_MAP
        self.assertIn("sales.salesvouitem", res.data["modules"])
        self.assertTrue(res.data["modules"]["sales.salesvouitem"]["post"])

    def test_requires_authentication(self):
        res = self.client.get(MY_PERMS_URL)
        self.assertEqual(res.status_code, 401)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python manage.py test userauth.tests.MyPermissionsTests -v 2`
Expected: FAIL — 404 on the URL (route does not exist yet).

- [ ] **Step 3: Add the view**

In `backend/userauth/views.py`, after the `list_modules` function add:

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_permissions(request):
    """Effective module→verb permission map for the calling user.

    Mirrors RBACPermission: superusers get everything, inline child models
    inherit their parent's verbs. Used by the frontend to hide menu items and
    dashboard tiles the user cannot access.
    """
    from userauth.permissions import INLINE_MODEL_MAP

    user = request.user
    if user.is_superuser:
        return Response({'is_superuser': True, 'modules': {}})

    try:
        user_role = UserRole.objects.select_related('role').get(user=user)
    except UserRole.DoesNotExist:
        return Response({'is_superuser': False, 'modules': {}})

    modules = {}
    for p in user_role.role.permissions.select_related('module').all():
        ct = p.module
        label = f"{ct.app_label}.{ct.model}"
        modules[label] = {
            'list':   p.can_list,
            'get':    p.can_get,
            'post':   p.can_post,
            'put':    p.can_put,
            'patch':  p.can_patch,
            'delete': p.can_delete,
        }

    # Inline children inherit the parent's verbs (matches RBACPermission fallback).
    for child_label, parent_label in INLINE_MODEL_MAP.items():
        if parent_label in modules and child_label not in modules:
            modules[child_label] = modules[parent_label]

    return Response({'is_superuser': False, 'modules': modules})
```

- [ ] **Step 4: Register the route**

In `backend/userauth/urls.py`, add alongside the other `api/` paths (e.g. just after the `api/modules/` line):

```python
    path('api/my-permissions/', views.my_permissions),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && python manage.py test userauth.tests.MyPermissionsTests -v 2`
Expected: PASS — 5 tests OK.

- [ ] **Step 6: Commit**

```bash
git add backend/userauth/views.py backend/userauth/urls.py backend/userauth/tests.py
git commit -m "feat(userauth): add /my-permissions endpoint for effective RBAC map"
```

---

## Task 2: Frontend pure permission helpers

**Files:**
- Create: `frontend/src/lib/permissions.js`
- Test: `frontend/src/lib/permissions.test.js`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/permissions.test.js`:

```js
import { describe, it, expect } from "vitest";
import { makeCanAccess, filterNavItems } from "./permissions";

describe("makeCanAccess", () => {
  it("superuser can access anything", () => {
    const can = makeCanAccess({ loaded: true, is_superuser: true, modules: {} });
    expect(can("sales.salesvou", "post")).toBe(true);
    expect(can("anything.atall", "delete")).toBe(true);
  });

  it("not-loaded is permissive (no flash-hide)", () => {
    const can = makeCanAccess({ loaded: false, is_superuser: false, modules: {} });
    expect(can("sales.salesvou", "list")).toBe(true);
  });

  it("grants only the verbs present in the map", () => {
    const can = makeCanAccess({
      loaded: true,
      is_superuser: false,
      modules: { "sales.salesvou": { list: true, post: false } },
    });
    expect(can("sales.salesvou", "list")).toBe(true);
    expect(can("sales.salesvou", "post")).toBe(false);
    expect(can("inventory.barcodemain", "list")).toBe(false);
  });

  it("defaults the verb to list", () => {
    const can = makeCanAccess({
      loaded: true,
      is_superuser: false,
      modules: { "inventory.barcodemain": { list: true } },
    });
    expect(can("inventory.barcodemain")).toBe(true);
  });
});

describe("filterNavItems", () => {
  const can = makeCanAccess({
    loaded: true,
    is_superuser: false,
    modules: { "sales.salesvou": { list: true, post: true } },
  });

  it("keeps untagged items", () => {
    const items = [{ title: "Plain", url: "/x" }];
    expect(filterNavItems(items, can)).toHaveLength(1);
  });

  it("drops a tagged leaf the user lacks", () => {
    const items = [
      { title: "Sales", url: "/s", module: "sales.salesvou", perm: "list" },
      { title: "Stock", url: "/k", module: "inventory.barcodemain", perm: "list" },
    ];
    const out = filterNavItems(items, can);
    expect(out.map((i) => i.title)).toEqual(["Sales"]);
  });

  it("filters children and drops a now-empty parent group", () => {
    const items = [
      {
        title: "Group",
        url: "#",
        items: [
          { title: "Allowed", url: "/a", module: "sales.salesvou" },
          { title: "Denied", url: "/d", module: "inventory.barcodemain" },
        ],
      },
      {
        title: "EmptyGroup",
        url: "#",
        items: [{ title: "Denied2", url: "/d2", module: "inventory.barcodemain" }],
      },
    ];
    const out = filterNavItems(items, can);
    expect(out).toHaveLength(1);
    expect(out[0].title).toBe("Group");
    expect(out[0].items.map((i) => i.title)).toEqual(["Allowed"]);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend && npx vitest run src/lib/permissions.test.js`
Expected: FAIL — cannot resolve `./permissions`.

- [ ] **Step 3: Write the helpers**

Create `frontend/src/lib/permissions.js`:

```js
// Pure, framework-free permission helpers. Kept separate from the React context
// so they can be unit-tested without a provider.

/**
 * Build a canAccess(moduleLabel, verb) predicate from a permission snapshot.
 * - Superuser: always true.
 * - Not loaded yet: true (avoids flash-hiding tiles during the fetch).
 * - Otherwise: true only if the verb is granted on that module.
 */
export function makeCanAccess({ loaded, is_superuser, modules }) {
  return function canAccess(moduleLabel, verb = "list") {
    if (is_superuser) return true;
    if (!loaded) return true;
    return Boolean(modules?.[moduleLabel]?.[verb]);
  };
}

/**
 * Filter a nav item list against canAccess.
 * - Items with no `module` tag are always kept.
 * - Tagged leaf items are kept only when canAccess(module, perm ?? "list") passes.
 * - Parent items (with nested `items`) are filtered recursively and dropped
 *   when no children survive.
 */
export function filterNavItems(items, canAccess) {
  const out = [];
  for (const item of items) {
    if (item.items && item.items.length > 0) {
      const children = filterNavItems(item.items, canAccess);
      if (children.length > 0) out.push({ ...item, items: children });
      continue;
    }
    if (!item.module || canAccess(item.module, item.perm ?? "list")) {
      out.push(item);
    }
  }
  return out;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd frontend && npx vitest run src/lib/permissions.test.js`
Expected: PASS — all tests green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/permissions.js frontend/src/lib/permissions.test.js
git commit -m "feat(frontend): pure canAccess + filterNavItems permission helpers"
```

---

## Task 3: `PermissionContext` provider

**Files:**
- Modify: `frontend/src/contexts/queryKeys.js`
- Create: `frontend/src/contexts/PermissionContext.jsx`
- Modify: `frontend/src/main.jsx`

- [ ] **Step 1: Add the query key**

In `frontend/src/contexts/queryKeys.js`, add:

```js
export const PERMISSIONS_KEY = ["permissions", "my-permissions"];
```

- [ ] **Step 2: Create the provider**

Create `frontend/src/contexts/PermissionContext.jsx` (mirrors `LicenseContext.jsx`):

```jsx
import { createContext, useContext, useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/apiClient";
import { PERMISSIONS_KEY } from "./queryKeys";
import { makeCanAccess } from "@/lib/permissions";

const PermissionContext = createContext(null);

const EMPTY = { is_superuser: false, modules: {} };

async function fetchPermissions() {
  try {
    const res = await apiClient.get("/userauth/api/my-permissions/");
    return res.data;
  } catch {
    // On error behave permissively so a transient failure never locks a user
    // out of their own menu. The backend API remains the source of truth.
    return { is_superuser: true, modules: {} };
  }
}

// eslint-disable-next-line react/prop-types
export function PermissionProvider({ children }) {
  const queryClient = useQueryClient();
  const enabled =
    typeof window !== "undefined" && !!sessionStorage.getItem("Token");

  const { data, isSuccess } = useQuery({
    queryKey: PERMISSIONS_KEY,
    queryFn: fetchPermissions,
    enabled,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  const snapshot = useMemo(
    () => ({
      loaded: isSuccess || !enabled,
      ...(data ?? EMPTY),
    }),
    [isSuccess, enabled, data]
  );

  const canAccess = useMemo(() => makeCanAccess(snapshot), [snapshot]);

  const refreshPermissions = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: PERMISSIONS_KEY });
  }, [queryClient]);

  const value = useMemo(
    () => ({ canAccess, refreshPermissions, permissionsLoaded: snapshot.loaded }),
    [canAccess, refreshPermissions, snapshot.loaded]
  );

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
}

export function usePermissions() {
  const ctx = useContext(PermissionContext);
  if (!ctx) throw new Error("usePermissions must be used inside <PermissionProvider>");
  return ctx;
}
```

- [ ] **Step 3: Mount the provider**

In `frontend/src/main.jsx`, import and wrap inside `LicenseProvider` (so it shares the same authenticated subtree). Add the import near the `LicenseProvider` import:

```jsx
import { PermissionProvider } from './contexts/PermissionContext';
```

Then wrap the children of `<LicenseProvider>`. Change:

```jsx
      <LicenseProvider>
```
…so the existing inner content is wrapped, e.g.:

```jsx
      <LicenseProvider>
        <PermissionProvider>
          {/* …existing children unchanged… */}
        </PermissionProvider>
      </LicenseProvider>
```

(Keep whatever JSX currently sits between `<LicenseProvider>` and `</LicenseProvider>` — just nest it one level deeper inside `<PermissionProvider>`.)

- [ ] **Step 4: Verify the app builds**

Run: `cd frontend && npx vite build`
Expected: Build succeeds with no import-resolution errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/contexts/queryKeys.js frontend/src/contexts/PermissionContext.jsx frontend/src/main.jsx
git commit -m "feat(frontend): PermissionProvider fetching effective RBAC map"
```

---

## Task 4: Filter Dashboard tiles

**Files:**
- Modify: `frontend/src/components/Dashboard/Dashboard.jsx`

- [ ] **Step 1: Import the hook**

Add near the other imports in `Dashboard.jsx`:

```jsx
import { usePermissions } from "@/contexts/PermissionContext";
```

- [ ] **Step 2: Replace the hardcoded Quick Actions block with a filtered config**

Replace the entire `{/* Quick Actions */}` `<div>` … its inner grid (the six `<QuickAction .../>` elements) with a config array + map. First, inside the `DashboardHome` component body (where `const user = …` is defined, near the top of the returned component's function), add:

```jsx
  const { canAccess } = usePermissions();

  const quickActions = [
    { to: "/sales/list/", icon: ReceiptText, label: "Sales Voucher", description: "Create or view sales bills", color: "violet", module: "sales.salesvou", perm: "post" },
    { to: "/purchase/list/", icon: ShoppingCart, label: "Purchase Voucher", description: "Record purchases", color: "emerald", module: "purchase.purchasevoucher", perm: "post" },
    { to: "/sales/estimate", icon: Calculator, label: "Estimate", description: "Create a new estimate", color: "sky", module: "sales.salesvou", perm: "post" },
    { to: "/manufacturing/issue/jobwork/", icon: Hammer, label: "Job Work Issue", description: "Issue to karigar", color: "amber", module: "manufacturing.jobworkissue", perm: "post" },
    { to: "/inventory/barcodemanagement/list/", icon: Package, label: "Barcode Management", description: "Manage inventory barcodes", color: "gray", module: "inventory.barcodemain", perm: "list" },
    { to: "/accounting/vouchers/select", icon: Wallet, label: "Accounting Voucher", description: "Receipt, payment, journal", color: "rose", module: "accounting.vouchermain", perm: "post" },
  ].filter((a) => canAccess(a.module, a.perm));

  const reports = [
    { to: "/accounting/ledger-statement", icon: FileText, label: "Ledger Statement", module: "accounting.vouchermain" },
    { to: "/accounting/day-book", icon: BookOpen, label: "Day Book", module: "accounting.vouchermain" },
    { to: "/accounting/outstanding", icon: Wallet, label: "Outstanding", module: "accounting.vouchermain" },
    { to: "/accounting/trialbalance", icon: BookOpen, label: "Trial Balance", module: "accounting.vouchermain" },
    { to: "/accounting/balancesheet", icon: BookOpen, label: "Balance Sheet", module: "accounting.vouchermain" },
    { to: "/accounting/profitloss", icon: BookOpen, label: "Profit & Loss", module: "accounting.vouchermain" },
    { to: "/inventory/reports/closing-stock", icon: Package, label: "Closing Stock", module: "inventory.barcodemain" },
    { to: "/inventory/reports/barcodestockreport", icon: Package, label: "Stock Report", module: "inventory.barcodemain" },
  ].filter((r) => canAccess(r.module, "list"));
```

Then replace the inner grid of the Quick Actions block:

```jsx
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {quickActions.map((a) => (
              <QuickAction key={a.to} to={a.to} icon={a.icon} label={a.label} description={a.description} color={a.color} />
            ))}
          </div>
```

And replace the inline array literal in the Reports block (`{[ … ].map(({ to, icon: Icon, label }) => (`) with the `reports` variable:

```jsx
            {reports.map(({ to, icon: Icon, label }) => (
              <Link
                key={to}
                to={to}
                className="group flex items-center gap-2.5 rounded-xl border border-gray-100 bg-white px-4 py-3 shadow-sm hover:shadow-md hover:border-accent-200 transition-all"
              >
                <Icon className="size-4 text-gray-400 group-hover:text-primary transition-colors shrink-0" />
                <span className="text-sm text-gray-700 group-hover:text-primary font-medium transition-colors truncate">
                  {label}
                </span>
              </Link>
            ))}
```

- [ ] **Step 3: Hide a section header when its list is empty (optional polish)**

Wrap each section so an empty list also hides the heading. For Quick Actions, change the outer `<div>` opening to render only when non-empty:

```jsx
        {quickActions.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">
            Quick Actions
          </h3>
          {/* …grid… */}
        </div>
        )}
```

Do the same `{reports.length > 0 && ( … )}` wrap around the Reports `<div>`.

- [ ] **Step 4: Verify build + dashboard renders**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

Then verify in the running app (preview workflow): a superuser sees all 6 quick actions + 8 reports; the values come from `canAccess` which returns true for superusers. (Permission-restricted verification happens in Task 6.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Dashboard/Dashboard.jsx
git commit -m "feat(dashboard): filter quick-action and report tiles by RBAC permission"
```

---

## Task 5: Filter sidebar + top-menu nav items

**Files:**
- Modify: `frontend/src/components/app-sidebar.jsx`
- Modify: `frontend/src/components/top-menu/TopMenuBar.jsx`
- Modify: `frontend/src/config/navData.js` (add `module`/`perm` tags to a verified set of leaf items)

- [ ] **Step 1: Tag a verified set of nav leaf items**

In `frontend/src/config/navData.js`, add `module` (and `perm` where it differs from `list`) to the leaf items whose backend model is confidently known. Apply exactly these (leave all other items untagged — they stay visible and remain backend-protected):

- In `navMain` → "Issue" group: the `{ title: "Job Work", url: "/manufacturing/issue/jobwork/" }` item gets `module: "manufacturing.jobworkissue", perm: "post"`.
  ```js
        { title: "Job Work",        url: "/manufacturing/issue/jobwork/", module: "manufacturing.jobworkissue", perm: "post" },
  ```
- Sales voucher list entry (in the Sales group, the item whose `url` is `/sales/list/`): add `module: "sales.salesvou", perm: "post"`.
  ```js
        { title: "Sales Voucher", url: "/sales/list/", module: "sales.salesvou", perm: "post" },
  ```
  (Match by the existing `url: "/sales/list/"` line; keep its existing `title`/`icon`.)
- Purchase voucher list entry (item with `url: "/purchase/list/"`): add `module: "purchase.purchasevoucher", perm: "post"`.
- Barcode Management entry (item with `url: "/inventory/barcodemanagement/list/"`): add `module: "inventory.barcodemain", perm: "list"`.
- Accounting voucher entry (item with `url: "/accounting/vouchers/select"`): add `module: "accounting.vouchermain", perm: "post"`.

> Only these five are in scope for v1 tagging — they map 1:1 to verified ContentTypes. Broader nav tagging is a deliberate follow-up (YAGNI): the filtering mechanism below handles any future tags with no further code change.

- [ ] **Step 2: Filter items in the sidebar**

In `frontend/src/components/app-sidebar.jsx`:

Add imports:
```jsx
import { usePermissions } from "@/contexts/PermissionContext";
import { filterNavItems } from "@/lib/permissions";
```

Change `useLicensedSections` to also accept and apply `canAccess`:
```js
function useLicensedSections() {
  const { isNavGroupLicensed } = useLicense()
  const { canAccess } = usePermissions()
  return navSections
    .map(({ label, parts }) => {
      const items = parts
        .filter(({ key }) => isNavGroupLicensed(key))
        .flatMap(({ items }) => items)
      return { label, items: filterNavItems(items, canAccess) }
    })
    .filter(({ items }) => items.length > 0)
}
```

- [ ] **Step 3: Filter items in the top-menu layout**

In `frontend/src/components/top-menu/TopMenuBar.jsx`:

Add imports:
```jsx
import { usePermissions } from "@/contexts/PermissionContext";
import { filterNavItems } from "@/lib/permissions";
```

Update the local `useLicensedSections(isNavGroupLicensed)` to filter items too. Change its body so the flattened items are passed through `filterNavItems`:
```js
function useLicensedSections(isNavGroupLicensed, canAccess) {
  return navSections
    .map(({ label, parts }) => {
      const items = parts
        .filter(({ key }) => isNavGroupLicensed(key))
        .flatMap(({ items }) => items)
      return { label, items: filterNavItems(items, canAccess) }
    })
    .filter(({ items }) => items.length > 0)
}
```

And at its call site (where `const { isNavGroupLicensed } = useLicense()` and `useLicensedSections(isNavGroupLicensed)` appear):
```js
  const { isNavGroupLicensed } = useLicense()
  const { canAccess } = usePermissions()
  const filteredSections = useLicensedSections(isNavGroupLicensed, canAccess)
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/config/navData.js frontend/src/components/app-sidebar.jsx frontend/src/components/top-menu/TopMenuBar.jsx
git commit -m "feat(nav): filter sidebar and top-menu items by RBAC permission"
```

---

## Task 6: Live refresh after role edits + manual verification

**Files:**
- Modify: `frontend/src/components/Settings/RoleManagement.jsx`

- [ ] **Step 1: Refresh permissions after saving a role's permissions**

In `frontend/src/components/Settings/RoleManagement.jsx`:

Add import:
```jsx
import { usePermissions } from "@/contexts/PermissionContext";
```

In the component body, near the other hooks:
```jsx
  const { refreshPermissions } = usePermissions();
```

After the successful `saveRolePermissions` call (the line `const res = await saveRolePermissions(selectedRole.id, payload);` and its success branch), call `refreshPermissions()` so the current admin's own menu updates without re-login:
```jsx
    const res = await saveRolePermissions(selectedRole.id, payload);
    if (res.success) {
      refreshPermissions();
      // …existing success toast / state updates…
    }
```
(Keep the existing success handling; only add the `refreshPermissions()` call.)

- [ ] **Step 2: Build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds.

- [ ] **Step 3: Manual end-to-end verification (preview workflow)**

1. Start the dev server (preview_start).
2. Log in as a **superuser** → dashboard shows all 6 quick actions + 8 reports; sidebar shows every group. (Superuser short-circuits `canAccess`.)
3. In Settings → Roles & Permissions, create a role with **only** `inventory.barcodemain` `can_list` granted. Create a user, assign that role.
4. Log in as that user → dashboard shows **only** the Barcode Management quick action and the two inventory reports (Closing Stock, Stock Report); the Quick Actions/Reports headers for empty groups are hidden; the sidebar shows the Barcode Management item but not the tagged Sales/Purchase/Accounting/Job Work items.
5. Confirm clicking an untagged item still works and that a directly-typed forbidden route still 403→/forbidden (unchanged behavior).

- [ ] **Step 4: Run the full frontend + backend test suites**

Run: `cd frontend && npx vitest run`
Expected: PASS (includes `permissions.test.js`).

Run: `cd backend && python manage.py test userauth -v 2`
Expected: PASS (includes `MyPermissionsTests`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Settings/RoleManagement.jsx
git commit -m "feat(roles): refresh effective permissions after saving role perms"
```

---

## Out of Scope / Follow-ups

- **Latent bug (flag, do not fix here):** `INLINE_MODEL_MAP` in `backend/userauth/permissions.py` maps `inventory.barcodedetails → inventory.barcode` and `inventory.designdetails/designdocument → inventory.design`, but the real parent ContentTypes are `inventory.barcodemain` and `inventory.designmain`. Those parent lookups silently fail (caught + logged), so inline barcode/design children never inherit. Worth a separate fix.
- **Broader nav tagging:** only five high-value leaf items are tagged in v1. Extending tags to the rest of `navData` is incremental data work requiring no code change.
- **Per-report permissions:** reports are gated by a proxy module (`accounting.vouchermain` / `inventory.barcodemain`). Dedicated report permissions would be a larger, separate feature.
```
