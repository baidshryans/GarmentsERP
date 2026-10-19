"""Delete a recorded step (owner, 19 Oct 2026): newest first, and it is gone entirely: its stock movements, its
journal entries, its lot cost and their history. The books and stock are exactly as before it was recorded."""
import pytest
from django.test import Client
from django.urls import reverse

from core.exceptions import BusinessRuleError
from core.models import Role
from core.services import periods
from inventory.models import StockMovement
from jobwork.models import JobWorkChallan
from jobwork.services import bills
from ledger.models import Voucher
from production.models import Bundle, CuttingEntry, FabricIssue, LotCostEntry, ProductionAction
from production.services import actions, cutting
from tests.conftest import make_user
from tests.deletion_helpers import books
from tests.prod_helpers import D, DAY, build, cut, set_inhouse_rate
from tests.test_step_undo import K, all_in_house, go, jw, last, ns, receive, send, state  # noqa: F401  (fixtures)


def _no_trace(action_pk, movement_pks, voucher_pks):
    assert not ProductionAction.objects.filter(pk=action_pk).exists()
    assert not StockMovement.objects.filter(pk__in=movement_pks).exists()
    assert not StockMovement.objects.filter(source_type="production.productionaction", source_id=action_pk).exists()
    assert not Voucher.objects.filter(pk__in=voucher_pks).exists()
    assert not Voucher.objects.filter(reverses_id__in=voucher_pks).exists()
    assert not Voucher.history.filter(id__in=voucher_pks).exists()


def _posted(action):
    items = list(action.items.all())
    return ([i.object_id for i in items if i.role == "movement"], [i.object_id for i in items if i.role == "voucher"])


def test_delete_cutting_leaves_no_trace_and_books_as_before(ns, company):
    set_inhouse_rate("CUT", "2")
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    before, before_books = state(ns), books(company)
    entry = cutting.receive_cutting(lot=ns.lot, user=ns.owner, date=DAY,
                                    bundles={ns.sizes["S"]: [17], ns.sizes["M"]: [25, 8], ns.sizes["L"]: [25, 8], ns.sizes["XL"]: [17]},
                                    rolls=[cutting.RollUseSpec(ns.roll_a, used=D("41"), waste=D("2"), remnant=D("17"))])
    action = last(K.CUTTING)
    moves, vouchers = _posted(action)
    assert len(vouchers) == 2                                   # the fabric cut and the cutting labour
    actions.delete_step(action, user=ns.owner)
    _no_trace(action.pk, moves, vouchers)
    assert state(ns) == before and books(company) == before_books
    assert not CuttingEntry.objects.filter(pk=entry.pk).exists() and not Bundle.objects.filter(lot=ns.lot).exists()
    assert not LotCostEntry.objects.filter(lot=ns.lot, kind="labour").exists()
    assert not Bundle.history.filter(lot_id=ns.lot.pk).exists() and not CuttingEntry.history.filter(id=entry.pk).exists()


def test_only_the_newest_step_can_be_deleted_and_the_message_names_the_later_steps(ns):
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    go(ns, bundles[:1], "IRON")
    with pytest.raises(BusinessRuleError) as exc:
        actions.delete_step(last(K.BUNDLES), user=ns.owner)
    text = str(exc.value)
    assert text.startswith("To delete this ") and ", then " in text and text.endswith(".")
    assert text.index("Bundles moved") < text.rindex("Bundles moved")      # newest first, both moves named


def test_delete_newest_then_the_one_before_then_enter_again(jw):
    challan = send(jw, jw.bundles[:2])
    receive(jw, challan)
    actions.delete_step(last(K.RECEIPT), user=jw.owner)
    actions.delete_step(last(K.CHALLAN), user=jw.owner)
    assert not JobWorkChallan.objects.filter(pk=challan.pk).exists()
    again = send(jw, jw.bundles[:2])
    assert again.status == "issued"


def test_delete_refused_in_a_locked_period(ns, company):
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    periods.lock_period(company=company, upto=DAY, user=ns.owner)
    with pytest.raises(BusinessRuleError, match="locked"):
        actions.delete_step(last(K.FABRIC), user=ns.owner)
    assert FabricIssue.objects.filter(lot=ns.lot).exists()


