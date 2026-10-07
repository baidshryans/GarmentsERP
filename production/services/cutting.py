"""Fabric issue, cutting and bundles (E7.4, E7.5).

Fabric moves from the godown to the cutting floor roll by roll. A cutting entry then consumes it: what was used or
wasted becomes lot cost (Dr WIP, Cr Raw Material Stock), and the remnant goes back to the store. Pieces cut per
size become bundles with QR tags.
"""
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Sum

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.factories import cutting_location, godown_location
from core.services.numbering import next_document_number
from inventory.models import FabricRoll, StockMovement
from inventory.services import stock
from ledger.services.posting import LineSpec, post_voucher
from masters.models import SKU
from production.models import (
    Bundle, CuttingEntry, CuttingRollUse, CuttingSize, FabricIssue, FabricIssueLine, Lot, LotCostEntry, LotStep,
)
from production.services import actions
from production.services import bundles as bundles_module
from production.services import costing

T = StockMovement.Type
THREE = Decimal("0.001")


def _open_lot(lot, user):
    lot = Lot.objects.select_related("company", "factory", "style", "colour", "bom_version").get(pk=lot.pk)
    assert_factory_access(user, lot.factory)
    if lot.status in (Lot.Status.CLOSED, Lot.Status.COMPLETED):
        raise BusinessRuleError(f"Lot {lot.lot_no} is finished.")
    return lot


def _fabric_step(issue, args, kwargs):
    lines = list(issue.lines.all())
    return {"lot": issue.lot, "date": issue.date, "doc": issue,
            "summary": f"{len(lines)} roll(s), {sum(l.qty for l in lines).normalize():f} to the cutting floor"}


def _cutting_step(entry, args, kwargs):
    return {"lot": entry.lot, "date": entry.date, "doc": entry,
            "summary": f"Lay {entry.lay_no}: {sum(cs.pieces for cs in entry.sizes.all())} pieces cut"}


def _bundles_step(made, args, kwargs):
    entry = CuttingEntry.objects.select_related("lot").get(pk=args[0].pk)
    return {"lot": entry.lot, "date": entry.date, "doc": entry,
            "summary": f"Lay {entry.lay_no}: {len(made)} bundle(s), {sum(b.qty for b in made)} pieces"}


@actions.recorded(actions.Kind.FABRIC, _fabric_step)
@transaction.atomic
def issue_fabric(*, lot, lines, user, date, from_location=None, estimated_pieces=None) -> FabricIssue:
    """Issue rolls to the cutting floor for a lot. lines = [(roll, qty)]. Blocked above a roll's balance (BR-02);
    warns (flag on the issue) when rolls of different shade lots go into one lot. `estimated_pieces` is the
    cutting master's own estimate of the pieces this fabric will give; the cutting is compared with it."""
    lot = _open_lot(lot, user)
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("Choose at least one roll to issue.")
    if estimated_pieces is not None and (isinstance(estimated_pieces, bool) or not isinstance(estimated_pieces, int)
                                         or estimated_pieces <= 0):
        raise BusinessRuleError("The estimated pieces must be a whole number above zero, or left empty.")
    factory = lot.factory
    source = from_location or godown_location(factory)
    cutting = cutting_location(factory)
    if source.factory_id != factory.pk:
        raise BusinessRuleError("The fabric must come from a location of the lot's factory; transfer it first.")
    issue = FabricIssue.objects.create(
        company=lot.company, factory=factory, lot=lot, from_location=source, to_location=cutting, date=date, created_by=user)
    for roll, qty in lines:
        if isinstance(qty, float) or qty <= 0:
            raise BusinessRuleError(f"The quantity of roll {roll.label_code} must be above zero (BR-01).")
        if roll.material.kind != "fabric":
            raise BusinessRuleError(f"{roll.label_code} is not fabric.")
        out = stock.post_movement(
            factory=factory, location=source, item=roll.material, qty=-qty, roll=roll, movement_type=T.TRANSFER_OUT,
            date=date, user=user, source=issue, lot=lot, notes=f"Issued to lot {lot.lot_no}")
        stock.post_movement(
            factory=factory, location=cutting, item=roll.material, qty=qty, roll=roll, value=-out.value,
            movement_type=T.TRANSFER_IN, date=date, user=user, source=issue, lot=lot, notes=f"Issued to lot {lot.lot_no}")
        FabricIssueLine.objects.create(issue=issue, roll=roll, qty=qty, value=-out.value)
    if estimated_pieces is not None:
        issue.expected_pieces = estimated_pieces
        issue.save(update_fields=["expected_pieces"])
    shades = {l.roll.lot_no for i in lot.fabric_issues.all() for l in i.lines.select_related("roll") if l.roll.lot_no}
    if len(shades) > 1:
        issue.mixed_shades = True
        issue.save(update_fields=["mixed_shades"])
    if lot.status == Lot.Status.PLANNED:
        lot.status = Lot.Status.CUTTING
        lot.save(update_fields=["status"])
    return issue


