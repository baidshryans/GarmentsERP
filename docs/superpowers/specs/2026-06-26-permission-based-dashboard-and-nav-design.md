# Permission-Based Dashboard Quick Links & Navigation — Design

**Date:** 2026-06-26
**Status:** Approved (design); pending implementation plan

## Problem

The dashboard home (`/`) shows hardcoded Quick Action and Report tiles to every
user. The sidebar and top-menu navigation likewise render every module item
regardless of the user's role. Users should only see links to forms and reports
they have permission to access. Today this is correct for admins (who can do
everything) but wrong for restricted roles: a user without Profit & Loss access
still sees the P&L tile.

The backend already enforces RBAC at the API layer (a forbidden click 403s and
redirects to `/forbidden`), but the UI advertises links the user cannot use.

## Goals

- Hide dashboard Quick Action and Report tiles the user lacks permission for.
- Hide sidebar and top-menu nav items the user lacks permission for, collapsing
  now-empty groups and sections.
- Survive mid-session role edits without requiring re-login.
- Be purely additive: an item with no permission tag is never hidden.

## Non-Goals

- Per-report permission granularity. Reports (P&L, Balance Sheet, etc.) are
  aggregate endpoints with no dedicated model, so they are gated by a sensible
  proxy module. Finer-grained report permissions are a separate, larger effort.
- Changing the backend RBAC enforcement model.
- Route-level guarding beyond the existing 403→Forbidden flow (the menu is the
  surface being fixed; the API remains the source of truth).

## Existing Architecture (confirmed)

- **Backend RBAC** is keyed per Django model via `ContentType`, label
  `app_label.model`. `Permission(role, module, can_list, can_get, can_post,
  can_put, can_patch, can_delete)`. `RBACPermission` enforces per-view-model
  access by HTTP method. Superusers bypass all checks.
- **`INLINE_MODEL_MAP`** (in `backend/userauth/permissions.py`) maps child/inline
  models to a parent; a user with the parent permission inherits the child's.
- **Login payload** (`UserLoginView`) returns `user` with `is_superuser`, `role`
  (name), `can_view_customer_data` — but NOT the effective permission set.
- **Nav** is centralized in `frontend/src/config/navData.js` → `navSections`,
  consumed by both `app-sidebar.jsx` and `top-menu/TopMenuBar.jsx`, already
  filtered through `useLicense()` / `isNavGroupLicensed`.
- **`LicenseContext.jsx`** is the established pattern: React Query fetch gated on
  a Token, cached, permissive-while-loading, with a manual refresh. The
  permission feature mirrors it.

## Approach (chosen)

Dedicated `/my-permissions/` endpoint + a `PermissionContext` mirroring
`LicenseContext` + per-item `module`/`perm` tags on tiles and nav items.

Rejected alternatives:
- **Embed permissions in the login payload** — goes stale on role edit until
  re-login.
- **Backend computes the whole nav tree per user** — couples backend to the
  frontend nav structure.

## Components

### 1. Backend endpoint

`GET /userauth/api/my-permissions/` (authenticated). Returns the calling user's
effective permissions:

```json
{
  "is_superuser": false,
  "modules": {
    "sales.salesvou":    { "list": true, "get": true, "post": true,  "put": true,  "patch": true,  "delete": false },
    "inventory.barcode": { "list": true, "get": true, "post": false, "put": false, "patch": false, "delete": false }
  }
}
```

- Built from the user's `UserRole → Role → Permission` rows, keyed by
  `app_label.model`.
- Applies `INLINE_MODEL_MAP` so a child module inherits the parent's verbs,
  matching `RBACPermission` runtime behavior.
- Superuser → `is_superuser: true`; frontend treats that as "everything".
- No role → empty `modules` (user sees only untagged/always-on items).

### 2. Frontend `PermissionContext`

New `frontend/src/contexts/PermissionContext.jsx`, a near-clone of
`LicenseContext`:

- `PermissionProvider` fetches `/userauth/api/my-permissions/` via React Query
  (`enabled` only when a Token exists), `staleTime` ~10 min, with
  `refreshPermissions()` to invalidate after admin role edits.
- `canAccess(moduleLabel, verb = "list")`:
  - `is_superuser` → `true`.
  - Not loaded yet → `true` (no flash-hide during fetch; mirrors license).
  - Otherwise → `true` only if `modules[moduleLabel]?.[verb]` is truthy.
- Mounted alongside `LicenseProvider` in the app tree.

Gating is additive: an untagged item is never hidden by permissions.

### 3. Tagging scheme

Two optional fields on nav items and dashboard tile configs:
- `module` — the `app_label.model` label that gates the item.
- `perm` — the verb required; defaults to `"list"`. The four "create" quick
  actions use `"post"`.

Dashboard tile tags:

| Tile                | module                        | perm |
|---------------------|-------------------------------|------|
| Sales Voucher       | `sales.salesvou`              | post |
| Purchase Voucher    | `purchase.purchasevoucher`    | post |
| Estimate            | `sales.salesvou`              | post |
| Job Work Issue      | `manufacturing.jobworkissue`  | post |
| Barcode Management  | `inventory.barcode`           | list |
| Accounting Voucher  | `accounting.vouchermain`      | post |

Report tile tags (proxy module, `perm: list`):

| Report                                                              | module                     |
|--------------------------------------------------------------------|----------------------------|
| Ledger Statement, Day Book, Outstanding, Trial Balance, Balance Sheet, Profit & Loss | `accounting.vouchermain` |
| Closing Stock, Stock Report                                         | `inventory.barcode`        |

Sidebar nav leaf items are tagged the same way. Items that cannot be confidently
mapped stay untagged (visible + backend-protected) rather than risk hiding them.

> Module label values above are the design intent. During implementation each
> label is verified against the actual `ContentType` rows / `MODEL_DISPLAY_NAMES`
> registry before being committed, since a wrong label would silently hide a tile.

### 4. Applying the filter

- **Dashboard** (`Dashboard.jsx`): refactor the hardcoded `QuickAction` tiles
  into a config array (Reports is already an array). Filter both arrays through
  `canAccess(module, perm)` before render. Untagged → always shown.
- **Sidebar** (`app-sidebar.jsx` → `useLicensedSections`): extend the existing
  pipeline to also drop items failing `canAccess`, then drop now-empty
  groups/sections — the same shape already used for licensing. A parent group
  (e.g. "Issue") shows if any child is visible.
- **Top menu** (`top-menu/TopMenuBar.jsx`): apply the same filter to its nav
  consumption so both layouts behave identically.

## Error Handling

- Endpoint fetch failure → behave permissive (return everything), consistent
  with `LicenseContext`'s fallback, so a transient backend error never locks a
  user out of their own menu.
- A tagged item whose `module` label does not exist in the user's map →
  treated as no access (hidden) for non-superusers. Implementation verifies
  labels up front to avoid accidental hides.

## Testing

- **Backend** unit tests for `/my-permissions/`: role with partial perms, no
  role, superuser, and inline-model inheritance.
- **Frontend** tests: `canAccess` logic (superuser, loading, present/absent
  verb) and that a tagged tile hides when the permission is absent while an
  untagged tile remains.

## Rollout Notes

- Existing roles already have `Permission` rows from RoleManagement, so the
  endpoint returns meaningful data immediately — no data migration.
- After an admin edits a role, call `refreshPermissions()` (and the existing
  `refreshLicense()` pattern) so the menu updates without re-login.
