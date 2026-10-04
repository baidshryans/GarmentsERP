from pathlib import Path

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from .models import Company, Factory

class Sub:
    """A fold-away section inside a menu group, so a long group reads as a few headings instead of one long list."""

    def __init__(self, label, items, open_by_default=False):
        self.label, self.items, self.open_by_default = label, items, open_by_default


NAV = [
    ("Home", [("home", "Home", "core.home")]),
    ("Masters", [
        ("style_list", "Styles", "masters.style"),
        ("material_list", "Materials", "masters.material"),
        ("party_list", "Parties", "masters.party"),
        ("pricelist_list", "Price lists", "masters.pricelist"),
        Sub("Setup", [
            ("route_list", "Routes", "masters.route"),
            ("process_list", "Processes", "masters.process"),
            ("unit_list", "Units, sizes, colours", "masters.basics"),
            ("hsn_list", "HSN and GST slabs", "tax.hsn"),
        ]),
        ("excel_import", "Import from Excel", "masters.import"),
    ]),
    ("Purchases", [
        ("po_list", "Purchase orders", "purchases.po"),
        ("grn_list", "Goods receipt (GRN)", "purchases.grn"),
        ("invoice_list", "Purchase invoices", "purchases.invoice"),
        ("debitnote_list", "Debit notes", "purchases.debitnote"),
    ]),
    ("Sales", [
        ("saleorder_list", "Sale orders", "sales.order"),
        ("packing_list", "Packing and dispatch", "sales.packing"),
        ("saleinvoice_list", "Sale invoices", "sales.invoice"),
        ("billing", "Barcode billing", "sales.invoice.create"),
        ("salecn_list", "Credit notes", "sales.creditnote"),
    ]),
    ("Inventory", [
        ("stock_enquiry", "Stock", "inventory.stock"),
        ("roll_list", "Fabric rolls", "inventory.stock"),
        Sub("Movements", [
            ("transfer_list", "Transfers", "inventory.transfer"),
            ("journal_list", "Stock journal", "inventory.journal"),
            ("opening_stock", "Opening stock", "inventory.opening"),
        ]),
        Sub("Alerts and labels", [
            ("reorder_levels", "Reorder levels", "inventory.reorder"),
            ("stock_alerts", "Low-stock alerts", "inventory.alerts"),
            ("tag_print", "Print tags", "inventory.labels"),
        ]),
    ]),
    ("Production", [
        ("production_dashboard", "Dashboard", "production.dashboard"),
        ("order_list", "Production orders", "production.order"),
        ("move_bundles", "Move bundles", "production.move"),
        Sub("Job work", [
            ("challan_list", "Challans", "jobwork.challan"),
            ("receipt_list", "Receipts and QC", "jobwork.receipt"),
        ]),
        Sub("Labour", [
            ("bill_list", "Labour bills", "jobwork.bill"),
            ("rate_list", "Labour rates", "jobwork.rate"),
        ]),
        Sub("Reports", [
            ("job_reports", "Fabricator reports", "jobwork.report"),
            ("daily_summary", "Daily summary", "jobwork.report"),
        ]),
    ]),
    ("Accounts", [
        ("chart_of_accounts", "Chart of accounts", "ledger.chart"),
        ("ledger_list", "Ledgers", "ledger.chart"),
        Sub("Enter a voucher", [
            ("voucher_payment", "Payment", "ledger.voucher.create"),
            ("voucher_receipt", "Receipt", "ledger.voucher.create"),
            ("voucher_contra", "Contra", "ledger.voucher.create"),
            ("voucher_journal", "Journal", "ledger.voucher.create"),
        ], open_by_default=True),
        Sub("Sales and purchase entries", [
            ("voucher_sales", "Sales voucher", "ledger.voucher.create"),
            ("voucher_purchase", "Purchase voucher", "ledger.voucher.create"),
            ("voucher_debit_note", "Debit note", "ledger.voucher.create"),
            ("voucher_credit_note", "Credit note", "ledger.voucher.create"),
        ]),
        ("voucher_list", "All vouchers", "ledger.voucher"),
        Sub("Books", [
            ("trial_balance", "Trial balance", "ledger.report"),
            ("profit_loss", "Profit and loss", "ledger.report"),
            ("balance_sheet", "Balance sheet", "ledger.report"),
            ("day_book", "Day book", "ledger.report"),
            ("ledger_book", "Ledger book", "ledger.report"),
            ("ledger_pick", "Ledger statement", "ledger.report"),
        ]),
        Sub("Set up and close", [
            ("opening_balances", "Opening balances", "ledger.opening"),
            ("period_locks", "Period locks", "core.period_lock"),
            ("year_end", "Year-end", "ledger.yearend"),
        ]),
    ]),
    ("Reports", [
        ("sales_report", "Sales", "sales.invoice"),
        ("purchase_report", "Purchases", "purchases.invoice"),
        ("finished_stock", "Finished stock", "inventory.stock"),
        Sub("Ageing", [
            ("ageing_debtors", "Receivables ageing", "ledger.report"),
            ("ageing_creditors", "Payables ageing", "ledger.report"),
        ]),
        Sub("GST", [
            ("gstr1", "GSTR-1 data", "tax.report"),
            ("gstr3b", "GSTR-3B summary", "tax.report"),
            ("tax_register", "Tax register", "tax.report"),
        ]),
    ]),
    ("Admin", [
        ("factory_list", "Factories", "core.factory"),
        ("user_list", "Users", "core.user"),
        ("role_list", "Roles", "core.role"),
        Sub("Settings", [
            ("tax_settings", "Tax settings", "tax.settings"),
            ("inventory_settings", "Inventory settings", "inventory.settings"),
            ("sales_settings", "Sales settings", "sales.settings"),
        ]),
    ]),
]


