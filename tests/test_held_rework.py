"""Pieces held back for rework (owner, 15 Oct 2026). Pieces that do not come back from a step are either lost
(a shortage, loss or rejection) or held back to be fixed: held pieces stay on the same lot, as a bundle of their own,
and are received or moved on later. Held pieces from a fabricator are paid at the challan's normal rate when they
come back, and no piece is paid twice."""
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError
from core.models import Role
from jobwork import selectors
from jobwork.models import ChallanBundle, JobWorkChallan, Receipt
from jobwork.services import bills, challans, rates, receipts
from jobwork.services.receipts import Counted
from production.models import Bundle, ProductionAction
from production.services import actions
from production.services import bundles as bundle_service
from production.services import costing, routes
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, go, step
from tests.test_step_undo import state
from tests.prod_helpers import set_inhouse_rate

K = ProductionAction.Kind


@pytest.fixture
def ns(company, factory, owner):
    ns = build(company, factory, owner)
    ns.bundles = cut(ns)  # B001 S17, B002 M25, B003 M8, B004 L25, B005 L8, B006 XL17
    ns.fab = fabricator(company)
    rates.save_rate(who=ns.fab, process=step(ns, "STITCH").process, rate=D("25"), effective_from=date(2026, 4, 1))
    return ns


def send(ns, bundles):
    return challans.create_and_issue(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                     bundles=bundles, date=DAY, user=ns.owner)


def receive(ns, challan, counts):
    """counts = {challan line: pieces counted, or (counted, held)}."""
    return receipts.create_receipt(challan=challan, user=ns.owner, date=DAY, counts=[
        Counted(cb, *(n if isinstance(n, tuple) else (n,))) for cb, n in counts.items()])


def held_line(ch):
    return ch.bundles.get(held_from__isnull=False)


# ---------------- fabricator receipts ----------------

def test_held_pieces_stay_with_the_fabricator_on_the_same_challan_and_only_the_rest_is_short(ns, company, factory):
    ch = send(ns, [ns.bundles[1]])                                   # B002, 25 pieces
    cb = ch.bundles.get()
    r = receive(ns, ch, {cb: (20, 3)})                               # 20 back, 3 being fixed, 2 lost
    line = r.lines.get()
    assert (line.qty_received, line.held_qty, line.shortage_qty) == (20, 3, 2)
    cb.refresh_from_db()
    assert (cb.qty_received, cb.qty_held, cb.qty_shortage, cb.pending) == (20, 3, 2, 0)
    parent = Bundle.objects.get(pk=ns.bundles[1].pk)
    assert parent.qty == 20 and parent.status == "received"
    move = parent.movements.get(kind="receipt")
    assert (move.qty_out, move.qty_in, move.shortage) == (22, 20, 2)            # BR-21 on what was left after the split
    held = held_line(ch)
    child = held.bundle
    assert (held.qty_issued, held.rate, held.held_from_id, held.pending) == (3, D("25.00"), cb.pk, 3)
    assert child.split_from_id == parent.pk and child.qty == 3 and child.lot_id == ns.lot.pk
    assert child.held_for_rework and child.status == "at_stage" and child.location.party_id == ns.fab.pk
    ch.refresh_from_db()
    assert ch.status == "partly_received"
    assert step(ns, "STITCH").status == "in_progress"                # the lot waits for the held pieces
    row = selectors.fabricator_ledger(ns.owner, ns.fab)[0]
    assert (row["issued"], row["received"], row["shortage"], row["in_process"], row["held"]) == (25, 20, 2, 3, 3)
    assert not costing.check_wip_reconciles(company)


def test_held_pieces_come_back_later_and_are_paid_at_the_normal_rate_once(ns, company, factory):
    ch = send(ns, [ns.bundles[1]])
    cb = ch.bundles.get()
    first = receive(ns, ch, {cb: (22, 3)})
    receipts.record_qc(receipt_line=first.lines.get(), accepted=22, user=ns.owner)
    later = receive(ns, ch, {held_line(ch): 3})
    child = held_line(ch).bundle
    child.refresh_from_db()
    assert child.status == "received" and not child.held_for_rework
    receipts.record_qc(receipt_line=later.lines.get(), accepted=3, user=ns.owner)
    ch.refresh_from_db()
    assert ch.status == "fully_received"
    bill = bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner)
    assert bill.gross == D("625.00")                                 # (22 + 3) x 25: the normal rate, 25 pieces in all
    bills.post_bill(bill, user=ns.owner)
    with pytest.raises(BusinessRuleError, match="no checked pieces waiting"):
        bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner)
    assert JobWorkChallan.objects.get().status == "billed"
    assert not costing.check_wip_reconciles(company)


