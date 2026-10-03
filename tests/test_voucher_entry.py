"""Manual vouchers (E9.2, E9.3): payment, receipt, contra, journal - and the chart-of-accounts forms."""
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from ledger.models import AccountGroup, BillAllocation, Ledger, Voucher
from ledger.selectors import outstanding_bills, trial_balance
from tests.conftest import IN_YEAR, make_user

D = Decimal


@pytest.fixture
def bank(company):
    return Ledger.objects.create(company=company, name="HDFC Current", group=AccountGroup.objects.get(company=company, name="Bank Accounts"))


@pytest.fixture
def supplier(company):
    return Ledger.objects.create(company=company, name="Sharma Fabrics", bill_wise=True,
                                 group=AccountGroup.objects.get(company=company, name="Sundry Creditors"))


@pytest.fixture
def client(owner):
    c = Client()
    c.force_login(owner)
    return c


def rows(*items):
    """Build the parallel row_* lists the form posts."""
    data = {k: [] for k in ("row_ledger", "row_amount", "row_debit", "row_credit", "row_ref_type", "row_reference", "row_due_date", "row_narration")}
    for it in items:
        data["row_ledger"].append(str(it["ledger"].pk))
        data["row_amount"].append(it.get("amount", ""))
        data["row_debit"].append(it.get("debit", ""))
        data["row_credit"].append(it.get("credit", ""))
        data["row_ref_type"].append(it.get("ref_type", "on_account"))
        data["row_reference"].append(it.get("reference", ""))
        data["row_due_date"].append(it.get("due_date", ""))
        data["row_narration"].append("")
    return data


def post(client, name, factory, **fields):
    body = {"factory": factory.pk, "date": IN_YEAR.isoformat(), "narration": "test", **fields}
    return client.post(reverse(name), body)


def test_entry_screens_open_with_todays_date(client, company, bank):
    for name in ("voucher_payment", "voucher_receipt", "voucher_contra", "voucher_journal"):
        r = client.get(reverse(name))
        assert r.status_code == 200 and f'value="{timezone.localdate().isoformat()}"' in r.content.decode(), name
    assert b"HDFC Current" in client.get(reverse("voucher_payment")).content


def test_payment_debits_the_expense_and_credits_the_bank(client, company, factory, bank, ledgers):
    r = post(client, "voucher_payment", factory, account=bank.pk, **rows({"ledger": ledgers("bank_charges"), "amount": "250.00"}))
    v = Voucher.objects.get()
    assert r.status_code == 302 and r["Location"] == reverse("voucher_detail", args=[v.pk])
    assert v.voucher_type == "payment" and v.number == "PAY/LDH1/26-27/0001" and v.total == D("250.00")
    by = {l.ledger.name: (l.debit, l.credit) for l in v.lines.all()}
    assert by == {"Bank Charges": (D("250.00"), D("0")), "HDFC Current": (D("0"), D("250.00"))}
    assert trial_balance(company)["tallies"]


def test_receipt_debits_the_bank_and_credits_the_party(client, company, factory, bank, ledgers):
    post(client, "voucher_receipt", factory, account=bank.pk, **rows({"ledger": ledgers("sales_stock"), "amount": "1000.00"}))
    v = Voucher.objects.get()
    assert v.voucher_type == "receipt" and v.number.startswith("REC/LDH1/")
    assert {l.ledger.name: l.debit for l in v.lines.all() if l.debit} == {"HDFC Current": D("1000.00")}


def test_contra_moves_money_between_cash_and_bank_only(client, company, factory, bank, ledgers):
    cash = ledgers("cash")
    r = post(client, "voucher_contra", factory, from_account=cash.pk, to_account=bank.pk, amount="500")
    v = Voucher.objects.get()
    assert r.status_code == 302 and v.voucher_type == "contra" and v.number.startswith("CNT/")
    assert {l.ledger.name: l.debit for l in v.lines.all() if l.debit} == {"HDFC Current": D("500.00")}
    # not a cash/bank ledger, or the same ledger twice
    for fields in ({"from_account": ledgers("bank_charges").pk, "to_account": bank.pk}, {"from_account": cash.pk, "to_account": cash.pk}):
        r = post(client, "voucher_contra", factory, amount="10", **fields)
        assert r.status_code == 200
    assert Voucher.objects.count() == 1


def test_journal_must_balance_and_nothing_is_saved_when_it_does_not(client, company, factory, ledgers):
    r = post(client, "voucher_journal", factory, **rows(
        {"ledger": ledgers("cash"), "debit": "100"}, {"ledger": ledgers("sales_stock"), "credit": "90"}))
    assert r.status_code == 200 and b"do not match" in r.content and not Voucher.objects.exists()
    r = post(client, "voucher_journal", factory, **rows(
        {"ledger": ledgers("cash"), "debit": "100"}, {"ledger": ledgers("sales_stock"), "credit": "100"}))
    assert r.status_code == 302 and Voucher.objects.get().number.startswith("JV/")


