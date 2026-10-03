"""Stock journal (E9.2): count corrections, damage, repacking and conversion, through the stock engine with one voucher."""
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.models import Location, Role
from inventory.exceptions import InsufficientStock
from inventory.models import RollBalance, StockBalance, StockJournal
from inventory.services.journal import JournalLineSpec as L, cancel_journal, post_journal
from ledger.models import Ledger
from ledger.selectors import ledger_balance
from tests import sales_helpers as sh
from tests.conftest import make_user
from tests.test_sales import quick_invoice

D = Decimal
DAY = sh.DAY


@pytest.fixture
def ns(company, factory, owner):
    return sh.build(company, factory, owner)          # 8 SKUs x 100 pieces at cost 300 in the Main Godown


def bal(company, key, factory=None):
    return ledger_balance(Ledger.objects.get(company=company, system_key=key), factory=factory)


def post(ns, lines, reason="damage", user=None, **kw):
    return post_journal(company=ns.company, factory=ns.factory, location=ns.godown, date=DAY, reason=reason, lines=lines,
                        user=user or ns.owner, **kw)


def on_hand(ns, sku):
    return StockBalance.objects.get(location=ns.godown, sku=sku).qty


def test_damage_takes_stock_out_at_cost_and_books_a_loss(ns, company, factory):
    j = post(ns, [L("out", ns.sku("Black", "M"), D("5"))], remarks="Water damage")
    assert j.number.startswith("SJ/LDH1/") and j.status == "posted" and (j.value_out, j.value_in) == (D("1500.00"), D("0.00"))
    assert on_hand(ns, ns.sku("Black", "M")) == D("95")
    assert j.voucher.voucher_type == "stock_journal" and j.voucher.source_id == j.pk
    assert bal(company, "stock_adjustment", factory) == D("1500.00")                         # a loss (debit)
    assert bal(company, "stock_finished", factory) == D("240000.00") - D("1500.00")
    assert [(l.direction, l.qty, l.value) for l in j.lines.all()] == [("out", D("5"), D("1500.00"))]


def test_a_count_correction_brings_stock_in_and_books_a_gain(ns, company, factory):
    j = post(ns, [L("in", ns.sku("Navy", "S"), D("3"), rate=D("300"))], reason="count")
    assert on_hand(ns, ns.sku("Navy", "S")) == D("103") and bal(company, "stock_adjustment") == D("-900.00")
    assert j.value_in == D("900.00")


def test_a_conversion_inside_one_stock_ledger_moves_value_and_books_nothing_when_equal(ns, company, factory):
    j = post(ns, [L("out", ns.sku("Black", "M"), D("10")), L("in", ns.sku("Navy", "M"), D("10"), rate=D("300"))], reason="conversion")
    assert on_hand(ns, ns.sku("Black", "M")) == D("90") and on_hand(ns, ns.sku("Navy", "M")) == D("110")
    assert bal(company, "stock_adjustment") == 0 and bal(company, "stock_finished") == D("240000.00")
    dr = [(l.ledger.system_key, l.debit, l.credit) for l in j.voucher.lines.select_related("ledger")]
    assert ("stock_finished", D("3000.00"), D("0.00")) in dr and ("stock_finished", D("0.00"), D("3000.00")) in dr
    dearer = post(ns, [L("out", ns.sku("Black", "L"), D("10")), L("in", ns.sku("Navy", "L"), D("10"), rate=D("320"))], reason="conversion")
    assert dearer.value_in - dearer.value_out == D("200.00") and bal(company, "stock_adjustment") == D("-200.00")


def test_fabric_goes_out_by_roll_and_comes_in_as_a_new_roll(company, factory, owner):
    from tests.prod_helpers import build

    ns = build(company, factory, owner)
    godown = Location.objects.get(factory=factory, name="Main Godown")
    before = RollBalance.objects.get(roll=ns.roll_a, location=godown).qty
    with pytest.raises(BusinessRuleError, match="choose the roll"):
        post_journal(company=company, factory=factory, location=godown, date=DAY, reason="damage", user=owner,
                     lines=[L("out", ns.fabric, D("5"))])
    j = post_journal(company=company, factory=factory, location=godown, date=DAY, reason="damage", user=owner,
                     lines=[L("out", ns.fabric, D("5"), roll=ns.roll_a)])
    assert RollBalance.objects.get(roll=ns.roll_a, location=godown).qty == before - D("5") and j.value_out == D("1050.00")    # weighted average of the two rolls (200 and 220) = 210
    with pytest.raises(BusinessRuleError, match="new roll's number"):
        post_journal(company=company, factory=factory, location=godown, date=DAY, reason="count", user=owner,
                     lines=[L("in", ns.fabric, D("8"), rate=D("210"))])
    j2 = post_journal(company=company, factory=factory, location=godown, date=DAY, reason="count", user=owner,
                      lines=[L("in", ns.fabric, D("8"), rate=D("210"), new_roll_no="NEW-1")])
    roll = j2.lines.get().roll
    assert roll.vendor_roll_no == "NEW-1" and RollBalance.objects.get(roll=roll, location=godown).qty == D("8")
    trim = post_journal(company=company, factory=factory, location=godown, date=DAY, reason="damage", user=owner,
                        lines=[L("out", ns.zipper, D("20"))])
    assert trim.value_out == D("40.00")                                                    # 20 zippers at 2


