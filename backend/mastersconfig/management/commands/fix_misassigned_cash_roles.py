"""
Data cleanup for a role-classification bug: `_infer_ledger_role`
(mastersconfig/views.py) used to check the 'cash'/'bank' keyword rule
*before* the 'charges'/'expense' rule, so pure expense ledgers whose name
contains "cash" or "bank" (e.g. "Cash Pickup Charges", "Cash Deposit
Charges", "Bank Charges") got wrongly tagged with the CA (Cash) or BA (Bank)
LedgerRole. That pollutes the Cash Book / Bank Book ledger picker dropdowns
with junk entries, and — combined with the API's default page_size=10 and
alphabetical ordering — can push the real per-retail "R00x_Cash" ledgers off
the first page entirely.

The classification rule itself is already fixed (expense/income keywords now
win). This command finds ledgers still carrying a stale CA/BA role from
before that fix and removes it, provided the ledger's real role can be
reclassified as EXP/INC/OTH by name/group.

Usage:
    python manage.py fix_misassigned_cash_roles            # dry-run (no writes)
    python manage.py fix_misassigned_cash_roles --apply    # write to DB
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from contacts.models import Ledger, LedgerRole

# Keywords that indicate the ledger is really an expense/income account, not
# an actual cash-in-hand / bank-account ledger, even though its name mentions
# "cash" or "bank" in passing.
_MISCLASSIFY_KEYWORDS = (
    'charges', 'expense', 'purchase', 'commission', 'machine',
    'insurance', 'fee', 'rent', 'income', 'revenue', 'sales',
)


class Command(BaseCommand):
    help = "Remove stale CA/BA LedgerRole tags from ledgers that are really expense/income accounts."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                             help="Actually write to the DB. Without this flag the command is a dry-run.")

    def handle(self, *args, **options):
        apply = options["apply"]

        candidates = LedgerRole.objects.filter(role__in=['CA', 'BA']).select_related(
            'ledger', 'ledger__ac_group'
        )

        to_fix = []
        for role_row in candidates:
            ledger = role_row.ledger
            text = f"{getattr(ledger.ac_group, 'name', '') or ''} {ledger.ac_name}".lower()
            if any(kw in text for kw in _MISCLASSIFY_KEYWORDS):
                to_fix.append(role_row)

        if not to_fix:
            self.stdout.write(self.style.SUCCESS("No misclassified CA/BA roles found."))
            return

        self.stdout.write(f"Found {len(to_fix)} ledger(s) with a stale CA/BA role:")
        for role_row in to_fix:
            ledger = role_row.ledger
            self.stdout.write(
                f"  [{role_row.role}] {ledger.ac_name} (id={ledger.id}, "
                f"group={getattr(ledger.ac_group, 'name', None)}, primary={role_row.is_primary})"
            )

        if not apply:
            self.stdout.write(self.style.WARNING("Dry-run only. Re-run with --apply to remove these roles."))
            return

        removed = 0
        with transaction.atomic():
            for role_row in to_fix:
                if role_row.is_primary:
                    # Never leave a ledger with zero roles — reassign is_primary
                    # to another existing role first, or fall back to OTH.
                    other = LedgerRole.objects.filter(
                        ledger=role_row.ledger
                    ).exclude(pk=role_row.pk).first()
                    if other:
                        other.is_primary = True
                        other.save(update_fields=['is_primary'])
                    else:
                        LedgerRole.objects.create(
                            ledger=role_row.ledger, role='OTH', is_primary=True
                        )
                role_row.delete()
                removed += 1

        self.stdout.write(self.style.SUCCESS(f"Removed {removed} stale CA/BA role(s)."))
