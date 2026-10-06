"""Goods receipt with QC (E5.2, E5.3).

Fabric arrives roll by roll; every other line is a quantity with a QC result. Only accepted
quantity enters stock. Posting writes the stock movements and one GL voucher
(Dr stock, Cr Goods Received Not Billed) in a single transaction. Rejected quantity raises a
draft debit note (E5.3).
"""
from dataclasses import dataclass, field
from datetime import date as date_cls
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from inventory.models import FabricRoll, StockMovement
from inventory.services import stock
from ledger.models import Ledger
from ledger.services.posting import LineSpec, post_voucher, reverse_voucher
from purchases.models import DebitNote, DebitNoteLine, Grn, GrnLine, GrnRoll, QcStatus
from purchases.services import orders

TWO = Decimal("0.01")
ZERO = Decimal("0.00")
Q = QcStatus
ACCEPTED_STATES = (Q.ACCEPTED, Q.ACCEPTED_REMARK)


@dataclass
class RollSpec:
    vendor_roll_no: str
    qty: Decimal
    lot_no: str = ""
    gsm: int | None = None
    width_cm: Decimal | None = None
    length_m: Decimal | None = None
    qc_status: str = Q.PENDING
    remark: str = ""


@dataclass
class GrnLineSpec:
    item: object
    rate: Decimal
    qty_received: Decimal = Decimal("0.000")  # non-fabric lines
    qty_rejected: Decimal = Decimal("0.000")  # non-fabric QC
    remark: str = ""
    po_line: object | None = None
    rolls: list = field(default_factory=list)  # fabric lines


def _is_fabric(item):
    return getattr(item, "kind", None) == "fabric"


def _check_inputs(po, vendor, factory, user, lines):
    assert_factory_access(user, factory)
    if not vendor.is_vendor:
        raise BusinessRuleError(f"{vendor.name} is not marked as a vendor.")
    if po is not None:
        if po.vendor_id != vendor.pk or po.factory_id != factory.pk:
            raise BusinessRuleError("The purchase order is for a different vendor or factory.")
        if po.status not in ("approved", "partly_received"):
            raise BusinessRuleError(f"Purchase order {po} is not open for receipt (status: {po.get_status_display()}).")
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("A GRN needs at least one line.")
    return lines


def _write_lines(grn, lines):
    seen_rolls = set()
    for spec in lines:
        if isinstance(spec.rate, float) or spec.rate < 0:
            raise BusinessRuleError(f"The rate of {spec.item} must be a non-negative Decimal.")
        item_kw = stock.item_kwargs(spec.item)
        if _is_fabric(spec.item):
            if not spec.rolls:
                raise BusinessRuleError(f"{spec.item.name} is received roll by roll; enter its rolls.")
            line = GrnLine.objects.create(grn=grn, po_line=spec.po_line, rate=spec.rate, remark=spec.remark, **item_kw)
            for r in spec.rolls:
                if r.qty <= 0:
                    raise BusinessRuleError(f"Roll {r.vendor_roll_no}: the quantity must be more than zero (BR-01).")
                key = (spec.item.pk, r.vendor_roll_no.strip())
                if not r.vendor_roll_no.strip():
                    raise BusinessRuleError("Every roll needs a roll number.")
                if key in seen_rolls:
                    raise BusinessRuleError(f"Roll {r.vendor_roll_no} appears twice on this GRN.")
                seen_rolls.add(key)
                if FabricRoll.objects.filter(supplier=grn.vendor, vendor_roll_no=r.vendor_roll_no.strip()).exists():
                    raise BusinessRuleError(f"Roll {r.vendor_roll_no} from {grn.vendor.name} was already received.")
                GrnRoll.objects.create(
                    line=line, vendor_roll_no=r.vendor_roll_no.strip(), lot_no=r.lot_no, gsm=r.gsm,
                    width_cm=r.width_cm, qty=r.qty, length_m=r.length_m, qc_status=r.qc_status, remark=r.remark,
                )
        else:
            if spec.qty_received <= 0:
                raise BusinessRuleError(f"Quantity of {spec.item} must be more than zero (BR-01).")
            if not 0 <= spec.qty_rejected <= spec.qty_received:
                raise BusinessRuleError(f"Rejected quantity of {spec.item} must be between 0 and the quantity received.")
            GrnLine.objects.create(
                grn=grn, po_line=spec.po_line, rate=spec.rate, qty_received=spec.qty_received,
                qty_rejected=spec.qty_rejected, remark=spec.remark, **item_kw,
            )
    # PO over-receipt guard (checked against what is still pending on each PO line)
    if grn.po_id:
        for line in grn.lines.exclude(po_line=None).select_related("po_line"):
            got = line.qty_received if not line.is_fabric_rolls else sum((r.qty for r in line.rolls.all()), Decimal("0"))
            if got > orders.pending_qty(line.po_line):
                raise BusinessRuleError(
                    f"{line.item} is received above the purchase order's pending quantity "
                    f"({orders.pending_qty(line.po_line).normalize():f}). Raise another purchase order for the extra."
                )


