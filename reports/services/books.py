"""The books as reports (E9.5, ACC-04, ACC-06, ACC-07, ACC-13, ACC-19): ledger statement, day book, profit and loss, balance
sheet and bill-wise ageing, each per factory or combined, always scoped to the factories the user may see.

Nothing here stores data. Profit is never "closed" into a ledger: a balance sheet ledger carries its balance forward
because balances are totals of posted lines, and the profit of earlier years is simply the total of the profit and loss
ledgers before the financial year began. So closing a year changes nothing in the figures; it locks the period (see
core.services.yearend), and reopening to post an audit adjustment flows into the later figures by itself (ACC-08).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Sum

from core.models import FinancialYear
from ledger.models import AccountGroup, BillAllocation, Ledger, Voucher, VoucherLine
from ledger.selectors import posted_lines, q2

ZERO = Decimal("0.00")

# profit and loss sections, by the root group a ledger sits under
TRADING_INCOME = ("Sales", "Direct Incomes")
TRADING_EXPENSE = ("Purchases", "Direct Expenses")
OTHER_INCOME = ("Indirect Incomes",)
OTHER_EXPENSE = ("Indirect Expenses",)


def _root_names(company):
    """{group id: name of its root group}."""
    groups = {g.pk: g for g in AccountGroup.objects.filter(company=company)}
    out = {}
    for pk, g in groups.items():
        node = g
        while node.parent_id:
            node = groups[node.parent_id]
        out[pk] = node.name
    return out


def _balances(company, user, factory, date_from=None, as_of=None, statement=None):
    """[(ledger_id, name, group name, root group name, nature, debit, credit)] for ledgers with postings in the period."""
    roots = _root_names(company)
    qs = posted_lines(user, factory, as_of, date_from).filter(ledger__company=company)
    if statement:
        qs = qs.filter(ledger__group__statement=statement)
    rows = qs.values("ledger_id", "ledger__name", "ledger__group_id", "ledger__group__name", "ledger__group__nature").annotate(
        d=Sum("debit"), c=Sum("credit")).order_by("ledger__group__sort_order", "ledger__name")
    return [(r["ledger_id"], r["ledger__name"], r["ledger__group__name"], roots[r["ledger__group_id"]],
             r["ledger__group__nature"], q2(r["d"]), q2(r["c"])) for r in rows]


# ---------------------------------------------------------------- ledger statement and day book (ACC-04)

def ledger_statement(ledger, *, user, factory=None, date_from=None, date_to=None):
    """Opening balance, every posted line in the period with a running balance (debit-positive), and the closing balance."""
    opening = ZERO
    if date_from is not None:
        agg = posted_lines(user, factory, date_from - timedelta(days=1)).filter(ledger=ledger).aggregate(d=Sum("debit"), c=Sum("credit"))
        opening = q2(agg["d"]) - q2(agg["c"])
    lines = posted_lines(user, factory, date_to, date_from).filter(ledger=ledger).select_related("voucher", "factory").order_by(
        "voucher__date", "voucher_id", "line_no")
    lines = list(lines)
    others = {}
    for l in VoucherLine.objects.filter(voucher_id__in={x.voucher_id for x in lines}).exclude(ledger=ledger).select_related("ledger"):
        others.setdefault(l.voucher_id, []).append(l.ledger.name)
    running, rows, total_dr, total_cr = opening, [], ZERO, ZERO
    for l in lines:
        running += l.debit - l.credit
        total_dr += l.debit
        total_cr += l.credit
        rows.append({"date": l.voucher.date, "voucher": l.voucher, "type": l.voucher.get_voucher_type_display(),
                     "particulars": ", ".join(sorted(set(others.get(l.voucher_id, [])))) or l.narration,
                     "narration": l.narration or l.voucher.narration, "debit": l.debit, "credit": l.credit, "balance": running,
                     "factory": l.factory.code})
    return {"ledger": ledger, "opening": opening, "rows": rows, "debit": total_dr, "credit": total_cr, "closing": running}


def day_book(company, *, user, factory=None, date_from=None, date_to=None, voucher_type=None):
    qs = Voucher.objects.for_user(user).filter(company=company, status="posted").select_related("factory")
    if factory is not None:
        qs = qs.filter(factory=factory)
    if date_from is not None:
        qs = qs.filter(date__gte=date_from)
    if date_to is not None:
        qs = qs.filter(date__lte=date_to)
    if voucher_type:
        qs = qs.filter(voucher_type=voucher_type)
    qs = qs.order_by("date", "id")
    vouchers = list(qs[:2000])
    return {"vouchers": vouchers, "total": sum((v.total for v in vouchers), ZERO), "truncated": qs.count() > 2000}


# ---------------------------------------------------------------- profit and loss (ACC-07, ACC-13)

def _section(rows, roots, sign):
    """Ledger lines under the given root groups; sign +1 shows credit minus debit, -1 debit minus credit."""
    out = []
    for lid, name, group, root, nature, d, c in rows:
        if root in roots:
            amount = (c - d) if sign > 0 else (d - c)
            if amount:
                out.append({"ledger_id": lid, "ledger": name, "group": group, "root": root, "amount": amount})
    return out


def profit_and_loss(company, *, user, factory=None, date_from, date_to):
    """Trading section (sales and direct incomes against purchases and direct expenses) to gross profit, then the
    indirect items to net profit. Cost of goods sold, labour absorbed and the like are ordinary ledgers in these groups."""
    rows = _balances(company, user, factory, date_from, date_to, statement="pl")
    income = _section(rows, TRADING_INCOME, +1)
    expense = _section(rows, TRADING_EXPENSE, -1)
    other_income = _section(rows, OTHER_INCOME, +1)
    other_expense = _section(rows, OTHER_EXPENSE, -1)
    t_inc, t_exp = sum((r["amount"] for r in income), ZERO), sum((r["amount"] for r in expense), ZERO)
    o_inc, o_exp = sum((r["amount"] for r in other_income), ZERO), sum((r["amount"] for r in other_expense), ZERO)
    gross = t_inc - t_exp
    net = gross + o_inc - o_exp
    sales = sum((r["amount"] for r in income if r["root"] == "Sales"), ZERO)
    return {
        "income": income, "expense": expense, "other_income": other_income, "other_expense": other_expense,
        "trading_income": t_inc, "trading_expense": t_exp, "gross_profit": gross,
        "other_income_total": o_inc, "other_expense_total": o_exp, "net_profit": net, "sales": sales,
        "gross_margin": (gross * 100 / t_inc).quantize(Decimal("0.1")) if t_inc else None,
        "net_margin": (net * 100 / t_inc).quantize(Decimal("0.1")) if t_inc else None,
        "date_from": date_from, "date_to": date_to,
    }


def previous_year_range(date_from, date_to):
    """The same days one year earlier (for the current-versus-last-year view)."""
    def back(d):
        try:
            return d.replace(year=d.year - 1)
        except ValueError:      # 29 Feb
            return d.replace(year=d.year - 1, day=28)
    return back(date_from), back(date_to)


def compare_profit_and_loss(company, *, user, factory=None, date_from, date_to):
    """Two periods side by side: {'now': pl, 'before': pl, 'lines': [(section, ledger, now, before)]}."""
    now = profit_and_loss(company, user=user, factory=factory, date_from=date_from, date_to=date_to)
    f2, t2 = previous_year_range(date_from, date_to)
    before = profit_and_loss(company, user=user, factory=factory, date_from=f2, date_to=t2)
    lines = []
    for key, label in (("income", "Sales and direct income"), ("expense", "Purchases and direct expenses"),
                       ("other_income", "Indirect income"), ("other_expense", "Indirect expenses")):
        merged = {}
        for r in now[key]:
            merged[r["ledger_id"]] = [r["ledger"], r["amount"], ZERO]
        for r in before[key]:
            merged.setdefault(r["ledger_id"], [r["ledger"], ZERO, ZERO])[2] = r["amount"]
        lines.append({"section": label, "rows": sorted(merged.values())})
    return {"now": now, "before": before, "lines": lines, "before_from": f2, "before_to": t2}


# ---------------------------------------------------------------- balance sheet (ACC-19)

def balance_sheet(company, *, user, factory=None, as_of):
    """Assets against liabilities as at a date. The profit of earlier financial years and of the current one are shown
    as their own lines, so the sheet balances without any closing entry."""
    rows = _balances(company, user, factory, None, as_of, statement="bs")
    assets, liabilities = [], []
    for lid, name, group, root, nature, d, c in rows:
        net = d - c
        if not net:
            continue
        if nature == "asset":
            assets.append({"ledger_id": lid, "ledger": name, "group": group, "root": root, "amount": net})
        else:
            liabilities.append({"ledger_id": lid, "ledger": name, "group": group, "root": root, "amount": -net})
    fy = FinancialYear.objects.filter(company=company, start_date__lte=as_of, end_date__gte=as_of).first()
    start = fy.start_date if fy else None
    pl_all = _balances(company, user, factory, None, as_of, statement="pl")
    pl_current = _balances(company, user, factory, start, as_of, statement="pl") if start else pl_all
    def net(rows_):
        return sum((c - d for _, _, _, _, _, d, c in rows_), ZERO)
    current, total_pl = net(pl_current), net(pl_all)
    prior = total_pl - current
    assets_total = sum((r["amount"] for r in assets), ZERO)
    liab_total = sum((r["amount"] for r in liabilities), ZERO) + prior + current
    return {
        "assets": assets, "liabilities": liabilities, "assets_total": assets_total, "liabilities_total": liab_total,
        "prior_profit": prior, "current_profit": current, "tallies": assets_total == liab_total,
        "as_of": as_of, "financial_year": fy,
    }


# ---------------------------------------------------------------- ageing (ACC-06)

BUCKETS = [("Not due", None, 0), ("1-30", 1, 30), ("31-60", 31, 60), ("61-90", 61, 90), ("91-180", 91, 180),
           ("181-365", 181, 365), ("Over a year", 366, None)]


def _bucket(days_overdue):
    for label, lo, hi in BUCKETS:
        if lo is None:
            if days_overdue <= 0:
                return label
        elif days_overdue >= lo and (hi is None or days_overdue <= hi):
            return label
    return BUCKETS[-1][0]


def ageing(company, *, user, kind="debtors", factory=None, as_of=None):
    """Open bills of every party ledger under Sundry Debtors (or Creditors), by days past the due date.

    Bills are tracked by their 'new' allocation; settlements reduce them; advances and on-account amounts are shown apart,
    so a customer's credit is not hidden inside an old bill."""
    as_of = as_of or date.today()
    group_name = "Sundry Debtors" if kind == "debtors" else "Sundry Creditors"
    groups = {g.pk: g for g in AccountGroup.objects.filter(company=company)}
    wanted = {pk for pk, g in groups.items() if g.name == group_name}
    changed = True
    while changed:
        changed = False
        for pk, g in groups.items():
            if g.parent_id in wanted and pk not in wanted:
                wanted.add(pk)
                changed = True
    allocs = BillAllocation.objects.filter(line__in=posted_lines(user, factory, as_of), line__ledger__group_id__in=wanted
                                           ).select_related("line__voucher", "line__ledger")
    sign = 1 if kind == "debtors" else -1            # open amount, positive = owed to us (debtors) or by us (creditors)
    bills, parties = {}, {}
    for a in allocs:
        ledger = a.line.ledger
        p = parties.setdefault(ledger.pk, {"ledger": ledger, "buckets": {b[0]: ZERO for b in BUCKETS}, "total": ZERO,
                                           "unadjusted": ZERO, "bills": []})
        signed = (a.amount if a.line.debit else -a.amount) * sign
        if a.ref_type in ("new", "against"):
            b = bills.setdefault((ledger.pk, a.reference), {"date": None, "due": None, "amount": ZERO, "ledger": ledger, "ref": a.reference})
            b["amount"] += signed
            if a.ref_type == "new":
                b["date"] = a.line.voucher.date
                b["due"] = a.due_date or a.line.voucher.date
        else:
            p["unadjusted"] += signed
    for (lid, ref), b in bills.items():
        if b["amount"] == 0:
            continue
        due = b["due"] or as_of
        days = (as_of - due).days
        p = parties[lid]
        label = _bucket(days)
        p["buckets"][label] += b["amount"]
        p["total"] += b["amount"]
        p["bills"].append({"reference": ref, "date": b["date"], "due": b["due"], "amount": b["amount"], "days": max(days, 0), "bucket": label})
    out = [p for p in parties.values() if p["total"] or p["unadjusted"]]
    out.sort(key=lambda p: -p["total"])
    totals = {label: sum((p["buckets"][label] for p in out), ZERO) for label, _, _ in BUCKETS}
    return {"parties": out, "totals": totals, "total": sum((p["total"] for p in out), ZERO),
            "unadjusted": sum((p["unadjusted"] for p in out), ZERO), "buckets": [b[0] for b in BUCKETS], "kind": kind, "as_of": as_of}
