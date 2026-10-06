"""Manual vouchers entered by an accountant: payment, receipt, contra and journal (PRD E9.2, E9.3).

The screen sends plain text; this module turns it into balanced voucher lines and hands them to the posting
engine, which numbers and posts them in one transaction. Nothing posts to GST or TDS ledgers unless the user
adds that ledger as a row (rule 3): there is no automatic tax here.
"""
from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal, InvalidOperation

from ledger.exceptions import PostingError
from ledger.models import AccountGroup, Ledger, VoucherType
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher

ZERO = Decimal("0.00")
CASH_BANK_GROUPS = ("Cash-in-hand", "Bank Accounts")
MANUAL_TYPES = {
    "payment": VoucherType.PAYMENT, "receipt": VoucherType.RECEIPT,
    "contra": VoucherType.CONTRA, "journal": VoucherType.JOURNAL,
}
REF_TYPES = ("new", "against", "advance", "on_account")


class EntryError(PostingError):
    """The entry cannot be turned into a voucher; the message says what to fix."""


@dataclass
class Row:
    ledger: str = ""
    to_ledger: str = ""
    amount: str = ""
    debit: str = ""
    credit: str = ""
    ref_type: str = ""
    reference: str = ""
    due_date: str = ""
    narration: str = ""

    @property
    def blank(self):
        # A row with only a note or a bill reference is not blank: it is rejected, never silently dropped.
        return not (self.ledger or self.to_ledger or self.amount or self.debit or self.credit
                    or self.narration.strip() or self.reference.strip() or self.due_date)


def cash_bank_ledgers(company):
    """Ledgers under Cash-in-hand or Bank Accounts, including any sub-groups the user adds there."""
    groups = AccountGroup.objects.filter(company=company)
    wanted = {g.pk for g in groups if g.name in CASH_BANK_GROUPS}
    frontier = set(wanted)
    while frontier:
        frontier = {g.pk for g in groups if g.parent_id in frontier} - wanted
        wanted |= frontier
    return Ledger.objects.filter(company=company, group_id__in=wanted, is_active=True).select_related("group")


def parse_amount(text, label):
    text = (text or "").strip().replace(",", "")
    if not text:
        return ZERO
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise EntryError(f"{label}: '{text}' is not a number.")
    if value < 0 or value != value.quantize(Decimal("0.01")):
        raise EntryError(f"{label}: use a positive amount with at most two decimals.")
    return value.quantize(Decimal("0.01"))


def _ledger(company, pk, label):
    try:
        return Ledger.objects.select_related("group").get(pk=int(pk), company=company, is_active=True)
    except (ValueError, TypeError, Ledger.DoesNotExist):
        raise EntryError(f"{label}: choose a ledger.")


def _allocations(ledger, amount, row, label):
    """Bill-wise ledgers carry a settlement trail: against a bill, a new bill, an advance, or on account."""
    if not ledger.bill_wise:
        return ()
    ref_type = row.ref_type or "on_account"
    if ref_type not in REF_TYPES:
        raise EntryError(f"{label}: unknown bill option '{ref_type}'.")
    if ref_type in ("new", "against") and not row.reference.strip():
        raise EntryError(f"{label}: enter the bill reference for '{ref_type}'.")
    due = None
    if row.due_date:
        try:
            due = date_cls.fromisoformat(row.due_date)
        except ValueError:
            raise EntryError(f"{label}: the due date must be a valid date.")
    return (AllocationSpec(ref_type, amount, row.reference.strip(), due),)


def _one_sided(company, rows, side):
    """Payment (side 'debit') and receipt (side 'credit'): the rows' ledgers on one side, a cash/bank ledger opposite."""
    specs, total = [], ZERO
    for n, row in enumerate(rows, start=1):
        if row.blank:
            continue
        label = f"Row {n}"
        amount = parse_amount(row.amount, f"{label} amount")
        if not amount:
            raise EntryError(f"{label}: enter an amount.")
        ledger = _ledger(company, row.ledger, label)
        specs.append(LineSpec(
            ledger=ledger, narration=row.narration.strip(), allocations=_allocations(ledger, amount, row, label),
            **{side: amount},
        ))
        total += amount
    if not specs:
        raise EntryError("Add at least one row with a ledger and an amount.")
    return specs, total


