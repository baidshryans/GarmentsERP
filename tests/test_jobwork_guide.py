"""The job work guide: where a challan is on its way from draft to paid, and the one thing it needs next
(guided job work, piece 2b). One test per row of the spec's table, then the lot guide's agreement, permissions,
and each offered link followed to the screen it opens."""
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from core.models import Role, RolePermission
from jobwork.models import JobWorkChallan
from jobwork.services import bills, challans, rates, receipts
from jobwork.services.guide import challan_guide, challan_next
from jobwork.services.receipts import Counted
from production.services.guide import lot_guide
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, step


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


def accept_all(ns, receipt):
    for line in receipt.lines.all():
        receipts.record_qc(receipt_line=line, accepted=line.qty_received, user=ns.owner)


def fresh(challan):
    return JobWorkChallan.objects.select_related("party", "lot", "step__process").get(pk=challan.pk)


def guide(ns, challan, user=None, perms=None):
    return challan_guide(fresh(challan), user or ns.owner, perms)


def offered(g):
    return [a for a in [g["primary"], *g["others"]] if a]


def seen(g):
    return [(a["label"], a["url"], a["pieces"]) for a in offered(g)]


def states(g):
    return {s["label"]: s["state"] for s in g["journey"]}


def pieces(g):
    return {s["label"]: s["pieces"] for s in g["journey"]}


def current(g):
    return [s["label"] for s in g["journey"] if s["current"]]


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


def login(user):
    c = Client()
    c.force_login(user)
    return c


def follow_links(ns, g, user=None):
    """Open every offered link as the user would, and check the screen it lands on really offers that work."""
    c = login(user or ns.owner)
    for a in offered(g):
        r = c.get(a["url"])
        assert r.status_code == 200, a
        html = r.content.decode()
        if a["url"].startswith(reverse("bill_new")):
            assert r.context["party"] == ns.fab and a["label"] == f"Make labour bill for {ns.fab.name}"
            assert sum(row["r"].accepted for row in r.context["rows"]) == a["pieces"], a
        elif a["label"].startswith("Receive from"):
            assert reverse("receipt_new", args=[r.context["ch"].pk]) == a["url"]
            assert sum(cb.bundle.qty for cb in r.context["lines"]) == a["pieces"], a
        elif a["label"].startswith("Issue challan"):
            assert r.context["ch"].status == "draft" and 'name="action" value="issue"' in html
        elif a["label"] == "Approve over-receipt":
            assert r.context["r"].status == "pending_approval" and 'name="action" value="approve"' in html
        elif a["label"] == "Check received pieces":
            assert r.context["r"].status == "received" and 'name="action" value="qc"' in html
        else:
            raise AssertionError(f"a link the guide should not offer: {a}")


# ---------------- one test per row of the table ----------------

def test_a_draft_challan_is_issued(ns):
    ch = draft(ns, ns.bundles[:3])  # 50 pieces
    g = guide(ns, ch)
    assert seen(g) == [(f"Issue challan to {ns.fab.name}", reverse("challan_detail", args=[ch.pk]), 50)]
    assert [s["label"] for s in g["journey"]] == ["Draft", "Issued", "Received", "Checked", "Billed"]
    assert states(g) == {"Draft": "now", "Issued": "todo", "Received": "todo", "Checked": "todo", "Billed": "todo"}
    assert current(g) == ["Draft"] and not any(pieces(g).values())
    assert g["waiting"] == "" and g["complete"] is False and g["closed"] is False
    follow_links(ns, g)


def test_an_issued_challan_is_received(ns):
    ch = issue(ns, ns.bundles[:3])
    g = guide(ns, ch)
    assert seen(g) == [(f"Receive from {ns.fab.name}", reverse("receipt_new", args=[ch.pk]), 50)]
    assert states(g) == {"Draft": "done", "Issued": "now", "Received": "todo", "Checked": "todo", "Billed": "todo"}
    assert current(g) == ["Issued"] and pieces(g)["Issued"] == 50 and pieces(g)["Received"] is None
    follow_links(ns, g)


