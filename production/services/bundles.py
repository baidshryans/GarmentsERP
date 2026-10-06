"""Bundle movement: stage moves, rework, inter-factory moves and packing (E7.6, E7.7, E7.9, BR-21, BR-22).

`apply_move` is the one place a bundle changes place: it checks the quantity balance, posts the WIP quantity
movements, records the StageMovement and updates the bundle. Moves, job work issue / receipt / QC and packing all
go through it.
"""
import uuid
from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.models import Location
from core.scoping import assert_factory_access
from core.services.factories import dispatch_location, process_location, rejects_location
from inventory.models import StockMovement
from inventory.services import stock
from ledger.services.posting import LineSpec, post_voucher
from production.models import Bundle, Lot, LotCostEntry, LotStep, StageMovement
from production.services import costing, orders

T = StockMovement.Type
ZERO = Decimal("0.00")


@dataclass
class Count:
    """What the supervisor counted at the receiving stage. qty_in is whatever is left after the three kinds of
    difference, so the move always balances (BR-21)."""

    loss: int = 0
    rejection: int = 0
    shortage: int = 0


def steps_ahead(bundle, steps):
    """(the next mandatory step or None, every step still ahead) for a bundle, counted from where it actually is:
    a bundle sitting at a stage has that stage behind it, any other has what it completed. `steps` is the lot's
    route in order without the skipped steps. The lot guide's button and the move screen both ask here."""
    at_stage = bundle.status == Bundle.Status.AT_STAGE and bundle.current_step_id
    done = bundle.current_step.sequence if at_stage else bundle.completed_seq
    later = [s for s in steps if s.sequence > done]
    return next((s for s in later if s.is_mandatory), None), later   # optional steps may be jumped over (see check_entry)


def next_stage(bundle, steps):
    """The stage a bundle goes to next: the next mandatory step, or the next optional one when no mandatory step is left."""
    mandatory, later = steps_ahead(bundle, steps)
    return mandatory or (later[0] if later else None)


def next_stage_label(bundle, steps):
    """What the move screen says about where a bundle goes next. A bundle out with a fabricator is received, not
    moved, and a fabricator's stage is entered by challan, so the label says so: `move_bundles` refuses both."""
    if bundle.location.loc_type == Location.Type.FABRICATOR:
        return "With fabricator"
    step = next_stage(bundle, steps)
    if step is None:
        return ""
    by_challan = " (by challan)" if step.assignment == LotStep.Assignment.SUBCONTRACT else ""
    return f"{step.process.name}{by_challan}"


def refresh_steps(lot):
    """Mark steps in progress or done from what the bundles have completed, then the lot and order status."""
    bundles = list(Bundle.objects.filter(lot=lot).exclude(status=Bundle.Status.SCRAPPED))
    for step in lot.steps.exclude(status=LotStep.Status.SKIPPED):
        if bundles and all(b.completed_seq >= step.sequence for b in bundles):
            status = LotStep.Status.DONE
        elif any(b.completed_seq >= step.sequence or b.current_step_id == step.pk for b in bundles):
            status = LotStep.Status.IN_PROGRESS
        else:
            status = LotStep.Status.PENDING
        if step.status != status:
            step.status = status
            if status != LotStep.Status.PENDING and step.started_at is None:
                step.started_at = timezone.now()
            step.save(update_fields=["status", "started_at"])
    live = [b for b in bundles if b.is_live]
    lot = Lot.objects.get(pk=lot.pk)
    if lot.status not in (Lot.Status.CLOSED,):
        if bundles and not live:
            lot.status = Lot.Status.COMPLETED
        elif bundles:
            lot.status = Lot.Status.IN_PRODUCTION
        lot.save(update_fields=["status"])
    orders.refresh_status(lot.order)


def cutting_steps(lot) -> list:
    """The cutting steps at the head of the route: bundles exist only once these are done."""
    out = []
    for step in lot.steps.select_related("process").order_by("sequence"):
        if step.process.kind != "cutting":
            break
        out.append(step)
    return out


def cutting_done_seq(lot) -> int:
    """Highest sequence of the cutting steps at the head of the route."""
    steps = cutting_steps(lot)
    return steps[-1].sequence if steps else 0


