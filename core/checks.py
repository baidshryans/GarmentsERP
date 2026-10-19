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


def not_future(day, what: str) -> None:
    from django.utils import timezone

    if day is not None and day > timezone.localdate():
        raise BusinessRuleError(f"{what} cannot be in the future.")


def not_before(day, earlier, what: str, earlier_what: str) -> None:
    if day is not None and earlier is not None and day < earlier:
        raise BusinessRuleError(f"{what} cannot be dated before {earlier_what} ({earlier.day:02d} {earlier:%b %Y}).")


def not_negative(value, what: str) -> None:
    if value is not None and value < 0:
        raise BusinessRuleError(f"{what} cannot be negative.")


def counts_whole(item) -> bool:
    """Garments (SKUs) are counted in whole pieces; materials are not."""
    from masters.models import SKU

    return isinstance(item, SKU)
