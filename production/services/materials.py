"""Accessories and packing materials used by a process (E7.6, E8.1).

The style's list says which materials a process needs per piece. When bundles enter an in-house step, or are
packed, those materials are issued from the store into the lot's cost (Dr WIP, Cr Raw Material Stock) in the same
transaction as the move. A fabricator's step gets them on the job work challan instead. What is issued is always
what the user confirmed: the list only fills the screen in.
"""
from decimal import Decimal

from django.db import transaction

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.factories import godown_location
from inventory.models import StockMovement
from inventory.services import stock
from ledger.services.posting import LineSpec, post_voucher
from masters.services import boms
from production.models import LotCostEntry, StageMovement, StepMaterialIssue, StepMaterialIssueLine
from production.services import costing

T = StockMovement.Type
ZERO = Decimal("0.00")
THREE = Decimal("0.001")


def been_at(bundle, step) -> bool:
    """Has this bundle (or the bundle it was split from) entered `step` before? Then its materials were issued."""
    ids = [bundle.pk]
    while bundle.split_from_id:
        bundle = bundle.split_from
        ids.append(bundle.pk)
    return StageMovement.objects.filter(bundle_id__in=ids, to_step=step).exists()


def _pieces_by_size(bundles) -> dict:
    out = {}
    for b in bundles:
        out[b.sku.size] = out.get(b.sku.size, 0) + b.qty
    return out


def needs_on_entry(lot, step, bundles) -> dict:
    """Materials the list says `step` needs for bundles about to enter it: {Material: quantity}. A bundle coming
    back to a step it has been through (rework) needs nothing more. The packing step's materials are issued when
    the bundles are packed, not when they reach it."""
    if step.process.kind == "packing":
        return {}
    return boms.needs(lot.bom_version, step.process, _pieces_by_size([b for b in bundles if not been_at(b, step)]))


def needs_at_packing(lot, step, bundles) -> dict:
    """Materials the list says packing needs for these bundles: {Material: quantity}."""
    return boms.needs(lot.bom_version, step.process, _pieces_by_size(bundles)) if step is not None else {}


def unused_lines(lot) -> list:
    """Lines of the lot's list that no step of its route uses: those materials are never filled in."""
    processes = [s.process for s in lot.steps.select_related("process") if s.status != "skipped"]
    return boms.unused_lines(lot.bom_version, processes)


def clean_lines(lines) -> list:
    """[(material, quantity)] checked: above zero, no fabric, each material once."""
    out, seen = [], set()
    for material, qty in lines or []:
        if isinstance(qty, float) or qty is None or Decimal(qty) <= 0:
            raise BusinessRuleError(f"The quantity of {material.name} must be above zero (BR-01).")
        if material.kind == "fabric":
            raise BusinessRuleError(f"{material.name} is fabric: issue it to cutting by roll.")
        if material.pk in seen:
            raise BusinessRuleError(f"{material.name} is entered twice.")
        seen.add(material.pk)
        out.append((material, Decimal(qty).quantize(THREE)))
    return out


@transaction.atomic
def issue_to_step(*, lot, step, factory, lines, user, date, pieces=0):
    """Issue materials from the factory's store to an in-house step of a lot. lines = [(material, quantity)].
    Returns the issue, or None when there is nothing to issue. Blocked above the stock on hand unless the company
    allows negative stock (BR-02)."""
    lines = clean_lines(lines)
    if not lines:
        return None
    assert_factory_access(user, factory)
    company = lot.company
    godown = godown_location(factory)
    issue = StepMaterialIssue.objects.create(company=company, factory=factory, lot=lot, step=step, date=date,
                                             pieces=pieces, created_by=user)
    total = ZERO
    for material, qty in lines:
        m = stock.post_movement(
            factory=factory, location=godown, item=material, qty=-qty, movement_type=T.ISSUE, date=date, user=user,
            source=issue, lot=lot, notes=f"{step.process.name}, lot {lot.lot_no}")
        StepMaterialIssueLine.objects.create(issue=issue, material=material, qty=qty, value=-m.value)
        total += -m.value
    total = costing.r2(total)
    if total > 0:
        voucher = post_voucher(
            company=company, factory=factory, voucher_type="stock_journal", date=date, user=user, source=issue,
            narration=f"Materials used at {step.process.name}, lot {lot.lot_no}",
            lines=[LineSpec(ledger=costing.ledger_for(company, "stock_wip"), debit=total),
                   LineSpec(ledger=costing.ledger_for(company, "stock_raw_material"), credit=total)])
        costing.add_cost(lot=lot, factory=factory, kind=LotCostEntry.Kind.TRIM, amount=total, date=date,
                         note=f"Materials at {step.process.name}", source=issue, voucher=voucher)
        issue.voucher = voucher
        issue.save(update_fields=["voucher"])
    return issue
