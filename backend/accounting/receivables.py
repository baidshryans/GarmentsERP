"""
GL-based outstanding receivables / payables.

The single source of truth for "what a customer owes us" is the General Ledger:
    balance(ledger) = opening(debit - credit) + Σ posted(debit - credit)
This is exactly what the ledger statement shows. The per-invoice `due_amt`
field is a denormalized cache that has historically drifted from the GL, so
outstanding figures (dashboard KPI, Outstanding report, Balance-Sheet debtors)
should be derived from here instead.

Because it reads only LedgerOpenBalance + VoucherDetail — both populated by the
import/sync pipeline — these figures are automatically correct after a fresh
database sync, with no dependence on `due_amt`.

Sign convention: a debit balance on a Sundry Debtor means the customer owes us
(a receivable). A credit balance means we hold their money (an advance / payable)
and is excluded from receivables. Customers whose net position is a credit are
typically classified under Sundry Creditors and are excluded automatically.
"""
from decimal import Decimal

from django.db.models import Sum, F, DecimalField, Value
from django.db.models.functions import Coalesce

DEBTOR_GROUPS = ("Sundry Debtors",)
CREDITOR_GROUPS = ("Sundry Creditors",)

_DEC = DecimalField(max_digits=20, decimal_places=4)


def _group_subtree_ids(root_names):
    """All Account ids in the subtree(s) rooted at the named groups.

    There can be more than one group with the same name (multiple seeded
    hierarchies), so every match and its descendants are included.
    """
    from accounting.models import Account
    accounts = list(Account.objects.all().only("id", "parent_id", "name"))
    children = {}
    for a in accounts:
        children.setdefault(a.parent_id, []).append(a.id)
    out = set()
    stack = [a.id for a in accounts if a.name in root_names]
    while stack:
        cur = stack.pop()
        if cur in out:
            continue
        out.add(cur)
        stack.extend(children.get(cur, []))
    return out


def ledger_balances(retail, ledger_ids, as_of=None):
    """{ledger_id: Decimal balance} for the given ledger ids.

    balance = opening(debit - credit) + Σ txn(debit - credit), scoped to `retail`
    (None = all retails) and to vouchers dated on/before `as_of` (None = all).
    A debit balance is positive (the party owes us).
    """
    from accounting.models import LedgerOpenBalance, VoucherDetail

    ledger_ids = list(ledger_ids)
    bal = {lid: Decimal("0") for lid in ledger_ids}
    if not ledger_ids:
        return bal

    ob_filter = {"ldgr_id__in": ledger_ids}
    if retail is not None:
        ob_filter["retail"] = retail
    for row in (LedgerOpenBalance.objects.filter(**ob_filter)
                .values("ldgr_id")
                .annotate(b=Coalesce(Sum(F("debit") - F("credit"), output_field=_DEC),
                                     Value(Decimal("0"), output_field=_DEC)))):
        bal[row["ldgr_id"]] = bal.get(row["ldgr_id"], Decimal("0")) + row["b"]

    txn_filter = {"account_id__in": ledger_ids}
    if retail is not None:
        txn_filter["voucher_main__retail"] = retail
    if as_of is not None:
        txn_filter["voucher_main__date__lte"] = as_of
    for row in (VoucherDetail.objects.filter(**txn_filter)
                .values("account_id")
                .annotate(b=Coalesce(Sum(F("debit") - F("credit"), output_field=_DEC),
                                     Value(Decimal("0"), output_field=_DEC)))):
        bal[row["account_id"]] = bal.get(row["account_id"], Decimal("0")) + row["b"]
    return bal


def ledger_balances_for_groups(retail, group_names, as_of=None):
    """{ledger_id: Decimal balance} for every ledger in the given account groups."""
    from contacts.models import Ledger
    group_ids = _group_subtree_ids(group_names)
    ledger_ids = Ledger.objects.filter(ac_group_id__in=group_ids).values_list("id", flat=True)
    return ledger_balances(retail, ledger_ids, as_of)


def outstanding_receivable(retail, as_of=None):
    """Total amount owed to us by customers (sum of positive debtor balances)."""
    bal = ledger_balances_for_groups(retail, DEBTOR_GROUPS, as_of)
    return sum((b for b in bal.values() if b > 0), Decimal("0"))


def outstanding_payable(retail, as_of=None):
    """Total we owe suppliers (sum of credit balances on Sundry Creditors)."""
    bal = ledger_balances_for_groups(retail, CREDITOR_GROUPS, as_of)
    return sum((-b for b in bal.values() if b < 0), Decimal("0"))
