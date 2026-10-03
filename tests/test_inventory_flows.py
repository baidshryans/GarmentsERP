from datetime import date
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.models import Location, Role
from inventory.models import FabricRoll, StockMovement
from inventory.services import stock, transfers
from inventory.services.opening import OpeningItem, post_opening_stock
from ledger.exceptions import Unbalanced
from ledger.models import Voucher
from ledger.selectors import ledger_balance, trial_balance
from ledger.services.posting import LineSpec, post_voucher
from masters.models import Colour, Material, Product, Size, Unit
from masters.services import styles
from tax import calc
from tax.models import TaxTemplate
from tests.conftest import make_user

D = Decimal
DAY = date(2026, 6, 15)


@pytest.fixture
def godown(factory):
    return Location.objects.get(factory=factory, name="Main Godown")


@pytest.fixture
def godown2(factory2):
    return Location.objects.get(factory=factory2, name="Main Godown")


@pytest.fixture
def trim(db):
    return Material.objects.create(code="ZIP-1", name="Zipper", kind="trim", unit=Unit.objects.get(code="PCS"))


@pytest.fixture
def fabric(db):
    return Material.objects.create(code="FAB-1", name="Fleece", kind="fabric", unit=Unit.objects.get(code="KG"))


@pytest.fixture
def sku(company):
    s = styles.create_style(company=company, style_no="JGR-1", product=Product.objects.get(code="JGR"), name="Jogger",
                            colours=list(Colour.objects.filter(name="Black")), sizes=list(Size.objects.filter(code="M")))
    return s.skus.get()


def bal(company, key, factory=None):
    from ledger.models import Ledger

    return ledger_balance(Ledger.objects.get(company=company, system_key=key), factory=factory)


# ---------------- posting rule: every factory balances on its own ----------------

def test_a_voucher_must_balance_factory_by_factory(company, factory, factory2, owner, ledgers):
    lines = [LineSpec(ledger=ledgers("cash"), debit=D("100")),
             LineSpec(ledger=ledgers("sales_stock"), credit=D("100"), factory=factory2)]
    with pytest.raises(Unbalanced, match="out of balance"):
        post_voucher(company=company, factory=factory, voucher_type="journal", date=DAY, lines=lines, user=owner)
    assert not Voucher.objects.exists()


def test_cross_factory_entries_work_through_the_inter_factory_ledgers(company, factory, factory2, owner, ledgers):
    lines = [
        LineSpec(ledger=ledgers("cash"), debit=D("100")),
        LineSpec(ledger=ledgers("interfactory_payable"), credit=D("100")),
        LineSpec(ledger=ledgers("interfactory_receivable"), debit=D("100"), factory=factory2),
        LineSpec(ledger=ledgers("sales_stock"), credit=D("100"), factory=factory2),
    ]
    post_voucher(company=company, factory=factory, voucher_type="journal", date=DAY, lines=lines, user=owner)
    for f in (factory, factory2):
        assert trial_balance(company, factory=f)["tallies"]


# ---------------- opening stock ----------------

def test_opening_stock_by_roll_item_and_sku_posts_one_balanced_voucher(company, factory, owner, godown, fabric, trim, sku):
    doc = post_opening_stock(company=company, factory=factory, location=godown, user=owner, entries=[
        OpeningItem(fabric, D("100"), D("180"), vendor_roll_no="OLD-1", lot_no="L1", gsm=280),
        OpeningItem(fabric, D("50"), D("190"), vendor_roll_no="OLD-2"),
        OpeningItem(trim, D("500"), D("2.50")),
        OpeningItem(sku, D("40"), D("300")),
    ])
    assert doc.number == "OST/LDH1/26-27/0001" and doc.total_value == D("18000") + D("9500") + D("1250") + D("12000")
    assert stock.on_hand(factory, fabric) == (D("150.000"), D("27500.00"))
    assert bal(company, "stock_raw_material", factory) == D("28750.00") and bal(company, "stock_finished", factory) == D("12000.00")
    assert bal(company, "opening_difference", factory) == D("-40750.00")  # the suspense the accountant clears
    assert FabricRoll.objects.filter(vendor_roll_no__in=["OLD-1", "OLD-2"]).count() == 2
    assert StockMovement.objects.filter(movement_type="opening").count() == 4


