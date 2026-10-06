"""The job work guide: where a challan is on its way from draft to paid, and the one thing it needs next
(guided job work, piece 2b). One test per row of the spec's table, then the lot guide's agreement, permissions,
and each offered link followed to the screen it opens."""
import re
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from core.exceptions import BusinessRuleError
from core.home_actions import home_actions
from core.models import Role, RolePermission
from jobwork.models import JobWorkChallan
from jobwork.services import bills, challans, rates, receipts
from jobwork.services.guide import challan_guide, challan_next
from jobwork.services.receipts import Counted
from inventory.models import StockMovement
from production.models import Bundle, StageMovement
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


def bill_url(ns, challan):
    return reverse("bill_new") + f"?party={ns.fab.pk}&factory={ns.factory.pk}&challan={challan.pk}"


def rework_url(ns, code="STITCH"):
    return reverse("challan_new") + f"?lot={ns.lot.pk}&kind=rework&step={step(ns, code).pk}"


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
        elif a["label"] == "Send back for rework":
            assert r.context["kind"] == "rework" and a["url"].endswith(f"&step={r.context['step'].pk}")
            assert sum(b.rework_qty for b in r.context["bundles"]) == a["pieces"], a
        elif a["label"] == "Post labour bill":
            assert r.context["b"].status == "draft" and 'name="action" value="post"' in html
            assert sum(l.qty for l in r.context["lines"]) >= a["pieces"] > 0
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
    follow_links(ns, g)   # the receipt form lists exactly the 25 pieces the button names
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
    assert seen(g) == [(f"Make labour bill for {ns.fab.name}", bill_url(ns, ch), 47)]
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
    # every accepted piece is on the draft bill: no second bill to make, but nothing is owed until that one is posted
    assert seen(g) == [("Post labour bill", reverse("bill_detail", args=[bill.pk]), 42)] and g["complete"] is False
    assert states(g)["Billed"] == "now"
    follow_links(ns, g)
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
    ("on_draft_bill", "jobwork.bill", "edit", "jobwork.bill", "Post labour bill", 403),
    ("sent_back", "jobwork.challan", "create", "jobwork.challan", "Send back for rework", 200),
])
def test_each_action_needs_the_right_to_do_it_and_view_on_the_screen_it_opens(ns, stage, screen, action, target, label, opens):
    ch = draft(ns, ns.bundles[:1])
    if stage != "draft":
        ch = challans.issue_challan(ch, user=ns.owner)
    if stage == "over":
        receive(ns, ch, {ch.bundles.get(): 19})
    elif stage in ("received", "accepted", "on_draft_bill"):
        r = receive(ns, ch)
        if stage != "received":
            accept_all(ns, r)
        if stage == "on_draft_bill":
            bills.create_bill(company=ns.company, factory=ns.factory, party=ns.fab, date=DAY, user=ns.owner)
    elif stage == "sent_back":
        receipts.record_qc(receipt_line=receive(ns, ch).lines.get(), accepted=0, rework=17, user=ns.owner)
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
    with django_assert_num_queries(4) as seen_queries:   # the challan's lines, its receipts, unbilled pieces, draft bills
        g = challan_guide(ch, ns.owner, answers)
    assert g["primary"]["label"] == f"Make labour bill for {ns.fab.name}"
    assert all(q["sql"].lstrip().upper().startswith("SELECT") for q in seen_queries.captured_queries)
    assert (ch.history.count(), fresh(ch).status) == before


# ================================================================ the guide on the screens

def page(user, name, *args, **query):
    r = login(user).get(reverse(name, args=args), query)
    assert r.status_code == 200
    return r.content.decode()


def guide_of(html):
    """The guide island alone: from its opening tag to the next island."""
    start = html.index('class="island guide"')
    return html[start:html.index('class="island"', start)]


def row_with(html, text):
    return next(r for r in re.findall(r"<tr>.*?</tr>", html, re.S) if text in r)


def button(url, label):
    return f'<a class="btn primary" href="{url}">{label}</a>'


