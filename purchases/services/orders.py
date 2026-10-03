"""Purchase orders (E5.1, BR-19): approval above the company's limit, short-close, received vs ordered."""
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from inventory.services.stock import item_kwargs, q3
from purchases.models import GrnLine, PurchaseOrder, PurchaseOrderLine

PO_SCREEN = "purchases.po"


@dataclass
class POLineSpec:
    item: object
    qty: Decimal
    rate: Decimal


def _check_vendor(vendor):
    if not vendor.is_vendor:
        raise BusinessRuleError(f"{vendor.name} is not marked as a vendor.")
    if not vendor.is_active:
        raise BusinessRuleError(f"{vendor.name} is inactive.")


def _write_lines(po, lines):
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("A purchase order needs at least one line.")
    for spec in lines:
        if isinstance(spec.qty, float) or isinstance(spec.rate, float):
            raise BusinessRuleError("Quantity and rate must be Decimal.")
        if spec.qty <= 0:
            raise BusinessRuleError(f"Quantity of {spec.item} must be more than zero (BR-01).")
        if spec.rate < 0:
            raise BusinessRuleError(f"The rate of {spec.item} cannot be negative.")
        PurchaseOrderLine.objects.create(po=po, qty=spec.qty, rate=spec.rate, **item_kwargs(spec.item))


@transaction.atomic
def create_po(*, company, factory, vendor, date, lines, user, expected_date=None, remarks="") -> PurchaseOrder:
    assert_factory_access(user, factory)
    _check_vendor(vendor)
    po = PurchaseOrder.objects.create(
        company=company, factory=factory, vendor=vendor, date=date, expected_date=expected_date,
        remarks=remarks, created_by=user,
    )
    _write_lines(po, lines)
    return po


@transaction.atomic
def update_po(po, *, lines, user, vendor=None, date=None, expected_date=None, remarks=None) -> PurchaseOrder:
    po = PurchaseOrder.objects.get(pk=po.pk)
    assert_factory_access(user, po.factory)
    if po.status != PurchaseOrder.Status.DRAFT:
        raise BusinessRuleError("Only a draft purchase order can be edited.")
    if vendor is not None:
        _check_vendor(vendor)
        po.vendor = vendor
    po.date = date or po.date
    po.expected_date = expected_date if expected_date is not None else po.expected_date
    po.remarks = remarks if remarks is not None else po.remarks
    po.save()
    po.lines.all().delete()
    _write_lines(po, lines)
    return po


@transaction.atomic
def submit_po(po, *, user) -> PurchaseOrder:
    """Number the PO and send it for approval if it is above the limit; otherwise it is approved at once."""
    po = PurchaseOrder.objects.select_related("company", "factory").get(pk=po.pk)
    assert_factory_access(user, po.factory)
    if po.status != PurchaseOrder.Status.DRAFT:
        raise BusinessRuleError("This purchase order has already been submitted.")
    if not po.lines.exists():
        raise BusinessRuleError("A purchase order needs at least one line.")
    po.number = po.number or next_document_number(factory=po.factory, doc_type="purchase_order", on_date=po.date)
    if po.total > po.company.po_approval_limit:
        po.status = PurchaseOrder.Status.PENDING
    else:
        po.status = PurchaseOrder.Status.APPROVED
        po.approved_at = timezone.now()
    po.save()
    return po


@transaction.atomic
def approve_po(po, *, user) -> PurchaseOrder:
    po = PurchaseOrder.objects.get(pk=po.pk)
    if not user.has_screen_perm(PO_SCREEN, "approve"):
        raise BusinessRuleError("Only the owner can approve purchase orders above the limit.")
    assert_factory_access(user, po.factory)
    if po.status != PurchaseOrder.Status.PENDING:
        raise BusinessRuleError("This purchase order is not waiting for approval.")
    po.status = PurchaseOrder.Status.APPROVED
    po.approved_by, po.approved_at = user, timezone.now()
    po.save()
    return po


@transaction.atomic
def reject_po(po, *, user, reason) -> PurchaseOrder:
    """Send a pending PO back to draft with a reason."""
    po = PurchaseOrder.objects.get(pk=po.pk)
    if not user.has_screen_perm(PO_SCREEN, "approve"):
        raise BusinessRuleError("Only the owner can reject a purchase order.")
    if po.status != PurchaseOrder.Status.PENDING:
        raise BusinessRuleError("This purchase order is not waiting for approval.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason for sending the purchase order back.")
    po.status, po.remarks = PurchaseOrder.Status.DRAFT, f"Returned: {reason.strip()}"[:255]
    po.save()
    return po


@transaction.atomic
def short_close(po, *, user, reason) -> PurchaseOrder:
    po = PurchaseOrder.objects.get(pk=po.pk)
    assert_factory_access(user, po.factory)
    if po.status not in (PurchaseOrder.Status.APPROVED, PurchaseOrder.Status.PARTLY):
        raise BusinessRuleError("Only an approved or partly received purchase order can be short-closed.")
    if not reason.strip():
        raise BusinessRuleError("Give a reason to short-close the purchase order.")
    po.status, po.close_reason = PurchaseOrder.Status.CLOSED, reason.strip()
    po.save()
    return po


def received_qty(po_line) -> Decimal:
    """Accepted quantity of posted GRNs: pieces that failed QC still have to be re-supplied against the PO."""
    agg = GrnLine.objects.filter(po_line=po_line, grn__status="posted").aggregate(q=Sum("qty_accepted"))
    return q3(agg["q"])


def pending_qty(po_line) -> Decimal:
    return max(Decimal("0.000"), po_line.qty - received_qty(po_line))


def refresh_status(po):
    """After a GRN is posted or cancelled: move the PO between approved, partly received and received."""
    po = PurchaseOrder.objects.get(pk=po.pk)
    if po.status in (PurchaseOrder.Status.DRAFT, PurchaseOrder.Status.PENDING, PurchaseOrder.Status.CLOSED):
        return po
    lines = list(po.lines.all())
    got = [received_qty(l) for l in lines]
    if all(g >= l.qty for g, l in zip(got, lines)):
        po.status = PurchaseOrder.Status.RECEIVED
    elif any(g > 0 for g in got):
        po.status = PurchaseOrder.Status.PARTLY
    else:
        po.status = PurchaseOrder.Status.APPROVED
    po.save()
    return po


def pending_report(user, factory=None):
    """Ordered vs received per open PO line (the pending-PO report)."""
    qs = PurchaseOrderLine.objects.filter(
        po__status__in=("approved", "partly_received")
    ).select_related("po", "po__vendor", "material", "sku").order_by("po__date")
    ids = user.allowed_factory_ids()
    if ids is not None:
        qs = qs.filter(po__factory_id__in=ids)
    if factory is not None:
        qs = qs.filter(po__factory=factory)
    rows = []
    for line in qs:
        got = received_qty(line)
        rows.append({"po": line.po, "line": line, "ordered": line.qty, "received": got, "pending": max(line.qty - got, Decimal("0"))})
    return rows