def test_a_partly_received_challan_still_asks_for_what_is_out_first(ns):
    ch = issue(ns, ns.bundles[:3])
    b1, b2, b3 = ch.bundles.order_by("id")
    r = receive(ns, ch, {b1: 17})
    g = guide(ns, ch)
    # what is furthest behind comes first: the 33 pieces still out, then QC of the 17 that came back
    assert seen(g) == [(f"Receive from {ns.fab.name}", reverse("receipt_new", args=[ch.pk]), 33),
                       ("Check received pieces", reverse("receipt_detail", args=[r.pk]), 0)]
    assert states(g) == {"Draft": "done", "Issued": "now", "Received": "now", "Checked": "now", "Billed": "todo"}
    assert current(g) == ["Issued"] and pieces(g)["Issued"] == 50 and pieces(g)["Received"] == 17
    follow_links(ns, g)


def test_an_over_receipt_waits_for_approval_and_its_bundles_are_not_counted_again(ns):
    ch = issue(ns, ns.bundles[:2])  # 17 + 25
    b1, b2 = ch.bundles.order_by("id")
    r = receive(ns, ch, {b1: 19})   # two more than were sent
    assert r.status == "pending_approval"
    g = guide(ns, ch)
    assert seen(g) == [(f"Receive from {ns.fab.name}", reverse("receipt_new", args=[ch.pk]), 25),   # only B002 is asked for
                       ("Approve over-receipt", reverse("receipt_detail", args=[r.pk]), 0)]
    assert states(g)["Received"] == "now" and pieces(g)["Received"] is None  # counted, but nothing has moved yet
    receive(ns, ch, {b2: 25})
    g = guide(ns, ch)
    assert [a["label"] for a in offered(g)] == ["Approve over-receipt", "Check received pieces"]
    follow_links(ns, g)


def test_received_pieces_wait_for_qc(ns):
    ch = issue(ns, ns.bundles[:2])
    r = receive(ns, ch)
    g = guide(ns, ch)
    assert seen(g) == [("Check received pieces", reverse("receipt_detail", args=[r.pk]), 0)]
    assert states(g) == {"Draft": "done", "Issued": "done", "Received": "done", "Checked": "now", "Billed": "todo"}
    assert current(g) == ["Checked"] and pieces(g)["Received"] == 42 and pieces(g)["Checked"] is None
    follow_links(ns, g)


def test_accepted_pieces_not_yet_on_a_bill_ask_for_the_labour_bill(ns):
    ch = issue(ns, ns.bundles[:3])
    l1, l2, l3 = receive(ns, ch).lines.order_by("id")
    receipts.record_qc(receipt_line=l1, accepted=17, user=ns.owner)
    receipts.record_qc(receipt_line=l2, accepted=22, rejected=3, reject_reason="Open seams", user=ns.owner)
    g = guide(ns, ch)
    # one line still waits for QC, so that comes first; the 39 accepted pieces can already be billed
    assert [(a["label"], a["pieces"]) for a in offered(g)] == [("Check received pieces", 0), (f"Make labour bill for {ns.fab.name}", 39)]
    receipts.record_qc(receipt_line=l3, accepted=8, user=ns.owner)
    g = guide(ns, ch)
    assert seen(g) == [(f"Make labour bill for {ns.fab.name}", reverse("bill_new") + f"?party={ns.fab.pk}", 47)]
    assert states(g) == {"Draft": "done", "Issued": "done", "Received": "done", "Checked": "done", "Billed": "now"}
    assert current(g) == ["Billed"] and pieces(g)["Checked"] == 47
    assert next(s for s in g["journey"] if s["label"] == "Checked")["detail"] == "accepted"
    follow_links(ns, g)
    # the guide counts exactly what the bill service would pay (rule 5: pay follows acceptance)
    assert g["primary"]["pieces"] == sum(r.accepted for r in bills.unbilled_qc(ns.fab, ns.factory))


def test_pieces_on_a_bill_are_not_offered_again_and_a_billed_challan_is_finished(ns):
    ch = issue(ns, ns.bundles[:2])
    accept_all(ns, receive(ns, ch))
    bill = bills.create_bill(company=ns.company, factory=ns.factory, party=ns.fab, date=DAY, user=ns.owner)
    g = guide(ns, ch)
    # every accepted piece is on the draft bill: nothing more to make, though the challan is not billed until it is posted
    assert offered(g) == [] and g["waiting"] == "" and g["complete"] is False
    bills.post_bill(bill, user=ns.owner)
    assert fresh(ch).status == "billed"
    g = guide(ns, ch)
    assert offered(g) == [] and g["waiting"] == "" and g["complete"] is True and g["closed"] is False
    assert set(states(g).values()) == {"done"} and current(g) == []
    assert challan_next(fresh(ch), ns.owner) is None


