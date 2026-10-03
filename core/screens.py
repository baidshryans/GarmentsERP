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
    "ledger.yearend": "Year-end close",
    "tax.settings": "Tax settings",
    "tax.hsn": "HSN codes and GST slabs",
    "tax.report": "GST and TDS returns",
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
    "inventory.reorder": "Reorder levels",
    "inventory.journal": "Stock journal",
    "inventory.alerts": "Low-stock alerts",
    "production.order": "Production orders",
    "production.lot": "Lots and route planning",
    "production.cutting": "Fabric issue and cutting",
    "production.bundle": "Bundles and QR tags",
    "production.move": "Move bundles between stages",
    "production.dashboard": "Production dashboard and tracking",
    "jobwork.challan": "Job work challans",
    "jobwork.receipt": "Job work receipts",
    "jobwork.qc": "QC of received work",
    "jobwork.rate": "Labour rates",
    "jobwork.bill": "Labour bills",
    "jobwork.report": "Fabricator ledger and reports",
    "sales.order": "Sale orders",
    "sales.packing": "Packing lists and dispatch",
    "sales.invoice": "Sale invoices and barcode billing",
    "sales.creditnote": "Sales credit notes",
    "sales.discount": "Discount above the limit",
    "sales.settings": "Sales settings",
}


def register_screens(screens: dict):
    SCREENS.update(screens)