def test_delete_qc_on_a_billed_line_names_the_bill(jw, company, factory):
    challan = send(jw, jw.bundles[:1])
    r = receive(jw, challan)
    from jobwork.services import receipts

    receipts.record_qc(receipt_line=r.lines.get(), accepted=r.lines.get().qty_received, user=jw.owner)
    bills.post_bill(bills.create_bill(company=company, factory=factory, party=jw.fab, date=DAY, user=jw.owner), user=jw.owner)
    with pytest.raises(BusinessRuleError, match="labour bill"):
        actions.delete_step(last(K.QC), user=jw.owner)


def test_delete_the_newest_step_on_lot_a_after_lot_b_used_the_same_trim(company, factory, owner):
    from types import SimpleNamespace

    from production.services import orders

    a = build(company, factory, owner)
    all_in_house(a)
    a_bundles = cut(a)
    order = orders.create_order(company=company, factory=factory, date=DAY, user=owner,
                                lines=[orders.OrderLineSpec(a.style, a.black, 20, {a.sizes["M"]: 1})])
    b = SimpleNamespace(**{**vars(a), "order": orders.release_order(order, user=owner)})
    b.lot = b.order.lines.get().lot
    cutting.issue_fabric(lot=b.lot, lines=[(a.roll_b, D("20"))], user=owner, date=DAY)
    cutting.receive_cutting(lot=b.lot, user=owner, date=DAY, bundles={b.sizes["M"]: [20]},
                            rolls=[cutting.RollUseSpec(a.roll_b, used=D("8"), waste=D("0"), remnant=D("12"))])
    go(a, a_bundles, "STITCH")                                  # the newest step on lot A, after lot B's cutting
    b_moves = set(StockMovement.objects.filter(lot=b.lot).values_list("pk", "qty", "value"))
    b_vouchers = set(Voucher.objects.filter(source_type="production.cuttingentry").values_list("pk", "total"))
    actions.delete_step(last(K.MOVE), user=owner)
    assert set(StockMovement.objects.filter(lot=b.lot).values_list("pk", "qty", "value")) == b_moves
    assert set(Voucher.objects.filter(source_type="production.cuttingentry").values_list("pk", "total")) == b_vouchers
    assert Bundle.objects.filter(lot=b.lot).count() == 1


def test_the_confirmation_lists_what_goes_and_hides_money_from_production(ns, factory):
    set_inhouse_rate("CUT", "2")
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    cutting.receive_cutting(lot=ns.lot, user=ns.owner, date=DAY, bundles={ns.sizes["M"]: [25]},
                            rolls=[cutting.RollUseSpec(ns.roll_a, used=D("10"), waste=D("0"), remnant=D("50"))])
    action = last(K.CUTTING)
    owner_lines = actions.consequences(action, ns.owner)
    assert any("journal entry" in s for s in owner_lines) and any("₹" in s for s in owner_lines)
    sup = make_user("sup")
    sup.roles.add(Role.objects.get(name="Production Supervisor"))
    sup.allowed_factories.add(factory)
    sup_lines = actions.consequences(action, sup)
    assert sup_lines and not any("₹" in s for s in sup_lines)
    c = Client()
    c.force_login(ns.owner)
    page = c.get(reverse("step_delete", args=[action.pk])).content.decode()
    assert "Keep it" in page and ">Delete<" in page and "Undo" not in page
    r = c.post(reverse("step_delete", args=[action.pk]))
    assert r.status_code == 302 and not ProductionAction.objects.filter(pk=action.pk).exists()


def test_a_step_recorded_with_millisecond_times_can_still_be_deleted(ns):
    """Steps logged before 7 Oct 2026 kept their times to the millisecond ("…080Z"); the row in the database holds
    microseconds. That is not a change made since, so it must not block the delete."""
    cutting.issue_fabric(lot=ns.lot, lines=[(ns.roll_a, D("60"))], user=ns.owner, date=DAY)
    action = last(K.FABRIC)
    for item in action.items.exclude(after=None):
        for k, v in list(item.after.items()):
            if isinstance(v, str) and len(v) > 23 and v[10:11] == "T":
                item.after[k] = v[:23] + "Z"
        item.save(update_fields=["after"])
    assert actions.delete_blockers(action) == []
    actions.delete_step(action, user=ns.owner)
    assert not FabricIssue.objects.filter(lot=ns.lot).exists()


def test_the_confirmation_speaks_plainly_about_a_move(ns):
    all_in_house(ns)
    bundles = cut(ns)
    go(ns, bundles, "STITCH")
    lines = actions.consequences(last(K.MOVE), ns.owner)
    assert lines[0].startswith("take back: ") and "pieces to Stitching" in lines[0]
    assert not any("stage movement" in s or "StageMovement" in s for s in lines)
