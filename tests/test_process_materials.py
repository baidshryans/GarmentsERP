"""Materials by process (E2.2, E7.6, E8.1; owner's decision, Oct 2026).

The style's list holds accessories and packing materials, each used in one process; the pieces from the step before
are that process's other input. The list fills in what a step needs, the user confirms or changes it, and what was
confirmed leaves the store into the lot's cost: with the bundle move for an in-house step, at packing, or on the
challan for a fabricator's step.
"""
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.models import Location, Role
from inventory.exceptions import InsufficientStock
from inventory.services import stock
from inventory.services.opening import OpeningItem, post_opening_stock
from jobwork.services import challans, rates
from masters.models import Material, Process, Unit
from masters.services import boms, styles
from production.models import Bundle, ProductionOrder
from production.services import bundles as bundle_service
from production.services import costing, materials, orders, routes
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, gl, go, step


@pytest.fixture
def ns(company, factory, owner):
    """The usual lot, with a list of: 1 zipper a piece (stitching, by its kind), 1 wash label a piece at finishing,
    and 1 polybag a piece with 2% wastage (packing, by its kind)."""
    ns = build(company, factory, owner)
    pcs = Unit.objects.get(code="PCS")
    ns.label = Material.objects.create(code="LBL-1", name="Wash label", kind="trim", unit=pcs)
    ns.polybag = Material.objects.create(code="PB-1", name="Polybag", kind="packing", unit=pcs)
    post_opening_stock(company=company, factory=factory, user=owner,
                       location=Location.objects.get(factory=factory, name="Main Godown"),
                       entries=[OpeningItem(ns.label, D("500"), D("0.5")), OpeningItem(ns.polybag, D("300"), D("1"))])
    version, _ = boms.save_bom(ns.style, user=owner, lines=[
        boms.BomLineSpec(ns.zipper, D("1")),
        boms.BomLineSpec(ns.label, D("1"), process=Process.objects.get(code="FINISH")),
        boms.BomLineSpec(ns.polybag, D("1"), wastage_pct=D("2"))])
    ns.lot.bom_version = version
    ns.lot.save()
    return ns


def in_house(ns):
    """Stitch in-house at no rate and skip the optional value-add steps."""
    routes.reassign_step(step(ns, "STITCH"), user=ns.owner, reason="Stitch in-house", assignment="in_house", rate=D("0"))
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=ns.owner, reason="Not needed")


def login(user):
    c = Client()
    c.force_login(user)
    return c


# ---------------- in-house steps ----------------

def test_an_in_house_move_issues_the_materials_that_were_confirmed(ns, company, factory):
    in_house(ns)
    bundles = cut(ns)                                           # S17, M25, M8, L25, L8, XL17
    stitch = step(ns, "STITCH")
    assert materials.needs_on_entry(ns.lot, stitch, bundles) == {ns.zipper: D("100.000")}    # only stitching's own
    go(ns, bundles[:1], "STITCH")                               # moved with no materials: nothing leaves the store
    assert not ns.lot.material_issues.exists() and stock.on_hand(factory, ns.zipper) == (D("1000.000"), D("2000.00"))

    go(ns, bundles[1:3], "STITCH", materials=[(ns.zipper, D("30")), (ns.label, D("5"))])     # changed, and one added
    issue = ns.lot.material_issues.get()
    assert issue.step == stitch and issue.pieces == 33 and issue.factory == factory
    assert {l.material: (l.qty, l.value) for l in issue.lines.all()} == {
        ns.zipper: (D("30.000"), D("60.00")), ns.label: (D("5.000"), D("2.50"))}
    assert stock.on_hand(factory, ns.zipper) == (D("970.000"), D("1940.00"))
    assert stock.on_hand(factory, ns.label) == (D("495.000"), D("247.50"))
    assert costing.cost_breakdown(ns.lot)["trim"] == D("62.50")
    assert gl(company, "stock_wip", factory) == D("9092.50")    # 9,030 fabric + 62.50 materials
    assert not costing.check_wip_reconciles(company)