def apply_move(*, bundle, kind, to_location, user, date, new_status, to_step=None, completed_seq=None, loss=0,
               rejection=0, shortage=0, extra=0, qty_in=None, reason="", is_rework=False, challan=None,
               reject_location=None) -> StageMovement:
    """Move a whole bundle and keep every count honest. qty_out is the bundle's current quantity."""
    bundle = Bundle.objects.select_related("lot", "sku", "location", "location__factory").get(pk=bundle.pk)
    lot, sku, src = bundle.lot, bundle.sku, bundle.location
    qty_out = bundle.qty
    for name, v in (("loss", loss), ("rejection", rejection), ("shortage", shortage), ("extra", extra)):
        if v < 0:
            raise BusinessRuleError(f"{name.capitalize()} cannot be negative.")
    balanced = qty_out + extra - loss - rejection - shortage
    if qty_in is not None and qty_in != balanced:
        raise BusinessRuleError(
            f"Bundle {bundle.bundle_no}: {qty_out} out must equal {qty_in} in plus loss, rejection and shortage "
            f"({loss + rejection + shortage}) (BR-21).")
    qty_in = balanced
    if qty_in < 0:
        raise BusinessRuleError(f"Bundle {bundle.bundle_no}: loss, rejection and shortage are more than the {qty_out} pieces (BR-21).")

    from_factory, dest_factory = src.factory, to_location.factory
    lost = loss + shortage
    through = qty_out - lost                                   # pieces that physically travel
    if through < 0:
        raise BusinessRuleError(f"Bundle {bundle.bundle_no}: loss and shortage are more than the pieces in it (BR-21).")
    same_place = src.pk == to_location.pk
    common = dict(item=sku, date=date, user=user, bundle=bundle, lot=lot, value=Decimal("0"))
    if lost:
        stock.post_movement(factory=from_factory, location=src, qty=-Decimal(lost), movement_type=T.LOSS,
                            notes=reason or f"{kind}: loss/shortage", **common)
    if through and not same_place:
        stock.post_movement(factory=from_factory, location=src, qty=-Decimal(through), movement_type=T.TRANSFER_OUT,
                            notes=reason or kind, **common)
    good = qty_in - extra
    if good < 0:
        raise BusinessRuleError("Over-receipt cannot be larger than the pieces received.")
    if not same_place:
        if good:
            stock.post_movement(factory=dest_factory, location=to_location, qty=Decimal(good), movement_type=T.TRANSFER_IN,
                                notes=reason or kind, enforce_scope=False, **common)
        if rejection:
            stock.post_movement(factory=dest_factory, location=reject_location or rejects_location(dest_factory),
                                qty=Decimal(rejection), movement_type=T.TRANSFER_IN, notes=reason or "Rejected",
                                enforce_scope=False, **common)
    else:
        if rejection:  # rejected pieces leave the bundle's place for the rejects stock
            stock.post_movement(factory=from_factory, location=src, qty=-Decimal(rejection), movement_type=T.TRANSFER_OUT,
                                notes=reason or "Rejected", **common)
            stock.post_movement(factory=dest_factory, location=reject_location or rejects_location(dest_factory),
                                qty=Decimal(rejection), movement_type=T.TRANSFER_IN, notes=reason or "Rejected",
                                enforce_scope=False, **common)
    if extra:
        stock.post_movement(factory=dest_factory, location=to_location, qty=Decimal(extra), movement_type=T.ADJUSTMENT,
                            notes="Approved over-receipt", enforce_scope=False, **common)

    movement = StageMovement.objects.create(
        factory=from_factory, bundle=bundle, kind=kind, from_step=bundle.current_step, to_step=to_step,
        from_location=src, to_location=to_location, qty_out=qty_out, qty_extra=extra, qty_in=qty_in, loss=loss,
        rejection=rejection, shortage=shortage, reason=reason, is_rework=is_rework, challan=challan, user=user)

    bundle.qty = qty_in
    bundle.location = to_location
    bundle.status = Bundle.Status.SCRAPPED if qty_in == 0 else new_status
    if to_step is not None:
        bundle.current_step = to_step
    if completed_seq is not None:
        bundle.completed_seq = completed_seq
    if to_step is not None:
        bundle.is_rework = is_rework          # rework lasts for the stage gone back to; moving on clears it
    if bundle.rework_qty > bundle.qty:
        bundle.rework_qty = bundle.qty
    bundle.save()
    return movement


