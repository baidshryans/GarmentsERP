"""Sale invoices (E4.2 - E4.6).

GST is optional on every invoice. When the company is GST registered the invoice suggests the tax from the HSN slab
(by value per piece) and the place of supply (CGST + SGST within the state, IGST across states). The user can pick one
template for the whole invoice or waive GST on this invoice; either change needs a note and is kept with what the
system had suggested. When GST is not switched on, nothing is charged and nothing posts to a GST ledger.

Voucher (one transaction with the stock issue and the invoice itself, all in the invoice's factory):
    Dr Customer                 - invoice total, bill-wise: new reference = invoice number, due after the credit days
    Cr Sales - Ready Stock / Made to Order   - value after discount
    Cr CGST / SGST / IGST Output             - only if GST is charged
    Dr / Cr Round Off           - if the total is rounded
    Dr Cost of Goods Sold       - stock value that left
    Cr Finished Goods Stock
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from inventory.models import StockMovement
from inventory.services import stock
from ledger.models import Ledger
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher, reverse_voucher
from sales.models import (
    PackingList, SaleInvoice, SaleInvoiceLine, SaleInvoiceLineTax, SaleInvoiceTax, SaleOrder, SaleOrderLine, SaleSetting,
)
from sales.services import orders as order_service, packing as packing_service, pricing
from sales.services.common import ZERO, check_decimal, check_discount, check_pieces, line_amount, r2, settings_for
from tax import calc
from tax import services as tax_services
from tax.models import TaxTemplate

Mode = SaleInvoice.TaxMode
T = StockMovement.Type


@dataclass
class InvoiceLineSpec:
    sku: object
    qty: Decimal
    rate: Decimal | None = None
    discount_pct: Decimal | None = None
    order_line: object | None = None


# ---------------------------------------------------------------- tax

class NoGstRate(BusinessRuleError):
    """GST cannot be suggested because a style has no HSN code (`hsn` is None) or its HSN has no slab for the value
    and date (`hsn` is that HSN). The same refusal as before, told apart so a screen can name the style."""

    def __init__(self, message, hsn=None):
        super().__init__(message)
        self.hsn = hsn


def gst_on(company, factory, on_date) -> bool:
    return tax_services.gst_enabled(company, on_date, factory)


def place_of_supply(customer, factory, override=None) -> str:
    return override or customer.state_code or factory.state_code


def _slab_template(hsn, unit_value, on_date, factory_state, place_state):
    """(rate, template) the HSN slab suggests for one piece value and where the goods go; errors say what is missing."""
    if hsn is None:
        raise NoGstRate("The style has no HSN code; set it, or choose a GST template or no GST for this bill.")
    rate = tax_services.gst_rate_for(hsn, unit_value, on_date)
    if rate is None:
        raise NoGstRate(f"No GST slab for HSN {hsn.code} on {on_date:%d %b %Y}; add the slab, or choose a template.", hsn)
    template = calc.suggest_gst_template(party_state=factory_state, place_state=place_state, rate=rate)
    if template is None:
        raise BusinessRuleError(f"There is no GST template for {rate.normalize():f}%; create one or choose another.")
    return rate, template


def _tax_plan(*, company, factory, customer, date, prepared, tax_mode, gst_template, tax_note, place_state):
    """Tax per prepared line: ([(template or None, rate)], mode, template, note, suggested text)."""
    charged = gst_on(company, factory, date)
    if not charged:
        if tax_mode not in (None, Mode.NONE):
            raise BusinessRuleError("GST is not switched on for this company from this date; the bill is issued without tax.")
        return [(None, ZERO)] * len(prepared), Mode.NONE, None, "", ""
    mode = tax_mode or Mode.AUTO
    suggested, names = [], []
    try:
        for p in prepared:
            unit = (p["amount"] / p["qty"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            rate, template = _slab_template(p["sku"].style.hsn, unit, date, factory.state_code, place_state)
            suggested.append((template, rate))
            names.append(template.name)
        text = ", ".join(sorted(set(names)))
    except BusinessRuleError:
        if mode == Mode.AUTO:
            raise
        suggested, text = None, ""
    note = (tax_note or "").strip()
    if mode == Mode.AUTO:
        return suggested, mode, None, "", text
    if mode == Mode.NONE:
        if not note:
            raise BusinessRuleError("Give a reason for issuing this bill without GST.")
        return [(None, ZERO)] * len(prepared), mode, None, note, text
    if mode == Mode.TEMPLATE:
        if gst_template is None or gst_template.kind != "gst" or gst_template.is_reverse_charge:
            raise BusinessRuleError("Choose a GST template (not reverse charge) for the bill.")
        if suggested is None or {t.pk for t, _ in suggested} != {gst_template.pk}:
            if not note:
                raise BusinessRuleError("Give a reason for changing the GST from what was suggested.")
        return [(gst_template, gst_template.total_rate)] * len(prepared), mode, gst_template, note, text
    raise BusinessRuleError(f"Unknown tax choice {mode!r}.")


def _write_taxes(invoice, line, template, base):
    total = ZERO
    if template is None:
        return total
    for t in calc.compute(template, base):
        SaleInvoiceLineTax.objects.create(line=line, component=t.component, rate=t.rate, amount=t.amount)
        total += t.amount
    return total


def _summarise_taxes(invoice):
    invoice.tax_lines.all().delete()
    groups = {}
    for lt in SaleInvoiceLineTax.objects.filter(line__invoice=invoice).select_related("line"):
        g = groups.setdefault((lt.component, lt.rate), [ZERO, ZERO])
        g[0] += lt.line.amount
        g[1] += lt.amount
    for (component, rate), (taxable, amount) in groups.items():
        SaleInvoiceTax.objects.create(invoice=invoice, component=component, rate=rate, taxable=taxable, amount=amount)


def _rounded(total, setting):
    if setting.rounding == SaleSetting.Rounding.RUPEE:
        return total.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))
    return total


# ---------------------------------------------------------------- draft

def _check_against_order(order, packing, prepared):
    if order is None:
        return
    lines = {l.sku_id: l for l in order.lines.all()}
    allowed = {s.pk: q for s, q in packing_service.sku_totals(packing).items()} if packing is not None else None
    for p in prepared:
        ol = lines.get(p["sku"].pk)
        if ol is None:
            raise BusinessRuleError(f"{p['sku']} is not on order {order}.")
        p["order_line"] = ol
        if p["qty"] > ol.qty - ol.qty_invoiced:
            raise BusinessRuleError(f"{p['sku']}: only {(ol.qty - ol.qty_invoiced).normalize():f} of the order is left to bill.")
        if allowed is not None and p["qty"] > allowed.get(p["sku"].pk, 0):
            raise BusinessRuleError(
                f"{p['sku']}: the bill covers only packed pieces; {allowed.get(p['sku'].pk, 0)} packed on {packing}.")


@transaction.atomic
def save_invoice(*, company, factory, customer, date, lines, user, location, invoice=None, order=None, packing=None,
                 tax_mode=None, gst_template=None, tax_note="", place_of_supply_state=None, due_date=None,
                 transporter=None, lr_no="", vehicle_no="", notes="") -> SaleInvoice:
    """Create a draft invoice, or replace the contents of an existing draft."""
    assert_factory_access(user, factory)
    if not customer.is_customer:
        raise BusinessRuleError(f"{customer.name} is not marked as a customer.")
    if location.factory_id != factory.pk:
        raise BusinessRuleError(f"Location {location} is not in factory {factory.code}.")
    if invoice is not None:
        invoice = SaleInvoice.objects.get(pk=invoice.pk)
        if invoice.status != SaleInvoice.Status.DRAFT:
            raise BusinessRuleError("Only a draft bill can be edited.")
    if order is not None and (order.customer_id != customer.pk or order.factory_id != factory.pk):
        raise BusinessRuleError("The order belongs to another customer or factory.")
    if packing is not None:
        if packing.order_id != (order.pk if order else None) or packing.status != PackingList.Status.PACKED:
            raise BusinessRuleError("Bill against a packing list that is finished and not yet billed.")
        other = SaleInvoice.objects.filter(packing=packing).exclude(status="cancelled")
        if invoice is not None:
            other = other.exclude(pk=invoice.pk)
        if other.exists():
            raise BusinessRuleError(f"{packing} already has a bill.")
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("Add at least one item to bill.")

    prepared, seen = [], set()
    for spec in lines:
        sku = spec.sku
        if sku.pk in seen:
            raise BusinessRuleError(f"{sku} appears twice; combine the quantities.")
        seen.add(sku.pk)
        qty = check_pieces(spec.qty, f"Quantity of {sku}")
        rate = spec.rate
        if rate is None:
            price = pricing.resolve(customer, sku, qty, date)
            if price is None:
                raise BusinessRuleError(f"No rate found for {sku.style.style_no}; enter one.")
            rate = price.rate
        rate = check_decimal(rate, f"Rate of {sku}")
        if rate < 0:
            raise BusinessRuleError(f"The rate of {sku} cannot be negative.")
        disc = customer.discount_pct if spec.discount_pct is None else spec.discount_pct
        disc = check_discount(user, company, disc)
        prepared.append({"sku": sku, "qty": qty, "rate": rate.quantize(Decimal("0.01")), "disc": disc,
                         "amount": line_amount(qty, rate, disc), "order_line": None})
    _check_against_order(order, packing, prepared)

    place_state = place_of_supply(customer, factory, place_of_supply_state)
    plan, mode, template, note, suggested_text = _tax_plan(
        company=company, factory=factory, customer=customer, date=date, prepared=prepared, tax_mode=tax_mode,
        gst_template=gst_template, tax_note=tax_note, place_state=place_state)

    setting = settings_for(company)
    subtotal = sum((p["amount"] for p in prepared), ZERO)
    discount_total = sum((r2(p["qty"] * p["rate"]) - p["amount"] for p in prepared), ZERO)
    fields = dict(
        company=company, factory=factory, customer=customer, order=order, packing=packing, location=location, date=date,
        due_date=due_date or date + timedelta(days=customer.credit_days), place_of_supply=place_state, tax_mode=mode,
        gst_template=template, tax_note=note, suggested_tax=suggested_text, transporter=transporter,
        lr_no=lr_no.strip(), vehicle_no=vehicle_no.strip().upper(), notes=notes, subtotal=subtotal,
        discount_total=discount_total,
    )
    if invoice is None:
        invoice = SaleInvoice.objects.create(created_by=user, **fields)
    else:
        for k, v in fields.items():
            setattr(invoice, k, v)
        invoice.save()
        invoice.lines.all().delete()
    gst_total = ZERO
    for p, (line_template, rate) in zip(prepared, plan):
        sku = p["sku"]
        line = SaleInvoiceLine.objects.create(
            invoice=invoice, sku=sku, order_line=p["order_line"], qty=p["qty"], rate=p["rate"], discount_pct=p["disc"],
            amount=p["amount"], hsn=sku.style.hsn.code if sku.style.hsn_id else "", gst_template=line_template, gst_rate=rate)
        tax = _write_taxes(invoice, line, line_template, p["amount"])
        line.tax_amount = tax
        line.save(update_fields=["tax_amount"])
        gst_total += tax
    _summarise_taxes(invoice)
    total = _rounded(subtotal + gst_total, setting)
    invoice.gst_total, invoice.total, invoice.round_off = gst_total, total, total - (subtotal + gst_total)
    invoice.save()
    return invoice


@transaction.atomic
def invoice_from_packing(packing, *, user, date=None, **kwargs) -> SaleInvoice:
    """A draft invoice for exactly the packed pieces of a packing list, at the order's rates."""
    packing = PackingList.objects.select_related("order__customer", "order__company", "factory", "location").get(pk=packing.pk)
    order = packing.order
    order_lines = {l.sku_id: l for l in order.lines.all()}
    specs = [InvoiceLineSpec(sku=sku, qty=qty, rate=order_lines[sku.pk].rate, discount_pct=order_lines[sku.pk].discount_pct)
             for sku, qty in packing_service.sku_totals(packing).items()]
    return save_invoice(
        company=order.company, factory=packing.factory, customer=order.customer, date=date or timezone.localdate(),
        lines=specs, user=user, location=packing.location, order=order, packing=packing, transporter=packing.transporter,
        lr_no=packing.lr_no, vehicle_no=packing.vehicle_no, **kwargs)


