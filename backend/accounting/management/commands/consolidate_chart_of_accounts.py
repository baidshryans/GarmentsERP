from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from accounting.models import Account, VoucherDetail, LedgerOpenBalance
from contacts.models import Ledger
from accounting.legacy_coa_map import (
    LEGACY_TO_STANDARD, is_legacy_code, resolve_standard_group,
)


class _DryRun(Exception):
    """Internal: raised to roll back the atomic block during a dry-run."""


def _trial_balance_totals():
    """(Σ debit, Σ credit) across all postings — invariant across this migration."""
    vd = VoucherDetail.objects.aggregate(d=Sum("debit"), c=Sum("credit"))
    ob = LedgerOpenBalance.objects.aggregate(d=Sum("debit"), c=Sum("credit"))
    z = 0
    return (
        (vd["d"] or z) + (ob["d"] or z),
        (vd["c"] or z) + (ob["c"] or z),
    )


class Command(BaseCommand):
    help = ("Re-point ledgers off the legacy MG-*/GM-*/SG-* chart onto the standard "
            "tree, then delete the empty legacy groups. Dry-run unless --apply.")

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true",
                            help="Commit changes (default: dry-run).")

    def handle(self, *args, **opts):
        apply = opts["apply"]

        legacy_groups = [a for a in Account.objects.all() if is_legacy_code(a.code)]

        # ── Pre-checks (abort, no changes) ────────────────────────────
        unmapped = sorted({
            g.code for g in legacy_groups
            if g.code not in LEGACY_TO_STANDARD
            and Ledger.objects.filter(ac_group=g).exists()
        })
        if unmapped:
            raise CommandError(
                "Unmapped legacy groups still hold ledgers: " + ", ".join(unmapped)
                + ". Add them to accounting/legacy_coa_map.py before running.")
        for code in set(LEGACY_TO_STANDARD.values()):
            if not Account.objects.filter(code=code).exists():
                raise CommandError(
                    f"Standard target '{code}' missing. Run setup_account_groups first.")

        if not legacy_groups:
            self.stdout.write(self.style.SUCCESS("No legacy groups found. Nothing to do."))
            return

        before = _trial_balance_totals()
        result = {"moved": 0, "deleted": 0}

        @transaction.atomic
        def _run():
            for g in legacy_groups:
                std = resolve_standard_group(g.code)
                if std is not None:
                    n = Ledger.objects.filter(ac_group=g).update(ac_group=std)
                    result["moved"] += n
                    if n:
                        self.stdout.write(
                            f"  {g.code} {g.name!r}: moved {n} ledger(s) -> {std.code}")
                    # Re-point any child Account groups onto the standard parent.
                    Account.objects.filter(parent=g).update(parent=std)
            # Delete legacy groups (now empty of ledgers; children re-parented).
            # ac_group is on_delete=SET_NULL so this cannot cascade-delete data.
            for g in [a for a in Account.objects.all() if is_legacy_code(a.code)]:
                g.delete()
                result["deleted"] += 1
            after = _trial_balance_totals()
            if before != after:
                raise CommandError(
                    f"Trial-balance drift (before={before} after={after}); rolling back.")
            if not apply:
                raise _DryRun()  # roll back the whole transaction

        try:
            _run()
        except _DryRun:
            pass

        self.stdout.write(self.style.SUCCESS(
            f"{'APPLIED' if apply else 'DRY-RUN (rolled back)'}: "
            f"{result['moved']} ledger(s) remapped, {result['deleted']} legacy group(s) "
            f"deleted. Trial balance {before} unchanged."))
