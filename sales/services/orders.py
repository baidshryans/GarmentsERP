"""Sale orders (E4.1, E4.7). An order is a draft until confirmed; a confirmed made-to-order (MTO) order raises a
draft production order that carries only the order number, never the customer (BR-15)."""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from production.services import orders as production_orders
from sales.models import SaleOrder, SaleOrderLine
from sales.services import pricing
from sales.services.common import check_decimal, check_discount, check_pieces

S = SaleOrder.Status


@dataclass
class OrderLineSpec:
    sku: object
    qty: Decimal
    rate: Decimal | None = None          # blank: the customer's rate is looked up (E4.3)
    discount_pct: Decimal | None = None  # blank: the customer's standing discount


def _write_lines(order, specs, user):
    specs = list(specs)
    if not specs:
        raise BusinessRuleError("Add at least one piece to the order.")
    seen = set()
    for spec in specs:
        sku = spec.sku
        if sku.pk in seen:
            raise BusinessRuleError(f"{sku} appears twice; combine it into one cell of the grid.")
        seen.add(sku.pk)
        if not sku.is_active:
            raise BusinessRuleError(f"{sku} is not active.")
        qty = check_pieces(spec.qty, f"Quantity of {sku}")
        rate = spec.rate
        if rate is None:
            price = pricing.resolve(order.customer, sku, qty, order.date)
            if price is None:
                raise BusinessRuleError(f"No rate found for {sku.style.style_no}; enter one.")
            rate = price.rate
        rate = check_decimal(rate, f"Rate of {sku}")
        if rate < 0:
            raise BusinessRuleError(f"The rate of {sku} cannot be negative.")
        disc = order.customer.discount_pct if spec.discount_pct is None else spec.discount_pct
        disc = check_discount(user, order.company, disc)
        SaleOrderLine.objects.create(order=order, sku=sku, qty=qty, rate=rate.quantize(Decimal("0.01")), discount_pct=disc)


def _check_customer(customer):
    if not customer.is_customer:
        raise BusinessRuleError(f"{customer.name} is not marked as a customer.")


@transaction.atomic
def create_order(*, company, factory, customer, date, lines, user, order_type="stock", due_date=None, remarks="") -> SaleOrder:
    assert_factory_access(user, factory)
    _check_customer(customer)
    order = SaleOrder.objects.create(company=company, factory=factory, customer=customer, date=date, due_date=due_date,
                                     order_type=order_type, remarks=remarks, created_by=user)
    _write_lines(order, lines, user)
    return order


@transaction.atomic
def update_order(order, *, lines, user, customer=None, date=None, due_date=None, order_type=None, remarks=None) -> SaleOrder:
    order = SaleOrder.objects.select_related("customer", "company", "factory").get(pk=order.pk)
    assert_factory_access(user, order.factory)
    if order.status != S.DRAFT:
        raise BusinessRuleError("Only a draft order can be edited.")
    if customer is not None:
        _check_customer(customer)
        order.customer = customer
    order.date = date or order.date
    order.due_date = due_date
    order.order_type = order_type or order.order_type
    if remarks is not None:
        order.remarks = remarks
    order.save()
    order.lines.all().delete()
    _write_lines(order, lines, user)
    return order


def _production_requirement(order, user):
    """A draft production order for the MTO order: style, colour and the size grid, with the order number only."""
    groups = {}
    for line in order.lines.select_related("sku__style", "sku__colour", "sku__size"):
        groups.setdefault((line.sku.style, line.sku.colour), {})[line.sku.size] = int(line.qty)
    specs = [production_orders.OrderLineSpec(style=style, colour=colour, total_qty=sum(by_size.values()), ratios=by_size)
             for (style, colour), by_size in groups.items()]
    return production_orders.create_order(
        company=order.company, factory=order.factory, date=order.date, due_date=order.due_date, lines=specs, user=user,
        purpose="mto", order_reference=order.number, remarks=f"Made to order {order.number}")