@transaction.atomic
def split_bundle(bundle, qty, *, user, date, reason="") -> Bundle:
    """Take `qty` pieces out of a bundle into a new bundle of its own, at the same place and stage, so the two can
    go different ways (E7.8). The new bundle is numbered after the first one (B002-R1) and needs its own tag.
    Stock at the place does not change, and neither does the lot's cost."""
    bundle = Bundle.objects.select_related("lot", "sku", "location", "location__factory", "split_from").get(pk=bundle.pk)
    if not bundle.is_live:
        raise BusinessRuleError(f"Bundle {bundle.bundle_no} is {bundle.get_status_display().lower()} and cannot be split.")
    if qty <= 0 or qty >= bundle.qty:
        raise BusinessRuleError(f"Bundle {bundle.bundle_no} has {bundle.qty} pieces: split off at least 1 and leave at least 1.")
    root = bundle
    while root.split_from_id:
        root = root.split_from
    taken = set(Bundle.objects.filter(lot=bundle.lot, bundle_no__startswith=f"{root.bundle_no}-R").values_list("bundle_no", flat=True))
    n = 1
    while f"{root.bundle_no}-R{n}" in taken:
        n += 1
    child = Bundle.objects.create(
        lot=bundle.lot, entry=bundle.entry, bundle_no=f"{root.bundle_no}-R{n}", sku=bundle.sku, qty=qty, original_qty=qty,
        qr_token=uuid.uuid4().hex[:16], status=bundle.status, location=bundle.location, current_step=bundle.current_step,
        completed_seq=bundle.completed_seq, split_from=bundle)
    common = dict(factory=bundle.location.factory, location=bundle.location, item=bundle.sku, value=Decimal("0"), date=date,
                  user=user, lot=bundle.lot, notes=reason or f"Split: {child.bundle_no} out of {bundle.bundle_no}")
    stock.post_movement(qty=-Decimal(qty), movement_type=T.TRANSFER_OUT, bundle=bundle, **common)
    stock.post_movement(qty=Decimal(qty), movement_type=T.TRANSFER_IN, bundle=child, **common)
    bundle.qty -= qty
    bundle.save(update_fields=["qty"])
    return child


def check_entry(b, to_step, reason=""):
    """Can bundle `b` enter `to_step` now? Returns (stage it is leaving or None, steps done, moving backwards)."""
    if b.status not in (Bundle.Status.CUT, Bundle.Status.READY, Bundle.Status.AT_STAGE):
        raise BusinessRuleError(f"Bundle {b.bundle_no} is {b.get_status_display().lower()} and cannot be moved now.")
    if b.status == Bundle.Status.AT_STAGE and b.location.loc_type == Location.Type.FABRICATOR:
        raise BusinessRuleError(f"Bundle {b.bundle_no} is with a fabricator: receive it first.")
    if b.rework_qty:
        raise BusinessRuleError(f"Bundle {b.bundle_no} has pieces waiting for rework; finish that first.")
    in_step = b.current_step if b.status == Bundle.Status.AT_STAGE else None
    done = in_step.sequence if in_step else b.completed_seq
    backwards = to_step.sequence <= done
    if in_step is not None and in_step.pk == to_step.pk:
        raise BusinessRuleError(f"Bundle {b.bundle_no} is already at {to_step.process.name}.")
    if backwards:
        if not reason.strip():
            raise BusinessRuleError("Moving back to an earlier stage needs a reason (BR-22).")
    else:
        for s in b.lot.steps.filter(sequence__gt=done, sequence__lt=to_step.sequence).exclude(status=LotStep.Status.SKIPPED):
            if s.is_mandatory:
                raise BusinessRuleError(
                    f"{s.process.name} is mandatory and not done for bundle {b.bundle_no}; only optional steps can be skipped.")
    return in_step, done, backwards


def accrue_leaving_labour(lot, items, date, user, note):
    """In-house piece-rate labour for stages bundles are leaving. items = [(bundle, stage left, pieces that pass)]."""
    labour = {}
    for b, in_step, passing in items:
        if in_step is not None and in_step.assignment == LotStep.Assignment.IN_HOUSE and passing > 0:
            rate = in_step.rework_rate if b.is_rework else in_step.rate
            if rate > 0:
                f = b.location.factory
                labour[f] = labour.get(f, ZERO) + costing.r2(rate * passing)
    for f, amount in labour.items():
        costing.accrue_labour(lot=lot, factory=f, amount=amount, date=date, user=user, note=note, source=lot)


