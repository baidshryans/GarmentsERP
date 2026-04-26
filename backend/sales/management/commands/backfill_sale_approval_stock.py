from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import BarcodeMain
from sales.models import SalesApprovalItem


class Command(BaseCommand):
    help = (
        "One-time backfill: any barcode currently sitting on an open Sale Approval "
        "(SalesApprovalItem.ret_status=False) is taken out of stock "
        "(BarcodeMain.stk_status=False) so the strict approval-stock invariant holds."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Report counts only; do not write changes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        open_barcode_ids = list(
            SalesApprovalItem.objects
            .filter(ret_status=False, barcode__isnull=False)
            .values_list('barcode_id', flat=True)
            .distinct()
        )

        target_qs = BarcodeMain.objects.filter(id__in=open_barcode_ids, stk_status=True)
        target_count = target_qs.count()
        already_off  = len(open_barcode_ids) - target_count

        self.stdout.write(self.style.NOTICE(
            f"Found {len(open_barcode_ids)} barcode(s) on open approvals — "
            f"{target_count} currently in stock, {already_off} already out."
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes written."))
            return

        if target_count:
            updated = target_qs.update(stk_status=False)
            self.stdout.write(self.style.SUCCESS(
                f"Set stk_status=False on {updated} barcode(s)."
            ))
        else:
            self.stdout.write("Nothing to update.")
