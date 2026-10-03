"""Receiving work back and QC (E8.2, E8.3, BR-03, BR-17).

The supervisor counts bundles back from the fabricator. A fabricator marking a bundle "Done" is not a receipt (MOB-03).
A count above what was issued needs approval (BR-03). Pieces not returned are a shortage recorded against the
fabricator. QC then accepts, rejects or sends a bundle back for rework; only accepted pieces are ever paid.
"""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.factories import godown_location, process_location
from core.services.numbering import next_document_number
from inventory.models import StockMovement
from inventory.services import stock
from jobwork.models import ChallanBundle, ChallanTrim, JobWorkChallan, QcResult, Receipt, ReceiptLine, ReceiptTrim
from ledger.services.posting import LineSpec, post_voucher
from production.models import Bundle, LotCostEntry, LotStep
from production.services import bundles as bundle_service
from production.services import costing

T = StockMovement.Type
ZERO = Decimal("0.00")
RECEIPT_SCREEN = "jobwork.receipt"


@dataclass
class Counted:
    """What came back for one challan bundle: the pieces counted, and (when closing the line) any that will not come."""

    challan_bundle: object
    counted: int
    shortage: int = 0  # filled in automatically: issued minus counted, when positive


def _cost_per_piece(lot, factory):
    pieces = costing.live_pieces(lot, factory)
    return costing.r2(costing.lot_cost(lot, factory) / pieces) if pieces else ZERO


@transaction.atomic
def create_receipt(*, challan, counts, user, date, location=None, trims=None) -> Receipt:
    """Count bundles back. counts = [Counted]; trims = {ChallanTrim: (returned, missing)}.

    Within the quantity on the challan the receipt is posted at once. If any bundle is counted above what was
    issued, nothing moves until the owner approves it (BR-03)."""
    challan = JobWorkChallan.objects.select_related("lot", "factory", "party", "company", "step").get(pk=challan.pk)
    assert_factory_access(user, challan.factory)
    if challan.status not in (JobWorkChallan.Status.ISSUED, JobWorkChallan.Status.PARTLY):
        raise BusinessRuleError("Only an issued challan can receive goods.")
    counts = list(counts)
    if not counts:
        raise BusinessRuleError("Scan or choose at least one bundle that came back.")
    place = location or process_location(challan.factory)
    if place.factory_id != challan.factory_id:
        raise BusinessRuleError("Receive into a location of the factory that issued the challan.")
    receipt = Receipt.objects.create(company=challan.company, factory=challan.factory, challan=challan, date=date,
                                     location=place, created_by=user)
    over = False
    seen = set()
    for c in counts:
        cb = ChallanBundle.objects.select_related("bundle").get(pk=c.challan_bundle.pk, challan=challan)
        if cb.pk in seen:
            raise BusinessRuleError(f"Bundle {cb.bundle.bundle_no} appears twice.")
        seen.add(cb.pk)
        if cb.qty_received or cb.qty_shortage:
            raise BusinessRuleError(f"Bundle {cb.bundle.bundle_no} has already been received.")
        if c.counted < 0:
            raise BusinessRuleError("The counted pieces cannot be negative.")
        over_qty = max(0, c.counted - cb.qty_issued)
        short = max(0, cb.qty_issued - c.counted)
        over = over or over_qty > 0
        ReceiptLine.objects.create(
            receipt=receipt, challan_bundle=cb, qty_received=c.counted, over_qty=over_qty, shortage_qty=short,
            shortage_value=costing.r2(_cost_per_piece(challan.lot, challan.factory) * short))
    for t, (returned, missing) in (trims or {}).items():
        t = ChallanTrim.objects.get(pk=t.pk, challan=challan)
        if returned < 0 or missing < 0 or returned + missing > t.qty_issued - t.qty_returned - t.qty_missing:
            raise BusinessRuleError(f"{t.material.name}: returned plus missing is more than what is still with the fabricator.")
        ReceiptTrim.objects.create(receipt=receipt, challan_trim=t, qty_returned=returned, qty_missing=missing)
    if over:
        receipt.status = Receipt.Status.PENDING_APPROVAL
        receipt.save(update_fields=["status"])
        return receipt
    return _post_receipt(receipt, user)


@transaction.atomic
def approve_receipt(receipt, *, user) -> Receipt:
    receipt = Receipt.objects.select_related("challan", "challan__factory").get(pk=receipt.pk)
    if not user.has_screen_perm(RECEIPT_SCREEN, "approve"):
        raise BusinessRuleError("Only the owner can approve a receipt above the quantity issued (BR-03).")
    assert_factory_access(user, receipt.challan.factory)
    if receipt.status != Receipt.Status.PENDING_APPROVAL:
        raise BusinessRuleError("This receipt is not waiting for approval.")
    receipt.approved_by = user
    receipt.save(update_fields=["approved_by"])
    return _post_receipt(receipt, user)


