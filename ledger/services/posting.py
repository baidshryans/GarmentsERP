"""The posting engine: every voucher in the system is created through this module.

Rules enforced here (BR-16, BR-20, BR-23, BR-24):
  * a voucher, draft or posted, always balances and always carries a factory;
  * all amounts are Decimal with at most two decimal places (floats are refused);
  * the voucher number is drawn inside the same transaction, so a failure leaves no gap;
  * a posted voucher is never edited or deleted - it is cancelled by a reversing voucher.

Source documents (GRN, invoice, challan bill ...) call post_voucher() from inside their own
transaction.atomic() block, so the document, its stock movements and its GL voucher commit
or roll back together.
"""
from dataclasses import dataclass, field
from datetime import date as date_cls
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.models import FinancialYear
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from core.services.periods import assert_period_open
from ledger.exceptions import (
    FactoryRequired,
    InvalidLine,
    NotReversible,
    PostedVoucherImmutable,
    PostingError,
    Unbalanced,
)
from ledger.models import BillAllocation, Voucher, VoucherLine

TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass
class AllocationSpec:
    ref_type: str
    amount: Decimal
    reference: str = ""
    due_date: date_cls | None = None


@dataclass
class LineSpec:
    ledger: object
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    narration: str = ""
    factory: object | None = None  # defaults to the voucher's factory
    allocations: tuple = field(default_factory=tuple)


def _money(value, what) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, int)):
        raise InvalidLine(f"{what} must be a Decimal, not {type(value).__name__}.")
    value = Decimal(value)
    if value != value.quantize(TWO_PLACES):
        raise InvalidLine(f"{what} {value} has more than two decimal places; round it before posting.")
    return value.quantize(TWO_PLACES)


def _validate(*, company, factory, lines, user, check_active=True, scope_lines=True):
    """Return normalised lines. Raises a PostingError subclass on any problem."""
    if factory is None:
        raise FactoryRequired("A voucher must carry a factory.")
    if factory.company_id != company.pk:
        raise PostingError("The factory belongs to a different company.")
    if not factory.is_active:
        raise PostingError(f"Factory {factory.code} is inactive.")
    assert_factory_access(user, factory)
    if len(lines) < 2:
        raise InvalidLine("A voucher needs at least two lines.")

    normalised = []
    total_dr = total_cr = ZERO
    settled = {}          # (ledger id, bill reference) -> settled so far in this voucher
    for i, spec in enumerate(lines, start=1):
        debit = _money(spec.debit, f"Line {i} debit")
        credit = _money(spec.credit, f"Line {i} credit")
        if debit < 0 or credit < 0:
            raise InvalidLine(f"Line {i}: amounts cannot be negative.")
        if (debit > 0) == (credit > 0):
            raise InvalidLine(f"Line {i}: enter either a debit or a credit amount, not both or neither.")
        ledger = spec.ledger
        if ledger.company_id != company.pk:
            raise InvalidLine(f"Line {i}: ledger {ledger} belongs to a different company.")
        if check_active and not ledger.is_active:
            raise InvalidLine(f"Line {i}: ledger {ledger} is inactive.")
        line_factory = spec.factory or factory
        if line_factory.pk != factory.pk:
            if line_factory.company_id != company.pk or not line_factory.is_active:
                raise InvalidLine(f"Line {i}: invalid factory.")
            if scope_lines:
                assert_factory_access(user, line_factory)

        amount = debit or credit
        allocations = _normalise_allocations(i, ledger, amount, spec.allocations)
        if check_active:        # a reversal re-opens bills and must not be held to the open-bill check
            _check_settlements(i, ledger, bool(debit), allocations, settled)
        total_dr += debit
        total_cr += credit
        normalised.append((spec, debit, credit, line_factory, allocations))

    if total_dr != total_cr:
        raise Unbalanced(f"Debits {total_dr} and credits {total_cr} do not match (difference {total_dr - total_cr}).")
    # Each factory's lines must balance on their own, so factory-wise books always tally (ACC-13).
    # A movement between factories goes through the Inter-Factory Receivable / Payable ledgers (ACC-17).
    by_factory = {}
    for _, debit, credit, line_factory, _ in normalised:
        net = by_factory.setdefault(line_factory.pk, [line_factory, ZERO])
        net[1] += debit - credit
    for line_factory, net in by_factory.values():
        if net != 0:
            raise Unbalanced(
                f"Factory {line_factory.code} is out of balance by {net}. Entries across factories must "
                "go through the Inter-Factory Receivable / Payable ledgers."
            )
    return normalised, total_dr


