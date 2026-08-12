"""
Delete engagement events older than a retention window.

`EngagementEvent` grows without bound — every message, catalog open and note.
Retention is much harder to retrofit once a table is large, so this ships in the
first release even though nothing schedules it yet. Wire it into the OS
scheduler (monthly is plenty) when the table starts to matter.

Defaults to keeping 36 months, and refuses to do anything without --apply.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

DEFAULT_KEEP_MONTHS = 36


class Command(BaseCommand):
    help = "Purge EngagementEvent rows older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-months", type=int, default=DEFAULT_KEEP_MONTHS,
            help=f"Retention window in months (default {DEFAULT_KEEP_MONTHS}).",
        )
        parser.add_argument(
            "--retail-id", type=int, default=None,
            help="Limit the purge to a single retail.",
        )
        parser.add_argument(
            "--apply", action="store_true",
            help="Actually delete. Without this the command only reports.",
        )

    def handle(self, *args, **options):
        from customer_intel.models import EngagementEvent

        cutoff = timezone.now() - timedelta(days=options["keep_months"] * 30)
        qs = EngagementEvent.objects.filter(occurred_at__lt=cutoff)
        if options["retail_id"]:
            qs = qs.filter(retail_id=options["retail_id"])

        count = qs.count()
        if not options["apply"]:
            self.stdout.write(
                f"{count} event(s) older than {cutoff:%Y-%m-%d} would be deleted. "
                f"Re-run with --apply to delete them."
            )
            return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Deleted {deleted} engagement event(s) older than {cutoff:%Y-%m-%d}."
        ))
