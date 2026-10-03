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
    "tax.hsn": "HSN codes and GST slabs",
    "masters.basics": "Units, sizes, colours, products",
    "masters.material": "Materials (fabric, trims)",
    "masters.style": "Styles and SKUs",
    "masters.bom": "Bill of materials",
    "masters.process": "Processes",
    "masters.route": "Route templates",
    "masters.party": "Parties (customers, vendors, fabricators)",
    "masters.pricelist": "Price lists and customer rates",
    "masters.import": "Excel import",
    "purchases.po": "Purchase orders",
    "purchases.grn": "Goods receipt (GRN) and QC",
    "purchases.invoice": "Purchase invoices",
    "purchases.debitnote": "Debit notes",
    "inventory.stock": "Stock enquiry",
    "inventory.transfer": "Stock transfers",
    "inventory.opening": "Opening stock",
    "inventory.labels": "Labels and tags",
    "inventory.settings": "Inventory and purchase settings",
}


def register_screens(screens: dict):
    SCREENS.update(screens)