def _check_settlements(i, ledger, is_debit, allocations, settled):
    """An 'against' allocation must name a bill that is still open on the opposite side, and may not exceed
    what is outstanding, so a fully paid invoice takes no further payment (ACC-14)."""
    from ledger.selectors import outstanding_bills

    for a in allocations:
        if a.ref_type != "against":
            continue
        key = (ledger.pk, a.reference)
        balance = outstanding_bills(ledger)["bills"].get(a.reference, ZERO)
        open_amount = (-balance if is_debit else balance) - settled.get(key, ZERO)
        if balance == 0 or open_amount <= 0:
            raise InvalidLine(
                f"Line {i}: bill '{a.reference}' of {ledger} is already fully settled or has no balance to settle; "
                "no further payment can be made against it."
            )
        if a.amount > open_amount:
            raise InvalidLine(
                f"Line {i}: bill '{a.reference}' of {ledger} has only {open_amount} outstanding, "
                f"but {a.amount} was entered."
            )
        settled[key] = settled.get(key, ZERO) + a.amount


def _normalise_allocations(i, ledger, amount, allocations):
    allocations = list(allocations or ())
    if not allocations:
        # Bill-wise ledgers always carry a settlement trail; default to "on account".
        if ledger.bill_wise:
            return [AllocationSpec("on_account", amount)]
        return []
    if not ledger.bill_wise:
        raise InvalidLine(f"Line {i}: ledger {ledger} is not bill-wise, so it cannot carry bill allocations.")
    total = ZERO
    out = []
    for a in allocations:
        amt = _money(a.amount, f"Line {i} allocation")
        if amt <= 0:
            raise InvalidLine(f"Line {i}: allocation amounts must be positive.")
        if a.ref_type in ("new", "against") and not a.reference.strip():
            raise InvalidLine(f"Line {i}: a bill reference is required for '{a.ref_type}' allocations.")
        total += amt
        out.append(AllocationSpec(a.ref_type, amt, a.reference.strip(), a.due_date))
    if total != amount:
        raise InvalidLine(f"Line {i}: allocations total {total} but the line is {amount}.")
    return out


def _write_lines(voucher, normalised):
    for n, (spec, debit, credit, line_factory, allocations) in enumerate(normalised, start=1):
        line = VoucherLine.objects.create(
            voucher=voucher, line_no=n, ledger=spec.ledger, debit=debit, credit=credit,
            narration=spec.narration, factory=line_factory,
        )
        for a in allocations:
            BillAllocation.objects.create(
                line=line, ref_type=a.ref_type, reference=a.reference, amount=a.amount, due_date=a.due_date
            )


def _source_fields(source):
    if source is None:
        return {}
    return {"source_type": source._meta.label_lower, "source_id": source.pk}


@transaction.atomic
def create_draft(*, company, factory, voucher_type, date, lines, user, narration="", source=None,
                 reverses=None, reversal_reason="", _reversal=False, scope_lines=True,
                 vendor_invoice_no="") -> Voucher:
    """Save a draft. A draft must already balance and carry a factory."""
    normalised, total = _validate(company=company, factory=factory, lines=lines, user=user,
                                  check_active=not _reversal, scope_lines=scope_lines)
    assert_period_open(company, factory, date)
    voucher = Voucher.objects.create(
        company=company, factory=factory, voucher_type=voucher_type, date=date,
        financial_year=FinancialYear.for_date(company, date), narration=narration, total=total,
        created_by=user, reverses=reverses, reversal_reason=reversal_reason, vendor_invoice_no=vendor_invoice_no.strip(),
        **_source_fields(source),
    )
    _write_lines(voucher, normalised)
    return voucher


