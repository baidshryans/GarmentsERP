"""Restore the system to its state at a given timestamp.

Usage:
    python manage.py restore_to_point --timestamp 2026-05-04T14:00 [--retail R001] [--dry-run]
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_aware


class Command(BaseCommand):
    help = "Restore every tracked row to its state at a given timestamp."

    def add_arguments(self, parser):
        parser.add_argument('--timestamp', required=True, help='ISO 8601 timestamp')
        parser.add_argument('--retail', help='Limit restore to one retail_code (optional)')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from common.restore import restore_to_point
        from mastersconfig.models import RetailMaster

        ts = parse_datetime(options['timestamp'])
        if ts is None:
            raise CommandError("--timestamp must be ISO 8601")
        if not is_aware(ts):
            ts = make_aware(ts)

        retail = None
        if options.get('retail'):
            try:
                retail = RetailMaster.objects.get(retail_code=options['retail'])
            except RetailMaster.DoesNotExist:
                raise CommandError(f"Retail {options['retail']} not found")

        try:
            summary = restore_to_point(ts, retail=retail, dry_run=options['dry_run'])
        except Exception as exc:
            raise CommandError(str(exc))

        verb = 'DRY RUN' if options['dry_run'] else 'APPLIED'
        self.stdout.write(self.style.SUCCESS(
            f"{verb}: timestamp={ts.isoformat()} retail={retail.retail_code if retail else 'all'}"
        ))
        self.stdout.write(
            f"  creates={summary.creates}, updates={summary.updates}, deletes={summary.deletes}"
        )
        if summary.blocked:
            self.stdout.write(self.style.WARNING("  Blocked:"))
            for b in summary.blocked:
                self.stdout.write(f"    {b}")
        if summary.affected_models:
            self.stdout.write(f"  Affected models: {len(summary.affected_models)}")
