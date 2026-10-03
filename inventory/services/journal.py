"""Stock journal (E9.2): stock taken out and brought in at one location, with the voucher, in one transaction.

    Cr / Dr stock ledger   - the value of what went out (Cr) and came in (Dr), per stock ledger (raw material, finished goods)
    Dr / Cr Stock Adjustments - the difference: a loss when more value went out than came in, a gain when less

Out lines are valued by the company's method (or the roll's own cost), like any issue. In lines need a rate. Fabric goes out
by roll and comes in as a new roll. A journal is cancelled by reversing its movements and voucher, which fails if the stock
has been used since."""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from inventory.models import FabricRoll, StockJournal, StockJournalLine, StockMovement
from inventory.services import stock
from ledger.models import Ledger
from ledger.services.posting import LineSpec, post_voucher, reverse_voucher
from masters.models import SKU, Material

ZERO = Decimal("0.00")
TWO = Decimal("0.01")
Dir = StockJournalLine.Direction


@dataclass
class JournalLineSpec:
    direction: str
    item: object
    qty: Decimal
    rate: Decimal | None = None   # brought-in lines
    roll: object | None = None    # fabric taken out: the FabricRoll; fabric brought in: leave blank and give new_roll_no
    new_roll_no: str = ""


def _r2(v):
    return Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


@transaction.atomic
def post_journal(*, company, factory, location, date, reason, lines, user, remarks="") -> StockJournal:
    assert_factory_access(user, factory)
    if location.factory_id != factory.pk:
        raise BusinessRuleError(f"Location {location} is not in factory {factory.code}.")
    if reason not in dict(StockJournal.Reason.choices):
        raise BusinessRuleError("Choose the reason for the journal.")
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("Add at least one line.")
    journal = StockJournal.objects.create(company=company, factory=factory, location=location, date=date, reason=reason,
                                          remarks=remarks.strip(), created_by=user)
    movements, value_in, value_out = [], ZERO, ZERO
    for spec in lines:
        if spec.direction not in (Dir.IN, Dir.OUT):
            raise BusinessRuleError("Each line is either taken out or brought in.")
        if not isinstance(spec.item, (Material, SKU)):
            raise BusinessRuleError("Choose an item on every line.")
        if isinstance(spec.qty, float) or not isinstance(spec.qty, (Decimal, int)) or spec.qty <= 0:
            raise BusinessRuleError(f"Quantity of {spec.item} must be a Decimal above zero.")
        is_fabric = isinstance(spec.item, Material) and spec.item.kind == "fabric"
        kw = {"material": spec.item} if isinstance(spec.item, Material) else {"sku": spec.item}
        roll = spec.roll
        if spec.direction == Dir.OUT:
            if is_fabric and roll is None:
                raise BusinessRuleError(f"{spec.item.name} is stocked by roll: choose the roll to take out.")
            m = stock.post_movement(factory=factory, location=location, item=spec.item, qty=-Decimal(spec.qty), roll=roll,
                                    movement_type=StockMovement.Type.ADJUSTMENT, date=date, user=user, source=journal,
                                    notes=f"Stock journal ({journal.get_reason_display()})")
            value_out += -m.value
            line_value, rate = -m.value, None
        else:
            if spec.rate is None or isinstance(spec.rate, float) or spec.rate < 0:
                raise BusinessRuleError(f"Give a rate (a Decimal, zero or more) for {spec.item} brought in.")
            if is_fabric:
                if not spec.new_roll_no.strip():
                    raise BusinessRuleError(f"{spec.item.name} comes in by roll: give the new roll's number.")
                roll = stock.create_roll(company=company, material=spec.item, vendor_roll_no=spec.new_roll_no.strip(),
                                         received_qty=Decimal(spec.qty), rate=spec.rate, received_date=date,
                                         source_type="inventory.stockjournal")
            m = stock.post_movement(factory=factory, location=location, item=spec.item, qty=Decimal(spec.qty), rate=spec.rate, roll=roll,
                                    movement_type=StockMovement.Type.ADJUSTMENT, date=date, user=user, source=journal,
                                    notes=f"Stock journal ({journal.get_reason_display()})")
            value_in += m.value
            line_value, rate = m.value, spec.rate
        movements.append(m)
        StockJournalLine.objects.create(journal=journal, direction=spec.direction, roll=roll, qty=Decimal(spec.qty), rate=rate,
                                        value=line_value, **kw)

    def ledger(key):
        return Ledger.objects.get(company=company, system_key=key)

    specs, gross = [], {}
    for m in movements:                   # gross, not netted, so a conversion inside one ledger still shows what moved
        key = stock.stock_ledger_key(m.item)
        side = gross.setdefault(key, [ZERO, ZERO])
        side[0 if m.qty > 0 else 1] += abs(m.value)
    for key, (dr, cr) in gross.items():
        if dr > 0:
            specs.append(LineSpec(ledger=ledger(key), debit=_r2(dr), narration="Stock brought in"))
        if cr > 0:
            specs.append(LineSpec(ledger=ledger(key), credit=_r2(cr), narration="Stock taken out"))
    diff = _r2(value_in - value_out)          # positive: stock value gained
    if diff > 0:
        specs.append(LineSpec(ledger=ledger("stock_adjustment"), credit=diff, narration="Stock gain"))
    elif diff < 0:
        specs.append(LineSpec(ledger=ledger("stock_adjustment"), debit=-diff, narration="Stock loss"))
    if not specs:
        raise BusinessRuleError("The journal has no value to post; give a rate on what comes in, or take out stock that has value.")
    voucher = post_voucher(
        company=company, factory=factory, voucher_type="stock_journal", date=date, lines=specs, user=user,
        narration=f"Stock journal: {journal.get_reason_display()}" + (f", {remarks.strip()}" if remarks.strip() else ""), source=journal)
    journal.number, journal.voucher = voucher.number, voucher
    journal.value_in, journal.value_out = value_in, value_out
    journal.save()
    return journal


@transaction.atomic
def cancel_journal(journal, *, user, reason) -> StockJournal:
    journal = StockJournal.objects.select_related("factory").get(pk=journal.pk)
    assert_factory_access(user, journal.factory)
    if journal.status != StockJournal.Status.POSTED:
        raise BusinessRuleError("This journal is already cancelled.")
    if not reason or not reason.strip():
        raise BusinessRuleError("Give a reason to cancel the journal.")
    when = max(timezone.localdate(), journal.date)
    # bring-ins are reversed first (they must still be on hand), then the take-outs go back
    moves = list(StockMovement.objects.filter(source_type=journal._meta.label_lower, source_id=journal.pk).select_related(
        "material", "sku", "roll", "location", "factory").order_by("-qty", "id"))
    for m in moves:
        stock.reverse_movement(m, user=user, date=when, source=journal, notes=f"Stock journal {journal.number} cancelled")
    reverse_voucher(journal.voucher, user=user, reason=f"Stock journal cancelled: {reason.strip()}", date=when)
    journal.status = StockJournal.Status.CANCELLED
    journal.remarks = f"Cancelled: {reason.strip()}"[:255]
    journal.save()
    return journal
