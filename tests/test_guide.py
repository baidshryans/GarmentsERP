"""The guide: where a lot is on its way to finished goods and the one thing it needs next (guided Making, piece 2a)."""
from datetime import date

import pytest
from django.urls import reverse

from core.models import Role, RolePermission
from jobwork.services import challans, rates, receipts
from jobwork.services.receipts import Counted
from production.models import Bundle
from production.services import bundles as bundle_service
from production.services import cutting, orders, routes
from production.services.guide import lot_guide, order_next
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, go, step

HALF = slice(0, 3)  # B001 S17 + B002 M25 + B003 M8 = 50 of the 100 pieces


@pytest.fixture
def ns(company, factory, owner):
    ns = build(company, factory, owner)
    ns.bundles = cut(ns)  # B001 S17, B002 M25, B003 M8, B004 L25, B005 L8, B006 XL17
    ns.fab = fabricator(company)
    rates.save_rate(party=ns.fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), rework_rate=D("5"),
                    effective_from=date(2026, 4, 1))
    return ns


def draft(ns, bundles, **kw):
    return challans.create_challan(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                   bundles=bundles, date=DAY, user=ns.owner, **kw)


def issue(ns, bundles, **kw):
    return challans.issue_challan(draft(ns, bundles, **kw), user=ns.owner)


def receive(ns, challan, counts=None):
    counts = counts if counts is not None else {cb: cb.qty_issued for cb in challan.bundles.all()}
    return receipts.create_receipt(challan=challan, user=ns.owner, date=DAY, counts=[Counted(cb, n) for cb, n in counts.items()])


def stitch_goes_to(ns, fab):
    return routes.reassign_step(step(ns, "STITCH"), user=ns.owner, reason="test", assignment="subcontract", party=fab,
                                factory=None, rate=D("25"), rework_rate=D("5"))


def stitch_in_house(ns):
    return routes.reassign_step(step(ns, "STITCH"), user=ns.owner, reason="test", assignment="in_house")


def primary(ns, user=None):
    return lot_guide(ns.lot, user or ns.owner)["primary"]


def stage(guide, label):
    return next(s for s in guide["journey"] if s["label"] == label)


def labels(guide):
    return [a["label"] for a in [guide["primary"], *guide["others"]] if a]


# ---------------- fabric, cutting, bundles ----------------

def test_a_released_lot_needs_fabric_first(company, factory, owner):
    ns = build(company, factory, owner)
    g = lot_guide(ns.lot, owner)
    assert g["primary"]["label"] == "Issue fabric" and g["primary"]["url"] == reverse("lot_fabric", args=[ns.lot.pk])
    names = [s["label"] for s in g["journey"]]
    assert names[:3] == ["Order", "Fabric", "Cut"] and names[-1] == "Finished goods"
    # the cutting step is the Cut stage itself; every other step of the route follows in order
    assert names[3:-1] == ["Stitching", "Embroidery", "Printing", "Washing", "Ironing and pressing",
                           "Thread cutting and finishing", "Quality check", "Packing"]
    assert [s["state"] for s in g["journey"]][:3] == ["done", "now", "todo"]
    assert not g["complete"] and not g["closed"] and g["others"] == [] and g["waiting"] == ""


def test_once_fabric_is_issued_the_lot_needs_cutting(company, factory, owner):
    ns = build(company, factory, owner)
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=owner, date=DAY)
    g = lot_guide(ns.lot, owner)
    assert g["primary"]["label"] == "Record cutting" and g["primary"]["url"] == reverse("lot_cutting", args=[ns.lot.pk])
    assert g["others"] == []
    assert stage(g, "Fabric")["state"] == "done" and stage(g, "Cut")["state"] == "now"


def test_a_lay_that_is_cut_needs_bundles(company, factory, owner):
    ns = build(company, factory, owner)
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=owner, date=DAY)
    cutting.record_cutting(lot=ns.lot, user=owner, date=DAY,
                           pieces={ns.sizes["S"]: 17, ns.sizes["M"]: 33, ns.sizes["L"]: 33, ns.sizes["XL"]: 17},
                           rolls=[cutting.RollUseSpec(ns.roll_a, used=D("41"), waste=D("2"), remnant=D("17"))])
    g = lot_guide(ns.lot, owner)
    assert g["primary"]["label"] == "Make bundles" and g["primary"]["url"] == reverse("lot_cutting", args=[ns.lot.pk])
    assert g["others"] == [] and stage(g, "Cut")["state"] == "now"


# ---------------- moving on: in-house or to a fabricator ----------------

