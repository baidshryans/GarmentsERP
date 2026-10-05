# Navigation and Home Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Regroup the menu into nine plain-word business groups and turn the home page into a job launchpad with a "Needs your attention" list, so a first-time owner can find any job without knowing ERP terms.

**Architecture:** The menu is data (`NAV` in `core/context_processors.py`); it is restructured and each entry gains optional search aliases that flow into the Ctrl+K index. The launchpad is a second data list (`HOME_ACTIONS`) filtered by the same role permissions the target views enforce. The attention list is a pure function over the figures `build_overview` already computes, so it inherits factory scoping. No model, migration, URL or posting change.

**Tech Stack:** Django 5 templates, plain CSS with tokens from `static/css/tokens.css`, vanilla JS in `static/js/app.js`, pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-10-05-navigation-and-home-design.md`

**Corrections to the spec found while reading the code** (two launchpad targets need a record id, so they open the pick list instead):

- "Pack and dispatch" opens `packing_list` (`packing_new` needs a sale order id).
- "Receive from fabricator" opens `challan_list` (`receipt_new` needs a challan id).

**Before starting:** the working tree has uncommitted changes in `production/views.py`, `templates/production/dashboard.html`, `tests/test_production_ui.py` and `CLAUDE.md` that are not part of this plan. Stage files by name in every commit below, and in Task 1 and Task 4 stage `tests/test_production_ui.py` with `git add -p` so only this plan's hunks go in.

**Run tests with:** `.venv/Scripts/python.exe -m pytest <path> -q` from `D:\Garment ERP`.

---

## File map

| File | Change | Responsibility |
| --- | --- | --- |
| `core/context_processors.py` | modify | New `NAV`, `ICONS`, `PREFIXES`; aliases into `nav_index` |
| `static/js/app.js` | modify line 207 | Search matches aliases |
| `core/home_actions.py` | create | `HOME_ACTIONS` and `home_actions(user)` |
| `reports/services/overview.py` | modify | `attention_items(data)`; `build_overview` adds `attention` |
| `core/views.py` | modify `home` | Pass launchpad islands to the template |
| `templates/core/home.html` | rewrite | Launchpad, attention list, today at a glance |
| `static/css/base.css` | append | Launchpad, attention and stat-row styles |
| 9 list / report templates | modify titles | Plain-word page titles |
| `docs/SETUP_GUIDE.md` | modify | Menu paths in the user guide |
| `tests/test_navigation.py` | create | All new tests |
| `tests/test_production_ui.py`, `tests/test_sales_ui.py`, `tests/test_purchases_ui.py` | modify | Old-label assertions |

---

### Task 1: Regroup the menu and add search aliases

**Files:**
- Create: `tests/test_navigation.py`
- Modify: `core/context_processors.py:17-161` and `:196-223`
- Modify: `static/js/app.js:207`
- Modify: `tests/test_production_ui.py:263`, `tests/test_sales_ui.py:315`, `tests/test_purchases_ui.py:315-317`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_navigation.py`:

```python
"""The menu is grouped by business job, keeps every screen reachable, and search still finds the old trade terms."""
import json
import re

from django.test import Client
from django.urls import reverse

from core.context_processors import NAV, flat_items

# Every screen the menu offered before the regroup. None may be dropped.
OLD_MENU = {
    "home", "style_list", "material_list", "party_list", "pricelist_list", "route_list", "process_list", "unit_list",
    "hsn_list", "excel_import", "po_list", "grn_list", "invoice_list", "debitnote_list", "saleorder_list",
    "packing_list", "saleinvoice_list", "billing", "salecn_list", "stock_enquiry", "roll_list", "transfer_list",
    "journal_list", "opening_stock", "reorder_levels", "stock_alerts", "tag_print", "production_dashboard",
    "order_list", "move_bundles", "challan_list", "receipt_list", "bill_list", "rate_list", "job_reports",
    "daily_summary", "ledger_list", "chart_of_accounts", "voucher_payment", "voucher_receipt", "voucher_contra",
    "voucher_journal", "voucher_sales", "voucher_purchase", "voucher_debit_note", "voucher_credit_note",
    "voucher_list", "trial_balance", "profit_loss", "balance_sheet", "day_book", "ledger_book", "ledger_pick",
    "opening_balances", "period_locks", "year_end", "sales_report", "purchase_report", "finished_stock",
    "ageing_debtors", "ageing_creditors", "gstr1", "gstr3b", "tax_register", "help", "factory_list", "user_list",
    "role_list", "tax_settings", "inventory_settings", "sales_settings", "reset_database",
}


def _client(user):
    c = Client()
    c.force_login(user)
    return c


def _index(html):
    return json.loads(re.search(r'<script id="nav-index" type="application/json">(.*?)</script>', html, re.S).group(1))


def test_menu_groups_are_the_nine_business_groups_in_order():
    assert [title for title, _ in NAV] == ["Home", "Masters", "Buy", "Make", "Sell", "Stock", "Money", "Reports", "More"]


def test_no_screen_was_dropped_and_none_is_listed_twice():
    names = [u for _, items in NAV for u, _, _ in flat_items(items)]
    assert set(names) >= OLD_MENU, sorted(OLD_MENU - set(names))
    assert len(names) == len(set(names))


def test_masters_is_still_a_top_level_group(company, owner):
    html = _client(owner).get(reverse("home")).content.decode()
    assert 'data-group="masters"' in html
    for label in ("Styles", "Materials", "Parties", "Price lists"):
        assert label in html


def test_search_finds_screens_by_their_old_trade_terms(company, owner):
    index = _index(_client(owner).get(reverse("home")).content.decode())
    by_url = {i["url"]: i for i in index}
    assert by_url[reverse("grn_list")]["label"] == "Goods received" and "grn" in by_url[reverse("grn_list")]["alt"].lower()
    assert "challan" in by_url[reverse("challan_list")]["alt"].lower()
    assert "debit note" in by_url[reverse("debitnote_list")]["alt"].lower()
    assert "credit note" in by_url[reverse("salecn_list")]["alt"].lower()
    assert by_url[reverse("journal_list")]["group"] == "More" and by_url[reverse("journal_list")]["sub"] == "Accountant"
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py -q`
Expected: 4 failed (group list differs; `KeyError: 'alt'`; `data-group="masters"` passes already, that one may pass).

