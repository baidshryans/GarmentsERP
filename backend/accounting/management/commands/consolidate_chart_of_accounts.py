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
        do_apply = opts["apply"]

        legacy_groups = [a for a in Account.objects.all() if is_legacy_code(a.code)]
        legacy_ids = {g.id for g in legacy_groups}

        # ── Pre-checks (abort, no changes) ────────────────────────────
        # A legacy group must be mapped if it carries anything that would be
        # detached when it is deleted: ledgers, or NON-legacy child groups.
        # (Legacy children are deleted themselves, so they don't need re-homing.)
        unmapped = set()
        for g in legacy_groups:
            if g.code in LEGACY_TO_STANDARD:
                continue
            has_ledgers = Ledger.objects.filter(ac_group=g).exists()
            has_nonlegacy_children = Account.objects.filter(parent=g).exclude(
                id__in=legacy_ids).exists()
            if has_ledgers or has_nonlegacy_children:
                unmapped.add(g.code)
        if unmapped:
            raise CommandError(
                "Unmapped legacy groups still hold ledgers or non-legacy children: "
                + ", ".join(sorted(unmapped))
                + ". Add them to accounting/legacy_coa_map.py before running.")
        for code in set(LEGACY_TO_STANDARD.values()):
            if not Account.objects.filter(code=code).exists():
                raise CommandError(
                    f"Standard target '{code}' missing. Run setup_account_groups first.")

        if not legacy_groups:
            self.stdout.write(self.style.SUCCESS("No legacy groups found. Nothing to do."))
            return

        before = _trial_balance_totals()
        result = {"moved": 0, "reparented": 0, "deleted": 0}

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
                    # Re-point any NON-legacy child groups onto the standard
                    # parent (legacy children are deleted below, so skip them).
                    r = Account.objects.filter(parent=g).exclude(
                        id__in=legacy_ids).update(parent=std)
                    result["reparented"] += r
                    if r:
                        self.stdout.write(
                            f"  {g.code} {g.name!r}: re-parented {r} account group(s) -> {std.code}")
            # Delete the legacy groups captured up-front (now empty of ledgers;
            # non-legacy children re-parented). ac_group / parent are SET_NULL,
            # so deletion cannot cascade-delete ledgers or vouchers.
            for g in legacy_groups:
                g.delete()
                result["deleted"] += 1
            after = _trial_balance_totals()
            if before != after:
                raise CommandError(
                    f"Trial-balance drift (before={before} after={after}); rolling back.")
            if not do_apply:
                raise _DryRun()  # roll back the whole transaction

        try:
            _run()
        except _DryRun:
            pass

        self.stdout.write(self.style.SUCCESS(
            f"{'APPLIED' if do_apply else 'DRY-RUN (rolled back)'}: "
            f"{result['moved']} ledger(s) remapped, {result['reparented']} child group(s) "
            f"re-parented, {result['deleted']} legacy group(s) deleted. "
            f"Trial balance {before} unchanged."))
