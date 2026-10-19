"""Logical checks every service makes by default (owner, 19 Oct 2026), with plain messages naming the field.

Garment pieces are whole numbers everywhere. Materials keep decimals: fabric is weighed or measured, trims are
issued with wastage (240 pieces at 2% is 244.8 zips) and thread is used by the cone."""
from decimal import Decimal

from core.exceptions import BusinessRuleError


def whole(value, what: str) -> int:
    """`value` as an int, refused unless it is a whole number (an int, or a Decimal with nothing after the point)."""
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)) or Decimal(value) != Decimal(value).to_integral_value():
        raise BusinessRuleError(f"{what} must be a whole number of pieces.")
    return int(value)


def counts_whole(item) -> bool:
    """Garments (SKUs) are counted in whole pieces; materials are not."""
    from masters.models import SKU

    return isinstance(item, SKU)