- [ ] **Step 3: Replace `NAV`, `flat_items`, `ICONS`, `PREFIXES`**

In `core/context_processors.py` replace everything from `NAV = [` through the end of the `PREFIXES = {...}` block with:

```python
# An entry is (url_name, label, screen) or (url_name, label, screen, aliases). The aliases are the trade or
# accounting terms a user may type in the quick-jump box; they are searched but never shown.
NAV = [
    ("Home", [("home", "Home", "core.home")]),
    ("Masters", [
        ("style_list", "Styles", "masters.style"),
        ("material_list", "Materials", "masters.material", "fabric trims items"),
        ("party_list", "Parties", "masters.party", "customers suppliers fabricators"),
        ("pricelist_list", "Price lists", "masters.pricelist"),
        Sub("Setup", [
            ("route_list", "Routes", "masters.route"),
            ("process_list", "Processes", "masters.process"),
            ("unit_list", "Units, sizes, colours", "masters.basics"),
            ("hsn_list", "HSN and GST slabs", "tax.hsn"),
        ]),
        ("excel_import", "Import from Excel", "masters.import"),
    ]),
    ("Buy", [
        ("po_list", "Purchase orders", "purchases.po", "PO"),
        ("grn_list", "Goods received", "purchases.grn", "GRN goods receipt inward"),
        ("invoice_list", "Supplier bills", "purchases.invoice", "purchase invoices"),
        ("debitnote_list", "Returns to supplier", "purchases.debitnote", "debit notes"),
    ]),
    ("Make", [
        ("production_dashboard", "Production dashboard", "production.dashboard"),
        ("order_list", "Production orders", "production.order", "lots cutting"),
        ("move_bundles", "Move bundles", "production.move"),
        ("challan_list", "Sent to fabricators", "jobwork.challan", "challans job work"),
        ("receipt_list", "Received from fabricators", "jobwork.receipt", "receipts and QC"),
        ("bill_list", "Labour bills", "jobwork.bill"),
        ("rate_list", "Labour rates", "jobwork.rate"),
    ]),
    ("Sell", [
        ("saleorder_list", "Sale orders", "sales.order"),
        ("packing_list", "Packing and dispatch", "sales.packing"),
        ("saleinvoice_list", "Bills", "sales.invoice", "sale invoices"),
        ("billing", "Quick billing (barcode)", "sales.invoice.create", "barcode billing scan counter sale"),
        ("salecn_list", "Returns from customer", "sales.creditnote", "credit notes"),
    ]),
    ("Stock", [
        ("stock_enquiry", "Stock", "inventory.stock"),
        ("roll_list", "Fabric rolls", "inventory.stock"),
        ("transfer_list", "Transfers", "inventory.transfer"),
        ("stock_alerts", "Low stock", "inventory.alerts", "low-stock alerts"),
        ("reorder_levels", "Reorder levels", "inventory.reorder"),
        ("tag_print", "Print tags", "inventory.labels", "labels barcode"),
    ]),
    ("Money", [
        ("voucher_receipt", "Money received", "ledger.voucher.create", "receipt voucher"),
        ("voucher_payment", "Money paid", "ledger.voucher.create", "payment voucher"),
        ("ledger_pick", "Party accounts", "ledger.report", "ledger statement"),
        ("voucher_list", "All entries", "ledger.voucher", "all vouchers"),
    ]),
    ("Reports", [
        ("sales_report", "Sales", "sales.invoice"),
        ("purchase_report", "Purchases", "purchases.invoice"),
        ("finished_stock", "Finished stock", "inventory.stock"),
        ("job_reports", "Fabricator reports", "jobwork.report"),
        ("daily_summary", "Daily summary", "jobwork.report"),
        ("ageing_debtors", "Who owes me", "ledger.report", "receivables ageing debtors outstanding"),
        ("ageing_creditors", "Whom I owe", "ledger.report", "payables ageing creditors outstanding"),
        ("profit_loss", "Profit and loss", "ledger.report", "P&L"),
        ("balance_sheet", "Balance sheet", "ledger.report"),
        Sub("GST", [
            ("gstr1", "GSTR-1 data", "tax.report"),
            ("gstr3b", "GSTR-3B summary", "tax.report"),
            ("tax_register", "Tax register", "tax.report"),
        ]),
    ]),
    ("More", [
        Sub("Accountant", [
            ("ledger_list", "Ledgers", "ledger.chart"),
            ("chart_of_accounts", "Chart of accounts", "ledger.chart"),
            ("voucher_journal", "Journal", "ledger.voucher.create"),
            ("voucher_contra", "Contra", "ledger.voucher.create", "cash bank transfer"),
            ("voucher_sales", "Sales voucher", "ledger.voucher.create"),
            ("voucher_purchase", "Purchase voucher", "ledger.voucher.create"),
            ("voucher_debit_note", "Debit note voucher", "ledger.voucher.create"),
            ("voucher_credit_note", "Credit note voucher", "ledger.voucher.create"),
            ("trial_balance", "Trial balance", "ledger.report"),
            ("day_book", "Day book", "ledger.report"),
            ("ledger_book", "Ledger book", "ledger.report"),
            ("opening_balances", "Opening balances", "ledger.opening"),
            ("opening_stock", "Opening stock", "inventory.opening"),
            ("journal_list", "Stock journal", "inventory.journal"),
            ("period_locks", "Period locks", "core.period_lock"),
            ("year_end", "Year-end", "ledger.yearend"),
        ]),
        Sub("Settings", [
            ("factory_list", "Factories", "core.factory"),
            ("user_list", "Users", "core.user"),
            ("role_list", "Roles", "core.role"),
            ("tax_settings", "Tax settings", "tax.settings"),
            ("inventory_settings", "Inventory settings", "inventory.settings"),
            ("sales_settings", "Sales settings", "sales.settings"),
            ("reset_database", "Reset database", "core.reset"),
        ]),
        ("help", "Help and user guide", "core.home"),
    ]),
]


def flat_items(items):
    """Every (url_name, label, screen) in a group, with the fold-away sections opened out."""
    for it in items:
        if isinstance(it, Sub):
            for k in it.items:
                yield k[:3]
        else:
            yield it[:3]


# A group is "current" when the page is one of its screens or lives under one of its URL prefixes
# (a lot page, a challan, a style are not menu entries but belong to Make, Masters).
ICONS = {
    "Home": "i-home", "Masters": "i-masters", "Buy": "i-purchases", "Make": "i-production", "Sell": "i-sales",
    "Stock": "i-inventory", "Money": "i-accounts", "Reports": "i-reports", "More": "i-admin",
}

PREFIXES = {
    "Masters": ("/masters/", "/import/"),
    "Buy": ("/purchases/",),
    "Make": ("/production/", "/jobwork/"),
    "Sell": ("/sales/",),
    "Stock": ("/inventory/",),
    "Reports": ("/reports/", "/accounts/ageing", "/accounts/profit", "/accounts/balance"),
    "More": ("/accounts/chart", "/accounts/opening", "/accounts/trial", "/accounts/day-book", "/accounts/period",
             "/accounts/year", "/factories/", "/users/", "/roles/", "/tax/", "/settings/"),
}
```

