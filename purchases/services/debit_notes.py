"""Debit notes (PUR-09, E5.3).

Rejection note - raised as a draft when a GRN rejects pieces. It posts only once the vendor has billed
those pieces: Dr Vendor, Cr Rejected Goods Recoverable (the amount the invoice parked there). The vendor's
debit is set against the bill(s) that billed those pieces, bill-wise, so the bill shows what is really left
to pay (E5.6); whatever a bill no longer has open stays on account.
Return note   - goods already in stock go back to the vendor: stock leaves at cost, Dr Vendor,
Cr Stock, Cr Input GST when claimable, and any difference to Purchase Returns.
"""
from dataclasses import dataclass
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
from datetime import timedelta

from ledger.selectors import outstanding_bills
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher, reverse_voucher
from purchases.models import DebitNote, DebitNoteLine, PurchaseInvoiceLine
from tax import calc

TWO = Decimal("0.01")
ZERO = Decimal("0.00")
T = StockMovement.Type


def _r2(v):
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


@dataclass
class ReturnLineSpec:
    item: object
    qty: Decimal
    rate: Decimal
    location: object
    roll: object | None = None
    grn_line: object | None = None


def _check_return_header(vendor, gst_template):
    if not vendor.is_vendor:
        raise BusinessRuleError(f"{vendor.name} is not marked as a vendor.")
    if gst_template is not None and (gst_template.kind != "gst" or gst_template.is_reverse_charge):
        raise BusinessRuleError("Choose a normal GST template (not reverse charge) for a return.")


def _write_return_lines(note, factory, lines, gst_template):
    """Write the lines of a draft return note and set its totals."""
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("A return note needs at least one line.")
    subtotal = ZERO
    for s in lines:
        if isinstance(s.qty, float) or isinstance(s.rate, float):
            raise BusinessRuleError("Quantity and rate must be Decimal.")
        if s.qty <= 0:
            raise BusinessRuleError(f"Quantity of {s.item} must be more than zero (BR-01).")
        if s.location.factory_id != factory.pk:
            raise BusinessRuleError(f"{s.location} is not in factory {factory.code}.")
        amount = _r2(s.qty * s.rate)
        subtotal += amount
        DebitNoteLine.objects.create(note=note, grn_line=s.grn_line, location=s.location, roll=s.roll, qty=s.qty,
                                     rate=s.rate, amount=amount, **stock.item_kwargs(s.item))
    tax = sum((t.amount for t in calc.compute(gst_template, subtotal)), ZERO) if gst_template else ZERO
    note.subtotal, note.tax_total, note.total = subtotal, tax, subtotal + tax
    note.save()


@transaction.atomic
def create_return_note(*, company, factory, vendor, date, lines, user, reason, gst_template=None,
                       itc_claimable=True, grn=None) -> DebitNote:
    assert_factory_access(user, factory)
    _check_return_header(vendor, gst_template)
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("A return note needs at least one line.")
    note = DebitNote.objects.create(
        company=company, factory=factory, kind=DebitNote.Kind.RETURN, vendor=vendor, grn=grn, date=date,
        reason=reason, gst_template=gst_template, itc_claimable=itc_claimable, created_by=user,
    )
    _write_return_lines(note, factory, lines, gst_template)
    return note


@transaction.atomic
def update_return_note(note, *, vendor, date, lines, user, reason, gst_template=None, itc_claimable=True) -> DebitNote:
    """Replace the contents of a draft return note. Posted notes are cancelled, never edited."""
    note = DebitNote.objects.select_related("factory").get(pk=note.pk)
    assert_factory_access(user, note.factory)
    if note.status != DebitNote.Status.DRAFT:
        raise BusinessRuleError("Only a draft debit note can be edited.")
    if note.kind != DebitNote.Kind.RETURN:
        raise BusinessRuleError("A note raised from a GRN rejection cannot be edited.")
    _check_return_header(vendor, gst_template)
    note.vendor, note.date, note.reason = vendor, date, reason
    note.gst_template, note.itc_claimable = gst_template, itc_claimable
    note.lines.all().delete()
    _write_return_lines(note, note.factory, lines, gst_template)
    return note


