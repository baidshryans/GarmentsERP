"""Low-stock alerts (E6.3) and the daily fabricator summary (E8.8), as plain desktop features."""
from datetime import date, datetime, timedelta, timezone as dt_tz
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.models import Location, Role
from inventory.models import ReorderLevel, StockAlert
from inventory.services import alerts
from inventory.services.opening import OpeningItem, post_opening_stock
from jobwork.models import DailySummary, QcResult
from jobwork.services import rates, summary
from masters.models import Material, Unit
from tests import sales_helpers as sh
from tests.conftest import make_user
from tests.prod_helpers import DAY, build, cut, fabricator, step
from tests.test_jobwork import issue, qc, receive
from tests.test_sales import quick_invoice

D = Decimal


def login(user):
    c = Client()
    c.force_login(user)
    return c


def user_with(role, name, factory):
    u = make_user(name)
    u.roles.add(Role.objects.get(name=role))
    u.allowed_factories.add(factory)
    return u


@pytest.fixture
def godown(factory):
    return Location.objects.get(factory=factory, name="Main Godown")


@pytest.fixture
def zipper(db):
    return Material.objects.create(code="ZIP-9", name="Zipper", kind="trim", unit=Unit.objects.get(code="PCS"))


def stock_zippers(company, factory, godown, owner, qty, day=DAY):
    post_opening_stock(company=company, factory=factory, location=godown, user=owner, date=day,
                       entries=[OpeningItem(Material.objects.get(code="ZIP-9"), D(qty), D("2"))])


# ---------------------------------------------------------------- E6.3 low-stock alerts

@pytest.mark.raw_stock
def test_one_alert_per_crossing_and_it_closes_when_stock_recovers(company, factory, godown, owner, zipper):
    stock_zippers(company, factory, godown, owner, "400")
    alerts.set_level(item=zipper, factory=factory, min_qty=D("500"), reorder_qty=D("1000"), max_qty=D("2000"), user=owner)
    first = alerts.check_low_stock(company)
    assert [(a.item, a.qty_at_alert, a.min_qty, a.reorder_qty) for a in first] == [(zipper, D("400"), D("500"), D("1000"))]
    assert alerts.check_low_stock(company) == [] and alerts.check_low_stock(company) == []        # not again and again
    assert StockAlert.objects.count() == 1 and StockAlert.objects.get().is_open
    stock_zippers(company, factory, godown, owner, "300", day=DAY + timedelta(days=1))              # 700: back above the minimum
    assert alerts.check_low_stock(company) == []
    assert StockAlert.objects.get().cleared_at is not None
    from inventory.services import stock

    stock.post_movement(factory=factory, location=godown, item=zipper, qty=D("-400"), movement_type="issue", date=DAY, user=owner)
    again = alerts.check_low_stock(company)                                                         # falls through it again: a new alert
    assert len(again) == 1 and again[0].qty_at_alert == D("300") and StockAlert.objects.count() == 2


def test_stock_exactly_at_the_minimum_is_not_below_it_and_zero_levels_never_alert(company, factory, godown, owner, zipper):
    stock_zippers(company, factory, godown, owner, "500")
    alerts.set_level(item=zipper, factory=factory, min_qty=D("500"), reorder_qty=D("0"), max_qty=D("0"), user=owner)
    assert alerts.check_low_stock(company) == []
    alerts.set_level(item=zipper, factory=factory, min_qty=D("0"), reorder_qty=D("0"), max_qty=D("0"), user=owner)
    assert alerts.check_low_stock(company) == [] and ReorderLevel.objects.count() == 1             # updated, not duplicated


@pytest.mark.raw_stock
def test_stock_on_the_cutting_floor_or_with_fabricators_is_not_counted(company, factory, godown, owner, zipper):
    from inventory.services import stock

    stock_zippers(company, factory, godown, owner, "1000")
    floor = Location.objects.get(factory=factory, name="Cutting Floor")
    stock.post_movement(factory=factory, location=godown, item=zipper, qty=D("-600"), movement_type="transfer_out", date=DAY, user=owner)
    stock.post_movement(factory=factory, location=floor, item=zipper, qty=D("600"), rate=D("2"), movement_type="transfer_in", date=DAY, user=owner)
    level = alerts.set_level(item=zipper, factory=factory, min_qty=D("500"), reorder_qty=D("0"), max_qty=D("0"), user=owner)
    assert alerts.stock_of(level) == D("400")                                                      # the godown only
    assert len(alerts.check_low_stock(company)) == 1