Money has no prefix on purpose: its four screens light up by exact match, so a journal voucher (under More) does not also open Money.

- [ ] **Step 4: Carry aliases into the search index**

In `app_shell`, replace the `visible` helper with:

```python
    def visible(entries):
        return [
            {"url_name": e[0], "label": e[1], "current": e[0] == current, "alt": e[3] if len(e) > 3 else ""}
            for e in entries
            if (e[2] == "core.home" or _allowed(user, e[2])) and _built(e[0])
        ]
```

and replace the `index.append(...)` call with:

```python
                    index.append({"label": k["label"], "group": title, "sub": i["label"] if i.get("sub") else "",
                                  "alt": k["alt"], "url": reverse(k["url_name"])})
```

In `static/js/app.js` line 207 replace the `hay` line with:

```javascript
    jump.items.forEach(function (i) { i.hay = (i.label + " " + (i.alt || "") + " " + i.sub + " " + i.group).toLowerCase(); });
```

- [ ] **Step 5: Update the three existing menu-label tests**

`tests/test_production_ui.py:263`:

```python
    assert "Move bundles" in html and "Sent to fabricators" in html and "Labour bills" not in html
```

`tests/test_sales_ui.py:315`:

```python
    for text in ("Sale orders", "Packing and dispatch", "Quick billing (barcode)", "Returns from customer", "Sales settings"):
```

