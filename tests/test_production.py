from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.models import Location
from inventory.exceptions import InsufficientStock
from inventory.models import StockBalance
from inventory.services import stock
from masters.models import Process
from masters.services import boms
from production.models import Bundle, LotStep, ProductionOrder, StageMovement
from production.services import bundles as bundle_service
from production.services import costing, cutting, orders, routes
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, gl, go, step


# ---------------- orders (E7.1) ----------------

def test_size_ratio_is_spread_in_whole_pieces_that_add_up():
    out = orders.spread(100, {"S": 1, "M": 2, "L": 2, "X": 1})
    assert sorted(out.values()) == [17, 17, 33, 33] and sum(out.values()) == 100
    assert sum(orders.spread(7, {"S": 1, "M": 1, "L": 1}).values()) == 7
    with pytest.raises(BusinessRuleError):
        orders.spread(10, {"S": 0})


def test_release_makes_a_lot_with_its_own_route_and_pins_the_bom(company, factory, owner):
    ns = build(company, factory, owner)
    assert ns.order.number == "PRO/LDH1/26-27/0001" and ns.order.status == "released"
    lot = ns.lot
    assert lot.lot_no == "LOT/LDH1/26-27/0001" and lot.bom_version == boms.current_version(ns.style)
    steps = list(lot.steps.all())
    assert [s.process.code for s in steps][:3] == ["CUT", "STITCH", "EMB"] and len(steps) == 9
    assert steps[1].assignment == "subcontract" and steps[0].factory == factory
    sizes = {l.size.code: l.qty for l in ns.order.lines.get().sizes.all()}
    assert sum(sizes.values()) == 100 and sizes["M"] == 33


def test_an_order_needs_a_route_to_be_released(company, factory, owner):
    ns = build(company, factory, owner, with_stock=False)
    other = orders.create_order(company=company, factory=factory, date=DAY, user=owner, lines=[
        orders.OrderLineSpec(ns.style, ns.black, 10, {ns.sizes["M"]: 1})])
    ns.style.default_route = None
    ns.style.save()
    with pytest.raises(BusinessRuleError, match="no default route"):
        orders.release_order(other, user=owner)


def test_order_lines_must_use_the_styles_colours_and_sizes(company, factory, owner):
    from masters.models import Colour, Size

    ns = build(company, factory, owner, with_stock=False)
    with pytest.raises(BusinessRuleError, match="not a colour"):
        orders.create_order(company=company, factory=factory, date=DAY, user=owner, lines=[
            orders.OrderLineSpec(ns.style, Colour.objects.get(name="Navy"), 10, {ns.sizes["M"]: 1})])
    with pytest.raises(BusinessRuleError, match="not a size"):
        orders.create_order(company=company, factory=factory, date=DAY, user=owner, lines=[
            orders.OrderLineSpec(ns.style, ns.black, 10, {Size.objects.get(code="XXL"): 1})])


def test_once_a_lot_is_cut_from_a_bom_changing_it_makes_a_new_version(company, factory, owner):
    ns = build(company, factory, owner)
    v, created = boms.save_bom(ns.style, lines=[boms.BomLineSpec(ns.zipper, D("2"))], user=owner)
    assert created and v.version_no == 2
    assert ns.lot.bom_version.version_no == 1 and ns.lot.bom_version.lines.get().qty_per_piece == D("1")  # the lot keeps v1


def test_an_order_is_released_for_a_style_with_no_material_list(company, factory, owner):
    """The list is optional: the lot simply has none, and nothing is filled in for it."""
    from masters.services import styles

    ns = build(company, factory, owner)
    bare = styles.create_style(company=company, style_no="JGR-2", product=ns.style.product, name="Plain jogger",
                               colours=[ns.black], sizes=list(ns.sizes.values()))
    bare.default_route = ns.style.default_route
    bare.save()
    order = orders.release_order(orders.create_order(
        company=company, factory=factory, date=DAY, user=owner,
        lines=[orders.OrderLineSpec(bare, ns.black, 10, {ns.sizes["M"]: 1})]), user=owner)
    lot = order.lines.get().lot
    assert order.status == "released" and lot.bom_version is None and lot.steps.exists()


def test_production_order_never_stores_the_customer(company, factory, owner):
    fields = {f.name for f in ProductionOrder._meta.get_fields()}
    assert not {"customer", "customer_name", "customer_phone", "party"} & fields


# ---------------- route planning (E7.2, E7.3) ----------------

