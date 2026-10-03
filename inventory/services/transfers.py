"""Stock transfers between locations and factories (E6.2, PRD E7.9 for goods).

Same factory: stock moves location to location when issued; nothing hits the GL.
Between factories: when issued the stock and its value leave the source factory and arrive in the
destination factory's In Transit location, with matching GL entries in both books through the
Inter-Factory Receivable / Payable ledgers (ACC-17). Receiving moves it from In Transit to the final
location inside the destination factory.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.factories import transit_location
from core.services.numbering import next_document_number
from inventory.models import StockMovement, StockTransfer, StockTransferLine
from inventory.services import stock
from ledger.models import Ledger
from ledger.services.posting import LineSpec, post_voucher

ZERO = Decimal("0.00")
T = StockMovement.Type


def _lines_ok(lines, from_factory):
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("A transfer needs at least one line.")
    for item, qty, roll in lines:
        if isinstance(qty, float) or qty <= 0:
            raise BusinessRuleError(f"Quantity of {item} must be a Decimal above zero (BR-01).")
    return lines


@transaction.atomic
def create_transfer(*, company, from_factory, from_location, to_factory, to_location, date, lines, user,
                    document_type="challan", vehicle_no="", remarks="") -> StockTransfer:
    assert_factory_access(user, from_factory)
    if from_location.factory_id != from_factory.pk or to_location.factory_id != to_factory.pk:
        raise BusinessRuleError("A location does not belong to the chosen factory.")
    if from_location.pk == to_location.pk:
        raise BusinessRuleError("The source and destination are the same location.")
    t = StockTransfer.objects.create(
        company=company, from_factory=from_factory, from_location=from_location, to_factory=to_factory,
        to_location=to_location, date=date, document_type=document_type, vehicle_no=vehicle_no, remarks=remarks,
        created_by=user,
    )
    for item, qty, roll in _lines_ok(lines, from_factory):
        StockTransferLine.objects.create(transfer=t, qty=qty, roll=roll, **stock.item_kwargs(item))
    return t


@transaction.atomic
def issue_transfer(transfer, *, user) -> StockTransfer:
    t = StockTransfer.objects.select_related("from_factory", "to_factory", "from_location", "to_location", "company").get(pk=transfer.pk)
    assert_factory_access(user, t.from_factory)
    if t.status != StockTransfer.Status.DRAFT:
        raise BusinessRuleError("This transfer has already been issued.")
    inter = t.is_inter_factory
    dest_loc = transit_location(t.to_factory) if inter else t.to_location
    out_moves, in_moves = [], []
    for line in t.lines.select_related("material", "sku", "roll"):
        out = stock.post_movement(
            factory=t.from_factory, location=t.from_location, item=line.item, qty=-line.qty, roll=line.roll,
            movement_type=T.TRANSFER_OUT, date=t.date, user=user, source=t,
        )
        line.value = -out.value
        line.save(update_fields=["value"])
        # The destination side is not scoped to the issuer's factories: the goods arrive there regardless.
        stock.post_movement(
            factory=t.to_factory, location=dest_loc, item=line.item, qty=line.qty, roll=line.roll, value=line.value,
            movement_type=T.TRANSFER_IN, date=t.date, user=user, source=t, enforce_scope=False,
        )
        out_moves.append(out)
        in_moves.append((line, line.value))

    voucher = None
    if inter:
        company = t.company
        specs = []
        total = ZERO
        for (_, key), v in stock.gl_values(out_moves).items():
            amt = -v
            if amt > 0:
                total += amt
                specs.append(LineSpec(ledger=Ledger.objects.get(company=company, system_key=key), credit=amt, factory=t.from_factory))
                specs.append(LineSpec(ledger=Ledger.objects.get(company=company, system_key=key), debit=amt, factory=t.to_factory))
        if total > 0:
            specs.append(LineSpec(ledger=Ledger.objects.get(company=company, system_key="interfactory_receivable"),
                                  debit=total, factory=t.from_factory, narration=f"Stock sent to {t.to_factory.code}"))
            specs.append(LineSpec(ledger=Ledger.objects.get(company=company, system_key="interfactory_payable"),
                                  credit=total, factory=t.to_factory, narration=f"Stock received from {t.from_factory.code}"))
            voucher = post_voucher(
                company=company, factory=t.from_factory, voucher_type="stock_journal", date=t.date, lines=specs,
                user=user, narration=f"Stock transfer {t.from_factory.code} to {t.to_factory.code}", source=t,
                scope_lines=False,
            )
    t.number = next_document_number(factory=t.from_factory, doc_type="stock_transfer", on_date=t.date)
    t.voucher, t.issued_at = voucher, timezone.now()
    if inter:
        t.status = StockTransfer.Status.ISSUED
    else:
        t.status, t.received_at = StockTransfer.Status.RECEIVED, timezone.now()
    t.save()
    return t


@transaction.atomic
def receive_transfer(transfer, *, user) -> StockTransfer:
    t = StockTransfer.objects.select_related("to_factory", "to_location").get(pk=transfer.pk)
    assert_factory_access(user, t.to_factory)
    if t.status != StockTransfer.Status.ISSUED:
        raise BusinessRuleError("Only a transfer that is in transit can be received.")
    transit = transit_location(t.to_factory)
    today = timezone.localdate()
    for line in t.lines.select_related("material", "sku", "roll"):
        stock.post_movement(
            factory=t.to_factory, location=transit, item=line.item, qty=-line.qty, roll=line.roll, value=line.value,
            movement_type=T.TRANSFER_OUT, date=today, user=user, source=t, notes="Received from transit",
        )
        stock.post_movement(
            factory=t.to_factory, location=t.to_location, item=line.item, qty=line.qty, roll=line.roll, value=line.value,
            movement_type=T.TRANSFER_IN, date=today, user=user, source=t, notes="Received from transit",
        )
    t.status, t.received_at = StockTransfer.Status.RECEIVED, timezone.now()
    t.save()
    return t