def test_a_style_level_counts_finished_pieces_and_a_level_for_all_factories_counts_them_together(company, factory, owner):
    ns = sh.build(company, factory, owner)                                                          # 8 SKUs x 100 = 800 pieces
    level = alerts.set_level(item=ns.style, factory=None, min_qty=D("700"), reorder_qty=D("500"), max_qty=D("0"), user=owner)
    assert alerts.stock_of(level) == D("800") and alerts.check_low_stock(company) == []
    quick_invoice(ns, qty="60", rate="500")
    quick_invoice(ns, qty="60", rate="500", color="Navy")
    assert alerts.stock_of(level) == D("680")
    raised = alerts.check_low_stock(company)
    assert len(raised) == 1 and raised[0].factory is None and raised[0].style == ns.style


def test_removing_a_level_closes_its_open_alert(company, factory, godown, owner, zipper):
    stock_zippers(company, factory, godown, owner, "10")
    level = alerts.set_level(item=zipper, factory=factory, min_qty=D("500"), reorder_qty=D("0"), max_qty=D("0"), user=owner)
    alerts.check_low_stock(company)
    alerts.delete_level(level, user=owner)
    alerts.check_low_stock(company)
    assert StockAlert.objects.get().cleared_at is not None and ReorderLevel.objects.count() == 0


def test_level_rules(company, factory, factory2, owner, zipper, accountant):
    set_ = lambda **kw: alerts.set_level(item=zipper, user=owner, **{"factory": factory, "min_qty": D("5"), "reorder_qty": D("0"),
                                                                       "max_qty": D("0"), **kw})
    with pytest.raises(BusinessRuleError, match="Decimal"):
        set_(min_qty=5.5)
    with pytest.raises(BusinessRuleError, match="negative"):
        set_(reorder_qty=D("-1"))
    with pytest.raises(BusinessRuleError, match="maximum cannot be below"):
        set_(max_qty=D("3"))
    with pytest.raises(BusinessRuleError, match="material or a style"):
        alerts.set_level(item=factory, factory=factory, min_qty=D("1"), reorder_qty=D("0"), max_qty=D("0"), user=owner)
    with pytest.raises(FactoryNotAllowed):
        alerts.set_level(item=zipper, factory=factory2, min_qty=D("1"), reorder_qty=D("0"), max_qty=D("0"), user=accountant)
    with pytest.raises(BusinessRuleError, match="every factory"):
        alerts.set_level(item=zipper, factory=None, min_qty=D("1"), reorder_qty=D("0"), max_qty=D("0"), user=accountant)


