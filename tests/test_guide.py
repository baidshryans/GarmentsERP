"""The guide: where a lot is on its way to finished goods and the one thing it needs next (guided Making, piece 2a)."""
from datetime import date

import re

import pytest
from django.test import Client
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


# ================================================================ the guide on the screens

def login(user):
    c = Client()
    c.force_login(user)
    return c


def user_with(name, role, factory):
    u = make_user(name)
    u.roles.add(Role.objects.get(name=role))
    u.allowed_factories.add(factory)
    return u


def lot_page(ns, user):
    return login(user).get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()


def guide_of(html):
    """The guide island alone: from its opening tag to the next island."""
    start = html.index('class="island guide"')
    return html[start:html.index('class="island"', start)]


def row_with(html, text):
    return next(r for r in re.findall(r"<tr>.*?</tr>", html, re.S) if text in r)


def test_the_lot_page_opens_with_the_journey_and_one_next_button(company, factory, owner):
    ns = build(company, factory, owner)
    html = lot_page(ns, owner)
    g = guide_of(html)
    assert 'class="journey"' in g and 'aria-current="step"' in g
    assert re.search(r'<a class="btn primary" href="%s">Issue fabric</a>' % re.escape(reverse("lot_fabric", args=[ns.lot.pk])), g)
    # the route is folded away, not removed: its table and its change forms are still on the page
    assert "<summary>Route and rates</summary>" in html and '<th scope="col">Process</th>' in html
    assert 'value="reassign"' in html and "<summary>Add a step</summary>" in html
    assert "<summary>Lot cost</summary>" in html
    assert g.count('class="j-tag"') == 3  # embroidery, printing and washing are marked optional
    # only labels, counts and links are shown: the permission and sort keys stay inside the service
    assert "production.cutting" not in html and "jobwork.challan" not in html
    # the four header buttons are gone; fabric, cutting and move live in the corrections row
    head = html[html.index('class="page-head"'):html.index('class="island guide"')]
    assert "Issue fabric" not in head and "Move bundles" not in head and "Cutting" not in head and ns.order.number in head
    more = html[html.index('class="guide-more"'):]
    for label, url in (("Fabric issue", reverse("lot_fabric", args=[ns.lot.pk])), ("Cutting", reverse("lot_cutting", args=[ns.lot.pk])),
                       ("Move bundles", reverse("move_bundles") + f"?lot={ns.lot.pk}&amp;back=1")):
        assert f'<a class="btn ghost" href="{url}">{label}</a>' in more


def test_a_role_that_may_not_cut_sees_what_the_lot_waits_for_and_no_link(company, factory, owner):
    ns = build(company, factory, owner)
    planner = user_with("planner", "Production Planner", factory)
    assert planner.has_screen_perm("production.lot", "view") and not planner.has_screen_perm("production.cutting", "create")
    html = lot_page(ns, planner)
    g = guide_of(html)
    assert "Waiting for: Issue fabric" in g and "btn primary" not in g
    assert f'href="{reverse("lot_fabric", args=[ns.lot.pk])}"' not in html


def test_the_orders_list_names_the_next_step_of_each_order(ns):
    blank = orders.create_order(company=ns.company, factory=ns.factory, date=DAY, user=ns.owner, lines=[
        orders.OrderLineSpec(ns.style, ns.black, 10, {ns.sizes["M"]: 1})])
    html = login(ns.owner).get(reverse("order_list")).content.decode()
    assert '<th scope="col">Next step</th>' in html
    released = row_with(html, reverse("order_detail", args=[ns.order.pk]))
    assert "Send to a fabricator for Stitching" in released and reverse("challan_new") in released
    waiting = row_with(html, f'<a href="{reverse("order_detail", args=[blank.pk])}">')
    assert re.search(r'<form method="post" action="%s">' % re.escape(reverse("order_detail", args=[blank.pk])), waiting)
    assert "<button" in waiting and 'value="release"' in waiting
    # someone who may only look at orders gets neither a release button nor a link they could not open
    seen = login(user_with("acct2", "Accountant", ns.factory)).get(reverse("order_list")).content.decode()
    assert 'value="release"' not in seen and reverse("challan_new") not in seen


