"""The stock engine: the only way stock quantity or value changes (PRD 10.2 item 4).

Every change is an append-only StockMovement; StockBalance and RollBalance are updated in the same
transaction with a conditional UPDATE (`qty >= x`), so an issue above stock on hand fails atomically
on SQLite and PostgreSQL alike, without select_for_update.

Valuation (company setting): weighted average per item per factory, or - for fabric rolls only -
the specific cost of the roll. Items that are not rolls always use weighted average. Both levels
(item balance and roll balance) always move by the same value, so they stay consistent whichever
method is chosen and whenever it is changed.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum

from core.models import Company
from core.scoping import assert_factory_access
from inventory.exceptions import InsufficientStock, StockError
from inventory.models import FabricRoll, RollBalance, StockBalance, StockMovement
from masters.models import SKU, Material

TWO = Decimal("0.01")
THREE = Decimal("0.001")
ZERO = Decimal("0.00")
T = StockMovement.Type

# Pieces (SKUs) in these places are work in progress: only the quantity is tracked here, the money sits in the
# lot's cost entries and the WIP ledger (Step 4). They never take part in a finished-goods average cost.
QTY_ONLY_TYPES = ("cutting", "process", "fabricator", "rejects")


def is_quantity_only(item, location) -> bool:
    return isinstance(item, SKU) and location.loc_type in QTY_ONLY_TYPES


def item_kwargs(item):
    if isinstance(item, Material):
        return {"material": item}
    if isinstance(item, SKU):
        return {"sku": item}
    raise StockError("Stock items are materials or SKUs.")


def stock_ledger_key(item) -> str:
    """Which GL stock ledger an item belongs to: fabric, trims and packing vs finished goods."""
    return "stock_raw_material" if isinstance(item, Material) else "stock_finished"


def q2(value) -> Decimal:
    """Round an aggregate (SQLite sums DecimalFields as floats) back to paise."""
    return Decimal(value or 0).quantize(TWO, rounding=ROUND_HALF_UP)


def q3(value) -> Decimal:
    return Decimal(value or 0).quantize(THREE, rounding=ROUND_HALF_UP)


def _qty(value, what="Quantity") -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, int)):
        raise StockError(f"{what} must be a Decimal, not {type(value).__name__}.")
    value = Decimal(value)
    if value != value.quantize(THREE):
        raise StockError(f"{what} {value} has more than three decimal places.")
    return value.quantize(THREE)


def _money(value, what="Value") -> Decimal:
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, int)):
        raise StockError(f"{what} must be a Decimal, not {type(value).__name__}.")
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def on_hand(factory, item):
    """(qty, value) of an item across all locations of a factory."""
    qs = StockBalance.objects.filter(factory=factory, **item_kwargs(item))
    if isinstance(item, SKU):
        qs = qs.exclude(location__loc_type__in=QTY_ONLY_TYPES)
    agg = qs.aggregate(q=Sum("qty"), v=Sum("value"))
    return q3(agg["q"]), q2(agg["v"])


def _outbound_value(*, factory, location, item, out_qty, roll, method):
    """Value that leaves stock for `out_qty` (positive). Clears the residue when the last unit goes."""
    if roll is not None and method == Company.Valuation.SPECIFIC_ROLL:
        rb = RollBalance.objects.filter(roll=roll, location=location).first()
        if rb is not None and rb.qty > 0:
            return rb.value if out_qty >= rb.qty else (rb.value * out_qty / rb.qty).quantize(TWO, rounding=ROUND_HALF_UP)
    total_qty, total_value = on_hand(factory, item)
    if total_qty <= 0:
        return ZERO
    if out_qty >= total_qty:
        return total_value
    return (total_value * out_qty / total_qty).quantize(TWO, rounding=ROUND_HALF_UP)


def _apply(model, pk, d_qty, d_value, *, floor, error):
    """Add to a balance row atomically: read, compute in Decimal, write only if the row is unchanged."""
    for _ in range(10):
        row = model.objects.get(pk=pk)
        new_qty, new_value = row.qty + d_qty, row.value + d_value
        if floor and new_qty < 0:
            raise error(row.qty)
        if model.objects.filter(pk=pk, qty=row.qty, value=row.value).update(qty=new_qty, value=new_value):
            return
    raise StockError("The stock record is busy; please try again.")


@transaction.atomic
def post_movement(*, factory, location, item, qty, movement_type, date, user, source=None, voucher=None,
                  roll=None, rate=None, value=None, notes="", enforce_scope=True, bundle=None, lot=None) -> StockMovement:
    """Record one movement. qty is signed (+ in, - out).

    Inbound needs `value` or `rate` (value = qty x rate). Outbound is valued by the company's method
    unless `value` (a positive magnitude) is given, which reversals and transfer receipts use to move
    exactly the value that left. A revaluation has qty 0 and a signed `value`.
    """
    if enforce_scope:  # a transfer's destination side is a consequence of the issuer's own action
        assert_factory_access(user, factory)
    company = factory.company
    if location.factory_id != factory.pk:
        raise StockError(f"Location {location} is not in factory {factory.code}.")
    kw = item_kwargs(item)
    is_reval = movement_type == T.REVALUATION
    qty = _qty(qty)
    if qty == 0 and not is_reval:
        raise StockError("A stock movement needs a quantity (BR-01).")
    if isinstance(item, Material) and item.kind == "fabric" and not is_reval and roll is None:
        raise StockError(f"Fabric ({item.name}) is stocked by roll; choose the roll.")
    if roll is not None:
        if not isinstance(item, Material) or roll.material_id != item.pk:
            raise StockError(f"Roll {roll.label_code} is not a roll of {item}.")

    method = company.valuation_method
    qty_only = is_quantity_only(item, location)
    if qty_only:
        if is_reval or (value is not None and Decimal(value) != 0) or (rate is not None and Decimal(rate) != 0):
            raise StockError("Work in progress is tracked by quantity here; its value sits in the lot's cost.")
        signed_value = ZERO
    elif is_reval:
        if value is None:
            raise StockError("A value adjustment needs a value.")
        signed_value = _money(value)
    elif qty > 0:
        if value is None:
            if rate is None:
                raise StockError("A receipt needs a rate or a value.")
            if isinstance(rate, float):
                raise StockError("Rate must be a Decimal.")
            value = Decimal(rate) * qty
        signed_value = _money(value)
        if signed_value < 0:
            raise StockError("A receipt cannot have a negative value.")
    else:
        out_qty = -qty
        mag = _money(value) if value is not None else _outbound_value(
            factory=factory, location=location, item=item, out_qty=out_qty, roll=roll, method=method
        )
        signed_value = -mag

    # ---- balances: Decimal arithmetic in Python + compare-and-set (SQLite would do SQL arithmetic in floats) ----
    bal, _ = StockBalance.objects.get_or_create(factory=factory, location=location, **kw)

    def no_stock(have):
        return InsufficientStock(f"Only {have.normalize():f} of {item} at {location}; cannot issue {(-qty).normalize():f}.")

    _apply(StockBalance, bal.pk, qty, signed_value, floor=qty < 0 and not company.allow_negative_stock, error=no_stock)
    if roll is not None:
        rb, _ = RollBalance.objects.get_or_create(roll=roll, location=location)

        def no_roll(have):
            return InsufficientStock(
                f"Roll {roll.label_code} has only {have.normalize():f} at {location}; "
                f"cannot issue {(-qty).normalize():f} (BR-02)."
            )

        _apply(RollBalance, rb.pk, qty, signed_value, floor=qty < 0, error=no_roll)

    return StockMovement.objects.create(
        factory=factory, location=location, roll=roll, movement_type=movement_type, qty=qty,
        value=signed_value, date=date, bundle=bundle, lot=lot, source_type=source._meta.label_lower if source is not None else "",
        source_id=source.pk if source is not None else None, voucher=voucher, notes=notes, created_by=user, **kw,
    )


@transaction.atomic
def reverse_movement(movement, *, user, date, source=None, voucher=None, notes="Reversal") -> StockMovement:
    """Post the exact opposite of a movement. Fails if the stock has since been used."""
    qty, value = -movement.qty, -movement.value
    kind = T.REVALUATION if movement.movement_type == T.REVALUATION else T.REVERSAL
    return post_movement(
        factory=movement.factory, location=movement.location, item=movement.item, qty=qty,
        movement_type=kind, date=date, user=user, source=source, voucher=voucher, roll=movement.roll,
        value=value if qty >= 0 or kind == T.REVALUATION else -value, notes=notes,
    )


def gl_values(movements):
    """Total movement value per GL stock-ledger key and factory, for building a source document's voucher.

    Returns {(factory_id, ledger_key): Decimal}.
    """
    out = {}
    for m in movements:
        key = (m.factory_id, stock_ledger_key(m.item))
        out[key] = out.get(key, ZERO) + m.value
    return out


@transaction.atomic
def create_roll(*, company, material, label_code=None, **fields) -> FabricRoll:
    from masters.services.codes import next_code

    roll = FabricRoll(company=company, material=material, label_code=label_code or next_code(company, "roll"), **fields)
    roll.full_clean(exclude=["supplier"] if not fields.get("supplier") else None)
    roll.save()
    return roll