def test_a_cancelled_bill_makes_its_pieces_billable_again(ns):
    ch = issue(ns, ns.bundles[:1])
    accept_all(ns, receive(ns, ch))
    bill = bills.post_bill(bills.create_bill(company=ns.company, factory=ns.factory, party=ns.fab, date=DAY, user=ns.owner), user=ns.owner)
    bills.cancel_bill(bill, user=ns.owner, reason="Wrong rate")
    g = guide(ns, ch)
    assert [(a["label"], a["pieces"]) for a in offered(g)] == [(f"Make labour bill for {ns.fab.name}", 17)] and g["complete"] is False
    follow_links(ns, g)


def test_a_cancelled_challan_asks_for_nothing(ns):
    ch = draft(ns, ns.bundles[:1])
    challans.cancel_draft(ch, user=ns.owner)
    g = guide(ns, ch)
    assert offered(g) == [] and g["waiting"] == "" and g["complete"] is False and g["closed"] is True
    assert set(states(g).values()) == {"todo"} and current(g) == []
    assert challan_next(fresh(ch), ns.owner) is None


# ---------------- the lot guide and the challan guide say the same thing ----------------

def test_the_lot_guide_and_the_challan_guide_agree_on_every_challan_and_receipt(ns):
    a = draft(ns, ns.bundles[:1])                              # a draft
    b = issue(ns, ns.bundles[1:2])                             # out with the fabricator
    c = issue(ns, ns.bundles[2:3])
    receive(ns, c)                                             # back, waiting for QC
    d = issue(ns, ns.bundles[3:4])
    over = receive(ns, d, {d.bundles.get(): 27})               # counted above what was sent
    assert over.status == "pending_approval"
    lot = {x["url"]: x for x in offered(lot_guide(ns.lot, ns.owner))}
    mine = [x for ch in (a, b, c, d) for x in offered(guide(ns, ch))]
    assert sorted(x["label"] for x in mine) == sorted([
        f"Issue challan to {ns.fab.name}", f"Receive from {ns.fab.name}", "Check received pieces", "Approve over-receipt"])
    for x in mine:
        same = lot[x["url"]]                                   # the lot offers it too, at the same address
        assert (same["label"], same["hint"], same["pieces"], same["perm"]) == (x["label"], x["hint"], x["pieces"], x["perm"])
    # and nothing the lot says about a challan or a receipt is missing from the challans' own guides
    about_job_work = [u for u in lot if not u.startswith((reverse("challan_new"), reverse("move_bundles")))]
    assert sorted(about_job_work) == sorted(x["url"] for x in mine)


# ---------------- permissions ----------------

def test_a_role_that_may_not_do_the_next_step_is_told_what_the_challan_waits_for(ns):
    ch = issue(ns, ns.bundles[:1])
    looker = role_user("jw_looker", {"jobwork.challan": ["view"]}, ns.factory)
    g = guide(ns, ch, looker)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == f"Receive from {ns.fab.name}"
    assert challan_next(fresh(ch), looker) is None


