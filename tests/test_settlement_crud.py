"""Pay / receive against an invoice, vendor invoice no., contra table, HSN slab edit and master delete."""
from decimal import Decimal

import pytest
from django.urls import reverse

from ledger.models import AccountGroup, Ledger, Voucher
from ledger.selectors import outstanding_bills
from tax.models import HSN, HsnSlab
from tests.test_voucher_entry import bank, client, post, rows, supplier  # noqa: F401  (fixtures)

D = Decimal


@pytest.fixture
def customer(company):
    return Ledger.objects.create(company=company, name="Mehta Traders", bill_wise=True,
                                 group=AccountGroup.objects.get(company=company, name="Sundry Debtors"))


def open_bill(client, factory, ledgers, supplier, ref="INV-1", amount="1000"):
    post(client, "voucher_journal", factory, vendor_invoice_no=ref, **rows(
        {"ledger": ledgers("bank_charges"), "debit": amount},
        {"ledger": supplier, "credit": amount, "ref_type": "new"}))


def test_journal_vendor_invoice_no_is_saved_and_opens_the_bill(client, company, factory, supplier, ledgers):
    open_bill(client, factory, ledgers, supplier, ref="V-55")
    v = Voucher.objects.get()
    assert v.vendor_invoice_no == "V-55"
    assert outstanding_bills(supplier)["bills"] == {"V-55": D("-1000.00")}
    assert b"V-55" in client.get(reverse("voucher_detail", args=[v.pk])).content
    assert b"V-55" in client.get(reverse("voucher_list") + "?q=V-55").content


def test_part_payments_settle_the_invoice_and_a_paid_invoice_takes_no_more(client, company, factory, bank, supplier, ledgers):
    open_bill(client, factory, ledgers, supplier)

    def pay(amount):
        return post(client, "voucher_payment", factory, account=bank.pk, **rows(
            {"ledger": supplier, "amount": amount, "ref_type": "against", "reference": "INV-1"}))

    assert pay("400").status_code == 302
    assert outstanding_bills(supplier)["bills"] == {"INV-1": D("-600.00")}
    r = pay("700")                                                    # more than is outstanding
    assert r.status_code == 200 and b"only 600.00 outstanding" in r.content
    assert pay("600").status_code == 302
    assert outstanding_bills(supplier)["bills"] == {}
    r = pay("1")                                                      # fully paid: no further payment
    assert r.status_code == 200 and b"fully settled" in r.content
    assert Voucher.objects.filter(voucher_type="payment").count() == 2


def test_two_rows_in_one_payment_cannot_together_exceed_the_invoice(client, company, factory, bank, supplier, ledgers):
    open_bill(client, factory, ledgers, supplier)
    r = post(client, "voucher_payment", factory, account=bank.pk, **rows(
        {"ledger": supplier, "amount": "600", "ref_type": "against", "reference": "INV-1"},
        {"ledger": supplier, "amount": "600", "ref_type": "against", "reference": "INV-1"}))
    assert r.status_code == 200 and b"outstanding" in r.content
    assert Voucher.objects.filter(voucher_type="payment").count() == 0


def test_cannot_pay_against_an_unknown_invoice(client, company, factory, bank, supplier):
    r = post(client, "voucher_payment", factory, account=bank.pk, **rows(
        {"ledger": supplier, "amount": "5", "ref_type": "against", "reference": "NOPE"}))
    assert r.status_code == 200 and b"fully settled or has no balance" in r.content


def test_receipt_against_a_customer_invoice(client, company, factory, bank, customer, ledgers):
    post(client, "voucher_journal", factory, **rows(
        {"ledger": customer, "debit": "500", "ref_type": "new", "reference": "SI-9"},
        {"ledger": ledgers("sales_stock"), "credit": "500"}))
    r = post(client, "voucher_receipt", factory, account=bank.pk, **rows(
        {"ledger": customer, "amount": "500", "ref_type": "against", "reference": "SI-9"}))
    assert r.status_code == 302 and outstanding_bills(customer)["bills"] == {}
    r = post(client, "voucher_receipt", factory, account=bank.pk, **rows(
        {"ledger": customer, "amount": "1", "ref_type": "against", "reference": "SI-9"}))
    assert r.status_code == 200 and not Voucher.objects.filter(voucher_type="receipt").count() == 2


def test_cancelling_a_payment_reopens_the_invoice(client, company, factory, bank, supplier, ledgers, owner):
    from ledger.services.posting import reverse_voucher

    open_bill(client, factory, ledgers, supplier)
    post(client, "voucher_payment", factory, account=bank.pk, **rows(
        {"ledger": supplier, "amount": "1000", "ref_type": "against", "reference": "INV-1"}))
    reverse_voucher(Voucher.objects.get(voucher_type="payment"), user=owner, reason="wrong bank")
    assert outstanding_bills(supplier)["bills"] == {"INV-1": D("-1000.00")}


def test_contra_table_saves_every_row(client, company, factory, bank, ledgers):
    cash = ledgers("cash")
    data = rows({"ledger": cash, "amount": "100"}, {"ledger": cash, "amount": "250"})
    data["row_to_ledger"] = [str(bank.pk), str(bank.pk)]
    r = post(client, "voucher_contra", factory, **data)
    assert r.status_code == 302
    v = Voucher.objects.get()
    assert v.lines.count() == 4 and v.total == D("350.00")


def test_a_half_filled_row_is_rejected_not_dropped(client, company, factory, bank, ledgers):
    data = rows({"ledger": ledgers("bank_charges"), "amount": "10"})
    data["row_ledger"].append("")
    data["row_amount"].append("")
    data["row_debit"].append("")
    data["row_credit"].append("")
    data["row_ref_type"].append("on_account")
    data["row_reference"].append("")
    data["row_due_date"].append("")
    data["row_narration"].append("lost note")
    r = post(client, "voucher_payment", factory, account=bank.pk, **data)
    assert r.status_code == 200 and not Voucher.objects.exists()


def test_hsn_slab_can_be_edited_and_deleted_in_place(client, company):
    hsn = HSN.objects.create(code="9999", description="Test HSN")
    slab = HsnSlab.objects.create(hsn=hsn, value_from=0, value_to=1000, gst_rate=5, effective_from="2026-04-01")
    r = client.post(reverse("hsn_slab_edit", args=[slab.pk]), {
        "value_from": "0", "value_to": "1000", "gst_rate": "12", "effective_from": "2026-04-01"})
    assert r.status_code == 302
    slab.refresh_from_db()
    assert slab.gst_rate == 12 and slab.history.count() == 2
    assert client.post(reverse("hsn_slab_delete", args=[slab.pk])).status_code == 302
    assert not HsnSlab.objects.filter(pk=slab.pk).exists()


def test_unused_master_is_deleted_and_a_used_one_is_protected(client, company, factory, ledgers):
    from masters.models import Unit

    unit = Unit.objects.create(code="ZZ", name="Test unit", kind="count")
    assert client.get(reverse("unit_delete", args=[unit.pk])).status_code == 200
    client.post(reverse("unit_delete", args=[unit.pk]))
    assert not Unit.objects.filter(pk=unit.pk).exists()

    cash = ledgers("cash")
    r = client.post(reverse("ledger_delete", args=[cash.pk]), follow=True)
    assert Ledger.objects.filter(pk=cash.pk).exists() and b"cannot be deleted" in r.content