def test_a_bundle_coming_back_to_a_step_needs_no_more_materials(ns):
    in_house(ns)
    bundles = cut(ns)
    stitch, finish = step(ns, "STITCH"), step(ns, "FINISH")
    go(ns, bundles[:2], "STITCH")
    go(ns, bundles[:1], "IRON")
    assert materials.needs_on_entry(ns.lot, finish, bundles[:1]) == {ns.label: D("17.000")}  # first time at finishing
    back = Bundle.objects.get(pk=bundles[0].pk)
    assert materials.needs_on_entry(ns.lot, stitch, [back]) == {}                            # rework at stitching
    fresh = Bundle.objects.get(pk=bundles[3].pk)                                             # L25, never stitched
    assert materials.needs_on_entry(ns.lot, stitch, [back, fresh]) == {ns.zipper: D("25.000")}
    child = bundle_service.split_bundle(Bundle.objects.get(pk=bundles[1].pk), 5, user=ns.owner, date=DAY)
    assert materials.been_at(child, stitch)                     # pieces split off were stitched with their bundle


def test_too_little_stock_stops_the_move_and_nothing_is_saved(ns, factory):
    in_house(ns)
    bundles = cut(ns)
    with pytest.raises(InsufficientStock):
        go(ns, bundles, "STITCH", materials=[(ns.zipper, D("5000"))])
    assert Bundle.objects.get(pk=bundles[0].pk).current_step is None and not ns.lot.material_issues.exists()
    assert stock.on_hand(factory, ns.zipper) == (D("1000.000"), D("2000.00"))


def test_materials_are_checked_before_anything_moves(ns):
    in_house(ns)
    bundles = cut(ns)
    for lines, message in (([(ns.fabric, D("1"))], "is fabric"), ([(ns.zipper, D("1")), (ns.zipper, D("2"))], "twice"),
                           ([(ns.zipper, D("0"))], "above zero"), ([(ns.zipper, D("-1"))], "above zero")):
        with pytest.raises(BusinessRuleError, match=message):
            go(ns, bundles, "STITCH", materials=lines)
    assert Bundle.objects.get(pk=bundles[0].pk).current_step is None


# ---------------- packing ----------------

def test_packing_materials_are_issued_at_packing_and_carried_by_the_finished_pieces(ns, company, factory):
    in_house(ns)
    bundles = cut(ns)
    for code in ("STITCH", "IRON", "FINISH", "QC"):
        go(ns, bundles, code)
    pack = step(ns, "PACK")
    assert materials.needs_on_entry(ns.lot, pack, bundles) == {}             # not on reaching the packing step
    go(ns, bundles, "PACK")
    live = list(Bundle.objects.filter(lot=ns.lot))
    assert materials.needs_at_packing(ns.lot, bundle_service.packing_step(ns.lot), live) == {ns.polybag: D("102.000")}
    bundle_service.pack_bundles(bundles=live, user=ns.owner, date=DAY, materials=[(ns.polybag, D("102"))])
    assert ns.lot.material_issues.get().step == pack and stock.on_hand(factory, ns.polybag) == (D("198.000"), D("198.00"))
    assert gl(company, "stock_finished", factory) == D("9132.00")           # 9,030 fabric + 102 polybags
    assert costing.lot_cost(ns.lot) == D("0.00") and gl(company, "stock_wip", factory) == D("0.00")
    assert not costing.check_wip_reconciles(company)


# ---------------- a fabricator's step ----------------