def test_the_challan_page_opens_with_the_journey_and_one_next_button(ns):
    ch = draft(ns, ns.bundles[:3])
    html = page(ns.owner, "challan_detail", ch.pk)
    g = guide_of(html)
    assert 'aria-label="Where this challan is"' in g and g.count('class="sr-only"') == 5
    assert re.search(r'<li class="now" aria-current="step">\s*<span class="j-label">Draft</span>', g)
    # issuing is done on this very page: the button jumps to the form instead of reloading the page
    assert button("#do-next", f"Issue challan to {ns.fab.name}") in g and "50 pieces." in g
    assert '<form method="post" class="island" id="do-next">' in html
    # only labels, counts and links are shown: the permission keys stay inside the service
    assert "jobwork.challan" not in html and "jobwork.receipt" not in html

    ch = challans.issue_challan(ch, user=ns.owner)
    html = page(ns.owner, "challan_detail", ch.pk)
    g = guide_of(html)
    assert button(reverse("receipt_new", args=[ch.pk]), f"Receive from {ns.fab.name}") in g and 'id="do-next"' not in html
    assert re.search(r'<li class="now" aria-current="step">\s*<span class="j-label">Issued</span>', g) and "50 pcs" in g

    b1, b2, b3 = ch.bundles.order_by("id")
    rec = receive(ns, ch, {b1: 17})
    g = guide_of(page(ns.owner, "challan_detail", ch.pk))
    also = g[g.index("Also waiting"):]
    assert f'<a href="{reverse("receipt_detail", args=[rec.pk])}">Check received pieces</a>' in also and "btn primary" not in also


def test_the_challan_page_tells_a_viewer_what_it_waits_for_and_gives_no_link(ns):
    ch = issue(ns, ns.bundles[:1])
    looker = role_user("jw_page_looker", {"jobwork.challan": ["view"]}, ns.factory)
    html = page(looker, "challan_detail", ch.pk)
    g = guide_of(html)
    assert f"Waiting for: Receive from {ns.fab.name}" in g and "btn primary" not in g
    assert reverse("receipt_new", args=[ch.pk]) not in html and reverse("lot_detail", args=[ns.lot.pk]) not in html


def test_a_finished_challan_and_a_cancelled_one_say_so(ns):
    ch = issue(ns, ns.bundles[:1])
    accept_all(ns, receive(ns, ch))
    g = guide_of(page(ns.owner, "challan_detail", ch.pk))
    assert button(escape(bill_url(ns, ch)), f"Make labour bill for {ns.fab.name}") in g and "17 pieces." in g
    bill = bills.create_bill(company=ns.company, factory=ns.factory, party=ns.fab, date=DAY, user=ns.owner)
    g = guide_of(page(ns.owner, "challan_detail", ch.pk))
    assert button(reverse("bill_detail", args=[bill.pk]), "Post labour bill") in g and "17 pieces." in g  # a draft, not yet posted
    bills.post_bill(bill, user=ns.owner)
    g = guide_of(page(ns.owner, "challan_detail", ch.pk))
    assert "This challan is finished." in g and "btn primary" not in g and "Waiting for" not in g and "aria-current" not in g

    gone = draft(ns, ns.bundles[1:2])
    challans.cancel_draft(gone, user=ns.owner)
    g = guide_of(page(ns.owner, "challan_detail", gone.pk))
    assert 'class="journey closed"' in g and "This challan was cancelled." in g and "aria-current" not in g and "btn primary" not in g