def test_held_pieces_that_never_come_back_are_written_off_as_a_shortage_later(ns, company):
    ch = send(ns, [ns.bundles[1]])
    receive(ns, ch, {ch.bundles.get(): (20, 5)})
    r = receive(ns, ch, {held_line(ch): 0})
    assert r.lines.get().shortage_qty == 5
    assert held_line(ch).bundle.status == "scrapped"
    ch.refresh_from_db()
    assert ch.status == "fully_received" and not costing.check_wip_reconciles(company)


def test_held_pieces_must_fit_in_what_was_issued_and_some_must_come_back(ns):
    ch = send(ns, [ns.bundles[1]])
    cb = ch.bundles.get()
    with pytest.raises(BusinessRuleError, match="all its pieces are still with the fabricator"):
        receive(ns, ch, {cb: (0, 25)})
    with pytest.raises(BusinessRuleError, match="are more than the 25 pieces issued"):
        receive(ns, ch, {cb: (23, 3)})
    with pytest.raises(BusinessRuleError, match="cannot be negative"):
        receive(ns, ch, {cb: (20, -1)})
    assert not Receipt.objects.exists() and ch.bundles.count() == 1


def test_a_held_line_is_not_counted_again_as_issued(ns, company, factory):
    ch = send(ns, ns.bundles[:2])                                    # 17 + 25 = 42 pieces
    receive(ns, ch, {ch.bundles.order_by("id")[1]: (21, 4)})
    page_total = sum(l.qty_issued for l in ch.bundles.all() if not l.is_held)
    assert page_total == 42 and ch.bundles.count() == 3


def test_a_receipt_with_held_pieces_is_undone_completely(ns):
    ch = send(ns, [ns.bundles[1]])
    sent = state(ns)
    receive(ns, ch, {ch.bundles.get(): (20, 3)})
    actions.undo(ProductionAction.objects.filter(kind=K.RECEIPT).order_by("pk").last(), user=ns.owner, reason="Counted wrongly")
    assert state(ns) == sent
    assert ch.bundles.count() == 1 and ch.bundles.get().qty_held == 0
    assert JobWorkChallan.objects.get().status == "issued"
    r = receive(ns, ch, {ch.bundles.get(): 25})                       # counted again, correctly this time
    assert r.lines.get().qty_received == 25


def test_the_receipt_of_held_pieces_must_be_undone_before_the_one_that_held_them(ns):
    ch = send(ns, [ns.bundles[1]])
    receive(ns, ch, {ch.bundles.get(): (20, 3)})
    holding = ProductionAction.objects.filter(kind=K.RECEIPT).order_by("pk").last()
    receive(ns, ch, {held_line(ch): 3})
    with pytest.raises(BusinessRuleError, match="came after this step"):
        actions.undo(holding, user=ns.owner, reason="x")


# ---------------- in-house moves ----------------

def in_house(ns):
    routes.reassign_step(step(ns, "STITCH"), user=ns.owner, reason="Stitch in-house", assignment="in_house")
    set_inhouse_rate(step(ns, "STITCH").process.code, D("10"))
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=ns.owner, reason="Not needed")


def labour(ns):
    return costing.cost_breakdown(ns.lot)["labour"]


