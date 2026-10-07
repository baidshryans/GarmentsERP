"""Edit and undo of recorded steps. The test for every step is the same: note everything, do the step, undo it,
and stock, books, lot cost, bundles and documents must be exactly as they were. The books and stock fixtures
check the trial balance, the WIP ledger and the stock ledger after every test as well."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError
from core.models import Role
from core.services import periods
from inventory.models import RollBalance, StockBalance, StockMovement
from jobwork.models import ChallanBundle, JobWorkChallan, QcResult, Receipt, ReceiptLine
from jobwork.services import bills, challans, rates, receipts
from jobwork.services.receipts import Counted
from ledger.models import Voucher, VoucherLine
from production.models import Bundle, CuttingEntry, FabricIssue, PackEntry, ProductionAction, StageMovement, StepMaterialIssue
from production.services import actions
from production.services import bundles as bundle_service
from production.services import costing, cutting, routes
from tests.conftest import make_user
from tests.prod_helpers import D, DAY, build, cut, fabricator, go, step

K = ProductionAction.Kind


def state(ns):
    """Everything a step may touch, in a form that can be compared."""
    books = {}
    for row in VoucherLine.objects.filter(voucher__status="posted").values("ledger_id", "factory_id").annotate(d=Sum("debit"), c=Sum("credit")):
        net = Decimal(str(row["d"] or 0)).quantize(D("0.01")) - Decimal(str(row["c"] or 0)).quantize(D("0.01"))
        if net:
            books[(row["ledger_id"], row["factory_id"])] = net
    return {
        "stock": {(b.location_id, b.material_id, b.sku_id): (b.qty, b.value) for b in StockBalance.objects.all() if b.qty or b.value},
        "rolls": {(b.location_id, b.roll_id): (b.qty, b.value) for b in RollBalance.objects.all() if b.qty or b.value},
        "books": books,
        "cost": costing.lot_cost(ns.lot),
        "bundles": sorted(Bundle.objects.filter(lot=ns.lot).values_list(
            "bundle_no", "qty", "status", "location_id", "current_step_id", "completed_seq", "rework_qty", "is_rework")),
        "lot": ProductionAction._meta.get_field("lot").related_model.objects.get(pk=ns.lot.pk).status,
        "steps": list(ns.lot.steps.order_by("sequence").values_list("status", flat=True)),
        "docs": (FabricIssue.objects.count(), CuttingEntry.objects.count(), StageMovement.objects.count(), PackEntry.objects.count(),
                 StepMaterialIssue.objects.count(), Receipt.objects.count(), ReceiptLine.objects.count(), QcResult.objects.count()),
        "challans": sorted(JobWorkChallan.objects.exclude(status="cancelled").values_list("pk", "status", "number")),
        "challan_lines": sorted(ChallanBundle.objects.exclude(challan__status="cancelled").values_list(
            "pk", "qty_received", "qty_shortage", "qty_accepted", "qty_rejected")),
    }


def last(kind):
    return ProductionAction.objects.filter(kind=kind, undone=False).order_by("-pk").first()


def undo(ns, kind, reason="Entered wrongly", **kw):
    return actions.undo(last(kind), user=ns.owner, reason=reason, **kw)


def all_in_house(ns):
    routes.reassign_step(step(ns, "STITCH"), user=ns.owner, reason="Stitch in-house", assignment="in_house", rate=D("10"), rework_rate=D("4"))
    for code in ("EMB", "PRINT", "WASH"):
        routes.skip_step(step(ns, code), user=ns.owner, reason="Not needed")


@pytest.fixture
def ns(company, factory, owner):
    return build(company, factory, owner)


@pytest.fixture
def jw(ns, company):
    ns.bundles = cut(ns)  # B001 S17, B002 M25, B003 M8, B004 L25, B005 L8, B006 XL17
    ns.fab = fabricator(company)
    rates.save_rate(party=ns.fab, process=step(ns, "STITCH").process, rate_type="A", base_rate=D("25"), rework_rate=D("5"),
                    effective_from=date(2026, 4, 1))
    return ns


def send(ns, bundles):
    return challans.create_and_issue(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                     bundles=bundles, date=DAY, user=ns.owner)


def receive(ns, challan, counts=None, trims=None):
    counts = counts if counts is not None else {cb: cb.qty_issued for cb in challan.bundles.all()}
    return receipts.create_receipt(challan=challan, user=ns.owner, date=DAY, trims=trims,
                                   counts=[Counted(cb, n) for cb, n in counts.items()])


# ---------------- fabric, cutting, bundles ----------------

def test_a_fabric_issue_can_be_undone_and_stays_on_record(ns):
    before = state(ns)
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60")), (ns.roll_b, D("10"))], user=ns.owner, date=DAY, estimated_pieces=150)
    action = last(K.FABRIC)
    assert action.summary == "2 roll(s), 70 to the cutting floor" and action.lot == ns.lot and not actions.blockers(action)
    assert state(ns) != before
    with pytest.raises(BusinessRuleError, match="Give the reason"):
        actions.undo(action, user=ns.owner, reason="  ")
    done = actions.undo(action, user=ns.owner, reason="Wrong roll")
    assert state(ns) == before and done.undone and done.undo_reason == "Wrong roll" and done.undone_by == ns.owner
    assert cutting.fabric_with_lot(ns.lot) == 0 and cutting.estimated_pieces(ns.lot) is None
    assert StockMovement.objects.filter(movement_type="reversal", lot=ns.lot).count() == 4      # posted, never edited
    with pytest.raises(BusinessRuleError, match="already been undone"):
        actions.undo(action, user=ns.owner, reason="Again")


def test_fabric_that_has_been_cut_cannot_be_taken_back(ns):
    cut(ns)
    with pytest.raises(BusinessRuleError, match="has been used since"):
        undo(ns, K.FABRIC)
    assert not last(K.FABRIC).undone and FabricIssue.objects.count() == 1


def test_cutting_is_corrected_by_undoing_the_bundles_then_the_lay(ns):
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY, estimated_pieces=100)
    issued = state(ns)
    S, M = ns.sizes["S"], ns.sizes["M"]
    entry = cutting.record_cutting(lot=ns.lot, user=ns.owner, date=DAY, pieces={S: 17, M: 33}, notes="First lay",
                                   rolls=[cutting.RollUseSpec(ns.roll_a, used=D("41"), waste=D("2"), remnant=D("17"))])
    cut_state = state(ns)
    cutting.create_bundles(entry, bundles={S: [9, 8], M: [12, 10, 9]}, user=ns.owner, loss={M: 2})
    # the lay cannot go while its bundles stand: the later step is named
    with pytest.raises(BusinessRuleError, match=r"Bundles made \(Lay 1: 5 bundle\(s\), 48 pieces\) came after this step. Undo that first."):
        undo(ns, K.CUTTING)
    assert actions.form_values(last(K.BUNDLES)) == {
        f"bundles_{S.pk}": "9 8", f"bundles_{M.pk}": "12 10 9", f"loss_{S.pk}": "", f"loss_{M.pk}": "2", "entry": str(entry.pk)}
    undo(ns, K.BUNDLES)
    assert state(ns) == cut_state and not ns.lot.bundles.exists()
    entry.refresh_from_db()
    assert not entry.bundled and not entry.sizes.filter(loss__gt=0).exists()
    assert Bundle.all_objects.filter(lot=ns.lot, voided=True).count() == 5          # kept for the record, never shown
    assert actions.form_values(last(K.CUTTING)) == {
        "date": "2026-06-15", "notes": "First lay", f"pieces_{S.pk}": "17", f"pieces_{M.pk}": "33",
        f"used_{ns.roll_a.pk}": "41.000", f"waste_{ns.roll_a.pk}": "2.000", f"remnant_{ns.roll_a.pk}": "17.000"}
    undo(ns, K.CUTTING)
    assert state(ns) == issued and not ns.lot.cuttings.exists()
    # entered again with the right figure: bundles start from B001 once more
    entry = cutting.record_cutting(lot=ns.lot, user=ns.owner, date=DAY, pieces={S: 17, M: 30},
                                   rolls=[cutting.RollUseSpec(ns.roll_a, used=D("41"), waste=D("2"), remnant=D("17"))])
    made = cutting.create_bundles(entry, bundles={S: [17], M: [30]}, user=ns.owner)
    assert [b.bundle_no for b in made] == ["B001", "B002"] and entry.lay_no == 1


def test_bundles_made_again_never_take_a_number_another_lay_holds(ns):
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    S = ns.sizes["S"]
    lays = [cutting.record_cutting(lot=ns.lot, user=ns.owner, date=DAY, pieces={S: 10},
                                   rolls=[cutting.RollUseSpec(ns.roll_a, used=D("10"))]) for _ in range(2)]
    cutting.create_bundles(lays[0], bundles={S: [6, 4]}, user=ns.owner)
    cutting.create_bundles(lays[1], bundles={S: [10]}, user=ns.owner)           # B003
    actions.undo(ProductionAction.objects.get(kind=K.BUNDLES, summary__startswith="Lay 1"), user=ns.owner, reason="Recount")
    again = cutting.create_bundles(lays[0], bundles={S: [5, 5]}, user=ns.owner)
    assert [b.bundle_no for b in again] == ["B004", "B005"]
    assert sorted(ns.lot.bundles.values_list("bundle_no", flat=True)) == ["B003", "B004", "B005"]


# ---------------- moves, counts, splits, packing ----------------

def test_a_move_is_undone_with_its_labour_and_materials(ns):
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH", materials=[(ns.zipper, D("100"))])
    stitched = state(ns)
    go(ns, bundles[:2], "IRON")                                   # 42 pieces leave stitching: labour accrues
    with pytest.raises(BusinessRuleError, match=r"Bundles moved \(2 bundle\(s\), 42 pieces to Ironing and pressing\) came after"):
        actions.undo(ProductionAction.objects.filter(kind=K.MOVE).order_by("pk").first(), user=ns.owner, reason="Wrong")
    undo(ns, K.MOVE)
    assert state(ns) == stitched
    cut_only = undo(ns, K.MOVE)                                   # the move into stitching, zippers back in the store
    assert cut_only.summary == "6 bundle(s), 100 pieces to Stitching"
    assert {b.status for b in ns.lot.bundles.all()} == {"cut"} and not StepMaterialIssue.objects.exists()
    assert StockBalance.objects.get(material=ns.zipper).qty == D("1000")
    assert step(ns, "STITCH").status == "pending" and state(ns)["lot"] == "in_production"


def test_bundles_that_went_different_ways_are_undone_on_their_own(ns):
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles[:3], "STITCH")
    first = last(K.MOVE)
    go(ns, bundles[3:], "STITCH")
    actions.undo(first, user=ns.owner, reason="Not these")        # the later move touched other bundles
    assert [b.status for b in ns.lot.bundles.order_by("bundle_no")] == ["cut"] * 3 + ["at_stage"] * 3


def test_counts_and_splits_are_undone(ns):
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    before = state(ns)
    bundle_service.count_bundles(bundles=bundles[:1], counts={bundles[0].pk: bundle_service.Count(loss=1, rejection=2)},
                                 user=ns.owner, reason="Torn", date=DAY)
    child = bundle_service.split_bundle(bundles[1], 5, user=ns.owner, date=DAY)
    assert last(K.COUNT).summary == "3 piece(s) taken out of 1 bundle(s): Torn" and last(K.SPLIT).summary == f"{child.bundle_no} (5 pieces) out of B002"
    undo(ns, K.COUNT)
    undo(ns, K.SPLIT)
    assert state(ns) == before and not Bundle.objects.filter(pk=child.pk).exists()


def test_packing_is_undone_and_the_pieces_are_work_in_progress_again(ns):
    all_in_house(ns)
    bundles = cut(ns)
    for code in ("STITCH", "IRON", "FINISH", "QC", "PACK"):
        go(ns, bundles, code)
    before = state(ns)
    bundle_service.pack_bundles(bundles=bundles[:2], user=ns.owner, date=DAY)
    bundle_service.pack_bundles(bundles=bundles[2:], user=ns.owner, date=DAY)
    assert state(ns)["lot"] == "completed" and costing.lot_cost(ns.lot) == 0
    undo(ns, K.PACK)
    undo(ns, K.PACK)
    assert state(ns) == before and before["lot"] == "in_production"


# ---------------- job work ----------------

def test_a_challan_issued_from_a_draft_goes_back_to_a_draft(jw):
    ns = jw
    draft = challans.create_challan(company=ns.company, factory=ns.factory, party=ns.fab, lot=ns.lot, step=step(ns, "STITCH"),
                                    bundles=ns.bundles[:2], date=DAY, user=ns.owner)
    with pytest.raises(BusinessRuleError, match="is on draft challan"):      # the bundles are promised to the draft
        undo(ns, K.BUNDLES)
    before = state(ns)
    challans.issue_challan(draft, user=ns.owner)
    assert last(K.CHALLAN).doc_id == draft.pk and state(ns) != before
    undo(ns, K.CHALLAN)
    after = state(ns)
    draft.refresh_from_db()
    assert draft.status == "draft" and draft.number is None and draft.voucher is None
    assert after == before


def test_a_challan_made_and_issued_in_one_go_is_cancelled(jw):
    ns = jw
    before = state(ns)
    ch = send(ns, ns.bundles[:2])
    undo(ns, K.CHALLAN)
    ch.refresh_from_db()
    assert ch.status == "cancelled" and state(ns) == before
    again = send(ns, ns.bundles[:2])                              # the bundles are free to go out again
    assert again.status == "issued" and again.bundles.count() == 2


def test_receipts_and_qc_are_undone_last_first(jw):
    ns = jw
    ch = send(ns, ns.bundles[:2])                                 # 17 + 25 with 42 zippers
    trim = ch.trims.get()
    sent = state(ns)
    r = receive(ns, ch, counts={ch.bundles.order_by("id")[0]: 15}, trims={trim: (D("2"), D("1"))})   # 2 short
    with pytest.raises(BusinessRuleError, match="Received from fabricator .* came after this step"):
        undo(ns, K.CHALLAN)
    received = state(ns)
    line = r.lines.get()
    receipts.record_qc(receipt_line=line, accepted=10, rejected=2, rework=3, user=ns.owner, reject_reason="Open seam")
    assert Bundle.objects.filter(lot=ns.lot, split_from__isnull=False).count() == 1
    with pytest.raises(BusinessRuleError, match="QC recorded .* came after this step"):
        undo(ns, K.RECEIPT)
    undo(ns, K.QC)
    assert state(ns) == received and Receipt.objects.get().status == "received"
    undo(ns, K.RECEIPT)
    assert state(ns) == sent and JobWorkChallan.objects.get().status == "issued"
    r2 = receive(ns, ch)                                          # counted again, correctly this time
    assert r2.status == "received" and JobWorkChallan.objects.get().status == "fully_received"


def test_qc_of_one_bundle_is_undone_without_the_others(jw):
    ns = jw
    ch = send(ns, ns.bundles[:2])
    r = receive(ns, ch)
    first, second = r.lines.order_by("id")
    receipts.record_qc(receipt_line=first, accepted=17, user=ns.owner)
    one_checked = last(K.QC)
    receipts.record_qc(receipt_line=second, accepted=25, user=ns.owner)
    assert Receipt.objects.get().status == "qc_done"
    actions.undo(one_checked, user=ns.owner, reason="Counted the wrong bundle")
    assert Receipt.objects.get().status == "received" and QcResult.objects.count() == 1
    assert ChallanBundle.objects.get(bundle=ns.bundles[0]).qty_accepted == 0


def test_pieces_on_a_labour_bill_cannot_be_unchecked_until_the_bill_is_cancelled(jw, company, factory):
    ns = jw
    ch = send(ns, ns.bundles[:1])
    line = receive(ns, ch).lines.get()
    receipts.record_qc(receipt_line=line, accepted=17, user=ns.owner)
    checked = state(ns)
    bill = bills.post_bill(bills.create_bill(company=company, factory=factory, party=ns.fab, date=DAY, user=ns.owner), user=ns.owner)
    with pytest.raises(BusinessRuleError, match="is on a labour bill. Cancel the bill first"):
        undo(ns, K.QC)
    bills.cancel_bill(bill, user=ns.owner, reason="Wrong pieces")
    assert state(ns) == checked
    undo(ns, K.QC)
    assert not QcResult.objects.exists() and Bundle.objects.get(pk=ns.bundles[0].pk).status == "received"


def test_an_over_receipt_and_its_approval_are_undone(jw):
    ns = jw
    ch = send(ns, ns.bundles[:1])
    sent = state(ns)
    r = receive(ns, ch, counts={ch.bundles.get(): 19})
    assert r.status == "pending_approval" and last(K.RECEIPT).summary.startswith("Waiting for approval: 19 pieces")
    waiting = state(ns)
    receipts.approve_receipt(r, user=ns.owner)
    with pytest.raises(BusinessRuleError, match="Over-receipt approved .* came after"):
        undo(ns, K.RECEIPT)
    undo(ns, K.APPROVAL)
    assert state(ns) == waiting and Receipt.objects.get().status == "pending_approval"
    undo(ns, K.RECEIPT)
    assert state(ns) == sent


# ---------------- who, when, and the books ----------------

def test_whoever_records_a_step_may_undo_it_in_their_own_factory(ns, factory, factory2):
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    action = last(K.FABRIC)
    cutter, accounts, elsewhere = make_user("cutter"), make_user("accounts"), make_user("elsewhere")
    cutter.roles.add(Role.objects.get(name="Cutting Master"))
    cutter.allowed_factories.add(factory)
    accounts.roles.add(Role.objects.get(name="Accountant"))
    accounts.allowed_factories.add(factory)
    elsewhere.roles.add(Role.objects.get(name="Cutting Master"))
    elsewhere.allowed_factories.add(factory2)
    assert actions.may_undo(action, cutter) and not actions.may_undo(action, accounts) and not actions.may_undo(action, elsewhere)
    with pytest.raises(BusinessRuleError, match="not allowed to undo"):
        actions.undo(action, user=accounts, reason="No")
    with pytest.raises(BusinessRuleError):
        actions.undo(action, user=elsewhere, reason="No")
    assert actions.undo(action, user=cutter, reason="Wrong roll").undone


def test_the_reversal_carries_the_date_chosen_and_respects_a_locked_period(ns, company):
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    cutting.record_cutting(lot=ns.lot, user=ns.owner, date=DAY, pieces={ns.sizes["S"]: 17},
                           rolls=[cutting.RollUseSpec(ns.roll_a, used=D("41"), waste=D("2"), remnant=D("17"))])
    action = last(K.CUTTING)
    posted = Voucher.objects.filter(source_type="production.cuttingentry").get()
    with pytest.raises(BusinessRuleError, match="cannot be dated before the step"):
        actions.undo(action, user=ns.owner, reason="Wrong", date=DAY - timedelta(days=1))
    periods.lock_period(user=ns.owner, company=company, upto=DAY + timedelta(days=5))
    with pytest.raises(BusinessRuleError):
        actions.undo(action, user=ns.owner, reason="Wrong", date=DAY)
    assert not ProductionAction.objects.get(pk=action.pk).undone and CuttingEntry.objects.exists()
    on = DAY + timedelta(days=10)
    done = actions.undo(action, user=ns.owner, reason="Wrong", date=on)
    reversal = Voucher.objects.get(reverses=posted)
    assert done.undo_date == on and reversal.date == on and posted.status == "posted"      # the original is untouched
    assert set(StockMovement.objects.filter(movement_type="reversal").values_list("date", flat=True)) == {on}
    assert costing.lot_cost(ns.lot) == 0 and ns.lot.cost_entries.count() == 2               # cost and its opposite


def test_a_closed_lot_is_left_alone(ns):
    from production.models import Lot

    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    Lot.objects.filter(pk=ns.lot.pk).update(status="closed")
    with pytest.raises(BusinessRuleError, match="is closed"):
        undo(ns, K.FABRIC)


# ---------------- the screens ----------------

def login(user):
    c = Client()
    c.force_login(user)
    return c


def test_a_wrong_cutting_is_edited_from_the_screens(ns, factory):
    cutter = make_user("cutter")
    cutter.roles.add(Role.objects.get(name="Cutting Master"))
    cutter.allowed_factories.add(factory)
    c, lot, S, M = login(cutter), ns.lot, ns.sizes["S"], ns.sizes["M"]
    c.post(reverse("lot_fabric", args=[lot.pk]), {"date": "2026-06-15", f"qty_{ns.roll_a.pk}": "60", "estimated_pieces": "50"})
    c.post(reverse("lot_cutting", args=[lot.pk]), {
        "date": "2026-06-15", "notes": "Morning lay", f"pieces_{S.pk}": "17", f"pieces_{M.pk}": "33",
        f"used_{ns.roll_a.pk}": "41", f"waste_{ns.roll_a.pk}": "2", f"remnant_{ns.roll_a.pk}": "17"})
    entry = lot.cuttings.get()
    c.post(reverse("lot_cutting", args=[lot.pk]), {"action": "bundles", "entry": entry.pk, f"bundles_{S.pk}": "9 8", f"bundles_{M.pk}": "20 13"})
    lay, made = last(K.CUTTING), last(K.BUNDLES)
    page = c.get(reverse("lot_cutting", args=[lot.pk])).content.decode()
    assert f'{reverse("step_undo", args=[made.pk])}?edit=1' in page and "Edit this lay" not in page     # bundles first

    # the lay cannot be edited while its bundles stand: the page says what to undo, and offers no form
    blocked = c.get(reverse("step_undo", args=[lay.pk]) + "?edit=1").content.decode()
    assert "cannot be taken back yet" in blocked and "Bundles made (Lay 1: 4 bundle(s), 50 pieces) came after this step" in blocked
    assert 'name="reason"' not in blocked

    confirm = c.get(reverse("step_undo", args=[made.pk]) + "?edit=1").content.decode()
    assert "Undo and enter again" in confirm and "stock movements reversed" in confirm and 'name="reason"' in confirm
    r = c.post(reverse("step_undo", args=[made.pk]), {"edit": "1", "reason": "", "date": "2026-06-15"})
    assert r.status_code == 200 and "Give the reason" in r.content.decode() and lot.bundles.count() == 4
    r = c.post(reverse("step_undo", args=[made.pk]), {"edit": "1", "reason": "Pieces cut were wrong", "date": "2026-06-15"})
    assert r.status_code == 302 and r.url == reverse("lot_cutting", args=[lot.pk]) and not lot.bundles.exists()
    page = c.get(r.url).content.decode()
    assert 'value="9 8"' in page and 'value="20 13"' in page and "Edit this lay" in page       # the bundles as they were typed
    assert 'value="9 8"' not in c.get(r.url).content.decode()                                   # shown once only

    r = c.post(reverse("step_undo", args=[lay.pk]), {"edit": "1", "reason": "Pieces cut were wrong", "date": "2026-06-15"})
    assert r.status_code == 302 and not lot.cuttings.exists()
    page = c.get(r.url).content.decode()
    for shown in (f'name="pieces_{S.pk}" value="17"', f'name="pieces_{M.pk}" value="33"', f'name="used_{ns.roll_a.pk}" value="41.000"',
                  f'name="remnant_{ns.roll_a.pk}" value="17.000"', 'value="Morning lay"'):
        assert shown in page, shown
    c.post(reverse("lot_cutting", args=[lot.pk]), {
        "date": "2026-06-15", f"pieces_{S.pk}": "17", f"pieces_{M.pk}": "31",
        f"used_{ns.roll_a.pk}": "41", f"waste_{ns.roll_a.pk}": "2", f"remnant_{ns.roll_a.pk}": "17"})
    assert sum(cs.pieces for cs in lot.cuttings.get().sizes.all()) == 48

    # the lot page lists every step, the undone ones with the reason
    owner_page = login(ns.owner).get(reverse("lot_detail", args=[lot.pk])).content.decode()
    assert "Steps recorded" in owner_page and owner_page.count("Pieces cut were wrong") == 2 and "Undone" in owner_page
    assert f'{reverse("step_undo", args=[last(K.FABRIC).pk])}?edit=1' in owner_page


def test_fabric_issue_is_refilled_for_editing(ns):
    c = login(ns.owner)
    c.post(reverse("lot_fabric", args=[ns.lot.pk]), {"date": "2026-06-15", f"qty_{ns.roll_a.pk}": "60", "estimated_pieces": "50"})
    page = c.get(reverse("lot_fabric", args=[ns.lot.pk])).content.decode()
    issued = last(K.FABRIC)
    assert f'{reverse("step_undo", args=[issued.pk])}?edit=1' in page
    r = c.post(reverse("step_undo", args=[issued.pk]), {"edit": "1", "reason": "Wrong quantity"})
    page = c.get(r.url).content.decode()
    assert f'name="qty_{ns.roll_a.pk}" value="60.000"' in page and 'name="estimated_pieces" type="text" inputmode="numeric" value="50"' in page


def test_only_those_who_may_record_a_step_see_and_reach_its_undo(ns, factory, factory2):
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    action = last(K.FABRIC)
    accounts, elsewhere = make_user("accounts"), make_user("elsewhere")
    accounts.roles.add(Role.objects.get(name="Accountant"))
    accounts.allowed_factories.add(factory)
    elsewhere.roles.add(Role.objects.get(name="Owner"))
    elsewhere.allowed_factories.add(factory2)
    assert login(accounts).get(reverse("step_undo", args=[action.pk])).status_code == 403
    assert login(accounts).post(reverse("step_undo", args=[action.pk]), {"reason": "x"}).status_code == 403
    assert login(elsewhere).get(reverse("step_undo", args=[action.pk])).status_code == 404        # another factory's lot
    assert not ProductionAction.objects.get(pk=action.pk).undone


def test_job_work_steps_are_listed_on_the_challan_and_the_receipt(jw):
    ns = jw
    c = login(ns.owner)
    ch = send(ns, ns.bundles[:1])
    r = receive(ns, ch)
    receipts.record_qc(receipt_line=r.lines.get(), accepted=17, user=ns.owner)
    page = c.get(reverse("challan_detail", args=[ch.pk])).content.decode()
    assert "Steps recorded" in page and reverse("step_undo", args=[last(K.CHALLAN).pk]) in page and reverse("step_undo", args=[last(K.RECEIPT).pk]) in page
    page = c.get(reverse("receipt_detail", args=[r.pk])).content.decode()
    assert reverse("step_undo", args=[last(K.QC).pk]) in page
    done = c.post(reverse("step_undo", args=[last(K.QC).pk]), {"edit": "1", "reason": "Wrong count"})
    assert done.status_code == 302 and done.url == reverse("receipt_detail", args=[r.pk]) and not QcResult.objects.exists()
    done = c.post(reverse("step_undo", args=[last(K.RECEIPT).pk]), {"edit": "1", "reason": "Wrong count"})
    assert done.url == reverse("receipt_new", args=[ch.pk]) and not Receipt.objects.exists()


# ---------------- steps recorded before the action log existed ----------------

def test_steps_recorded_earlier_get_their_action_and_can_be_undone(ns):
    import importlib

    from django.apps import apps

    backfill = importlib.import_module("production.migrations.0007_backfill_step_actions").backfill
    all_in_house(ns)
    start = state(ns)
    S = ns.sizes["S"]
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY, estimated_pieces=40)
    lays = [cutting.record_cutting(lot=ns.lot, user=ns.owner, date=DAY, pieces={S: 20},
                                   rolls=[cutting.RollUseSpec(ns.roll_a, used=D("20"), waste=D("1"), remnant=D("9"))]) for _ in range(2)]
    cutting.create_bundles(lays[0], bundles={S: [12, 8]}, user=ns.owner)
    moved = cutting.create_bundles(lays[1], bundles={S: [20]}, user=ns.owner)
    go(ns, moved, "STITCH")
    ProductionAction.objects.all().delete()                       # as if all of it had been entered before this feature

    backfill(apps)
    backfill(apps)                                                # running it again adds nothing
    found = sorted(ProductionAction.objects.values_list("kind", "summary"))
    assert found == [("bundles", "Lay 1: 2 bundle(s), 20 pieces"), ("cutting", "Lay 1: 20 pieces cut"),
                     ("cutting", "Lay 2: 20 pieces cut"), ("fabric", "1 roll(s), 60 to the cutting floor")]
    # lay 2's bundles have moved on, and that move was recorded before: the lay says so and stays
    lay2 = ProductionAction.objects.get(kind=K.CUTTING, summary__startswith="Lay 2")
    with pytest.raises(BusinessRuleError, match="Bundles have been made from Lay 2 and have moved on"):
        actions.undo(lay2, user=ns.owner, reason="Wrong")
    with pytest.raises(BusinessRuleError, match=r"Bundles made \(Lay 1: 2 bundle\(s\), 20 pieces\) came after this step"):
        actions.undo(ProductionAction.objects.get(kind=K.CUTTING, summary__startswith="Lay 1"), user=ns.owner, reason="Wrong")
    undo(ns, K.BUNDLES)
    actions.undo(ProductionAction.objects.get(kind=K.CUTTING, summary__startswith="Lay 1"), user=ns.owner, reason="Wrong")
    assert list(ns.lot.cuttings.values_list("lay_no", flat=True)) == [2] and ns.lot.bundles.count() == 1
    assert costing.lot_cost(ns.lot) == D("4410.00")             # lay 2 alone: 21 kg at the average 210
    assert start["lot"] == "planned" and state(ns)["lot"] == "in_production"
