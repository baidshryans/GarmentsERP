"""The purge engine: the only place posted rows are removed.

The owner decided on 19 Oct 2026 that deleting a step or a document deletes it and its journal entries entirely:
no reversal left behind, no "cancelled" voucher, no history row, for anyone, an auditor included. This overrides
the earlier rule that posted vouchers are only ever reversed (CLAUDE.md, rule 1).

Deleting is built on what the ERP already does well. A delete service first undoes or cancels the step or document
the usual way, which posts exact reversals and puts every other row back. The posting and its reversal then net to
nothing, so removing both leaves every balance as it was. This module removes them, refusing any set that does not
net to nothing unless the caller says the entry stands alone (a hand-made entry, which has no reversal).
"""
from collections import defaultdict
from decimal import Decimal

from django.db import models, transaction

from core.exceptions import BusinessRuleError


class PurgeError(BusinessRuleError):
    """What was asked to be removed would change the books."""


def history(model, pks) -> None:
    """Remove every history row of these ids, including the one written when the row itself was deleted."""
    pks = [pk for pk in pks if pk is not None]
    manager = getattr(model, "history", None)
    if pks and manager is not None:
        manager.model.objects.filter(id__in=pks).delete()


def history_since(model, pk, since) -> None:
    """Remove the history of a kept row from `since` on: the changes a deleted step made to it and their undoing."""
    manager = getattr(model, "history", None)
    if manager is not None and pk is not None:
        manager.model.objects.filter(id=pk, history_date__gte=since).delete()


@transaction.atomic
def movements(qs) -> None:
    """Delete stock movements that net to nothing per place, item and roll. Balances are not touched: they already
    hold the net of the set, which is nothing."""
    from inventory.models import StockMovement

    rows = list(qs)
    net = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for m in rows:
        key = (m.location_id, m.material_id, m.sku_id, m.roll_id)
        net[key][0] += m.qty
        net[key][1] += m.value
    if any(q != 0 or v != 0 for q, v in net.values()):
        raise PurgeError("These stock movements do not cancel each other out; removing them would change the stock.")
    pks = [m.pk for m in rows]
    StockMovement._base_manager.filter(pk__in=pks).delete()      # past the append-only guard: this is the one place
    history(StockMovement, pks)


def _release(vouchers) -> None:
    """Clear the links other rows keep to these vouchers, so the vouchers can go. A row that must have its voucher
    (and is not being deleted by the caller) stops the purge."""
    from ledger.models import Voucher

    ids = [v.pk for v in vouchers]
    for rel in Voucher._meta.get_fields(include_hidden=True):
        if not isinstance(rel, models.ManyToOneRel) or rel.on_delete is models.CASCADE:
            continue
        field = rel.field
        if field.model is Voucher:                       # a reversal pointing at its original: both go
            continue
        qs = field.model._base_manager.filter(**{f"{field.name}__in": ids})
        if not qs.exists():
            continue
        if not field.null:
            raise PurgeError(f"A {field.model._meta.verbose_name} still uses this entry; delete it first.")
        qs.update(**{field.name: None})


@transaction.atomic
def vouchers(qs, *, lone=False) -> None:
    """Delete vouchers with their lines and bill allocations. Every posted voucher must go with its reversal (or be
    a reversal going with its original), unless `lone` says the caller deletes a hand-made entry on its own."""
    from ledger.models import BillAllocation, Voucher, VoucherLine

    rows = list(qs)
    ids = {v.pk for v in rows}
    if not lone:
        for v in rows:
            if v.status != Voucher.Status.POSTED:
                continue
            paired = (v.reverses_id in ids) or Voucher.objects.filter(reverses=v, pk__in=ids).exists()
            if not paired:
                raise PurgeError(f"{v.number} would be removed without its reversal; that would change the books.")
    _release(rows)
    line_ids = list(VoucherLine.objects.filter(voucher_id__in=ids).values_list("pk", flat=True))
    alloc_ids = list(BillAllocation.objects.filter(line_id__in=line_ids).values_list("pk", flat=True))
    BillAllocation._base_manager.filter(pk__in=alloc_ids).delete()
    VoucherLine._base_manager.filter(pk__in=line_ids).delete()
    Voucher._base_manager.filter(pk__in=ids, reverses__isnull=False).delete()     # reversals first: they point at originals
    Voucher._base_manager.filter(pk__in=ids).delete()
    history(BillAllocation, alloc_ids)
    history(VoucherLine, line_ids)
    history(Voucher, ids)