`tests/test_purchases_ui.py:315-317`:

```python
    assert "Goods received" in html and "Transfers" in html and "Supplier bills" not in html
    html = login(accountant).get(reverse("home")).content.decode()
    assert "Supplier bills" in html and "Returns to supplier" in html
```

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py tests/test_routes.py tests/test_ui.py tests/test_production_ui.py tests/test_sales_ui.py tests/test_purchases_ui.py -q`
Expected: all pass. If a test elsewhere asserts an old menu label, change the assertion to the new label from the spec's wording table.

- [ ] **Step 7: Commit**

```bash
git add core/context_processors.py static/js/app.js tests/test_navigation.py tests/test_sales_ui.py tests/test_purchases_ui.py
git add -p tests/test_production_ui.py
git commit -m "UI: menu regrouped by business job, search keeps the old terms"
```

---

### Task 2: Launchpad actions

**Files:**
- Create: `core/home_actions.py`
- Modify: `tests/test_navigation.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_navigation.py`:

```python
from core.home_actions import HOME_ACTIONS, home_actions
from core.models import Role
from tests.conftest import make_user


def test_every_launchpad_button_points_at_a_real_screen():
    for _, _, actions in HOME_ACTIONS:
        for url_name, label, screen, action in actions:
            assert reverse(url_name), label


def test_owner_gets_all_five_islands(company, owner):
    islands = home_actions(owner)
    assert [i["title"] for i in islands] == ["Buy", "Make", "Sell", "Money", "Masters"]
    assert sum(len(i["actions"]) for i in islands) == 17


def test_launchpad_follows_the_role(company, factory):
    sup = make_user("sup_launch")
    sup.roles.add(Role.objects.get(name="Production Supervisor"))
    sup.allowed_factories.add(factory)
    labels = {a["label"] for i in home_actions(sup) for a in i["actions"]}
    assert "Money received" not in labels and "Make a bill" not in labels
    assert all(i["actions"] for i in home_actions(sup))          # an island with nothing allowed is dropped


def test_user_with_no_role_gets_no_islands(company):
    assert home_actions(make_user("nobody")) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'core.home_actions'`.

- [ ] **Step 3: Implement**

Create `core/home_actions.py`:

```python
"""The home launchpad: the everyday jobs in plain words, each opening the screen where that job is done.
A button is offered only when the user's role passes the same permission check the target view enforces."""
from django.urls import reverse

# (island title, icon, [(url_name, label, screen, action), ...])
HOME_ACTIONS = [
    ("Buy", "i-purchases", [
        ("po_new", "Order fabric or material", "purchases.po", "create"),
        ("grn_new", "Receive goods", "purchases.grn", "create"),
        ("invoice_new", "Enter a supplier bill", "purchases.invoice", "create"),
    ]),
    ("Make", "i-production", [
        ("order_new", "Start a production order", "production.order", "create"),
        ("order_list", "Cut a lot", "production.order", "view"),
        ("challan_new", "Send to fabricator", "jobwork.challan", "create"),
        ("challan_list", "Receive from fabricator", "jobwork.challan", "view"),
    ]),
    ("Sell", "i-sales", [
        ("saleorder_new", "Take an order", "sales.order", "create"),
        ("billing", "Make a bill", "sales.invoice", "create"),
        ("packing_list", "Pack and dispatch", "sales.packing", "view"),
    ]),
    ("Money", "i-accounts", [
        ("voucher_receipt", "Money received", "ledger.voucher", "create"),
        ("voucher_payment", "Money paid", "ledger.voucher", "create"),
        ("ageing_debtors", "Who owes me", "ledger.report", "view"),
        ("ageing_creditors", "Whom I owe", "ledger.report", "view"),
    ]),
    ("Masters", "i-masters", [
        ("style_new", "New style", "masters.style", "create"),
        ("material_new", "New material", "masters.material", "create"),
        ("party_new", "New party", "masters.party", "create"),
    ]),
]