def test_the_receipt_page_shows_its_challans_guide_so_the_next_step_is_one_click(ns):
    ch = issue(ns, ns.bundles[:2])
    b1, b2 = ch.bundles.order_by("id")
    rec = receive(ns, ch, {b1: 17})
    html = page(ns.owner, "receipt_detail", rec.pk)
    g = guide_of(html)
    # what is furthest behind first: the bundle still out; checking this receipt is done here, so that link jumps down
    assert button(reverse("receipt_new", args=[ch.pk]), f"Receive from {ns.fab.name}") in g
    assert '<a href="#do-next">Check received pieces</a>' in g and '<span id="do-next"></span>' in html
    assert html.index('id="do-next"') < html.index('name="action" value="qc"')

    # a checker who may not open lots stays on the receipt after the last line, and sees what comes next
    checker = role_user("qc_stays", {"jobwork.qc": ["create"], "jobwork.receipt": ["view"]}, ns.factory)
    c = login(checker)
    here = reverse("receipt_detail", args=[rec.pk])
    assert button("#do-next", "Check received pieces") in guide_of(c.get(here).content.decode())  # receiving is not theirs
    line = rec.lines.get()
    r = c.post(here, {"action": "qc", "line": line.pk, "accepted": "17", "rejected": "0", "rework": "0"}, follow=True)
    assert r.redirect_chain == [(here, 302)]
    g = guide_of(r.content.decode())
    assert f"Waiting for: Receive from {ns.fab.name}" in g and "btn primary" not in g
    # the owner, on the same receipt: the other bundle first, then the labour bill for what was accepted
    g = guide_of(page(ns.owner, "receipt_detail", rec.pk))
    assert button(reverse("receipt_new", args=[ch.pk]), f"Receive from {ns.fab.name}") in g
    assert f'<a href="{escape(bill_url(ns, ch))}">Make labour bill for {ns.fab.name}</a>' in g


def test_an_over_receipt_page_points_the_owner_at_the_approve_button_below(ns, accountant):
    ch = issue(ns, ns.bundles[:1])
    rec = receive(ns, ch, {ch.bundles.get(): 19})
    html = page(ns.owner, "receipt_detail", rec.pk)
    assert button("#do-next", "Approve over-receipt") in guide_of(html)
    assert html.index('id="do-next"') < html.index('name="action" value="approve"')


def test_the_challan_list_names_the_next_step_of_each_row_and_filters_what_is_out(ns):
    a = draft(ns, ns.bundles[:1])
    b = issue(ns, ns.bundles[1:2])
    c = issue(ns, ns.bundles[2:4])
    c1, c2 = c.bundles.order_by("id")
    receive(ns, c, {c1: 8})                                   # partly received
    d = issue(ns, ns.bundles[4:5])
    rec = receive(ns, d)                                      # fully received, waiting for QC
    html = page(ns.owner, "challan_list")
    assert '<th scope="col">Next step</th>' in html

    def nxt(html, ch):
        return row_with(html, f'href="{reverse("challan_detail", args=[ch.pk])}">')

    assert f'<a class="btn" href="{reverse("challan_detail", args=[a.pk])}">Issue challan to {ns.fab.name}</a>' in nxt(html, a)
    for ch in (b, c):
        assert f'<a class="btn" href="{reverse("receipt_new", args=[ch.pk])}">Receive from {ns.fab.name}</a>' in nxt(html, ch)
    assert f'<a class="btn" href="{reverse("receipt_detail", args=[rec.pk])}">Check received pieces</a>' in nxt(html, d)

    # the filter the Home button uses: only what is with a fabricator, and every row there asks to be received
    r = login(ns.owner).get(reverse("challan_list"), {"status": "out"})
    out = r.content.decode()
    assert {x.pk for x in r.context["challans"]} == {b.pk, c.pk}
    assert all(x.next["label"] == f"Receive from {ns.fab.name}" for x in r.context["challans"])
    assert '<a class="step current" href="?status=out">Out with fabricators</a>' in out
    assert '<a class="step " href="?status=out">Out with fabricators</a>' in html
    # the single-status tabs work as before
    assert {x.pk for x in login(ns.owner).get(reverse("challan_list"), {"status": "issued"}).context["challans"]} == {b.pk}

    # someone who may only look gets the rows and no link they could not open
    looker = role_user("jw_list_looker", {"jobwork.challan": ["view"]}, ns.factory)
    seen_by_looker = page(looker, "challan_list")
    assert reverse("receipt_new", args=[b.pk]) not in seen_by_looker and reverse("receipt_detail", args=[rec.pk]) not in seen_by_looker
    assert f'href="{reverse("challan_detail", args=[b.pk])}"' in seen_by_looker


