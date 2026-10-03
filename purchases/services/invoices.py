"""Vendor bill booked from GRN lines (E5.4).

On each bill the user chooses the tax: none, a GST template, reverse charge, or lines entered by
hand, and whether input credit is claimable. Nothing posts to a tax ledger unless chosen. If input
credit is not claimable, the GST (and any rate difference) is added to the item cost through a
stock value adjustment. TDS is deducted only if a TDS template is selected.

Voucher (all lines in the invoice's factory):
    Dr Goods Received Not Billed   - what the GRN credited for the accepted pieces billed
    Dr Rejected Goods Recoverable  - value (and tax) of billed pieces that failed QC, claimable by debit note
    Dr / Cr Stock                  - rate difference and non-claimable GST capitalised into stock value
    Dr Input GST                   - when claimable
    Cr RCM payable                 - reverse charge
    Cr TDS payable                 - if TDS selected
    Cr Vendor                      - bill value + GST - TDS (bill-wise, new reference = vendor invoice no.)
"""
from dataclasses import dataclass
from datetime import timedelta
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
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher, reverse_voucher
from purchases.models import DebitNote, GrnLine, PurchaseInvoice, PurchaseInvoiceLine, PurchaseInvoiceTax
from tax import calc

TWO = Decimal("0.01")
ZERO = Decimal("0.00")
THREE = Decimal("0.001")
GST_COMPONENTS = ("cgst", "sgst", "igst")
Mode = PurchaseInvoice.TaxMode


@dataclass
class InvoiceLineSpec:
    grn_line: object
    qty: Decimal
    rate: Decimal


def _r2(v):
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


def allocate(total, weights):
    """Split `total` over `weights` so the parts add up to exactly `total` (the last part takes the remainder)."""
    weights = list(weights)
    wsum = sum(weights, ZERO)
    if not weights:
        return []
    if wsum == 0:
        if total != 0:
            raise BusinessRuleError("There is no value on the accepted pieces to carry the tax.")
        return [ZERO] * len(weights)
    out, running = [], ZERO
    for i, w in enumerate(weights):
        part = total - running if i == len(weights) - 1 else _r2(total * w / wsum)
        out.append(part)
        running += part
    return out


def billed_qty(grn_line, exclude=None) -> Decimal:
    qs = PurchaseInvoiceLine.objects.filter(grn_line=grn_line, invoice__status="posted")
    if exclude is not None:
        qs = qs.exclude(invoice=exclude)
    return Decimal(qs.aggregate(q=Sum("qty"))["q"] or 0).quantize(THREE)


def billable_qty(grn_line, exclude=None) -> Decimal:
    return grn_line.qty_received - billed_qty(grn_line, exclude)


def last_rate(vendor, grn_line, exclude=None):
    kw = {"grn_line__material": grn_line.material} if grn_line.material_id else {"grn_line__sku": grn_line.sku}
    qs = PurchaseInvoiceLine.objects.filter(invoice__vendor=vendor, invoice__status="posted", **kw)
    if exclude is not None:
        qs = qs.exclude(invoice=exclude)
    prev = qs.order_by("-invoice__date", "-id").first()
    return prev.rate if prev else None


