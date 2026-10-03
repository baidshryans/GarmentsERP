"""Versioned BOM (E2.2, BR-18).

A version that no lot has used yet can be edited in place. Once production references it,
saving a change creates a new version and old lots keep the one they were cut with.
`register_usage_check` lets the production app say "this version is used" later.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from core.exceptions import BusinessRuleError
from masters.models import BomCharge, BomLine, BomLineSize, BomVersion

_USAGE_CHECKS = []


def register_usage_check(fn):
    """fn(version) -> bool; True when something (a lot) already uses this BOM version."""
    _USAGE_CHECKS.append(fn)


def is_version_used(version) -> bool:
    return any(check(version) for check in _USAGE_CHECKS)


@dataclass
class BomLineSpec:
    material: object
    qty_per_piece: Decimal
    wastage_pct: Decimal = Decimal("0")
    size_qty: dict = field(default_factory=dict)  # {Size: Decimal} overrides


@dataclass
class BomChargeSpec:
    description: str
    amount_per_piece: Decimal
    process: object | None = None


def current_version(style):
    return style.bom_versions.filter(is_current=True).first()


def _write(version, lines, charges):
    for spec in lines:
        if spec.qty_per_piece is None or spec.qty_per_piece <= 0:
            raise BusinessRuleError(f"Consumption of {spec.material.name} must be more than zero.")
        line = BomLine.objects.create(
            version=version, material=spec.material, qty_per_piece=spec.qty_per_piece, wastage_pct=spec.wastage_pct
        )
        for size, qty in spec.size_qty.items():
            if qty <= 0:
                raise BusinessRuleError(f"Size {size.code} consumption must be more than zero.")
            BomLineSize.objects.create(line=line, size=size, qty_per_piece=qty)
    for c in charges:
        BomCharge.objects.create(
            version=version, description=c.description, process=c.process, amount_per_piece=c.amount_per_piece
        )


@transaction.atomic
def save_bom(style, *, lines, charges=(), user=None, notes=""):
    """Returns (version, created_new_version). Never edits a version that lots already use."""
    lines = list(lines)
    if not lines:
        raise BusinessRuleError("A BOM needs at least one material line.")
    materials = [l.material.pk for l in lines]
    if len(materials) != len(set(materials)):
        raise BusinessRuleError("A material can appear only once in a BOM.")
    sizes = set(style.style_sizes.values_list("size_id", flat=True))
    for l in lines:
        for size in l.size_qty:
            if size.pk not in sizes:
                raise BusinessRuleError(f"Size {size.code} is not one of this style's sizes.")

    current = current_version(style)
    if current is not None and not is_version_used(current):
        current.lines.all().delete()
        current.charges.all().delete()
        current.notes = notes or current.notes
        current.save(update_fields=["notes"])
        _write(current, lines, charges)
        return current, False

    next_no = (style.bom_versions.order_by("-version_no").values_list("version_no", flat=True).first() or 0) + 1
    if current is not None:
        current.is_current = False
        current.save(update_fields=["is_current"])
    version = BomVersion.objects.create(
        style=style, version_no=next_no, is_current=True, notes=notes, created_by=user
    )
    _write(version, lines, charges)
    return version, current is not None


def consumption_for(version, size):
    """Per-piece consumption of each material for one size, size overrides applied."""
    result = []
    for line in version.lines.select_related("material").prefetch_related("size_overrides"):
        qty = line.qty_per_piece
        for o in line.size_overrides.all():
            if o.size_id == size.pk:
                qty = o.qty_per_piece
        result.append((line.material, qty, line.wastage_pct))
    return result
