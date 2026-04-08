"""
Strips the company-name prefix from system ledger ac_name and display_name.
Safe to re-run (idempotent).

Usage:
    python manage.py rename_system_ledgers
"""
from django.core.management.base import BaseCommand
from mastersconfig.models import CompanyMaster
from contacts.models import Ledger

OPERATIONAL_LABELS = [
    'Sale Discount', 'Discount', 'Round Off', 'Hallmark Charges',
    'Making Receive', 'Gold Conversion', 'Carriage Inward',
    'Making Charge Purchase',
]
MISC_LABELS = [
    'Advance Income Tax', 'Professional Tax (Staff)',
    'Discount Received', 'Freight Outward', 'Bank Charges',
    'Interest Received', 'Interest Paid',
]
TRADING_LABELS = [
    'Gold Purchase', 'Diamond Purchase', 'Emerald Purchase', 'Ruby Purchase',
    'Semi Precious Purchase', 'Old Gold Purchase', 'Standard Bar Purchase',
    'Other Purchase', 'Gold Sales', 'Diamond Sales', 'Emerald Sales',
    'Ruby Sales', 'Semi Precious Sales', 'Standard Bar Sales', 'Other Sales',
]
EQUIPMENT_LABELS = ['Mobile', 'Computer', 'Camera', 'Printer', 'Weighing Machine']

ALL_LABELS = OPERATIONAL_LABELS + MISC_LABELS + TRADING_LABELS + EQUIPMENT_LABELS


def _prefixed_variants(prefix, label):
    """Return all ac_name forms that the old seeding code might have produced."""
    return [
        f"{prefix}_{label.replace(' ', '_')}",
        f"{prefix} {label}",
        f"{prefix}_{label}",
        # older underscored label forms (e.g. Round_Off, Carriage_Inward)
        f"{prefix}_{label.replace(' ', '_').replace('_', '_')}",
    ]


class Command(BaseCommand):
    help = "Rename system ledgers — strip company-name prefix from ac_name and display_name"

    def handle(self, *args, **options):
        total = 0
        for company in CompanyMaster.objects.all():
            prefix = company.company_name
            for label in ALL_LABELS:
                for variant in _prefixed_variants(prefix, label):
                    updated = Ledger.objects.filter(
                        ac_name=variant, is_system=True
                    ).update(ac_name=label, display_name=label)
                    total += updated
                    if updated:
                        self.stdout.write(f"  Renamed: '{variant}' -> '{label}'")

        self.stdout.write(self.style.SUCCESS(f"Done. {total} ledger(s) renamed."))
