"""Trial balance with Opening | Debit | Credit | Closing for a period (owner, 19 Oct 2026). Opening is everything
before the start date plus the opening entries; Debit and Credit are only the period's own activity."""
from datetime import date
from decimal import Decimal

from django.test import Client
from django.urls import reverse

from ledger.selectors import trial_balance
from ledger.services.opening import OpeningEntry, post_opening_balances
from ledger.services.posting import LineSpec, post_voucher

D = Decimal


def _row(tb, ledger):
    return next(r for r in tb["rows"] if r["ledger_id"] == ledger.pk)


def _setup(company, factory, owner, ledgers):
    post_opening_balances(company=company, factory=factory, user=owner, entries=[
        OpeningEntry(ledgers("cash"), debit=D("25000"))])   # the difference goes to Opening Balance Difference
    for day, amount in ((date(2026, 5, 10), "1000"), (date(2026, 7, 10), "300")):
        post_voucher(company=company, factory=factory, voucher_type="journal", date=day, user=owner, narration="charges",
                     lines=[LineSpec(ledger=ledgers("bank_charges"), debit=D(amount)),
                            LineSpec(ledger=ledgers("cash"), credit=D(amount))])


def test_opening_balances_sit_in_the_opening_column(company, factory, owner, ledgers):
    _setup(company, factory, owner, ledgers)
    tb = trial_balance(company, user=owner, date_from=date(2026, 4, 1), as_of=date(2027, 3, 31))
    cash = _row(tb, ledgers("cash"))
    assert (cash["opening"], cash["debit"], cash["credit"], cash["closing"]) == (D("25000.00"), D("0.00"), D("1300.00"), D("23700.00"))
    assert (cash["closing_debit"], cash["closing_credit"]) == (D("23700.00"), D("0.00"))
    assert tb["tallies"] and tb["total_debit"] == tb["total_credit"] == D("1300.00")


def test_activity_before_the_start_date_moves_into_opening(company, factory, owner, ledgers):
    _setup(company, factory, owner, ledgers)
    tb = trial_balance(company, user=owner, date_from=date(2026, 7, 1), as_of=date(2026, 7, 31))
    cash, charges = _row(tb, ledgers("cash")), _row(tb, ledgers("bank_charges"))
    assert (cash["opening"], cash["credit"], cash["closing"]) == (D("24000.00"), D("300.00"), D("23700.00"))
    assert (charges["opening"], charges["debit"], charges["closing"]) == (D("1000.00"), D("300.00"), D("1300.00"))
    assert tb["tallies"]


def test_the_page_has_from_and_to_dates_and_an_opening_column(company, factory, owner, ledgers):
    _setup(company, factory, owner, ledgers)
    c = Client()
    c.force_login(owner)
    html = c.get(reverse("trial_balance"), {"date_from": "2026-04-01", "as_of": "2027-03-31"}).content.decode()
    assert 'name="date_from"' in html and 'name="as_of"' in html
    head = html[html.index("<thead>"):html.index("</thead>")]
    assert [h for h in ("Opening", "Debit", "Credit", "Closing") if h in head] == ["Opening", "Debit", "Credit", "Closing"]
    assert "25000.00" in html