def test_route_changes_are_logged_and_obey_the_rules(company, factory, owner):
    ns = build(company, factory, owner)
    lot = ns.lot
    emb = step(ns, "EMB")
    routes.skip_step(emb, user=owner, reason="No embroidery on this lot")
    assert LotStep.objects.get(pk=emb.pk).status == "skipped"
    with pytest.raises(BusinessRuleError, match="mandatory"):
        routes.skip_step(step(ns, "IRON"), user=owner, reason="x")
    with pytest.raises(BusinessRuleError, match="reason"):
        routes.skip_step(step(ns, "WASH"), user=owner, reason=" ")
    fab = fabricator(company)
    routes.reassign_step(step(ns, "STITCH"), user=owner, reason="Sharma is free", assignment="subcontract", party=fab, rate=D("25"))
    st = step(ns, "STITCH")
    assert st.party == fab and st.rate == D("25.00")
    routes.reassign_step(step(ns, "IRON"), user=owner, reason="Unit 1 is busy", assignment="subcontract", party=fab)
    new = routes.add_step(lot, process=Process.objects.get(code="DYE"), after_sequence=1, user=owner, reason="Needs dyeing",
                          assignment="subcontract", party=fab, rate=D("8"))
    assert [s.process.code for s in lot.steps.all()][:3] == ["CUT", "DYE", "STITCH"] and new.sequence == 2
    assert [s.sequence for s in lot.steps.all()] == list(range(1, 11))
    routes.reorder_step(step(ns, "WASH"), new_sequence=2, user=owner, reason="Wash before stitching")
    assert lot.steps.get(sequence=2).process.code == "WASH"
    routes.remove_step(step(ns, "PRINT"), user=owner, reason="Not needed")
    assert not lot.steps.filter(process__code="PRINT").exists() and lot.steps.count() == 9
    actions = [c.action for c in lot.route_changes.all()]
    assert actions.count("reassigned") == 2 and {"skipped", "added", "reordered", "removed"} <= set(actions)
    assert all(c.user == owner and c.reason for c in lot.route_changes.all())


def test_a_started_step_cannot_be_changed(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles[:1], "STITCH")
    with pytest.raises(BusinessRuleError, match="already started"):
        routes.reassign_step(step(ns, "STITCH"), user=owner, reason="x", assignment="in_house")


def test_route_assignment_rules(company, factory, owner):
    from masters.services import parties

    ns = build(company, factory, owner)
    cust = parties.create_party(company=company, name="Dealer", mobile="9822222222", is_customer=True)
    with pytest.raises(BusinessRuleError, match="not marked as a fabricator"):
        routes.reassign_step(step(ns, "STITCH"), user=owner, reason="x", assignment="subcontract", party=cust)
    with pytest.raises(BusinessRuleError, match="in-house step cannot"):
        routes.reassign_step(step(ns, "IRON"), user=owner, reason="x", assignment="in_house", party=fabricator(company))


# ---------------- fabric issue and cutting (E7.4) ----------------

def test_fabric_issue_moves_rolls_to_the_cutting_floor_at_cost(company, factory, owner):
    ns = build(company, factory, owner)
    issue = cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=owner, date=DAY)
    cutting_floor = Location.objects.get(factory=factory, name="Cutting Floor")
    assert issue.lines.get().value == D("12600.00")  # 60 kg at the 210 average
    assert StockBalance.objects.get(location=cutting_floor, material=ns.fabric).qty == D("60.000")
    ns.lot.refresh_from_db()
    assert ns.lot.status == "cutting"
    assert gl(company, "stock_raw_material", factory) == D("44000.00")  # 42,000 fabric + 2,000 zippers; a move has no GL


def test_fabric_issue_is_blocked_above_the_roll_balance_and_warns_on_mixed_shades(company, factory, owner):
    from inventory.models import FabricRoll

    ns = build(company, factory, owner)
    with pytest.raises(InsufficientStock, match="BR-02"):
        cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("101"))], user=owner, date=DAY)
    ok = cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("10"))], user=owner, date=DAY)
    assert not ok.mixed_shades
    odd = FabricRoll.objects.get(vendor_roll_no="B")
    odd.lot_no = "L2"
    odd.save()
    mixed = cutting.issue_fabric(lot=ns.lot, lines=[(odd, D("10"))], user=owner, date=DAY)
    assert mixed.mixed_shades


def test_cutting_books_consumed_fabric_as_lot_cost_and_returns_the_remnant(company, factory, owner):
    ns = build(company, factory, owner)
    cut(ns)
    lot = ns.lot
    assert costing.lot_cost(lot, factory) == D("9030.00")  # (41 used + 2 waste) x 210
    assert gl(company, "stock_wip", factory) == D("9030.00")
    godown = Location.objects.get(factory=factory, name="Main Godown")
    cutting_floor = Location.objects.get(factory=factory, name="Cutting Floor")
    assert StockBalance.objects.get(location=godown, material=ns.fabric).qty == D("157.000")  # 200 - 60 + 17 remnant
    assert StockBalance.objects.get(location=cutting_floor, material=ns.fabric).qty == D("0.000")
    use = ns.entry.rolls.get()
    assert use.used_qty + use.waste_qty + use.remnant_qty == D("60.000")  # issued = used + waste + remnant
    assert costing.cost_breakdown(lot)["fabric"] == D("9030.00")
    assert not costing.check_wip_reconciles(company)