def test_row_needs_one_side_and_a_ledger(client, company, factory, ledgers):
    r = post(client, "voucher_journal", factory, **rows(
        {"ledger": ledgers("cash"), "debit": "5", "credit": "5"}, {"ledger": ledgers("sales_stock"), "credit": "5"}))
    assert r.status_code == 200 and b"either a debit or a credit" in r.content
    r = post(client, "voucher_payment", factory, account=ledgers("cash").pk)
    assert r.status_code == 200 and b"at least one row" in r.content and not Voucher.objects.exists()


def test_bill_wise_settlement_new_bill_then_payment_against_it(client, company, factory, bank, supplier, ledgers):
    post(client, "voucher_journal", factory, **rows(
        {"ledger": ledgers("bank_charges"), "debit": "800"},
        {"ledger": supplier, "credit": "800", "ref_type": "new", "reference": "INV-7"}))
    assert outstanding_bills(supplier)["bills"] == {"INV-7": D("-800.00")}
    got = client.get(reverse("ledger_bills", args=[supplier.pk])).json()
    assert got["bill_wise"] and got["bills"] == [{"reference": "INV-7", "amount": "800.00", "side": "Cr"}]

    post(client, "voucher_payment", factory, account=bank.pk, **rows(
        {"ledger": supplier, "amount": "800", "ref_type": "against", "reference": "INV-7"}))
    assert outstanding_bills(supplier)["bills"] == {}
    assert BillAllocation.objects.filter(reference="INV-7").count() == 2


def test_bill_reference_is_required_for_new_and_against(client, company, factory, bank, supplier):
    r = post(client, "voucher_payment", factory, account=bank.pk, **rows({"ledger": supplier, "amount": "50", "ref_type": "against"}))
    assert r.status_code == 200 and b"bill reference" in r.content and not Voucher.objects.exists()


def test_ledger_that_does_not_track_bills_ignores_bill_options(client, company, factory, bank, ledgers):
    post(client, "voucher_payment", factory, account=bank.pk,
         **rows({"ledger": ledgers("bank_charges"), "amount": "20", "ref_type": "against", "reference": "X"}))
    assert Voucher.objects.count() == 1 and not BillAllocation.objects.exists()


def test_no_tax_is_added_unless_the_user_adds_a_tax_ledger(client, company, factory, bank, ledgers):
    post(client, "voucher_payment", factory, account=bank.pk, **rows({"ledger": ledgers("bank_charges"), "amount": "100"}))
    names = {l.ledger.name for l in Voucher.objects.get().lines.all()}
    assert not any("GST" in n or "TDS" in n for n in names)


def test_entry_needs_create_permission_and_a_login(company, factory, bank, ledgers):
    nobody = make_user("nobody")
    c = Client()
    assert c.get(reverse("voucher_payment")).status_code == 302
    c.force_login(nobody)
    assert c.get(reverse("voucher_payment")).status_code == 403
    assert c.post(reverse("voucher_payment"), {"factory": factory.pk}).status_code == 403


def test_user_cannot_post_into_a_factory_they_may_not_use(company, factory, factory2, accountant, bank, ledgers):
    c = Client()
    c.force_login(accountant)                      # allowed LDH1 only
    r = c.post(reverse("voucher_payment"), {"factory": factory2.pk, "date": IN_YEAR.isoformat(), "account": bank.pk,
                                            **rows({"ledger": ledgers("bank_charges"), "amount": "5"})})
    assert r.status_code == 404 and not Voucher.objects.exists()


def test_accounts_menu_lists_the_entry_screens(client, company):
    html = client.get(reverse("home")).content.decode()
    for name in ("voucher_payment", "voucher_receipt", "voucher_contra", "voucher_journal"):
        assert reverse(name) in html


# ---------------- chart of accounts forms ----------------

def test_group_and_ledger_forms_are_clearly_different_pages(client, company):
    g = client.get(reverse("group_create")).content.decode()
    l = client.get(reverse("ledger_create")).content.decode()
    assert "New account group" in g and 'name="parent"' in g and 'name="group"' not in g
    assert "New ledger" in l and 'name="group"' in l and 'name="parent"' not in l


def test_parent_and_group_drop_downs_show_the_hierarchy(client, company):
    html = client.get(reverse("group_create")).content.decode()
    nbsp = "    "
    assert f"{nbsp}└ Cash-in-hand" in html          # child indented under its parent
    assert html.index("Current Assets") < html.index("Cash-in-hand")
    assert f"{nbsp}└ Cash-in-hand" in client.get(reverse("ledger_create")).content.decode()


def test_group_cannot_be_moved_under_its_own_child(client, company):
    assets = AccountGroup.objects.get(company=company, name="Current Assets")
    child = AccountGroup.objects.get(company=company, name="Cash-in-hand")
    html = client.get(reverse("group_edit", args=[assets.pk])).content.decode()
    assert f'value="{child.pk}"' not in html.split('name="parent"')[1].split("</select>")[0]
