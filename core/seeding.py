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
        {"core.company": ["view", "edit"], "inventory.settings": ["view", "edit"], "core.factory": ["view", "create", "edit"],
         "core.user": ["view", "create", "edit"], "core.role": ["view", "create", "edit"],
         "tax.settings": ["view", "edit"]},
        [],
    ),
    "Accountant": (
        "Vouchers, opening balances, books and tax settings",
        {"ledger.chart": ["view", "create", "edit"], "ledger.voucher": ["view", "create", "edit", "cancel"],
         "ledger.opening": ["view", "create"], "ledger.report": ["view"], "ledger.yearend": ["view"], "tax.settings": ["view", "edit"],
         "tax.hsn": ["view", "create", "edit"], "tax.report": ["view"], "masters.party": ["view", "create", "edit"],
         "masters.import": ["view", "create"], "core.period_lock": ["view", "edit"],
         "purchases.invoice": ["view", "create", "edit", "cancel"], "purchases.debitnote": ["view", "create", "edit", "cancel"],
         "purchases.po": ["view"], "purchases.grn": ["view"], "inventory.stock": ["view"],
         "inventory.opening": ["view", "create"], "inventory.transfer": ["view"],
         "inventory.journal": ["view", "create", "cancel"],
         "jobwork.bill": ["view", "create", "edit", "cancel"], "jobwork.rate": ["view", "create", "edit"],
         "jobwork.report": ["view"], "production.dashboard": ["view"], "production.order": ["view"],
         "sales.order": ["view"], "sales.packing": ["view"], "sales.invoice": ["view", "create", "edit", "cancel"],
         "sales.creditnote": ["view", "create", "edit", "cancel"], "sales.settings": ["view", "edit"]},
        list(SENSITIVE_FIELDS),
    ),
    "Purchase Officer": (
        "Purchase orders and vendors",
        {"purchases.po": ["view", "create", "edit"], "purchases.grn": ["view"], "masters.party": ["view", "create", "edit"],
         "masters.material": ["view"], "inventory.stock": ["view"], "inventory.alerts": ["view"], "inventory.reorder": ["view"]},
        [],
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
    "Production Planner": (
        "Production orders and route planning",
        {"production.order": ["view", "create", "edit"], "production.lot": ["view", "create", "edit"],
         "production.dashboard": ["view"], "masters.style": ["view"], "masters.route": ["view"],
         "masters.process": ["view"], "masters.party": ["view"]},
        [],
    ),
    "Production Supervisor": (
        "Bundle issue, receipt and QC",
        {"masters.style": ["view"], "masters.route": ["view"], "masters.process": ["view"],
         "production.order": ["view"], "production.lot": ["view", "edit"], "production.bundle": ["view", "create"],
         "production.move": ["view", "create", "edit"], "production.dashboard": ["view"],
         "jobwork.challan": ["view", "create", "edit"], "jobwork.receipt": ["view", "create", "edit"],
         "jobwork.qc": ["view", "create", "edit"], "jobwork.report": ["view"], "masters.party": ["view"]}, [],
    ),
    "QC Checker": (
        "Accept, reject and send back received work",
        {"jobwork.qc": ["view", "create", "edit"], "jobwork.receipt": ["view"], "production.bundle": ["view"],
         "production.dashboard": ["view"]},
        [],
    ),
    "Cutting Master": (
        "Lay, cutting and bundle tags",
        {"production.cutting": ["view", "create", "edit"], "production.bundle": ["view", "create"],
         "production.order": ["view"], "production.dashboard": ["view"], "inventory.stock": ["view"]},
        [],
    ),
    "Store Keeper": (
        "Fabric and trims receipt, issue and transfers",
        {"masters.material": ["view"], "masters.style": ["view"], "masters.basics": ["view"],
         "purchases.grn": ["view", "create", "edit"], "purchases.po": ["view"], "inventory.stock": ["view"],
         "inventory.transfer": ["view", "create", "edit"], "inventory.labels": ["view", "create"],
         "inventory.opening": ["view", "create"], "purchases.debitnote": ["view"],
         "inventory.reorder": ["view", "create", "edit"], "inventory.alerts": ["view", "edit"],
         "inventory.journal": ["view", "create"]}, [],
    ),
    "Billing Clerk": (
        "Invoices, packing lists and dispatch",
        {"masters.party": ["view", "create", "edit"], "masters.style": ["view"], "masters.pricelist": ["view"],
         "sales.order": ["view", "create", "edit"], "sales.packing": ["view", "create", "edit"],
         "sales.invoice": ["view", "create", "edit"], "sales.creditnote": ["view", "create"],
         "inventory.stock": ["view"], "inventory.labels": ["view", "create"]},
        ["customer_phone"],
    ),
    "Salesperson": (
        "Orders and own customers",
        {"masters.party": ["view"], "masters.style": ["view"], "sales.order": ["view", "create", "edit"]},
        ["customer_phone"]
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