def test_cutting_shows_pieces_cut_against_the_estimate_and_flags_beyond_tolerance(company, factory, owner):
    ns = build(company, factory, owner)
    cut(ns, burnt=("41", "2"), remnant="17", estimate=150)      # 150 pieces from 60 kg; 43 kg burnt should give 107
    e = ns.entry
    assert e.expected_pieces == 107 and e.variance_pct == D("-6.54") and e.over_tolerance   # 100 cut
    assert e.expected_fabric is None                            # no longer compared in kg


def test_variance_inside_the_tolerance_is_not_flagged_and_the_tolerance_is_a_setting(company, factory, owner):
    ns = build(company, factory, owner)
    cut(ns, burnt=("40", "1"), remnant="19", estimate=150)  # 41 kg burnt should give 102: 100 cut is 1.96% under
    assert ns.entry.expected_pieces == 102 and ns.entry.variance_pct == D("-1.96") and not ns.entry.over_tolerance
    company.bom_tolerance_pct = D("1")
    company.save()
    other = orders.release_order(orders.create_order(
        company=company, factory=factory, date=DAY, user=owner,
        lines=[orders.OrderLineSpec(ns.style, ns.black, 10, {ns.sizes["M"]: 1})]), user=owner).lines.get().lot
    cutting.issue_fabric(lot=other, lines=[(ns.roll_b, D("5"))], user=owner, date=DAY, estimated_pieces=255)
    e = cutting.record_cutting(lot=other, user=owner, date=DAY, pieces={ns.sizes["M"]: 200},
                               rolls=[cutting.RollUseSpec(ns.roll_b, used=D("4"), waste=D("0.0"), remnant=D("1"))])
    assert e.expected_pieces == 204 and e.variance_pct == D("-1.96") and e.over_tolerance  # now beyond a 1% tolerance


def test_cutting_validates_its_input(company, factory, owner):
    from masters.models import Size

    ns = build(company, factory, owner)
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("10"))], user=owner, date=DAY)
    with pytest.raises(BusinessRuleError, match="not a size"):
        cutting.record_cutting(lot=ns.lot, user=owner, date=DAY, pieces={Size.objects.get(code="XXL"): 5},
                               rolls=[cutting.RollUseSpec(ns.roll_a, used=D("1"))])
    with pytest.raises(BusinessRuleError, match="at least one size"):
        cutting.record_cutting(lot=ns.lot, user=owner, date=DAY, pieces={}, rolls=[cutting.RollUseSpec(ns.roll_a, used=D("1"))])
    with pytest.raises(InsufficientStock):
        cutting.record_cutting(lot=ns.lot, user=owner, date=DAY, pieces={ns.sizes["M"]: 5},
                               rolls=[cutting.RollUseSpec(ns.roll_a, used=D("11"))])


def test_cutting_needs_a_user_in_the_lots_factory(company, factory, owner):
    ns = build(company, factory, owner)
    with pytest.raises(FactoryNotAllowed):
        cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("1"))], user=make_user("stranger"), date=DAY)


# ---------------- bundles and QR (E7.5) ----------------

def test_bundles_are_made_per_size_with_unique_qr_tokens(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns, bundle_size=25)
    by_size = {}
    for b in bundles:
        by_size.setdefault(b.sku.size.code, []).append(b.qty)
    assert by_size == {"S": [17], "M": [25, 8], "L": [25, 8], "XL": [17]} and len(bundles) == 6
    assert len({b.qr_token for b in bundles}) == 6 and [b.bundle_no for b in bundles] == [f"B00{i}" for i in range(1, 7)]
    assert all(b.status == "cut" and b.location.loc_type == "cutting" for b in bundles)
    assert step(ns, "CUT").status == "done" and all(b.completed_seq == 1 for b in bundles)
    with pytest.raises(BusinessRuleError, match="already made"):
        cutting.create_bundles(ns.entry, bundle_size=10, user=owner)


# ---------------- stage moves (E7.6, E7.7, BR-21, BR-22) ----------------

def all_in_house(ns, stitch_rate="10"):
    """Make the whole route in-house (stitching included) and skip the optional value-add steps."""
    routes.reassign_step(step(ns, "STITCH"), user=ns.owner, reason="Stitch in-house", assignment="in_house",
                         rate=D(stitch_rate), rework_rate=D("4"))
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=ns.owner, reason="Not needed")


def wip_qty(ns, loc_name):
    loc = Location.objects.get(factory=ns.factory, name=loc_name)
    return sum(int(b.qty) for b in StockBalance.objects.filter(location=loc, sku__isnull=False))


