"""
Rebuild per-invoice `due_amt` from the General Ledger.

`due_amt` is a denormalized cache used by the per-bill outstanding/aging report
and by bill allocation. The authoritative outstanding is the party's GL balance
(see accounting/receivables.py). This module re-derives each bill's `due_amt`
so that, per (retail, party):

    Σ due_amt == max(0, amount the party owes us / we owe them)

distributed FIFO — oldest bills are considered settled first, so the unpaid
balance sits on the newest bills (correct ageing). Because it reads only the GL
(opening balances + posted vouchers), it produces correct values after a fresh
database sync, with no dependence on legacy allocation amounts.

Sales debtors carry debit balances (sign +1); purchase creditors carry credit
balances (sign -1).
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

_D = lambda x: Decimal(str(x or 0))
_EPS = Decimal("0.005")


def _compute_rebuild(bills, total_of, sign, as_of):
    """Core FIFO rebuild shared by sales and purchase.

    bills      : list of model instances exposing id, retail_id, ldgr_id,
                 date1, due_amt.
    total_of   : callable(bill) -> Decimal billed total.
    sign       : +1 if a debit GL balance means "owed to us" (sales),
                 -1 if a credit GL balance means it (purchase).
    Returns (changes, unchanged) with changes = [(bill, old_due, new_due)].
    """
    from accounting.receivables import ledger_balances
    from mastersconfig.models import RetailMaster

    total_cache = {b.id: total_of(b) for b in bills}

    groups = defaultdict(list)
    for b in bills:
        groups[(b.retail_id, b.ldgr_id)].append(b)

    ledgers_by_retail = defaultdict(set)
    for (rid, lid) in groups:
        ledgers_by_retail[rid].add(lid)
    bal_lookup = {}
    for rid, lids in ledgers_by_retail.items():
        retail_obj = RetailMaster.objects.filter(id=rid).first() if rid else None
        for lid, val in ledger_balances(retail_obj, lids, as_of).items():
            bal_lookup[(rid, lid)] = val

    changes, unchanged = [], 0
    for key, group_bills in groups.items():
        owed = max(Decimal("0"), sign * bal_lookup.get(key, Decimal("0")))
        group_bills.sort(key=lambda b: (b.date1 or date.min, b.id))  # oldest first
        total_billed = sum(total_cache[b.id] for b in group_bills)
        remaining_paid = max(Decimal("0"), total_billed - owed)  # FIFO settled pool
        for b in group_bills:
            t = total_cache[b.id]
            applied = min(remaining_paid, t)
            new_due = t - applied
            remaining_paid -= applied
            old_due = _D(b.due_amt)
            if abs(old_due - new_due) > _EPS:
                changes.append((b, old_due, new_due))
            else:
                unchanged += 1
    return changes, unchanged


def _apply(changes):
    from django.db import transaction
    if changes:
        with transaction.atomic():
            for b, _old, new in changes:
                b.due_amt = new
                b.save(update_fields=["due_amt"])


def _summary(changes, unchanged):
    old_sum = sum((o for _, o, _ in changes), Decimal("0"))
    new_sum = sum((n for _, _, n in changes), Decimal("0"))
    return {
        "changed": len(changes),
        "unchanged": unchanged,
        "old_sum": old_sum,
        "new_sum": new_sum,
        "delta": new_sum - old_sum,
        "changes": changes,
    }


# ── Sales (debtors) ─────────────────────────────────────────────────────────
def compute_sales_due_rebuild(retail=None, as_of=None, ldgr=None):
    from sales.models import SalesVou
    qs = SalesVou.objects.filter(ret_status=False)
    if retail is not None:
        qs = qs.filter(retail=retail)
    if ldgr is not None:
        qs = qs.filter(ldgr=ldgr)
    return _compute_rebuild(list(qs), lambda b: _D(b.total_bill_value),
                            Decimal("1"), as_of)


def rebuild_sales_due(retail=None, as_of=None, apply=False, ldgr=None):
    changes, unchanged = compute_sales_due_rebuild(retail=retail, as_of=as_of, ldgr=ldgr)
    if apply:
        _apply(changes)
    return _summary(changes, unchanged)


# ── Purchases (creditors) ───────────────────────────────────────────────────
def compute_purchase_due_rebuild(retail=None, as_of=None, ldgr=None):
    from purchase.models import PurchaseVoucher
    qs = PurchaseVoucher.objects.filter(is_return=False)
    if retail is not None:
        qs = qs.filter(retail=retail)
    if ldgr is not None:
        qs = qs.filter(ldgr=ldgr)
    return _compute_rebuild(list(qs),
                            lambda b: _D(b.total_incl_gst or b.bill_value),
                            Decimal("-1"), as_of)


def rebuild_purchase_due(retail=None, as_of=None, apply=False, ldgr=None):
    changes, unchanged = compute_purchase_due_rebuild(retail=retail, as_of=as_of, ldgr=ldgr)
    if apply:
        _apply(changes)
    return _summary(changes, unchanged)