@transaction.atomic
def save_invoice(*, company, factory, vendor, vendor_invoice_no, vendor_invoice_date, date, lines, user,
                 invoice=None, tax_mode=Mode.NONE, gst_template=None, itc_claimable=True, tds_template=None,
                 tax_overrides=None, manual_tax=None, notes="") -> PurchaseInvoice:
    """Create a draft invoice, or replace the contents of an existing draft."""
    assert_factory_access(user, factory)
    if not vendor.is_vendor:
        raise BusinessRuleError(f"{vendor.name} is not marked as a vendor.")
    if invoice is not None:
        invoice = PurchaseInvoice.objects.get(pk=invoice.pk)
        if invoice.status != PurchaseInvoice.Status.DRAFT:
            raise BusinessRuleError("Only a draft invoice can be edited.")
    vendor_invoice_no = vendor_invoice_no.strip()
    if not vendor_invoice_no:
        raise BusinessRuleError("Enter the vendor's invoice number.")
    clash = PurchaseInvoice.objects.filter(company=company, vendor=vendor, vendor_invoice_no=vendor_invoice_no).exclude(status="cancelled")
    if invoice is not None:
        clash = clash.exclude(pk=invoice.pk)
    if clash.exists():
        raise BusinessRuleError(f"Invoice {vendor_invoice_no} from {vendor.name} has already been entered.")
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("Pick at least one GRN line to bill.")

    seen, prepared, subtotal = set(), [], ZERO
    for spec in lines:
        gl = GrnLine.objects.select_related("grn", "material", "sku").get(pk=spec.grn_line.pk)
        if gl.pk in seen:
            raise BusinessRuleError("A GRN line can be billed only once per invoice.")
        seen.add(gl.pk)
        if gl.grn.status != "posted" or gl.grn.vendor_id != vendor.pk or gl.grn.factory_id != factory.pk:
            raise BusinessRuleError(f"GRN {gl.grn} is not a posted GRN of this vendor and factory.")
        if isinstance(spec.qty, float) or isinstance(spec.rate, float):
            raise BusinessRuleError("Quantity and rate must be Decimal.")
        if spec.qty <= 0:
            raise BusinessRuleError(f"Billed quantity of {gl.item} must be more than zero.")
        if spec.rate < 0:
            raise BusinessRuleError(f"The rate of {gl.item} cannot be negative.")
        avail = billable_qty(gl, exclude=invoice)
        if spec.qty > avail:
            raise BusinessRuleError(f"{gl.item}: only {avail.normalize():f} is left to bill on {gl.grn}.")
        amount = _r2(spec.qty * spec.rate)
        prev = last_rate(vendor, gl, exclude=invoice)
        prepared.append((gl, spec, amount, prev is not None and prev != spec.rate))
        subtotal += amount

    gst = []
    if tax_mode == Mode.NONE:
        pass
    elif tax_mode in (Mode.TEMPLATE, Mode.REVERSE_CHARGE):
        if gst_template is None or gst_template.kind != "gst":
            raise BusinessRuleError("Choose a GST template.")
        if (tax_mode == Mode.REVERSE_CHARGE) != gst_template.is_reverse_charge:
            raise BusinessRuleError("The template does not match the tax choice (reverse charge vs normal).")
        gst = calc.apply_overrides(calc.compute(gst_template, subtotal), tax_overrides or {})
    elif tax_mode == Mode.MANUAL:
        entries = manual_tax or []
        if not entries or any(c not in GST_COMPONENTS for c, _ in entries):
            raise BusinessRuleError("Enter tax lines as CGST, SGST or IGST amounts.")
        gst = calc.manual_lines(entries)
    gst_total = sum((t.amount for t in gst), ZERO)
    tds = []
    if tds_template is not None:
        if tds_template.kind != "tds":
            raise BusinessRuleError("Choose a TDS template for TDS.")
        tds = calc.apply_overrides(calc.compute(tds_template, subtotal), tax_overrides or {})
    tds_total = sum((t.amount for t in tds), ZERO)
    payable = subtotal + (ZERO if tax_mode == Mode.REVERSE_CHARGE else gst_total) - tds_total
    if payable < 0:
        raise BusinessRuleError("TDS cannot be more than the bill value.")

    fields = dict(
        company=company, factory=factory, vendor=vendor, vendor_invoice_no=vendor_invoice_no,
        vendor_invoice_date=vendor_invoice_date, date=date, tax_mode=tax_mode, gst_template=gst_template,
        itc_claimable=itc_claimable, tds_template=tds_template, subtotal=subtotal, gst_total=gst_total,
        tds_total=tds_total, payable=payable, notes=notes,
    )
    if invoice is None:
        invoice = PurchaseInvoice.objects.create(created_by=user, **fields)
    else:
        for k, v in fields.items():
            setattr(invoice, k, v)
        invoice.save()
        invoice.lines.all().delete()
        invoice.tax_lines.all().delete()
    for gl, spec, amount, variance in prepared:
        PurchaseInvoiceLine.objects.create(invoice=invoice, grn_line=gl, qty=spec.qty, rate=spec.rate,
                                           amount=amount, rate_variance=variance)
    for kind, items in (("gst", gst), ("tds", tds)):
        for t in items:
            PurchaseInvoiceTax.objects.create(invoice=invoice, kind=kind, component=t.component, rate=t.rate,
                                              amount=t.amount, is_override=t.is_override, reason=t.reason)
    return invoice