def _remaining_recoverable(grn_line):
    billed = PurchaseInvoiceLine.objects.filter(grn_line=grn_line, invoice__status="posted").aggregate(
        r=Sum("recoverable_amount"))["r"] or ZERO
    debited = DebitNoteLine.objects.filter(grn_line=grn_line, note__status="posted", note__kind="rejection").aggregate(
        a=Sum("amount"))["a"] or ZERO
    return _r2(billed) - _r2(debited)


def _traced_to_bills(grn_line, amount):
    """Split `amount` (what is still recoverable on a GRN line: what `_remaining_recoverable` returned) over the posted
    bills that parked it there. {invoice: part}; the parts add up to `amount` exactly. Earlier posted rejection
    notes took the oldest bills' recoverable first, so this note takes what is left, oldest bill first: the very
    bills whose posting made this note postable."""
    taken = DebitNoteLine.objects.filter(grn_line=grn_line, note__status="posted", note__kind="rejection").aggregate(
        a=Sum("amount"))["a"] or ZERO
    taken, left, traced = _r2(taken), amount, {}
    for il in PurchaseInvoiceLine.objects.filter(grn_line=grn_line, invoice__status="posted", recoverable_amount__gt=0
                                                 ).select_related("invoice").order_by("invoice_id", "id"):
        gone = min(il.recoverable_amount, taken)
        taken -= gone
        part = min(il.recoverable_amount - gone, left)
        if part > 0:
            traced[il.invoice] = traced.get(il.invoice, ZERO) + part
            left -= part
    return traced


def _bill_allocations(vendor, vendor_ledger, traced, total):
    """Bill-wise allocations for the vendor's debit of a rejection note: 'against' each bill it was traced to, up to
    what that bill still has open in the ledger; the rest (a bill already paid, or nothing traced) on account.
    Empty means the posting engine's default, on account, exactly as before."""
    if not vendor_ledger.bill_wise:
        return ()
    open_bills = outstanding_bills(vendor_ledger)["bills"]
    out, against = [], ZERO
    for inv, amount in sorted(traced.items(), key=lambda pair: pair[0].pk):
        open_amount = max(-open_bills.get(inv.vendor_invoice_no, ZERO), ZERO)   # a bill we owe is a credit balance
        part = min(amount, open_amount)
        if part > 0:
            due = inv.vendor_invoice_date + timedelta(days=vendor.credit_days)  # the due date the bill was posted with
            out.append(AllocationSpec("against", part, inv.vendor_invoice_no, due))
            against += part
    if not out:
        return ()
    if total - against > 0:
        out.append(AllocationSpec("on_account", total - against))
    return tuple(out)


def can_post(note) -> bool:
    """Read-only: is this a draft that `post_debit_note` would take now? A rejection note waits until the vendor
    has billed every line of it (the same test posting applies); a return note is ready as soon as it is saved."""
    if note.status != DebitNote.Status.DRAFT:
        return False
    if note.kind != DebitNote.Kind.REJECTION:
        return True
    lines = list(note.lines.select_related("grn_line"))
    return bool(lines) and all(_remaining_recoverable(l.grn_line) > 0 for l in lines)