def test_what_is_refused_and_nothing_is_left_behind(ns, company, factory, factory2, owner, accountant):
    before = (StockJournal.objects.count(), StockBalance.objects.get(sku=ns.sku("Black", "M")).qty)
    with pytest.raises(InsufficientStock):
        post(ns, [L("in", ns.sku("Navy", "S"), D("1"), rate=D("300")), L("out", ns.sku("Black", "M"), D("101"))])
    assert (StockJournal.objects.count(), StockBalance.objects.get(sku=ns.sku("Black", "M")).qty) == before
    assert on_hand(ns, ns.sku("Navy", "S")) == D("100")                                    # the in line rolled back with it
    with pytest.raises(BusinessRuleError, match="at least one line"):
        post(ns, [])
    with pytest.raises(BusinessRuleError, match="Give a rate"):
        post(ns, [L("in", ns.sku("Navy", "S"), D("1"))])
    with pytest.raises(BusinessRuleError, match="Decimal above zero"):
        post(ns, [L("out", ns.sku("Black", "M"), 2.5)])
    with pytest.raises(BusinessRuleError, match="Decimal above zero"):
        post(ns, [L("out", ns.sku("Black", "M"), D("0"))])
    with pytest.raises(BusinessRuleError, match="reason"):
        post(ns, [L("out", ns.sku("Black", "M"), D("1"))], reason="whim")
    with pytest.raises(BusinessRuleError, match="not in factory"):
        post_journal(company=company, factory=factory2, location=ns.godown, date=DAY, reason="damage", user=owner, lines=[L("out", ns.sku("Black", "M"), D("1"))])
    with pytest.raises(BusinessRuleError, match="no value to post"):
        post(ns, [L("in", ns.sku("Navy", "S"), D("1"), rate=D("0"))])
    with pytest.raises(FactoryNotAllowed):
        post(ns, [L("out", ns.sku("Black", "M"), D("1"))], user=make_user("nobody-here"))


def test_cancelling_puts_stock_and_books_back_and_fails_if_the_stock_was_used(ns, company, factory):
    j = post(ns, [L("out", ns.sku("Black", "M"), D("5"))])
    with pytest.raises(BusinessRuleError, match="reason"):
        cancel_journal(j, user=ns.owner, reason=" ")
    cancel_journal(j, user=ns.owner, reason="Counted wrongly")
    assert on_hand(ns, ns.sku("Black", "M")) == D("100") and bal(company, "stock_adjustment") == 0
    j.refresh_from_db()
    assert j.status == "cancelled"
    with pytest.raises(BusinessRuleError, match="already cancelled"):
        cancel_journal(j, user=ns.owner, reason="again")
    gain = post(ns, [L("in", ns.sku("Navy", "S"), D("5"), rate=D("300"))], reason="count")
    quick_invoice(ns, qty="105", rate="500", color="Navy", size="S")                          # the extra pieces have been sold
    with pytest.raises(BusinessRuleError, match="Only"):
        cancel_journal(gain, user=ns.owner, reason="oops")
    gain.refresh_from_db()
    assert gain.status == "posted"                                                           # nothing half-reversed


def test_stock_journal_screens_roles_and_scoping(ns, company, factory, factory2, owner, accountant):
    c = Client()
    c.force_login(owner)
    assert c.get(reverse("journal_list")).status_code == 200 and c.get(reverse("journal_new")).status_code == 200
    sku, navy = ns.sku("Black", "M"), ns.sku("Navy", "M")
    r = c.post(reverse("journal_new"), {
        "factory": factory.pk, "location": ns.godown.pk, "date": "2026-06-15", "reason": "conversion", "remarks": "Repack",
        "direction": ["out", "in", "out"], "item": [f"s:{sku.pk}", f"s:{navy.pk}", ""], "roll": ["", "", ""], "new_roll_no": ["", "", ""],
        "qty": ["4", "4", ""], "rate": ["", "300", ""]})
    j = StockJournal.objects.get()
    assert r.status_code == 302 and r["Location"] == reverse("journal_detail", args=[j.pk]) and j.reason == "conversion"
    page = c.get(reverse("journal_detail", args=[j.pk])).content.decode()
    assert j.number in page and "Repack" in page and "Taken out" in page and "Brought in" in page
    assert j.number in c.get(reverse("journal_list")).content.decode()
    bad = c.post(reverse("journal_new"), {"factory": factory.pk, "location": ns.godown.pk, "date": "2026-06-15", "reason": "damage",
                                          "direction": ["out"], "item": [f"s:{sku.pk}"], "roll": [""], "new_roll_no": [""], "qty": ["5000"], "rate": [""]})
    assert bad.status_code == 200 and "Only" in bad.content.decode() and StockJournal.objects.count() == 1
    keeper = make_user("keeper5")
    keeper.roles.add(Role.objects.get(name="Store Keeper"))
    keeper.allowed_factories.add(factory)
    kc = Client()
    kc.force_login(keeper)
    assert kc.get(reverse("journal_new")).status_code == 200
    assert kc.post(reverse("journal_detail", args=[j.pk]), {"reason": "x"}).status_code == 403             # a keeper cannot cancel
    ac = Client()
    ac.force_login(accountant)
    r = ac.post(reverse("journal_detail", args=[j.pk]), {"reason": "Entered twice"}, follow=True)
    assert "cancelled" in r.content.decode() and StockJournal.objects.get().status == "cancelled"
    clerk = make_user("clerk7")
    clerk.roles.add(Role.objects.get(name="Billing Clerk"))
    clerk.allowed_factories.add(factory)
    cc = Client()
    cc.force_login(clerk)
    assert cc.get(reverse("journal_list")).status_code == 403
    other = make_user("keeper6")
    other.roles.add(Role.objects.get(name="Store Keeper"))
    other.allowed_factories.add(factory2)
    oc = Client()
    oc.force_login(other)
    assert oc.get(reverse("journal_detail", args=[j.pk])).status_code == 404