def test_move_to_the_next_stage_balances_and_keeps_wip_stock_in_step(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    assert wip_qty(ns, "Cutting Floor") == 100
    moves = go(ns, bundles, "STITCH")
    assert all(m.qty_out == m.qty_in and m.loss == m.rejection == m.shortage == 0 for m in moves)
    assert wip_qty(ns, "Cutting Floor") == 0 and wip_qty(ns, "Process Area") == 100
    b = Bundle.objects.get(pk=bundles[0].pk)
    assert b.status == "at_stage" and b.current_step == step(ns, "STITCH") and b.location.loc_type == "process"
    assert step(ns, "STITCH").status == "in_progress"


def test_a_move_with_loss_rejection_and_shortage_still_balances(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    target = bundles[1]  # 25 pieces
    (m,) = go(ns, [target], "STITCH", counts={target.pk: bundle_service.Count(loss=1, rejection=2, shortage=1)})
    assert (m.qty_out, m.qty_in, m.loss, m.rejection, m.shortage) == (25, 21, 1, 2, 1)
    assert m.qty_out == m.qty_in + m.loss + m.rejection + m.shortage  # BR-21
    assert Bundle.objects.get(pk=target.pk).qty == 21
    assert wip_qty(ns, "Rejects") == 2 and wip_qty(ns, "Process Area") == 21


def test_the_database_itself_refuses_an_unbalanced_stage_movement(company, factory, owner):
    from django.db import IntegrityError, transaction

    ns = build(company, factory, owner)
    b = cut(ns)[0]
    with pytest.raises(IntegrityError), transaction.atomic():
        StageMovement.objects.create(factory=factory, bundle=b, kind="move", from_location=b.location, to_location=b.location,
                                     qty_out=17, qty_in=16)


def test_losses_larger_than_the_bundle_are_refused(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    with pytest.raises(BusinessRuleError, match="BR-21"):
        go(ns, [bundles[0]], "STITCH", counts={bundles[0].pk: bundle_service.Count(loss=10, rejection=10)})
    assert Bundle.objects.get(pk=bundles[0].pk).location.loc_type == "cutting"


def test_a_mandatory_stage_cannot_be_skipped_but_an_optional_one_can(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    with pytest.raises(BusinessRuleError, match="mandatory"):
        go(ns, bundles, "IRON")  # STITCH is mandatory
    go(ns, bundles, "STITCH")
    go(ns, bundles, "IRON")  # the optional EMB / PRINT / WASH steps were skipped on the route
    assert step(ns, "STITCH").status == "done"


def test_moving_back_needs_a_reason_and_marks_the_bundle_as_rework(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles, "IRON")
    with pytest.raises(BusinessRuleError, match="BR-22"):
        go(ns, bundles[:1], "STITCH")
    (m,) = go(ns, bundles[:1], "STITCH", reason="Re-stitch loose seam")
    b = Bundle.objects.get(pk=bundles[0].pk)
    assert m.is_rework and m.reason and b.is_rework and b.completed_seq == step(ns, "STITCH").sequence - 1
    assert sum(x.qty for x in Bundle.objects.filter(lot=ns.lot, is_rework=True)) == bundles[0].qty  # shown separately


def test_in_house_labour_is_added_to_lot_cost_when_pieces_leave_a_stage(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns, stitch_rate="10")
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    assert costing.lot_cost(ns.lot) == D("9030.00")  # nothing yet: the stitching is not finished
    go(ns, bundles, "IRON")
    assert costing.cost_breakdown(ns.lot)["labour"] == D("1000.00")  # 100 pieces x 10
    assert gl(company, "labour_absorbed", factory) == D("-1000.00") and gl(company, "stock_wip", factory) == D("10030.00")
    assert not costing.check_wip_reconciles(company)


def test_rework_uses_the_rework_rate(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns, stitch_rate="10")
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles, "IRON")
    go(ns, bundles[:1], "STITCH", reason="Redo")
    before = costing.cost_breakdown(ns.lot)["labour"]
    go(ns, bundles[:1], "IRON")
    assert costing.cost_breakdown(ns.lot)["labour"] - before == D("68.00")  # 17 pieces x rework rate 4


def test_subcontracted_stages_refuse_a_plain_move(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = cut(ns)
    with pytest.raises(BusinessRuleError, match="job work challan"):
        go(ns, bundles, "STITCH")


def test_bundles_of_two_lots_cannot_be_moved_together(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    other = orders.release_order(orders.create_order(
        company=company, factory=factory, date=DAY, user=owner,
        lines=[orders.OrderLineSpec(ns.style, ns.black, 10, {ns.sizes["M"]: 1})]), user=owner).lines.get().lot
    stray = Bundle.objects.get(pk=bundles[0].pk)
    stray.lot = other
    stray.save()
    with pytest.raises(BusinessRuleError, match="one lot"):
        bundle_service.move_bundles(bundles=[stray, bundles[1]], to_step=step(ns, "STITCH"), user=owner)
    stray.lot = ns.lot
    stray.save()


# ---------------- inter-factory WIP (E7.9) ----------------

def test_moving_a_lot_to_a_stage_at_another_factory_moves_its_cost_and_keeps_both_books_tallying(company, factory, factory2, owner):
    from ledger.selectors import trial_balance

    ns = build(company, factory, owner)
    all_in_house(ns)
    routes.reassign_step(step(ns, "IRON"), user=owner, reason="Iron at unit 2", assignment="in_house", factory=factory2, rate=D("2"))
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles, "IRON")  # all 100 pieces cross to factory 2
    assert costing.live_pieces(ns.lot, factory2) == 100 and costing.live_pieces(ns.lot, factory) == 0
    assert costing.lot_cost(ns.lot, factory) == D("0.00") and costing.lot_cost(ns.lot, factory2) == D("10030.00")
    assert gl(company, "stock_wip", factory2) == D("10030.00") and gl(company, "stock_wip", factory) == D("0.00")
    assert gl(company, "interfactory_receivable", factory) == D("10030.00")
    assert gl(company, "interfactory_payable", factory2) == D("-10030.00")
    assert trial_balance(company, factory=factory)["tallies"] and trial_balance(company, factory=factory2)["tallies"]
    assert "factory" in {m.kind for m in StageMovement.objects.filter(bundle__lot=ns.lot)}
    assert not costing.check_wip_reconciles(company)


def test_a_part_of_the_lot_moving_takes_its_share_of_cost(company, factory, factory2, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    routes.reassign_step(step(ns, "IRON"), user=owner, reason="Iron at unit 2", assignment="in_house", factory=factory2)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles[:1], "IRON")  # the first bundle: 17 of 100 pieces
    # its stitching (17 x 10 = 170) is accrued first, so 9,200 sits at factory 1 and 17% of it moves
    assert costing.lot_cost(ns.lot, factory2) == D("1564.00") and costing.lot_cost(ns.lot, factory) == D("7636.00")
    assert not costing.check_wip_reconciles(company)


# ---------------- packing into finished goods ----------------

def finish_route(ns):
    all_in_house(ns)
    bundles = cut(ns)
    for code in ("STITCH", "IRON", "FINISH", "QC", "PACK"):
        go(ns, bundles, code)
    return bundles


def test_packing_receives_finished_goods_at_lot_cost_and_clears_wip(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = finish_route(ns)
    packed = bundle_service.pack_bundles(bundles=bundles, user=owner, date=DAY)
    assert all(b.status == "packed" for b in packed)
    assert costing.lot_cost(ns.lot) == D("0.00") and gl(company, "stock_wip", factory) == D("0.00")
    assert gl(company, "stock_finished", factory) == D("10030.00")  # 9,030 fabric + 1,000 stitching
    dispatch = Location.objects.get(factory=factory, name="Dispatch")
    assert StockBalance.objects.filter(location=dispatch, sku__isnull=False).count() == 4
    ns.lot.refresh_from_db()
    ns.order.refresh_from_db()
    assert ns.lot.status == "completed" and ns.order.status == "completed"
    assert wip_qty(ns, "Process Area") == 0
    assert not costing.check_wip_reconciles(company)


def test_a_partial_pack_relieves_cost_in_proportion(company, factory, owner):
    ns = build(company, factory, owner)
    bundles = finish_route(ns)
    total = costing.lot_cost(ns.lot, factory)
    bundle_service.pack_bundles(bundles=bundles[:2], user=owner, date=DAY)  # 17 + 25 = 42 of 100 pieces
    relieved = gl(company, "stock_finished", factory)
    assert relieved == (total * 42 / 100).quantize(D("0.01")) and costing.lot_cost(ns.lot, factory) == total - relieved
    ns.lot.refresh_from_db()
    ns.order.refresh_from_db()
    assert ns.lot.status == "in_production" and ns.order.status == "in_production"


def test_packing_needs_the_packing_stage(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    with pytest.raises(BusinessRuleError, match="not reached"):
        bundle_service.pack_bundles(bundles=bundles, user=owner)


def test_losses_during_production_raise_the_cost_of_the_pieces_left(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns, stitch_rate="0")
    bundles = cut(ns)
    go(ns, bundles, "STITCH", counts={bundles[0].pk: bundle_service.Count(loss=17)})  # one whole small bundle lost
    live = [b for b in bundles if Bundle.objects.get(pk=b.pk).status != "scrapped"]
    for code in ("IRON", "FINISH", "QC", "PACK"):
        go(ns, live, code)
    bundle_service.pack_bundles(bundles=live, user=owner)
    assert gl(company, "stock_finished", factory) == D("9030.00")  # the lost pieces' cost is carried by the 83 good ones
    assert costing.lot_cost(ns.lot) == D("0.00")


# ---------------- closing an order ----------------

def test_closing_an_order_writes_off_remaining_wip_and_needs_the_owner(company, factory, owner, accountant):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    with pytest.raises(BusinessRuleError, match="owner"):
        orders.close_order(ns.order, user=accountant, reason="Abandoned")
    with pytest.raises(BusinessRuleError, match="reason"):
        orders.close_order(ns.order, user=owner, reason="")
    orders.close_order(ns.order, user=owner, reason="Customer cancelled")
    ns.order.refresh_from_db()
    assert ns.order.status == "closed" and ns.order.closed_by == owner
    assert gl(company, "stock_wip", factory) == D("0.00") and gl(company, "wip_written_off", factory) == D("9030.00")
    assert not Bundle.objects.filter(status__in=Bundle.LIVE).exists() and wip_qty(ns, "Process Area") == 0
    assert costing.lot_cost(ns.lot) == D("0.00") and not costing.check_wip_reconciles(company)


# ---------------- scoping ----------------

def test_production_data_is_scoped_to_the_users_factories(company, factory, factory2, owner, accountant):
    from production.models import Lot

    ns = build(company, factory, owner)
    assert Lot.objects.for_user(owner).count() == 1 and Lot.objects.for_user(accountant).count() == 1
    draft = orders.create_order(company=company, factory=factory, date=DAY, user=owner, lines=[
        orders.OrderLineSpec(ns.style, ns.black, 5, {ns.sizes["M"]: 1})])
    accountant.allowed_factories.set([factory2])
    assert Lot.objects.for_user(accountant).count() == 0 and ProductionOrder.objects.for_user(accountant).count() == 0
    with pytest.raises(FactoryNotAllowed):
        orders.release_order(draft, user=accountant)


# ---------------- no-loss stages ----------------

def test_a_no_loss_stage_refuses_loss_rejection_and_shortage_when_pieces_leave_it(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles, "IRON", counts={bundles[0].pk: bundle_service.Count(loss=1)})   # a loss leaving stitching is fine
    assert Process.objects.get(code="IRON").no_loss
    for count in (bundle_service.Count(loss=1), bundle_service.Count(rejection=1), bundle_service.Count(shortage=1)):
        with pytest.raises(BusinessRuleError, match="allows no loss"):
            go(ns, bundles, "FINISH", counts={bundles[1].pk: count})
    assert all(b.current_step == step(ns, "IRON") for b in Bundle.objects.filter(lot=ns.lot))   # nothing moved
    go(ns, bundles, "FINISH")
    Process.objects.filter(code="FINISH").update(no_loss=True)      # the flag is a setting on the process
    with pytest.raises(BusinessRuleError, match="allows no loss"):
        go(ns, bundles, "QC", counts={bundles[1].pk: bundle_service.Count(rejection=2)})


# ---------------- in-house cutting labour, rework flag ----------------

def test_in_house_cutting_labour_is_added_to_lot_cost_on_the_pieces_cut(company, factory, owner):
    ns = build(company, factory, owner)
    routes.reassign_step(step(ns, "CUT"), user=owner, reason="Cutting rate", assignment="in_house", rate=D("2"))
    cut(ns)
    assert costing.cost_breakdown(ns.lot)["labour"] == D("200.00")     # 100 pieces cut x 2
    assert gl(company, "labour_absorbed", factory) == D("-200.00") and gl(company, "stock_wip", factory) == D("9230.00")
    assert not costing.check_wip_reconciles(company)


def test_cutting_with_no_rate_adds_no_labour(company, factory, owner):
    ns = build(company, factory, owner)
    cut(ns)
    assert costing.cost_breakdown(ns.lot)["labour"] == D("0.00") and gl(company, "labour_absorbed", factory) == D("0.00")


def test_a_reworked_bundle_goes_back_to_the_normal_rate_once_it_moves_on(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns, stitch_rate="10")
    routes.reassign_step(step(ns, "IRON"), user=owner, reason="Ironing rate", assignment="in_house", rate=D("3"), rework_rate=D("1"))
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles, "IRON")
    go(ns, bundles[:1], "STITCH", reason="Redo")
    go(ns, bundles[:1], "IRON")                         # the redone stitching: rework rate
    assert not Bundle.objects.get(pk=bundles[0].pk).is_rework
    before = costing.cost_breakdown(ns.lot)["labour"]
    go(ns, bundles[:1], "FINISH")                       # ironing after it: the normal rate again
    assert costing.cost_breakdown(ns.lot)["labour"] - before == D("51.00")   # 17 pieces x 3


# ---------------- pieces expected from fabric, loss in cutting ----------------

def test_fabric_issued_says_how_many_pieces_it_should_give(company, factory, owner):
    ns = build(company, factory, owner)
    issue = cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=owner, date=DAY, estimated_pieces=150)
    assert issue.expected_pieces == 150                      # the cutting master's own figure for these 60 kg
    assert cutting.fabric_with_lot(ns.lot) == D("60") and cutting.estimated_pieces(ns.lot) == 150
    entry = cutting.record_cutting(
        lot=ns.lot, user=owner, date=DAY, pieces={ns.sizes["M"]: 50, ns.sizes["L"]: 50},
        rolls=[cutting.RollUseSpec(ns.roll_a, used=D("41"), waste=D("2"), remnant=D("17"))])
    assert entry.expected_pieces == 107                      # 43 kg burnt at 2.5 pieces a kg
    assert cutting.fabric_with_lot(ns.lot) == D("43")        # the remnant went back to the store
    assert cutting.estimated_pieces(ns.lot) == 107           # so the lot is judged on the fabric it kept


def test_estimates_of_several_issues_add_up_and_a_bad_estimate_is_refused(company, factory, owner):
    ns = build(company, factory, owner)
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("40"))], user=owner, date=DAY, estimated_pieces=100)
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_b, D("20"))], user=owner, date=DAY, estimated_pieces=40)
    assert cutting.estimated_pieces(ns.lot) == 140 and cutting.estimated_pieces(ns.lot, D("30")) == 70
    for bad in (0, -5, D("12.5"), True):
        with pytest.raises(BusinessRuleError, match="whole number above zero"):
            cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("1"))], user=owner, date=DAY, estimated_pieces=bad)


