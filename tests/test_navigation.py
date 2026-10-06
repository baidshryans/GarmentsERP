"""The menu is grouped by business job, keeps every screen reachable, and search still finds the old trade terms."""
import json
import re

import pytest
from django.test import Client
from django.urls import reverse

from core.context_processors import NAV, flat_items
from core.home_actions import HOME_ACTIONS, home_actions
from core.models import Role
from reports.services.overview import attention_items, build_overview
from tests.conftest import make_user

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


def test_a_party_statement_keeps_the_money_group_lit(company, owner, ledgers):
    html = _client(owner).get(reverse("ledger_statement", args=[ledgers("cash").pk])).content.decode()
    assert re.search(r'<details class="nav-group active" data-group="money"', html)
    assert not re.search(r'<details class="nav-group active" data-group="more"', html)


def test_every_launchpad_button_points_at_a_real_screen():
    for _, _, actions in HOME_ACTIONS:
        for url_name, label, screen, action in actions:
            assert reverse(url_name), label


def test_owner_gets_the_four_islands(company, owner):
    islands = home_actions(owner)
    assert [i["title"] for i in islands] == ["Buy", "Make", "Sell", "Money"]
    assert sum(len(i["actions"]) for i in islands) == 9


def test_launchpad_follows_the_role(company, factory):
    sup = make_user("sup_launch")
    sup.roles.add(Role.objects.get(name="Production Supervisor"))
    sup.allowed_factories.add(factory)
    labels = {a["label"] for i in home_actions(sup) for a in i["actions"]}
    assert "Send to fabricator" in labels
    assert "Money received" not in labels and "Make a bill" not in labels
    assert all(i["actions"] for i in home_actions(sup))          # an island with nothing allowed is dropped


def test_user_with_no_role_gets_no_islands(company):
    assert home_actions(make_user("nobody")) == []


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


class _Role:
    """Stands in for a user: may view only the screens named."""

    def __init__(self, *screens):
        self.screens = screens

    def has_screen_perm(self, screen, action):
        return action == "view" and ("*" in self.screens or screen in self.screens)


def test_attention_lists_only_what_is_waiting_with_a_link_to_fix_it():
    items = attention_items(_figures(production__awaiting_qc=3, purchases__pos_to_approve=1, low_stock=5), _Role("*"))
    assert [(i["count"], i["text"], i["url"]) for i in items] == [
        (3, "receipts from fabricators are waiting to be checked", reverse("receipt_list")),
        (1, "purchase order is waiting for approval", reverse("po_list")),
        (5, "items are below their minimum stock", reverse("stock_alerts")),
    ]


def test_attention_skips_sections_the_role_may_not_see():
    data = _figures()
    data["production"] = data["purchases"] = data["sales"] = data["low_stock"] = None
    assert attention_items(data, _Role("*")) == []


def test_attention_never_links_to_a_screen_the_role_cannot_open():
    waiting = _figures(production__awaiting_qc=1, production__late_lots=2, production__orders_to_release=1,
                       purchases__grn_pending=1, sales__overdue_orders=1)
    urls = [i["url"] for i in attention_items(waiting, _Role("production.dashboard"))]
    assert urls == [reverse("production_dashboard")]
    assert len(attention_items(waiting, _Role("*"))) == 5


def test_every_home_link_opens_for_the_role_that_sees_it(company, factory):
    for role in Role.objects.all():
        user = make_user(f"r{role.pk}")
        user.roles.add(role)
        user.allowed_factories.add(factory)
        c = _client(user)
        html = c.get(reverse("home")).content.decode()
        main = html[html.index('id="content"'):]
        for href in set(re.findall(r'href="(/[^"#]*)"', main)):
            assert c.get(href).status_code != 403, f"{role.name} is shown {href} on home but may not open it"


def test_a_menu_screen_lights_only_its_own_group(company, owner):
    html = _client(owner).get(reverse("journal_list")).content.decode()
    assert re.findall(r'<details class="nav-group active" data-group="([\w-]+)"', html) == ["more"]


def test_overview_carries_the_attention_list(company, owner):
    assert build_overview(owner)["attention"] == []


def test_home_is_a_launchpad(company, owner):
    html = _client(owner).get(reverse("home")).content.decode()
    assert "What do you want to do?" in html
    for label in ("Order fabric or material", "Send to fabricator", "Make a bill", "Money received"):
        assert label in html
    assert f'href="{reverse("grn_new")}"' in html
    assert "Nothing is waiting on you" in html
    assert "Posted vouchers" not in html and "Active factories" not in html and "Recent vouchers" not in html


def test_home_for_a_user_with_no_role_still_opens(company):
    r = _client(make_user("norole")).get(reverse("home"))
    assert r.status_code == 200 and "What do you want to do?" not in r.content.decode()



@pytest.mark.parametrize("url_name,title", [
    ("grn_list", "Goods received"), ("invoice_list", "Supplier bills"), ("debitnote_list", "Returns to supplier"),
    ("challan_list", "Sent to fabricators"), ("receipt_list", "Received from fabricators"),
    ("saleinvoice_list", "Bills"), ("billing", "Quick billing"), ("salecn_list", "Returns from customer"),
    ("ageing_debtors", "Who owes me"), ("ageing_creditors", "Whom I owe"),
])
def test_page_heading_matches_the_menu_wording(company, owner, url_name, title):
    html = _client(owner).get(reverse(url_name)).content.decode()
    assert re.search(r'<h1 class="page-title">\s*' + re.escape(title) + r"\s*</h1>", html), url_name


def test_the_menu_reads_the_users_permissions_once_not_once_per_entry(company, accountant, django_assert_max_num_queries):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    c = _client(accountant)
    with CaptureQueriesContext(connection) as seen:
        html = c.get(reverse("help")).content.decode()
    asked = [q["sql"] for q in seen.captured_queries if "rolepermission" in q["sql"].lower()]
    assert len(asked) <= 3, len(asked)          # the menu's one read, plus the page's own check
    assert "Supplier bills" in html and "Reset database" not in html      # and the menu is still filtered by role
