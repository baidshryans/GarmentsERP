"""Sales, purchase, debit note and credit note vouchers entered by hand against a party (PRD E9.2, E9.4, ACC-12, ACC-15).

The accountant picks the party, the counter ledgers with their amounts, and optionally a GST template and (purchase)
a TDS template or (sales) a TCS template. The system works the tax out from the template; any component can be changed
with a reason. With no template there is no tax line at all (rule 3). GST and TDS are independent of each other.

    purchase     Dr counter ledgers, Dr Input GST (or Dr Input / Cr RCM payable for reverse charge), Cr TDS payable, Cr party
    sales        Cr counter ledgers, Cr Output GST, Cr TCS payable, Dr party
    debit note   Dr party (settles the bill), Cr counter ledgers, Cr Input GST reversed
    credit note  Cr party (settles the bill), Dr counter ledgers, Dr Output GST reversed
"""
from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal

from ledger.exceptions import PostingError
from ledger.models import AccountGroup, Ledger, VoucherType
from ledger.services.manual import EntryError, parse_amount
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher
from tax import calc

ZERO = Decimal("0.00")
PARTY_TYPES = {"sales": VoucherType.SALES, "purchase": VoucherType.PURCHASE,
               "debit_note": VoucherType.DEBIT_NOTE, "credit_note": VoucherType.CREDIT_NOTE}
RECEIVABLE = ("sales", "credit_note")          # the party is a debtor; the others are creditors
GST = ("cgst", "sgst", "igst")


@dataclass
class PartyRow:
    ledger: str = ""
    amount: str = ""
    narration: str = ""

    @property
    def blank(self):
        return not (self.ledger or self.amount.strip() or self.narration.strip())


def _under(ledger, group_name):
    node = ledger.group
    while node is not None:
        if node.name == group_name:
            return True
        node = node.parent
    return False


def _party(company, pk, vtype):
    try:
        ledger = Ledger.objects.select_related("group").get(pk=int(pk), company=company, is_active=True)
    except (TypeError, ValueError, Ledger.DoesNotExist):
        raise EntryError("Choose the party.")
    want = "Sundry Debtors" if vtype in RECEIVABLE else "Sundry Creditors"
    if not _under(ledger, want):
        raise EntryError(f"The party of a {vtype.replace('_', ' ')} must be a ledger under {want}.")
    return ledger


def _counter(company, pk, label):
    try:
        return Ledger.objects.get(pk=int(pk), company=company, is_active=True)
    except (TypeError, ValueError, Ledger.DoesNotExist):
        raise EntryError(f"{label}: choose a ledger.")


def _tax(template, base, kind, overrides):
    if template is None:
        return []
    if template.kind not in kind:
        raise EntryError(f"{template.name} is not a {' / '.join(k.upper() for k in kind)} template.")
    return calc.apply_overrides(calc.compute(template, base), overrides or {})


