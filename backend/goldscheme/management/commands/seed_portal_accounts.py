from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from contacts.models import Ledger
from goldscheme.models import CustomerPortalCredential, CustomerPortalAccount


class Command(BaseCommand):
    help = "One-time: create CustomerPortalAccount rows from existing credentials, " \
           "linking ledgers by current mobile match. Idempotent. Use --apply to write."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist changes")

    @transaction.atomic
    def handle(self, *args, **opts):
        apply = opts["apply"]
        created = linked = skipped = 0
        for cred in CustomerPortalCredential.objects.select_related("ledger"):
            led = cred.ledger
            email = (getattr(led, "email", "") or "").strip().lower()
            if not email:
                skipped += 1
                self.stdout.write(f"SKIP (no email): {led.ac_name}")
                continue
            acc, is_new = CustomerPortalAccount.objects.get_or_create(
                primary_email=email,
                defaults={"password_hash": cred.password_hash,
                          "phone": getattr(led, "mobile1", "") or "",
                          "is_active": cred.is_active},
            )
            if is_new:
                created += 1
            mobiles = [m for m in [getattr(led, "mobile1", ""), getattr(led, "mobile2", ""),
                                   getattr(led, "phone1", "")] if m]
            q = Q(pk=led.pk)
            for m in mobiles:
                q |= Q(mobile1=m) | Q(mobile2=m) | Q(phone1=m)
            for match in Ledger.objects.filter(q):
                if match not in acc.linked_ledgers.all():
                    acc.linked_ledgers.add(match)
                    linked += 1
        self.stdout.write(self.style.SUCCESS(
            f"accounts_created={created} ledgers_linked={linked} skipped={skipped} apply={apply}"))
        if not apply:
            transaction.set_rollback(True)
            self.stdout.write("DRY RUN — rolled back. Re-run with --apply to persist.")
