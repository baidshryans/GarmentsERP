"""GST and TDS returns support (E9.10): GSTR-1 data, GSTR-3B summary, tax register."""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from core.models import Role
from ledger.models import Ledger
from ledger.services.party_voucher import PartyRow, post_party_voucher
from masters.services import parties
from reports.services import gst
from sales.services import credit_notes
from tax.models import TaxTemplate
from tests import sales_helpers as sh
from tests.conftest import make_user
from tests.test_sales import quick_invoice

D = Decimal
DAY = sh.DAY
FROM, TO = date(2026, 4, 1), date(2027, 3, 31)


def led(company, key):
    return Ledger.objects.get(company=company, system_key=key)


def tpl(name):
    return TaxTemplate.objects.get(name=name)


@pytest.fixture
def month(company, factory, owner):
    ns = sh.build(company, factory, owner)
    sh.gst_on(company)
    quick_invoice(ns, ns.local, qty="10", rate="500")                                      # B2C, same state: 5%
    quick_invoice(ns, ns.far, qty="10", rate="500")                                        # B2B, IGST 5%
    quick_invoice(ns, ns.far, qty="20", rate="3000", size="S")                             # B2B, IGST 18%
    quick_invoice(ns, ns.local, qty="5", rate="500", color="Navy", tax_mode="none", tax_note="Export under LUT")
    first = ns.local.sale_invoices.filter(status="posted").order_by("id").first()
    credit_notes.post_credit_note(credit_notes.save_credit_note(
        invoice=first, location=ns.godown, date=DAY, user=owner, lines=[(first.lines.get(), D("4"))], reason="Return"), user=owner)
    vendor = parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True)
    post_party_voucher(company=company, factory=factory, vtype="purchase", on_date=DAY, party=vendor.payable_ledger.pk, user=owner,
                       rows=[PartyRow(ledger=str(led(company, "purchases_fabric").pk), amount="10000.00")], reference="B-1",
                       gst_template=tpl("GST 12% intra-state (CGST + SGST)"), tax_template=tpl("TDS 194C - others (2%)"))
    return ns


def r1(company, owner, factory=None):
    return gst.gstr1(company, user=owner, factory=factory, date_from=FROM, date_to=TO)


def test_gstr1_lists_b2b_b2c_credit_notes_hsn_and_waived_invoices(month, company, factory, factory2, owner):
    r = r1(company, owner)
    assert sorted((x["gstin"], x["rate"], x["taxable"], x["igst"]) for x in r["b2b"]) == [
        (sh.BUYER_GSTIN, D("5.000"), D("5000.00"), D("250.00")), (sh.BUYER_GSTIN, D("18.000"), D("60000.00"), D("10800.00"))]
    assert [(x["place"], x["rate"], x["docs"], x["taxable"], x["cgst"], x["sgst"]) for x in r["b2c"]] == [
        ("03", D("5.000"), 1, D("5000.00"), D("125.00"), D("125.00"))]
    [cdn] = r["cdn"]
    assert (cdn["registered"], cdn["taxable"], cdn["cgst"], cdn["sgst"]) == (False, D("2000.00"), D("50.00"), D("50.00"))
    hsn = {(x["hsn"], x["rate"]): x for x in r["hsn"]}
    assert hsn[("6112", D("5.00"))]["qty"] == D("16") and hsn[("6112", D("5.00"))]["taxable"] == D("8000.00")      # 10 + 10 - 4 returned
    assert hsn[("6112", D("18.00"))]["igst"] == D("10800.00")
    assert [(x["taxable"], x["note"]) for x in r["nil"]] == [(D("2500.00"), "Export under LUT")]
    assert r["totals"]["taxable"] == D("68000.00") and r["totals"]["igst"] == D("11050.00") and r["totals"]["cgst"] == D("75.00")
    assert r["docs"]["invoices"] == 4
    empty = r1(company, owner, factory2)
    assert empty["b2b"] == [] and empty["totals"]["taxable"] == 0


def test_gstr3b_comes_from_the_tax_ledgers_including_hand_entered_vouchers(month, company, factory, owner):
    r = gst.gstr3b(company, user=owner, date_from=FROM, date_to=TO)
    assert r["output"] == {"igst": D("11050.00"), "cgst": D("75.00"), "sgst": D("75.00")}
    assert r["itc"] == {"igst": D("0.00"), "cgst": D("600.00"), "sgst": D("600.00")}          # from the hand-entered purchase
    assert r["payable"] == {"igst": D("11050.00"), "cgst": D("-525.00"), "sgst": D("-525.00")}  # a negative is credit carried forward
    assert r["taxable_outward"] == D("70500.00") and r["payable_total"] == D("10000.00")
    none = gst.gstr3b(company, user=owner, date_from=date(2026, 4, 1), date_to=date(2026, 6, 1))
    assert none["output_total"] == 0 and none["itc_total"] == 0


def test_tax_register_shows_every_tax_line_with_its_party(month, company, owner):
    g = gst.tax_register(company, user=owner, date_from=FROM, date_to=TO, kind="gst")
    names = {x["ledger"] for x in g["rows"]}
    assert {"CGST Output", "SGST Output", "IGST Output", "CGST Input", "SGST Input"} <= names
    assert {x["party"] for x in g["rows"]} >= {"Punjab Traders", "Mumbai Mart", "Yarn House"}
    t = gst.tax_register(company, user=owner, date_from=FROM, date_to=TO, kind="tds")
    assert [(x["ledger"], x["party"], x["credit"]) for x in t["rows"]] == [("TDS Payable", "Yarn House", D("200.00"))] and t["net"] == D("200.00")
    assert gst.tax_register(company, user=owner, date_from=FROM, date_to=TO, kind="tcs")["rows"] == []


def test_return_screens_open_export_and_are_for_the_accountant_and_owner(month, company, factory, factory2, owner, accountant):
    c = Client()
    c.force_login(owner)
    for name in ("gstr1", "gstr3b", "tax_register"):
        assert c.get(reverse(name)).status_code == 200, name
    assert c.get(reverse("tax_register"), {"kind": "tds"}).status_code == 200
    page = c.get(reverse("gstr1")).content.decode()
    assert sh.BUYER_GSTIN in page and "HSN summary" in page and "Export under LUT" in page
    for name, title in (("gstr1", "GSTR-1 data"), ("gstr3b", "GSTR-3B summary"), ("tax_register", "GST register")):
        r = c.get(reverse(name), {"format": "xlsx"})
        assert r.status_code == 200 and load_workbook(BytesIO(r.content)).active["A1"].value == title
    ac = Client()
    ac.force_login(accountant)
    assert ac.get(reverse("gstr3b")).status_code == 200
    clerk = make_user("clerk5")
    clerk.roles.add(Role.objects.get(name="Billing Clerk"))
    clerk.allowed_factories.add(factory)
    cc = Client()
    cc.force_login(clerk)
    assert cc.get(reverse("gstr1")).status_code == 403
    other = make_user("acct3")
    other.roles.add(Role.objects.get(name="Accountant"))
    other.allowed_factories.add(factory2)
    oc = Client()
    oc.force_login(other)
    assert sh.BUYER_GSTIN not in oc.get(reverse("gstr1")).content.decode()


def test_the_screens_say_so_when_gst_is_not_on(company, factory, owner):
    c = Client()
    c.force_login(owner)
    assert "GST is not switched on" in c.get(reverse("gstr1")).content.decode()
    assert "TDS is not switched on" in c.get(reverse("tax_register"), {"kind": "tds"}).content.decode()
