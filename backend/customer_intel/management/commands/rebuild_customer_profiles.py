"""
Rebuild customer profile snapshots.

Intended to run nightly (~02:15) from the OS scheduler, alongside the existing
minute-ly `run_due_crm` entry:

    python manage.py rebuild_customer_profiles

By default it enqueues onto the django-tasks worker (`manage.py db_worker`).
Pass --sync to compute inline instead, which is what you want for a first run,
for timing it, and in tests.
"""

import logging
import time

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Rebuild CustomerProfileSnapshot rows for every retail (or one)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--retail-id", type=int, default=None,
            help="Limit the rebuild to a single retail.",
        )
        parser.add_argument(
            "--sync", action="store_true",
            help="Compute inline instead of enqueuing onto the task worker.",
        )
        parser.add_argument(
            "--batch-size", type=int, default=None,
            help="Ledgers per query batch (default 2000).",
        )

    def handle(self, *args, **options):
        from mastersconfig.models import RetailMaster

        retails = RetailMaster.objects.all()
        if options["retail_id"]:
            retails = retails.filter(id=options["retail_id"])

        if not retails.exists():
            self.stdout.write(self.style.WARNING("No matching retail found."))
            return

        for retail in retails:
            if options["sync"]:
                from customer_intel.services.snapshot import BATCH_SIZE, SnapshotBuilder

                started = time.monotonic()
                result = SnapshotBuilder(
                    retail.id, batch_size=options["batch_size"] or BATCH_SIZE,
                ).run()
                elapsed = time.monotonic() - started
                self.stdout.write(
                    f"retail {retail.id} ({retail}): "
                    f"{result['written']} snapshot(s) from {result['customers']} "
                    f"customer(s) in {elapsed:.1f}s — scoring basis "
                    f"{result.get('basis')}, cohort {result.get('cohort_size')}, "
                    f"repeat share {result.get('repeat_share')}"
                )
            else:
                from customer_intel.tasks import rebuild_retail_profiles

                rebuild_retail_profiles.enqueue(retail.id, options["batch_size"])
                self.stdout.write(f"retail {retail.id}: rebuild enqueued")
