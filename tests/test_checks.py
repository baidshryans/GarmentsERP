"""Logical checks by default (owner, 19 Oct 2026): garment pieces are whole numbers everywhere, in every service,
not only on the forms. Materials (fabric in kg or metres, trims issued with wastage, thread by the cone) keep
their decimals."""
from decimal import Decimal

import pytest

from core import checks
from core.exceptions import BusinessRuleError
from core.services.factories import godown_location
from inventory.services import stock
from jobwork.services import challans, rates, receipts
from jobwork.services.receipts import Counted
from production.services import bundles as bundle_service
from tests.prod_helpers import DAY, build, cut, fabricator, go, step

D = Decimal


def test_whole_accepts_whole_numbers_and_refuses_the_rest():
    assert checks.whole(5, "Pieces") == 5 and checks.whole(D("5.000"), "Pieces") == 5
    for bad in (D("2.5"), 2.5, True, "3"):
        with pytest.raises(BusinessRuleError, match="Pieces must be a whole number of pieces."):
            checks.whole(bad, "Pieces")


def test_stock_movement_of_a_garment_refuses_a_fraction(company, factory, owner):
    ns = build(company, factory, owner)
    sku = ns.style.skus.first()
    with pytest.raises(BusinessRuleError, match="whole number of pieces"):
        stock.post_movement(factory=factory, location=godown_location(factory), item=sku, qty=D("2.5"), rate=D("100"),
                            movement_type="opening", date=DAY, user=owner)


@pytest.mark.raw_stock
def test_fabric_and_trims_keep_their_decimals(company, factory, owner):
    ns = build(company, factory, owner)
    m = stock.post_movement(factory=factory, location=godown_location(factory), item=ns.zipper, qty=D("244.8"),
                            rate=D("2"), movement_type="receipt", date=DAY, user=owner)
    assert m.qty == D("244.800")


def test_move_bundles_refuses_a_fraction_when_called_directly(company, factory, owner):
    ns = build(company, factory, owner)
    for s in ns.lot.steps.all():
        s.assignment, s.party, s.factory = "in_house", None, factory
        s.save()
    bundles = cut(ns)
    with pytest.raises(BusinessRuleError, match="whole number of pieces"):
        go(ns, bundles[:1], "STITCH", counts={bundles[0].pk: bundle_service.Count(loss=D("1.5"))})


def test_split_refuses_a_fraction(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    with pytest.raises(BusinessRuleError, match="whole number of pieces"):
        bundle_service.split_bundle(bundles[0], D("2.5"), user=owner, date=DAY)


def test_receipt_refuses_a_fraction(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab = fabricator(company)
    rates.save_rate(who=fab, process=step(ns, "STITCH").process, rate=D("25"), effective_from=DAY)
    ch = challans.create_and_issue(company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"),
                                   bundles=bundles[:1], date=DAY, user=owner)
    with pytest.raises(BusinessRuleError, match="whole number of pieces"):
        receipts.create_receipt(challan=ch, user=owner, date=DAY, counts=[Counted(ch.bundles.get(), D("10.5"))])


# ---------------- limits, dates and money (Task 9) ----------------

from datetime import timedelta

from django.utils import timezone

from inventory.exceptions import InsufficientStock
from jobwork.services import bills
from production.services import cutting


def _issued(company, factory, owner, day=DAY):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab = fabricator(company)
    rates.save_rate(who=fab, process=step(ns, "STITCH").process, rate=D("25"), effective_from=DAY)
    ch = challans.create_and_issue(company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"),
                                   bundles=bundles[:1], date=day, user=owner)
    return ns, fab, ch


def test_not_future_and_not_before_say_what_is_wrong():
    today = timezone.localdate()
    with pytest.raises(BusinessRuleError, match="^The cutting cannot be in the future.$"):
        checks.not_future(today + timedelta(days=1), "The cutting")
    checks.not_future(today, "The cutting")
    with pytest.raises(BusinessRuleError, match=r"^The receipt cannot be dated before the challan \(15 Jun 2026\).$"):
        checks.not_before(DAY - timedelta(days=1), DAY, "The receipt", "the challan")
    with pytest.raises(BusinessRuleError, match="^A rate cannot be negative.$"):
        checks.not_negative(D("-1"), "A rate")


def test_a_future_dated_step_is_refused(company, factory, owner):
    ns = build(company, factory, owner)
    tomorrow = timezone.localdate() + timedelta(days=1)
    with pytest.raises(BusinessRuleError, match="cannot be in the future"):
        cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("10"))], user=owner, date=tomorrow)
    assert not ns.lot.fabric_issues.exists()


def test_a_receipt_before_its_challan_is_refused(company, factory, owner):
    ns, fab, ch = _issued(company, factory, owner)
    with pytest.raises(BusinessRuleError, match=r"cannot be dated before the challan \(15 Jun 2026\)"):
        receipts.create_receipt(challan=ch, user=owner, date=DAY - timedelta(days=1),
                                counts=[Counted(ch.bundles.get(), ch.bundles.get().qty_issued)])


def test_a_bill_before_its_pieces_were_checked_is_refused(company, factory, owner):
    ns, fab, ch = _issued(company, factory, owner)
    r = receipts.create_receipt(challan=ch, user=owner, date=DAY, counts=[Counted(ch.bundles.get(), ch.bundles.get().qty_issued)])
    receipts.record_qc(receipt_line=r.lines.get(), accepted=r.lines.get().qty_received, user=owner)
    with pytest.raises(BusinessRuleError, match="cannot be dated before the pieces on it were received"):
        bills.create_bill(company=company, factory=factory, party=fab, date=DAY - timedelta(days=1), user=owner)


def test_fabric_issued_beyond_the_roll_is_refused(company, factory, owner):
    ns = build(company, factory, owner)
    with pytest.raises(InsufficientStock, match="Roll .* has only 100"):
        cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("150"))], user=owner, date=DAY)


def test_a_negative_rate_is_refused(company):
    from masters.models import Process

    with pytest.raises(BusinessRuleError, match="A rate cannot be negative."):
        rates.save_rate(who=None, process=Process.objects.get(code="CUT"), effective_from=DAY, rate=D("-1"))