def estimate_basis(lot):
    """(pieces, fabric) of the issues that carry an estimate: what the cutting master expects, and from how much."""
    pieces, fabric = 0, Decimal("0")
    for issue in lot.fabric_issues.exclude(expected_pieces__isnull=True).prefetch_related("lines"):
        pieces += issue.expected_pieces
        fabric += sum((l.qty for l in issue.lines.all()), Decimal("0"))
    return pieces, fabric


def estimated_pieces(lot, fabric=None):
    """Whole pieces the estimate says `fabric` should give; the fabric still with the lot (issued less remnants
    returned) when left out. None when no issue carries an estimate."""
    pieces, basis = estimate_basis(lot)
    if not pieces or basis <= 0:
        return None
    return int(pieces * (fabric_with_lot(lot) if fabric is None else Decimal(fabric)) / basis)


def fabric_with_lot(lot) -> Decimal:
    """Fabric issued to the lot so far, less remnants sent back to the store."""
    issued = FabricIssueLine.objects.filter(issue__lot=lot).aggregate(s=Sum("qty"))["s"] or Decimal("0")
    back = CuttingRollUse.objects.filter(entry__lot=lot).aggregate(s=Sum("remnant_qty"))["s"] or Decimal("0")
    return issued - back


def _check_loss(pieces, loss):
    """Loss per size ({Size: n}) can be no more than the pieces cut of that size."""
    loss = {s: n for s, n in (loss or {}).items() if n}
    for size, n in loss.items():
        if n < 0 or n > pieces.get(size, 0):
            raise BusinessRuleError(f"Size {size.code}: the pieces lost cannot be more than the {pieces.get(size, 0)} cut.")
    return loss


@dataclass
class RollUseSpec:
    roll: object
    used: Decimal
    waste: Decimal = Decimal("0.000")
    remnant: Decimal = Decimal("0.000")


