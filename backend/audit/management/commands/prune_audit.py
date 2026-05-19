"""
Apply AUDIT_RETENTION policy by deleting old AuditEvent rows.

Per-action retention is configured in settings.AUDIT_RETENTION (a dict of
action → timedelta). LOGIN/LOGIN_FAILED/LOGOUT are typically short-lived;
CREATE/UPDATE/DELETE/RESTORE are kept for years (compliance).

For SQLite this is a row-level DELETE. On Postgres, an analogous command
(ensure_partitions + DROP PARTITION) is preferable for old months — both
strategies leave the same AuditEvent semantics intact.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.timezone import now

from audit.models import AuditEvent


DEFAULT_RETENTION = {
    'LOGIN':         timedelta(days=180),
    'LOGOUT':        timedelta(days=180),
    'LOGIN_FAILED':  timedelta(days=90),
    'CREATE':        timedelta(days=365 * 7),
    'UPDATE':        timedelta(days=365 * 7),
    'DELETE':        timedelta(days=365 * 7),
    'RESTORE':       timedelta(days=365 * 7),
    'BULK':          timedelta(days=365 * 7),
    'CUSTOM':        timedelta(days=365 * 7),
}


class Command(BaseCommand):
    help = 'Delete AuditEvent rows older than the configured retention.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, dry_run, **options):
        retention = {**DEFAULT_RETENTION, **getattr(settings, 'AUDIT_RETENTION', {})}
        nowt = now()
        total = 0
        for action, delta in retention.items():
            cutoff = nowt - delta
            qs = AuditEvent.objects.filter(action=action, timestamp__lt=cutoff)
            count = qs.count()
            if not count:
                continue
            self.stdout.write(f'[{action}] cutoff={cutoff.isoformat()}  rows={count}')
            if not dry_run:
                qs.delete()
            total += count
        self.stdout.write(self.style.SUCCESS(f'Done. {"Would delete" if dry_run else "Deleted"} {total} rows.'))
