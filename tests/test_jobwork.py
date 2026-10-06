from datetime import date
from decimal import Decimal

import pytest

from core.exceptions import BusinessRuleError, FactoryNotAllowed
from core.models import Location
from inventory.models import StockBalance
from inventory.services import stock
from jobwork.models import ChallanBundle, JobWorkChallan, QcResult, Receipt
from jobwork.services import bills, challans, rates, receipts
from jobwork.services.challans import SecondFabricatorWarning
from jobwork.services.receipts import Counted
from ledger.selectors import outstanding_bills
from masters.models import Size
from production.models import Bundle, LotCostEntry
from production.services import bundles as bundle_service
from production.services import costing, routes
from tax.models import TaxTemplate
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, gl, step

TDS2 = "TDS 194C - others (2%)"


@pytest.fixture
def ns(company, factory, owner):
    ns = build(company, factory, owner)
    ns.bundles = cut(ns)  # B001 S17, B002 M25, B003 M8, B004 L25, B005 L8, B006 XL17
    ns.fab = fabricator(company)
    ns.fab2 = fabricator(company, "Gupta Stitching", "9822222233")
    rates.save_rate(party=ns.fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), rework_rate=D("5"),
                    effective_from=date(2026, 4, 1))
    rates.save_rate(party=ns.fab2, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("24"),
                    effective_from=date(2026, 4, 1))
    return ns


def issue(ns, party, bundles, **kw):
    c = challans.create_challan(company=ns.company, factory=ns.factory, party=party, lot=ns.lot, step=step(ns, "STITCH"),
                                bundles=bundles, date=DAY, user=ns.owner, **kw)
    return challans.issue_challan(c, user=ns.owner)


def receive(ns, challan, counts=None, trims=None, **kw):
    counts = counts if counts is not None else {cb: cb.qty_issued for cb in challan.bundles.all()}
    return receipts.create_receipt(challan=challan, user=ns.owner, date=DAY, trims=trims,
                                   counts=[Counted(cb, n) for cb, n in counts.items()], **kw)


def qc(ns, receipt_line, **kw):
    return receipts.record_qc(receipt_line=receipt_line, user=ns.owner, **kw)


# ---------------- labour rates (JOB-06) ----------------

def test_rate_types_a_b_c_d_resolve_as_the_agreement_says(ns, company):
    proc = step(ns, "STITCH").process
    f = ns.fab
    b = rates.save_rate(party=f, process=proc, rate_type="B", base_rate=D("20"), addons=[("Bar tack", D("2")), ("Thread trim", D("1.5"))],
                        effective_from=date(2026, 5, 1))
    spec = rates.resolve(f, step(ns, "STITCH"), date(2026, 5, 2))
    assert spec.rate_type == "B" and spec.for_size(ns.sizes["M"]) == D("23.50")
    c = rates.save_rate(party=f, process=proc, rate_type="C", effective_from=date(2026, 6, 1),
                        size_rates={ns.sizes["S"]: D("22"), ns.sizes["M"]: D("24"), ns.sizes["L"]: D("26"), ns.sizes["XL"]: D("28")})
    spec = rates.resolve(f, step(ns, "STITCH"), date(2026, 6, 2))
    assert spec.rate_type == "C" and [spec.for_size(ns.sizes[x]) for x in "S M L XL".split()] == [D("22"), D("24"), D("26"), D("28")]
    rates.save_rate(party=f, process=proc, rate_type="D", flat_amount=D("5000"), effective_from=date(2026, 7, 1))
    spec = rates.resolve(f, step(ns, "STITCH"), date(2026, 7, 2))
    assert spec.rate_type == "D" and spec.flat == D("5000.00")
    assert rates.resolve(f, step(ns, "STITCH"), date(2026, 4, 15)).for_size(ns.sizes["M"]) == D("25.00")  # an older date keeps the older rate


