from datetime import date
from decimal import Decimal

import pytest
from django.db.models import Sum

from core.exceptions import FactoryNotAllowed
from core.models import Location
from inventory.exceptions import InsufficientStock, MovementImmutable, StockError
from inventory.models import RollBalance, StockBalance, StockMovement
from inventory.services import stock
from masters.models import Material, Unit

pytestmark = pytest.mark.raw_stock
D = Decimal
DAY = date(2026, 6, 15)
T = StockMovement.Type


@pytest.fixture
def godown(factory):
    return Location.objects.get(factory=factory, name="Main Godown")


@pytest.fixture
def fabric(db):
    return Material.objects.create(code="FAB-1", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG"))


@pytest.fixture
def trim(db):
    return Material.objects.create(code="ZIP-1", name="Zipper", kind="trim", unit=Unit.objects.get(code="PCS"))


def roll(company, fabric, no, qty="100", rate="50"):
    return stock.create_roll(company=company, material=fabric, vendor_roll_no=no, received_qty=D(qty),
                             rate=D(rate), received_date=DAY)


def receive(factory, loc, item, qty, rate, user, r=None):
    return stock.post_movement(factory=factory, location=loc, item=item, qty=D(qty), rate=D(rate), roll=r,
                               movement_type=T.RECEIPT, date=DAY, user=user)


def issue(factory, loc, item, qty, user, r=None):
    return stock.post_movement(factory=factory, location=loc, item=item, qty=-D(qty), roll=r,
                               movement_type=T.ISSUE, date=DAY, user=user)


def totals(item):
    agg = StockBalance.objects.filter(material=item).aggregate(q=Sum("qty"), v=Sum("value"))
    return stock.q3(agg["q"]), stock.q2(agg["v"])


def test_weighted_average_issue_value(company, factory, godown, trim, owner):
    receive(factory, godown, trim, "100", "50", owner)
    receive(factory, godown, trim, "100", "70", owner)  # average is now 60
    m = issue(factory, godown, trim, "50", owner)
    assert m.value == D("-3000.00") and m.qty == D("-50.000")
    assert totals(trim) == (D("150.000"), D("9000.00"))


def test_last_unit_clears_the_residue_exactly(company, factory, godown, trim, owner):
    receive(factory, godown, trim, "3", "10.00", owner)
    receive(factory, godown, trim, "4", "10.01", owner)  # value 70.04 over 7 pieces
    issue(factory, godown, trim, "2", owner)
    issue(factory, godown, trim, "5", owner)
    assert totals(trim) == (D("0.000"), D("0.00"))


def test_specific_roll_cost_mode_values_at_the_rolls_own_cost(company, factory, godown, fabric, owner):
    company.valuation_method = "specific_roll"
    company.save()
    a, b = roll(company, fabric, "A"), roll(company, fabric, "B")
    receive(factory, godown, fabric, "100", "50", owner, a)
    receive(factory, godown, fabric, "100", "70", owner, b)
    assert issue(factory, godown, fabric, "50", owner, b).value == D("-3500.00")  # roll B costs 70
    assert issue(factory, godown, fabric, "50", owner, a).value == D("-2500.00")  # roll A costs 50
    assert totals(fabric) == (D("100.000"), D("6000.00"))


def test_weighted_average_mode_values_rolls_at_the_item_average(company, factory, godown, fabric, owner):
    a, b = roll(company, fabric, "A"), roll(company, fabric, "B")
    receive(factory, godown, fabric, "100", "50", owner, a)
    receive(factory, godown, fabric, "100", "70", owner, b)
    assert issue(factory, godown, fabric, "50", owner, b).value == D("-3000.00")  # average 60, not roll cost


def test_switching_valuation_method_keeps_item_and_roll_values_consistent(company, factory, godown, fabric, owner):
    a, b = roll(company, fabric, "A"), roll(company, fabric, "B")
    receive(factory, godown, fabric, "100", "50", owner, a)
    receive(factory, godown, fabric, "100", "70", owner, b)
    issue(factory, godown, fabric, "40", owner, b)  # weighted average
    company.valuation_method = "specific_roll"
    company.save()
    issue(factory, godown, fabric, "30", owner, a)
    issue(factory, godown, fabric, "10", owner, b)
    q, v = totals(fabric)
    rq = RollBalance.objects.aggregate(q=Sum("qty"), v=Sum("value"))
    assert (q, v) == (stock.q3(rq["q"]), stock.q2(rq["v"]))


def test_issue_above_stock_is_blocked_and_nothing_changes(company, factory, godown, trim, owner):
    receive(factory, godown, trim, "10", "5", owner)
    with pytest.raises(InsufficientStock):
        issue(factory, godown, trim, "11", owner)
    assert totals(trim) == (D("10.000"), D("50.00")) and StockMovement.objects.count() == 1


def test_negative_stock_allowed_when_the_setting_is_on(company, factory, godown, trim, owner):
    company.allow_negative_stock = True
    company.save()
    issue(factory, godown, trim, "4", owner)
    assert totals(trim)[0] == D("-4.000")


def test_roll_balance_cannot_be_exceeded_even_when_negative_stock_is_allowed(company, factory, godown, fabric, owner):
    company.allow_negative_stock = True
    company.save()
    a = roll(company, fabric, "A")
    receive(factory, godown, fabric, "100", "50", owner, a)
    receive(factory, godown, fabric, "100", "50", owner, roll(company, fabric, "B"))
    with pytest.raises(InsufficientStock, match="BR-02"):
        issue(factory, godown, fabric, "101", owner, a)
    assert totals(fabric)[0] == D("200.000")


def test_fabric_must_be_stocked_by_roll_and_roll_must_match(company, factory, godown, fabric, trim, owner):
    with pytest.raises(StockError, match="by roll"):
        receive(factory, godown, fabric, "10", "5", owner)
    with pytest.raises(StockError, match="not a roll"):
        receive(factory, godown, trim, "10", "5", owner, roll(company, fabric, "A"))


def test_quantities_must_be_decimal_nonzero_and_three_places(company, factory, godown, trim, owner):
    for bad in (1.5, "3", D("1.0001")):
        with pytest.raises(StockError):
            stock.post_movement(factory=factory, location=godown, item=trim, qty=bad, rate=D("1"),
                                movement_type=T.RECEIPT, date=DAY, user=owner)
    with pytest.raises(StockError, match="BR-01"):
        stock.post_movement(factory=factory, location=godown, item=trim, qty=D("0"), rate=D("1"),
                            movement_type=T.RECEIPT, date=DAY, user=owner)
    with pytest.raises(StockError):
        stock.post_movement(factory=factory, location=godown, item=trim, qty=D("1"), rate=1.5,
                            movement_type=T.RECEIPT, date=DAY, user=owner)


def test_location_must_belong_to_the_factory(company, factory, factory2, trim, owner):
    other = Location.objects.get(factory=factory2, name="Main Godown")
    with pytest.raises(StockError, match="not in factory"):
        receive(factory, other, trim, "1", "1", owner)


def test_user_without_factory_access_cannot_move_stock(company, factory, factory2, godown, trim, accountant):
    other = Location.objects.get(factory=factory2, name="Main Godown")
    with pytest.raises(FactoryNotAllowed):
        receive(factory2, other, trim, "1", "1", accountant)


def test_movement_ledger_is_append_only(company, factory, godown, trim, owner):
    m = receive(factory, godown, trim, "10", "5", owner)
    m.notes = "tamper"
    with pytest.raises(MovementImmutable):
        m.save()
    with pytest.raises(MovementImmutable):
        m.delete()
    with pytest.raises(MovementImmutable):
        StockMovement.objects.filter(pk=m.pk).update(qty=D("99"))
    with pytest.raises(MovementImmutable):
        StockMovement.objects.filter(pk=m.pk).delete()


def test_reversal_restores_exact_qty_and_value(company, factory, godown, trim, owner):
    receive(factory, godown, trim, "10", "5", owner)
    m = receive(factory, godown, trim, "10", "7", owner)
    stock.reverse_movement(m, user=owner, date=DAY)
    assert totals(trim) == (D("10.000"), D("50.00"))


def test_reversal_of_a_receipt_fails_if_the_stock_was_used(company, factory, godown, trim, owner):
    m = receive(factory, godown, trim, "10", "5", owner)
    issue(factory, godown, trim, "8", owner)
    with pytest.raises(InsufficientStock):
        stock.reverse_movement(m, user=owner, date=DAY)


def test_revaluation_changes_value_not_quantity(company, factory, godown, trim, owner):
    receive(factory, godown, trim, "10", "5", owner)
    stock.post_movement(factory=factory, location=godown, item=trim, qty=D("0"), value=D("12.50"),
                        movement_type=T.REVALUATION, date=DAY, user=owner)
    assert totals(trim) == (D("10.000"), D("62.50"))
    assert issue(factory, godown, trim, "10", owner).value == D("-62.50")


def test_balances_always_equal_the_sum_of_movements(company, factory, godown, trim, fabric, owner):
    a = roll(company, fabric, "A")
    receive(factory, godown, trim, "100", "5", owner)
    receive(factory, godown, fabric, "100", "50", owner, a)
    issue(factory, godown, trim, "33", owner)
    issue(factory, godown, fabric, "10", owner, a)
    for bal in StockBalance.objects.all():
        agg = StockMovement.objects.filter(location=bal.location, material=bal.material, sku=bal.sku).aggregate(
            q=Sum("qty"), v=Sum("value"))
        assert (stock.q3(agg["q"]), stock.q2(agg["v"])) == (bal.qty, bal.value)