def _post_receipt(receipt, user) -> Receipt:
    challan = receipt.challan
    lot, factory, date = challan.lot, challan.factory, receipt.date
    for line in receipt.lines.select_related("challan_bundle", "challan_bundle__bundle"):
        cb = line.challan_bundle
        bundle_service.apply_move(
            bundle=cb.bundle, kind="receipt", to_location=receipt.location, user=user, date=date,
            new_status=Bundle.Status.RECEIVED, shortage=line.shortage_qty, extra=line.over_qty,
            reason=f"Received from {challan.party.name}", challan=challan)
        cb.qty_received, cb.qty_shortage = line.qty_received, line.shortage_qty
        cb.save(update_fields=["qty_received", "qty_shortage"])
    returned_value = ZERO
    godown = godown_location(factory)
    for rt in receipt.trims.select_related("challan_trim", "challan_trim__material"):
        t = rt.challan_trim
        if rt.qty_returned > 0:
            value = costing.r2(t.unit_cost * rt.qty_returned)
            stock.post_movement(factory=factory, location=godown, item=t.material, qty=rt.qty_returned, value=value,
                                movement_type=T.RECEIPT, date=date, user=user, source=receipt, lot=lot,
                                notes=f"Trims returned by {challan.party.name}")
            returned_value += value
        t.qty_returned += rt.qty_returned
        t.qty_missing += rt.qty_missing
        t.save(update_fields=["qty_returned", "qty_missing"])
    if returned_value > 0:
        company = challan.company
        voucher = post_voucher(
            company=company, factory=factory, voucher_type="stock_journal", date=date, user=user, source=receipt,
            narration=f"Trims returned by {challan.party.name}, lot {lot.lot_no}",
            lines=[LineSpec(ledger=costing.ledger_for(company, "stock_raw_material"), debit=returned_value),
                   LineSpec(ledger=costing.ledger_for(company, "stock_wip"), credit=returned_value)])
        costing.add_cost(lot=lot, factory=factory, kind=LotCostEntry.Kind.TRIM, amount=-returned_value, date=date,
                         note="Trims returned", source=receipt, voucher=voucher)
    receipt.number = next_document_number(factory=factory, doc_type="jw_receipt", on_date=date)
    receipt.status = Receipt.Status.RECEIVED
    receipt.save()
    _refresh_challan(challan)
    bundle_service.refresh_steps(lot)
    return receipt


def _refresh_challan(challan):
    challan = JobWorkChallan.objects.get(pk=challan.pk)
    lines = list(challan.bundles.all())
    if challan.status in (JobWorkChallan.Status.BILLED, JobWorkChallan.Status.CLOSED, JobWorkChallan.Status.CANCELLED):
        return challan
    done = [cb for cb in lines if cb.qty_received or cb.qty_shortage]
    if len(done) == len(lines):
        challan.status = JobWorkChallan.Status.RECEIVED
    elif done:
        challan.status = JobWorkChallan.Status.PARTLY
    challan.save(update_fields=["status"])
    return challan


@transaction.atomic
def record_qc(*, receipt_line, accepted, rejected=0, rework=0, user, reject_reason="", destination="rejects") -> QcResult:
    """QC of one received bundle. accepted + rejected + rework must equal the pieces received.

    Rejected pieces go to rejects stock (or are scrapped). Rework sends the whole bundle back to the fabricator
    on a rework challan, so no pieces are accepted yet (split bundles arrive in a later release)."""
    line = ReceiptLine.objects.select_related(
        "receipt", "receipt__challan", "receipt__challan__factory", "receipt__challan__lot", "challan_bundle",
        "challan_bundle__bundle", "challan_bundle__challan").get(pk=receipt_line.pk)
    challan = line.receipt.challan
    assert_factory_access(user, challan.factory)
    if line.receipt.status == Receipt.Status.PENDING_APPROVAL:
        raise BusinessRuleError("This receipt is waiting for approval; QC comes after.")
    if line.qc_done:
        raise BusinessRuleError("QC has already been recorded for this bundle.")
    for name, v in (("accepted", accepted), ("rejected", rejected), ("rework", rework)):
        if v < 0:
            raise BusinessRuleError(f"{name.capitalize()} cannot be negative.")
    if accepted + rejected + rework != line.qty_received:
        raise BusinessRuleError(
            f"Accepted {accepted} + rejected {rejected} + rework {rework} must equal the {line.qty_received} pieces received.")
    if rework and accepted:
        raise BusinessRuleError("To send pieces back for rework, send the whole bundle: accepted pieces cannot be split off yet.")
    if rejected and not reject_reason.strip():
        raise BusinessRuleError("Give the reason for rejecting pieces.")
    cb = line.challan_bundle
    bundle = Bundle.objects.select_related("current_step", "lot").get(pk=cb.bundle_id)
    step = challan.step
    date = timezone.localdate()
    scrap = destination == QcResult.Destination.SCRAP
    new_status = Bundle.Status.REWORK if rework else Bundle.Status.READY
    bundle_service.apply_move(
        bundle=bundle, kind="qc", to_location=bundle.location, user=user, date=date, new_status=new_status,
        completed_seq=None if rework else max(bundle.completed_seq, step.sequence),
        rejection=0 if scrap else rejected, loss=rejected if scrap else 0, reason=reject_reason or "QC")
    Bundle.objects.filter(pk=bundle.pk).update(rework_qty=rework)
    result = QcResult.objects.create(
        line=line, accepted=accepted, rejected=rejected, rework=rework, reject_reason=reject_reason.strip(),
        destination=destination, rate=cb.rate, is_rework_pass=challan.kind == JobWorkChallan.Kind.REWORK, checked_by=user)
    line.qc_done = True
    line.save(update_fields=["qc_done"])
    cb.qty_accepted += accepted
    cb.qty_rejected += rejected
    cb.save(update_fields=["qty_accepted", "qty_rejected"])
    receipt = line.receipt
    if not receipt.lines.filter(qc_done=False).exists():
        receipt.status = Receipt.Status.QC_DONE
        receipt.save(update_fields=["status"])
    bundle_service.refresh_steps(bundle.lot)
    return result