def test_rate_validation(ns):
    proc = step(ns, "STITCH").process
    with pytest.raises(BusinessRuleError):
        rates.save_rate(party=ns.fab, process=proc, rate_type="A", base_rate=D("0"), effective_from=date(2026, 8, 1))
    with pytest.raises(BusinessRuleError, match="already"):
        rates.save_rate(party=ns.fab, process=proc, rate_type="A", base_rate=D("30"), effective_from=date(2026, 4, 1))
    with pytest.raises(BusinessRuleError, match="add-on"):
        rates.save_rate(party=ns.fab, process=proc, rate_type="B", base_rate=D("30"), effective_from=date(2026, 8, 1))


# ---------------- issuing (E8.1, BR-04, BR-05) ----------------

def test_issue_moves_bundles_to_the_fabricator_and_trims_into_lot_cost(ns, company, factory):
    ch = issue(ns, ns.fab, ns.bundles[:3])  # S17 + M25 + M8 = 50 pieces
    assert ch.status == "issued" and ch.number == "JWC/LDH1/26-27/0001" and ch.rate_type == "A"
    assert [cb.rate for cb in ch.bundles.all()] == [D("25.00")] * 3
    place = Location.objects.get(factory=factory, party=ns.fab)
    assert place.loc_type == "fabricator" and sum(int(b.qty) for b in StockBalance.objects.filter(location=place)) == 50
    b = Bundle.objects.get(pk=ns.bundles[0].pk)
    assert b.status == "at_stage" and b.location == place and b.current_step == step(ns, "STITCH")
    trim = ch.trims.get()  # BOM: one zipper per piece
    assert trim.qty_issued == D("50.000") and trim.value == D("100.00")
    assert costing.lot_cost(ns.lot) == D("9130.00") and costing.cost_breakdown(ns.lot)["trim"] == D("100.00")
    assert stock.on_hand(factory, ns.zipper) == (D("950.000"), D("1900.00"))
    assert step(ns, "STITCH").status == "in_progress"
    assert not costing.check_wip_reconciles(company)


def test_a_challan_is_for_one_lot_and_one_fabricator_and_open_bundles_cannot_be_issued_twice(ns, company, factory, owner):
    issue(ns, ns.fab, ns.bundles[:1])
    with pytest.raises(BusinessRuleError, match="already on an open challan"):
        challans.create_challan(company=company, factory=factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                bundles=ns.bundles[:1], date=DAY, user=owner)
    cust = __import__("masters.services.parties", fromlist=["x"]).create_party(
        company=company, name="Dealer", mobile="9833333300", is_customer=True)
    with pytest.raises(BusinessRuleError, match="not marked as a fabricator"):
        challans.create_challan(company=company, factory=factory, party=cust, lot=ns.lot, step=step(ns, "STITCH"),
                                bundles=ns.bundles[1:2], date=DAY, user=owner)


def test_issuing_the_same_lot_to_a_second_fabricator_warns_until_confirmed(ns, company, factory, owner):
    issue(ns, ns.fab, ns.bundles[:2])
    with pytest.raises(SecondFabricatorWarning, match="Sharma Stitching"):
        challans.create_challan(company=company, factory=factory, party=ns.fab2, lot=ns.lot, step=step(ns, "STITCH"),
                                bundles=ns.bundles[3:4], date=DAY, user=owner)
    ch = challans.create_challan(company=company, factory=factory, party=ns.fab2, lot=ns.lot, step=step(ns, "STITCH"),
                                 bundles=ns.bundles[3:4], date=DAY, user=owner, confirm_second_fabricator=True)
    assert ch.second_fabricator_ack


def test_a_challan_needs_a_labour_rate(ns, company, factory, owner):
    nobody = fabricator(company, "No Rate Stitching", "9844444455")
    with pytest.raises(BusinessRuleError, match="no labour rate"):
        challans.create_challan(company=company, factory=factory, party=nobody, lot=ns.lot, step=step(ns, "STITCH"),
                                bundles=ns.bundles[:1], date=DAY, user=owner)