def test_low_stock_screens_roles_scoping_and_the_home_tile(company, factory, factory2, godown, owner, zipper):
    stock_zippers(company, factory, godown, owner, "100")
    oc = login(owner)
    r = oc.post(reverse("reorder_levels"), {"item": f"m:{zipper.pk}", "factory": factory.pk, "min_qty": "500", "reorder_qty": "1000", "max_qty": ""})
    assert r.status_code == 302 and ReorderLevel.objects.get().min_qty == D("500")
    page = oc.get(reverse("reorder_levels")).content.decode()
    assert "Zipper" in page and "Below minimum" in page and "100" in page
    bad = oc.post(reverse("reorder_levels"), {"item": "", "factory": factory.pk, "min_qty": "5"})
    assert bad.status_code == 200 and "Choose a material or a style" in bad.content.decode()
    r = oc.post(reverse("stock_alerts"), {"action": "check"}, follow=True)
    assert "1 new alert" in r.content.decode()
    r = oc.post(reverse("stock_alerts"), {"action": "check"}, follow=True)
    assert "Nothing new" in r.content.decode()
    assert "Zipper" in oc.get(reverse("stock_alerts")).content.decode()
    home = oc.get(reverse("home")).content.decode()
    assert "Low stock" in home and reverse("stock_alerts") in home
    alert = StockAlert.objects.get()
    oc.post(reverse("stock_alerts"), {"action": "ack", "alert": alert.pk})
    alert.refresh_from_db()
    assert alert.acknowledged_by == owner and "Seen by owner" in oc.get(reverse("stock_alerts")).content.decode()
    # roles: the purchase officer sees alerts but cannot change anything; a stranger in another factory sees none
    officer = login(user_with("Purchase Officer", "buyer", factory))
    assert officer.get(reverse("stock_alerts")).status_code == 200 and "Zipper" in officer.get(reverse("stock_alerts")).content.decode()
    assert officer.post(reverse("stock_alerts"), {"action": "check"}).status_code == 403
    assert officer.post(reverse("reorder_levels"), {"item": f"m:{zipper.pk}", "factory": factory.pk, "min_qty": "1"}).status_code == 403
    stranger = login(user_with("Store Keeper", "keeper2", factory2))
    assert "Zipper" not in stranger.get(reverse("stock_alerts")).content.decode()
    assert stranger.post(reverse("stock_alerts"), {"action": "ack", "alert": alert.pk}).status_code == 404
    assert login(make_user("nobody")).get(reverse("stock_alerts")).status_code == 403


def test_the_check_low_stock_command_reports_new_alerts(company, factory, godown, owner, zipper):
    stock_zippers(company, factory, godown, owner, "5")
    alerts.set_level(item=zipper, factory=factory, min_qty=D("50"), reorder_qty=D("0"), max_qty=D("0"), user=owner)
    out = StringIO()
    call_command("check_low_stock", stdout=out)
    assert "LOW Zipper (ZIP-9) at LDH1: 5 (minimum 50)" in out.getvalue() and "1 new alert." in out.getvalue()
    out = StringIO()
    call_command("check_low_stock", stdout=out)
    assert "0 new alerts." in out.getvalue()


# ---------------------------------------------------------------- E8.8 daily summary

@pytest.fixture
def ns(company, factory, owner):
    ns = build(company, factory, owner)
    ns.bundles = cut(ns)        # B001 S17, B002 M25, B003 M8, B004 L25, B005 L8, B006 XL17
    ns.fab = fabricator(company)
    ns.fab2 = fabricator(company, "Gupta Stitching", "9822222233")
    rates.save_rate(party=ns.fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), effective_from=date(2026, 4, 1))
    rates.save_rate(party=ns.fab2, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("24"), effective_from=date(2026, 4, 1))
    return ns


def at_5pm(day):
    return datetime(day.year, day.month, day.day, 17, 0, tzinfo=dt_tz.utc)


