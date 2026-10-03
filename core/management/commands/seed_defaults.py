from django.core.management.base import BaseCommand

from core.models import Company
from core.seeding import seed_company


class Command(BaseCommand):
    help = "Re-run every registered seeder for the company. Safe to repeat: only missing rows are added."

    def handle(self, *args, **options):
        company = Company.objects.filter(setup_complete=True).first()
        if company is None:
            self.stderr.write("Run the setup wizard first.")
            return
        seed_company(company)
        self.stdout.write(self.style.SUCCESS("Defaults are up to date."))
