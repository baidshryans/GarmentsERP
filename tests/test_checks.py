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