@transaction.atomic
def finish_packing_and_bill(packing, *, user, date=None) -> SaleInvoice:
    """Finish a draft packing list and draft the bill for its pieces in one go (the packing list's "Finish packing
    and make bill"). One transaction: if the bill cannot be drafted, the list stays a draft and no number is used.
    The bill is a draft; GST is chosen or waived on it and posting stays a separate step."""
    return invoice_from_packing(packing_service.finalize_packing(packing, user=user), user=user, date=date)


# ---------------------------------------------------------------- posting

@transaction.atomic
def post_invoice(invoice, *, user) -> SaleInvoice:
    inv = SaleInvoice.objects.select_related("factory", "customer", "company", "location", "order", "packing").get(pk=invoice.pk)
    assert_factory_access(user, inv.factory)
    if inv.status != SaleInvoice.Status.DRAFT:
        raise BusinessRuleError("This bill has already been posted or cancelled.")
    customer_ledger = inv.customer.customer_ledger
    if customer_ledger is None:
        raise BusinessRuleError(f"{inv.customer.name} has no customer ledger.")
    lines = list(inv.lines.select_related("sku__style", "sku__colour", "sku__size", "order_line"))
    if inv.order_id is not None:
        if inv.order.status not in (SaleOrder.Status.CONFIRMED, SaleOrder.Status.PARTLY):
            raise BusinessRuleError(f"Order {inv.order} is not open for billing.")
        for l in lines:
            ol = SaleOrderLine.objects.get(pk=l.order_line_id)
            if l.qty > ol.qty - ol.qty_invoiced:
                raise BusinessRuleError(f"{l.sku}: only {(ol.qty - ol.qty_invoiced).normalize():f} of the order is left to bill.")
    if inv.packing_id is not None and inv.packing.status != PackingList.Status.PACKED:
        raise BusinessRuleError(f"{inv.packing} is no longer a finished packing list.")

    inv.number = next_document_number(factory=inv.factory, doc_type="sale_invoice", on_date=inv.date)
    movements = []
    for l in lines:
        m = stock.post_movement(
            factory=inv.factory, location=inv.location, item=l.sku, qty=-l.qty, movement_type=T.ISSUE, date=inv.date,
            user=user, source=inv, notes=f"Sold on {inv.number}")
        movements.append(m)
        l.cost_value = -m.value
        l.save(update_fields=["cost_value"])
    cogs = sum((l.cost_value for l in lines), ZERO)

    def ledger(key):
        return Ledger.objects.get(company=inv.company, system_key=key)

    sales_key = "sales_mto" if inv.order_id and inv.order.order_type == SaleOrder.Type.MTO else "sales_stock"
    specs = [LineSpec(ledger=customer_ledger, debit=inv.total, narration=f"Invoice {inv.number}",
                      allocations=(AllocationSpec("new", inv.total, inv.number, inv.due_date),))]
    if inv.subtotal > 0:
        specs.append(LineSpec(ledger=ledger(sales_key), credit=inv.subtotal))
    by_component = {}
    for t in inv.tax_lines.all():
        by_component[t.component] = by_component.get(t.component, ZERO) + t.amount
    for component, amount in by_component.items():
        if amount > 0:
            specs.append(LineSpec(ledger=ledger(f"{component}_output"), credit=amount))
    if inv.round_off > 0:
        specs.append(LineSpec(ledger=ledger("round_off"), credit=inv.round_off))
    elif inv.round_off < 0:
        specs.append(LineSpec(ledger=ledger("round_off"), debit=-inv.round_off))
    if cogs > 0:
        specs.append(LineSpec(ledger=ledger("cogs"), debit=cogs, narration="Cost of goods sold"))
        for (_, key), value in stock.gl_values(movements).items():
            if value < 0:
                specs.append(LineSpec(ledger=ledger(key), credit=-value))
    voucher = post_voucher(
        company=inv.company, factory=inv.factory, voucher_type="sales", date=inv.date, lines=specs, user=user,
        narration=f"Sale to {inv.customer.name}, invoice {inv.number}", source=inv)
    inv.cogs_total, inv.voucher, inv.status = cogs, voucher, SaleInvoice.Status.POSTED
    inv.save()
    for l in lines:
        if l.order_line_id:
            ol = SaleOrderLine.objects.get(pk=l.order_line_id)
            ol.qty_invoiced += l.qty
            ol.save(update_fields=["qty_invoiced"])
    if inv.packing_id is not None:
        PackingList.objects.filter(pk=inv.packing_id).update(status=PackingList.Status.INVOICED)
    if inv.order_id is not None:
        order_service.refresh_status(inv.order)
    return inv


