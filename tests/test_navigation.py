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