def test_a_rate_change_after_issue_does_not_touch_the_challan(ns, company):
    ch = issue(ns, ns.fab, ns.bundles[:1])
    rates.save_rate(party=ns.fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("40"), effective_from=date(2026, 6, 1))
    assert ChallanBundle.objects.get(challan=ch).rate == D("25.00")  # BR-12: price changes apply to later documents only


def test_challan_scoping(ns, company, factory, factory2, owner):
    stranger = make_user("stranger")
    with pytest.raises(FactoryNotAllowed):
        challans.create_challan(company=company, factory=factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                bundles=ns.bundles[:1], date=DAY, user=stranger)
    issue(ns, ns.fab, ns.bundles[:1])
    assert JobWorkChallan.objects.for_user(owner).count() == 1 and JobWorkChallan.objects.for_user(stranger).count() == 0


# ---------------- receiving (E8.2, BR-03) ----------------

def test_partial_receipt_then_the_rest_moves_the_challan_through_its_statuses(ns, company):
    ch = issue(ns, ns.fab, ns.bundles[:3])
    first = receive(ns, ch, {cb: cb.qty_issued for cb in list(ch.bundles.all())[:2]})
    ch.refresh_from_db()
    assert ch.status == "partly_received" and first.number.startswith("JWR/") and first.status == "received"
    assert Bundle.objects.get(pk=ns.bundles[0].pk).status == "received"
    assert Bundle.objects.get(pk=ns.bundles[2].pk).status == "at_stage"  # still with the fabricator
    receive(ns, ch, {list(ch.bundles.all())[2]: 8})
    ch.refresh_from_db()
    assert ch.status == "fully_received"
    assert not costing.check_wip_reconciles(company)


def test_done_by_the_fabricator_is_not_a_receipt_and_a_bundle_is_received_only_once(ns):
    ch = issue(ns, ns.fab, ns.bundles[:1])
    receive(ns, ch)
    with pytest.raises(BusinessRuleError, match="Only an issued challan"):
        receive(ns, ch)


def test_a_short_count_records_the_shortage_against_the_fabricator_at_cost(ns, factory):
    ch = issue(ns, ns.fab, ns.bundles[:2])  # S17 + M25
    pieces, cost = costing.live_pieces(ns.lot, factory), costing.lot_cost(ns.lot, factory)
    cb = list(ch.bundles.all())[1]
    r = receive(ns, ch, {list(ch.bundles.all())[0]: 17, cb: 23})
    line = r.lines.get(challan_bundle=cb)
    assert line.shortage_qty == 2 and line.shortage_value == costing.r2(cost / pieces * 2)
    m = Bundle.objects.get(pk=cb.bundle_id)
    assert m.qty == 23
    move = m.movements.get(kind="receipt")
    assert (move.qty_out, move.qty_in, move.shortage) == (25, 23, 2)  # BR-21


def test_receiving_more_than_was_issued_waits_for_the_owner_and_moves_nothing(ns, accountant, factory):
    ch = issue(ns, ns.fab, ns.bundles[:1])  # 17 pieces
    r = receive(ns, ch, {list(ch.bundles.all())[0]: 19})
    assert r.status == "pending_approval" and r.number is None
    assert Bundle.objects.get(pk=ns.bundles[0].pk).status == "at_stage"  # nothing moved yet
    with pytest.raises(BusinessRuleError, match="owner"):
        receipts.approve_receipt(r, user=accountant)
    with pytest.raises(BusinessRuleError, match="waiting for approval"):
        qc(ns, r.lines.get(), accepted=19)
    r = receipts.approve_receipt(r, user=ns.owner)
    b = Bundle.objects.get(pk=ns.bundles[0].pk)
    assert r.status == "received" and r.approved_by == ns.owner and b.qty == 19 and b.status == "received"
    move = b.movements.get(kind="receipt")
    assert move.qty_extra == 2 and move.qty_out + move.qty_extra == move.qty_in  # BR-21 with the approved extra


