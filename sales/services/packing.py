"""Packing lists and cartons (E4.6): what is packed, in which carton, in which size. The invoice that follows covers
only the packed quantity, and the order keeps showing the balance still pending."""
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from inventory.models import StockBalance
from sales.models import Carton, CartonLine, PackingList, SaleOrder, SaleOrderLine
from sales.services.common import check_pieces

P = PackingList.Status
LIVE = (P.DRAFT, P.PACKED, P.INVOICED)
QZERO = Decimal("0.000")


@dataclass
class CartonSpec:
    items: dict = field(default_factory=dict)  # {SKU: pieces}


def carton_code(packing, carton_no) -> str:
    return f"C{packing.pk:06d}-{carton_no:02d}"


def packed_qty(order_line, exclude=None) -> Decimal:
    """Pieces of this order line on live packing lists (draft, packed or invoiced)."""
    qs = CartonLine.objects.filter(carton__packing__order=order_line.order, carton__packing__status__in=LIVE, sku=order_line.sku)
    if exclude is not None:
        qs = qs.exclude(carton__packing=exclude)
    return Decimal(qs.aggregate(q=Sum("qty"))["q"] or 0).quantize(Decimal("0.001"))


def refresh_packed(order):
    for line in SaleOrderLine.objects.filter(order=order):
        line.qty_packed = packed_qty(line)
        line.save(update_fields=["qty_packed"])


def available_at(location, sku, exclude=None) -> Decimal:
    """Stock at the location not already promised to another packed (not yet invoiced) list."""
    bal = StockBalance.objects.filter(location=location, sku=sku).first()
    have = bal.qty if bal else QZERO
    held = CartonLine.objects.filter(carton__packing__location=location, carton__packing__status=P.PACKED, sku=sku)
    if exclude is not None:
        held = held.exclude(carton__packing=exclude)
    return have - Decimal(held.aggregate(q=Sum("qty"))["q"] or 0)


def _write(packing, cartons, order):
    if not cartons:
        raise BusinessRuleError("Add at least one carton.")
    totals = {}
    for n, spec in enumerate(cartons, start=1):
        items = {sku: check_pieces(q, f"Carton {n} quantity of {sku}") for sku, q in spec.items.items() if q not in (None, 0)}
        if not items:
            raise BusinessRuleError(f"Carton {n} is empty.")
        carton = Carton.objects.create(packing=packing, carton_no=n, code=carton_code(packing, n))
        for sku, qty in items.items():
            CartonLine.objects.create(carton=carton, sku=sku, qty=qty)
            totals[sku.pk] = totals.get(sku.pk, QZERO) + qty
    lines = {l.sku_id: l for l in order.lines.select_related("sku")}
    for sku_id, qty in totals.items():
        line = lines.get(sku_id)
        if line is None:
            raise BusinessRuleError(f"{CartonLine.objects.filter(carton__packing=packing, sku_id=sku_id).first().sku} is not on order {order}.")
        other = packed_qty(line, exclude=packing)
        if qty > line.qty - other:
            raise BusinessRuleError(
                f"{line.sku}: {qty.normalize():f} packed but only {max(line.qty - other, QZERO).normalize():f} of the order is left to pack.")


@transaction.atomic
def save_packing(*, order, location, date, cartons, user, packing=None, transporter=None, lr_no="", lr_date=None,
                 vehicle_no="", remarks="") -> PackingList:
    """Create a draft packing list, or replace the cartons of an existing draft."""
    order = SaleOrder.objects.select_related("factory", "company").get(pk=order.pk)
    assert_factory_access(user, order.factory)
    if order.status not in (SaleOrder.Status.CONFIRMED, SaleOrder.Status.PARTLY):
        raise BusinessRuleError("Pack against a confirmed order that is still open.")
    if location.factory_id != order.factory_id:
        raise BusinessRuleError(f"Location {location} is not in factory {order.factory.code}.")
    fields = dict(location=location, date=date, transporter=transporter, lr_no=lr_no.strip(), lr_date=lr_date,
                  vehicle_no=vehicle_no.strip().upper(), remarks=remarks)
    if packing is None:
        packing = PackingList.objects.create(company=order.company, factory=order.factory, order=order, created_by=user, **fields)
    else:
        packing = PackingList.objects.get(pk=packing.pk)
        if packing.status != P.DRAFT:
            raise BusinessRuleError("Only a draft packing list can be edited.")
        for k, v in fields.items():
            setattr(packing, k, v)
        packing.save()
        packing.cartons.all().delete()
    _write(packing, list(cartons), order)
    refresh_packed(order)
    return packing


@transaction.atomic
def finalize_packing(packing, *, user) -> PackingList:
    """Close the cartons: numbers the list and checks the pieces are in stock."""
    packing = PackingList.objects.select_related("factory", "order", "location").get(pk=packing.pk)
    assert_factory_access(user, packing.factory)
    if packing.status != P.DRAFT:
        raise BusinessRuleError("This packing list is already finalised or cancelled.")
    totals = {}
    for cl in CartonLine.objects.filter(carton__packing=packing).select_related("sku__style", "sku__colour", "sku__size"):
        totals[cl.sku] = totals.get(cl.sku, QZERO) + cl.qty
    for sku, qty in totals.items():
        have = available_at(packing.location, sku, exclude=packing)
        if qty > have:
            raise BusinessRuleError(f"{sku}: only {max(have, QZERO).normalize():f} available at {packing.location}; {qty.normalize():f} packed.")
    packing.number = next_document_number(factory=packing.factory, doc_type="packing_list", on_date=packing.date)
    packing.status = P.PACKED
    packing.save()
    return packing


@transaction.atomic
def cancel_packing(packing, *, user, reason="") -> PackingList:
    packing = PackingList.objects.select_related("factory", "order").get(pk=packing.pk)
    assert_factory_access(user, packing.factory)
    if packing.status == P.INVOICED:
        raise BusinessRuleError("This list has been invoiced; cancel the invoice first.")
    if packing.status == P.CANCELLED:
        raise BusinessRuleError("This packing list is already cancelled.")
    if packing.status == P.PACKED and not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the packing list.")
    packing.status = P.CANCELLED
    packing.remarks = (f"Cancelled: {reason.strip()}" if reason.strip() else packing.remarks)[:255]
    packing.save()
    refresh_packed(packing.order)
    return packing


def sku_totals(packing) -> dict:
    """{SKU: pieces} over all cartons."""
    out = {}
    for cl in CartonLine.objects.filter(carton__packing=packing).select_related("sku__style", "sku__colour", "sku__size"):
        out[cl.sku] = out.get(cl.sku, QZERO) + cl.qty
    return out
