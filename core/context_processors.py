from .models import Company, Factory

NAV = [
    ("Home", [("home", "Home", "core.home")]),
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
