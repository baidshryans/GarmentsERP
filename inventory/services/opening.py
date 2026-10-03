"""Opening stock at go-live: fabric by roll, trims and packing by item, finished goods by SKU (INV, PRD E5/E6).

One document posts the stock movements and one balanced voucher: Dr stock ledgers, Cr Opening Balance
Difference (the same suspense ledger the opening balances use, so the accountant clears both together).
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from core.services.numbering import next_document_number
from inventory.models import OpeningStock, StockMovement
from inventory.services import stock
from ledger.models import Ledger
from ledger.services.posting import LineSpec, post_voucher

TWO = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass
class OpeningItem:
    item: object
    qty: Decimal
    rate: Decimal
    vendor_roll_no: str = ""  # fabric: the roll number on the roll
    lot_no: str = ""
    gsm: int | None = None
    width_cm: Decimal | None = None
    length_m: Decimal | None = None
    supplier: object | None = None


@transaction.atomic
def post_opening_stock(*, company, factory, location, entries, user, date=None) -> OpeningStock:
    assert_factory_access(user, factory)
    if location.factory_id != factory.pk:
        raise BusinessRuleError(f"{location} is not in factory {factory.code}.")
    entries = list(entries)
    if not entries:
        raise BusinessRuleError("Enter at least one item of opening stock.")
    date = date or company.books_from
    doc_no = next_document_number(factory=factory, doc_type="opening_stock", on_date=date)
    movements = []
    for e in entries:
        if isinstance(e.qty, float) or isinstance(e.rate, float):
            raise BusinessRuleError("Quantity and rate must be Decimal.")
        if e.qty <= 0:
            raise BusinessRuleError(f"Quantity of {e.item} must be more than zero (BR-01).")
        if e.rate < 0:
            raise BusinessRuleError(f"The rate of {e.item} cannot be negative.")
        roll = None
        if getattr(e.item, "kind", None) == "fabric":
            if not e.vendor_roll_no.strip():
                raise BusinessRuleError(f"{e.item.name} is stocked by roll: give each roll's number.")
            roll = stock.create_roll(
                company=company, material=e.item, supplier=e.supplier, vendor_roll_no=e.vendor_roll_no.strip(),
                lot_no=e.lot_no, gsm=e.gsm, width_cm=e.width_cm, received_qty=e.qty, received_length_m=e.length_m,
                rate=e.rate, received_date=date, source_type="inventory.openingstock",
            )
        movements.append(stock.post_movement(
            factory=factory, location=location, item=e.item, qty=e.qty, rate=e.rate, roll=roll,
            movement_type=StockMovement.Type.OPENING, date=date, user=user, notes=f"Opening stock {doc_no}",
        ))
    by_key = {}
    for (_, key), v in stock.gl_values(movements).items():
        by_key[key] = by_key.get(key, ZERO) + v
    specs = [LineSpec(ledger=Ledger.objects.get(company=company, system_key=k), debit=v.quantize(TWO, rounding=ROUND_HALF_UP))
             for k, v in by_key.items() if v > 0]
    total = sum((s.debit for s in specs), ZERO)
    if total > 0:
        specs.append(LineSpec(ledger=Ledger.objects.get(company=company, system_key="opening_difference"), credit=total,
                              narration="Opening stock"))
        voucher = post_voucher(company=company, factory=factory, voucher_type="opening", date=date, lines=specs,
                               user=user, narration=f"Opening stock {doc_no}")
    else:
        raise BusinessRuleError("The opening stock has no value; enter rates.")
    return OpeningStock.objects.create(
        company=company, factory=factory, location=location, number=doc_no, date=date, voucher=voucher,
        total_value=total, created_by=user,
    )


