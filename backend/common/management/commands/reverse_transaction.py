"""Undo every historical row tagged with a single transaction UUID.

Usage:
    python manage.py reverse_transaction --txn-id <uuid> [--dry-run]
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Undo every change written during one HTTP request."

    def add_arguments(self, parser):
        parser.add_argument('--txn-id', required=True, help='history_transaction_id (UUID)')
        parser.add_argument('--dry-run', action='store_true', help='Preview only')

    def handle(self, *args, **options):
        from common.restore import reverse_transaction
        try:
            summary = reverse_transaction(options['txn_id'], dry_run=options['dry_run'])
        except Exception as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS(
            f"{'DRY RUN' if options['dry_run'] else 'APPLIED'}: "
            f"creates={summary.creates}, updates={summary.updates}, deletes={summary.deletes}"
        ))
        if summary.blocked:
            self.stdout.write(self.style.WARNING("Blocked entries:"))
            for b in summary.blocked:
                self.stdout.write(f"  {b}")
        if summary.affected_models:
            self.stdout.write(f"Affected models: {', '.join(summary.affected_models)}")
