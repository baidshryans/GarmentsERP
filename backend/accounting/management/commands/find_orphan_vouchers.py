"""
find_orphan_vouchers
====================

Detect (and optionally delete) VoucherMain rows that have NO owning source
document but belong to a voucher type that is *always* supposed to be created
from one.

Background
----------
The cash book / day book / ledgers / P&L are all built from the General Ledger
(``VoucherMain`` + ``VoucherDetail``). Source documents such as a sales invoice
(``sales.SalesVou``) link to their GL voucher via a ``SET_NULL`` foreign key
(``SalesVou.ac_voucher``). If a source document is deleted through a path that
does not cascade to its GL voucher (e.g. data created before the current
delete-cascade signals existed, or an interrupted write), the ``VoucherMain``
is left behind as an *orphan*: it still shows in the cash book but has no
invoice in the Sales Voucher list. This command finds those.

Why only some voucher types are checked by default
--------------------------------------------------
Many voucher types are *manually entered* and legitimately have no source
document (journals, payments, receipts, contras). Empirically, on clean data
these show up as 100% "unreferenced":

    JRNL, PMNT, CNTR, RCPT   -> standalone by design, NEVER flag

Others are only partially linked because they were imported as GL-only rows in
the legacy migration (``PURC-SC``, ``PURC-CO``, ``SCHM-C``): flagging them would
produce false positives.

Only these types reliably carry an owning document (0 orphans on healthy data),
so they are the safe DEFAULT set:

    SALE, RCPT-SALE, PURC-RET, SALE-RET, SCHM

Pass ``--types`` to override the set (e.g. after you have confirmed a normally
"unreliable" type should be clean).

Usage
-----
    # dry run (default) over the safe default types
    python manage.py find_orphan_vouchers

    # restrict to one retail and a date window
    python manage.py find_orphan_vouchers --retail 1 --from 2026-04-01 --to 2027-03-31

    # actually delete what the dry run reported (VoucherDetail cascades)
    python manage.py find_orphan_vouchers --delete

    # check specific types
    python manage.py find_orphan_vouchers --types SALE,RCPT-SALE

    # instead of the missing-document check, find malformed GL vouchers whose
    # debit total != credit total (or that have fewer than 2 lines). These are
    # corrupt regardless of voucher type (e.g. a receipt with only the cash leg
    # and no counterparty, which shows as "—" in the cash book).
    python manage.py find_orphan_vouchers --unbalanced
    python manage.py find_orphan_vouchers --unbalanced --delete
"""
from datetime import datetime

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Sum

from accounting.models import VoucherMain, VoucherDetail


# Voucher types that are reliably backed by an owning source document.
DEFAULT_TYPES = ["SALE", "RCPT-SALE", "PURC-RET", "SALE-RET", "SCHM"]

# FKs that point AT VoucherMain but are the voucher's own internal components
# (they are owned BY the voucher, not owners OF it). These must be excluded when
# building the "referenced by a source document" set, otherwise every voucher
# that simply has ledger lines would look "referenced".
CHILD_FIELDS = {
    "accounting.VoucherDetail.voucher_main",
    "accounting.ReferenceBills.voucher",
    "accounting.CashGoldConversion.v_type",
    "accounting.VoucherAttachment.voucher",
    "accounting.AuditMark.voucher",
}


def _owner_links():
    """Discover every (model, field_name) that OWNS a VoucherMain, i.e. every
    concrete FK/O2O pointing at VoucherMain except the child components above.
    Dynamic discovery keeps this correct as new source-document models appear."""
    links = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            remote = getattr(field, "remote_field", None)
            if not (remote and getattr(remote, "model", None) is VoucherMain):
                continue
            if not getattr(field, "concrete", False):
                continue
            dotted = f"{model._meta.app_label}.{model.__name__}.{field.name}"
            if dotted in CHILD_FIELDS:
                continue
            links.append((model, field.name))
    return links