def _check_same_lot(bundles):
    lots = {b.lot_id for b in bundles}
    if len(lots) != 1:
        raise BusinessRuleError("Move bundles of one lot at a time.")


@transaction.atomic
def move_bundles(*, bundles, to_step, user, date=None, factory=None, location=None, counts=None, reason="") -> list:
    """Move bundles to an in-house stage (E7.6). Choosing an earlier stage is rework and needs a reason (BR-22).
    A stage at another factory moves the lot's WIP there with its cost (E7.9). Subcontracted stages go through a
    job work challan instead."""
    date = date or timezone.localdate()
    bundles = [Bundle.objects.select_related("lot", "lot__factory", "lot__company", "location", "location__factory",
                                             "current_step", "current_step__process", "sku").get(pk=b.pk) for b in bundles]
    if not bundles:
        raise BusinessRuleError("Scan or choose at least one bundle.")
    _check_same_lot(bundles)
    to_step = LotStep.objects.select_related("lot", "process", "factory").get(pk=to_step.pk)
    lot = bundles[0].lot
    if to_step.lot_id != lot.pk:
        raise BusinessRuleError("That stage belongs to a different lot.")
    if to_step.status == LotStep.Status.SKIPPED:
        raise BusinessRuleError(f"{to_step.process.name} was skipped on this lot.")
    if to_step.assignment == LotStep.Assignment.SUBCONTRACT:
        raise BusinessRuleError(f"{to_step.process.name} is done by a fabricator: issue a job work challan instead.")
    counts = counts or {}
    dest_factory = factory or to_step.factory or lot.factory
    dest_location = location or process_location(dest_factory)
    if dest_location.factory_id != dest_factory.pk:
        raise BusinessRuleError("The chosen place is not in that factory.")
    assert_factory_access(user, bundles[0].location.factory)

    plan = []
    for b in bundles:
        assert_factory_access(user, b.location.factory)
        in_step, done, backwards = check_entry(b, to_step, reason)
        c = counts.get(b.pk) or Count()
        if in_step is not None and in_step.process.no_loss and (c.loss or c.rejection or c.shortage):
            raise BusinessRuleError(
                f"{in_step.process.name} allows no loss: bundle {b.bundle_no} must leave with the {b.qty} pieces it came in with.")
        plan.append((b, in_step, done, backwards, c))

    # in-house labour for the stage each bundle is leaving (on the pieces that pass)
    accrue_leaving_labour(
        lot, [(b, in_step, b.qty - c.loss - c.rejection - c.shortage) for b, in_step, _, backwards, c in plan if not backwards],
        date, user, note=f"Stage output, moved to {to_step.process.name}")

    # inter-factory: move the lot's WIP cost for the pieces that cross, before they change place
    crossing = {}
    for b, _, _, _, c in plan:
        if b.location.factory_id != dest_factory.pk:
            crossing.setdefault(b.location.factory, 0)
            crossing[b.location.factory] += b.qty - c.loss - c.shortage
    for from_f, pieces in crossing.items():
        costing.transfer_cost_between_factories(lot=lot, from_factory=from_f, to_factory=dest_factory, pieces=pieces,
                                                date=date, user=user, source=lot)

    out = []
    for b, in_step, done, backwards, c in plan:
        kind = StageMovement.Kind.FACTORY if b.location.factory_id != dest_factory.pk else StageMovement.Kind.MOVE
        completed = (to_step.sequence - 1) if backwards else (in_step.sequence if in_step else b.completed_seq)
        if backwards:
            completed = min(completed, b.completed_seq)
        out.append(apply_move(
            bundle=b, kind=kind, to_location=dest_location, user=user, date=date, new_status=Bundle.Status.AT_STAGE,
            to_step=to_step, completed_seq=completed, loss=c.loss, rejection=c.rejection, shortage=c.shortage,
            reason=reason, is_rework=backwards))
    refresh_steps(lot)
    return out