@transaction.atomic
def create_grn(*, company, factory, location, vendor, date, lines, user, po=None, vendor_challan_no="",
               vendor_challan_date=None, remarks="") -> Grn:
    lines = _check_inputs(po, vendor, factory, user, lines)
    if location.factory_id != factory.pk:
        raise BusinessRuleError("The receiving location belongs to a different factory.")
    grn = Grn.objects.create(
        company=company, factory=factory, location=location, vendor=vendor, po=po, date=date,
        vendor_challan_no=vendor_challan_no, vendor_challan_date=vendor_challan_date, remarks=remarks, created_by=user,
    )
    _write_lines(grn, lines)
    return grn


@transaction.atomic
def update_grn(grn, *, lines, user, date=None, location=None, vendor_challan_no=None, remarks=None) -> Grn:
    grn = Grn.objects.select_related("po", "factory", "vendor").get(pk=grn.pk)
    assert_factory_access(user, grn.factory)
    if grn.status not in (Grn.Status.DRAFT, Grn.Status.QC_DONE):
        raise BusinessRuleError("A posted GRN cannot be edited; cancel it instead.")
    _check_inputs(grn.po, grn.vendor, grn.factory, user, lines)
    grn.date = date or grn.date
    if location is not None:
        grn.location = location
    if vendor_challan_no is not None:
        grn.vendor_challan_no = vendor_challan_no
    if remarks is not None:
        grn.remarks = remarks
    grn.status = Grn.Status.DRAFT
    grn.save()
    grn.lines.all().delete()
    _write_lines(grn, lines)
    return grn


@transaction.atomic
def finish_qc(grn, *, user) -> Grn:
    """Derive accepted / rejected quantities from the QC marks and move the GRN to 'QC done' (E5.3)."""
    grn = Grn.objects.get(pk=grn.pk)
    assert_factory_access(user, grn.factory)
    if grn.status not in (Grn.Status.DRAFT, Grn.Status.QC_DONE):
        raise BusinessRuleError("Only a draft GRN can go through QC.")
    for line in grn.lines.select_related("material", "sku").prefetch_related("rolls"):
        if line.is_fabric_rolls:
            rolls = list(line.rolls.all())
            if any(r.qc_status == Q.PENDING for r in rolls):
                raise BusinessRuleError(f"Mark every roll of {line.item.name} as accepted or rejected.")
            for r in rolls:
                if r.qc_status == Q.ACCEPTED_REMARK and not r.remark.strip():
                    raise BusinessRuleError(f"Roll {r.vendor_roll_no}: a remark is needed when accepting with a remark.")
            line.qty_received = sum((r.qty for r in rolls), Decimal("0.000"))
            line.qty_accepted = sum((r.qty for r in rolls if r.qc_status in ACCEPTED_STATES), Decimal("0.000"))
            line.qty_rejected = line.qty_received - line.qty_accepted
            statuses = {r.qc_status for r in rolls}
            line.qc_status = (Q.REJECTED if statuses == {Q.REJECTED} else
                              Q.ACCEPTED if statuses == {Q.ACCEPTED} else Q.ACCEPTED_REMARK)
        else:
            rej = line.qty_rejected
            line.qty_accepted = line.qty_received - rej
            if rej == line.qty_received:
                line.qc_status = Q.REJECTED
            elif rej == 0 and not line.remark.strip():
                line.qc_status = Q.ACCEPTED
            else:
                if not line.remark.strip():
                    raise BusinessRuleError(f"{line.item}: a remark is needed when part of the quantity is rejected.")
                line.qc_status = Q.ACCEPTED_REMARK
        line.save()
    grn.status = Grn.Status.QC_DONE
    grn.save()
    return grn


