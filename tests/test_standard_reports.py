"""Standard operating reports (RPT-01, RPT-05, RPT-06) and the dashboard's day (E10.1)."""
from datetime import date, datetime, timedelta, timezone as dt_tz
from decimal import Decimal
from io import BytesIO

import pytest
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from core.models import Role
from ledger.models import Ledger
from ledger.services.posting import AllocationSpec, LineSpec, post_voucher
from masters.services import parties
from production.models import StageMovement
from purchases.models import PurchaseInvoice
from reports.services import standard
from sales.services import credit_notes
from tests import sales_helpers as sh
from tests.conftest import make_user
from tests.test_sales import quick_invoice

D = Decimal
DAY = sh.DAY
FROM, TO = date(2026, 4, 1), date(2027, 3, 31)


@pytest.fixture
def ns(company, factory, owner):
    return sh.build(company, factory, owner)


@pytest.fixture
def sold(ns, owner):
    agent = parties.create_party(company=ns.company, name="Agent Singh", mobile="9855555555", is_agent=True)
    ns.far.agent = agent
    ns.far.save()
    first = quick_invoice(ns, ns.local, qty="10", rate="500")
    quick_invoice(ns, ns.far, qty="20", rate="600", color="Navy", size="L", date_=DAY + timedelta(days=1))
    credit_notes.post_credit_note(credit_notes.save_credit_note(
        invoice=first, location=ns.godown, date=DAY + timedelta(days=2), user=owner, lines=[(first.lines.get(), D("3"))], reason="Return"), user=owner)
    return ns


def sales(owner, by, factory=None):
    return standard.sales_report(user=owner, factory=factory, date_from=FROM, date_to=TO, by=by)


def test_sales_report_by_customer_style_day_and_agent_less_returns(sold, owner, factory, factory2):
    r = sales(owner, "customer")
    assert [(x["key"], x["pieces"], x["value"], x["returned_pieces"], x["net_value"]) for x in r["rows"]] == [
        ("Mumbai Mart", D("20"), D("12000.00"), D("0"), D("12000.00")), ("Punjab Traders", D("10"), D("5000.00"), D("3"), D("3500.00"))]
    assert r["total"]["net_value"] == D("15500.00") and r["total"]["net_pieces"] == D("27")
    assert [x["key"] for x in sales(owner, "style")["rows"]] == ["TP-1 Track pant"] and sales(owner, "style")["total"]["pieces"] == D("30")
    days = sales(owner, "day")
    assert [x["key"] for x in days["rows"]] == ["2026-06-15", "2026-06-16", "2026-06-17"]
    assert days["rows"][2]["returned_value"] == D("1500.00") and days["rows"][2]["pieces"] == 0                    # the return, on its own day
    assert {x["key"]: x["net_value"] for x in sales(owner, "agent")["rows"]} == {"Agent Singh": D("12000.00"), "No agent": D("3500.00")}
    assert sales(owner, "bogus")["by"] == "customer"
    assert sales(owner, "customer", factory2)["rows"] == [] and sales(owner, "customer", factory)["total"]["value"] == D("17000.00")
    assert standard.sales_report(user=owner, date_from=DAY + timedelta(days=5), date_to=TO)["rows"] == []


def test_purchase_report_by_vendor_and_month(ns, company, factory, owner):
    v1 = parties.create_party(company=company, name="Yarn House", mobile="9833333333", is_vendor=True)
    v2 = parties.create_party(company=company, name="Zip Co", mobile="9833333344", is_vendor=True)
    for vendor, no, on, sub, gst in ((v1, "A1", DAY, "10000.00", "1200.00"), (v1, "A2", date(2026, 7, 5), "5000.00", "0.00"), (v2, "B1", DAY, "2000.00", "100.00")):
        PurchaseInvoice.objects.create(company=company, factory=factory, vendor=vendor, vendor_invoice_no=no, vendor_invoice_date=on, date=on,
                                       status="posted", subtotal=D(sub), gst_total=D(gst), payable=D(sub) + D(gst), created_by=owner)
    r = standard.purchase_report(user=owner, date_from=FROM, date_to=TO)
    assert [(x["key"], x["bills"], x["value"], x["gst"], x["payable"]) for x in r["rows"]] == [
        ("Yarn House", 2, D("15000.00"), D("1200.00"), D("16200.00")), ("Zip Co", 1, D("2000.00"), D("100.00"), D("2100.00"))]
    m = standard.purchase_report(user=owner, date_from=FROM, date_to=TO, by="month")
    assert [(x["key"], x["bills"]) for x in m["rows"]] == [("2026-06", 2), ("2026-07", 1)] and m["total"]["value"] == D("17000.00")
    assert standard.purchase_report(user=owner, date_from=FROM, date_to=TO)["total"]["variances"] == 0