def test_returned_trims_go_back_to_stock_and_missing_ones_are_recorded(ns, company, factory):
    ch = issue(ns, ns.fab, ns.bundles[:1])  # 17 zippers issued
    trim = ch.trims.get()
    receive(ns, ch, trims={trim: (D("3"), D("2"))})
    trim.refresh_from_db()
    assert trim.qty_returned == D("3.000") and trim.qty_missing == D("2.000")
    assert stock.on_hand(factory, ns.zipper)[0] == D("986.000")  # 1000 - 17 + 3
    assert costing.cost_breakdown(ns.lot)["trim"] == D("28.00")  # 34 issued less 6 returned
    with pytest.raises(BusinessRuleError):
        receipts.create_receipt(challan=ch, user=ns.owner, date=DAY, counts=[], trims={trim: (D("99"), D("0"))})
    assert not costing.check_wip_reconciles(company)


# ---------------- QC (E8.3, BR-17) ----------------

def test_qc_accepts_rejects_and_sends_whole_bundles_back_for_rework(ns, factory):
    ch = issue(ns, ns.fab, ns.bundles[:3])  # B001 S17, B002 M25, B003 M8
    r = receive(ns, ch)
    l1, l2, l3 = list(r.lines.order_by("id"))
    qc(ns, l1, accepted=17)
    qc(ns, l2, accepted=22, rejected=3, reject_reason="Open seams")
    qc(ns, l3, accepted=0, rework=8)
    b1, b2, b3 = (Bundle.objects.get(pk=b.pk) for b in ns.bundles[:3])
    assert b1.status == "ready" and b1.completed_seq == step(ns, "STITCH").sequence
    assert b2.status == "ready" and b2.qty == 22
    assert b3.status == "rework" and b3.rework_qty == 8 and b3.qty == 8
    rejects = Location.objects.get(factory=factory, name="Rejects")
    assert sum(int(x.qty) for x in StockBalance.objects.filter(location=rejects)) == 3
    r.refresh_from_db()
    assert r.status == "qc_done" and QcResult.objects.count() == 3
    with pytest.raises(BusinessRuleError, match="already been recorded"):
        qc(ns, l1, accepted=17)


def test_qc_quantities_must_add_up_and_rejects_need_a_reason(ns):
    ch = issue(ns, ns.fab, ns.bundles[:1])
    line = receive(ns, ch).lines.get()
    with pytest.raises(BusinessRuleError, match="must equal"):
        qc(ns, line, accepted=10)
    with pytest.raises(BusinessRuleError, match="reason"):
        qc(ns, line, accepted=15, rejected=2)
    with pytest.raises(BusinessRuleError, match="whole bundle"):
        qc(ns, line, accepted=10, rework=7)
    assert not QcResult.objects.exists()


def test_scrapped_rejects_leave_stock_instead_of_going_to_rejects(ns, factory):
    ch = issue(ns, ns.fab, ns.bundles[:1])
    line = receive(ns, ch).lines.get()
    qc(ns, line, accepted=15, rejected=2, reject_reason="Burnt", destination="scrap")
    rejects = Location.objects.get(factory=factory, name="Rejects")
    assert not StockBalance.objects.filter(location=rejects, qty__gt=0).exists()
    move = Bundle.objects.get(pk=ns.bundles[0].pk).movements.get(kind="qc")
    assert (move.qty_out, move.qty_in, move.loss) == (17, 15, 2)


