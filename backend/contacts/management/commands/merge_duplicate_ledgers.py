"""Merge duplicate ledgers that share an ``ac_name``.

Ledger names are not unique, which used to crash name-based voucher lookups and
still fragments balances across accidental duplicates. This command collapses
each *safe* duplicate group into a single canonical ledger, repointing every
foreign key that referenced a removed ledger.

Safety categories (only the first two are merged automatically):

* ``statutory`` – TDS / TCS / GST / statutory payable ledgers. These are
  company-level accounts that should exist once, shared across branches, so the
  canonical row is set to ``retail_code = NULL``.
* ``empty_dup`` – groups where at most one ledger carries transactions; the
  empty siblings are redundant and safe to fold in.
* ``review`` – transactions on more than one copy (possibly distinct real
  parties). Never merged automatically; reported for a human decision.

Dry-run by default. Pass ``--apply`` to commit inside a transaction.
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction, IntegrityError
from django.db.models import Count

from contacts.models import Ledger, LedgerRole
from accounting.models import Account, VoucherDetail

# Names that denote a single company-level statutory account.
STATUTORY_RE = re.compile(
    r"\b(tds|tcs|gst|cgst|sgst|igst|professional tax|provident|esi|pf)\b", re.I
)


def _txn_count(ledger_id):
    return VoucherDetail.objects.filter(account_id=ledger_id).count()


def _fk_relations():
    """FK/O2O relations pointing into the ledger_master table.

    ``contacts.Ledger`` and ``accounting.Account`` are two model classes mapped
    onto the same table, so a foreign key may be declared against either one.
    Collect from both and de-duplicate by (model label, field name).
    """
    seen = {}
    for model in (Ledger, Account):
        for rel in model._meta.related_objects:
            # ``rel`` is the reverse descriptor: a plain FK reverse is
            # one-to-many, an O2O reverse is one-to-one. Skip only true m2m.
            if rel.many_to_many:
                continue
            key = (rel.related_model._meta.label, rel.field.name)
            seen[key] = (rel.related_model, rel.field.name, rel.one_to_one)
    return list(seen.values())


class Command(BaseCommand):
    help = "Merge duplicate ledgers sharing an ac_name into a canonical row."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Commit the merge. Without this the command only reports.",
        )

    def handle(self, *args, **opts):
        apply = opts["apply"]
        relations = _fk_relations()

        groups = (
            Ledger.objects.values("ac_name")
            .annotate(c=Count("id")).filter(c__gt=1)
        )

        merges, review = [], []
        for g in groups:
            leds = list(Ledger.objects.filter(ac_name=g["ac_name"]).order_by("id"))
            counts = {l.id: _txn_count(l.id) for l in leds}
            nonempty = [l for l in leds if counts[l.id] > 0]

            if STATUTORY_RE.search(g["ac_name"]):
                category = "statutory"
            elif len(nonempty) <= 1:
                category = "empty_dup"
            else:
                review.append((g["ac_name"], [counts[l.id] for l in leds]))
                continue

            # Canonical: most transactions, then lowest id.
            canonical = max(leds, key=lambda l: (counts[l.id], -l.id))
            losers = [l for l in leds if l.id != canonical.id]
            merges.append((category, canonical, losers, counts))

        self._report(merges, review, relations)

        if not apply:
            self.stdout.write(self.style.WARNING(
                "\nDry run. Re-run with --apply to perform the merge."))
            return

        with transaction.atomic():
            for category, canonical, losers, _counts in merges:
                self._merge_group(category, canonical, losers, relations)
        self.stdout.write(self.style.SUCCESS("\nMerge applied."))

    # ── helpers ──────────────────────────────────────────────────────────
    def _report(self, merges, review, relations):
        self.stdout.write(f"Relations to repoint: {len(relations)}")
        self.stdout.write(f"\nGroups to merge: {len(merges)}")
        for category, canonical, losers, counts in merges:
            loser_ids = ", ".join(str(l.id) for l in losers)
            self.stdout.write(
                f"  [{category}] {canonical.ac_name!r}: keep #{canonical.id} "
                f"(txns={counts[canonical.id]}), remove #{loser_ids}"
            )
        self.stdout.write(f"\nGroups left for manual review: {len(review)}")
        for name, counts in review:
            self.stdout.write(f"  [review] {name!r}: txns per copy = {counts}")

    def _merge_group(self, category, canonical, losers, relations):
        loser_ids = [l.id for l in losers]

        # Roles carry a UNIQUE(ledger, role) constraint, so a blind repoint would
        # collide with a role the canonical ledger already holds. Move only the
        # roles the canonical lacks; drop the rest.
        self._merge_roles(canonical, loser_ids)

        for related_model, field_name, is_o2o in relations:
            if related_model is LedgerRole and field_name == "ledger":
                continue  # handled above
            qs = related_model.objects.filter(**{f"{field_name}__in": loser_ids})
            if not qs.exists():
                continue
            self._repoint(related_model, field_name, canonical, loser_ids)

        # Statutory accounts are company-level → share one row across branches.
        if category == "statutory" and canonical.retail_code_id is not None:
            canonical.retail_code = None
            canonical.save(update_fields=["retail_code"])

        Ledger.objects.filter(id__in=loser_ids).delete()

    def _repoint(self, related_model, field_name, canonical, loser_ids):
        """Repoint rows from losers to canonical, tolerating unique-constraint
        collisions. Several tables carry a UNIQUE constraint that includes the
        ledger FK (opening balance, roles, O2O profiles); when the canonical
        ledger already has the matching row, the loser's row is redundant (a
        loser is an empty or duplicate ledger) and is dropped."""
        qs = related_model.objects.filter(**{f"{field_name}__in": loser_ids})
        try:
            with transaction.atomic():
                qs.update(**{field_name: canonical})
            return
        except IntegrityError:
            pass
        # Fall back to row-by-row so a single collision doesn't fail the batch.
        for obj in list(related_model.objects.filter(**{f"{field_name}__in": loser_ids})):
            setattr(obj, field_name, canonical)
            try:
                with transaction.atomic():
                    obj.save(update_fields=[field_name])
            except IntegrityError:
                obj.delete()

    def _merge_roles(self, canonical, loser_ids):
        existing = set(canonical.roles.values_list("role", flat=True))
        for lr in LedgerRole.objects.filter(ledger_id__in=loser_ids):
            if lr.role in existing:
                lr.delete()
            else:
                lr.ledger = canonical
                lr.save(update_fields=["ledger"])
                existing.add(lr.role)
