"""Sales credit notes (returns against a posted invoice). GST is reversed exactly as it was charged, line by line, and
the returned pieces come back into stock at the cost they left at.

Voucher (all in the invoice's factory):
    Dr Sales Returns            - value of the returned pieces
    Dr CGST / SGST / IGST Output - the GST that was charged on them
    Dr / Cr Round Off           - if the total is rounded
    Cr Customer                 - settles the invoice's bill first; anything above what is open stays on account
    Dr Finished Goods Stock     - cost of the returned pieces
    Cr Cost of Goods Sold
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from inventory.models import StockMovement
from inventory.services import stock
from ledger.models import Ledger
from ledger.selectors import outstanding_bills
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher, reverse_voucher
from sales.models import (
    SaleCreditNote, SaleCreditNoteLine, SaleCreditNoteLineTax, SaleInvoice, SaleInvoiceLine, SaleInvoiceLineTax, SaleSetting,
)
from sales.services.common import ZERO, check_pieces, r2, settings_for

S = SaleCreditNote.Status


def _share(total, qty, line_qty, already, remaining_qty):
    """The part of `total` that `qty` of `line_qty` carries; the last pieces take whatever is left (so nothing is lost)."""
    if qty == remaining_qty:
        return total - already
    return r2(total * qty / line_qty)


def _write_lines(note, specs):
    inv = note.invoice
    seen = set()
    for line, qty in specs:
        line = SaleInvoiceLine.objects.get(pk=line.pk)
        if line.invoice_id != inv.pk:
            raise BusinessRuleError("A returned line must come from the bill it is returned against.")
        if line.pk in seen:
            raise BusinessRuleError(f"{line.sku} appears twice.")
        seen.add(line.pk)
        qty = check_pieces(qty, f"Returned quantity of {line.sku}")
        if qty > line.returnable:
            raise BusinessRuleError(f"{line.sku}: only {line.returnable.normalize():f} can still be returned on {inv.number}.")
        posted = SaleCreditNoteLine.objects.filter(invoice_line=line, note__status=S.POSTED)
        amount = _share(line.amount, qty, line.qty, Decimal(posted.aggregate(v=Sum("amount"))["v"] or 0), line.returnable)
        cost = _share(line.cost_value, qty, line.qty, Decimal(posted.aggregate(v=Sum("cost_value"))["v"] or 0), line.returnable)
        cl = SaleCreditNoteLine.objects.create(note=note, invoice_line=line, qty=qty, amount=amount, cost_value=cost)
        for src in line.taxes.all():
            tax = _share(src.amount, qty, line.qty, src.returned, line.returnable)
            SaleCreditNoteLineTax.objects.create(line=cl, source=src, component=src.component, rate=src.rate, amount=tax)


def _totals(note, setting):
    subtotal = sum((l.amount for l in note.lines.all()), ZERO)
    gst = sum((t.amount for l in note.lines.all() for t in l.taxes.all()), ZERO)
    total = subtotal + gst
    if setting.rounding == SaleSetting.Rounding.RUPEE:
        total = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP).quantize(Decimal("0.01"))
    note.subtotal, note.gst_total, note.total, note.round_off = subtotal, gst, total, total - (subtotal + gst)
    note.save()


@transaction.atomic
def save_credit_note(*, invoice, location, date, lines, reason, user, note=None) -> SaleCreditNote:
    """Create a draft credit note, or replace the lines of an existing draft. lines: [(SaleInvoiceLine, qty)]."""
    invoice = SaleInvoice.objects.select_related("factory", "customer", "company").get(pk=invoice.pk)
    assert_factory_access(user, invoice.factory)
    if invoice.status != SaleInvoice.Status.POSTED:
        raise BusinessRuleError("A return from customer can be made only against a posted bill.")
    if location.factory_id != invoice.factory_id:
        raise BusinessRuleError(f"Location {location} is not in factory {invoice.factory.code}.")
    if date < invoice.date:
        raise BusinessRuleError("The return cannot be dated before the bill.")
    if not reason.strip():
        raise BusinessRuleError("Give the reason for the return.")
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("Enter the pieces returned on at least one line of the bill.")
    if note is None:
        note = SaleCreditNote.objects.create(company=invoice.company, factory=invoice.factory, customer=invoice.customer,
                                             invoice=invoice, location=location, date=date, reason=reason.strip(), created_by=user)
    else:
        note = SaleCreditNote.objects.get(pk=note.pk)
        if note.status != S.DRAFT:
            raise BusinessRuleError("Only a draft return from customer can be edited.")
        note.location, note.date, note.reason = location, date, reason.strip()
        note.save()
        note.lines.all().delete()
    _write_lines(note, lines)
    _totals(note, settings_for(invoice.company))
    return note


@transaction.atomic
def post_credit_note(note, *, user) -> SaleCreditNote:
    note = SaleCreditNote.objects.select_related("factory", "customer", "company", "invoice", "location").get(pk=note.pk)
    assert_factory_access(user, note.factory)
    if note.status != S.DRAFT:
        raise BusinessRuleError("This return from customer has already been posted or cancelled.")
    inv = note.invoice
    if inv.status != SaleInvoice.Status.POSTED:
        raise BusinessRuleError(f"Bill {inv.number} is no longer posted.")
    customer_ledger = note.customer.customer_ledger
    if customer_ledger is None:
        raise BusinessRuleError(f"{note.customer.name} has no customer ledger.")
    # re-work the lines now: another credit note may have been posted since this draft was saved
    pairs = [(l.invoice_line, l.qty) for l in note.lines.select_related("invoice_line")]
    note.lines.all().delete()
    _write_lines(note, pairs)
    _totals(note, settings_for(note.company))
    note.refresh_from_db()
    lines = list(note.lines.select_related("invoice_line__sku").prefetch_related("taxes"))

    movements = []
    for l in lines:
        movements.append(stock.post_movement(
            factory=note.factory, location=note.location, item=l.invoice_line.sku, qty=l.qty, value=l.cost_value,
            movement_type=StockMovement.Type.RECEIPT, date=note.date, user=user, source=note,
            notes=f"Returned against {inv.number}"))
    cost = sum((l.cost_value for l in lines), ZERO)

    def ledger(key):
        return Ledger.objects.get(company=note.company, system_key=key)

    open_amount = max(outstanding_bills(customer_ledger)["bills"].get(inv.number, ZERO), ZERO)
    against = min(note.total, open_amount)
    allocations = []
    if against > 0:
        allocations.append(AllocationSpec("against", against, inv.number))
    if note.total - against > 0:
        allocations.append(AllocationSpec("on_account", note.total - against))
    specs = [LineSpec(ledger=customer_ledger, credit=note.total, narration=f"Credit note against {inv.number}",
                      allocations=tuple(allocations))]
    if note.subtotal > 0:
        specs.append(LineSpec(ledger=ledger("sales_returns"), debit=note.subtotal))
    by_component = {}
    for l in lines:
        for t in l.taxes.all():
            by_component[t.component] = by_component.get(t.component, ZERO) + t.amount
    for component, amount in by_component.items():
        if amount > 0:
            specs.append(LineSpec(ledger=ledger(f"{component}_output"), debit=amount))
    if note.round_off > 0:
        specs.append(LineSpec(ledger=ledger("round_off"), debit=note.round_off))
    elif note.round_off < 0:
        specs.append(LineSpec(ledger=ledger("round_off"), credit=-note.round_off))
    if cost > 0:
        specs.append(LineSpec(ledger=ledger("cogs"), credit=cost, narration="Cost of returned goods"))
        for (_, key), value in stock.gl_values(movements).items():
            if value > 0:
                specs.append(LineSpec(ledger=ledger(key), debit=value))
    note.number = next_document_number(factory=note.factory, doc_type="sale_credit_note", on_date=note.date)
    voucher = post_voucher(
        company=note.company, factory=note.factory, voucher_type="credit_note", date=note.date, lines=specs, user=user,
        narration=f"Credit note to {note.customer.name} against {inv.number}: {note.reason}"[:500], source=note)
    for l in lines:
        il = SaleInvoiceLine.objects.get(pk=l.invoice_line_id)
        il.qty_returned += l.qty
        il.save(update_fields=["qty_returned"])
        for t in l.taxes.all():
            SaleInvoiceLineTax.objects.filter(pk=t.source_id).update(returned=t.source.returned + t.amount)
    note.status, note.voucher = S.POSTED, voucher
    note.save()
    return note


@transaction.atomic
def cancel_credit_note(note, *, user, reason="") -> SaleCreditNote:
    note = SaleCreditNote.objects.select_related("factory").get(pk=note.pk)
    assert_factory_access(user, note.factory)
    if note.status == S.DRAFT:
        note.status = S.CANCELLED
        note.save()
        return note
    if note.status != S.POSTED:
        raise BusinessRuleError("This return from customer is already cancelled.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the return from customer.")
    when = max(timezone.localdate(), note.date)
    for m in StockMovement.objects.filter(source_type=note._meta.label_lower, source_id=note.pk,
                                          movement_type=StockMovement.Type.RECEIPT).select_related("sku", "location", "factory"):
        stock.reverse_movement(m, user=user, date=when, source=note, notes=f"Credit note {note.number} cancelled")
    reverse_voucher(note.voucher, user=user, reason=f"Credit note cancelled: {reason.strip()}", date=when)
    for l in note.lines.select_related("invoice_line").prefetch_related("taxes"):
        il = SaleInvoiceLine.objects.get(pk=l.invoice_line_id)
        il.qty_returned -= l.qty
        il.save(update_fields=["qty_returned"])
        for t in l.taxes.select_related("source"):
            SaleInvoiceLineTax.objects.filter(pk=t.source_id).update(returned=t.source.returned - t.amount)
    note.status = S.CANCELLED
    note.reason = f"{note.reason} (cancelled: {reason.strip()})"[:255]
    note.save()
    return note