def test_rework_goes_out_on_its_own_challan_at_the_rework_rate_and_comes_back_accepted(ns):
    ch = issue(ns, ns.fab, ns.bundles[2:3])  # B003, 8 pieces
    qc(ns, receive(ns, ch).lines.get(), accepted=0, rework=8)
    b = Bundle.objects.get(pk=ns.bundles[2].pk)
    rw = challans.create_challan(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                 bundles=[b], date=DAY, user=ns.owner, kind="rework")
    rw = challans.issue_challan(rw, user=ns.owner)
    cb = rw.bundles.get()
    assert rw.kind == "rework" and cb.rate == D("30.00") and cb.qty_issued == 8  # 25 + 5 rework charge
    assert Bundle.objects.get(pk=b.pk).status == "at_stage" and Bundle.objects.get(pk=b.pk).rework_qty == 0
    assert not rw.trims.exists()  # no trims go out again
    res = qc(ns, receive(ns, rw).lines.get(), accepted=8)
    assert res.is_rework_pass and Bundle.objects.get(pk=b.pk).status == "ready"


def embroidery_sent_back(ns):
    """B001 stitched and accepted, then sent out for embroidery and sent back by QC: it waits for rework at embroidery."""
    emb = step(ns, "EMB")
    rates.save_rate(party=ns.fab, process=emb.process, rate_type="A", base_rate=D("8"), rework_rate=D("2"), effective_from=date(2026, 4, 1))
    qc(ns, receive(ns, issue(ns, ns.fab, ns.bundles[:1])).lines.get(), accepted=17)
    out = challans.issue_challan(challans.create_challan(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=emb,
                                                         bundles=ns.bundles[:1], date=DAY, user=ns.owner), user=ns.owner)
    qc(ns, receive(ns, out).lines.get(), accepted=0, rework=17)
    b = Bundle.objects.get(pk=ns.bundles[0].pk)
    assert b.status == "rework" and b.current_step_id == emb.pk
    return b, emb


def test_a_rework_challan_takes_only_bundles_waiting_at_its_own_step(ns):
    b, emb = embroidery_sent_back(ns)
    before = JobWorkChallan.objects.count()
    with pytest.raises(BusinessRuleError, match=r"Bundle B001 is waiting for rework at Embroidery, not Stitching"):
        challans.create_challan(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                bundles=[b], date=DAY, user=ns.owner, kind="rework")
    assert JobWorkChallan.objects.count() == before  # nothing was saved
    rw = challans.create_challan(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=emb,
                                 bundles=[b], date=DAY, user=ns.owner, kind="rework")
    assert rw.kind == "rework" and rw.step_id == emb.pk and rw.bundles.get().rate == D("10.00")  # 8 + 2 rework charge


def test_the_rework_form_lists_only_the_rework_bundles_of_the_chosen_step(ns):
    from django.test import Client
    from django.urls import reverse

    b, emb = embroidery_sent_back(ns)
    qc(ns, receive(ns, issue(ns, ns.fab, ns.bundles[2:3])).lines.get(), accepted=0, rework=8)  # B003 waits at stitching
    c = Client()
    c.force_login(ns.owner)

    def listed(code):
        page = c.get(reverse("challan_new"), {"lot": ns.lot.pk, "kind": "rework", "step": step(ns, code).pk})
        return [x.bundle_no for x in page.context["bundles"]]

    assert listed("EMB") == ["B001"] and listed("STITCH") == ["B003"] and listed("WASH") == []
    # a hand-made post for the wrong step is refused by the service and says where the bundle waits
    r = c.post(reverse("challan_new"), {"lot": ns.lot.pk, "step": step(ns, "STITCH").pk, "kind": "rework", "factory": ns.factory.pk,
                                        "party": ns.fab.pk, "date": "2026-06-16", "bundle": [b.pk]})
    assert r.status_code == 200 and "waiting for rework at Embroidery, not Stitching" in r.content.decode()
    assert not ns.lot.challans.filter(kind="rework").exists()


def test_a_bundle_waiting_for_rework_cannot_be_moved_on_or_packed(ns):
    ch = issue(ns, ns.fab, ns.bundles[:1])
    qc(ns, receive(ns, ch).lines.get(), accepted=0, rework=17)
    b = Bundle.objects.get(pk=ns.bundles[0].pk)
    routes.reassign_step(step(ns, "IRON"), user=ns.owner, reason="x", assignment="in_house")
    with pytest.raises(BusinessRuleError, match="rework"):
        bundle_service.move_bundles(bundles=[b], to_step=step(ns, "IRON"), user=ns.owner)