def test_cut_bundles_move_to_the_next_in_house_step(ns):
    stitch_in_house(ns)
    nxt = ns.lot.steps.exclude(status="skipped").filter(sequence__gt=ns.bundles[0].completed_seq).order_by("sequence").first()
    assert nxt.process.code == "STITCH" and nxt.assignment == "in_house"
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == f"Move to {nxt.process.name}" == "Move to Stitching"
    assert g["primary"]["url"] == reverse("move_bundles") + f"?lot={ns.lot.pk}&back=1"
    assert g["primary"]["pieces"] == 100 and g["others"] == []
    assert stage(g, "Cut")["state"] == "done" and stage(g, "Cut")["pieces"] == 100


def test_cut_bundles_go_to_the_fabricator_when_the_next_step_is_subcontracted(ns):
    st = step(ns, "STITCH")
    url = reverse("challan_new") + f"?lot={ns.lot.pk}&step={st.pk}"
    # the standard route subcontracts stitching without naming anyone
    p = primary(ns)
    assert p["label"] == "Send to a fabricator for Stitching" and p["url"] == url and p["pieces"] == 100
    stitch_goes_to(ns, ns.fab)
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == f"Send to {ns.fab.name} for {st.process.name}" == "Send to Sharma Stitching for Stitching"
    assert g["primary"]["url"] == url and g["primary"]["pieces"] == 100 and g["others"] == []
    assert stage(g, "Stitching")["detail"] == ns.fab.name and stage(g, "Stitching")["state"] == "todo"


def test_a_draft_challan_is_issued_before_anything_else_is_asked_of_its_bundles(ns):
    ch = draft(ns, ns.bundles)
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == f"Issue challan to {ns.fab.name}"
    assert g["primary"]["url"] == reverse("challan_detail", args=[ch.pk]) and g["primary"]["pieces"] == 100
    assert g["others"] == []  # the bundles on the draft do not also ask to be sent


def test_bundles_with_a_fabricator_are_received(ns):
    ch = issue(ns, ns.bundles)
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == f"Receive from {ns.fab.name}"
    assert g["primary"]["url"] == reverse("receipt_new", args=[ch.pk]) and g["primary"]["pieces"] == 100
    assert g["others"] == []
    st = stage(g, "Stitching")
    assert (st["state"], st["pieces"], st["detail"]) == ("now", 100, ns.fab.name)


def test_what_is_furthest_behind_comes_first(ns):
    ch = issue(ns, ns.bundles[HALF])
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == f"Send to {ns.fab.name} for Stitching" and g["primary"]["pieces"] == 50
    assert g["primary"]["url"] == reverse("challan_new") + f"?lot={ns.lot.pk}&step={step(ns, 'STITCH').pk}"
    assert [(a["label"], a["url"], a["pieces"]) for a in g["others"]] == [
        (f"Receive from {ns.fab.name}", reverse("receipt_new", args=[ch.pk]), 50)]


def test_received_pieces_wait_for_qc(ns):
    r = receive(ns, issue(ns, ns.bundles))
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == "Check received pieces" and g["primary"]["url"] == reverse("receipt_detail", args=[r.pk])
    assert g["others"] == []


def test_an_over_receipt_waits_for_the_owner(ns, accountant):
    ch = issue(ns, ns.bundles)
    counts = {cb: cb.qty_issued for cb in ch.bundles.all()}
    counts[next(iter(counts))] += 2
    r = receive(ns, ch, counts)
    assert r.status == "pending_approval"
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == "Approve over-receipt" and g["primary"]["url"] == reverse("receipt_detail", args=[r.pk])
    assert g["others"] == []  # already counted: nobody is asked to receive these bundles again
    # someone who may not approve is told what the lot waits for, with no link
    waits = lot_guide(ns.lot, accountant)
    assert waits["primary"] is None and waits["others"] == [] and waits["waiting"] == "Approve over-receipt"


def test_pieces_qc_sends_back_go_out_for_rework(ns):
    r = receive(ns, issue(ns, ns.bundles))
    b3 = r.lines.get(challan_bundle__bundle=ns.bundles[2])  # B003, 8 pieces
    receipts.record_qc(receipt_line=b3, accepted=0, rework=8, user=ns.owner)
    assert Bundle.objects.get(pk=ns.bundles[2].pk).status == "rework"
    g = lot_guide(ns.lot, ns.owner)
    rework = [a for a in [g["primary"], *g["others"]] if a["label"] == "Send back for rework"]
    assert len(rework) == 1
    assert rework[0]["url"] == reverse("challan_new") + f"?lot={ns.lot.pk}&kind=rework" and rework[0]["pieces"] == 8
    assert labels(g) == ["Check received pieces", "Send back for rework"]  # five lines still wait for QC


