"""Opening balances for the books (financial side). Dated at the company's books-from date.

Any difference between total debits and credits is posted to the "Opening Balance Difference"
ledger, so the voucher still balances (BR-24) and the gap stays visible until the accountant
clears it. Opening stock is added in the inventory step and posts through the same ledger.
"""
from dataclasses import dataclass
from datetime import date as date_cls
from decimal import Decimal

from ledger.exceptions import PostingError
from ledger.models import Ledger
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher

ZERO = Decimal("0.00")


@dataclass
class OpeningEntry:
    ledger: Ledger
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    reference: str = ""  # bill reference for bill-wise ledgers (debtors, creditors ...)
    due_date: date_cls | None = None


def post_opening_balances(*, company, factory, entries, user, date=None):
    entries = [e for e in entries if (e.debit or e.credit)]
    if not entries:
        raise PostingError("Enter at least one opening balance.")
    difference_ledger = Ledger.objects.get(company=company, system_key="opening_difference")
    lines = []
    for e in entries:
        if (e.ledger.system_key or "").startswith("stock_"):
            raise PostingError(
                f"{e.ledger.name} is a stock ledger: enter opening stock under Inventory > Opening stock "
                "so quantities and value stay in step."
            )
        if e.ledger.pk == difference_ledger.pk:
            raise PostingError("The Opening Balance Difference ledger is filled in automatically.")
        amount = e.debit or e.credit
        allocations = ()
        if e.ledger.bill_wise:
            if e.reference.strip():
                allocations = (AllocationSpec("new", amount, e.reference, e.due_date),)
            else:
                allocations = (AllocationSpec("on_account", amount),)
        lines.append(LineSpec(
            ledger=e.ledger, debit=e.debit or ZERO, credit=e.credit or ZERO, allocations=allocations,
        ))
    total_dr = sum((l.debit for l in lines), ZERO)
    total_cr = sum((l.credit for l in lines), ZERO)
    if total_dr != total_cr:
        diff = total_dr - total_cr
        lines.append(LineSpec(
            ledger=difference_ledger,
            credit=diff if diff > 0 else ZERO,
            debit=-diff if diff < 0 else ZERO,
            narration="Difference in opening balances",
        ))
    return post_voucher(
        company=company, factory=factory, voucher_type="opening",
        date=date or company.books_from, lines=lines, user=user,
        narration="Opening balances",
    )
