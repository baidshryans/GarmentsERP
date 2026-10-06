"""Job work challans (E8.1, JOB-01 to JOB-04, BR-04, BR-05).

A challan sends bundles (and the trims the BOM needs) to a fabricator for one step of a lot. Issuing it moves the
bundles to the fabricator's location, takes the trims out of stock into the lot's cost, and opens the fabricator's
material ledger. Rework goes out on its own challan with a rework rate.
"""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.factories import fabricator_location, godown_location
from core.services.numbering import next_document_number
from inventory.models import StockMovement
from inventory.services import stock
from jobwork.models import ChallanBundle, ChallanTrim, JobWorkChallan
from jobwork.services import rates
from ledger.services.posting import LineSpec, post_voucher
from masters.services import boms
from production.models import Bundle, LotCostEntry, LotRouteChange, LotStep
from production.services import bundles as bundle_service
from production.services import costing

T = StockMovement.Type
ZERO = Decimal("0.00")


class SecondFabricatorWarning(BusinessRuleError):
    """The lot is already open with another fabricator (BR-05). Confirm to go ahead."""


def open_challans(lot, exclude_party=None):
    qs = JobWorkChallan.objects.filter(lot=lot, status__in=("issued", "partly_received"))
    if exclude_party is not None:
        qs = qs.exclude(party=exclude_party)
    return qs


def _trim_needs(lot, bundles):
    """Trims the BOM needs for these bundles: {Material: quantity}. Only trims, not fabric."""
    version = lot.bom_version
    needs = {}
    if version is None:
        return needs
    for b in bundles:
        for material, qty, wastage in boms.consumption_for(version, b.sku.size):
            if material.kind == "trim":
                needs[material] = needs.get(material, Decimal("0")) + qty * (1 + wastage / 100) * b.qty
    return {m: q.quantize(Decimal("0.001")) for m, q in needs.items()}


@transaction.atomic
def create_challan(*, company, factory, party, lot, step, bundles, date, user, expected_date=None, kind="issue",
                   remarks="", confirm_second_fabricator=False) -> JobWorkChallan:
    assert_factory_access(user, factory)
    lot = type(lot).objects.select_related("company", "factory", "bom_version").get(pk=lot.pk)
    step = LotStep.objects.select_related("process", "party").get(pk=step.pk)
    if not party.is_fabricator:
        raise BusinessRuleError(f"{party.name} is not marked as a fabricator.")
    if not party.is_active:
        raise BusinessRuleError(f"{party.name} is inactive.")
    if step.lot_id != lot.pk:
        raise BusinessRuleError("That step belongs to a different lot (BR-04: a challan is for one lot).")
    if step.status == LotStep.Status.SKIPPED:
        raise BusinessRuleError(f"{step.process.name} was skipped on this lot.")
    bundles = [Bundle.objects.select_related("lot", "sku", "sku__size", "location", "location__factory", "current_step").get(pk=b.pk)
               for b in bundles]
    if not bundles:
        raise BusinessRuleError("Scan or choose at least one bundle.")
    for b in bundles:
        if b.lot_id != lot.pk:
            raise BusinessRuleError(f"Bundle {b.bundle_no} is from a different lot.")
        if b.location.factory_id != factory.pk:
            raise BusinessRuleError(f"Bundle {b.bundle_no} is in another factory; move it here first.")
        if b.challan_lines.filter(challan__status__in=("draft", "issued", "partly_received"), challan__kind=kind).exists():
            raise BusinessRuleError(f"Bundle {b.bundle_no} is already on an open challan.")

    others = open_challans(lot, exclude_party=party)
    if others.exists() and not confirm_second_fabricator:
        names = ", ".join(sorted({c.party.name for c in others.select_related("party")}))
        raise SecondFabricatorWarning(
            f"Lot {lot.lot_no} is already open with {names}. Issue it to {party.name} as well? (BR-05)")

    rate = rates.resolve(party, step, date)
    lines = []
    for b in bundles:
        if kind == JobWorkChallan.Kind.REWORK:
            if b.status != Bundle.Status.REWORK or not b.rework_qty:
                raise BusinessRuleError(f"Bundle {b.bundle_no} is not waiting for rework.")
            if b.current_step_id != step.pk:
                # a bundle sent back keeps the step of the challan it came back on: rework is that fabricator's step again
                where = b.current_step.process.name if b.current_step_id else "no step"
                raise BusinessRuleError(
                    f"Bundle {b.bundle_no} is waiting for rework at {where}, not {step.process.name}. "
                    f"Make the rework challan for {where}.")
            base = (ChallanBundle.objects.filter(bundle=b, challan__kind="issue").order_by("-id").first())
            price = (base.rate if base else ZERO) + rate.rework
            qty = b.qty
        else:
            bundle_service.check_entry(b, step, "")
            price = rate.for_size(b.sku.size)
            qty = b.qty
        lines.append((b, qty, price))
    if kind == JobWorkChallan.Kind.ISSUE and rate.rate_type != "D" and all(p <= 0 for _, _, p in lines):
        raise BusinessRuleError(f"There is no labour rate for {party.name} on {step.process.name}. Add one under Labour rates, or set a rate on the step.")

    challan = JobWorkChallan.objects.create(
        company=company, factory=factory, party=party, lot=lot, step=step, kind=kind, date=date,
        expected_date=expected_date, rate_type=rate.rate_type, flat_amount=rate.flat if kind == "issue" else ZERO,
        remarks=remarks, second_fabricator_ack=bool(others.exists()), created_by=user)
    for b, qty, price in lines:
        ChallanBundle.objects.create(challan=challan, bundle=b, qty_issued=qty, rate=price)
    if kind == JobWorkChallan.Kind.ISSUE and step.process.kind == "stitching":
        for material, qty in _trim_needs(lot, bundles).items():
            if qty > 0:
                ChallanTrim.objects.create(challan=challan, material=material, qty_issued=qty)
    return challan


