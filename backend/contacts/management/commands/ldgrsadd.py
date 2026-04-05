from django.core.management.base import BaseCommand
from contacts.models import Ledger

class Command(BaseCommand):
    help = 'Creates default ledger accounts if they do not exist'

    def handle(self, *args, **kwargs):
        missing_accounts = [
            "OUTPUT CGST",
            "OUTPUT SGST",
            "OUTPUT IGST",
            "INPUT CGST",
            "INPUT SGST",
            "INPUT IGST",
            "TCS",
            "Making Charge",
            "DISCOUNT",
            "CASH",
            "Purchase Ledger 1",
            "HALLMARK CHARGES",
            "FREIGHT CHARGES",
            "ROUND OFF",
        ]

        for account_name in missing_accounts:
            ledger, created = Ledger.objects.get_or_create(
                ac_name=account_name,
                defaults={
                    "display_name": account_name,
                    "type": "OTH",  # Adjust based on category
                    "mobile1": account_name,
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created Ledger: {account_name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Ledger already exists: {account_name}"))
