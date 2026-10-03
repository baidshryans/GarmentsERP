"""Hand-entered sales, purchase, debit note and credit note vouchers with optional template tax (E9.2, E9.4), and the
link from a voucher back to its source document (E9.1)."""
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError
from ledger.exceptions import PostingError
from ledger.models import Ledger
from ledger.selectors import ledger_balance, outstanding_bills
from ledger.services.party_voucher import PartyRow, post_party_voucher
from masters.services import parties
from tax.models import TaxTemplate
from tests import sales_helpers as sh
from tests.conftest import make_user
from tests.test_sales import quick_invoice

D = Decimal
DAY = date(2026, 6, 15)
GST12 = "GST 12% intra-state (CGST + SGST)"


def led(company, key):
    return Ledger.objects.get(company=company, system_key=key)


def bal(company, key):
    return ledger_balance(led(company, key))


def tpl(name):
    return TaxTemplate.objects.get(name=name)


@pytest.fixture
def vendor(company):
    return parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True, credit_days=30)


@pytest.fixture
def customer(company):
    return parties.create_party(company=company, name="Retail Rani", mobile="9844444444", is_customer=True)


def rows(company, key, amount):
    return [PartyRow(ledger=str(led(company, key).pk), amount=amount)]


def purchase(company, factory, owner, vendor, **kw):
    args = dict(company=company, factory=factory, vtype="purchase", on_date=DAY, party=vendor.payable_ledger.pk, user=owner,
                rows=rows(company, "purchases_fabric", "10000.00"), reference="BILL-1")
    args.update(kw)
    return post_party_voucher(**args)


def test_a_purchase_without_a_template_posts_no_tax(company, factory, owner, vendor):
    v = purchase(company, factory, owner, vendor)
    assert v.voucher_type == "purchase" and v.vendor_invoice_no == "BILL-1" and v.total == D("10000.00")
    assert bal(company, "purchases_fabric") == D("10000.00") and ledger_balance(vendor.payable_ledger) == D("-10000.00")
    assert all(bal(company, k) == 0 for k in ("cgst_input", "sgst_input", "igst_input", "tds_payable"))
    assert outstanding_bills(vendor.payable_ledger)["bills"] == {"BILL-1": D("-10000.00")}


def test_purchase_with_gst_and_tds_templates_works_both_out_independently(company, factory, owner, vendor):
    v = purchase(company, factory, owner, vendor, gst_template=tpl(GST12), tax_template=tpl("TDS 194C - others (2%)"))
    assert bal(company, "cgst_input") == D("600.00") and bal(company, "sgst_input") == D("600.00") and bal(company, "tds_payable") == D("-200.00")
    assert ledger_balance(vendor.payable_ledger) == D("-11000.00")                         # 10,000 + 1,200 GST - 200 TDS
    assert v.total == D("11200.00")                                                         # debits: 10,000 + 1,200
    only_tds = purchase(company, factory, owner, vendor, reference="BILL-2", tax_template=tpl("TDS 194C - others (2%)"))
    assert only_tds.total == D("10000.00") and ledger_balance(vendor.payable_ledger) == D("-11000.00") + D("-9800.00")


def test_reverse_charge_credits_the_rcm_ledger_and_not_the_vendor(company, factory, owner, vendor):
    purchase(company, factory, owner, vendor, gst_template=tpl("GST 12% intra-state, reverse charge"))
    assert bal(company, "cgst_input") == D("600.00") and bal(company, "cgst_rcm") == D("-600.00")
    assert ledger_balance(vendor.payable_ledger) == D("-10000.00")


def test_a_changed_tax_amount_needs_a_reason_and_is_used(company, factory, owner, vendor):
    with pytest.raises(BusinessRuleError, match="reason"):
        purchase(company, factory, owner, vendor, gst_template=tpl(GST12), overrides={"cgst": (D("590.00"), "")})
    purchase(company, factory, owner, vendor, gst_template=tpl(GST12), overrides={"cgst": (D("590.00"), "Vendor rounded down")})
    assert bal(company, "cgst_input") == D("590.00") and ledger_balance(vendor.payable_ledger) == D("-11190.00")


def test_a_sale_by_hand_carries_gst_and_tcs_only_when_chosen(company, factory, owner, customer):
    v = post_party_voucher(company=company, factory=factory, vtype="sales", on_date=DAY, party=customer.customer_ledger.pk, user=owner,
                           rows=rows(company, "sales_stock", "5000.00"), reference="S-1", gst_template=tpl("GST 5% inter-state (IGST)"))
    assert v.voucher_type == "sales" and bal(company, "sales_stock") == D("-5000.00") and bal(company, "igst_output") == D("-250.00")
    assert ledger_balance(customer.customer_ledger) == D("5250.00")
    plain = post_party_voucher(company=company, factory=factory, vtype="sales", on_date=DAY, party=customer.customer_ledger.pk, user=owner,
                               rows=rows(company, "sales_stock", "1000.00"), reference="S-2")
    assert plain.total == D("1000.00") and bal(company, "igst_output") == D("-250.00")


