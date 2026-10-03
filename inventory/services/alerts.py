"""Low-stock alerts (E6.3, INV-06): reorder levels per item, and one alert each time stock falls below the minimum.

An alert stays open until stock is back at or above the minimum; only then can the item alert again, so the owner is
told once per crossing and not on every check. Checking is a plain function run by `manage.py check_low_stock`
(cron) and by the "Check now" button. Delivery here is in the app; sending to WhatsApp needs the WhatsApp
integration, which is not built yet.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.exceptions import BusinessRuleError
from core.scoping import assert_factory_access
from inventory.models import ReorderLevel, StockAlert, StockBalance
from masters.models import Material, Style

THREE = Decimal("0.001")
STOCKROOMS = ("godown", "showroom", "dispatch")  # stock you could use or sell now: not on the cutting floor, in process or at a fabricator


def q3(value) -> Decimal:
    return Decimal(value or 0).quantize(THREE, rounding=ROUND_HALF_UP)


def stock_of(level) -> Decimal:
    """On hand for the level's item: in its factory, or across all factories when the level has none."""
    qs = StockBalance.objects.filter(location__loc_type__in=STOCKROOMS)
    if level.factory_id:
        qs = qs.filter(factory_id=level.factory_id)
    qs = qs.filter(material_id=level.material_id) if level.material_id else qs.filter(sku__style_id=level.style_id)
    return q3(qs.aggregate(q=Sum("qty"))["q"])


@transaction.atomic
def set_level(*, item, factory, min_qty, reorder_qty, max_qty, user) -> ReorderLevel:
    """Create or change the level of one item (per factory, or for all factories when factory is None)."""
    if factory is not None:
        assert_factory_access(user, factory)
    elif user.allowed_factory_ids() is not None:
        raise BusinessRuleError("A level for all factories can be set only by a user who may see every factory.")
    for what, value in (("Minimum", min_qty), ("Reorder quantity", reorder_qty), ("Maximum", max_qty)):
        if isinstance(value, float) or not isinstance(value, (Decimal, int)):
            raise BusinessRuleError(f"{what} must be a Decimal.")
        if value < 0:
            raise BusinessRuleError(f"{what} cannot be negative.")
    if max_qty and max_qty < min_qty:
        raise BusinessRuleError("The maximum cannot be below the minimum.")
    kw = {"material": item} if isinstance(item, Material) else {"style": item}
    if not isinstance(item, (Material, Style)):
        raise BusinessRuleError("Levels are set for a material or a style.")
    level = ReorderLevel.objects.filter(factory=factory, **kw).first() or ReorderLevel(factory=factory, **kw)
    level.min_qty, level.reorder_qty, level.max_qty = q3(min_qty), q3(reorder_qty), q3(max_qty)
    level.save()
    return level


@transaction.atomic
def delete_level(level, *, user):
    if level.factory_id:
        assert_factory_access(user, level.factory)
    level.delete()


@transaction.atomic
def check_low_stock(company, *, now=None) -> list:
    """Raise an alert for every item below its minimum that has none open, and close alerts for items that recovered.
    Safe to run as often as you like. Returns the alerts raised by this run."""
    now = now or timezone.now()
    raised = []
    for level in ReorderLevel.objects.select_related("factory", "material", "style"):
        if level.min_qty <= 0:
            continue
        qty = stock_of(level)
        open_alert = StockAlert.objects.filter(
            company=company, factory=level.factory, material=level.material, style=level.style, cleared_at__isnull=True).first()
        if qty < level.min_qty:
            if open_alert is None:
                raised.append(StockAlert.objects.create(
                    company=company, factory=level.factory, material=level.material, style=level.style,
                    min_qty=level.min_qty, reorder_qty=level.reorder_qty, qty_at_alert=qty))
        elif open_alert is not None:
            open_alert.cleared_at = now
            open_alert.save(update_fields=["cleared_at"])
    # a level that was removed no longer holds an alert open
    for alert in StockAlert.objects.filter(company=company, cleared_at__isnull=True):
        if not ReorderLevel.objects.filter(factory=alert.factory, material=alert.material, style=alert.style).exists():
            alert.cleared_at = now
            alert.save(update_fields=["cleared_at"])
    return raised


@transaction.atomic
def acknowledge(alert, *, user) -> StockAlert:
    alert = StockAlert.objects.get(pk=alert.pk)
    if alert.factory_id:
        assert_factory_access(user, alert.factory)
    if alert.acknowledged_at is None:
        alert.acknowledged_by, alert.acknowledged_at = user, timezone.now()
        alert.save(update_fields=["acknowledged_by", "acknowledged_at"])
    return alert


def alert_rows(user):
    """Open alerts with today's stock beside the level, for the alerts screen."""
    rows = []
    for a in StockAlert.visible_to(user).filter(cleared_at__isnull=True).select_related("factory", "material__unit", "style"):
        level = ReorderLevel.objects.filter(factory=a.factory, material=a.material, style=a.style).first()
        rows.append({"alert": a, "now": stock_of(level) if level else None, "unit": a.material.unit if a.material_id else "pcs"})
    return rows


def level_rows(user):
    ids = user.allowed_factory_ids()
    qs = ReorderLevel.objects.select_related("factory", "material__unit", "style")
    if ids is not None:
        qs = qs.filter(factory_id__in=ids)
    return [{"level": l, "stock": stock_of(l), "low": l.min_qty > 0 and stock_of(l) < l.min_qty,
             "unit": l.material.unit if l.material_id else "pcs"} for l in qs.order_by("material__name", "style__style_no", "factory__code")]