def test_fabric_issued_with_no_estimate_is_cut_with_no_comparison(company, factory, owner):
    ns = build(company, factory, owner)
    cut(ns)
    assert ns.lot.fabric_issues.get().expected_pieces is None and cutting.estimated_pieces(ns.lot) is None
    assert ns.entry.expected_pieces is None and ns.entry.variance_pct is None and not ns.entry.over_tolerance


def test_pieces_lost_in_cutting_are_left_out_of_the_bundles(company, factory, owner):
    ns = build(company, factory, owner)
    routes.reassign_step(step(ns, "CUT"), user=owner, reason="Cutting rate", assignment="in_house", rate=D("2"))
    bundles = cut(ns, loss={ns.sizes["M"]: 2})
    assert sum(b.qty for b in bundles) == 98 and wip_qty(ns, "Cutting Floor") == 98
    assert sorted(b.qty for b in bundles if b.sku.size == ns.sizes["M"]) == [6, 25]      # 33 cut, 2 lost
    m = ns.entry.sizes.get(size=ns.sizes["M"])
    assert (m.pieces, m.loss, m.good) == (33, 2, 31)
    assert costing.cost_breakdown(ns.lot)["fabric"] == D("9030.00")     # the lost pieces' fabric stays in the lot
    assert costing.cost_breakdown(ns.lot)["labour"] == D("200.00")      # cutters are paid on the 100 pieces cut
    assert not costing.check_wip_reconciles(company)


