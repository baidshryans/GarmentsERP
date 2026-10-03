"""Registry of screen codes that role permissions refer to (E1.6).

Each app adds its screens here as it is built. Permissions are rows in the database
(RolePermission); this registry only supplies the list of valid screens and labels.
"""

SCREENS = {
    "core.company": "Company settings",
    "core.factory": "Factories and locations",
    "core.user": "Users",
    "core.role": "Roles and permissions",
    "core.period_lock": "Period locks",
    "ledger.chart": "Chart of accounts",
    "ledger.voucher": "Vouchers",
    "ledger.opening": "Opening balances",
    "ledger.report": "Books and trial balance",
    "tax.settings": "Tax settings",
}


def register_screens(screens: dict):
    SCREENS.update(screens)
