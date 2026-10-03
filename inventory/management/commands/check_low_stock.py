from django.core.management.base import BaseCommand

from core.models import Company
from inventory.services.alerts import check_low_stock


class Command(BaseCommand):
    help = ("Raise a low-stock alert for each item below its minimum that has none open, and close the alerts of items that "
            "recovered. Safe to run often; schedule it (for example every hour) with cron or Task Scheduler.")

    def handle(self, *args, **options):
        company = Company.objects.filter(setup_complete=True).first()
        if company is None:
            self.stderr.write("Run the setup wizard first.")
            return
        raised = check_low_stock(company)
        for a in raised:
            where = a.factory.code if a.factory_id else "all factories"
            self.stdout.write(f"LOW {a.item} at {where}: {a.qty_at_alert.normalize():f} (minimum {a.min_qty.normalize():f})")
        self.stdout.write(self.style.SUCCESS(f"{len(raised)} new alert{'s' if len(raised) != 1 else ''}."))