def test_the_receipt_list_names_the_next_step_of_each_receipt(ns):
    ch = issue(ns, ns.bundles[:2])
    b1, b2 = ch.bundles.order_by("id")
    first = receive(ns, ch, {b1: 17})
    html = page(ns.owner, "receipt_list")
    assert '<th scope="col">Next step</th>' in html
    row = row_with(html, f'href="{reverse("receipt_detail", args=[first.pk])}">{first.number}')
    assert f'<a class="btn" href="{reverse("receipt_new", args=[ch.pk])}">Receive from {ns.fab.name}</a>' in row
    second = receive(ns, ch, {b2: 25})
    accept_all(ns, first)
    r = login(ns.owner).get(reverse("receipt_list"))
    nexts = {x.pk: x.next for x in r.context["receipts"]}
    # both receipts are of one challan, so both name the same step: the receipt still unchecked
    assert nexts[first.pk] is nexts[second.pk] and nexts[first.pk]["url"] == reverse("receipt_detail", args=[second.pk])
    accept_all(ns, second)
    html = page(ns.owner, "receipt_list")
    assert html.count(f'<a class="btn" href="{escape(bill_url(ns, ch))}">Make labour bill for {ns.fab.name}</a>') == 2
    looker = role_user("rc_list_looker", {"jobwork.receipt": ["view"]}, ns.factory)
    assert reverse("bill_new") not in page(looker, "receipt_list")


def test_the_lists_ask_each_permission_once_however_many_rows_they_show(ns):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def asked(name):
        c = login(ns.owner)
        with CaptureQueriesContext(connection) as q:
            assert c.get(reverse(name)).status_code == 200
        return len([x for x in q.captured_queries if "core_rolepermission" in x["sql"]]), len(q)

    receive(ns, issue(ns, ns.bundles[:1]))
    one = {name: asked(name) for name in ("challan_list", "receipt_list")}
    for b in ns.bundles[1:4]:
        receive(ns, issue(ns, [b]))
    four = {name: asked(name) for name in ("challan_list", "receipt_list")}
    for name in one:
        assert four[name][0] == one[name][0], name                 # three more rows, no permission asked again
        assert four[name][1] - one[name][1] <= 3 * 3, name         # each row: its lines, its receipts, its unbilled pieces


# ---------------- Save and issue ----------------

def form(ns, bundles, **extra):
    return {"lot": ns.lot.pk, "step": step(ns, "STITCH").pk, "kind": "issue", "factory": ns.factory.pk, "party": ns.fab.pk,
            "date": "2026-06-16", "bundle": [b.pk for b in bundles], **extra}


def form_of(html):
    """The challan form alone (the page's other forms and the menu are not its business)."""
    start = html.index('<form method="post" class="island" novalidate>')
    return html[start:html.index("</form>", start)]


def new_form(user, ns):
    return login(user).get(reverse("challan_new"), {"lot": ns.lot.pk, "step": step(ns, "STITCH").pk}).content.decode()


def test_save_and_issue_makes_the_challan_and_hands_the_bundles_over_in_one_step(ns):
    html = new_form(ns.owner, ns)
    assert '<button class="btn primary" name="then" value="issue">Save and issue</button>' in html
    assert '<button class="btn" name="then" value="draft">Save challan</button>' in html
    r = login(ns.owner).post(reverse("challan_new"), form(ns, ns.bundles[:2], then="issue"), follow=True)
    ch = ns.lot.challans.get()
    assert r.redirect_chain == [(reverse("challan_detail", args=[ch.pk]), 302)]
    assert ch.status == "issued" and ch.number and ch.trims.get().value > 0
    done = r.content.decode()
    assert f"{ch.number} issued. The bundles are now with {ns.fab.name}. Print it from this page." in done
    assert f'href="{reverse("challan_print", args=[ch.pk])}"' in done
    assert button(reverse("receipt_new", args=[ch.pk]), f"Receive from {ns.fab.name}") in guide_of(done)
    assert {Bundle.objects.get(pk=b.pk).location.loc_type for b in ns.bundles[:2]} == {"fabricator"}


