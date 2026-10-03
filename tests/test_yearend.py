"""Period locks (E9.9) and year-end close and reopen (E9.8, ACC-08)."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError, PeriodLocked
from core.models import FinancialYear, PeriodLock, Role
from core.services import periods, yearend
from ledger.models import Ledger, Voucher
from ledger.services.posting import LineSpec, create_draft, post_voucher
from reports.services import books
from tests import sales_helpers as sh
from tests.conftest import make_user
from tests.test_sales import quick_invoice

D = Decimal
DAY = sh.DAY
FY = lambda company: FinancialYear.objects.get(company=company, label="26-27")


def led(company, key):
    return Ledger.objects.get(company=company, system_key=key)


def journal(company, factory, owner, on, amount="100.00", dr="office_expenses", cr="cash"):
    return post_voucher(company=company, factory=factory, voucher_type="journal", date=on, user=owner, lines=[
        LineSpec(ledger=led(company, dr), debit=D(amount)), LineSpec(ledger=led(company, cr), credit=D(amount))])


@pytest.fixture
def ns(company, factory, owner):
    return sh.build(company, factory, owner)


def test_closing_a_year_checks_creates_the_next_year_and_locks(ns, company, factory, owner):
    quick_invoice(ns)
    fy = FY(company)
    assert all(ok for ok, _ in yearend.readiness(company, fy))
    nxt = yearend.close_year(user=owner, company=company, financial_year=fy)
    fy.refresh_from_db()
    assert fy.is_closed and nxt.label == "27-28" and (nxt.start_date, nxt.end_date) == (date(2027, 4, 1), date(2028, 3, 31))
    assert periods.locked_upto(company, factory) == date(2027, 3, 31)
    with pytest.raises(PeriodLocked):
        journal(company, factory, owner, date(2027, 3, 31))
    journal(company, factory, owner, date(2027, 4, 1))                                     # the new year is open
    from core.services.numbering import next_document_number

    assert "/27-28/" in next_document_number(factory=factory, doc_type="sale_invoice", on_date=date(2027, 5, 1))
    with pytest.raises(BusinessRuleError, match="already closed"):
        yearend.close_year(user=owner, company=company, financial_year=fy)


def test_a_year_with_draft_vouchers_or_an_open_earlier_year_will_not_close(ns, company, factory, owner):
    create_draft(company=company, factory=factory, voucher_type="journal", date=DAY, user=owner, lines=[
        LineSpec(ledger=led(company, "office_expenses"), debit=D("5.00")), LineSpec(ledger=led(company, "cash"), credit=D("5.00"))])
    with pytest.raises(BusinessRuleError, match="1 draft voucher"):
        yearend.close_year(user=owner, company=company, financial_year=FY(company))
    Voucher.objects.filter(status="draft").delete()
    nxt = yearend.close_year(user=owner, company=company, financial_year=FY(company))
    FinancialYear.objects.create(company=company, start_date=date(2028, 4, 1), end_date=date(2029, 3, 31), label="28-29")
    with pytest.raises(BusinessRuleError, match="earlier financial year is still open"):
        yearend.close_year(user=owner, company=company, financial_year=FinancialYear.objects.get(label="28-29"))
    assert nxt.label == "27-28"


def test_reopening_for_an_audit_adjustment_flows_into_the_next_year_by_itself(ns, company, factory, owner):
    quick_invoice(ns, qty="10", rate="500")                                                 # profit 2,000 in FY 26-27
    journal(company, factory, owner, DAY, "500.00")                                         # office expense: profit 1,500
    yearend.close_year(user=owner, company=company, financial_year=FY(company))
    nxt_bs = lambda: books.balance_sheet(company, user=owner, as_of=date(2027, 6, 30))
    before = nxt_bs()
    assert before["prior_profit"] == D("1500.00") and before["current_profit"] == D("0.00") and before["tallies"]
    with pytest.raises(BusinessRuleError, match="reason"):
        yearend.reopen_year(user=owner, company=company, financial_year=FY(company), reason=" ")
    yearend.reopen_year(user=owner, company=company, financial_year=FY(company), reason="Auditor: provision for audit fee")
    assert not FY(company).is_closed and periods.locked_upto(company, factory) is None
    journal(company, factory, owner, date(2027, 3, 31), "300.00")                           # the audit adjustment, in the old year
    after = nxt_bs()
    assert after["prior_profit"] == D("1200.00") and after["tallies"]                       # the new year's opening figure moved
    yearend.close_year(user=owner, company=company, financial_year=FY(company))
    assert periods.locked_upto(company, factory) == date(2027, 3, 31)


def test_only_the_latest_closed_year_reopens_and_only_the_owner_closes_or_reopens(ns, company, factory, owner, accountant):
    yearend.close_year(user=owner, company=company, financial_year=FY(company))
    nxt = FinancialYear.objects.get(label="27-28")
    yearend.close_year(user=owner, company=company, financial_year=nxt)
    with pytest.raises(BusinessRuleError, match="later year is closed"):
        yearend.reopen_year(user=owner, company=company, financial_year=FY(company), reason="x")
    with pytest.raises(BusinessRuleError, match="not closed"):
        yearend.reopen_year(user=owner, company=company, financial_year=FinancialYear.objects.create(
            company=company, start_date=date(2029, 4, 1), end_date=date(2030, 3, 31), label="29-30"), reason="x")
    with pytest.raises(BusinessRuleError, match="Only the owner"):
        yearend.reopen_year(user=accountant, company=company, financial_year=nxt, reason="x")
    yearend.reopen_year(user=owner, company=company, financial_year=nxt, reason="late audit entry")
    assert periods.locked_upto(company, factory) == date(2027, 3, 31)                      # back to the end of the earlier year


def test_an_accountant_cannot_close_a_year(ns, company, accountant):
    with pytest.raises(BusinessRuleError, match="Only the owner"):
        yearend.close_year(user=accountant, company=company, financial_year=FY(company))


def test_period_lock_screens_accountant_locks_owner_unlocks(ns, company, factory, owner, accountant):
    oc, ac = Client(), Client()
    oc.force_login(owner)
    ac.force_login(accountant)
    assert ac.get(reverse("period_locks")).status_code == 200
    r = ac.post(reverse("period_locks"), {"action": "lock", "upto": "2026-06-30", "factory": "", "reason": "GSTR-3B filed"}, follow=True)
    assert "Period locked" in r.content.decode() and PeriodLock.objects.get().locked_upto == date(2026, 6, 30)
    with pytest.raises(PeriodLocked):
        journal(company, factory, owner, date(2026, 6, 30))
    r = ac.post(reverse("period_locks"), {"action": "unlock", "new_upto": "", "reason": "oops"}, follow=True)
    assert "Only the owner can unlock" in r.content.decode() and PeriodLock.objects.count() == 1
    r = oc.post(reverse("period_locks"), {"action": "unlock", "new_upto": "", "reason": "Late bill found"}, follow=True)
    assert "Period unlocked" in r.content.decode() and PeriodLock.objects.count() == 0
    page = oc.get(reverse("period_locks")).content.decode()
    assert "GSTR-3B filed" in page and "Late bill found" in page                            # both are in the log
    bad = oc.post(reverse("period_locks"), {"action": "lock", "upto": "30/06/2026"}, follow=True)
    assert "YYYY-MM-DD" in bad.content.decode()
    assert Client().get(reverse("period_locks")).status_code == 302


def test_year_end_screen(ns, company, owner, accountant):
    oc, ac = Client(), Client()
    oc.force_login(owner)
    ac.force_login(accountant)
    page = oc.get(reverse("year_end")).content.decode()
    assert "FY 26-27" in page and "Close FY 26-27" in page and "No draft vouchers" in page
    assert "Close FY" not in ac.get(reverse("year_end")).content.decode()                  # the accountant can only look
    r = ac.post(reverse("year_end"), {"action": "close", "year": FY(company).pk}, follow=True)
    assert "Only the owner" in r.content.decode() and not FY(company).is_closed
    r = oc.post(reverse("year_end"), {"action": "close", "year": FY(company).pk, "reason": "Accounts finalised"}, follow=True)
    assert "FY 26-27 closed" in r.content.decode() and FY(company).is_closed
    page = oc.get(reverse("year_end")).content.decode()
    assert "Reopen FY 26-27" in page
    r = oc.post(reverse("year_end"), {"action": "reopen", "year": FY(company).pk, "reason": "Audit"}, follow=True)
    assert "reopened" in r.content.decode() and not FY(company).is_closed