def test_finished_stock_shows_age_and_slow_movers(sold, owner, factory2):
    r = standard.finished_stock(user=owner, today=DAY + timedelta(days=90), slow_days=60)
    by = {str(x["sku"]): x for x in r["rows"]}
    sold_sku = by["TP-1/Black/M"]
    assert sold_sku["qty"] == D("93") and sold_sku["last_out"] == DAY and sold_sku["age"] == 88      # the 3 returned pieces came back on DAY + 2
    assert sold_sku["slow"] is True                                                         # 90 days since the last sale
    assert by["TP-1/Black/S"]["last_out"] is None and by["TP-1/Black/S"]["slow"] is True    # never sold, old stock
    fresh = standard.finished_stock(user=owner, today=DAY + timedelta(days=2), slow_days=60)
    assert {str(x["sku"]) for x in fresh["rows"] if x["slow"]} == {str(x["sku"]) for x in fresh["rows"] if x["last_out"] is None}   # only never-sold, old stock
    assert r["pieces"] == D("800") - D("30") + D("3") and standard.finished_stock(user=owner, factory=factory2)["rows"] == []


def test_the_dashboards_day(sold, ns, company, factory, owner):
    cash = Ledger.objects.get(company=company, system_key="cash")
    inv = ns.local.sale_invoices.first()
    post_voucher(company=company, factory=factory, voucher_type="receipt", date=DAY, user=owner, lines=[
        LineSpec(ledger=cash, debit=D("1000.00")),
        LineSpec(ledger=ns.local.customer_ledger, credit=D("1000.00"), allocations=(AllocationSpec("against", D("1000.00"), inv.number),))])
    t = standard.today_figures(owner, DAY)
    assert t["sales_today"] == D("5000.00") and t["invoices_today"] == 1 and t["collections_today"] == D("1000.00")
    assert t["cut_today"] == 0 and t["packed_today"] == 0
    assert standard.today_figures(owner, DAY + timedelta(days=1))["sales_today"] == D("12000.00")


def test_cut_and_packed_today_come_from_production(company, factory, owner):
    from production.services import bundles as bundle_service
    from tests.prod_helpers import build, cut
    from tests.test_production import finish_route

    ns = build(company, factory, owner)
    bundles = finish_route(ns)
    bundle_service.pack_bundles(bundles=bundles, user=owner, date=DAY)
    StageMovement.objects.update(at=datetime(2026, 6, 15, 12, 0, tzinfo=dt_tz.utc))
    t = standard.today_figures(owner, DAY)
    assert t["cut_today"] == 100 and t["packed_today"] == 100


def test_report_screens_export_scope_and_the_home_tiles(sold, ns, company, factory, factory2, owner):
    c = Client()
    c.force_login(owner)
    for name in ("sales_report", "purchase_report", "finished_stock"):
        assert c.get(reverse(name)).status_code == 200, name
    assert "Mumbai Mart" in c.get(reverse("sales_report"), {"by": "customer"}).content.decode()
    assert "Agent Singh" in c.get(reverse("sales_report"), {"by": "agent"}).content.decode()
    assert "Slow" in c.get(reverse("finished_stock"), {"slow": "1"}).content.decode()
    for name, args, title in (("sales_report", {"by": "style"}, "Sales"), ("purchase_report", {}, "Purchases"), ("finished_stock", {}, "Finished stock")):
        r = c.get(reverse(name), {**args, "format": "xlsx"})
        assert r.status_code == 200 and load_workbook(BytesIO(r.content)).active["A1"].value == title
    home = c.get(reverse("home")).content.decode()
    assert "Sales today" in home and "Collections today" in home
    other = make_user("books9")
    other.roles.add(Role.objects.get(name="Accountant"))
    other.allowed_factories.add(factory2)
    oc = Client()
    oc.force_login(other)
    assert "Mumbai Mart" not in oc.get(reverse("sales_report")).content.decode()
    clerk = make_user("clerk9")
    clerk.roles.add(Role.objects.get(name="Production Supervisor"))
    clerk.allowed_factories.add(factory)
    cc = Client()
    cc.force_login(clerk)
    assert cc.get(reverse("sales_report")).status_code == 403 and cc.get(reverse("purchase_report")).status_code == 403
    assert "Sales today" not in cc.get(reverse("home")).content.decode()