# ---------------- optional steps: offered beside the next mandatory one, never instead of it ----------------

def stitched(ns):
    """Every bundle sent out for stitching, counted back in full and accepted by QC."""
    r = receive(ns, issue(ns, ns.bundles))
    for line in r.lines.all():
        receipts.record_qc(receipt_line=line, accepted=line.qty_received, user=ns.owner)
    return r


def optional_send(ns, code, name):
    return (f"Send to a fabricator for {name} (optional)", reverse("challan_new") + f"?lot={ns.lot.pk}&step={step(ns, code).pk}", 100)


def test_after_stitching_the_next_step_is_ironing_and_the_optional_steps_are_offered_beside_it(ns):
    stitched(ns)
    assert {b.status for b in Bundle.objects.filter(lot=ns.lot)} == {"ready"}
    g = lot_guide(ns.lot, ns.owner)
    assert (g["primary"]["label"], g["primary"]["url"], g["primary"]["pieces"]) == (
        "Move to Ironing and pressing", reverse("move_bundles") + f"?lot={ns.lot.pk}&back=1", 100)
    assert [(a["label"], a["url"], a["pieces"]) for a in g["others"]] == [
        optional_send(ns, "EMB", "Embroidery"), optional_send(ns, "PRINT", "Printing"), optional_send(ns, "WASH", "Washing")]
    # the strip still shows every step of the route, and says which ones may be left out
    assert [s["label"] for s in g["journey"] if s["optional"]] == ["Embroidery", "Printing", "Washing"]
    assert not any(s["optional"] for s in g["journey"] if s["label"] in ("Order", "Fabric", "Cut", "Stitching", "Packing", "Finished goods"))


def test_an_optional_step_skipped_on_the_lot_is_not_offered(ns):
    routes.skip_step(step(ns, "PRINT"), user=ns.owner, reason="plain pant")
    stitched(ns)
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == "Move to Ironing and pressing"
    assert [(a["label"], a["url"], a["pieces"]) for a in g["others"]] == [
        optional_send(ns, "EMB", "Embroidery"), optional_send(ns, "WASH", "Washing")]
    assert "Printing" not in [s["label"] for s in g["journey"]]


def test_an_in_house_optional_step_is_a_move_and_still_comes_after_the_mandatory_one(ns):
    routes.reassign_step(step(ns, "WASH"), user=ns.owner, reason="own washing unit", assignment="in_house")
    stitched(ns)
    g = lot_guide(ns.lot, ns.owner)
    move_url = reverse("move_bundles") + f"?lot={ns.lot.pk}&back=1"
    assert g["primary"]["label"] == "Move to Ironing and pressing"
    assert [(a["label"], a["url"]) for a in g["others"]] == [
        optional_send(ns, "EMB", "Embroidery")[:2], optional_send(ns, "PRINT", "Printing")[:2], ("Move to Washing (optional)", move_url)]


def test_bundles_at_different_points_keep_furthest_behind_first_with_optionals_behind_their_own_target(ns):
    stitched(ns)
    go(ns, ns.bundles[HALF], "IRON")
    g = lot_guide(ns.lot, ns.owner)
    # ready after stitching (target Ironing, with its three optional steps), then the half already at Ironing
    assert labels(g) == ["Move to Ironing and pressing", "Send to a fabricator for Embroidery (optional)",
                         "Send to a fabricator for Printing (optional)", "Send to a fabricator for Washing (optional)",
                         "Move to Thread cutting and finishing"]
    assert [a["pieces"] for a in [g["primary"], *g["others"]]] == [50, 50, 50, 50, 50]


def test_a_role_that_may_send_but_not_move_gets_the_optional_sends(ns):
    role = Role.objects.create(name="Job work clerk")
    for action in ("view", "create"):
        RolePermission.objects.create(role=role, screen="jobwork.challan", action=action)
    clerk = make_user("jwclerk")
    clerk.roles.add(role)
    clerk.allowed_factories.add(ns.factory)
    assert clerk.has_screen_perm("jobwork.challan", "create") and not clerk.has_screen_perm("production.move", "create")
    stitched(ns)
    g = lot_guide(ns.lot, clerk)
    # The rule: the primary is the first action the user may do. The mandatory move is not theirs, so an optional
    # send becomes their primary. That is accepted: it is a real thing they can do, and the label says "(optional)".
    assert g["primary"]["label"] == "Send to a fabricator for Embroidery (optional)"
    assert [a["label"] for a in g["others"]] == ["Send to a fabricator for Printing (optional)", "Send to a fabricator for Washing (optional)"]
    assert g["waiting"] == ""  # `waiting` is only for a user who may do nothing at all
    # someone who may do neither is told about the mandatory step, not an optional one
    idle = make_user("idle")
    idle.allowed_factories.add(ns.factory)
    waits = lot_guide(ns.lot, idle)
    assert waits["primary"] is None and waits["others"] == [] and waits["waiting"] == "Move to Ironing and pressing"