# ---------------- labour bill (E8.4, JOB-07, BR-17) ----------------

def accepted_challan(ns, party=None, bundles=None, accepted=None):
    ch = issue(ns, party or ns.fab, bundles or ns.bundles[:2])
    r = receive(ns, ch)
    for line in r.lines.order_by("id"):
        qc(ns, line, accepted=line.qty_received if accepted is None else accepted)
    return ch


def test_a_bill_pays_only_accepted_pieces_at_the_rate_on_the_challan(ns, company, factory):
    ch = issue(ns, ns.fab, ns.bundles[:3])
    l1, l2, l3 = list(receive(ns, ch).lines.order_by("id"))
    qc(ns, l1, accepted=17)
    qc(ns, l2, accepted=22, rejected=3, reject_reason="Open seams")
    qc(ns, l3, accepted=0, rework=8)  # not accepted, so not paid
    bill = bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner)
    assert (bill.gross, bill.deductions, bill.tds, bill.net) == (D("975.00"), D("0.00"), D("0.00"), D("975.00"))  # (17 + 22) x 25
    line = bill.lines.get()
    assert line.qty == 39 and line.rate == D("25.00") and "Stitching" in line.description
    bill = bills.post_bill(bill, user=ns.owner)
    assert bill.number == "LB/LDH1/26-27/0001" and bill.status == "posted"
    assert gl(company, "stock_wip", factory) == D("10105.00")  # 9,030 fabric + 100 trims + 975 labour
    assert costing.cost_breakdown(ns.lot)["jobwork"] == D("975.00")
    assert outstanding_bills(ns.fab.payable_ledger)["bills"] == {bill.number: D("-975.00")}
    assert not costing.check_wip_reconciles(company)


def test_accepted_pieces_can_never_be_paid_twice(ns, company, factory):
    accepted_challan(ns)
    first = bills.post_bill(bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner), user=ns.owner)
    with pytest.raises(BusinessRuleError, match="no accepted pieces waiting"):
        bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner)
    with pytest.raises(BusinessRuleError, match="not been paid before"):
        bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner,
                          qc_results=[first.lines.first().qc_results.first()])
    ch = JobWorkChallan.objects.get(party=ns.fab)
    assert ch.status == "billed"


def test_nothing_is_billable_before_qc_accepts_it(ns, company, factory):
    ch = issue(ns, ns.fab, ns.bundles[:2])
    receive(ns, ch)  # received but not QC'd
    with pytest.raises(BusinessRuleError, match="no accepted pieces"):
        bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner)


def test_tds_is_deducted_only_when_selected_and_deductions_come_off_first(ns, company, factory):
    ch = issue(ns, ns.fab, ns.bundles[:2])  # S17 + M25, 17 zippers + 25 zippers
    trims = ch.trims.get()
    pieces, cost = costing.live_pieces(ns.lot, factory), costing.lot_cost(ns.lot, factory)
    r = receive(ns, ch, {list(ch.bundles.all())[0]: 17, list(ch.bundles.all())[1]: 24}, trims={trims: (D("0"), D("3"))})
    for line in r.lines.order_by("id"):
        qc(ns, line, accepted=line.qty_received)
    shortage_value = costing.r2(cost / pieces * 1)
    missing_value = D("6.00")  # 3 zippers at 2
    pend = {d[0]: d[4] for d in bills.pending_deductions(ns.fab, factory)}
    assert pend == {"shortage": shortage_value, "missing_trims": missing_value}
    bill = bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner,
                             tds_template=TaxTemplate.objects.get(name=TDS2))
    gross = D("41") * D("25")  # 17 + 24 accepted
    base = gross - shortage_value - missing_value
    assert bill.gross == gross and bill.deductions == shortage_value + missing_value
    assert bill.tds == costing.r2(base * D("0.02")) and bill.net == base - bill.tds
    bill = bills.post_bill(bill, user=ns.owner)
    assert gl(company, "tds_payable", factory) == -bill.tds
    assert outstanding_bills(ns.fab.payable_ledger)["bills"] == {bill.number: -bill.net}
    assert costing.cost_breakdown(ns.lot)["jobwork"] == base  # lot cost carries the net of recoveries
    assert not bills.pending_deductions(ns.fab, factory)  # recovered once
    assert not costing.check_wip_reconciles(company)