@actions.recorded(actions.Kind.CUTTING, _cutting_step)
@transaction.atomic
def record_cutting(*, lot, pieces, rolls, user, date, notes="", loss=None) -> CuttingEntry:
    """Record a lay. pieces = {Size: count}; rolls = [RollUseSpec]; loss = {Size: pieces cut but lost}, which can
    also be given when the bundles are made. Returns the entry with its variance: the pieces cut against the
    pieces estimated for the fabric burnt."""
    lot = _open_lot(lot, user)
    pieces = {s: n for s, n in pieces.items() if n}
    if not pieces or any(n < 0 for n in pieces.values()):
        raise BusinessRuleError("Enter the pieces cut for at least one size.")
    allowed = {s.size_id for s in lot.style.style_sizes.all()}
    for size in pieces:
        if size.pk not in allowed:
            raise BusinessRuleError(f"Size {size.code} is not a size of {lot.style.style_no}.")
    rolls = list(rolls)
    if not rolls:
        raise BusinessRuleError("Record the rolls this lay used.")
    factory, company = lot.factory, lot.company
    cutting, godown = cutting_location(factory), godown_location(factory)
    lay_no = (lot.cuttings.aggregate(m=Max("lay_no"))["m"] or 0) + 1
    entry = CuttingEntry.objects.create(company=company, factory=factory, lot=lot, lay_no=lay_no, date=date, notes=notes, created_by=user)
    loss = _check_loss(pieces, loss)
    for size, n in pieces.items():
        CuttingSize.objects.create(entry=entry, size=size, pieces=n, loss=loss.get(size, 0))
    cut_total = sum(pieces.values())
    for cut_step in bundles_module.cutting_steps(lot):   # in-house cutting is paid on the pieces cut
        if cut_step.status != LotStep.Status.SKIPPED and cut_step.assignment == LotStep.Assignment.IN_HOUSE:
            costing.accrue_labour(lot=lot, factory=factory, amount=cut_step.rate * cut_total, date=date, user=user,
                                  note=f"Cutting, lay {lay_no}: {cut_total} pieces", source=entry)

    consumed = []
    actual = Decimal("0")
    total_value = Decimal("0.00")
    for spec in rolls:
        for label, v in (("used", spec.used), ("waste", spec.waste), ("remnant", spec.remnant)):
            if isinstance(v, float) or v < 0:
                raise BusinessRuleError(f"Roll {spec.roll.label_code}: {label} must be a number of zero or more.")
        burnt = spec.used + spec.waste
        if burnt + spec.remnant <= 0:
            raise BusinessRuleError(f"Roll {spec.roll.label_code}: enter what was used, wasted or returned (BR-01).")
        use = CuttingRollUse.objects.create(entry=entry, roll=spec.roll, used_qty=spec.used, waste_qty=spec.waste,
                                            remnant_qty=spec.remnant)
        if burnt > 0:
            m = stock.post_movement(
                factory=factory, location=cutting, item=spec.roll.material, qty=-burnt, roll=spec.roll,
                movement_type=T.ISSUE, date=date, user=user, source=entry, lot=lot, notes=f"Cut: lot {lot.lot_no} lay {lay_no}")
            consumed.append(m)
            use.value = -m.value
            total_value += use.value
            actual += burnt
        if spec.remnant > 0:
            out = stock.post_movement(
                factory=factory, location=cutting, item=spec.roll.material, qty=-spec.remnant, roll=spec.roll,
                movement_type=T.TRANSFER_OUT, date=date, user=user, source=entry, lot=lot, notes="Remnant returned to store")
            stock.post_movement(
                factory=factory, location=godown, item=spec.roll.material, qty=spec.remnant, roll=spec.roll, value=-out.value,
                movement_type=T.TRANSFER_IN, date=date, user=user, source=entry, lot=lot, notes="Remnant returned to store")
        use.save(update_fields=["value"])

    if consumed and total_value > 0:
        voucher = post_voucher(
            company=company, factory=factory, voucher_type="stock_journal", date=date, user=user, source=entry,
            narration=f"Fabric cut for lot {lot.lot_no}, lay {lay_no}",
            lines=[LineSpec(ledger=costing.ledger_for(company, "stock_wip"), debit=costing.r2(total_value)),
                   LineSpec(ledger=costing.ledger_for(company, "stock_raw_material"), credit=costing.r2(total_value))])
        costing.add_cost(lot=lot, factory=factory, kind=LotCostEntry.Kind.FABRIC, amount=total_value, date=date,
                         note=f"Lay {lay_no}", source=entry, voucher=voucher)

    entry.fabric_value = costing.r2(total_value)
    entry.expected_pieces = estimated_pieces(lot, actual)
    if entry.expected_pieces:
        pct = (Decimal(cut_total - entry.expected_pieces) / entry.expected_pieces * 100).quantize(Decimal("0.01"))
        entry.variance_pct = pct
        entry.over_tolerance = abs(pct) > company.bom_tolerance_pct
    entry.save()
    if lot.status != Lot.Status.IN_PRODUCTION:
        lot.status = Lot.Status.CUTTING
        lot.save(update_fields=["status"])
    return entry


