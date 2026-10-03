"""Registry of seeders run by the setup wizard (SYS-02 to SYS-04) and by `manage.py seed_defaults`.

Every app registers its seeder here; each seeder must be idempotent (create what is missing,
never overwrite what an admin edited). Masters seeders (units, sizes, processes, GST slabs)
register themselves when the masters app is built.
"""
from django.db import transaction

from core.constants import SENSITIVE_FIELDS
from core.models import FieldPermission, Role, RolePermission
from core.screens import SCREENS

_SEEDERS = []


def register_seeder(name, fn, order=100):
    if not any(n == name for _, n, _ in _SEEDERS):
        _SEEDERS.append((order, name, fn))
        _SEEDERS.sort(key=lambda s: (s[0], s[1]))


@transaction.atomic
def seed_company(company):
    for _, _, fn in list(_SEEDERS):
        fn(company)


ALL_ACTIONS = ["view", "create", "edit", "cancel", "approve"]

# role -> (description, {screen prefix or code: actions}, sensitive fields)
SYSTEM_ROLES = {
    "Owner": ("Approvals, dashboards and everything else", {"*": ALL_ACTIONS}, list(SENSITIVE_FIELDS)),
    "Administrator": (
        "Company, factories, users and roles. Cannot post transactions.",
        {"core.company": ["view", "edit"], "core.factory": ["view", "create", "edit"],
         "core.user": ["view", "create", "edit"], "core.role": ["view", "create", "edit"],
         "tax.settings": ["view", "edit"]},
        [],
    ),
    "Accountant": (
        "Vouchers, opening balances, books and tax settings",
        {"ledger.chart": ["view", "create", "edit"], "ledger.voucher": ["view", "create", "edit", "cancel"],
         "ledger.opening": ["view", "create"], "ledger.report": ["view"], "tax.settings": ["view", "edit"],
         "tax.hsn": ["view", "create", "edit"], "masters.party": ["view", "create", "edit"],
         "masters.import": ["view", "create"],
         "core.period_lock": ["view", "edit"]},
        list(SENSITIVE_FIELDS),
    ),
    "Merchandiser": (
        "Styles, SKUs, BOMs, routes and materials",
        {"masters.style": ["view", "create", "edit"], "masters.bom": ["view", "create", "edit"],
         "masters.material": ["view", "create", "edit"], "masters.process": ["view", "create", "edit"],
         "masters.route": ["view", "create", "edit"], "masters.basics": ["view", "create", "edit"],
         "masters.pricelist": ["view", "create", "edit"], "masters.party": ["view"], "tax.hsn": ["view"],
         "masters.import": ["view", "create"]},
        [],
    ),
    "Production Supervisor": (
        "Bundle issue, receipt and QC",
        {"masters.style": ["view"], "masters.route": ["view"], "masters.process": ["view"]}, [],
    ),
    "Cutting Master": ("Lay, cutting and bundle tags", {}, []),
    "Store Keeper": (
        "Fabric and trims receipt, issue and transfers",
        {"masters.material": ["view"], "masters.style": ["view"], "masters.basics": ["view"]}, [],
    ),
    "Billing Clerk": (
        "Invoices, packing lists and dispatch",
        {"masters.party": ["view", "create", "edit"], "masters.style": ["view"], "masters.pricelist": ["view"]},
        ["customer_phone"],
    ),
    "Salesperson": (
        "Orders and own customers", {"masters.party": ["view"], "masters.style": ["view"]}, ["customer_phone"]
    ),
    "Fabricator": ("Own bundles and earnings on the mobile app", {}, []),
}


@transaction.atomic
def seed_roles(company=None):
    for name, (description, grants, fields) in SYSTEM_ROLES.items():
        role, _ = Role.objects.get_or_create(name=name, defaults={"description": description, "is_system": True})
        for screen, actions in grants.items():
            targets = list(SCREENS) if screen == "*" else [screen]
            for target in targets:
                for action in actions:
                    RolePermission.objects.get_or_create(role=role, screen=target, action=action)
        for field in fields:
            FieldPermission.objects.get_or_create(role=role, field_key=field)


register_seeder("roles", seed_roles, order=10)