def home_actions(user):
    """Islands of permitted buttons for this user, in display order. Empty islands are left out."""
    islands = []
    for title, icon, actions in HOME_ACTIONS:
        allowed = [{"label": label, "url": reverse(url_name)}
                   for url_name, label, screen, action in actions if user.has_screen_perm(screen, action)]
        if allowed:
            islands.append({"title": title, "icon": icon, "actions": allowed})
    return islands
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py -q`
Expected: all pass. If `test_launchpad_follows_the_role` fails because the seeded Production Supervisor role holds one of the two asserted permissions, that is a real finding: stop and report it rather than loosening the assertion.

- [ ] **Step 5: Commit**

```bash
git add core/home_actions.py tests/test_navigation.py
git commit -m "UI: home launchpad actions filtered by role"
```

---

### Task 3: "Needs your attention" list

**Files:**
- Modify: `reports/services/overview.py` (add function before `build_overview`; one line inside it)
- Modify: `tests/test_navigation.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_navigation.py`:

```python
from reports.services.overview import attention_items, build_overview


def _figures(**over):
    data = {
        "production": {"awaiting_qc": 0, "late_lots": 0, "orders_to_release": 0},
        "purchases": {"pos_to_approve": 0, "grn_pending": 0},
        "sales": {"overdue_orders": 0},
        "low_stock": 0,
    }
    for key, value in over.items():
        section, _, field = key.partition("__")
        if field:
            data[section][field] = value
        else:
            data[section] = value
    return data


def test_attention_lists_only_what_is_waiting_with_a_link_to_fix_it():
    items = attention_items(_figures(production__awaiting_qc=3, purchases__pos_to_approve=1, low_stock=5))
    assert [(i["count"], i["text"], i["url"]) for i in items] == [
        (3, "receipts from fabricators are waiting to be checked", reverse("receipt_list")),
        (1, "purchase order is waiting for approval", reverse("po_list")),
        (5, "items are below their minimum stock", reverse("stock_alerts")),
    ]


def test_attention_skips_sections_the_role_may_not_see():
    data = _figures(low_stock=2)
    data["production"] = data["purchases"] = data["sales"] = None
    data["low_stock"] = None
    assert attention_items(data) == []


def test_overview_carries_the_attention_list(company, owner):
    assert build_overview(owner)["attention"] == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py -q`
Expected: collection error, `ImportError: cannot import name 'attention_items'`.

- [ ] **Step 3: Implement**

In `reports/services/overview.py` add `from django.urls import reverse` to the imports, and add above `build_overview`:

```python
# (section, figure, text for one, text for many, screen that deals with it)
ATTENTION = [
    ("production", "awaiting_qc", "receipt from a fabricator is waiting to be checked",
     "receipts from fabricators are waiting to be checked", "receipt_list"),
    ("production", "late_lots", "lot is past its due date", "lots are past their due date", "production_dashboard"),
    ("production", "orders_to_release", "production order is a draft, waiting to be released",
     "production orders are drafts, waiting to be released", "order_list"),
    ("purchases", "pos_to_approve", "purchase order is waiting for approval",
     "purchase orders are waiting for approval", "po_list"),
    ("purchases", "grn_pending", "goods receipt is not posted yet", "goods receipts are not posted yet", "grn_list"),
    ("sales", "overdue_orders", "sale order is past its due date", "sale orders are past their due date", "saleorder_list"),
    (None, "low_stock", "item is below its minimum stock", "items are below their minimum stock", "stock_alerts"),
]


def attention_items(data):
    """What is waiting on the user, from the figures already gathered for them (so already factory-scoped
    and already limited to what their role may see). Nothing waiting, no line."""
    items = []
    for section, figure, one, many, url_name in ATTENTION:
        source = data if section is None else data.get(section)
        count = (source or {}).get(figure) or 0
        if count:
            items.append({"count": count, "text": one if count == 1 else many, "url": reverse(url_name)})
    return items
```

In `build_overview`, just before `return data`, add:

```python
    data["attention"] = attention_items(data)
```

- [ ] **Step 4: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add reports/services/overview.py tests/test_navigation.py
git commit -m "UI: needs-your-attention list from the overview figures"
```

---

### Task 4: The new home page

**Files:**
- Modify: `core/views.py:31-32`
- Rewrite: `templates/core/home.html`
- Modify: `static/css/base.css` (append)
- Modify: `tests/test_production_ui.py:268-274`, `tests/test_navigation.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_navigation.py`:

```python
def test_home_is_a_launchpad(company, owner):
    html = _client(owner).get(reverse("home")).content.decode()
    assert "What do you want to do?" in html
    for label in ("Order fabric or material", "Send to fabricator", "Make a bill", "Money received", "New party"):
        assert label in html
    assert f'href="{reverse("grn_new")}"' in html
    assert "Nothing is waiting on you" in html
    assert "Posted vouchers" not in html and "Active factories" not in html and "Recent vouchers" not in html


def test_home_for_a_user_with_no_role_still_opens(company):
    r = _client(make_user("norole")).get(reverse("home"))
    assert r.status_code == 200 and "What do you want to do?" not in r.content.decode()
```

Replace `tests/test_production_ui.py:268-274` with:

```python
def test_home_shows_lots_in_production_and_hides_money_from_production_roles(company, factory, owner):
    ns = build(company, factory, owner, with_stock=True)
    html = login(owner).get(reverse("home")).content.decode()
    assert "Items in production" in html and "Today at a glance" in html and ns.lot.lot_no in html
    sup = user_with("sup_home", "Production Supervisor", factory)
    body = login(sup).get(reverse("home")).content.decode()
    assert "Money received" not in body and "Sales today" not in body
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py tests/test_production_ui.py -q`
Expected: the three home tests fail on `"What do you want to do?"` / `"Today at a glance"`.

- [ ] **Step 3: Pass the islands from the view**

`core/views.py`, replace the body of `home`:

```python
def home(request):
    from .home_actions import home_actions

    ctx = build_overview(request.user)
    ctx["islands"] = home_actions(request.user)
    return render(request, "core/home.html", ctx)
```

- [ ] **Step 4: Rewrite the template**

Replace the whole of `templates/core/home.html` with:

```html
{% extends "base.html" %}
{% block title %}Home{% endblock %}
{% block content %}
  <div class="page-head"><h1 class="page-title">Hello, {{ request.user.first_name|default:request.user.username }}</h1><span class="muted">{{ today|date:"l, d M Y" }}</span></div>

  {% if islands %}
  <h2 class="section-title">What do you want to do?</h2>
  <div class="launch">
    {% for island in islands %}
    <section class="island" aria-labelledby="launch-{{ forloop.counter }}">
      <h2 id="launch-{{ forloop.counter }}"><svg aria-hidden="true"><use href="#{{ island.icon }}"/></svg>{{ island.title }}</h2>
      <div class="launch-actions">{% for a in island.actions %}<a class="btn" href="{{ a.url }}">{{ a.label }}</a>{% endfor %}</div>
    </section>
    {% endfor %}
  </div>
  {% endif %}

  <h2 class="section-title">Needs your attention</h2>
  <div class="island">
    {% if attention %}
      <ul class="attention">{% for item in attention %}
        <li><a href="{{ item.url }}"><span class="count">{{ item.count }}</span><span>{{ item.text }}</span></a></li>
      {% endfor %}</ul>
    {% else %}
      <p class="muted">Nothing is waiting on you.</p>
    {% endif %}
  </div>

  {% if production or day or sales %}
  <h2 class="section-title">Today at a glance</h2>
  <div class="stat-row">
    {% if production %}
    <div class="island"><div class="label muted">Pieces in progress</div><div class="stat">{{ production.wip_total }}</div><div class="muted">{{ production.open_lots }} open lot{{ production.open_lots|pluralize }}</div></div>
    <div class="island"><div class="label muted">With fabricators</div><div class="stat">{{ production.challans_out }}</div><div class="muted">open challan{{ production.challans_out|pluralize }}</div></div>
    {% endif %}
    {% if day.sales_today is not None %}<div class="island"><div class="label muted">Sales today</div><div class="stat">{{ day.sales_today }}</div><div class="muted">{{ day.invoices_today }} bill{{ day.invoices_today|pluralize }}</div></div>{% endif %}
    {% if day.collections_today is not None %}<div class="island"><div class="label muted">Collections today</div><div class="stat">{{ day.collections_today }}</div><div class="muted">received in cash and bank</div></div>{% endif %}
    {% if sales %}<div class="island"><div class="label muted">Sales this month</div><div class="stat">{{ sales.month_sales }}</div><div class="muted">{{ sales.month_invoices }} bill{{ sales.month_invoices|pluralize }}</div></div>{% endif %}
  </div>
  {% endif %}

  {% if production %}
  <div class="island">
    <h2>Items in production</h2>
    {% if production.rows %}
      <div class="table-scroll"><table>
        <thead><tr><th scope="col">Lot</th><th scope="col">Style</th><th scope="col">Order</th><th scope="col" class="num">Planned</th><th scope="col" class="num">Cut</th><th scope="col" class="num">In progress</th><th scope="col">Stages</th><th scope="col">Where</th><th scope="col">Due</th></tr></thead>
        <tbody>{% for r in production.rows %}
          <tr><td><a href="{% url 'lot_detail' r.lot.pk %}">{{ r.lot.lot_no }}</a></td><td>{{ r.lot.style.style_no }} {{ r.lot.colour }}</td><td>{{ r.order.number|default:"-" }}</td>
            <td class="num">{{ r.planned }}</td><td class="num">{{ r.cut }}</td><td class="num">{{ r.wip }}</td><td>{{ r.stages }}</td><td>{{ r.where }}</td>
            <td>{% if r.order.due_date %}{{ r.order.due_date|date:"d M" }}{% endif %}{% if r.late %} <span class="pill danger">Late</span>{% endif %}</td></tr>
        {% endfor %}</tbody>
      </table></div>
      <p><a href="{% url 'production_dashboard' %}">Full production dashboard</a></p>
    {% else %}
      <p class="muted">Nothing is in production right now.</p>
    {% endif %}
  </div>
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Add the styles**

Append to `static/css/base.css` (tokens only, no hex values):

```css
/* ---- home launchpad ---- */
.launch { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.launch .island { margin-bottom: 0; }
.launch h2 { display: flex; align-items: center; gap: var(--space-2); }
.launch h2 svg { width: 20px; height: 20px; color: var(--color-primary); }
.launch-actions { display: grid; gap: var(--space-2); }
.launch-actions .btn { display: flex; justify-content: flex-start; width: 100%; min-height: 44px; text-align: left; }
.attention { list-style: none; margin: 0; padding: 0; }
.attention li + li { border-top: 1px solid var(--color-hairline); }
.attention a { display: flex; align-items: baseline; gap: var(--space-3); padding: var(--space-2) 0; color: var(--color-ink); }
.attention a:hover { color: var(--color-primary); text-decoration: none; }
.attention .count { min-width: 2.5em; text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--color-primary); }
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.stat-row .island { margin-bottom: 0; }
```

Before saving, open `static/css/tokens.css` and confirm `--space-2`, `--space-3`, `--space-4`, `--color-hairline`, `--color-primary`, `--color-ink` exist under those exact names; use the file's actual name if one differs.

- [ ] **Step 6: Run the tests**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py tests/test_production_ui.py tests/test_ui.py tests/test_routes.py -q`
Expected: all pass.