def _even_bundles(sizes, bundle_size):
    """{size pk: [pieces]} for bundles of `bundle_size` pieces each; the last of a size may be smaller."""
    if bundle_size <= 0:
        raise BusinessRuleError("The bundle size must be more than zero.")
    most = max((cs.good for cs in sizes), default=0)
    if most and bundle_size > most:   # a bundle holds one size, so it can never be bigger than the largest size cut
        raise BusinessRuleError(
            f"A bundle of {bundle_size} is more than the pieces cut: the largest size has {most} pieces to bundle. "
            f"Enter {most} or fewer per bundle.")
    return {cs.size_id: [bundle_size] * (cs.good // bundle_size) + ([cs.good % bundle_size] if cs.good % bundle_size else [])
            for cs in sizes}


def _counted_bundles(sizes, bundles):
    """{size pk: [pieces]} from the bundles as they came off the cutting floor ({Size: [pieces in each bundle]}).
    The bundles of a size must add up to the pieces of it left to bundle."""
    cut = {cs.size_id for cs in sizes}
    given = {}
    for size, counts in bundles.items():
        counts = list(counts)
        if not counts:
            continue
        if size.pk not in cut:
            raise BusinessRuleError(f"Size {size.code} was not cut in this lay.")
        if any(isinstance(n, bool) or not isinstance(n, int) or n <= 0 for n in counts):
            raise BusinessRuleError(f"Size {size.code}: every bundle must have a whole number of pieces above zero.")
        given[size.pk] = counts
    for cs in sizes:
        total = sum(given.get(cs.size_id, []))
        if total != cs.good:
            gap = f"{cs.good - total} short" if total < cs.good else f"{total - cs.good} too many"
            raise BusinessRuleError(
                f"Size {cs.size.code}: the bundles add up to {total} pieces but {cs.good} are to be bundled ({gap}). "
                f"Correct the bundles, or the pieces lost in cutting.")
    return given


@actions.recorded(actions.Kind.BUNDLES, _bundles_step)
@transaction.atomic
def create_bundles(entry, *, user, bundles=None, bundle_size=None, loss=None) -> list:
    """Make bundles from a lay's good pieces per size. bundles = {Size: [pieces in each bundle]}, as counted when
    they come off the cutting floor: bundles need not be equal, but those of a size must add up to its good pieces.
    `bundle_size` instead makes equal bundles (the last of a size may be smaller).
    loss = {Size: pieces lost in cutting}, known at the end of cutting: those pieces are never bundled."""
    entry = CuttingEntry.objects.select_related("lot", "lot__style", "lot__colour", "factory").get(pk=entry.pk)
    lot = _open_lot(entry.lot, user)
    if entry.bundled:
        raise BusinessRuleError("Bundles were already made for this lay.")
    if (bundles is None) == (bundle_size is None):
        raise BusinessRuleError("Give the pieces in each bundle.")
    cutting = cutting_location(lot.factory)
    sizes = list(entry.sizes.select_related("size").order_by("size__sort_order"))
    if loss is not None:
        loss = _check_loss({cs.size: cs.pieces for cs in sizes}, loss)
        for cs in sizes:
            cs.loss = loss.get(cs.size, 0)
            cs.save(update_fields=["loss"])
    per_size = _counted_bundles(sizes, bundles) if bundles is not None else _even_bundles(sizes, bundle_size)
    # a split bundle is numbered after its first; go on from the highest number, as bundles made again after an
    # undo must not take a number another lay still holds
    seq = max((int(no[1:]) for no in lot.bundles.filter(split_from__isnull=True).values_list("bundle_no", flat=True)
               if no[1:].isdigit()), default=0)
    made = []
    for cs in sizes:
        sku = SKU.objects.filter(style=lot.style, colour=lot.colour, size=cs.size, is_active=True).first()
        if sku is None:
            raise BusinessRuleError(f"There is no SKU for {lot.style.style_no} / {lot.colour} / {cs.size}.")
        for n in per_size.get(cs.size_id, []):
            seq += 1
            b = Bundle.objects.create(
                lot=lot, entry=entry, bundle_no=f"B{seq:03d}", sku=sku, qty=n, original_qty=n,
                qr_token=uuid.uuid4().hex[:16], location=cutting, completed_seq=bundles_module.cutting_done_seq(lot))
            stock.post_movement(
                factory=lot.factory, location=cutting, item=sku, qty=Decimal(n), value=Decimal("0"),
                movement_type=T.PRODUCTION, date=entry.date, user=user, source=entry, bundle=b, lot=lot,
                notes=f"Cut: {b.bundle_no}")
            made.append(b)
    entry.bundled = True
    entry.save(update_fields=["bundled"])
    bundles_module.refresh_steps(lot)
    return made