def test_the_orders_list_says_issue_fabric_for_a_fresh_order_and_the_order_page_shows_it_beside_the_lot(company, factory, owner):
    ns = build(company, factory, owner)
    c = login(owner)
    assert "Issue fabric" in row_with(c.get(reverse("order_list")).content.decode(), reverse("order_detail", args=[ns.order.pk]))
    page = c.get(reverse("order_detail", args=[ns.order.pk])).content.decode()
    assert f'<a class="btn primary" href="{reverse("lot_fabric", args=[ns.lot.pk])}">Issue fabric</a>' in page
    assert f'href="{reverse("lot_detail", args=[ns.lot.pk])}"' in page


def test_home_names_the_next_step_of_each_lot_in_production(company, factory, owner):
    ns = build(company, factory, owner)
    html = login(owner).get(reverse("home")).content.decode()
    assert "Items in production" in html and '<th scope="col">Next step</th>' in html
    row = row_with(html, ns.lot.lot_no)
    assert f'href="{reverse("lot_fabric", args=[ns.lot.pk])}"' in row and "Issue fabric" in row
    sup = user_with("sup_guide", "Production Supervisor", factory)
    body = login(sup).get(reverse("home")).content.decode()
    assert "Money received" not in body and "Sales today" not in body
    # issuing fabric is not the supervisor's job: the row is there, the link is not
    assert reverse("lot_fabric", args=[ns.lot.pk]) not in row_with(body, ns.lot.lot_no)


def test_a_finished_lot_says_so_and_asks_for_nothing(ns):
    to_packing(ns)
    html = lot_page(ns, ns.owner)
    assert 'id="pack"' in html and "Pack into finished goods" in guide_of(html)
    bundle_service.pack_bundles(bundles=ns.bundles, user=ns.owner, date=DAY)
    g = guide_of(lot_page(ns, ns.owner))
    assert "This lot is complete." in g and "btn primary" not in g and "Waiting for" not in g


def test_a_closed_lot_shows_no_stage_as_current(company, factory, owner):
    ns = build(company, factory, owner)
    orders.close_order(ns.order, user=owner, reason="x")
    g = guide_of(lot_page(ns, owner))
    assert 'class="journey closed"' in g and "aria-current" not in g and "This lot is closed." in g and "btn primary" not in g


def test_the_lot_page_offers_optional_steps_as_smaller_links_never_as_the_button(ns):
    stitched(ns)
    g = guide_of(lot_page(ns, ns.owner))
    assert re.search(r'<a class="btn primary" href="[^"]*">Move to Ironing and pressing</a>', g)
    also = g[g.index("Also waiting"):]
    assert "Send to a fabricator for Embroidery (optional)" in also and "btn primary" not in also


def test_a_lot_in_another_factory_cannot_be_opened(company, factory, factory2, owner):
    ns = build(company, factory, owner)
    other = user_with("sup_far", "Production Supervisor", factory2)
    assert login(other).get(reverse("lot_detail", args=[ns.lot.pk])).status_code == 404


# ================================================================ each step leads on to the next

def role_user(name, grants, factory):
    """A user whose own role holds exactly these screen permissions: {screen: [actions]}."""
    role = Role.objects.create(name=f"{name} role")
    for screen, actions in grants.items():
        for action in actions:
            RolePermission.objects.create(role=role, screen=screen, action=action)
    u = make_user(name)
    u.roles.add(role)
    u.allowed_factories.add(factory)
    return u


def draft_order(ns):
    return orders.create_order(company=ns.company, factory=ns.factory, date=DAY, user=ns.owner, lines=[
        orders.OrderLineSpec(ns.style, ns.black, 10, {ns.sizes["M"]: 1})])


def test_releasing_a_single_lot_order_opens_its_lot(company, factory, owner):
    ns = build(company, factory, owner)
    order = draft_order(ns)
    r = login(owner).post(reverse("order_detail", args=[order.pk]), {"action": "release"})
    order.refresh_from_db()
    assert order.status == "released"
    assert r.status_code == 302 and r["Location"] == reverse("lot_detail", args=[order.lines.get().lot.pk])


def test_releasing_stays_on_the_order_for_someone_who_may_not_open_lots(company, factory, owner):
    ns = build(company, factory, owner)
    order = draft_order(ns)
    clerk = role_user("orderclerk", {"production.order": ["view", "edit"]}, factory)
    r = login(clerk).post(reverse("order_detail", args=[order.pk]), {"action": "release"})
    order.refresh_from_db()
    assert order.status == "released"
    assert r.status_code == 302 and r["Location"] == reverse("order_detail", args=[order.pk])