def test_a_challan_fills_in_its_own_process_and_the_draft_can_be_changed(ns, company, factory):
    fab = fabricator(company)
    stitch = step(ns, "STITCH")
    rates.save_rate(party=fab, process=stitch.process, rate_type="A", base_rate=D("25"), effective_from=date(2026, 4, 1))
    bundles = cut(ns)
    ch = challans.create_challan(company=company, factory=factory, party=fab, lot=ns.lot, step=stitch, bundles=bundles[:3],
                                 date=DAY, user=ns.owner)
    assert {t.material: t.qty_issued for t in ch.trims.all()} == {ns.zipper: D("50.000")}    # no label, no polybag

    for lines, message in (([(ns.fabric, D("1"))], "is fabric"), ([(ns.zipper, D("1")), (ns.zipper, D("1"))], "twice")):
        with pytest.raises(BusinessRuleError, match=message):
            challans.set_materials(ch, lines=lines, user=ns.owner)
    with pytest.raises(FactoryNotAllowed):
        challans.set_materials(ch, lines=[(ns.zipper, D("1"))], user=make_user("stranger"))
    challans.set_materials(ch, lines=[(ns.zipper, D("48")), (ns.label, D("50"))], user=ns.owner)
    ch = challans.issue_challan(ch, user=ns.owner)
    assert {t.material: (t.qty_issued, t.value) for t in ch.trims.all()} == {
        ns.zipper: (D("48.000"), D("96.00")), ns.label: (D("50.000"), D("25.00"))}
    assert stock.on_hand(factory, ns.zipper)[0] == D("952.000") and stock.on_hand(factory, ns.label)[0] == D("450.000")
    assert costing.cost_breakdown(ns.lot)["trim"] == D("121.00")
    with pytest.raises(BusinessRuleError, match="while the challan is a draft"):
        challans.set_materials(ch, lines=[], user=ns.owner)

    bare = challans.create_challan(company=company, factory=factory, party=fab, lot=ns.lot, step=stitch, bundles=bundles[3:4],
                                   date=DAY, user=ns.owner)
    challans.set_materials(bare, lines=[], user=ns.owner)       # the fabricator brings their own
    bare = challans.issue_challan(bare, user=ns.owner)
    assert not bare.trims.exists() and bare.voucher is None and stock.on_hand(factory, ns.zipper)[0] == D("952.000")
    assert not costing.check_wip_reconciles(company)


def test_a_challan_for_any_process_carries_that_process_materials(ns, company, factory):
    in_house(ns)
    finish = step(ns, "FINISH")
    fab = fabricator(company, "Verma Finishing", "9833333344")
    routes.reassign_step(finish, user=ns.owner, reason="Finish outside", assignment="subcontract", party=fab, rate=D("2"))
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles, "IRON")
    ch = challans.create_challan(company=company, factory=factory, party=fab, lot=ns.lot, step=finish,
                                 bundles=list(Bundle.objects.filter(lot=ns.lot)), date=DAY, user=ns.owner)
    assert {t.material: t.qty_issued for t in ch.trims.all()} == {ns.label: D("100.000")}


# ---------------- a route that lacks the process ----------------

def test_a_material_whose_process_is_not_on_the_route_is_pointed_out(ns, owner):
    assert materials.unused_lines(ns.lot) == []
    version, _ = boms.save_bom(ns.style, user=owner, lines=[
        boms.BomLineSpec(ns.zipper, D("1")), boms.BomLineSpec(ns.label, D("1"), process=Process.objects.get(code="EMB"))])
    ns.lot.bom_version = version
    ns.lot.save()
    assert materials.unused_lines(ns.lot) == []                 # embroidery is an optional step of the route
    in_house(ns)                                                # ... until it is skipped
    assert [l.material for l in materials.unused_lines(ns.lot)] == [ns.label]
    page = login(owner).get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "Not on this route" in page and "Wash label (Embroidery)" in page


# ---------------- through the screens ----------------

def test_the_pack_screen_asks_for_the_packing_materials_first(ns, factory, owner):
    in_house(ns)
    bundles = cut(ns)
    for code in ("STITCH", "IRON", "FINISH", "QC", "PACK"):
        go(ns, bundles, code)
    c = login(owner)
    form = {"bundle": [b.pk for b in bundles]}
    ask = c.post(reverse("pack_bundles", args=[ns.lot.pk]), form)
    page = ask.content.decode()
    assert ask.status_code == 200 and "Packing materials" in page and "Polybag" in page and 'value="102"' in page
    assert not Bundle.objects.filter(lot=ns.lot, status="packed").exists()         # the trial run left nothing behind
    r = c.post(reverse("pack_bundles", args=[ns.lot.pk]), {
        **form, "materials_step": "1", "mat_material": [ns.polybag.pk, ns.label.pk, ""], "mat_qty": ["100", "", ""]})
    assert r.status_code == 302 and Bundle.objects.filter(lot=ns.lot, status="packed").count() == 6
    assert ns.lot.material_issues.get().lines.get().qty == D("100.000")           # the label row was left empty
    page = c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "Materials used in-house" in page and "Polybag 100 PCS" in page


