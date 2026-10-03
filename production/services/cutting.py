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
from masters.services import boms
from production.models import (
    Bundle, CuttingEntry, CuttingRollUse, CuttingSize, FabricIssue, FabricIssueLine, Lot, LotCostEntry,
)
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


@transaction.atomic
def issue_fabric(*, lot, lines, user, date, from_location=None) -> FabricIssue:
    """Issue rolls to the cutting floor for a lot. lines = [(roll, qty)]. Blocked above a roll's balance (BR-02);
    warns (flag on the issue) when rolls of different shade lots go into one lot."""
    lot = _open_lot(lot, user)
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("Choose at least one roll to issue.")
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
    shades = {l.roll.lot_no for i in lot.fabric_issues.all() for l in i.lines.select_related("roll") if l.roll.lot_no}
    if len(shades) > 1:
        issue.mixed_shades = True
        issue.save(update_fields=["mixed_shades"])
    if lot.status == Lot.Status.PLANNED:
        lot.status = Lot.Status.CUTTING
        lot.save(update_fields=["status"])
    return issue


def expected_fabric(lot, pieces) -> Decimal:
    """Fabric the BOM says these pieces need ({Size: pieces}), wastage allowance included."""
    version = lot.bom_version
    if version is None:
        return Decimal("0.000")
    total = Decimal("0")
    for size, n in pieces.items():
        for material, qty, wastage in boms.consumption_for(version, size):
            if material.kind == "fabric":
                total += qty * (1 + wastage / 100) * n
    return total.quantize(THREE)


@dataclass
class RollUseSpec:
    roll: object
    used: Decimal
    waste: Decimal = Decimal("0.000")
    remnant: Decimal = Decimal("0.000")


@transaction.atomic
def record_cutting(*, lot, pieces, rolls, user, date, notes="") -> CuttingEntry:
    """Record a lay. pieces = {Size: count}; rolls = [RollUseSpec]. Returns the entry with its BOM variance."""
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
    for size, n in pieces.items():
        CuttingSize.objects.create(entry=entry, size=size, pieces=n)

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

    expected = expected_fabric(lot, pieces)
    entry.fabric_value = costing.r2(total_value)
    entry.expected_fabric = expected
    if expected > 0:
        pct = ((actual - expected) / expected * 100).quantize(Decimal("0.01"))
        entry.variance_pct = pct
        entry.over_tolerance = abs(pct) > company.bom_tolerance_pct
    entry.save()
    if lot.status != Lot.Status.IN_PRODUCTION:
        lot.status = Lot.Status.CUTTING
        lot.save(update_fields=["status"])
    return entry


@transaction.atomic
def create_bundles(entry, *, bundle_size, user) -> list:
    """Make bundles from a lay's pieces per size, `bundle_size` pieces each (the last of a size may be smaller)."""
    entry = CuttingEntry.objects.select_related("lot", "lot__style", "lot__colour", "factory").get(pk=entry.pk)
    lot = _open_lot(entry.lot, user)
    if entry.bundled:
        raise BusinessRuleError("Bundles were already made for this lay.")
    if bundle_size <= 0:
        raise BusinessRuleError("The bundle size must be more than zero.")
    cutting = cutting_location(lot.factory)
    seq = lot.bundles.count()
    made = []
    for cs in entry.sizes.select_related("size").order_by("size__sort_order"):
        sku = SKU.objects.filter(style=lot.style, colour=lot.colour, size=cs.size, is_active=True).first()
        if sku is None:
            raise BusinessRuleError(f"There is no SKU for {lot.style.style_no} / {lot.colour} / {cs.size}.")
        remaining = cs.pieces
        while remaining > 0:
            n = min(bundle_size, remaining)
            remaining -= n
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
