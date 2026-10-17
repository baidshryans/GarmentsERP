"""The lot page's Step by step view (owner, 15 Oct 2026): pieces in, out, lost, held and still at each route step,
the cost posted at that step, job work still to be billed, and what was recorded there. The steps' cost and the
whole-lot lines always add up to the lot's work in progress, which is what the books hold."""
import importlib
from datetime import date

import pytest
from django.apps import apps
from django.test import Client
from django.urls import reverse

from core.models import Role
from jobwork.services import bills, challans, rates, receipts
from jobwork.services.receipts import Counted
from production.models import LotCostEntry, ProductionAction
from production.services import actions, costing, routes, step_view
from production.services import bundles as bundle_service
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, go, step

K = ProductionAction.Kind


@pytest.fixture
def ns(company, factory, owner):
    ns = build(company, factory, owner)
    ns.bundles = cut(ns)  # B001 S17, B002 M25, B003 M8, B004 L25, B005 L8, B006 XL17
    ns.fab = fabricator(company)
    rates.save_rate(party=ns.fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), rework_rate=D("5"),
                    effective_from=date(2026, 4, 1))
    return ns


def row(view, code):
    return next(r for r in view.rows if r.step.process.code == code)


def adds_up(ns, view):
    """The steps' cost and the whole-lot lines are the lot's work in progress."""
    total = view.spent + view.transfer + view.relief + view.write_off
    return total == view.wip == costing.lot_cost(ns.lot)


def stitched_outside(ns):
    """B001 (17) and B002 (25) to the fabricator; back: 17, and 20 with 3 held and 2 short; QC rejects 2 of B002."""
    ch = challans.create_and_issue(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                   bundles=ns.bundles[:2], date=DAY, user=ns.owner)
    first, second = ch.bundles.order_by("id")
    r = receipts.create_receipt(challan=ch, user=ns.owner, date=DAY, counts=[Counted(first, 17), Counted(second, 20, held=3)])
    l1, l2 = r.lines.order_by("id")
    receipts.record_qc(receipt_line=l1, accepted=17, user=ns.owner)
    receipts.record_qc(receipt_line=l2, accepted=18, rejected=2, reject_reason="Open seam", user=ns.owner)
    return ch


def test_job_work_step_shows_pieces_cost_and_what_is_still_to_be_billed(ns, company, factory):
    stitched_outside(ns)
    view = step_view.build(ns.lot, ns.owner)
    cut_row, stitch = row(view, "CUT"), row(view, "STITCH")
    assert (cut_row.pieces_in, cut_row.pieces_out, cut_row.here) == (100, 42, 58)
    assert cut_row.fabric == costing.cost_breakdown(ns.lot)["fabric"] > 0
    assert (stitch.pieces_in, stitch.short, stitch.rejected, stitch.lost, stitch.held, stitch.here) == (42, 2, 2, 4, 3, 35)
    assert stitch.pieces_in == stitch.pieces_out + stitch.lost + stitch.held + stitch.here      # every piece accounted for
    assert stitch.materials == D("84.00")                           # a zipper a piece at 2.00, sent with the challan
    assert stitch.jobwork == 0 and stitch.to_bill == D("875.00")    # (17 + 18) accepted x 25, not billed yet
    assert stitch.per_piece is None                                 # nothing has gone on from stitching yet
    titles = [e.title for e in stitch.events]
    assert titles[:2] == ["Sent to fabricator", "Received from fabricator"] and titles.count("QC recorded") == 2
    assert view.unlinked == 0 and adds_up(ns, view)

    bill = bills.post_bill(bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner), user=ns.owner)
    assert bill.gross == D("875.00") and bill.deductions > 0        # the 2 short pieces come off at lot cost
    stitch = row(step_view.build(ns.lot, ns.owner), "STITCH")
    assert stitch.jobwork == bill.gross - bill.deductions and stitch.to_bill == 0
    assert any(e.title == "Job work" and e.cost == stitch.jobwork and "/jobwork/bills/" in e.url for e in stitch.events)
    assert adds_up(ns, step_view.build(ns.lot, ns.owner))