def _apply_revaluation(invoice, grn_line, amount, user):
    """Add `amount` (can be negative) to the stock value of the pieces this GRN line brought in."""
    if amount == 0:
        return []
    grn = grn_line.grn
    item = grn_line.item
    if grn_line.is_fabric_rolls:
        rolls = [r for r in grn_line.rolls.all() if r.roll_id]
        parts = allocate(amount, [r.qty for r in rolls])
        pairs = [(r.roll, p) for r, p in zip(rolls, parts)]
    else:
        pairs = [(None, amount)]
    out = []
    for roll, part in pairs:
        if part == 0:
            continue
        out.append(stock.post_movement(
            factory=invoice.factory, location=grn.location, item=item, qty=Decimal("0"), value=part, roll=roll,
            movement_type=StockMovement.Type.REVALUATION, date=invoice.date, user=user, source=invoice,
            notes=f"Invoice {invoice.vendor_invoice_no}: rate difference / non-claimable tax",
        ))
    return out


@transaction.atomic
def post_invoice(invoice, *, user) -> PurchaseInvoice:
    inv = PurchaseInvoice.objects.select_related("factory", "vendor", "company").get(pk=invoice.pk)
    assert_factory_access(user, inv.factory)
    if inv.status != PurchaseInvoice.Status.DRAFT:
        raise BusinessRuleError("This invoice has already been posted or cancelled.")
    vendor_ledger = inv.vendor.payable_ledger
    if vendor_ledger is None:
        raise BusinessRuleError(f"{inv.vendor.name} has no payable ledger.")
    is_rcm = inv.tax_mode == Mode.REVERSE_CHARGE
    lines = list(inv.lines.select_related("grn_line__grn", "grn_line__material", "grn_line__sku"))

    rows = []
    for l in lines:
        gl = l.grn_line
        avail = billable_qty(gl, exclude=inv)
        if l.qty > avail:
            raise BusinessRuleError(f"{gl.item}: only {avail.normalize():f} is left to bill on {gl.grn}.")
        prior = PurchaseInvoiceLine.objects.filter(grn_line=gl, invoice__status="posted").exclude(invoice=inv)
        agg = prior.aggregate(q=Sum("qty_accepted_part"), c=Sum("grni_cleared"))
        remaining_acc = max(Decimal("0"), gl.qty_accepted - Decimal(agg["q"] or 0).quantize(THREE))
        acc = min(l.qty, remaining_acc)
        rej = l.qty - acc
        a_amt = _r2(acc * l.rate)
        rej_amt = l.amount - a_amt
        if acc > 0 and acc == remaining_acc:
            cleared = _r2(gl.value - (agg["c"] or ZERO))  # the last accepted pieces clear whatever is left
        elif acc > 0:
            cleared = _r2(gl.value * acc / gl.qty_accepted)
        else:
            cleared = ZERO
        rows.append({"line": l, "gl": gl, "acc": acc, "rej": rej, "a_amt": a_amt, "rej_amt": rej_amt,
                     "grni": cleared, "variance": a_amt - cleared, "rej_tax": ZERO, "cap_tax": ZERO})

    gst_lines = list(inv.tax_lines.filter(kind="gst"))
    input_by_comp = {}
    for tl in gst_lines:
        weights = [r["a_amt"] for r in rows] if is_rcm else [r["line"].amount for r in rows]
        shares = allocate(tl.amount, weights)
        acc_total = ZERO
        for r, share in zip(rows, shares):
            rej_share = ZERO if is_rcm or r["line"].amount == 0 else _r2(share * r["rej_amt"] / r["line"].amount)
            acc_share = share - rej_share
            r["rej_tax"] += rej_share
            acc_total += acc_share
            if not inv.itc_claimable:
                r["cap_tax"] += acc_share
        if inv.itc_claimable:
            input_by_comp[tl.component] = acc_total

    movements = []
    for r in rows:
        movements += _apply_revaluation(inv, r["gl"], r["variance"] + r["cap_tax"], user)

    specs = []
    company = inv.company

    def ledger(key):
        return Ledger.objects.get(company=company, system_key=key)

    grni_total = sum((r["grni"] for r in rows), ZERO)
    rec_total = sum((r["rej_amt"] + r["rej_tax"] for r in rows), ZERO)
    for key, amount in (("grni", grni_total), ("rejected_recoverable", rec_total)):
        if amount > 0:
            specs.append(LineSpec(ledger=ledger(key), debit=amount))
    for (_, key), net in stock.gl_values(movements).items():
        net = _r2(net)
        if net > 0:
            specs.append(LineSpec(ledger=ledger(key), debit=net, narration="Rate difference / non-claimable tax added to cost"))
        elif net < 0:
            specs.append(LineSpec(ledger=ledger(key), credit=-net, narration="Rate difference below GRN value"))
    for comp, amount in input_by_comp.items():
        if amount > 0:
            specs.append(LineSpec(ledger=ledger(f"{comp}_input"), debit=amount))
    if is_rcm:
        for tl in gst_lines:
            if tl.amount > 0:
                specs.append(LineSpec(ledger=ledger(f"{tl.component}_rcm"), credit=tl.amount, narration="Reverse charge"))
    if inv.tds_total > 0:
        specs.append(LineSpec(ledger=ledger("tds_payable"), credit=inv.tds_total, narration="TDS deducted"))
    due = inv.vendor_invoice_date + timedelta(days=inv.vendor.credit_days)
    specs.append(LineSpec(
        ledger=vendor_ledger, credit=inv.payable, narration=f"Invoice {inv.vendor_invoice_no}",
        allocations=(AllocationSpec("new", inv.payable, inv.vendor_invoice_no, due),),
    ))
    voucher = post_voucher(
        company=company, factory=inv.factory, voucher_type="purchase", date=inv.date, lines=specs, user=user,
        narration=f"Purchase from {inv.vendor.name}, invoice {inv.vendor_invoice_no}", source=inv,
        vendor_invoice_no=inv.vendor_invoice_no,
    )
    for r in rows:
        l = r["line"]
        l.qty_accepted_part, l.qty_rejected_part = r["acc"], r["rej"]
        l.grni_cleared, l.recoverable_amount = r["grni"], r["rej_amt"] + r["rej_tax"]
        l.save()
    inv.number = next_document_number(factory=inv.factory, doc_type="purchase_invoice", on_date=inv.date)
    inv.status, inv.voucher = PurchaseInvoice.Status.POSTED, voucher
    inv.save()
    return inv