# `opens`: what the link itself answers to someone holding only the right to do the thing. A form that needs only
# `create` opens, but saving it lands on a page that needs `view`, so the guide asks for both either way.
@pytest.mark.parametrize("stage, screen, action, target, label, opens", [
    ("draft", "jobwork.challan", "edit", "jobwork.challan", "Issue challan to Sharma Stitching", 403),
    ("issued", "jobwork.receipt", "create", "jobwork.receipt", "Receive from Sharma Stitching", 200),
    ("over", "jobwork.receipt", "approve", "jobwork.receipt", "Approve over-receipt", 403),
    ("received", "jobwork.qc", "create", "jobwork.receipt", "Check received pieces", 403),
    ("accepted", "jobwork.bill", "create", "jobwork.bill", "Make labour bill for Sharma Stitching", 200),
])
def test_each_action_needs_the_right_to_do_it_and_view_on_the_screen_it_opens(ns, stage, screen, action, target, label, opens):
    ch = draft(ns, ns.bundles[:1])
    if stage != "draft":
        ch = challans.issue_challan(ch, user=ns.owner)
    if stage == "over":
        receive(ns, ch, {ch.bundles.get(): 19})
    elif stage in ("received", "accepted"):
        r = receive(ns, ch)
        if stage == "accepted":
            accept_all(ns, r)
    wanted = next(a for a in offered(guide(ns, ch)) if a["label"] == label)
    # the right to do it alone is not enough: the link would open a screen the role is refused on
    blind = role_user("blind", {screen: [action]}, ns.factory)
    g = guide(ns, ch, blind)
    assert offered(g) == [] and g["waiting"] == label
    assert login(blind).get(wanted["url"]).status_code == opens
    # view alone is not enough either
    only_view = role_user("only_view", {target: ["view"]}, ns.factory)
    g = guide(ns, ch, only_view)
    assert offered(g) == [] and g["waiting"] == label
    # both together: offered, and the link opens
    seeing = role_user("seeing", {screen: [action], target: ["view"]} if screen != target else {screen: [action, "view"]}, ns.factory)
    g = guide(ns, ch, seeing)
    assert label in [a["label"] for a in offered(g)] and g["waiting"] == ""
    assert login(seeing).get(wanted["url"]).status_code == 200


def test_a_custom_role_with_create_but_not_view_gets_no_link(ns):
    ch = issue(ns, ns.bundles[:1])
    clerk = role_user("receive_only", {"jobwork.receipt": ["create"], "jobwork.challan": ["view"]}, ns.factory)
    assert clerk.has_screen_perm("jobwork.receipt", "create") and not clerk.has_screen_perm("jobwork.receipt", "view")
    g = guide(ns, ch, clerk)
    assert g["primary"] is None and g["others"] == [] and g["waiting"] == f"Receive from {ns.fab.name}"


def test_someone_who_may_do_a_later_step_gets_that_one_and_no_waiting_line(ns):
    ch = issue(ns, ns.bundles[:2])
    b1, b2 = ch.bundles.order_by("id")
    r = receive(ns, ch, {b1: 17})
    checker = role_user("qc_person", {"jobwork.qc": ["create"], "jobwork.receipt": ["view"]}, ns.factory)
    g = guide(ns, ch, checker)
    # receiving the rest is not theirs; checking what came back is, so that is their button
    assert seen(g) == [("Check received pieces", reverse("receipt_detail", args=[r.pk]), 0)] and g["waiting"] == ""
    follow_links(ns, g, checker)


def test_one_call_asks_each_permission_once_and_callers_can_share_the_answers(ns):
    class Counting:
        def __init__(self, user):
            self.user, self.asked = user, []

        def has_screen_perm(self, screen, action):
            self.asked.append((screen, action))
            return self.user.has_screen_perm(screen, action)

    ch = issue(ns, ns.bundles[:2])
    b1, b2 = ch.bundles.order_by("id")
    receive(ns, ch, {b1: 17})
    other = issue(ns, ns.bundles[2:3])
    who = Counting(ns.owner)
    g = challan_guide(fresh(ch), who)
    assert len(offered(g)) == 2 and len(who.asked) == len(set(who.asked)) == 3  # receipt create and view, QC create
    shared, again = {}, Counting(ns.owner)
    assert challan_guide(fresh(ch), again, shared) == g
    assert challan_next(fresh(other), again, shared)["label"] == f"Receive from {ns.fab.name}"
    assert len(again.asked) == 3  # the second challan asked nothing new
    assert lot_guide(ns.lot, again, shared)["primary"] and len(set(again.asked)) == len(again.asked)  # one memo serves both guides


def test_the_guide_reads_and_never_writes(ns, django_assert_num_queries):
    ch = issue(ns, ns.bundles[:2])
    accept_all(ns, receive(ns, ch))
    ch = fresh(ch)
    before = (ch.history.count(), ch.status)
    answers = {("jobwork.bill", "create"): True, ("jobwork.bill", "view"): True}
    with django_assert_num_queries(3) as seen_queries:   # the challan's lines, its receipts, the unbilled pieces
        g = challan_guide(ch, ns.owner, answers)
    assert g["primary"]["label"] == f"Make labour bill for {ns.fab.name}"
    assert all(q["sql"].lstrip().upper().startswith("SELECT") for q in seen_queries.captured_queries)
    assert (ch.history.count(), fresh(ch).status) == before