def test_no_tds_without_a_template(ns, company, factory):
    accepted_challan(ns)
    bill = bills.post_bill(bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner), user=ns.owner)
    assert bill.tds == 0 and gl(company, "tds_payable", factory) == 0


def test_flat_per_lot_rate_is_paid_pro_rata_on_accepted_pieces(ns, company, factory):
    rates.save_rate(party=ns.fab2, process=step(ns, "STITCH").process, rate_type="D", flat_amount=D("1000"), effective_from=date(2026, 5, 1))
    ch = issue(ns, ns.fab2, ns.bundles[:2])  # 42 pieces issued for a flat 1,000
    assert ch.rate_type == "D" and ch.flat_amount == D("1000.00")
    r = receive(ns, ch)
    l1, l2 = list(r.lines.order_by("id"))
    qc(ns, l1, accepted=17)
    qc(ns, l2, accepted=20, rejected=5, reject_reason="Stains")
    bill = bills.create_bill(company=company, factory=factory, party=ns.fab2, date=DAY, user=ns.owner)
    assert bill.gross == costing.r2(D("1000") * 17 / 42) + costing.r2(D("1000") * 20 / 42)


def test_size_wise_rates_are_fixed_per_bundle_when_issued(ns, company, factory):
    rates.save_rate(party=ns.fab2, process=step(ns, "STITCH").process, rate_type="C", effective_from=date(2026, 5, 1),
                    size_rates={ns.sizes["S"]: D("20"), ns.sizes["M"]: D("30"), ns.sizes["L"]: D("40"), ns.sizes["XL"]: D("50")})
    ch = issue(ns, ns.fab2, [ns.bundles[0], ns.bundles[1]])  # S17 and M25
    assert sorted(cb.rate for cb in ch.bundles.all()) == [D("20.00"), D("30.00")]
    r = receive(ns, ch)
    for line in r.lines.order_by("id"):
        qc(ns, line, accepted=line.qty_received)
    bill = bills.create_bill(company=company, factory=factory, party=ns.fab2, date=DAY, user=ns.owner)
    assert bill.gross == D("17") * 20 + D("25") * 30 and bill.lines.count() == 2


def test_cancelling_a_posted_bill_reverses_books_and_cost_and_frees_the_pieces(ns, company, factory):
    accepted_challan(ns)
    bill = bills.post_bill(bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner), user=ns.owner)
    with pytest.raises(BusinessRuleError, match="reason"):
        bills.cancel_bill(bill, user=ns.owner, reason="")
    bills.cancel_bill(bill, user=ns.owner, reason="Wrong rate")
    assert gl(company, "stock_wip", factory) == D("9114.00") and outstanding_bills(ns.fab.payable_ledger)["bills"] == {}  # fabric + 42 zippers
    assert costing.cost_breakdown(ns.lot)["jobwork"] == D("0.00")
    again = bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner)  # payable again
    assert again.gross == D("42") * D("25")
    assert not costing.check_wip_reconciles(company)


def test_billing_is_scoped_to_the_factory_and_party(ns, company, factory, factory2, owner):
    accepted_challan(ns)
    with pytest.raises(BusinessRuleError):
        bills.create_bill(company=company, factory=factory, party=ns.fab2, date=DAY, user=owner)
    with pytest.raises(FactoryNotAllowed):
        bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=make_user("stranger"))


# ---------------- A11-style journey: cut at factory 1, stitched outside, ironed at factory 2, re-pressed ----------------