def test_cutting_loss_can_be_given_with_the_lay_and_cannot_exceed_the_pieces_cut(company, factory, owner):
    from django.db import IntegrityError, transaction

    ns = build(company, factory, owner)
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=owner, date=DAY)
    rolls = [cutting.RollUseSpec(ns.roll_a, used=D("41"), waste=D("2"), remnant=D("17"))]
    with pytest.raises(BusinessRuleError, match="cannot be more than"):
        cutting.record_cutting(lot=ns.lot, user=owner, date=DAY, pieces={ns.sizes["M"]: 10}, rolls=rolls, loss={ns.sizes["M"]: 11})
    with pytest.raises(BusinessRuleError, match="cannot be more than"):
        cutting.record_cutting(lot=ns.lot, user=owner, date=DAY, pieces={ns.sizes["M"]: 10}, rolls=rolls, loss={ns.sizes["L"]: 1})
    entry = cutting.record_cutting(lot=ns.lot, user=owner, date=DAY, pieces={ns.sizes["M"]: 10}, rolls=rolls, loss={ns.sizes["M"]: 10})
    with pytest.raises(BusinessRuleError, match="cannot be more than"):
        cutting.create_bundles(entry, bundle_size=25, user=owner, loss={ns.sizes["M"]: 12})
    assert cutting.create_bundles(entry, bundle_size=25, user=owner) == []     # every piece was lost: nothing to bundle
    with pytest.raises(IntegrityError), transaction.atomic():
        entry.sizes.update(loss=11)                                            # the database refuses it too