@transaction.atomic
def issue_challan(challan, *, user) -> JobWorkChallan:
    challan = JobWorkChallan.objects.select_related("lot", "lot__company", "step", "step__process", "party", "factory").get(pk=challan.pk)
    assert_factory_access(user, challan.factory)
    if challan.status != JobWorkChallan.Status.DRAFT:
        raise BusinessRuleError("This challan has already been issued.")
    lot, step, party, factory = challan.lot, challan.step, challan.party, challan.factory
    date = challan.date
    place = fabricator_location(factory, party)
    bundles = [(cb, Bundle.objects.select_related("lot", "sku", "location", "location__factory", "current_step").get(pk=cb.bundle_id))
               for cb in challan.bundles.all()]

    rework = challan.kind == JobWorkChallan.Kind.REWORK
    if not rework:
        for _, b in bundles:
            bundle_service.check_entry(b, step, "")
        bundle_service.accrue_leaving_labour(
            lot, [(b, *_left(b)) for _, b in bundles], date, user, note=f"Issued to {party.name}")
    # the step belongs to this fabricator now
    if step.party_id != party.pk or step.assignment != LotStep.Assignment.SUBCONTRACT:
        if step.status in (LotStep.Status.PENDING, LotStep.Status.SKIPPED):
            step.assignment, step.party, step.factory = LotStep.Assignment.SUBCONTRACT, party, None
            step.save(update_fields=["assignment", "party", "factory"])
            LotRouteChange.objects.create(lot=lot, action="reassigned", reason=f"Challan to {party.name}", user=user,
                                          detail=f"{step.process.name} given to {party.name}")
    for cb, b in bundles:
        left_step, _ = _left(b)
        completed = b.completed_seq if (rework or left_step is None) else left_step.sequence
        bundle_service.apply_move(
            bundle=b, kind="issue", to_location=place, user=user, date=date, new_status=Bundle.Status.AT_STAGE,
            to_step=step, completed_seq=completed, challan=challan, reason=f"Challan {challan.kind}")
        if rework:
            Bundle.objects.filter(pk=b.pk).update(rework_qty=0)

    voucher = None
    trims = list(challan.trims.select_related("material"))
    if trims:
        godown = godown_location(factory)
        moves = []
        for t in trims:
            m = stock.post_movement(
                factory=factory, location=godown, item=t.material, qty=-t.qty_issued, movement_type=T.ISSUE, date=date,
                user=user, source=challan, lot=lot, notes=f"Trims to {party.name} for lot {lot.lot_no}")
            t.value = -m.value
            t.save(update_fields=["value"])
            moves.append(m)
        total = costing.r2(sum((t.value for t in trims), ZERO))
        if total > 0:
            company = challan.company
            voucher = post_voucher(
                company=company, factory=factory, voucher_type="stock_journal", date=date, user=user, source=challan,
                narration=f"Trims issued to {party.name} on challan, lot {lot.lot_no}",
                lines=[LineSpec(ledger=costing.ledger_for(company, "stock_wip"), debit=total),
                       LineSpec(ledger=costing.ledger_for(company, "stock_raw_material"), credit=total)])
            costing.add_cost(lot=lot, factory=factory, kind=LotCostEntry.Kind.TRIM, amount=total, date=date,
                             note=f"Trims to {party.name}", source=challan, voucher=voucher)
    challan.number = next_document_number(factory=factory, doc_type="challan", on_date=date)
    challan.status, challan.issued_at, challan.voucher = JobWorkChallan.Status.ISSUED, timezone.now(), voucher
    challan.save()
    bundle_service.refresh_steps(lot)
    return challan


def _left(b):
    """(stage being left, pieces passing) for a bundle about to be issued."""
    in_step = b.current_step if b.status == Bundle.Status.AT_STAGE else None
    return in_step, b.qty


@transaction.atomic
def cancel_draft(challan, *, user):
    challan = JobWorkChallan.objects.get(pk=challan.pk)
    assert_factory_access(user, challan.factory)
    if challan.status != JobWorkChallan.Status.DRAFT:
        raise BusinessRuleError("Only a draft challan can be discarded.")
    challan.status = JobWorkChallan.Status.CANCELLED
    challan.save(update_fields=["status"])