def test_debit_and_credit_notes_settle_the_bill_and_reverse_the_gst(company, factory, owner, vendor, customer):
    purchase(company, factory, owner, vendor, gst_template=tpl(GST12))                      # vendor is owed 11,200
    dn = post_party_voucher(company=company, factory=factory, vtype="debit_note", on_date=DAY, party=vendor.payable_ledger.pk, user=owner,
                            rows=rows(company, "purchase_returns", "1000.00"), reference="BILL-1", gst_template=tpl(GST12))
    assert dn.voucher_type == "debit_note" and bal(company, "purchase_returns") == D("-1000.00")
    assert bal(company, "cgst_input") == D("540.00")                                        # 600 claimed, 60 reversed
    assert outstanding_bills(vendor.payable_ledger)["bills"] == {"BILL-1": D("-10080.00")}
    post_party_voucher(company=company, factory=factory, vtype="sales", on_date=DAY, party=customer.customer_ledger.pk, user=owner,
                       rows=rows(company, "sales_stock", "2000.00"), reference="S-9", gst_template=tpl(GST12))
    cn = post_party_voucher(company=company, factory=factory, vtype="credit_note", on_date=DAY, party=customer.customer_ledger.pk, user=owner,
                            rows=rows(company, "sales_returns", "500.00"), reference="S-9", gst_template=tpl(GST12))
    assert cn.voucher_type == "credit_note" and outstanding_bills(customer.customer_ledger)["bills"] == {"S-9": D("1680.00")}
    assert bal(company, "cgst_output") == D("-90.00")                                      # 120 charged, 30 reversed


def test_what_cannot_be_entered(company, factory, owner, vendor, customer):
    ok = dict(company=company, factory=factory, on_date=DAY, user=owner)
    with pytest.raises(PostingError, match="Sundry Debtors"):
        post_party_voucher(vtype="sales", party=vendor.payable_ledger.pk, rows=rows(company, "sales_stock", "1"), reference="x", **ok)
    with pytest.raises(PostingError, match="Sundry Creditors"):
        post_party_voucher(vtype="purchase", party=customer.customer_ledger.pk, rows=rows(company, "purchases_fabric", "1"), reference="x", **ok)
    with pytest.raises(PostingError, match="Choose the party"):
        post_party_voucher(vtype="purchase", party="", rows=rows(company, "purchases_fabric", "1"), reference="x", **ok)
    with pytest.raises(PostingError, match="at least one row"):
        post_party_voucher(vtype="purchase", party=vendor.payable_ledger.pk, rows=[PartyRow()], reference="x", **ok)
    with pytest.raises(PostingError, match="bill reference"):
        post_party_voucher(vtype="purchase", party=vendor.payable_ledger.pk, rows=rows(company, "purchases_fabric", "1"), reference="", **ok)
    with pytest.raises(PostingError, match="Reverse charge applies to a purchase"):
        post_party_voucher(vtype="sales", party=customer.customer_ledger.pk, rows=rows(company, "sales_stock", "1"), reference="x",
                           gst_template=tpl("GST 5% intra-state, reverse charge"), **ok)
    with pytest.raises(PostingError, match="TDS applies to a purchase"):
        post_party_voucher(vtype="debit_note", party=vendor.payable_ledger.pk, rows=rows(company, "purchase_returns", "1"), reference="x",
                           tax_template=tpl("TDS 194C - others (2%)"), **ok)
    with pytest.raises(PostingError, match="not a TDS template"):
        post_party_voucher(vtype="purchase", party=vendor.payable_ledger.pk, rows=rows(company, "purchases_fabric", "1"), reference="x",
                           tax_template=tpl(GST12), **ok)
    with pytest.raises(PostingError, match="two decimals"):
        post_party_voucher(vtype="purchase", party=vendor.payable_ledger.pk, rows=rows(company, "purchases_fabric", "1.005"), reference="x", **ok)


def test_party_voucher_screens(company, factory, owner, vendor, customer):
    c = Client()
    c.force_login(owner)
    for name in ("voucher_sales", "voucher_purchase", "voucher_debit_note", "voucher_credit_note"):
        r = c.get(reverse(name))
        assert r.status_code == 200, name
    r = c.get(reverse("voucher_purchase"))
    assert [l.name for l in r.context["parties"]] == ["Yarn House"] and "TDS deducted" in r.content.decode()
    assert [l.name for l in c.get(reverse("voucher_sales")).context["parties"]] == ["Retail Rani"]
    r = c.post(reverse("voucher_purchase"), {
        "factory": factory.pk, "date": "2026-06-15", "party": vendor.payable_ledger.pk, "ref_type": "new", "reference": "B-77",
        "due_date": "2026-07-15", "gst_template": tpl(GST12).pk, "other_template": tpl("TDS 194C - others (2%)").pk,
        "row_ledger": [led(company, "purchases_fabric").pk], "row_amount": ["10000"], "row_narration": [""]}, follow=True)
    html = r.content.decode()
    assert "posted" in html and "CGST Input" in html and "TDS Payable" in html
    bad = c.post(reverse("voucher_purchase"), {"factory": factory.pk, "date": "2026-06-15", "party": "", "row_amount": ["5"]})
    assert bad.status_code == 200 and "Choose the party" in bad.content.decode()
    clerk = make_user("clerk4")
    from core.models import Role

    clerk.roles.add(Role.objects.get(name="Billing Clerk"))
    clerk.allowed_factories.add(factory)
    cc = Client()
    cc.force_login(clerk)
    assert cc.get(reverse("voucher_purchase")).status_code == 403


def test_a_voucher_links_back_to_the_document_that_made_it(company, factory, owner):
    from sales.models import SaleInvoice

    ns = sh.build(company, factory, owner)
    inv = quick_invoice(ns)
    c = Client()
    c.force_login(owner)
    page = c.get(reverse("voucher_detail", args=[inv.voucher.pk])).content.decode()
    assert f'href="{reverse("saleinvoice_detail", args=[inv.pk])}"' in page and inv.number in page and "Sale invoice" in page
    hand = post_party_voucher(company=company, factory=factory, vtype="sales", on_date=DAY, party=ns.local.customer_ledger.pk, user=owner,
                              rows=rows(company, "sales_stock", "10.00"), reference="Z")
    assert "Made by" not in c.get(reverse("voucher_detail", args=[hand.pk])).content.decode()