def untouched(grn) -> bool:
    """Read-only: a draft on which no quality check result has been recorded yet, on any roll or line."""
    if grn.status != Grn.Status.DRAFT:
        return False
    if GrnRoll.objects.filter(line__grn=grn).exclude(qc_status=Q.PENDING).exists():
        return False
    for line in grn.lines.select_related("material"):
        if line.qc_status != Q.PENDING or (not line.is_fabric_rolls and (line.qty_rejected or line.remark.strip())):
            return False
    return True


@transaction.atomic
def accept_all_and_post(grn, *, user) -> Grn:
    """Accept everything on an unchecked GRN, finish its QC and post it (the page's "Accept all and post").
    The three existing steps in one transaction: if any of them fails, nothing is saved and no number is used."""
    grn = Grn.objects.get(pk=grn.pk)
    if not untouched(grn):
        raise BusinessRuleError("Some of these goods already have a quality check result. Finish the check line by line, then post.")
    rolls = {pk: (Q.ACCEPTED, "") for pk in GrnRoll.objects.filter(line__grn=grn).values_list("pk", flat=True)}
    lines = {l.pk: (Decimal("0.000"), "") for l in grn.lines.select_related("material") if not l.is_fabric_rolls}
    record_qc(grn, user=user, rolls=rolls, lines=lines)
    finish_qc(grn, user=user)
    return post_grn(grn, user=user)


def _round(v):
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


@transaction.atomic
def post_grn(grn, *, user) -> Grn:
    grn = Grn.objects.select_related("factory", "location", "vendor", "po", "company").get(pk=grn.pk)
    assert_factory_access(user, grn.factory)
    if grn.status != Grn.Status.QC_DONE:
        raise BusinessRuleError("Finish QC before posting the GRN.")
    movements = []
    rejected_lines = []
    for line in grn.lines.select_related("material", "sku").prefetch_related("rolls"):
        value = ZERO
        if line.is_fabric_rolls:
            for r in line.rolls.all():
                if r.qc_status not in ACCEPTED_STATES:
                    continue
                roll = stock.create_roll(
                    company=grn.company, material=line.material, supplier=grn.vendor, vendor_roll_no=r.vendor_roll_no,
                    lot_no=r.lot_no, gsm=r.gsm, width_cm=r.width_cm, received_qty=r.qty, received_length_m=r.length_m,
                    rate=line.rate, received_date=grn.date, source_type=grn._meta.label_lower, source_id=grn.pk,
                )
                r.roll = roll
                r.save(update_fields=["roll"])
                m = stock.post_movement(
                    factory=grn.factory, location=grn.location, item=line.material, qty=r.qty, rate=line.rate,
                    roll=roll, movement_type=StockMovement.Type.RECEIPT, date=grn.date, user=user, source=grn,
                )
                movements.append(m)
                value += m.value
        elif line.qty_accepted > 0:
            m = stock.post_movement(
                factory=grn.factory, location=grn.location, item=line.item, qty=line.qty_accepted, rate=line.rate,
                movement_type=StockMovement.Type.RECEIPT, date=grn.date, user=user, source=grn,
            )
            movements.append(m)
            value = m.value
        line.value = value
        line.save(update_fields=["value"])
        if line.qty_rejected > 0:
            rejected_lines.append(line)

    voucher = None
    if movements:
        by_ledger = stock.gl_values(movements)
        specs = [
            LineSpec(ledger=Ledger.objects.get(company=grn.company, system_key=key), debit=_round(total))
            for (_, key), total in by_ledger.items() if total > 0
        ]
        grni = sum((s.debit for s in specs), ZERO)
        specs.append(LineSpec(
            ledger=Ledger.objects.get(company=grn.company, system_key="grni"), credit=grni,
            narration=f"GRN {grn.vendor.name}",
        ))
        voucher = post_voucher(
            company=grn.company, factory=grn.factory, voucher_type="stock_journal", date=grn.date, lines=specs,
            user=user, narration=f"Goods received from {grn.vendor.name}", source=grn,
        )
    grn.number = next_document_number(factory=grn.factory, doc_type="goods_receipt", on_date=grn.date)
    grn.status, grn.voucher, grn.posted_at = Grn.Status.POSTED, voucher, timezone.now()
    grn.save()

    if rejected_lines:
        note = DebitNote.objects.create(
            company=grn.company, factory=grn.factory, kind=DebitNote.Kind.REJECTION, vendor=grn.vendor, grn=grn,
            date=grn.date, reason=f"Rejected at QC on {grn.number}", created_by=user,
        )
        for line in rejected_lines:
            DebitNoteLine.objects.create(
                note=note, grn_line=line, qty=line.qty_rejected, rate=line.rate, amount=ZERO, **stock.item_kwargs(line.item)
            )
    if grn.po_id:
        orders.refresh_status(grn.po)
    return grn


