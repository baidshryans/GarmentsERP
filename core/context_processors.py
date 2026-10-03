from .models import Company, Factory

NAV = [
    ("Home", [("home", "Home", "core.home")]),
    ("Masters", [
        ("style_list", "Styles", "masters.style"),
        ("material_list", "Materials", "masters.material"),
        ("party_list", "Parties", "masters.party"),
        ("pricelist_list", "Price lists", "masters.pricelist"),
        ("route_list", "Routes", "masters.route"),
        ("process_list", "Processes", "masters.process"),
        ("unit_list", "Units, sizes, colours", "masters.basics"),
        ("hsn_list", "HSN and GST slabs", "tax.hsn"),
        ("excel_import", "Import from Excel", "masters.import"),
    ]),
    ("Purchases", [
        ("po_list", "Purchase orders", "purchases.po"),
        ("grn_list", "Goods receipt (GRN)", "purchases.grn"),
        ("invoice_list", "Purchase invoices", "purchases.invoice"),
        ("debitnote_list", "Debit notes", "purchases.debitnote"),
    ]),
    ("Inventory", [
        ("stock_enquiry", "Stock", "inventory.stock"),
        ("roll_list", "Fabric rolls", "inventory.stock"),
        ("transfer_list", "Transfers", "inventory.transfer"),
        ("opening_stock", "Opening stock", "inventory.opening"),
        ("tag_print", "Print tags", "inventory.labels"),
    ]),
    ("Production", [
        ("production_dashboard", "Dashboard", "production.dashboard"),
        ("order_list", "Production orders", "production.order"),
        ("move_bundles", "Move bundles", "production.move"),
    ]),
    ("Job work", [
        ("challan_list", "Challans", "jobwork.challan"),
        ("receipt_list", "Receipts and QC", "jobwork.receipt"),
        ("bill_list", "Labour bills", "jobwork.bill"),
        ("rate_list", "Labour rates", "jobwork.rate"),
        ("job_reports", "Fabricator reports", "jobwork.report"),
    ]),
    ("Accounts", [
        ("chart_of_accounts", "Chart of accounts", "ledger.chart"),
        ("voucher_list", "Vouchers", "ledger.voucher"),
        ("opening_balances", "Opening balances", "ledger.opening"),
        ("trial_balance", "Trial balance", "ledger.report"),
    ]),
    ("Admin", [
        ("factory_list", "Factories", "core.factory"),
        ("user_list", "Users", "core.user"),
        ("role_list", "Roles", "core.role"),
        ("tax_settings", "Tax settings", "tax.settings"),
        ("inventory_settings", "Inventory settings", "inventory.settings"),
    ]),
]


def app_shell(request):
    """Navigation rail and company name for the base layout. Only built screens are listed."""
    user = request.user
    if not user.is_authenticated:
        return {}
    groups = []
    for title, items in NAV:
        visible = [
            {"url_name": u, "label": label}
            for u, label, screen in items
            if screen == "core.home" or user.has_screen_perm(screen, "view")
        ]
        if visible:
            groups.append({"title": title, "items": visible})
    company = Company.objects.filter(setup_complete=True).first()
    return {
        "nav_groups": groups,
        "company": company,
        "user_factories": Factory.objects.for_user(user).filter(is_active=True),
    }
