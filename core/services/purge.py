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
def rows(objs) -> None:
    """Delete these rows with everything that cascades from them, and the history of all of it. A row that must
    keep them (a protected link from elsewhere) stops the delete with a plain message."""
    from django.db import router
    from django.db.models.deletion import Collector, ProtectedError, RestrictedError

    objs = list(objs)
    if not objs:
        return
    collector = Collector(using=router.db_for_write(type(objs[0])))
    try:
        collector.collect(objs)
    except (ProtectedError, RestrictedError) as exc:
        used = sorted({o._meta.verbose_name for o in exc.protected_objects} if hasattr(exc, "protected_objects")
                      else {o._meta.verbose_name for o in exc.restricted_objects})
        raise PurgeError(f"Still used by: {', '.join(used)}. Delete that first.")
    collected = {model: [o.pk for o in instances] for model, instances in collector.data.items()}
    collector.delete()
    for model, pks in collected.items():
        history(model, pks)


def assert_dates_open(factory, day) -> None:
    """A delete touches the document's own date and today (the date its reversal is posted on, before both are
    purged): neither may be in a locked period."""
    from django.utils import timezone

    from core.services.periods import assert_period_open

    assert_period_open(factory.company, factory, day)
    assert_period_open(factory.company, factory, max(timezone.localdate(), day))


@transaction.atomic
def rolls(roll_ids) -> None:
    """Fabric rolls a deleted document brought in: their (empty) balances and the rolls themselves, so the vendor's
    roll numbers can be received again."""
    from inventory.models import FabricRoll, RollBalance

    roll_ids = [r for r in roll_ids if r is not None]
    if RollBalance.objects.filter(roll_id__in=roll_ids).exclude(qty=0).exists():
        raise PurgeError("A roll from these goods is still in stock somewhere; it cannot be removed.")
    RollBalance.objects.filter(roll_id__in=roll_ids).delete()
    rows(FabricRoll.objects.filter(pk__in=roll_ids))


@transaction.atomic
def delete_document(doc, *, cancel=None, after=None) -> None:
    """Delete a posted document entirely: `cancel()` undoes it the usual way (exact reversals of its stock movements
    and its voucher), then the document's movements and vouchers and their reversals are purged, `after()` clears
    anything else the document made, and the document's rows go with their history."""
    from inventory.models import StockMovement
    from ledger.models import Voucher

    if cancel is not None:
        cancel()
    src = {"source_type": doc._meta.label_lower, "source_id": doc.pk}
    movements(StockMovement.objects.filter(**src))
    own = list(Voucher.objects.filter(**src).values_list("pk", flat=True))
    reversed_ = list(Voucher.objects.filter(reverses_id__in=own).values_list("pk", flat=True))
    vouchers(Voucher.objects.filter(pk__in=own + reversed_))
    rows([type(doc)._base_manager.get(pk=doc.pk)])
    if after is not None:
        after()


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