def flat_items(items):
    """Every (url_name, label, screen) in a group, with the fold-away sections opened out."""
    for it in items:
        if isinstance(it, Sub):
            yield from it.items
        else:
            yield it


# A group is "current" when the page is one of its screens or lives under one of its URL prefixes
# (a lot page, a challan, a style are not menu entries but belong to Production, Job work, Masters).
ICONS = {
    "Home": "i-home", "Masters": "i-masters", "Purchases": "i-purchases", "Sales": "i-sales", "Inventory": "i-inventory",
    "Production": "i-production", "Accounts": "i-accounts", "Reports": "i-reports", "Admin": "i-admin",
}

PREFIXES = {
    "Masters": ("/masters/", "/import/"),
    "Purchases": ("/purchases/",),
    "Sales": ("/sales/",),
    "Inventory": ("/inventory/",),
    "Production": ("/production/", "/jobwork/"),
    "Accounts": ("/accounts/chart", "/accounts/vouchers", "/accounts/opening", "/accounts/trial", "/accounts/ledgers", "/accounts/profit",
                 "/accounts/balance", "/accounts/day-book", "/accounts/ageing", "/accounts/period", "/accounts/year"),
    "Reports": ("/reports/",),
    "Admin": ("/factories/", "/users/", "/roles/", "/tax/", "/settings/"),
}


def _built(url_name):
    """A screen is listed only once its URL exists, so a menu entry never breaks the page."""
    try:
        reverse(url_name)
    except NoReverseMatch:
        return False
    return True


def _allowed(user, screen):
    """'app.screen' needs view; 'app.screen.create' (or .edit ...) needs that action instead."""
    base, _, action = screen.rpartition(".") if screen.count(".") == 2 else (screen, "", "view")
    return user.has_screen_perm(base, action or "view")


def _asset_version():
    """Newest modification time of our own css/js, so a changed file is never served from a stale browser cache."""
    root = Path(settings.BASE_DIR) / "static"
    stamps = [f.stat().st_mtime for sub in ("css", "js") for f in (root / sub).glob("*") if f.is_file()]
    return str(int(max(stamps))) if stamps else "0"


def app_shell(request):
    """Navigation rail and company name for the base layout. Only built screens are listed."""
    user = request.user
    today = timezone.localdate().isoformat()   # ISO text, ready for <input type="date">
    asset_v = _asset_version()
    if not user.is_authenticated:
        return {"today": today, "asset_v": asset_v}
    groups, index = [], []
    current = request.resolver_match.url_name if getattr(request, "resolver_match", None) else None

    def visible(entries):
        return [
            {"url_name": u, "label": label, "current": u == current}
            for u, label, screen in entries
            if (screen == "core.home" or _allowed(user, screen)) and _built(u)
        ]

    for title, items in NAV:
        key = title.lower().replace(" ", "-")
        shown = []
        for it in items:
            if isinstance(it, Sub):
                kids = visible(it.items)
                if kids:
                    shown.append({"sub": True, "label": it.label, "items": kids, "key": f"{key}/{it.label.lower().replace(' ', '-')}",
                                  "active": any(k["current"] for k in kids), "default_open": it.open_by_default})
            else:
                shown.extend(visible([it]))
        if shown:
            leaves = [k for i in shown for k in (i["items"] if i.get("sub") else [i])]
            groups.append({
                "title": title, "items": shown, "key": key, "icon": ICONS.get(title, "i-masters"),
                "active": any(k["current"] for k in leaves) or any(request.path.startswith(p) for p in PREFIXES.get(title, ())),
            })
            for i in shown:
                for k in (i["items"] if i.get("sub") else [i]):
                    index.append({"label": k["label"], "group": title, "sub": i["label"] if i.get("sub") else "",
                                  "url": reverse(k["url_name"])})
    company = Company.objects.filter(setup_complete=True).first()
    return {
        "today": today, "asset_v": asset_v,
        "nav_groups": groups, "nav_index": index,
        "company": company,
        "user_factories": Factory.objects.for_user(user).filter(is_active=True),
    }