@transaction.atomic
def confirm_order(order, *, user) -> SaleOrder:
    order = SaleOrder.objects.select_related("customer", "company", "factory").get(pk=order.pk)
    assert_factory_access(user, order.factory)
    if order.status != S.DRAFT:
        raise BusinessRuleError("This order has already been confirmed.")
    if not order.lines.exists():
        raise BusinessRuleError("The order has no lines.")
    order.number = next_document_number(factory=order.factory, doc_type="sale_order", on_date=order.date)
    order.status = S.CONFIRMED
    order.save()
    if order.order_type == SaleOrder.Type.MTO:
        order.production_order = _production_requirement(order, user)
        order.save(update_fields=["production_order"])
    return order


@transaction.atomic
def create_and_confirm(*, user, **details) -> SaleOrder:
    """Take an order and confirm it in one go (the form's "Save and confirm"). `details` are the arguments of
    `create_order`. One transaction: if confirming fails, no draft is left behind, no number is used and no
    production requirement is raised."""
    return confirm_order(create_order(user=user, **details), user=user)


@transaction.atomic
def cancel_order(order, *, user, reason) -> SaleOrder:
    order = SaleOrder.objects.select_related("factory", "production_order").get(pk=order.pk)
    assert_factory_access(user, order.factory)
    if order.status in (S.CANCELLED, S.CLOSED, S.DISPATCHED):
        raise BusinessRuleError("This order can no longer be cancelled.")
    if order.status != S.DRAFT and not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the order.")
    if order.invoices.exclude(status="cancelled").exists() or order.packing_lists.exclude(status="cancelled").exists():
        raise BusinessRuleError("The order has packing lists or bills; cancel them first, or close the order instead.")
    po = order.production_order
    if po is not None and po.status != "draft":
        raise BusinessRuleError(f"Production {po.number} has been released for this order; close that production order first.")
    order.status = S.CANCELLED
    order.close_reason = reason.strip()[:255]
    order.save()
    return order


@transaction.atomic
def close_order(order, *, user, reason) -> SaleOrder:
    """Short-close: no more will be dispatched against the balance."""
    order = SaleOrder.objects.select_related("factory").get(pk=order.pk)
    assert_factory_access(user, order.factory)
    if order.status not in (S.CONFIRMED, S.PARTLY):
        raise BusinessRuleError("Only a confirmed order can be closed.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to close the order.")
    if order.packing_lists.filter(status__in=("draft", "packed")).exists():
        raise BusinessRuleError("There is a packing list not yet billed; bill or cancel it first.")
    order.status = S.CLOSED
    order.close_reason = reason.strip()[:255]
    order.save()
    return order


def refresh_status(order):
    """Confirmed, partly dispatched or fully invoiced, from what has been invoiced so far."""
    order = SaleOrder.objects.get(pk=order.pk)
    if order.status not in (S.CONFIRMED, S.PARTLY, S.DISPATCHED):
        return order
    lines = list(order.lines.all())
    if all(l.qty_invoiced >= l.qty for l in lines):
        new = S.DISPATCHED
    elif any(l.qty_invoiced > 0 for l in lines):
        new = S.PARTLY
    else:
        new = S.CONFIRMED
    if new != order.status:
        order.status = new
        order.save(update_fields=["status"])
    return order


def production_stages(order):
    """Where the pieces of a made-to-order order are now, by stage: [(stage, pieces)]. Says nothing about the customer."""
    if order.production_order_id is None:
        return []
    from production.models import Bundle

    counts = {}
    for b in Bundle.objects.filter(lot__order_line__order_id=order.production_order_id).select_related("current_step__process"):
        if b.status in ("packed", "dispatched"):
            label = "Packed, in finished stock" if b.status == "packed" else "Dispatched"
        elif b.current_step_id:
            label = b.current_step.process.name
        else:
            label = "Cut"
        counts[label] = counts.get(label, 0) + b.qty
    return sorted(counts.items())


def order_book(user, factory=None):
    """Open orders with the balance still pending, for the dispatch desk (E4.6, BRD A7)."""
    qs = SaleOrder.objects.for_user(user).filter(status__in=(S.CONFIRMED, S.PARTLY)).select_related("customer", "factory")
    if factory is not None:
        qs = qs.filter(factory=factory)
    return [{"order": o, "ordered": o.total_qty, "invoiced": sum((l.qty_invoiced for l in o.lines.all()), Decimal("0")),
             "balance": o.balance_qty} for o in qs]