def in_house(ns):
    routes.reassign_step(step(ns, "STITCH"), user=ns.owner, reason="Stitch in-house", assignment="in_house", rate=D("10"), rework_rate=D("4"))
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=ns.owner, reason="Not needed")


def test_in_house_labour_belongs_to_the_step_the_pieces_leave_and_per_piece_is_on_good_output(ns):
    in_house(ns)
    b = ns.bundles[1]                                               # 25 pieces
    go(ns, [b], "STITCH")
    go(ns, [b], "IRON", counts={b.pk: bundle_service.Count(loss=1, rejection=2, held=2)})
    view = step_view.build(ns.lot, ns.owner)
    stitch, iron = row(view, "STITCH"), row(view, "IRON")
    assert (stitch.pieces_in, stitch.pieces_out, stitch.loss, stitch.rejected, stitch.held) == (25, 20, 1, 2, 2)
    assert stitch.labour == D("200.00")                             # 20 good pieces x 10, booked as they left stitching
    assert stitch.per_piece == D("10.00")
    assert iron.pieces_in == 20 and iron.here == 20 and iron.cost == 0
    assert any(e.title == "Bundles moved" for e in iron.events)
    assert any(e.title == "Bundles moved (cost of this step)" and e.cost == D("200.00") for e in stitch.events)
    assert adds_up(ns, view)


def test_an_undone_step_shows_no_cost_and_the_lot_still_adds_up(ns):
    in_house(ns)
    b = ns.bundles[1]
    go(ns, [b], "STITCH")
    go(ns, [b], "IRON")
    move = ProductionAction.objects.filter(kind=K.MOVE).order_by("pk").last()
    actions.undo(move, user=ns.owner, reason="Wrong stage")
    view = step_view.build(ns.lot, ns.owner)
    stitch = row(view, "STITCH")
    assert stitch.labour == 0
    undone = [e for e in stitch.events if e.action and e.action.undone]
    assert undone and all(e.cost == 0 for e in undone)
    assert adds_up(ns, view)


def test_whole_lot_costs_stay_off_the_steps(ns, company, factory, factory2):
    in_house(ns)
    b = ns.bundles[1]
    go(ns, [b], "STITCH", factory=factory2)                         # stitched at the second factory
    view = step_view.build(ns.lot, ns.owner)
    assert view.transfer == 0                                       # out of one factory and into the other
    assert row(view, "STITCH").cost == 0 and adds_up(ns, view)


def test_the_lot_page_shows_steps_to_all_and_money_only_with_the_cost_permission(ns, factory):
    stitched_outside(ns)
    sup = make_user("sup")
    sup.roles.add(Role.objects.get(name="Production Supervisor"))
    sup.allowed_factories.add(factory)
    c = Client()
    c.force_login(sup)
    page = c.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "Step by step" in page and 'aria-controls="ev-' in page and "Received from fabricator" in page
    assert "To bill" not in page and "875.00" not in page and "Work in progress now" not in page
    o = Client()
    o.force_login(ns.owner)
    page = o.get(reverse("lot_detail", args=[ns.lot.pk])).content.decode()
    assert "To bill" in page and "875.00" in page and "Work in progress now" in page and "js/step_view.js" in page
    assert "Change the route" in page and "Lot cost</summary>" not in page


def test_cost_recorded_before_steps_carried_their_cost_is_linked_by_the_backfill(ns):
    stitched_outside(ns)
    in_house_issue = LotCostEntry.objects.filter(lot=ns.lot).exclude(step__isnull=True)
    linked = dict(in_house_issue.values_list("pk", "step_id"))
    assert linked                                                   # fabric and challan trims carry their step now
    LotCostEntry.objects.filter(lot=ns.lot).update(step=None)
    importlib.import_module("production.migrations.0010_lot_cost_step_backfill").backfill(apps, None)
    assert dict(LotCostEntry.objects.filter(pk__in=linked).values_list("pk", "step_id")) == linked