def test_pieces_held_at_an_in_house_stage_stay_there_and_move_on_later_at_the_normal_rate(ns, company):
    in_house(ns)
    b = ns.bundles[1]                                                # 25 pieces
    go(ns, [b], "STITCH")
    (m,) = go(ns, [b], "IRON", counts={b.pk: bundle_service.Count(held=5, loss=1)})
    assert (m.qty_out, m.qty_in, m.loss) == (20, 19, 1)                # BR-21 on the pieces that left
    assert labour(ns) == D("190.00")                                 # 19 pieces passed stitching at 10
    child = Bundle.objects.get(split_from=b)
    assert child.qty == 5 and child.held_for_rework and child.current_step == step(ns, "STITCH")
    assert Bundle.objects.get(pk=b.pk).current_step == step(ns, "IRON")
    assert step(ns, "STITCH").status == "in_progress"
    go(ns, [child], "IRON")
    child.refresh_from_db()
    assert not child.held_for_rework and child.current_step == step(ns, "IRON")
    assert labour(ns) == D("240.00")                                 # + 5 x 10: the normal rate, not the rework rate
    assert not costing.check_wip_reconciles(company)


def test_holding_every_piece_back_is_refused(ns):
    in_house(ns)
    b = ns.bundles[2]                                                # 8 pieces
    go(ns, [b], "STITCH")
    with pytest.raises(BusinessRuleError, match="nothing is left to move"):
        go(ns, [b], "IRON", counts={b.pk: bundle_service.Count(held=6, shortage=2)})
    assert Bundle.objects.get(pk=b.pk).qty == 8 and not Bundle.objects.filter(split_from=b).exists()


def test_a_move_with_held_pieces_is_undone_completely(ns):
    in_house(ns)
    b = ns.bundles[1]
    go(ns, [b], "STITCH")
    before = state(ns)
    go(ns, [b], "IRON", counts={b.pk: bundle_service.Count(held=5)})
    actions.undo(ProductionAction.objects.filter(kind=K.MOVE).order_by("pk").last(), user=ns.owner, reason="Wrong count")
    assert state(ns) == before


# ---------------- screens ----------------

def login(user):
    c = Client()
    c.force_login(user)
    return c


def supervisor(factory):
    u = make_user("sup")
    u.roles.add(Role.objects.get(name="Production Supervisor"))
    u.allowed_factories.add(factory)
    return u


def test_receipt_and_challan_screens_take_and_show_held_pieces(ns, factory):
    ch = send(ns, [ns.bundles[1]])
    cb = ch.bundles.get()
    c = login(supervisor(factory))
    form = c.get(reverse("receipt_new", args=[ch.pk])).content.decode()
    assert "Held for rework" in form and f'name="held_{cb.pk}"' in form
    bad = c.post(reverse("receipt_new", args=[ch.pk]), {"date": "2026-06-20", f"use_{cb.pk}": "on", f"count_{cb.pk}": "23",
                                                        f"held_{cb.pk}": "3"})
    assert bad.status_code == 200 and "more than the 25 pieces issued" in bad.content.decode()
    assert 'value="23"' in bad.content.decode()                      # what was typed comes back
    r = c.post(reverse("receipt_new", args=[ch.pk]), {"date": "2026-06-20", f"use_{cb.pk}": "on", f"count_{cb.pk}": "20",
                                                      f"held_{cb.pk}": "3"})
    assert r.status_code == 302
    detail = c.get(r.url).content.decode()
    assert "held for rework 3" in detail and "short 2" in detail
    page = c.get(reverse("challan_detail", args=[ch.pk])).content.decode()
    child = held_line(ch).bundle
    assert child.bundle_no in page and "Held for rework" in page and f"from {ns.bundles[1].bundle_no}" in page
    again = c.get(reverse("receipt_new", args=[ch.pk])).content.decode()
    assert child.bundle_no in again                                  # the held pieces wait to be received


def test_move_screen_takes_held_pieces(ns, factory):
    in_house(ns)
    b = ns.bundles[1]
    go(ns, [b], "STITCH")
    c = login(supervisor(factory))
    page = c.get(reverse("move_bundles"), {"lot": ns.lot.pk}).content.decode()
    assert f'name="held_{b.pk}"' in page
    r = c.post(reverse("move_bundles"), {"lot": ns.lot.pk, "bundle": [b.pk], "to_step": step(ns, "IRON").pk, f"held_{b.pk}": "4"})
    assert r.status_code == 302
    child = Bundle.objects.get(split_from=b)
    assert child.qty == 4 and child.held_for_rework
    page = c.get(reverse("move_bundles"), {"lot": ns.lot.pk}).content.decode()
    assert child.bundle_no in page and "Held for rework" in page