@transaction.atomic
def discard_draft(invoice, *, user):
    inv = SaleInvoice.objects.select_related("factory").get(pk=invoice.pk)
    assert_factory_access(user, inv.factory)
    if inv.status != SaleInvoice.Status.DRAFT:
        raise BusinessRuleError("Only a draft bill can be discarded.")
    inv.delete()


@transaction.atomic
def cancel_invoice(invoice, *, user, reason) -> SaleInvoice:
    inv = SaleInvoice.objects.select_related("factory", "order", "packing").get(pk=invoice.pk)
    assert_factory_access(user, inv.factory)
    if inv.status != SaleInvoice.Status.POSTED:
        raise BusinessRuleError("Only a posted bill can be cancelled.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the bill.")
    if inv.credit_notes.filter(status="posted").exists():
        raise BusinessRuleError("A return from customer has been posted against this bill; cancel it first.")
    if inv.einvoice_status == SaleInvoice.EInvoice.GENERATED:
        raise BusinessRuleError("An IRN has been generated for this bill; cancel the e-invoice first.")
    when = max(timezone.localdate(), inv.date)
    for m in StockMovement.objects.filter(source_type=inv._meta.label_lower, source_id=inv.pk, movement_type=T.ISSUE
                                          ).select_related("sku", "location", "factory"):
        stock.reverse_movement(m, user=user, date=when, source=inv, notes=f"Invoice {inv.number} cancelled")
    reverse_voucher(inv.voucher, user=user, reason=f"Invoice cancelled: {reason.strip()}", date=when)
    for l in inv.lines.select_related("order_line"):
        if l.order_line_id:
            ol = SaleOrderLine.objects.get(pk=l.order_line_id)
            ol.qty_invoiced -= l.qty
            ol.save(update_fields=["qty_invoiced"])
    if inv.packing_id is not None:
        PackingList.objects.filter(pk=inv.packing_id).update(status=PackingList.Status.PACKED)
    inv.status = SaleInvoice.Status.CANCELLED
    inv.notes = f"Cancelled: {reason.strip()}"[:255]
    inv.save()
    if inv.order_id is not None:
        order_service.refresh_status(inv.order)
    return inv