def test_the_draft_button_still_saves_a_draft(ns):
    c = login(ns.owner)
    for extra in ({"then": "draft"}, {}):
        before = set(ns.lot.challans.values_list("pk", flat=True))
        bundle = ns.bundles[len(before)]
        r = c.post(reverse("challan_new"), form(ns, [bundle], **extra), follow=True)
        ch = ns.lot.challans.exclude(pk__in=before).get()
        assert ch.status == "draft" and ch.number is None and "Challan saved as a draft. Check it, then issue it." in r.content.decode()
        assert Bundle.objects.get(pk=bundle.pk).status == "cut"


def test_without_edit_only_the_draft_button_shows_and_a_forged_issue_is_refused(ns):
    clerk = role_user("draft_only", {"jobwork.challan": ["view", "create"], "production.lot": ["view"]}, ns.factory)
    html = new_form(clerk, ns)
    assert "Save and issue" not in html and '<button class="btn primary">Save challan</button>' in html
    r = login(clerk).post(reverse("challan_new"), form(ns, ns.bundles[:1], then="issue"))
    assert r.status_code == 403 and not ns.lot.challans.exists()
    assert login(clerk).post(reverse("challan_new"), form(ns, ns.bundles[:1])).status_code == 302
    assert ns.lot.challans.get().status == "draft"


def test_if_issuing_fails_nothing_is_saved_and_the_form_comes_back(ns, monkeypatch):
    def fails(lot):
        raise BusinessRuleError("The route could not be refreshed.")

    # the very last thing issuing does, after the bundles moved, the trims left stock and the number was drawn:
    # all of it must come back, the number included
    monkeypatch.setattr(challans.bundle_service, "refresh_steps", fails)
    from inventory.services import stock

    zips = stock.on_hand(ns.factory, ns.zipper)
    moves, stock_moves = StageMovement.objects.count(), StockMovement.objects.count()
    c = login(ns.owner)
    r = c.post(reverse("challan_new"), form(ns, ns.bundles[:2], then="issue"))
    html = r.content.decode()
    assert r.status_code == 200 and "The route could not be refreshed." in html
    assert not JobWorkChallan.objects.exists()                                     # no draft left behind
    assert (StageMovement.objects.count(), StockMovement.objects.count()) == (moves, stock_moves)
    assert {Bundle.objects.get(pk=b.pk).status for b in ns.bundles[:2]} == {"cut"}
    assert stock.on_hand(ns.factory, ns.zipper) == zips
    assert step(ns, "STITCH").status == "pending"
    # the form comes back with both buttons and the bundles still ticked; no button grabs the focus past the message
    assert '<button class="btn primary" name="then" value="issue">Save and issue</button>' in html
    assert '<button class="btn" name="then" value="draft">Save challan</button>' in html
    for b in ns.bundles[:2]:
        assert f'name="bundle" value="{b.pk}" checked' in html
    assert f'name="bundle" value="{ns.bundles[2].pk}" checked' not in html and "autofocus" not in form_of(html)
    # the number drawn by the failed attempt was given back: the next challan is the first of the series
    monkeypatch.undo()
    assert c.post(reverse("challan_new"), form(ns, ns.bundles[:2], then="issue")).status_code == 302
    assert JobWorkChallan.objects.get().number == "JWC/LDH1/26-27/0001"


def test_a_validation_error_shows_for_both_buttons_and_saves_nothing(ns):
    c = login(ns.owner)
    for then in ("issue", "draft"):
        r = c.post(reverse("challan_new"), form(ns, [], then=then))
        html = r.content.decode()
        assert r.status_code == 200 and "Scan or choose at least one bundle." in html
        assert 'value="issue">Save and issue</button>' in html and "autofocus" not in form_of(html)
    assert not JobWorkChallan.objects.exists()