def _packing_step(lot):
    steps = list(lot.steps.exclude(status=LotStep.Status.SKIPPED).order_by("-sequence"))
    for s in steps:
        if s.process.kind == "packing":
            return s
    return steps[0] if steps else None


@transaction.atomic
def pack_bundles(*, bundles, user, date=None, location=None) -> list:
    """Pack bundles and receive them into finished goods at lot cost (Dr Finished Goods, Cr WIP)."""
    date = date or timezone.localdate()
    bundles = [Bundle.objects.select_related("lot", "lot__factory", "lot__company", "location", "location__factory",
                                             "current_step", "sku").get(pk=b.pk) for b in bundles]
    if not bundles:
        raise BusinessRuleError("Choose at least one bundle to pack.")
    _check_same_lot(bundles)
    lot = bundles[0].lot
    pack_step = _packing_step(lot)
    factories = {b.location.factory_id for b in bundles}
    if len(factories) != 1:
        raise BusinessRuleError("Pack bundles that are in one factory.")
    factory = bundles[0].location.factory
    assert_factory_access(user, factory)
    target = location or dispatch_location(factory)
    if target.factory_id != factory.pk:
        raise BusinessRuleError("Finished goods must go to a location of the factory the bundles are in.")

    labour = ZERO
    for b in bundles:
        at_pack = (b.status == Bundle.Status.AT_STAGE and b.current_step_id == pack_step.pk)
        done_pack = (b.status == Bundle.Status.READY and b.completed_seq >= pack_step.sequence)
        if not (at_pack or done_pack):
            raise BusinessRuleError(f"Bundle {b.bundle_no} has not reached {pack_step.process.name}; move it there first.")
        if b.rework_qty:
            raise BusinessRuleError(f"Bundle {b.bundle_no} has pieces waiting for rework.")
        if at_pack and pack_step.assignment == LotStep.Assignment.IN_HOUSE:
            rate = pack_step.rework_rate if b.is_rework else pack_step.rate
            labour += costing.r2(rate * b.qty)
    if labour > 0:
        costing.accrue_labour(lot=lot, factory=factory, amount=labour, date=date, user=user,
                              note=f"Packing, {sum(b.qty for b in bundles)} pieces", source=lot)

    packed = sum(b.qty for b in bundles)
    here = costing.live_pieces(lot, factory)
    cost = costing.lot_cost(lot, factory)
    relief = cost if packed >= here else costing.r2(cost * packed / here)
    parts, running = [], ZERO
    for i, b in enumerate(bundles):
        part = relief - running if i == len(bundles) - 1 else costing.r2(relief * b.qty / packed)
        parts.append(part)
        running += part

    company = lot.company
    for b, part in zip(bundles, parts):
        qty = b.qty
        stock.post_movement(factory=factory, location=b.location, item=b.sku, qty=-Decimal(qty), value=Decimal("0"),
                            movement_type=T.TRANSFER_OUT, date=date, user=user, bundle=b, lot=lot, notes="Packed")
        stock.post_movement(factory=factory, location=target, item=b.sku, qty=Decimal(qty), value=part,
                            movement_type=T.PRODUCTION, date=date, user=user, bundle=b, lot=lot,
                            notes=f"Lot {lot.lot_no} packed")
        StageMovement.objects.create(
            factory=factory, bundle=b, kind=StageMovement.Kind.PACK, from_step=b.current_step, to_step=None,
            from_location=b.location, to_location=target, qty_out=qty, qty_in=qty, user=user)
        b.status, b.location = Bundle.Status.PACKED, target
        b.completed_seq = max(b.completed_seq, pack_step.sequence)
        b.save()
    if relief > 0:
        voucher = post_voucher(
            company=company, factory=factory, voucher_type="stock_journal", date=date, user=user, source=lot,
            narration=f"Lot {lot.lot_no}: {packed} pieces packed into finished goods",
            lines=[LineSpec(ledger=costing.ledger_for(company, "stock_finished"), debit=relief),
                   LineSpec(ledger=costing.ledger_for(company, "stock_wip"), credit=relief)])
        costing.add_cost(lot=lot, factory=factory, kind=LotCostEntry.Kind.RELIEF, amount=-relief, date=date,
                         note=f"{packed} pieces to finished goods", source=lot, voucher=voucher)
    refresh_steps(lot)
    return bundles
