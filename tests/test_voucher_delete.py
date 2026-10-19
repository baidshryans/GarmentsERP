"""Delete a hand-made entry (owner, 19 Oct 2026): a payment, receipt, contra or journal entered by hand is removed
completely. An entry a document made is deleted by deleting the document."""
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError
from core.services import periods
from ledger.models import Ledger, Voucher
from ledger.services import deletion, settlement
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher
from tests.deletion_helpers import books

D = Decimal
DAY = date(2026, 6, 15)


def _l(company, key):
    return Ledger.objects.get(company=company, system_key=key)


def _supplier_bill_and_payment(company, factory, owner):
    from masters.services import parties

    vendor = parties.create_party(company=company, name="Kapoor Fabrics", mobile="9811100000", is_vendor=True)
    bill = post_voucher(company=company, factory=factory, voucher_type="journal", date=DAY, user=owner, narration="Bill",
                        lines=[LineSpec(ledger=_l(company, "bank_charges"), debit=D("500")),
                               LineSpec(ledger=vendor.payable_ledger, credit=D("500"),
                                        allocations=(AllocationSpec("new", D("500"), "INV-7"),))])
    pay = post_voucher(company=company, factory=factory, voucher_type="payment", date=DAY, user=owner, narration="Paid",
                       lines=[LineSpec(ledger=vendor.payable_ledger, debit=D("500"),
                                       allocations=(AllocationSpec("against", D("500"), "INV-7"),)),
                              LineSpec(ledger=_l(company, "cash"), credit=D("500"))])
    return bill, pay


def test_deleting_a_payment_frees_the_bill_it_settled(company, factory, owner):
    bill, pay = _supplier_bill_and_payment(company, factory, owner)
    assert settlement.settled_against(bill) == [pay]
    with pytest.raises(BusinessRuleError, match=f"Payment {pay.number} is settled against this entry"):
        deletion.delete_voucher(bill, user=owner)
    deletion.delete_voucher(pay, user=owner)
    assert settlement.settled_against(bill) == []
    deletion.delete_voucher(bill, user=owner)
    assert not Voucher.objects.filter(pk__in=[bill.pk, pay.pk]).exists()


def test_deleting_a_journal_leaves_no_trace(company, factory, owner):
    before = books(company)
    v = post_voucher(company=company, factory=factory, voucher_type="journal", date=DAY, user=owner, narration="Wrong",
                     lines=[LineSpec(ledger=_l(company, "bank_charges"), debit=D("75")),
                            LineSpec(ledger=_l(company, "cash"), credit=D("75"))])
    deletion.delete_voucher(v, user=owner)
    assert books(company) == before and not Voucher.history.filter(id=v.pk).exists()


def test_an_entry_made_by_a_document_is_deleted_with_the_document(company, factory, owner):
    from tests.prod_helpers import build, cut, set_inhouse_rate

    ns = build(company, factory, owner)
    set_inhouse_rate("CUT", "2")
    cut(ns)
    v = Voucher.objects.filter(narration__startswith="Cutting in-house").get()
    with pytest.raises(BusinessRuleError, match="This entry was made by .*Delete that instead."):
        deletion.delete_voucher(v, user=owner)


def test_deleting_in_a_locked_period_is_refused(company, factory, owner):
    v = post_voucher(company=company, factory=factory, voucher_type="journal", date=DAY, user=owner, narration="x",
                     lines=[LineSpec(ledger=_l(company, "bank_charges"), debit=D("5")),
                            LineSpec(ledger=_l(company, "cash"), credit=D("5"))])
    periods.lock_period(company=company, upto=DAY, user=owner)
    with pytest.raises(BusinessRuleError, match="locked"):
        deletion.delete_voucher(v, user=owner)


def test_the_entry_page_offers_delete_for_a_hand_made_entry(company, factory, owner):
    v = post_voucher(company=company, factory=factory, voucher_type="journal", date=DAY, user=owner, narration="x",
                     lines=[LineSpec(ledger=_l(company, "bank_charges"), debit=D("5")),
                            LineSpec(ledger=_l(company, "cash"), credit=D("5"))])
    c = Client()
    c.force_login(owner)
    page = c.get(reverse("voucher_detail", args=[v.pk])).content.decode()
    assert "Delete this entry" in page and "Cancel voucher" not in page
    r = c.post(reverse("voucher_detail", args=[v.pk]), {"action": "delete"})
    assert r.status_code == 302 and not Voucher.objects.filter(pk=v.pk).exists()