def test_when_only_optional_steps_remain_they_are_all_that_is_offered(ns):
    stitch_in_house(ns)
    for code in ("IRON", "FINISH", "QC", "PACK"):
        routes.remove_step(step(ns, code), user=ns.owner, reason="test: a route that ends in optional steps")
    go(ns, ns.bundles, "STITCH")
    g = lot_guide(ns.lot, ns.owner)
    assert labels(g) == ["Send to a fabricator for Embroidery (optional)", "Send to a fabricator for Printing (optional)",
                         "Send to a fabricator for Washing (optional)"]


# ---------------- packing and the end ----------------

def to_packing(ns):
    """All in-house: take every bundle through each mandatory step to the packing table."""
    stitch_in_house(ns)
    for code in ("STITCH", "IRON", "FINISH", "QC", "PACK"):
        go(ns, ns.bundles, code)


def test_bundles_spread_over_two_stages_then_packed_into_finished_goods(ns):
    move_url = reverse("move_bundles") + f"?lot={ns.lot.pk}&back=1"
    stitch_in_house(ns)
    go(ns, ns.bundles, "STITCH")
    g = lot_guide(ns.lot, ns.owner)
    assert (stage(g, "Stitching")["state"], stage(g, "Stitching")["pieces"]) == ("now", 100)
    go(ns, ns.bundles, "IRON")
    go(ns, ns.bundles[HALF], "FINISH")
    g = lot_guide(ns.lot, ns.owner)
    assert (g["primary"]["label"], g["primary"]["url"], g["primary"]["pieces"]) == ("Move to Thread cutting and finishing", move_url, 50)
    assert [(a["label"], a["url"], a["pieces"]) for a in g["others"]] == [("Move to Quality check", move_url, 50)]
    assert stage(g, "Ironing and pressing")["pieces"] == 50 and stage(g, "Thread cutting and finishing")["pieces"] == 50
    assert stage(g, "Stitching")["state"] == "done" and stage(g, "Stitching")["pieces"] is None

    go(ns, ns.bundles[3:], "FINISH")
    go(ns, ns.bundles, "QC")
    go(ns, ns.bundles, "PACK")
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"]["label"] == "Pack into finished goods" and g["primary"]["pieces"] == 100
    assert g["primary"]["url"] == reverse("lot_detail", args=[ns.lot.pk]) + "#pack"
    assert g["others"] == [] and g["journey"][-1]["state"] == "todo"

    bundle_service.pack_bundles(bundles=ns.bundles, user=ns.owner, date=DAY)
    ns.lot.refresh_from_db()
    g = lot_guide(ns.lot, ns.owner)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == "" and g["complete"] is True
    assert (g["journey"][-1]["label"], g["journey"][-1]["state"], g["journey"][-1]["pieces"]) == ("Finished goods", "done", 100)


def test_a_role_that_may_not_do_the_next_step_is_told_what_the_lot_waits_for(company, factory, owner, accountant):
    ns = build(company, factory, owner)
    assert not accountant.has_screen_perm("production.cutting", "create")
    g = lot_guide(ns.lot, accountant)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == "Issue fabric"


def test_a_closed_lot_asks_for_nothing(company, factory, owner):
    ns = build(company, factory, owner)
    orders.close_order(ns.order, user=owner, reason="x")
    ns.lot.refresh_from_db()
    g = lot_guide(ns.lot, owner)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == "" and g["closed"] is True and g["complete"] is False


# ---------------- the order's next step ----------------

def test_order_next_releases_a_draft_then_follows_its_lot_until_the_order_is_complete(ns, accountant):
    blank = orders.create_order(company=ns.company, factory=ns.factory, date=DAY, user=ns.owner, lines=[
        orders.OrderLineSpec(ns.style, ns.black, 10, {ns.sizes["M"]: 1})])
    assert blank.status == "draft"
    assert order_next(blank, ns.owner) == {"release": True}
    assert order_next(blank, accountant) is None  # may view orders, not release them

    ns.order.refresh_from_db()
    nxt = order_next(ns.order, ns.owner)
    assert nxt == primary(ns) and nxt["label"] == "Send to a fabricator for Stitching"

    to_packing(ns)
    bundle_service.pack_bundles(bundles=ns.bundles, user=ns.owner, date=DAY)
    ns.order.refresh_from_db()
    assert ns.order.status == "completed" and order_next(ns.order, ns.owner) is None
