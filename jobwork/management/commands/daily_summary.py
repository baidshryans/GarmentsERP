from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Factory
from jobwork.services import summary


class Command(BaseCommand):
    help = ("Build the daily fabricator summary for every active factory (default: today). Schedule it at the time the owner "
            "wants it, for example 18:00, with cron or Task Scheduler. Safe to repeat: the day is replaced.")

    def add_arguments(self, parser):
        parser.add_argument("--date", help="YYYY-MM-DD; defaults to today")

    def handle(self, *args, **options):
        try:
            on_date = date.fromisoformat(options["date"]) if options.get("date") else timezone.localdate()
        except ValueError:
            raise CommandError("Use --date YYYY-MM-DD.")
        for factory in Factory.objects.filter(is_active=True):
            s = summary.build_summary(factory, on_date)
            self.stdout.write(summary.as_text(s))
        self.stdout.write(self.style.SUCCESS(f"Summary built for {on_date}."))
