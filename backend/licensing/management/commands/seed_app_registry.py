"""
Seed the AppRegistry with all ERP modules.
Safe to re-run — uses update_or_create on the code field.
"""
from django.core.management.base import BaseCommand
from django.db import transaction


APPS = [
    # code, name, django_app_label, icon, is_core, monthly_price, sort_order, description, nav_group_keys
    (
        "mastersconfig",
        "Masters & Setup",
        "mastersconfig",
        "Settings",
        True, 0, 10,
        "Company, branch, GSTIN, retail, fiscal year, HSN, items, and all master configuration.",
        ["navMain0"],
    ),
    (
        "contacts",
        "CRM & Contacts",
        "contacts",
        "Heart",
        True, 0, 20,
        "Customer ledgers, supplier ledgers, and CRM occasion tracking.",
        ["navCRM", "navCRMOccasions"],
    ),
    (
        "accounting",
        "Financial Accounting",
        "accounting",
        "Calculator",
        True, 0, 30,
        "Journal vouchers, ledger statements, trial balance, P&L, balance sheet, GST registers.",
        ["navMain4"],
    ),
    (
        "goldrates",
        "Gold Rates",
        "goldrates",
        "DollarSign",
        True, 0, 40,
        "Daily gold and silver rate management used across sales, purchase, and valuation.",
        [],
    ),
    (
        "userauth",
        "Users & Roles",
        "userauth",
        "Users",
        True, 0, 50,
        "User accounts, role-based permissions, audit logs, and system settings.",
        [],
    ),
    (
        "sales",
        "Sales & Billing",
        "sales",
        "ShoppingCart",
        False, 999, 60,
        "Sales vouchers, sales returns, approvals, customer orders, and salesperson commission reports.",
        ["navMain2"],
    ),
    (
        "purchase",
        "Purchases",
        "purchase",
        "ReceiptText",
        False, 499, 70,
        "Purchase vouchers, purchase returns, purchase approvals, and purchase orders.",
        ["navPurchases"],
    ),
    (
        "manufacturing",
        "Manufacturing",
        "manufacturing",
        "Hammer",
        False, 799, 80,
        "Karigar job work, gold/stone issues, hallmark, refinery, and repair job cards.",
        ["navMain"],
    ),
    (
        "inventory",
        "Inventory",
        "inventory",
        "Package",
        False, 499, 90,
        "Barcode management, stock transfers, stock journals, and inventory reports.",
        ["navMain3"],
    ),
    (
        "ai_layer",
        "AI Assistant",
        "ai_layer",
        "Sparkles",
        False, 299, 100,
        "Natural-language queries and AI-powered insights across your ERP data.",
        ["navMainAI"],
    ),
]


class Command(BaseCommand):
    help = "Seed AppRegistry with all ERP module definitions."

    def handle(self, *args, **kwargs):
        from licensing.models import AppRegistry

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for (
                code, name, app_label, icon, is_core,
                monthly_price, sort_order, description, nav_group_keys
            ) in APPS:
                _, created = AppRegistry.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "django_app_label": app_label,
                        "icon": icon,
                        "is_core": is_core,
                        "monthly_price": monthly_price,
                        "sort_order": sort_order,
                        "description": description,
                        "nav_group_keys": nav_group_keys,
                        "is_active": True,
                    },
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"App registry seeded: {created_count} created, {updated_count} updated."
            )
        )
