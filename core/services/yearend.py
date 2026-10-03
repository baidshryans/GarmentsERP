"""Year-end close and reopen (E9.8, ACC-08).

Balances carry forward by themselves, because every balance is a total of posted lines and the profit of earlier years is
the total of the profit and loss ledgers before the year began (see reports.services.books). So closing a year does three
things only: checks the books are in order, makes sure the next financial year (and its number series) exists, and locks
every factory up to the last day of the year. Reopening the latest closed year lowers the lock so an audit adjustment can be
posted; the adjustment then flows into the later years' opening figures with nothing to re-run."""
from datetime import timedelta

from django.db import transaction
from django.db.models import Sum

from core.exceptions import BusinessRuleError
from core.models import Factory, FinancialYear
from core.services import periods
from core.services.numbering import create_default_series

SCREEN = "ledger.yearend"


def readiness(company, fy):
    """What stands in the way of closing, as [(ok, message)]."""
    from ledger.models import Voucher, VoucherLine

    drafts = Voucher.objects.filter(company=company, status="draft", date__range=(fy.start_date, fy.end_date)).count()
    agg = VoucherLine.objects.filter(voucher__company=company, voucher__status="posted", voucher__date__lte=fy.end_date).aggregate(
        d=Sum("debit"), c=Sum("credit"))
    tallies = round(float(agg["d"] or 0) - float(agg["c"] or 0), 2) == 0
    earlier = FinancialYear.objects.filter(company=company, end_date__lt=fy.start_date, is_closed=False).exists()
    return [
        (not earlier, "Every earlier financial year is closed." if not earlier else "An earlier financial year is still open; close it first."),
        (drafts == 0, "No draft vouchers are left in the year." if not drafts else f"{drafts} draft voucher{'s' if drafts != 1 else ''} dated in the year; post or discard them."),
        (tallies, "Debits equal credits up to the last day of the year." if tallies else "Debits and credits do not tally up to the year end."),
    ]


@transaction.atomic
def close_year(*, user, company, financial_year, reason=""):
    if not user.has_screen_perm(SCREEN, "edit"):
        raise BusinessRuleError("Only the owner can close a financial year.")
    fy = FinancialYear.objects.get(pk=financial_year.pk)
    if fy.is_closed:
        raise BusinessRuleError(f"FY {fy.label} is already closed.")
    problems = [m for ok, m in readiness(company, fy) if not ok]
    if problems:
        raise BusinessRuleError(" ".join(problems))
    nxt = FinancialYear.objects.filter(company=company, start_date=fy.end_date + timedelta(days=1)).first()
    if nxt is None:
        start = fy.end_date + timedelta(days=1)
        end = start.replace(year=start.year + 1) - timedelta(days=1)
        nxt = FinancialYear.objects.create(company=company, start_date=start, end_date=end, label=FinancialYear.label_for(start))
    for factory in Factory.objects.filter(company=company, is_active=True):
        create_default_series(factory=factory, financial_year=nxt)
    current = periods.locked_upto(company, None)
    if current is None or current < fy.end_date:
        periods.lock_period(user=user, company=company, upto=fy.end_date, reason=reason.strip() or f"Year-end close FY {fy.label}")
    fy.is_closed = True
    fy.save(update_fields=["is_closed"])
    return nxt


@transaction.atomic
def reopen_year(*, user, company, financial_year, reason):
    if not user.has_screen_perm(SCREEN, "approve"):
        raise BusinessRuleError("Only the owner can reopen a financial year.")
    if not reason or not reason.strip():
        raise BusinessRuleError("Give a reason to reopen the year (for example: audit adjustments).")
    fy = FinancialYear.objects.get(pk=financial_year.pk)
    if not fy.is_closed:
        raise BusinessRuleError(f"FY {fy.label} is not closed.")
    if FinancialYear.objects.filter(company=company, start_date__gt=fy.start_date, is_closed=True).exists():
        raise BusinessRuleError("A later year is closed; reopen the latest closed year first.")
    previous = FinancialYear.objects.filter(company=company, end_date__lt=fy.start_date, is_closed=True).order_by("-end_date").first()
    lock = periods.locked_upto(company, None)
    target = previous.end_date if previous else None
    if lock is not None and (target is None or lock > target):
        periods.unlock_period(user=user, company=company, new_upto=target, reason=f"Reopen FY {fy.label}: {reason.strip()}")
    fy.is_closed = False
    fy.save(update_fields=["is_closed"])
    return fy