class Command(BaseCommand):
    help = "Find (and optionally delete) orphaned GL vouchers with no source document."

    def add_arguments(self, parser):
        parser.add_argument(
            "--types",
            default=",".join(DEFAULT_TYPES),
            help=f"Comma-separated voucher_type values to check. Default: {','.join(DEFAULT_TYPES)}",
        )
        parser.add_argument(
            "--unbalanced",
            action="store_true",
            help="Ignore --types; instead find vouchers whose debit total != credit total "
                 "or that have fewer than 2 ledger lines (malformed, any type).",
        )
        parser.add_argument("--retail", type=int, help="Limit to a single retail id.")
        parser.add_argument("--from", dest="from_date", help="Only vouchers on/after this date (YYYY-MM-DD).")
        parser.add_argument("--to", dest="to_date", help="Only vouchers on/before this date (YYYY-MM-DD).")
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Delete the reported orphans (VoucherDetail cascades). Default is a dry run.",
        )

    def _unbalanced_qs(self):
        """VoucherMain whose ledger lines don't balance (sum debit != sum credit)
        or that have fewer than 2 lines. Corrupt regardless of voucher type."""
        agg = (
            VoucherMain.objects
            .annotate(d=Sum("transactions__debit"), c=Sum("transactions__credit"),
                      n=Count("transactions"))
        )
        bad = [
            vm.id for vm in agg
            if (vm.n or 0) < 2 or abs(float(vm.d or 0) - float(vm.c or 0)) >= 0.01
        ]
        return VoucherMain.objects.filter(id__in=bad)

    def _parse_date(self, value, label):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(f"--{label} must be YYYY-MM-DD, got {value!r}")

    def handle(self, *args, **opts):
        if opts["unbalanced"]:
            qs = self._unbalanced_qs()
            self.stdout.write("Mode: unbalanced / single-leg vouchers (all types)")
        else:
            types = [t.strip() for t in opts["types"].split(",") if t.strip()]

            # Build the set of VoucherMain ids referenced by any owning document.
            referenced = set()
            for model, field in _owner_links():
                referenced |= set(
                    model.objects.exclude(**{f"{field}__isnull": True})
                    .values_list(field, flat=True)
                )
            qs = VoucherMain.objects.filter(voucher_type__in=types).exclude(id__in=referenced)
            self.stdout.write(f"Checking types: {', '.join(types)}")

        if opts["retail"]:
            qs = qs.filter(retail_id=opts["retail"])
        if opts["from_date"]:
            qs = qs.filter(date__gte=self._parse_date(opts["from_date"], "from"))
        if opts["to_date"]:
            qs = qs.filter(date__lte=self._parse_date(opts["to_date"], "to"))
        qs = qs.order_by("voucher_type", "date", "voucher_no")

        orphans = list(qs)
        self.stdout.write(f"Found {len(orphans)} problem voucher(s).\n")

        if not orphans:
            self.stdout.write(self.style.SUCCESS("No orphans. GL is consistent with source documents."))
            return

        # Per-voucher detail: show balance so genuinely-corrupt (unbalanced)
        # rows are obvious.
        header = f"{'id':>9} {'type':10} {'date':10} {'voucher_no':22} {'amount':>13} {'bal?':5} legacy_key / narration"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        vids = [o.id for o in orphans]
        agg = {
            r["voucher_main_id"]: r
            for r in VoucherDetail.objects.filter(voucher_main_id__in=vids)
            .values("voucher_main_id")
            .annotate(d=Sum("debit"), c=Sum("credit"))
        }
        for o in orphans:
            a = agg.get(o.id, {})
            dr = a.get("d") or 0
            cr = a.get("c") or 0
            balanced = "ok" if abs(dr - cr) < 0.01 else "UNBAL"
            tag = getattr(o, "legacy_key", None) or (o.narration or "")[:40]
            self.stdout.write(
                f"{o.id:>9} {o.voucher_type:10} {str(o.date):10} {(o.voucher_no or ''):22} "
                f"{float(o.amount or 0):>13,.2f} {balanced:5} {tag}"
            )

        if not opts["delete"]:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Dry run — nothing deleted. Re-run with --delete to remove these."))
            return

        with transaction.atomic():
            result = VoucherMain.objects.filter(id__in=vids).delete()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Deleted: {result}"))
