"""Delete sales and purchase documents (owner, 19 Oct 2026): newest first, each with its stock movements, journal
entries and history, so the books and stock are exactly as before it."""
from datetime import timedelta
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleError
from core.services.factories import godown_location
from inventory.models import FabricRoll
from inventory.services.journal import JournalLineSpec, post_journal
from purchases.models import Grn
from purchases.services import grn as grns
from sales.models import PackingList, SaleCreditNote, SaleInvoice
from sales.services import credit_notes, invoices
from tests import sales_helpers as h
from tests.deletion_helpers import assert_no_trace, books
from tests.test_purchases import fabric, fabric_grn, godown, trim, trim_grn, vendor  # noqa: F401  (fixtures)
from tests.test_sales import DAY, confirmed_order, pack, quick_invoice

D = Decimal


@pytest.fixture
def ns(company, factory, owner):
    return h.build(company, factory, owner)


def test_delete_a_grn_leaves_no_trace_and_frees_its_roll_numbers(company, factory, owner, vendor, godown, fabric):
    before = books(company)
    g = fabric_grn(company, factory, vendor, godown, fabric, owner)
    assert FabricRoll.objects.filter(vendor_roll_no="R1").exists()
    grns.delete_grn(g, user=owner)
    assert_no_trace("purchases.grn", g.pk)
    assert not Grn.objects.filter(pk=g.pk).exists() and books(company) == before
    assert not FabricRoll.objects.filter(vendor_roll_no__startswith="R1").exists()
    assert fabric_grn(company, factory, vendor, godown, fabric, owner).status == "posted"    # the same rolls again


def test_delete_a_grn_refused_once_its_goods_are_used(company, factory, owner, vendor, godown, trim):
    from inventory.services import stock

    g = trim_grn(company, factory, vendor, godown, trim, owner, qty="100")
    used = stock.post_movement(factory=factory, location=godown, item=trim, qty=D("-60"), movement_type="issue", date=DAY,
                               user=owner)
    with pytest.raises(BusinessRuleError):
        grns.delete_grn(g, user=owner)
    assert Grn.objects.filter(pk=g.pk).exists()
    stock.reverse_movement(used, user=owner, date=DAY)        # put the stock back so the books still tally
    grns.delete_grn(g, user=owner)
    assert not Grn.objects.filter(pk=g.pk).exists()


def test_delete_a_sale_bill_leaves_no_trace(ns, company):
    before = books(company)
    inv = quick_invoice(ns, qty="10", rate="500")
    invoices.delete_invoice(inv, user=ns.owner)
    assert_no_trace("sales.saleinvoice", inv.pk)
    assert not SaleInvoice.objects.filter(pk=inv.pk).exists() and books(company) == before


def test_delete_a_bill_with_an_irn_or_eway_bill_is_refused(ns):
    inv = quick_invoice(ns, qty="10", rate="500")
    SaleInvoice.objects.filter(pk=inv.pk).update(irn="IRN123")
    with pytest.raises(BusinessRuleError, match="This bill has an e-invoice / e-way bill. Cancel it on the portal first."):
        invoices.delete_invoice(inv, user=ns.owner)
    SaleInvoice.objects.filter(pk=inv.pk).update(irn="", eway_bill_no="EWB1")
    with pytest.raises(BusinessRuleError, match="e-way bill"):
        invoices.delete_invoice(inv, user=ns.owner)


def test_a_bill_with_a_return_waits_for_the_return_to_be_deleted(ns, company):
    before = books(company)
    inv = quick_invoice(ns, qty="10", rate="500")
    note = credit_notes.post_credit_note(credit_notes.save_credit_note(
        invoice=inv, location=ns.godown, date=DAY + timedelta(days=1), user=ns.owner,
        lines=[(inv.lines.get(), D("4"))], reason="Wrong colour"), user=ns.owner)
    with pytest.raises(BusinessRuleError, match="Delete the credit note first"):
        invoices.delete_invoice(inv, user=ns.owner)
    credit_notes.delete_credit_note(note, user=ns.owner)
    assert_no_trace("sales.salecreditnote", note.pk)
    assert not SaleCreditNote.objects.filter(pk=note.pk).exists()
    invoices.delete_invoice(inv, user=ns.owner)
    assert books(company) == before


def test_delete_packing_refused_while_invoiced(ns):
    from sales.services import packing

    order = confirmed_order(ns)
    p = pack(ns, order, [{"M": "5"}])
    inv = invoices.post_invoice(invoices.invoice_from_packing(p, user=ns.owner, date=DAY), user=ns.owner)
    with pytest.raises(BusinessRuleError):
        packing.delete_packing(p, user=ns.owner)
    invoices.delete_invoice(inv, user=ns.owner)
    packing.delete_packing(p, user=ns.owner)
    assert not PackingList.objects.filter(pk=p.pk).exists()


def test_delete_a_stock_journal_leaves_no_trace(ns, company):
    from inventory.services import journal

    before = books(company)
    j = post_journal(company=company, factory=ns.factory, location=ns.godown, date=DAY, reason="damage", user=ns.owner,
                     lines=[JournalLineSpec("out", ns.sku("Black", "M"), D("2"))])
    journal.delete_journal(j, user=ns.owner)
    assert_no_trace("inventory.stockjournal", j.pk)
    assert books(company) == before


def test_godown_location_is_where_sales_test_stock_sits(ns, factory):
    assert ns.godown == godown_location(factory)


# ---------------- a deleted GST bill leaves its number (owner, 19 Oct 2026) ----------------

def test_a_deleted_bill_leaves_a_record_of_its_number(ns, company):
    from sales.models import DeletedInvoiceNumber

    inv = quick_invoice(ns, qty="10", rate="500")
    number, day = inv.number, inv.date
    invoices.delete_invoice(inv, user=ns.owner)
    stub = DeletedInvoiceNumber.objects.get()
    assert (stub.number, stub.date, stub.factory_id) == (number, day, ns.factory.pk)
    assert not SaleInvoice.objects.filter(number=number).exists()
    nxt = quick_invoice(ns, qty="1", rate="500")
    assert nxt.number != number                               # the number is never given out again


def test_a_draft_bill_has_no_number_to_keep(ns):
    from sales.models import DeletedInvoiceNumber

    inv = quick_invoice(ns, qty="10", rate="500", post=False)
    invoices.delete_invoice(inv, user=ns.owner)
    assert not DeletedInvoiceNumber.objects.exists()


def test_deleted_numbers_show_on_the_bills_list_and_in_gstr1(ns, company):
    from django.test import Client
    from django.urls import reverse

    inv = quick_invoice(ns, qty="10", rate="500")
    number = inv.number
    invoices.delete_invoice(inv, user=ns.owner)
    c = Client()
    c.force_login(ns.owner)
    assert f"Deleted bill numbers: {number}" in c.get(reverse("saleinvoice_list")).content.decode()
    page = c.get(reverse("gstr1"), {"date_from": "2026-04-01", "date_to": "2027-03-31"}).content.decode()
    assert "1 deleted" in page and number in page
