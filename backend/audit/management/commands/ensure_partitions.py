"""
On Postgres: ensure the next N months of `audit_event` partitions exist.
On SQLite (current project default): no-op — SQLite doesn't support
native partitioning; the `created_month` index + prune_audit cover us.
"""
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create upcoming monthly partitions for audit_event (Postgres only).'

    def add_arguments(self, parser):
        parser.add_argument('--months', type=int, default=3,
                            help='Number of future months to ensure (default 3).')

    def handle(self, *args, months, **options):
        engine = settings.DATABASES['default']['ENGINE']
        if 'postgresql' not in engine:
            self.stdout.write(self.style.WARNING(
                f"Database engine is {engine!r} — partitioning is a Postgres-only "
                "feature. The `created_month` index + `prune_audit` cover retention "
                "on SQLite. No-op."
            ))
            return

        # Postgres native partitioning would be implemented here. Left as a
        # placeholder until the project migrates off SQLite — see the spec
        # at C:/Users/baids/.claude/plans/i-want-you-to-rippling-eclipse.md.
        self.stdout.write(self.style.NOTICE(
            'Postgres partitioning not yet implemented — see project spec.'
        ))