@transaction.atomic
def update_draft(voucher, *, lines, user, date=None, narration=None) -> Voucher:
    voucher = Voucher.objects.select_related("factory", "company").get(pk=voucher.pk)
    if voucher.is_posted:
        raise PostedVoucherImmutable(f"{voucher.number} is posted; reverse it instead of editing.")
    normalised, total = _validate(company=voucher.company, factory=voucher.factory, lines=lines, user=user)
    new_date = date or voucher.date
    assert_period_open(voucher.company, voucher.factory, new_date)
    voucher.date = new_date
    voucher.financial_year = FinancialYear.for_date(voucher.company, new_date)
    if narration is not None:
        voucher.narration = narration
    voucher.total = total
    voucher.save()
    VoucherLine.objects.filter(voucher=voucher).delete()
    _write_lines(voucher, normalised)
    return voucher


@transaction.atomic
def post_draft(voucher, *, user) -> Voucher:
    voucher = Voucher.objects.select_related("factory", "company").get(pk=voucher.pk)
    if voucher.is_posted:
        raise PostedVoucherImmutable(f"{voucher.number} is already posted.")
    assert_factory_access(user, voucher.factory)
    assert_period_open(voucher.company, voucher.factory, voucher.date)
    lines = list(voucher.lines.all())
    debit = sum((l.debit for l in lines), ZERO)
    credit = sum((l.credit for l in lines), ZERO)
    if len(lines) < 2 or debit != credit:
        raise Unbalanced("The draft no longer balances and cannot be posted.")
    per_factory = {}
    for l in lines:
        per_factory[l.factory_id] = per_factory.get(l.factory_id, ZERO) + l.debit - l.credit
    if any(net != 0 for net in per_factory.values()):
        raise Unbalanced("The draft no longer balances factory by factory and cannot be posted.")
    voucher.number = next_document_number(
        factory=voucher.factory, doc_type=voucher.voucher_type, on_date=voucher.date
    )
    voucher.status = Voucher.Status.POSTED
    voucher.posted_by = user
    voucher.posted_at = timezone.now()
    voucher.save()
    return voucher


@transaction.atomic
def post_voucher(*, company, factory, voucher_type, date, lines, user, narration="", source=None,
                 scope_lines=True, vendor_invoice_no="") -> Voucher:
    """Validate, number and post in one transaction. The usual entry point for source documents.

    scope_lines=False lets a source document post a line into another factory the user cannot access
    (an inter-factory transfer's receiving side). The header factory is always checked.
    """
    draft = create_draft(
        company=company, factory=factory, voucher_type=voucher_type, date=date, lines=lines,
        user=user, narration=narration, source=source, scope_lines=scope_lines,
        vendor_invoice_no=vendor_invoice_no,
    )
    return post_draft(draft, user=user)


_SWAP = {"new": "against", "against": "new", "advance": "advance", "on_account": "on_account"}


@transaction.atomic
def reverse_voucher(voucher, *, user, reason, date=None) -> Voucher:
    """Cancel a posted voucher by posting its mirror image. The original is never touched."""
    voucher = Voucher.objects.select_related("factory", "company").get(pk=voucher.pk)
    if not voucher.is_posted:
        raise NotReversible("Only a posted voucher can be reversed; discard a draft instead.")
    if voucher.reverses_id:
        raise NotReversible("A reversing voucher cannot itself be reversed; post a new entry.")
    if voucher.reversals.exists():
        raise NotReversible(f"{voucher.number} has already been reversed.")
    if not reason or not reason.strip():
        raise PostingError("A reason is required to reverse a voucher.")

    specs = []
    for line in voucher.lines.select_related("ledger", "factory").prefetch_related("allocations"):
        specs.append(LineSpec(
            ledger=line.ledger, debit=line.credit, credit=line.debit, narration=line.narration,
            factory=line.factory,
            allocations=tuple(
                AllocationSpec(_SWAP[a.ref_type], a.amount, a.reference, a.due_date)
                for a in line.allocations.all()
            ),
        ))
    reversal = create_draft(
        company=voucher.company, factory=voucher.factory, voucher_type=voucher.voucher_type,
        date=date or timezone.localdate(), lines=specs, user=user,
        narration=f"Reversal of {voucher.number}: {reason.strip()}"[:500],
        reverses=voucher, reversal_reason=reason.strip(), _reversal=True,
    )
    return post_draft(reversal, user=user)