- [ ] **Step 7: Look at it in the browser**

Start the dev server with the preview tool (`preview_start` with the Django entry in `.claude/launch.json`), sign in as the owner, open `/`. Check: five islands in a row on a wide window and stacked at 375px; buttons at least 44px tall; attention list reads as sentences; no console errors; the opt-in dark theme keeps readable contrast. Open Ctrl+K, type `grn` and `challan`, confirm "Goods received" and "Sent to fabricators" come up. Take a screenshot of the home page for the owner.

- [ ] **Step 8: Commit**

```bash
git add core/views.py templates/core/home.html static/css/base.css tests/test_navigation.py
git add -p tests/test_production_ui.py
git commit -m "UI: home is a job launchpad with a needs-your-attention list"
```

---

### Task 5: Plain-word page titles

**Files:** the nine templates below; `tests/test_navigation.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_navigation.py`:

```python
import pytest


@pytest.mark.parametrize("url_name,title", [
    ("grn_list", "Goods received"), ("invoice_list", "Supplier bills"), ("debitnote_list", "Returns to supplier"),
    ("challan_list", "Sent to fabricators"), ("receipt_list", "Received from fabricators"),
    ("saleinvoice_list", "Bills"), ("billing", "Quick billing"), ("salecn_list", "Returns from customer"),
    ("ageing_debtors", "Who owes me"), ("ageing_creditors", "Whom I owe"),
])
def test_page_heading_matches_the_menu_wording(company, owner, url_name, title):
    html = _client(owner).get(reverse(url_name)).content.decode()
    assert re.search(r'<h1 class="page-title">\s*' + re.escape(title) + r"\s*</h1>", html), url_name
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_navigation.py -q -k heading`
Expected: 10 failed.

- [ ] **Step 3: Change the titles**

In each file change both the `{% block title %}...{% endblock %}` text and the text inside `<h1 class="page-title">...</h1>`; leave everything else on those lines as it is.

| File | Old text | New text |
| --- | --- | --- |
| `templates/purchases/grn_list.html` | `Goods receipt` / `Goods receipt (GRN)` | `Goods received` |
| `templates/purchases/invoice_list.html` | `Purchase invoices` | `Supplier bills` |
| `templates/purchases/debitnote_list.html` | `Debit notes` | `Returns to supplier` |
| `templates/jobwork/challan_list.html` | current heading (`Challans` / `Job work challans`) | `Sent to fabricators` |
| `templates/jobwork/receipt_list.html` | `Receipts and QC` | `Received from fabricators` |
| `templates/sales/invoice_list.html` | `Sale invoices` | `Bills` |
| `templates/sales/billing.html` | `Barcode billing` | `Quick billing` |
| `templates/sales/creditnote_list.html` | current heading (`Credit notes`) | `Returns from customer` |

`templates/reports/ageing.html` line 4, replace the `<h1>` with:

```html
<h1 class="page-title">{% if kind == "debtors" %}Who owes me{% else %}Whom I owe{% endif %}</h1>
```

and set its `{% block title %}` the same way. Do not touch any `*_print.html` template, form headings, document number prefixes or model `verbose_name`s: printed documents keep Challan, Tax Invoice, Credit Note, Debit Note.

