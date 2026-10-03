"""Read-only queries over posted vouchers. Reports never hold data of their own."""
from decimal import Decimal

from django.db.models import Sum

from ledger.models import BillAllocation, Ledger, VoucherLine

ZERO = Decimal("0.00")


def q2(value) -> Decimal:
    """Round an aggregate back to paise: SQLite adds DecimalFields as floats, so sums can carry 1e-14 noise."""
    return Decimal(value or 0).quantize(Decimal("0.01"))


def posted_lines(user=None, factory=None, as_of=None):
    qs = VoucherLine.objects.filter(voucher__status="posted")
    if user is not None:
        qs = qs.for_user(user)
    if factory is not None:
        qs = qs.filter(factory=factory)
    if as_of is not None:
        qs = qs.filter(voucher__date__lte=as_of)
    return qs


def trial_balance(company, *, user=None, factory=None, as_of=None):
    """Per-ledger totals and closing balance. Filter by factory, or all factories the user may see."""
    rows = (
        posted_lines(user, factory, as_of)
        .filter(ledger__company=company)
        .values("ledger_id", "ledger__name", "ledger__group__name", "ledger__group__nature")
        .annotate(debit=Sum("debit"), credit=Sum("credit"))
        .order_by("ledger__group__sort_order", "ledger__name")
    )
    result = []
    total_dr = total_cr = ZERO
    for r in rows:
        dr, cr = q2(r["debit"]), q2(r["credit"])
        closing = dr - cr
        result.append({
            "ledger_id": r["ledger_id"], "ledger": r["ledger__name"], "group": r["ledger__group__name"],
            "nature": r["ledger__group__nature"], "debit": dr, "credit": cr,
            "closing_debit": closing if closing > 0 else ZERO,
            "closing_credit": -closing if closing < 0 else ZERO,
        })
        total_dr += dr
        total_cr += cr
    return {
        "rows": result, "total_debit": total_dr, "total_credit": total_cr,
        "tallies": total_dr == total_cr,
    }


def ledger_balance(ledger: Ledger, *, user=None, factory=None, as_of=None) -> Decimal:
    """Debit-positive balance of one ledger."""
    agg = posted_lines(user, factory, as_of).filter(ledger=ledger).aggregate(d=Sum("debit"), c=Sum("credit"))
    return q2(agg["d"]) - q2(agg["c"])


def outstanding_bills(ledger: Ledger, *, user=None, factory=None):
    """Bill-wise outstanding for a ledger: {reference: signed balance}, debit-positive, non-zero only.

    A 'new' allocation opens a bill on the side of its line, an 'against' allocation settles it from
    the other side. Advances and on-account amounts are returned under their own keys.
    """
    allocs = BillAllocation.objects.filter(line__ledger=ledger, line__voucher__status="posted")
    if user is not None:
        allocs = allocs.filter(line__in=VoucherLine.objects.for_user(user))
    if factory is not None:
        allocs = allocs.filter(line__factory=factory)
    bills, advance, on_account = {}, ZERO, ZERO
    for a in allocs.select_related("line"):
        signed = a.amount if a.line.debit else -a.amount
        if a.ref_type in ("new", "against"):
            bills[a.reference] = bills.get(a.reference, ZERO) + signed
        elif a.ref_type == "advance":
            advance += signed
        else:
            on_account += signed
    return {
        "bills": {ref: bal for ref, bal in bills.items() if bal != 0},
        "advance": advance,
        "on_account": on_account,
    }