@transaction.atomic
def cancel_grn(grn, *, user, reason) -> Grn:
    """Reverse a posted GRN. Refused if it has been invoiced, debited, or its stock has been used."""
    grn = Grn.objects.select_related("factory", "po").get(pk=grn.pk)
    assert_factory_access(user, grn.factory)
    if grn.status != Grn.Status.POSTED:
        raise BusinessRuleError("Only a posted GRN can be cancelled.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the GRN.")
    if grn.lines.filter(invoice_lines__invoice__status="posted").exists():
        raise BusinessRuleError("This GRN has been invoiced; cancel the purchase invoice first.")
    if DebitNote.objects.filter(grn=grn, status="posted").exists():
        raise BusinessRuleError("A debit note has been posted against this GRN; cancel it first.")
    today = timezone.localdate()
    for m in StockMovement.objects.filter(source_type=grn._meta.label_lower, source_id=grn.pk,
                                          movement_type=StockMovement.Type.RECEIPT).select_related("material", "sku", "roll", "location", "factory"):
        stock.reverse_movement(m, user=user, date=max(today, grn.date), source=grn, notes=f"GRN {grn.number} cancelled")
    if grn.voucher_id:
        reverse_voucher(grn.voucher, user=user, reason=f"GRN cancelled: {reason.strip()}", date=max(today, grn.date))
    for gr in GrnRoll.objects.filter(line__grn=grn, roll__isnull=False).select_related("roll"):
        # free the vendor's roll number so the roll can be received again on a corrected GRN
        gr.roll.vendor_roll_no = f"{gr.roll.vendor_roll_no}-CANCELLED-{grn.pk}"[:40]
        gr.roll.save(update_fields=["vendor_roll_no"])
    DebitNote.objects.filter(grn=grn, status="draft").update(status="cancelled")
    grn.status = Grn.Status.CANCELLED
    grn.remarks = f"Cancelled: {reason.strip()}"[:255]
    grn.save()
    if grn.po_id:
        orders.refresh_status(grn.po)
    return grn


@transaction.atomic
def record_qc(grn, *, user, rolls=None, lines=None) -> Grn:
    """Store QC marks: rolls = {GrnRoll id: (status, remark)}, lines = {GrnLine id: (qty_rejected, remark)}."""
    grn = Grn.objects.get(pk=grn.pk)
    assert_factory_access(user, grn.factory)
    if grn.status not in (Grn.Status.DRAFT, Grn.Status.QC_DONE):
        raise BusinessRuleError("A posted GRN cannot go through QC again.")
    valid = {s for s, _ in QcStatus.choices}
    for rid, (status, remark) in (rolls or {}).items():
        if status not in valid:
            raise BusinessRuleError("Unknown QC status.")
        GrnRoll.objects.filter(pk=rid, line__grn=grn).update(qc_status=status, remark=remark.strip())
    for lid, (rejected, remark) in (lines or {}).items():
        line = GrnLine.objects.get(pk=lid, grn=grn)
        if line.is_fabric_rolls:
            continue
        if rejected < 0 or rejected > line.qty_received:
            raise BusinessRuleError(f"Rejected quantity of {line.item} must be between 0 and {line.qty_received.normalize():f}.")
        line.qty_rejected, line.remark = rejected, remark.strip()
        line.save(update_fields=["qty_rejected", "remark"])
    grn.status = Grn.Status.DRAFT
    grn.save(update_fields=["status"])
    return grn