@transaction.atomic
def post_debit_note(note, *, user) -> DebitNote:
    note = DebitNote.objects.select_related("factory", "vendor", "company", "gst_template").get(pk=note.pk)
    assert_factory_access(user, note.factory)
    if note.status != DebitNote.Status.DRAFT:
        raise BusinessRuleError("This debit note has already been posted or cancelled.")
    vendor_ledger = note.vendor.payable_ledger
    if vendor_ledger is None:
        raise BusinessRuleError(f"{note.vendor.name} has no payable ledger.")
    company = note.company

    def ledger(key):
        return Ledger.objects.get(company=company, system_key=key)

    specs = []
    if note.kind == DebitNote.Kind.REJECTION:
        total, traced = ZERO, {}
        for line in note.lines.select_related("grn_line"):
            remaining = _remaining_recoverable(line.grn_line)
            if remaining <= 0:
                raise BusinessRuleError(
                    f"The vendor has not billed the rejected {line.item} yet (or it is already debited); "
                    "post the vendor's invoice first."
                )
            for inv, part in _traced_to_bills(line.grn_line, remaining).items():
                traced[inv] = traced.get(inv, ZERO) + part
            line.amount = remaining
            line.save(update_fields=["amount"])
            total += remaining
        note.subtotal = note.total = total
        specs = [
            LineSpec(ledger=vendor_ledger, debit=total, narration=note.reason,
                     allocations=_bill_allocations(note.vendor, vendor_ledger, traced, total)),
            LineSpec(ledger=ledger("rejected_recoverable"), credit=total),
        ]
    else:
        movements = []
        for line in note.lines.select_related("material", "sku", "roll", "location"):
            movements.append(stock.post_movement(
                factory=note.factory, location=line.location, item=line.item, qty=-line.qty, roll=line.roll,
                movement_type=T.RETURN_OUT, date=note.date, user=user, source=note,
            ))
        by_key = stock.gl_values(movements)
        out_value = ZERO
        specs.append(LineSpec(ledger=vendor_ledger, debit=note.total, narration=note.reason))
        for (_, key), v in by_key.items():
            amt = _r2(-v)
            out_value += amt
            if amt > 0:
                specs.append(LineSpec(ledger=ledger(key), credit=amt))
        input_total = ZERO
        if note.gst_template and note.itc_claimable:
            for t in calc.compute(note.gst_template, note.subtotal):
                if t.amount > 0:
                    specs.append(LineSpec(ledger=ledger(f"{t.component}_input"), credit=t.amount))
                    input_total += t.amount
        diff = note.total - out_value - input_total  # Cr Purchase Returns (or Dr if the goods were worth more)
        if diff > 0:
            specs.append(LineSpec(ledger=ledger("purchase_returns"), credit=diff))
        elif diff < 0:
            specs.append(LineSpec(ledger=ledger("purchase_returns"), debit=-diff))
    voucher = post_voucher(
        company=company, factory=note.factory, voucher_type="debit_note", date=note.date, lines=specs, user=user,
        narration=f"Debit note to {note.vendor.name}: {note.reason}"[:500], source=note,
    )
    note.number = next_document_number(factory=note.factory, doc_type="debit_note", on_date=note.date)
    note.status, note.voucher = DebitNote.Status.POSTED, voucher
    note.save()
    return note


@transaction.atomic
def cancel_debit_note(note, *, user, reason) -> DebitNote:
    note = DebitNote.objects.select_related("factory").get(pk=note.pk)
    assert_factory_access(user, note.factory)
    if note.status == DebitNote.Status.DRAFT:
        note.status = DebitNote.Status.CANCELLED
        note.save()
        return note
    if note.status != DebitNote.Status.POSTED:
        raise BusinessRuleError("This debit note is already cancelled.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the debit note.")
    when = max(timezone.localdate(), note.date)
    for m in StockMovement.objects.filter(source_type=note._meta.label_lower, source_id=note.pk,
                                          movement_type=T.RETURN_OUT).select_related("material", "sku", "roll", "location", "factory"):
        stock.reverse_movement(m, user=user, date=when, source=note, notes=f"Debit note {note.number} cancelled")
    reverse_voucher(note.voucher, user=user, reason=f"Debit note cancelled: {reason.strip()}", date=when)
    note.status = DebitNote.Status.CANCELLED
    note.save()
    return note