- [ ] **Step 4: Run the whole suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass. Any failure that asserts one of the old headings in the table above: update that assertion to the new text. Any other failure: stop and investigate, it is not expected from this change.

- [ ] **Step 5: Commit**

```bash
git add templates/purchases/grn_list.html templates/purchases/invoice_list.html templates/purchases/debitnote_list.html templates/jobwork/challan_list.html templates/jobwork/receipt_list.html templates/sales/invoice_list.html templates/sales/billing.html templates/sales/creditnote_list.html templates/reports/ageing.html tests/test_navigation.py
git commit -m "UI: list screens use the same plain words as the menu"
```

(Add by name any other test file whose heading assertion was updated in Step 4.)

---

### Task 6: User guide follows the new menu

**Files:** `docs/SETUP_GUIDE.md`

- [ ] **Step 1: Find every menu path in the guide**

Run: `.venv/Scripts/python.exe -m pytest tests/test_help_and_settlement.py -q` first to see the guide tests pass, then search the guide for italic menu paths with the Grep tool, pattern `\*(Masters|Purchases|Sales|Inventory|Production|Accounts|Reports|Admin|Help) →`.

- [ ] **Step 2: Rewrite each path with this mapping**

| Old path prefix | New path |
| --- | --- |
| `Purchases → Purchase orders` | `Buy → Purchase orders` |
| `Purchases → Goods receipt (GRN)` | `Buy → Goods received` |
| `Purchases → Purchase invoices` | `Buy → Supplier bills` |
| `Purchases → Debit notes` | `Buy → Returns to supplier` |
| `Sales → Sale orders` / `Packing and dispatch` | `Sell → Sale orders` / `Sell → Packing and dispatch` |
| `Sales → Sale invoices` | `Sell → Bills` |
| `Sales → Barcode billing` | `Sell → Quick billing (barcode)` |
| `Sales → Credit notes` | `Sell → Returns from customer` |
| `Inventory → Movements → Transfers` | `Stock → Transfers` |
| `Inventory → Movements → Stock journal` / `Opening stock` | `More → Accountant → Stock journal` / `Opening stock` |
| `Inventory → Alerts and labels → X` | `Stock → X` (Low-stock alerts is now `Low stock`) |
| `Inventory → X` (others) | `Stock → X` |
| `Production → Job work → Challans` | `Make → Sent to fabricators` |
| `Production → Job work → Receipts and QC` | `Make → Received from fabricators` |
| `Production → Labour → X` | `Make → X` |
| `Production → Reports → X` | `Reports → X` |
| `Production → Dashboard` | `Make → Production dashboard` |
| `Production → X` (others) | `Make → X` |
| `Accounts → Enter a voucher → Payment` / `Receipt` | `Money → Money paid` / `Money → Money received` |
| `Accounts → Enter a voucher → Contra` / `Journal` | `More → Accountant → Contra` / `Journal` |
| `Accounts → Sales and purchase entries → X` | `More → Accountant → X` |
| `Accounts → All vouchers` | `Money → All entries` |
| `Accounts → Books → Profit and loss` / `Balance sheet` | `Reports → Profit and loss` / `Balance sheet` |
| `Accounts → Books → Ledger statement` | `Money → Party accounts` |
| `Accounts → Books → X` (others), `Accounts → Set up and close → X`, `Accounts → Ledgers` / `Chart of accounts` | `More → Accountant → X` |
| `Reports → Ageing → Receivables ageing` / `Payables ageing` | `Reports → Who owes me` / `Whom I owe` |
| `Admin → Settings → X` / `Admin → X` | `More → Settings → X` |
| `Help → Help and user guide` | `More → Help and user guide` |

`Masters → ...` paths are unchanged. Where the guide's prose (not a path) says "the Barcode billing screen" or "Sale invoices list", use the new screen name; where it describes a printed document, keep the formal name. Add one sentence near the top of the user-guide section: "Home shows the everyday jobs as buttons; the menu on the left holds the same screens grouped as Buy, Make, Sell, Stock and Money, with accountant and settings screens under More."

- [ ] **Step 3: Run the full suite**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: all pass (the guide is rendered by `core/help.py`; its tests check anchors, which this edit does not rename. Do not rename any heading in the guide).

- [ ] **Step 4: Commit**

```bash
git add docs/SETUP_GUIDE.md
git commit -m "Docs: user guide follows the regrouped menu"
```

---

## Done when

- `.venv/Scripts/python.exe -m pytest -q` is green, including the autouse trial-balance and stock reconciliation checks.
- Owner home shows five islands (17 buttons), the attention list and one row of figures; a Production Supervisor sees no money buttons or figures.
- Ctrl+K finds screens by both new labels and old terms (GRN, challan, debit note, credit note).
- No migration was created (`.venv/Scripts/python.exe manage.py makemigrations --check --dry-run` reports no changes).
