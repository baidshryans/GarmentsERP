"""Production orders and lots (E7.1, E7.2). Releasing an order makes one lot per style and colour, each with its own
copy of the route so every step can be assigned in-house or to a fabricator on that lot (PRD principle 3)."""
from dataclasses import dataclass, field
from datetime import date as date_cls
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from inventory.models import StockMovement
from inventory.services import stock
from ledger.services.posting import LineSpec, post_voucher
from masters.services import boms
from production.models import (
    Bundle, Lot, LotCostEntry, LotStep, ProductionOrder, ProductionOrderLine, ProductionOrderLineSize,
)
from production.services import costing

PRODUCTION_SCREEN = "production.order"


@dataclass
class OrderLineSpec:
    style: object
    colour: object
    total_qty: int
    ratios: dict = field(default_factory=dict)  # {Size: ratio}


def spread(total: int, ratios: dict) -> dict:
    """Spread a total over sizes by ratio. Whole pieces only; leftovers go to the largest remainders."""
    if total <= 0:
        raise BusinessRuleError("The total quantity must be more than zero.")
    ratios = {s: r for s, r in ratios.items() if r}
    weight = sum(ratios.values())
    if weight <= 0:
        raise BusinessRuleError("Give a size ratio (for example 1 : 2 : 2 : 1).")
    exact = {s: Decimal(total) * r / weight for s, r in ratios.items()}
    out = {s: int(v) for s, v in exact.items()}
    left = total - sum(out.values())
    for s in sorted(exact, key=lambda k: (exact[k] - out[k], ratios[k]), reverse=True)[:left]:
        out[s] += 1
    return out


def _write_lines(order, lines):
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("An order needs at least one style and colour.")
    for spec in lines:
        style = spec.style
        if not style.style_colours.filter(colour=spec.colour).exists():
            raise BusinessRuleError(f"{spec.colour} is not a colour of {style.style_no}.")
        allowed = {s.size_id for s in style.style_sizes.all()}
        for size in spec.ratios:
            if size.pk not in allowed:
                raise BusinessRuleError(f"Size {size.code} is not a size of {style.style_no}.")
        parts = spread(spec.total_qty, spec.ratios)
        line = ProductionOrderLine.objects.create(
            order=order, style=style, colour=spec.colour, total_qty=spec.total_qty,
            bom_version=boms.current_version(style), route=style.default_route,
        )
        for size, ratio in spec.ratios.items():
            if ratio:
                ProductionOrderLineSize.objects.create(line=line, size=size, ratio=ratio, qty=parts[size])


@transaction.atomic
def create_order(*, company, factory, date, lines, user, due_date=None, purpose="stock", order_reference="", remarks="") -> ProductionOrder:
    assert_factory_access(user, factory)
    order = ProductionOrder.objects.create(
        company=company, factory=factory, date=date, due_date=due_date, purpose=purpose,
        order_reference=order_reference, remarks=remarks, created_by=user,
    )
    _write_lines(order, lines)
    return order


@transaction.atomic
def update_order(order, *, lines, user, date=None, due_date=None, order_reference=None, remarks=None) -> ProductionOrder:
    order = ProductionOrder.objects.get(pk=order.pk)
    assert_factory_access(user, order.factory)
    if order.status != ProductionOrder.Status.DRAFT:
        raise BusinessRuleError("Only a draft order can be edited.")
    order.date = date or order.date
    order.due_date = due_date if due_date is not None else order.due_date
    if order_reference is not None:
        order.order_reference = order_reference
    if remarks is not None:
        order.remarks = remarks
    order.save()
    order.lines.all().delete()
    _write_lines(order, lines)
    return order