# ---------------- boxes at packing ----------------

def test_boxes_are_worked_out_from_pieces_per_box_one_sku_to_a_box(company, factory, owner):
    from masters.models import SKU
    from masters.services.styles import pieces_per_box
    from production.services import boxes

    ns = build(company, factory, owner, with_stock=False)
    m = SKU.objects.get(style=ns.style, colour=ns.black, size=ns.sizes["M"])
    s = SKU.objects.get(style=ns.style, colour=ns.black, size=ns.sizes["S"])
    assert pieces_per_box(ns.style, company) == 0 and boxes.plan({m: 33}, company) == []      # not set: no boxes
    company.pieces_per_box = 12
    company.save()
    (line,) = boxes.plan({m: 33}, company)
    assert (line.per_box, line.full_boxes, line.short_box_qty, line.boxes) == (12, 2, 9, 3)
    ns.style.pieces_per_box = 10                                            # the style's own setting wins
    ns.style.save()
    m, s = SKU.objects.get(pk=m.pk), SKU.objects.get(pk=s.pk)
    first, second = boxes.plan({m: 33, s: 20}, company)
    assert (first.sku, first.full_boxes, first.short_box_qty) == (s, 2, 0)                      # sizes in order
    assert (second.sku, second.full_boxes, second.short_box_qty) == (m, 3, 3)
    assert boxes.describe([first, second]) == "5 boxes of 10 and 1 short box of 3"
    assert boxes.describe([]) == ""


