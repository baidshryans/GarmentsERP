"""Journal entry narrations in plain sentences (owner, 19 Oct 2026).

Every voucher that production and job work post says what happened, who did it, on which lot, and for labour
the pieces x the rate = the amount with the date of the rate used, so an owner who has never used an ERP can
read the day book and recognise his own work. The functions only read names off what they are given.
"""
from decimal import ROUND_HALF_UP, Decimal

MAX = 500


def _group(whole: str) -> str:
    """Indian digit grouping: 1,23,456."""
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join(pairs + [tail])


def money(value) -> str:
    """₹ with Indian grouping; whole rupees without paise (₹360), otherwise two places (₹1.50)."""
    v = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if v < 0 else ""
    v = abs(v)
    whole, paise = f"{v:.2f}".split(".")
    return f"{sign}₹{_group(whole)}" + ("" if paise == "00" else f".{paise}")


def number(value) -> str:
    """A quantity as a person writes it: 4.000 -> 4, 58.4 -> 58.40, 1.125 -> 1.125."""
    v = Decimal(value)
    if v == v.to_integral_value():
        return str(v.quantize(Decimal("1")))
    n = v.normalize()
    return f"{n:f}" if n.as_tuple().exponent < -2 else f"{v:.2f}"


def _rate_date(rate) -> str:
    d = rate.effective_from
    return f"rate from {d.day} {d:%b %Y}"


def _labour(what, lot, qty, rate) -> str:
    amount = Decimal(rate.rate) * qty
    return f"{what}, lot {lot.lot_no}: {qty} pieces × {money(rate.rate)} = {money(amount)} ({_rate_date(rate)})"


def _cut(text: str) -> str:
    return text[:MAX]


def inhouse_labour(process, factory, lot, qty, rate) -> str:
    return _cut(_labour(f"{process.name} in-house at {factory.name}", lot, qty, rate))


def labour_bill(party, items, tds) -> str:
    """items = [(lot, process, pieces, rate)], one clause each."""
    clauses = [_labour(f"{process.name} by {party.name}", lot, qty, rate) for lot, process, qty, rate in items]
    if tds and Decimal(tds) > 0:
        clauses.append(f"TDS {money(tds)}")
    return _cut("; ".join(clauses))


def packed(lot, qty, per_piece) -> str:
    return _cut(f"Lot {lot.lot_no}: {qty} pieces packed into Ready Goods at {money(per_piece)} a piece")


def moved_between_factories(lot, from_factory, to_factory, qty, amount) -> str:
    return _cut(f"Lot {lot.lot_no} moved from {from_factory.name} to {to_factory.name}: {qty} pieces, "
                f"{money(amount)} of work in progress")


def fabric_cut(lot, cutting_no, qty, unit, amount) -> str:
    return _cut(f"Fabric cut for lot {lot.lot_no}, Cutting {cutting_no}: {number(qty)} {unit}, {money(amount)}")


def _lines(lines) -> str:
    return ", ".join(f"{m.name} {number(q)} {m.unit.code}" for m, q in lines)


def materials_used(process, lot, lines, amount) -> str:
    return _cut(f"Trims used at {process.name}, lot {lot.lot_no}: {_lines(lines)}, {money(amount)}")


def materials_to_fabricator(party, lot, lines, amount) -> str:
    return _cut(f"Trims sent to {party.name} with lot {lot.lot_no}: {_lines(lines)}, {money(amount)}")


def trims_returned(party, lot, amount) -> str:
    return _cut(f"Trims returned by {party.name}, lot {lot.lot_no}: {money(amount)}")


def wip_written_off(lot, order, amount) -> str:
    return _cut(f"Lot {lot.lot_no}: {money(amount)} of work in progress written off, order {order.number} closed")
