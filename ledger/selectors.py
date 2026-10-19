"""Read-only queries over posted vouchers. Reports never hold data of their own."""
from decimal import Decimal

from django.db.models import Sum

from ledger.models import BillAllocation, Ledger, VoucherLine

ZERO = Decimal("0.00")


def q2(value) -> Decimal:
    """Round an aggregate back to paise: SQLite adds DecimalFields as floats, so sums can carry 1e-14 noise."""
    return Decimal(value or 0).quantize(Decimal("0.01"))


def posted_lines(user=None, factory=None, as_of=None, date_from=None):
    qs = VoucherLine.objects.filter(voucher__status="posted")
    if date_from is not None:
        qs = qs.filter(voucher__date__gte=date_from)
    if user is not None:
        qs = qs.for_user(user)
    if factory is not None:
        qs = qs.filter(factory=factory)
    if as_of is not None:
        qs = qs.filter(voucher__date__lte=as_of)
    return qs


def trial_balance(company, *, user=None, factory=None, as_of=None, date_from=None):
    """Per ledger: Opening | Debit | Credit | Closing for the period from `date_from` to `as_of` (owner, 19 Oct
    2026). Opening is everything dated before `date_from` plus the opening entries (opening balances and opening
    stock), wherever they fall; Debit and Credit are the period's own activity. Without `date_from`, opening is the
    opening entries alone and everything else up to `as_of` is activity. Filter by factory, or all the user's."""
    from django.db.models import Q

    is_opening = Q(voucher__voucher_type="opening")
    if date_from is not None:
        is_opening |= Q(voucher__date__lt=date_from)
    lines = posted_lines(user, factory, as_of).filter(ledger__company=company)
    keys = ("ledger_id", "ledger__name", "ledger__group__name", "ledger__group__nature", "ledger__group__sort_order")
    opening = {r["ledger_id"]: q2(r["d"]) - q2(r["c"]) for r in
               lines.filter(is_opening).values("ledger_id").annotate(d=Sum("debit"), c=Sum("credit"))}
    period = {r["ledger_id"]: r for r in
              lines.exclude(is_opening).values(*keys).annotate(debit=Sum("debit"), credit=Sum("credit"))}
    names = {r["ledger_id"]: r for r in lines.values(*keys).distinct()}
    result = []
    total_dr = total_cr = closing_dr = closing_cr = ZERO
    for ledger_id, r in sorted(names.items(), key=lambda kv: (kv[1]["ledger__group__sort_order"], kv[1]["ledger__name"])):
        p = period.get(ledger_id, {})
        dr, cr, op = q2(p.get("debit")), q2(p.get("credit")), opening.get(ledger_id, ZERO)
        closing = op + dr - cr
        result.append({
            "ledger_id": ledger_id, "ledger": r["ledger__name"], "group": r["ledger__group__name"],
            "nature": r["ledger__group__nature"], "opening": op, "debit": dr, "credit": cr, "closing": closing,
            "opening_debit": op if op > 0 else ZERO, "opening_credit": -op if op < 0 else ZERO,
            "closing_debit": closing if closing > 0 else ZERO,
            "closing_credit": -closing if closing < 0 else ZERO,
        })
        total_dr += dr
        total_cr += cr
        closing_dr += closing if closing > 0 else ZERO
        closing_cr += -closing if closing < 0 else ZERO
    return {
        "rows": result, "total_debit": total_dr, "total_credit": total_cr,
        "total_closing_debit": closing_dr, "total_closing_credit": closing_cr,
        "tallies": total_dr == total_cr and closing_dr == closing_cr,
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


def bill_outstanding(ledger: Ledger, reference: str, *, user=None) -> Decimal:
    """Signed (debit-positive) amount still open on one bill of a ledger; zero when settled or unknown."""
    if ledger is None or not reference:
        return ZERO
    return outstanding_bills(ledger, user=user)["bills"].get(reference, ZERO)


def ledger_position(ledger: Ledger, *, user=None) -> dict:
    """What is owed on a ledger across every factory the user may see, for display beside a party or ledger choice.

    `outstanding` is the net of its open bills (debit-positive); `advance` and `on_account` are kept apart;
    `balance` is the full ledger balance. Information only: nothing is blocked on it.
    """
    data = outstanding_bills(ledger, user=user)
    return {
        "balance": ledger_balance(ledger, user=user),
        "outstanding": sum(data["bills"].values(), ZERO),
        "open_bills": len(data["bills"]),
        "advance": data["advance"],
        "on_account": data["on_account"],
        "bill_wise": ledger.bill_wise,
    }