def test_packing_records_the_boxes_and_changes_nothing_in_stock_or_the_books(company, factory, owner):
    from production.models import PackEntry
    from production.services import boxes

    ns = build(company, factory, owner)
    bundles = finish_route(ns)
    bundle_service.pack_bundles(bundles=bundles[:1], user=owner, date=DAY)          # pieces per box not set
    assert not PackEntry.objects.exists()
    finished, wip = gl(company, "stock_finished", factory), gl(company, "stock_wip", factory)
    cost_before = costing.lot_cost(ns.lot, factory)
    company.pieces_per_box = 12
    company.save()
    bundle_service.pack_bundles(bundles=bundles[1:3], user=owner, date=DAY)         # B002 + B003: 33 pieces of M
    entry = PackEntry.objects.get()
    line = entry.lines.get()
    assert (line.pieces, line.pieces_per_box, line.full_boxes, line.short_box_qty) == (33, 12, 2, 9)
    assert entry.boxes == 3 and entry.factory == factory and entry.location.name == "Dispatch"
    labels = boxes.labels_for(entry)
    assert [(l["qty"], l["no"], l["total"], l["short"]) for l in labels] == [(12, 1, 3, False), (12, 2, 3, False), (9, 3, 3, True)]
    # the same money moved as a pack without boxes would move: 33 of the 83 pieces left
    relieved = gl(company, "stock_finished", factory) - finished
    assert relieved == (cost_before * 33 / 83).quantize(D("0.01")) and gl(company, "stock_wip", factory) == wip - relieved
    dispatch = Location.objects.get(factory=factory, name="Dispatch")
    assert StockBalance.objects.get(location=dispatch, sku=line.sku).qty == 33      # stock is in pieces, not boxes
    assert not costing.check_wip_reconciles(company)


def test_the_database_refuses_boxes_that_do_not_add_up(company, factory, owner):
    from django.db import IntegrityError, transaction

    from production.models import PackEntry, PackEntryLine

    ns = build(company, factory, owner)
    bundles = finish_route(ns)
    company.pieces_per_box = 12
    company.save()
    bundle_service.pack_bundles(bundles=bundles[:1], user=owner, date=DAY)
    line = PackEntry.objects.get().lines.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        PackEntryLine.objects.filter(pk=line.pk).update(full_boxes=5)


# ---------------- taking loss out without moving ----------------

def test_loss_can_be_taken_out_of_a_bundle_where_it_stands(company, factory, owner):
    ns = build(company, factory, owner)
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    b = bundles[1]                                                          # 25 pieces
    Count = bundle_service.Count
    with pytest.raises(BusinessRuleError, match="reason"):
        bundle_service.count_bundles(bundles=[b], counts={b.pk: Count(loss=1)}, user=owner, reason=" ")
    with pytest.raises(BusinessRuleError, match="enter the pieces"):
        bundle_service.count_bundles(bundles=[b], counts={}, user=owner, reason="x")
    (m,) = bundle_service.count_bundles(bundles=[b], counts={b.pk: Count(loss=1, rejection=2)}, user=owner, date=DAY,
                                        reason="Stained at the table")
    b.refresh_from_db()
    assert (m.kind, m.qty_out, m.qty_in, m.loss, m.rejection) == ("write_off", 25, 22, 1, 2)       # BR-21 holds
    assert b.qty == 22 and b.status == "at_stage" and b.current_step == step(ns, "STITCH")         # it did not move
    assert wip_qty(ns, "Process Area") == 97 and wip_qty(ns, "Rejects") == 2
    go(ns, bundles, "IRON")
    with pytest.raises(BusinessRuleError, match="allows no loss"):                                  # not at a no-loss stage
        bundle_service.count_bundles(bundles=[b], counts={b.pk: Count(loss=1)}, user=owner, reason="x")


def test_loss_cannot_be_taken_out_of_a_bundle_that_is_with_a_fabricator(company, factory, owner):
    from jobwork.services import challans, rates

    ns = build(company, factory, owner)
    bundles = cut(ns)
    fab = fabricator(company)
    rates.save_rate(party=fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), effective_from=DAY)
    challans.create_and_issue(company=company, factory=factory, party=fab, lot=ns.lot, step=step(ns, "STITCH"),
                              bundles=bundles[:1], date=DAY, user=owner)
    with pytest.raises(BusinessRuleError, match="with a fabricator"):
        bundle_service.count_bundles(bundles=bundles[:1], counts={bundles[0].pk: bundle_service.Count(shortage=1)},
                                     user=owner, reason="x")
    stranger = make_user("elsewhere")
    with pytest.raises(FactoryNotAllowed):
        bundle_service.count_bundles(bundles=bundles[1:2], counts={bundles[1].pk: bundle_service.Count(loss=1)},
                                     user=stranger, reason="x")