def test_one_lot_cut_in_house_stitched_by_a_subcontractor_ironed_at_factory_2_and_sent_back_for_a_re_press(ns, company, factory, factory2):
    from ledger.selectors import trial_balance

    routes.skip_step(step(ns, "EMB"), user=ns.owner, reason="n/a")
    routes.skip_step(step(ns, "PRINT"), user=ns.owner, reason="n/a")
    routes.skip_step(step(ns, "WASH"), user=ns.owner, reason="n/a")
    routes.reassign_step(step(ns, "IRON"), user=ns.owner, reason="Iron at unit 2", assignment="in_house", factory=factory2, rate=D("2"))
    for code in ("FINISH", "QC", "PACK"):
        routes.reassign_step(step(ns, code), user=ns.owner, reason="Finish at unit 2", assignment="in_house", factory=factory2)
    ch = issue(ns, ns.fab, ns.bundles)  # all 100 pieces
    r = receive(ns, ch)
    for line in r.lines.order_by("id"):
        qc(ns, line, accepted=line.qty_received)
    bill = bills.post_bill(bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner,
                                             tds_template=TaxTemplate.objects.get(name=TDS2)), user=ns.owner)
    assert bill.gross == D("2500.00") and costing.lot_cost(ns.lot, factory) == D("9030.00") + D("100.00") * 2 + D("2500.00")
    live = [Bundle.objects.get(pk=b.pk) for b in ns.bundles]
    bundle_service.move_bundles(bundles=live, to_step=step(ns, "IRON"), user=ns.owner, date=DAY)  # crosses to factory 2
    assert costing.live_pieces(ns.lot, factory2) == 100 and costing.lot_cost(ns.lot, factory) == D("0.00")
    assert costing.lot_cost(ns.lot, factory2) == D("9030.00") + D("200.00") + D("2500.00")
    again = [Bundle.objects.get(pk=b.pk) for b in ns.bundles]
    bundle_service.move_bundles(bundles=again[:2], to_step=step(ns, "FINISH"), user=ns.owner, date=DAY)
    bundle_service.move_bundles(bundles=again[:2], to_step=step(ns, "IRON"), user=ns.owner, date=DAY, reason="Re-press")  # sent back
    moved_back = Bundle.objects.get(pk=ns.bundles[0].pk)
    assert moved_back.is_rework and moved_back.current_step == step(ns, "IRON")
    for f in (factory, factory2):
        assert trial_balance(company, factory=f)["tallies"]
    assert not costing.check_wip_reconciles(company)
    assert "Iron" in step(ns, "IRON").process.name and step(ns, "STITCH").status == "done"


# ---------------- reports ----------------

def test_fabricator_ledger_shortage_report_and_ageing(ns, company, factory, owner):
    from jobwork import selectors

    ch = issue(ns, ns.fab, ns.bundles[:2])
    other = issue(ns, ns.fab2, ns.bundles[3:5], confirm_second_fabricator=True)
    receive(ns, ch, {list(ch.bundles.all())[0]: 17, list(ch.bundles.all())[1]: 23}, trims={ch.trims.get(): (D("0"), D("2"))})
    rows = selectors.fabricator_ledger(owner, ns.fab)
    assert rows[0]["issued"] == 42 and rows[0]["received"] == 40 and rows[0]["shortage"] == 2 and rows[0]["in_process"] == 0
    assert rows[0]["trims"][0][0] == "Zipper" and rows[0]["trims"][0][3] == D("2.000")
    short = selectors.shortage_report(owner)
    assert short[0]["party"] == ns.fab and short[0]["pieces"] == 2 and short[0]["trims"] == [("Zipper", D("2.000"))]
    ageing = selectors.ageing(owner, today=date(2026, 7, 20))  # the other challan has been out for 35 days
    assert ageing["buckets"]["31+"] == 33 and ageing["parties"][0]["party"] == ns.fab2