def test_the_second_fabricator_warning_still_asks_before_save_and_issue(ns):
    other = fabricator(ns.company, "Gupta Stitching", "9822222233")
    rates.save_rate(party=other, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("24"), effective_from=date(2026, 4, 1))
    first = issue(ns, ns.bundles[:1])
    c = login(ns.owner)
    data = form(ns, ns.bundles[1:2], then="issue", party=other.pk)
    r = c.post(reverse("challan_new"), data)
    html = r.content.decode()
    assert r.status_code == 200 and f"already open with {ns.fab.name}" in html
    # the question takes the focus, and the bundle ticked before is still ticked
    assert '<input id="cs" type="checkbox" name="confirm_second" autofocus>' in html and form_of(html).count("autofocus") == 1
    assert f'name="bundle" value="{ns.bundles[1].pk}" checked' in html and form_of(html).count(" checked") == 1
    assert '<button class="btn primary" name="then" value="issue">Save and issue</button>' in html
    assert list(ns.lot.challans.values_list("pk", flat=True)) == [first.pk]       # nothing saved, nothing issued
    r = c.post(reverse("challan_new"), {**data, "confirm_second": "on"})
    made = ns.lot.challans.exclude(pk=first.pk).get()
    assert r.status_code == 302 and made.status == "issued" and made.party == other and made.second_fabricator_ack
    # and the draft button goes through the same question
    data = form(ns, ns.bundles[2:3], then="draft", party=other.pk)
    third = fabricator(ns.company, "Verma Stitching", "9822222244")
    rates.save_rate(party=third, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("24"), effective_from=date(2026, 4, 1))
    data["party"] = third.pk
    r = c.post(reverse("challan_new"), data)
    assert r.status_code == 200 and 'name="confirm_second"' in r.content.decode() and ns.lot.challans.count() == 2
    assert c.post(reverse("challan_new"), {**data, "confirm_second": "on"}).status_code == 302
    assert ns.lot.challans.get(party=third).status == "draft"


# ---------------- Home ----------------

def test_home_receive_from_fabricator_opens_the_challans_that_are_out(ns):
    out = issue(ns, ns.bundles[:1])
    draft(ns, ns.bundles[1:2])
    url = reverse("challan_list") + "?status=out"
    make = next(i for i in home_actions(ns.owner) if i["title"] == "Make")
    assert {"label": "Receive from fabricator", "url": url} in make["actions"]
    assert {"label": "Send to fabricator", "url": reverse("challan_new")} in make["actions"]      # the others are untouched
    c = login(ns.owner)
    assert f'<a class="btn" href="{url}">Receive from fabricator</a>' in c.get(reverse("home")).content.decode()
    r = c.get(url)
    assert r.status_code == 200 and [x.pk for x in r.context["challans"]] == [out.pk]
    assert f'href="{reverse("receipt_new", args=[out.pk])}">Receive from {ns.fab.name}</a>' in r.content.decode()


# ================================================================ no dead ends on a challan

def sent_back(ns):
    """B001 (17) accepted and B002 (25) sent back by QC, both on one fully received challan."""
    ch = issue(ns, ns.bundles[:2])
    l1, l2 = receive(ns, ch).lines.order_by("id")
    receipts.record_qc(receipt_line=l1, accepted=17, user=ns.owner)
    receipts.record_qc(receipt_line=l2, accepted=0, rework=25, user=ns.owner)
    return ch, l2.receipt