@transaction.atomic
def release_order(order, *, user) -> ProductionOrder:
    order = ProductionOrder.objects.select_related("company", "factory").get(pk=order.pk)
    assert_factory_access(user, order.factory)
    if order.status != ProductionOrder.Status.DRAFT:
        raise BusinessRuleError("This order has already been released.")
    lines = list(order.lines.select_related("style", "colour", "bom_version", "route"))
    for line in lines:
        # re-read the latest BOM and route: they may have changed since the draft was saved (E7.1)
        line.bom_version = boms.current_version(line.style)
        line.route = line.style.default_route
        if line.bom_version is None:
            raise BusinessRuleError(f"{line.style.style_no} has no BOM yet; define it before releasing the order.")
        if line.route is None or not line.route.steps.exists():
            raise BusinessRuleError(f"{line.style.style_no} has no default route; choose one on the style.")
        line.save(update_fields=["bom_version", "route"])
    order.number = next_document_number(factory=order.factory, doc_type="production_order", on_date=order.date)
    order.status, order.released_at = ProductionOrder.Status.RELEASED, timezone.now()
    order.save()
    for line in lines:
        lot = Lot.objects.create(
            company=order.company, factory=order.factory, lot_no=next_document_number(
                factory=order.factory, doc_type="lot", on_date=order.date),
            order_line=line, style=line.style, colour=line.colour, bom_version=line.bom_version,
        )
        for step in line.route.steps.select_related("default_factory", "default_party").order_by("sequence"):
            subcontract = step.assignment == "subcontract"
            LotStep.objects.create(
                lot=lot, sequence=step.sequence, process=step.process, is_mandatory=step.is_mandatory,
                assignment=step.assignment, rate=step.rate,
                factory=None if subcontract else (step.default_factory or order.factory),
                party=step.default_party if subcontract else None,
            )
    return order


def refresh_status(order):
    """Move an order between released, in production, partly completed and completed as its lots progress."""
    order = ProductionOrder.objects.get(pk=order.pk)
    if order.status in (ProductionOrder.Status.DRAFT, ProductionOrder.Status.CLOSED):
        return order
    lots = list(Lot.objects.filter(order_line__order=order))
    if lots and all(l.status in ("completed", "closed") for l in lots):
        order.status = ProductionOrder.Status.COMPLETED
    elif any(l.status == "completed" for l in lots):
        order.status = ProductionOrder.Status.PARTLY
    elif any(l.status in ("cutting", "in_production") for l in lots):
        order.status = ProductionOrder.Status.IN_PRODUCTION
    else:
        order.status = ProductionOrder.Status.RELEASED
    order.save()
    return order


@transaction.atomic
def close_order(order, *, user, reason) -> ProductionOrder:
    """Close an order and write off whatever is still in progress. Needs approval (PRD section 6)."""
    order = ProductionOrder.objects.select_related("company", "factory").get(pk=order.pk)
    if not user.has_screen_perm(PRODUCTION_SCREEN, "approve"):
        raise BusinessRuleError("Only the owner can close an order and write off its work in progress.")
    assert_factory_access(user, order.factory)
    if order.status in (ProductionOrder.Status.DRAFT, ProductionOrder.Status.CLOSED):
        raise BusinessRuleError("Only a released order can be closed.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to close the order.")
    today = timezone.localdate()
    company = order.company
    for lot in Lot.objects.filter(order_line__order=order).select_related("factory"):
        for bundle in Bundle.objects.filter(lot=lot, status__in=Bundle.LIVE).select_related("sku", "location"):
            stock.post_movement(
                factory=bundle.location.factory, location=bundle.location, item=bundle.sku, qty=-Decimal(bundle.qty),
                movement_type=StockMovement.Type.LOSS, date=today, user=user, bundle=bundle, lot=lot, value=Decimal("0"),
                notes=f"Order {order.number} closed: {reason.strip()}"[:255],
            )
            bundle.status, bundle.qty, bundle.rework_qty = Bundle.Status.SCRAPPED, 0, 0
            bundle.save(update_fields=["status", "qty", "rework_qty"])
        for factory_id in set(lot.cost_entries.values_list("factory_id", flat=True)):
            from core.models import Factory

            f = Factory.objects.get(pk=factory_id)
            amount = costing.lot_cost(lot, f)
            if amount > 0:
                voucher = post_voucher(
                    company=company, factory=f, voucher_type="stock_journal", date=today, user=user,
                    narration=f"Work in progress written off: lot {lot.lot_no}, order {order.number} closed",
                    lines=[LineSpec(ledger=costing.ledger_for(company, "wip_written_off"), debit=amount),
                           LineSpec(ledger=costing.ledger_for(company, "stock_wip"), credit=amount)],
                    scope_lines=False,
                )
                costing.add_cost(lot=lot, factory=f, kind=LotCostEntry.Kind.WRITE_OFF, amount=-amount, date=today,
                                 note=reason.strip(), voucher=voucher)
        lot.steps.filter(status__in=("pending", "in_progress")).update(status="skipped")
        lot.status = Lot.Status.CLOSED
        lot.save(update_fields=["status"])
    order.status, order.closed_at, order.closed_by, order.close_reason = (
        ProductionOrder.Status.CLOSED, timezone.now(), user, reason.strip())
    order.save()
    return order