def test_opening_stock_rules(company, factory, owner, godown, fabric, trim):
    with pytest.raises(BusinessRuleError, match="roll"):
        post_opening_stock(company=company, factory=factory, location=godown, user=owner,
                           entries=[OpeningItem(fabric, D("10"), D("5"))])
    with pytest.raises(BusinessRuleError, match="no value"):
        post_opening_stock(company=company, factory=factory, location=godown, user=owner,
                           entries=[OpeningItem(trim, D("10"), D("0"))])
    with pytest.raises(BusinessRuleError):
        post_opening_stock(company=company, factory=factory, location=godown, user=owner, entries=[])
    assert not Voucher.objects.exists() and not StockMovement.objects.exists()  # all or nothing


def test_stock_ledgers_cannot_take_opening_balances_directly(company, factory, owner, ledgers):
    from ledger.exceptions import PostingError
    from ledger.services.opening import OpeningEntry, post_opening_balances

    with pytest.raises(PostingError, match="stock ledger"):
        post_opening_balances(company=company, factory=factory, user=owner,
                              entries=[OpeningEntry(ledgers("stock_raw_material"), debit=D("100"))])


# ---------------- transfers (E6.2) ----------------

def stocked(company, factory, owner, godown, trim, qty="100", rate="5"):
    post_opening_stock(company=company, factory=factory, location=godown, user=owner,
                       entries=[OpeningItem(trim, D(qty), D(rate))])


def test_transfer_between_locations_in_one_factory_moves_stock_without_gl(company, factory, owner, godown, trim):
    stocked(company, factory, owner, godown, trim)
    cutting = Location.objects.get(factory=factory, name="Cutting Floor")
    before = Voucher.objects.count()
    t = transfers.create_transfer(company=company, from_factory=factory, from_location=godown, to_factory=factory,
                                  to_location=cutting, date=DAY, user=owner, lines=[(trim, D("30"), None)])
    t = transfers.issue_transfer(t, user=owner)
    assert t.status == "received" and t.voucher is None and Voucher.objects.count() == before
    from inventory.models import StockBalance

    assert StockBalance.objects.get(location=godown, material=trim).qty == D("70.000")
    assert StockBalance.objects.get(location=cutting, material=trim).value == D("150.00")


def test_inter_factory_transfer_moves_stock_and_value_and_both_books(company, factory, factory2, owner, godown, godown2, trim):
    stocked(company, factory, owner, godown, trim)
    t = transfers.create_transfer(company=company, from_factory=factory, from_location=godown, to_factory=factory2,
                                  to_location=godown2, date=DAY, user=owner, lines=[(trim, D("40"), None)],
                                  document_type="tax_invoice")
    t = transfers.issue_transfer(t, user=owner)
    assert t.status == "issued" and t.voucher_id and t.number.startswith("STF/LDH1/")
    assert stock.on_hand(factory, trim) == (D("60.000"), D("300.00"))
    assert stock.on_hand(factory2, trim) == (D("40.000"), D("200.00"))
    transit = Location.objects.get(factory=factory2, loc_type="transit")
    from inventory.models import StockBalance

    assert StockBalance.objects.get(location=transit, material=trim).qty == D("40.000")  # visible as in transit
    assert bal(company, "stock_raw_material", factory) == D("300.00") and bal(company, "stock_raw_material", factory2) == D("200.00")
    assert bal(company, "interfactory_receivable", factory) == D("200.00") and bal(company, "interfactory_payable", factory2) == D("-200.00")
    assert trial_balance(company, factory=factory)["tallies"] and trial_balance(company, factory=factory2)["tallies"]
    t = transfers.receive_transfer(t, user=owner)
    assert t.status == "received" and StockBalance.objects.get(location=godown2, material=trim).qty == D("40.000")
    assert StockBalance.objects.get(location=transit, material=trim).qty == D("0.000")


def test_transfer_valued_at_the_source_average_and_rolls_travel_with_their_balance(company, factory, factory2, owner, godown, godown2, fabric):
    post_opening_stock(company=company, factory=factory, location=godown, user=owner, entries=[
        OpeningItem(fabric, D("100"), D("50"), vendor_roll_no="A"), OpeningItem(fabric, D("100"), D("70"), vendor_roll_no="B")])
    roll_b = FabricRoll.objects.get(vendor_roll_no="B")
    t = transfers.create_transfer(company=company, from_factory=factory, from_location=godown, to_factory=factory2,
                                  to_location=godown2, date=DAY, user=owner, lines=[(fabric, D("50"), roll_b)])
    t = transfers.issue_transfer(t, user=owner)
    assert t.lines.get().value == D("3000.00")  # weighted average 60 (default valuation)
    transfers.receive_transfer(t, user=owner)
    from inventory.models import RollBalance

    assert RollBalance.objects.get(roll=roll_b, location=godown2).qty == D("50.000")
    assert RollBalance.objects.get(roll=roll_b, location=godown).qty == D("50.000")


