from pathlib import Path

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from .help import anchor_for as help_anchor_for
from .models import Company, Factory, RolePermission

class Sub:
    """A fold-away section inside a menu group, so a long group reads as a few headings instead of one long list."""

    def __init__(self, label, items, open_by_default=False):
        self.label, self.items, self.open_by_default = label, items, open_by_default


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

# Record pages that belong to a group but share a URL prefix with another group's screens, so they are named.
DETAIL_PAGES = {
    "Money": ("voucher_detail", "ledger_statement", "ledger_bills"),
}


def _built(url_name):
    """A screen is listed only once its URL exists, so a menu entry never breaks the page."""
    try:
        reverse(url_name)
    except NoReverseMatch:
        return False
    return True


def _menu_perms(user):
    """Every (screen, action) the user's roles grant, read once for the whole menu instead of once per entry.
    None stands for everything (a superuser); the rule is the same as `User.has_screen_perm`."""
    if not user.is_active:
        return set()
    if user.is_superuser:
        return None
    return set(RolePermission.objects.filter(role__users=user).values_list("screen", "action"))


def _allowed(perms, screen):
    """'app.screen' needs view; 'app.screen.create' (or .edit ...) needs that action instead."""
    base, _, action = screen.rpartition(".") if screen.count(".") == 2 else (screen, "", "view")
    return perms is None or (base, action or "view") in perms


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
    perms = _menu_perms(user)
    current = request.resolver_match.url_name if getattr(request, "resolver_match", None) else None

    def visible(entries):
        return [
            {"url_name": e[0], "label": e[1], "current": e[0] == current, "alt": e[3] if len(e) > 3 else ""}
            for e in entries
            if (e[2] == "core.home" or _allowed(perms, e[2])) and _built(e[0])
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
                "exact": any(k["current"] for k in leaves) or current in DETAIL_PAGES.get(title, ()),
                "active": any(request.path.startswith(p) for p in PREFIXES.get(title, ())),
            })
            for i in shown:
                for k in (i["items"] if i.get("sub") else [i]):
                    index.append({"label": k["label"], "group": title, "sub": i["label"] if i.get("sub") else "",
                                  "alt": k["alt"], "url": reverse(k["url_name"])})
    # A page that is itself a menu entry lights only its own group, even when its URL sits under another group's prefix.
    listed = any(g["exact"] for g in groups)
    for g in groups:
        g["active"] = g["exact"] if listed else g["active"]
    company = Company.objects.filter(setup_complete=True).first()
    return {
        "today": today, "asset_v": asset_v,
        "help_anchor": help_anchor_for(request.path),
        "nav_groups": groups, "nav_index": index,
        "company": company,
        "user_factories": Factory.objects.for_user(user).filter(is_active=True),
    }
