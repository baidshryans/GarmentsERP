"""Backfill per-enrollment scheme sub-ledgers and repoint legacy voucher credit legs."""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Create per-enrollment scheme-advances sub-ledgers and migrate historical balances."

    def handle(self, *args, **opts):
        from goldscheme.models import SchemeEnrollment, SchemePayment
        from goldscheme.services.ledgers import get_or_create_enrollment_liability_ledger
        from accounting.models import VoucherDetail

        created, repointed = 0, 0
        for enr in SchemeEnrollment.objects.all():
            with transaction.atomic():
                had = bool(enr.liability_ledger_id)
                sub = get_or_create_enrollment_liability_ledger(enr)
                if not had:
                    created += 1
                # Repoint legacy SCHM credit legs from the shared pool to this sub-ledger.
                payment_vouchers = list(SchemePayment.objects.filter(
                    enrollment=enr, voucher__isnull=False
                ).values_list('voucher_id', flat=True))
                legs = VoucherDetail.objects.filter(
                    voucher_main_id__in=payment_vouchers, credit__gt=0,
                ).exclude(account_id=sub.id)
                for leg in legs:
                    leg.account = sub
                    leg.save(update_fields=['account'])
                    repointed += 1
        self.stdout.write(self.style.SUCCESS(
            f"Backfill complete: {created} sub-ledgers created, {repointed} credit legs repointed."
        ))