def test_transfer_cannot_exceed_stock_and_leaves_nothing_behind(company, factory, factory2, owner, godown, godown2, trim):
    stocked(company, factory, owner, godown, trim, qty="10")
    t = transfers.create_transfer(company=company, from_factory=factory, from_location=godown, to_factory=factory2,
                                  to_location=godown2, date=DAY, user=owner, lines=[(trim, D("11"), None)])
    with pytest.raises(BusinessRuleError, match="Only 10"):
        transfers.issue_transfer(t, user=owner)
    t.refresh_from_db()
    assert t.status == "draft" and stock.on_hand(factory2, trim)[0] == D("0.000")


def test_transfer_permissions_issuer_needs_source_receiver_needs_destination(company, factory, factory2, owner, godown, godown2, trim):
    stocked(company, factory, owner, godown, trim)
    keeper1 = make_user("k1")
    keeper1.roles.add(Role.objects.get(name="Store Keeper"))
    keeper1.allowed_factories.add(factory)
    keeper2 = make_user("k2")
    keeper2.roles.add(Role.objects.get(name="Store Keeper"))
    keeper2.allowed_factories.add(factory2)
    t = transfers.create_transfer(company=company, from_factory=factory, from_location=godown, to_factory=factory2,
                                  to_location=godown2, date=DAY, user=keeper1, lines=[(trim, D("5"), None)])
    with pytest.raises(FactoryNotAllowed):
        transfers.issue_transfer(t, user=keeper2)
    t = transfers.issue_transfer(t, user=keeper1)  # keeper1 cannot see factory 2 but the goods still arrive there
    with pytest.raises(FactoryNotAllowed):
        transfers.receive_transfer(t, user=keeper1)
    transfers.receive_transfer(t, user=keeper2)
    from inventory.models import StockTransfer

    assert StockTransfer.visible_to(keeper2).count() == 1 and StockTransfer.visible_to(make_user("k3")).count() == 0


def test_transfer_validation(company, factory, owner, godown, trim):
    with pytest.raises(BusinessRuleError, match="same location"):
        transfers.create_transfer(company=company, from_factory=factory, from_location=godown, to_factory=factory,
                                  to_location=godown, date=DAY, user=owner, lines=[(trim, D("1"), None)])
    cutting = Location.objects.get(factory=factory, name="Cutting Floor")
    with pytest.raises(BusinessRuleError, match="above zero"):
        transfers.create_transfer(company=company, from_factory=factory, from_location=godown, to_factory=factory,
                                  to_location=cutting, date=DAY, user=owner, lines=[(trim, D("0"), None)])


# ---------------- tax templates (E9.4) ----------------

def test_tax_templates_are_seeded_and_calculate_per_component(company):
    t = TaxTemplate.objects.get(name="GST 12% intra-state (CGST + SGST)")
    amounts = {l.component: l.amount for l in calc.compute(t, D("1001.00"))}
    assert amounts == {"cgst": D("60.06"), "sgst": D("60.06")}
    igst = TaxTemplate.objects.get(name="GST 18% inter-state (IGST)")
    assert calc.compute(igst, D("1000"))[0].amount == D("180.00")
    assert TaxTemplate.objects.get(name="TDS 194C - others (2%)").section == "194C"
    assert TaxTemplate.objects.filter(kind="gst", is_reverse_charge=True).count() == 8


def test_gst_template_suggestion_follows_the_place_of_supply_and_is_only_a_suggestion(company):
    assert calc.suggest_gst_template(party_state="03", place_state="03", rate=D("12")).name == "GST 12% intra-state (CGST + SGST)"
    assert calc.suggest_gst_template(party_state="27", place_state="03", rate=D("12")).is_interstate
    assert calc.suggest_gst_template(party_state="03", place_state="03", rate=D("7")) is None


def test_override_needs_a_reason():
    from tax.calc import TaxAmount, apply_overrides

    lines = [TaxAmount("cgst", D("6"), D("60.00"))]
    with pytest.raises(BusinessRuleError):
        apply_overrides(lines, {"cgst": (D("50"), "")})
    out = apply_overrides(lines, {"cgst": (D("50"), "Round figure")})
    assert out[0].amount == D("50.00") and out[0].is_override