def test_a_bundle_sent_back_asks_for_a_rework_challan_exactly_as_the_lot_does(ns):
    ch, rec = sent_back(ns)
    g = guide(ns, ch)
    assert seen(g) == [("Send back for rework", rework_url(ns), 25), (f"Make labour bill for {ns.fab.name}", bill_url(ns, ch), 17)]
    assert g["complete"] is False
    follow_links(ns, g)
    mine = g["primary"]
    theirs = next(a for a in offered(lot_guide(ns.lot, ns.owner)) if a["label"] == "Send back for rework")
    assert (theirs["url"], theirs["hint"], theirs["pieces"], theirs["perm"]) == (mine["url"], mine["hint"], mine["pieces"], mine["perm"])
    # on the challan page, the receipt page and the list row
    assert button(escape(rework_url(ns)), "Send back for rework") in guide_of(page(ns.owner, "challan_detail", ch.pk))
    assert button(escape(rework_url(ns)), "Send back for rework") in guide_of(page(ns.owner, "receipt_detail", rec.pk))
    assert f'<a class="btn" href="{escape(rework_url(ns))}">Send back for rework</a>' in row_with(
        page(ns.owner, "challan_list"), f'href="{reverse("challan_detail", args=[ch.pk])}">')
    # someone who may not make challans is told what it waits for
    looker = role_user("rw_looker", {"jobwork.challan": ["view"]}, ns.factory)
    assert guide(ns, ch, looker)["waiting"] == "Send back for rework"


def test_once_the_rework_challan_is_drafted_the_first_challan_stops_asking_and_finishes_when_it_goes_out(ns):
    ch, rec = sent_back(ns)
    bills.post_bill(bills.create_bill(company=ns.company, factory=ns.factory, party=ns.fab, date=DAY, user=ns.owner), user=ns.owner)
    assert fresh(ch).status == "fully_received"      # not marked billed: a bundle of it is still waiting for rework
    g = guide(ns, ch)
    assert [a["label"] for a in offered(g)] == ["Send back for rework"] and g["complete"] is False
    rw = challans.create_challan(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                 bundles=[Bundle.objects.get(pk=ns.bundles[1].pk)], date=DAY, user=ns.owner, kind="rework")
    # the bundle is on a draft now: that draft asks to be issued (on its own page and on the lot), not for another challan
    g = guide(ns, ch)
    assert offered(g) == [] and g["waiting"] == "" and g["complete"] is False
    assert "Nothing to do on this challan right now." in guide_of(page(ns.owner, "challan_detail", ch.pk))
    assert [a["label"] for a in offered(guide(ns, rw))] == [f"Issue challan to {ns.fab.name}"]
    assert "Send back for rework" not in [a["label"] for a in offered(lot_guide(ns.lot, ns.owner))]
    challans.issue_challan(rw, user=ns.owner)
    # the bundle has gone out again on its own challan and everything accepted here is paid: this one is finished
    g = guide(ns, ch)
    assert offered(g) == [] and g["complete"] is True and fresh(ch).status == "fully_received"
    assert states(g) == {"Draft": "done", "Issued": "done", "Received": "done", "Checked": "done", "Billed": "done"}
    assert "This challan is finished." in guide_of(page(ns.owner, "challan_detail", ch.pk))
    assert [a["label"] for a in offered(guide(ns, rw))] == [f"Receive from {ns.fab.name}"]


def test_a_challan_whose_pieces_were_all_rejected_is_finished_without_a_bill(ns):
    ch = issue(ns, ns.bundles[:1])
    receipts.record_qc(receipt_line=receive(ns, ch).lines.get(), accepted=0, rejected=17, reject_reason="Wrong shade", user=ns.owner)
    g = guide(ns, ch)
    assert fresh(ch).status == "fully_received" and offered(g) == [] and g["waiting"] == "" and g["complete"] is True
    # nothing was accepted, so nothing will ever be billed: the stage is left to come, not shown as in progress
    assert states(g) == {"Draft": "done", "Issued": "done", "Received": "done", "Checked": "done", "Billed": "todo"} and current(g) == []
    html = guide_of(page(ns.owner, "challan_detail", ch.pk))
    assert "This challan is finished." in html and "Nothing to do" not in html


def test_a_received_challan_still_waiting_for_qc_is_not_finished_for_someone_who_may_do_nothing(ns):
    ch = issue(ns, ns.bundles[:1])
    receive(ns, ch)
    looker = role_user("unfinished_looker", {"jobwork.challan": ["view"]}, ns.factory)
    g = guide(ns, ch, looker)
    assert g["complete"] is False and g["waiting"] == "Check received pieces"