def build_lines(company, vtype, header, rows):
    cash_bank = {l.pk for l in cash_bank_ledgers(company)}

    if vtype in ("payment", "receipt"):
        label = "Paid from" if vtype == "payment" else "Received in"
        account = _ledger(company, header.get("account"), label)
        if account.pk not in cash_bank:
            raise EntryError(f"{label} must be a cash or bank ledger.")
        specs, total = _one_sided(company, rows, "debit" if vtype == "payment" else "credit")
        if any(s.ledger.pk == account.pk for s in specs):
            raise EntryError(f"A row uses the same ledger as '{label}'. Use a contra entry to move money between cash and bank.")
        opposite = {"credit": total} if vtype == "payment" else {"debit": total}
        return specs + [LineSpec(ledger=account, **opposite)]

    if vtype == "contra" and any(not r.blank for r in rows):
        specs = []
        for n, row in enumerate(rows, start=1):
            if row.blank:
                continue
            label = f"Row {n}"
            source = _ledger(company, row.ledger, f"{label} From")
            target = _ledger(company, row.to_ledger, f"{label} To")
            if source.pk not in cash_bank or target.pk not in cash_bank:
                raise EntryError(f"{label}: a contra entry moves money between cash and bank ledgers only.")
            if source.pk == target.pk:
                raise EntryError(f"{label}: 'From' and 'To' must be different.")
            amount = parse_amount(row.amount, f"{label} amount")
            if not amount:
                raise EntryError(f"{label}: enter an amount.")
            note = row.narration.strip()
            specs += [LineSpec(ledger=target, debit=amount, narration=note), LineSpec(ledger=source, credit=amount, narration=note)]
        return specs

    if vtype == "contra":
        source = _ledger(company, header.get("from_account"), "From")
        target = _ledger(company, header.get("to_account"), "To")
        if source.pk not in cash_bank or target.pk not in cash_bank:
            raise EntryError("A contra entry moves money between cash and bank ledgers only.")
        if source.pk == target.pk:
            raise EntryError("'From' and 'To' must be different.")
        amount = parse_amount(header.get("amount"), "Amount")
        if not amount:
            raise EntryError("Enter the amount.")
        return [LineSpec(ledger=target, debit=amount), LineSpec(ledger=source, credit=amount)]

    specs = []                                           # journal
    for n, row in enumerate(rows, start=1):
        if row.blank:
            continue
        label = f"Row {n}"
        debit, credit = parse_amount(row.debit, f"{label} debit"), parse_amount(row.credit, f"{label} credit")
        if bool(debit) == bool(credit):
            raise EntryError(f"{label}: enter either a debit or a credit.")
        ledger = _ledger(company, row.ledger, label)
        amount = debit or credit
        if row.ref_type == "new" and not row.reference.strip() and header.get("vendor_invoice_no", "").strip():
            row.reference = header["vendor_invoice_no"].strip()      # the vendor's invoice number opens the bill
        specs.append(LineSpec(ledger=ledger, debit=debit, credit=credit, narration=row.narration.strip(),
                              allocations=_allocations(ledger, amount, row, label)))
    if len(specs) < 2:
        raise EntryError("A journal needs at least two rows.")
    return specs


def post_manual_voucher(*, company, factory, vtype, on_date, narration, header, rows, user):
    """Build the lines and post the voucher. Raises PostingError (incl. EntryError) with nothing saved."""
    if vtype not in MANUAL_TYPES:
        raise EntryError("This voucher type cannot be entered by hand.")
    if on_date is None:
        raise EntryError("Enter a valid date.")
    if len((header.get("vendor_invoice_no") or "").strip()) > 40:
        raise EntryError("Supplier's bill no. can be at most 40 characters.")
    header = {**header, "vendor_invoice_no": (header.get("vendor_invoice_no") or "").strip()}
    lines = build_lines(company, vtype, header, rows)
    return post_voucher(
        company=company, factory=factory, voucher_type=MANUAL_TYPES[vtype], date=on_date,
        lines=lines, user=user, narration=narration.strip(),
        vendor_invoice_no=(header.get("vendor_invoice_no") or "") if vtype == "journal" else "",
    )