def test_the_summary_shows_each_fabricators_day_and_is_rebuilt_not_doubled(ns, factory):
    ch1 = issue(ns, ns.fab, ns.bundles[:3], expected_date=DAY - timedelta(days=1))    # 17 + 25 + 8 = 50 pieces, already late
    ch2 = issue(ns, ns.fab2, ns.bundles[3:5], expected_date=DAY + timedelta(days=5), confirm_second_fabricator=True)  # 25 + 8 = 33 pieces
    rec = receive(ns, ch1, {ch1.bundles.get(bundle=ns.bundles[0]): 17, ch1.bundles.get(bundle=ns.bundles[1]): 20})
    qc(ns, rec.lines.get(challan_bundle__bundle=ns.bundles[0]), accepted=15, rejected=2, reject_reason="Stitching fault")
    QcResult.objects.update(checked_at=at_5pm(DAY))
    s = summary.build_summary(factory, DAY)
    by = {r.party.name: r for r in s.rows.select_related("party")}
    a, b = by["Sharma Stitching"], by["Gupta Stitching"]
    assert (a.issued_bundles, a.issued_pcs, a.received_pcs, a.accepted_pcs) == (3, 50, 37, 15)
    assert a.earnings == D("375.00")                                              # 15 accepted x 25
    assert a.pending_pcs == 8 and a.overdue_pcs == 8     # only the M8 bundle is still out (the 5 pieces not returned are a shortage); due yesterday
    assert (b.issued_bundles, b.issued_pcs, b.received_pcs, b.accepted_pcs, b.pending_pcs, b.overdue_pcs) == (2, 33, 0, 0, 33, 0)
    assert b.earnings == D("0.00")
    assert summary.totals(s)["issued_pcs"] == 83 and summary.totals(s)["earnings"] == D("375.00")
    again = summary.build_summary(factory, DAY)                                   # building again replaces the day
    assert again.pk == s.pk and DailySummary.objects.count() == 1 and again.rows.count() == 2
    assert "Sharma Stitching: issued 50 pcs in 3 bundles, received 37, accepted 15, pending 8, overdue 8, earned Rs 375.00" in summary.as_text(again)
    quiet = summary.build_summary(factory, DAY + timedelta(days=3))               # a later day: nothing issued, the rest still pending
    rows = {r.party.name: r for r in quiet.rows.select_related("party")}
    assert rows["Sharma Stitching"].issued_pcs == 0 and rows["Sharma Stitching"].pending_pcs == 8
    assert rows["Gupta Stitching"].pending_pcs == 33 and rows["Gupta Stitching"].overdue_pcs == 0     # due on DAY+5: not late yet
    late = summary.build_summary(factory, DAY + timedelta(days=6))
    assert {r.party.name: r.overdue_pcs for r in late.rows.select_related("party")}["Gupta Stitching"] == 33   # now it is
    assert ch2.expected_date == DAY + timedelta(days=5)


def test_a_day_with_nothing_makes_an_empty_summary_and_the_command_builds_every_factory(ns, factory, factory2):
    out = StringIO()
    call_command("daily_summary", "--date", "2026-06-20", stdout=out)
    assert DailySummary.objects.count() == 2 and "Nothing issued, received or pending." in out.getvalue()
    assert "Summary built for 2026-06-20." in out.getvalue()
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("daily_summary", "--date", "20-06-2026")


def test_summary_scoping_screen_and_permissions(ns, company, factory, factory2, owner):
    issue(ns, ns.fab, ns.bundles[:1])
    oc = login(owner)
    oc.post(reverse("factory_switch"), {"factory": factory2.pk})
    oc.post(reverse("daily_summary"), {"date": DAY.isoformat()})
    assert DailySummary.objects.filter(date=DAY).count() == 1                      # only the active factory is built
    oc.post(reverse("factory_switch"), {"factory": "all"})
    r = oc.post(reverse("daily_summary"), {"date": DAY.isoformat()}, follow=True)
    html = r.content.decode()
    assert "Summary built for 15 Jun 2026" in html and "Sharma Stitching" in html and "Message text" in html
    assert DailySummary.objects.filter(date=DAY).count() == 2                      # all mode: one per factory the owner may see
    assert "No summary for this day yet" in oc.get(reverse("daily_summary"), {"date": "2026-07-01"}).content.decode()
    # an accountant (factory 1 only, view only) reads it but cannot build; a user of factory 2 sees only factory 2
    acct = user_with("Accountant", "acct2", factory)
    ac = login(acct)
    assert "Sharma Stitching" in ac.get(reverse("daily_summary"), {"date": DAY.isoformat()}).content.decode()
    assert ac.post(reverse("daily_summary"), {"date": DAY.isoformat()}).status_code == 403
    other = login(user_with("Production Supervisor", "sup2", factory2))
    page = other.get(reverse("daily_summary"), {"date": DAY.isoformat()}).content.decode()
    assert "Sharma Stitching" not in page and "LDH2" in page and "No fabricator activity" in page and "LDH1" not in page
    with pytest.raises(FactoryNotAllowed):
        summary.build_summary(factory, DAY, user=user_with("Production Supervisor", "sup3", factory2))
    assert login(make_user("nobody2")).get(reverse("daily_summary")).status_code == 403