def test_the_challan_page_header_offers_receive_goods_only_while_the_guide_does(ns):
    ch = issue(ns, ns.bundles[:1])
    plain = f'<a class="btn" href="{reverse("receipt_new", args=[ch.pk])}">Receive goods</a>'
    html = page(ns.owner, "challan_detail", ch.pk)
    head = html[html.index('class="page-head"'):html.index('class="island guide"')]
    assert plain in head and "btn primary" not in head       # the one violet button is the guide's
    looker = role_user("head_looker", {"jobwork.challan": ["view"]}, ns.factory)
    assert "Receive goods" not in page(looker, "challan_detail", ch.pk)
    # every line still out is on an over-receipt that waits for approval: there is nothing to receive
    receive(ns, ch, {ch.bundles.get(): 19})
    assert fresh(ch).is_open
    html = page(ns.owner, "challan_detail", ch.pk)
    assert "Receive goods" not in html and "Approve over-receipt" in guide_of(html)


# ---------------- the labour bill link and the active factory ----------------

def test_the_labour_bill_link_sends_you_back_when_another_factory_is_active(ns, factory2):
    ch = issue(ns, ns.bundles[:1])
    accept_all(ns, receive(ns, ch))
    url = guide(ns, ch)["primary"]["url"]
    assert url == bill_url(ns, ch)
    back = reverse("challan_detail", args=[ch.pk])
    told = f"These pieces are in {ns.factory.name}. Choose it in the top bar, then press the button again."
    c = login(ns.owner)
    for mode in (str(factory2.pk), "all"):
        c.post(reverse("factory_switch"), {"factory": mode})
        r = c.get(url, follow=True)
        assert r.redirect_chain == [(back, 302)], mode
        assert told in r.content.decode()
    # the link never chooses the factory: with the factory left out of it, the form is for the active one, as before
    c.post(reverse("factory_switch"), {"factory": str(factory2.pk)})
    r = c.get(reverse("bill_new"), {"party": ns.fab.pk})
    assert r.status_code == 200 and r.context["factory"] == factory2 and r.context["rows"] == []
    # a made-up factory in the link changes nothing either
    r = c.get(reverse("bill_new"), {"party": ns.fab.pk, "factory": ns.factory.pk})
    assert r.status_code == 200 and r.context["factory"] == factory2 and r.context["rows"] == []
    # with the challan's factory active the link opens the form on those pieces
    c.post(reverse("factory_switch"), {"factory": str(ns.factory.pk)})
    r = c.get(url)
    assert r.status_code == 200 and r.context["factory"] == ns.factory and sum(x["r"].accepted for x in r.context["rows"]) == 17
    assert not ns.fab.job_work_bills.exists()


def test_the_labour_bill_link_never_sends_anyone_to_a_challan_they_cannot_open(ns, factory2):
    ch = issue(ns, ns.bundles[:1])
    accept_all(ns, receive(ns, ch))
    url = bill_url(ns, ch)
    # may make bills in both factories but may not open challans: the existing behaviour, no redirect to a 403
    biller = role_user("bills_only", {"jobwork.bill": ["create", "view"]}, ns.factory)
    biller.allowed_factories.add(factory2)
    c = login(biller)
    c.post(reverse("factory_switch"), {"factory": str(factory2.pk)})
    r = c.get(url)
    assert r.status_code == 200 and r.context["factory"] == factory2
    c.post(reverse("factory_switch"), {"factory": "all"})
    r = c.get(url, follow=True)
    assert r.redirect_chain == [(reverse("bill_list"), 302)] and "Choose a single factory" in r.content.decode()
    # works in the other factory only: the challan is not theirs to see, so nothing about it is said
    far = role_user("far_biller", {"jobwork.bill": ["create", "view"], "jobwork.challan": ["view"]}, factory2)
    r = login(far).get(url)
    assert r.status_code == 200 and r.context["factory"] == factory2 and ns.factory.name not in r.content.decode()