def test_the_move_screen_can_issue_materials_that_are_not_on_the_list(ns, factory, owner):
    in_house(ns)
    bundles = cut(ns)
    for code in ("STITCH", "IRON"):
        go(ns, bundles, code)
    sup = make_user("sup")
    sup.roles.add(Role.objects.get(name="Production Supervisor"))
    sup.allowed_factories.add(factory)
    c = login(sup)
    qc_move = {"lot": ns.lot.pk, "bundle": [bundles[0].pk], "to_step": step(ns, "QC").pk}
    bad = c.post(reverse("move_bundles"), {**qc_move, "with_materials": "on"})     # finishing is mandatory first
    assert bad.status_code == 200 and b"mandatory" in bad.content and b"Materials for" not in bad.content
    move = {"lot": ns.lot.pk, "bundle": [bundles[0].pk], "to_step": step(ns, "FINISH").pk}
    ask = c.post(reverse("move_bundles"), move)
    assert ask.status_code == 200 and "Materials for Thread cutting and finishing" in ask.content.decode()
    assert 'value="17"' in ask.content.decode()                                    # 17 labels for the 17 pieces
    short = c.post(reverse("move_bundles"), {**move, "materials_step": "1", "mat_material": [ns.label.pk], "mat_qty": ["9999"]})
    assert short.status_code == 200 and 'value="9999"' in short.content.decode()   # back on the materials step
    assert Bundle.objects.get(pk=bundles[0].pk).current_step == step(ns, "IRON")
    r = c.post(reverse("move_bundles"), {**move, "materials_step": "1", "mat_material": [ns.label.pk, ns.zipper.pk],
                                         "mat_qty": ["17", "2"]})
    assert r.status_code == 302
    assert {l.material: l.qty for l in ns.lot.material_issues.get().lines.all()} == {ns.label: D("17.000"), ns.zipper: D("2.000")}


def test_the_draft_challan_screen_changes_the_materials_and_issues_with_them(ns, company, factory, owner):
    fab = fabricator(company)
    stitch = step(ns, "STITCH")
    rates.save_rate(party=fab, process=stitch.process, rate_type="A", base_rate=D("25"), effective_from=date(2026, 4, 1))
    bundles = cut(ns)
    ch = challans.create_challan(company=company, factory=factory, party=fab, lot=ns.lot, step=stitch, bundles=bundles[:1],
                                 date=DAY, user=owner)
    c = login(owner)
    url = reverse("challan_detail", args=[ch.pk])
    page = c.get(url).content.decode()
    assert "Materials going with the bundles" in page and 'value="17"' in page and "Add a material" in page
    r = c.post(url, {"action": "materials", "mat_material": [ns.zipper.pk, ns.label.pk], "mat_qty": ["16", "17"]}, follow=True)
    assert b"Materials saved" in r.content and {t.material: t.qty_issued for t in ch.trims.all()} == {
        ns.zipper: D("16.000"), ns.label: D("17.000")}
    c.post(url, {"action": "issue", "mat_material": [ns.zipper.pk, ns.label.pk], "mat_qty": ["16", ""]})
    ch.refresh_from_db()
    assert ch.status == "issued" and ch.trims.get().material == ns.zipper and stock.on_hand(factory, ns.zipper)[0] == D("984.000")
    assert "Materials issued" in c.get(url).content.decode()


def test_releasing_an_order_for_a_style_with_no_list_says_so_and_goes_ahead(ns, company, factory, owner):
    bare = styles.create_style(company=company, style_no="JGR-2", product=ns.style.product, name="Plain jogger",
                               colours=[ns.black], sizes=list(ns.sizes.values()))
    bare.default_route = ns.style.default_route
    bare.save()
    order = orders.create_order(company=company, factory=factory, date=DAY, user=owner,
                                lines=[orders.OrderLineSpec(bare, ns.black, 10, {ns.sizes["M"]: 1})])
    r = login(owner).post(reverse("order_detail", args=[order.pk]), {"action": "release"}, follow=True)
    assert ProductionOrder.objects.get(pk=order.pk).status == "released"
    assert "JGR-2: no material list on the style" in r.content.decode()