@transaction.atomic
def cancel_invoice(invoice, *, user, reason) -> PurchaseInvoice:
    inv = PurchaseInvoice.objects.select_related("factory").get(pk=invoice.pk)
    assert_factory_access(user, inv.factory)
    if inv.status != PurchaseInvoice.Status.POSTED:
        raise BusinessRuleError("Only a posted invoice can be cancelled.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the invoice.")
    if DebitNote.objects.filter(status="posted", kind="rejection",
                                lines__grn_line__invoice_lines__invoice=inv).exists():
        raise BusinessRuleError("A debit note has been posted against this invoice's rejected pieces; cancel it first.")
    today = timezone.localdate()
    when = max(today, inv.date)
    for m in StockMovement.objects.filter(source_type=inv._meta.label_lower, source_id=inv.pk,
                                          movement_type=StockMovement.Type.REVALUATION).select_related(
            "material", "sku", "roll", "location", "factory"):
        stock.reverse_movement(m, user=user, date=when, source=inv, notes=f"Invoice {inv.vendor_invoice_no} cancelled")
    reverse_voucher(inv.voucher, user=user, reason=f"Invoice cancelled: {reason.strip()}", date=when)
    inv.status = PurchaseInvoice.Status.CANCELLED
    inv.notes = f"Cancelled: {reason.strip()}"[:255]
    inv.save()
    return inv