def test_a_move_started_from_the_lot_returns_to_it_and_one_from_the_menu_stays_put(ns):
    stitch_in_house(ns)
    c = login(ns.owner)
    url, st = reverse("move_bundles"), step(ns, "STITCH")
    page = c.get(url, {"lot": ns.lot.pk, "back": "1"}).content.decode()
    assert '<input type="hidden" name="back" value="1">' in page
    assert 'name="back"' not in c.get(url, {"lot": ns.lot.pk}).content.decode()
    r = c.post(url, {"lot": ns.lot.pk, "bundle": [ns.bundles[0].pk], "to_step": st.pk, "back": "1"})
    assert r.status_code == 302 and r["Location"] == reverse("lot_detail", args=[ns.lot.pk])
    r = c.post(url, {"lot": ns.lot.pk, "bundle": [ns.bundles[1].pk], "to_step": st.pk})
    assert r.status_code == 302 and r["Location"] == f"{url}?lot={ns.lot.pk}"
    assert {Bundle.objects.get(pk=b.pk).current_step_id for b in ns.bundles[:2]} == {st.pk}
    # a move that fails shows the form again and still remembers where it came from
    bad = c.post(url, {"lot": ns.lot.pk, "bundle": [ns.bundles[2].pk], "to_step": step(ns, "FINISH").pk, "back": "1"})
    assert bad.status_code == 200 and '<input type="hidden" name="back" value="1">' in bad.content.decode()


def test_qc_of_the_last_line_returns_to_the_lot(ns):
    rec = receive(ns, issue(ns, ns.bundles[:2]))
    first, last = rec.lines.order_by("id")
    c = login(ns.owner)
    here = reverse("receipt_detail", args=[rec.pk])
    r = c.post(here, {"action": "qc", "line": first.pk, "accepted": first.qty_received, "rejected": "0", "rework": "0"})
    assert r.status_code == 302 and r["Location"] == here  # another line still waits
    r = c.post(here, {"action": "qc", "line": last.pk, "accepted": last.qty_received, "rejected": "0", "rework": "0"}, follow=True)
    assert r.redirect_chain == [(reverse("lot_detail", args=[ns.lot.pk]), 302)]
    html = r.content.decode()
    # one message per line checked (the first is still queued, as that redirect was not followed); the last says it is the last
    assert html.count("QC recorded.") == 2 and html.count("QC recorded. Every bundle on this receipt is checked.") == 1
    rec.refresh_from_db()
    assert rec.status == "qc_done"


def test_qc_stays_on_the_receipt_for_a_checker_who_may_not_open_lots(ns):
    rec = receive(ns, issue(ns, ns.bundles[:1]))
    line = rec.lines.get()
    checker = user_with("qc_only", "QC Checker", ns.factory)
    assert not checker.has_screen_perm("production.lot", "view")
    here = reverse("receipt_detail", args=[rec.pk])
    c = login(checker)
    assert "Back to lot" not in c.get(here).content.decode()
    r = c.post(here, {"action": "qc", "line": line.pk, "accepted": line.qty_received, "rejected": "0", "rework": "0"})
    rec.refresh_from_db()
    assert rec.status == "qc_done" and r.status_code == 302 and r["Location"] == here


def test_every_step_screen_has_a_way_back_to_the_lot_for_those_who_may_open_it(ns):
    ch = issue(ns, ns.bundles[:1])
    rec = receive(ns, ch)
    back = f'<a class="btn" href="{reverse("lot_detail", args=[ns.lot.pk])}">Back to lot</a>'
    pages = [reverse("lot_tags", args=[ns.lot.pk]), reverse("lot_cutting", args=[ns.lot.pk]), reverse("lot_fabric", args=[ns.lot.pk]),
             reverse("challan_detail", args=[ch.pk]), reverse("receipt_detail", args=[rec.pk])]
    c = login(ns.owner)
    for url in pages:
        assert back in c.get(url).content.decode(), url
    # no lot link for a role that would get a 403 on it
    lot_url = reverse("lot_detail", args=[ns.lot.pk])
    clerk = role_user("jwonly", {"jobwork.challan": ["view"]}, ns.factory)
    html = login(clerk).get(reverse("challan_detail", args=[ch.pk]))
    assert html.status_code == 200 and "Back to lot" not in html.content.decode() and f'href="{lot_url}"' not in html.content.decode()
    cutter = user_with("cutter_back", "Cutting Master", ns.factory)
    k = login(cutter)
    for url in pages[:3]:
        page = k.get(url)
        assert page.status_code == 200 and "Back to lot" not in page.content.decode(), url
