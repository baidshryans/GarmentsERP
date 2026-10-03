from decimal import ROUND_HALF_UP, Decimal

from core.exceptions import BusinessRuleError
from sales.models import SaleSetting

TWO = Decimal("0.01")
THREE = Decimal("0.001")
ZERO = Decimal("0.00")


def r2(value) -> Decimal:
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


def line_amount(qty, rate, discount_pct) -> Decimal:
    return r2(Decimal(qty) * Decimal(rate) * (Decimal("100") - Decimal(discount_pct)) / 100)


def settings_for(company) -> SaleSetting:
    obj, _ = SaleSetting.objects.get_or_create(company=company)
    return obj


def check_decimal(value, what):
    if isinstance(value, bool) or isinstance(value, float) or not isinstance(value, (Decimal, int)):
        raise BusinessRuleError(f"{what} must be a Decimal, not {type(value).__name__}.")
    return Decimal(value)


def check_pieces(qty, what="Quantity") -> Decimal:
    """Garments are sold in whole pieces."""
    qty = check_decimal(qty, what)
    if qty <= 0:
        raise BusinessRuleError(f"{what} must be more than zero.")
    if qty != qty.to_integral_value():
        raise BusinessRuleError(f"{what} must be whole pieces.")
    return qty.quantize(THREE)


def check_discount(user, company, discount_pct):
    discount_pct = check_decimal(discount_pct, "Discount")
    if not 0 <= discount_pct <= 100:
        raise BusinessRuleError("Discount % must be between 0 and 100.")
    limit = settings_for(company).max_discount_pct
    if discount_pct > limit and not (user is not None and user.has_screen_perm("sales.discount", "edit")):
        raise BusinessRuleError(f"A discount of {discount_pct.normalize():f}% is above your limit of {limit.normalize():f}%.")
    return discount_pct
