"""Lot costing (E7.11). Quantities of pieces live in the stock movement ledger; the money on a lot lives here
and in the Work-in-Progress ledger. A lot's cost entries per factory always add up to that factory's WIP balance
(the test fixture checks it after every test).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum

from core.exceptions import BusinessRuleError
from ledger.models import Ledger
from ledger.services.posting import LineSpec, post_voucher
from production.models import Bundle, LotCostEntry

TWO = Decimal("0.01")
ZERO = Decimal("0.00")


def r2(value) -> Decimal:
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def ledger_for(company, key):
    return Ledger.objects.get(company=company, system_key=key)


def lot_cost(lot, factory=None) -> Decimal:
    qs = LotCostEntry.objects.filter(lot=lot)
    if factory is not None:
        qs = qs.filter(factory=factory)
    return r2(qs.aggregate(s=Sum("amount"))["s"] or 0)


def cost_breakdown(lot):
    """Cost by kind across all factories, for the lot cost screen."""
    rows = {k: ZERO for k, _ in LotCostEntry.Kind.choices}
    for e in lot.cost_entries.all():
        rows[e.kind] = rows[e.kind] + e.amount
    return {k: r2(v) for k, v in rows.items()}


def live_pieces(lot, factory=None) -> int:
    qs = Bundle.objects.filter(lot=lot, status__in=Bundle.LIVE)
    if factory is not None:
        qs = qs.filter(location__factory=factory)
    return qs.aggregate(s=Sum("qty"))["s"] or 0


def add_cost(*, lot, factory, kind, amount, date, note="", source=None, voucher=None) -> LotCostEntry:
    """Record cost on a lot. The caller posts the matching GL entry (and passes its voucher)."""
    return LotCostEntry.objects.create(
        lot=lot, factory=factory, kind=kind, amount=r2(amount), date=date, note=note[:255], voucher=voucher,
        source_type=source._meta.label_lower if source is not None else "", source_id=source.pk if source is not None else None,
    )


@transaction.atomic
def accrue_labour(*, lot, factory, amount, date, user, note="", source=None):
    """In-house piece-rate labour on accepted output: Dr WIP, Cr Labour Absorbed. Actual wages are booked separately."""
    amount = r2(amount)
    if amount <= 0:
        return None
    company = lot.company
    voucher = post_voucher(
        company=company, factory=factory, voucher_type="stock_journal", date=date, user=user, source=source,
        narration=f"In-house labour on lot {lot.lot_no}: {note}"[:500],
        lines=[LineSpec(ledger=ledger_for(company, "stock_wip"), debit=amount),
               LineSpec(ledger=ledger_for(company, "labour_absorbed"), credit=amount)],
    )
    return add_cost(lot=lot, factory=factory, kind=LotCostEntry.Kind.LABOUR, amount=amount, date=date, note=note,
                    source=source, voucher=voucher)


@transaction.atomic
def transfer_cost_between_factories(*, lot, from_factory, to_factory, pieces, date, user, source=None):
    """Move the share of a lot's WIP cost that belongs to `pieces` from one factory's books to another's,
    through the Inter-Factory ledgers, so each factory's WIP ledger keeps matching what is physically there."""
    here = live_pieces(lot, from_factory)
    if pieces <= 0 or here <= 0:
        return ZERO
    cost = lot_cost(lot, from_factory)
    moved = cost if pieces >= here else r2(cost * pieces / here)
    if moved == 0:
        return ZERO
    company = lot.company
    wip = ledger_for(company, "stock_wip")
    voucher = post_voucher(
        company=company, factory=from_factory, voucher_type="stock_journal", date=date, user=user, source=source,
        scope_lines=False, narration=f"Lot {lot.lot_no} moved from {from_factory.code} to {to_factory.code}",
        lines=[
            LineSpec(ledger=ledger_for(company, "interfactory_receivable"), debit=moved, factory=from_factory),
            LineSpec(ledger=wip, credit=moved, factory=from_factory),
            LineSpec(ledger=wip, debit=moved, factory=to_factory),
            LineSpec(ledger=ledger_for(company, "interfactory_payable"), credit=moved, factory=to_factory),
        ],
    )
    add_cost(lot=lot, factory=from_factory, kind=LotCostEntry.Kind.TRANSFER, amount=-moved, date=date,
             note=f"To {to_factory.code}", source=source, voucher=voucher)
    add_cost(lot=lot, factory=to_factory, kind=LotCostEntry.Kind.TRANSFER, amount=moved, date=date,
             note=f"From {from_factory.code}", source=source, voucher=voucher)
    return moved


def check_wip_reconciles(company):
    """For the tests and a future health check: every factory's lot cost equals its WIP ledger. Returns differences."""
    from core.models import Factory
    from ledger.models import VoucherLine

    problems = {}
    for f in Factory.objects.filter(company=company):
        costs = r2(LotCostEntry.objects.filter(factory=f).aggregate(s=Sum("amount"))["s"] or 0)
        gl = VoucherLine.objects.filter(factory=f, voucher__status="posted", ledger__system_key="stock_wip").aggregate(
            d=Sum("debit"), c=Sum("credit"))
        balance = r2(gl["d"] or 0) - r2(gl["c"] or 0)
        if costs != balance:
            problems[f.code] = (costs, balance)
    return problems