def build_lines(company, vtype, *, party_ledger, rows, ref_type, reference, due_date, gst_template, tax_template, overrides):
    """tax_template is the TDS template for a purchase and the TCS template for sales; notes take GST only."""
    counters, subtotal = [], ZERO
    for n, row in enumerate(rows, start=1):
        if row.blank:
            continue
        amount = parse_amount(row.amount, f"Row {n} amount")
        if not amount:
            raise EntryError(f"Row {n}: enter an amount.")
        ledger = _counter(company, row.ledger, f"Row {n}")
        if ledger.pk == party_ledger.pk:
            raise EntryError(f"Row {n} is the party itself; the party's line is made for you.")
        counters.append((ledger, amount, row.narration.strip()))
        subtotal += amount
    if not counters:
        raise EntryError("Add at least one row with a ledger and an amount.")
    if gst_template is not None and gst_template.kind != "gst":
        raise EntryError("Choose a GST template for GST.")
    reverse = bool(gst_template and gst_template.is_reverse_charge)
    if reverse and vtype != "purchase":
        raise EntryError("Reverse charge applies to a purchase only.")
    gst = _tax(gst_template, subtotal, ("gst",), overrides)
    if tax_template is not None and vtype not in ("purchase", "sales"):
        raise EntryError("TDS applies to a purchase and TCS to a sale; a note carries GST only.")
    other = _tax(tax_template, subtotal, ("tds",) if vtype == "purchase" else ("tcs",), overrides)
    gst_total = sum((t.amount for t in gst), ZERO)
    other_total = sum((t.amount for t in other), ZERO)

    def L(key):
        return Ledger.objects.get(company=company, system_key=key)

    debit_side = vtype in ("purchase", "credit_note")          # the counter ledgers are debited
    specs = []
    for ledger, amount, note in counters:
        specs.append(LineSpec(ledger=ledger, narration=note, **({"debit": amount} if debit_side else {"credit": amount})))
    for t in gst:
        if not t.amount:
            continue
        if vtype == "purchase":
            specs.append(LineSpec(ledger=L(f"{t.component}_input"), debit=t.amount, narration="GST input" + (" (reverse charge)" if reverse else "")))
            if reverse:
                specs.append(LineSpec(ledger=L(f"{t.component}_rcm"), credit=t.amount, narration="Reverse charge"))
        elif vtype == "sales":
            specs.append(LineSpec(ledger=L(f"{t.component}_output"), credit=t.amount, narration="GST output"))
        elif vtype == "debit_note":
            specs.append(LineSpec(ledger=L(f"{t.component}_input"), credit=t.amount, narration="GST input reversed"))
        else:
            specs.append(LineSpec(ledger=L(f"{t.component}_output"), debit=t.amount, narration="GST output reversed"))
    for t in other:
        if t.amount:
            key = "tds_payable" if vtype == "purchase" else "tcs_payable"
            specs.append(LineSpec(ledger=L(key), credit=t.amount, narration=("TDS deducted" if vtype == "purchase" else "TCS collected")))

    if vtype == "purchase":
        party_amount = subtotal + (ZERO if reverse else gst_total) - other_total
        party_side = {"credit": party_amount}
    elif vtype == "sales":
        party_amount = subtotal + gst_total + other_total
        party_side = {"debit": party_amount}
    elif vtype == "debit_note":
        party_amount = subtotal + gst_total
        party_side = {"debit": party_amount}
    else:
        party_amount = subtotal + gst_total
        party_side = {"credit": party_amount}
    if party_amount <= 0:
        raise EntryError("The party's amount is not more than zero; check the tax.")
    ref_type = ref_type or ("new" if vtype in ("purchase", "sales") else "against")
    if ref_type not in ("new", "against", "advance", "on_account"):
        raise EntryError("Unknown bill option.")
    if ref_type in ("new", "against") and not reference.strip():
        raise EntryError("Enter the bill reference (the invoice number).")
    allocations = (AllocationSpec(ref_type, party_amount, reference.strip(), due_date),) if party_ledger.bill_wise else ()
    specs.append(LineSpec(ledger=party_ledger, allocations=allocations, **party_side))
    return specs, party_amount


def post_party_voucher(*, company, factory, vtype, on_date, party, rows, user, narration="", ref_type="", reference="",
                       due_date=None, gst_template=None, tax_template=None, overrides=None):
    if vtype not in PARTY_TYPES:
        raise EntryError("This voucher type is not entered here.")
    if not isinstance(on_date, date_cls):
        raise EntryError("Enter a valid date.")
    party_ledger = _party(company, party, vtype)
    lines, _ = build_lines(company, vtype, party_ledger=party_ledger, rows=rows, ref_type=ref_type, reference=reference,
                           due_date=due_date, gst_template=gst_template, tax_template=tax_template, overrides=overrides)
    return post_voucher(company=company, factory=factory, voucher_type=PARTY_TYPES[vtype], date=on_date, lines=lines, user=user,
                        narration=narration.strip() or f"{PARTY_TYPES[vtype].label} {reference.strip()}".strip(),
                        vendor_invoice_no=reference.strip()[:40] if vtype == "purchase" else "")
