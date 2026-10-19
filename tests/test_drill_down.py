"""Trial balance, profit and loss and balance sheet as drill-downs (owner, 19 Oct 2026): top groups first, each
opening into its sub-groups and then its ledgers, with every level carrying its own total."""
from datetime import date
from decimal import Decimal

from django.test import Client
from django.urls import reverse

from ledger.services.opening import OpeningEntry, post_opening_balances
from ledger.services.posting import LineSpec, post_voucher
from reports.services import tree

D = Decimal


def _post(company, factory, owner, ledgers):
    post_opening_balances(company=company, factory=factory, user=owner, entries=[OpeningEntry(ledgers("cash"), debit=D("25000"))])
    post_voucher(company=company, factory=factory, voucher_type="journal", date=date(2026, 5, 10), user=owner, narration="charges",
                 lines=[LineSpec(ledger=ledgers("bank_charges"), debit=D("1000")), LineSpec(ledger=ledgers("cash"), credit=D("1000"))])


def test_ledgers_roll_up_into_their_groups_and_top_groups(company, ledgers):
    cash = ledgers("cash")
    items = [{"ledger_id": cash.pk, "ledger": "Cash", "group": "Cash-in-hand", "values": [D("24000")]}]
    rows = tree.flatten(tree.build(company, items, width=1))
    top, sub, leaf = rows[0], rows[1], rows[2]
    assert (top["name"], top["depth"], top["values"]) == ("Current Assets", 0, [D("24000")])
    assert (sub["name"], sub["depth"], sub["parent"]) == ("Cash-in-hand", 1, top["key"])
    assert (leaf["name"], leaf["kind"], leaf["depth"], leaf["parent"]) == ("Cash", "ledger", 2, sub["key"])
    assert top["has_children"] and not leaf["has_children"]


def test_a_group_with_nothing_in_it_is_left_out(company, ledgers):
    items = [{"ledger_id": ledgers("cash").pk, "ledger": "Cash", "group": "Cash-in-hand", "values": [D("1")]}]
    names = [r["name"] for r in tree.flatten(tree.build(company, items, width=1))]
    assert "Bank Accounts" not in names and "Fixed Assets" not in names


def _page(owner, name, **params):
    c = Client()
    c.force_login(owner)
    return c.get(reverse(name), params).content.decode()


def test_the_trial_balance_opens_on_its_top_groups(company, factory, owner, ledgers):
    _post(company, factory, owner, ledgers)
    html = _page(owner, "trial_balance", date_from="2026-04-01", as_of="2027-03-31")
    assert 'data-drill-key' in html and "Expand all" in html and "Collapse all" in html
    assert ">Current Assets<" in html and ">Indirect Expenses<" in html
    assert 'data-depth="2"' in html and "hidden" in html.split('data-depth="2"')[1][:200]     # ledgers start folded


def test_profit_and_loss_and_balance_sheet_drill_down(company, factory, owner, ledgers):
    _post(company, factory, owner, ledgers)
    pl = _page(owner, "profit_loss", **{"from": "2026-04-01", "to": "2027-03-31"})
    assert ">Indirect Expenses<" in pl and ">Bank Charges<" in pl and "data-drill-key" in pl
    bs = _page(owner, "balance_sheet", as_of="2027-03-31")
    assert ">Current Assets<" in bs and ">Cash-in-hand<" in bs and ">Cash<" in bs and "data-drill-key" in bs


def test_the_pages_load_the_drill_script_in_the_body_and_show_no_template_comment(company, factory, owner, ledgers):
    _post(company, factory, owner, ledgers)
    for name, params in (("trial_balance", {}), ("profit_loss", {}), ("balance_sheet", {})):
        html = _page(owner, name, **params)
        title = html[html.index("<title>"):html.index("</title>")]
        assert "<script" not in title, name
        assert "js/drill.js" in html.split("</title>")[1], name
        assert "{#" not in html and "Drill-down rows:" not in html, name
