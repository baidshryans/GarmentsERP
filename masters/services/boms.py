"""Versioned material list of a style (E2.2, BR-18).

The list holds accessories and packing materials, each used in one process: the pieces coming from the step before
are the other input of that process. Fabric is not on it; the pieces a fabric should give are estimated when it is
issued to cutting.

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
THREE = Decimal("0.001")
# where a material is used when its line names no process
DEFAULT_PROCESS_KIND = {"trim": "stitching", "packing": "packing"}


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
    process: object | None = None                 # blank = by the kind of material


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
            version=version, material=spec.material, process=spec.process, qty_per_piece=spec.qty_per_piece,
            wastage_pct=spec.wastage_pct)
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
    lines, charges = list(lines), list(charges)
    if not lines and not charges:
        raise BusinessRuleError("Enter at least one material or one fixed charge.")
    materials = [l.material.pk for l in lines]
    if len(materials) != len(set(materials)):
        raise BusinessRuleError("A material can appear only once in the list.")
    sizes = set(style.style_sizes.values_list("size_id", flat=True))
    for l in lines:
        if l.material.kind == "fabric":
            raise BusinessRuleError(
                f"{l.material.name} is fabric and is not listed here: enter the pieces you expect when you issue "
                f"the fabric to cutting.")
        if l.process is not None and l.process.kind == "cutting":
            raise BusinessRuleError(
                f"{l.material.name}: materials are issued when bundles enter a process, so choose a process after cutting.")
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


def used_in(line, process) -> bool:
    """Is this line's material used in `process`? By the process the line names, or by the kind of material when
    it names none. Fabric lines on old versions are never used: fabric is issued to cutting roll by roll."""
    if line.material.kind == "fabric":
        return False
    if line.process_id:
        return line.process_id == process.pk
    return DEFAULT_PROCESS_KIND.get(line.material.kind) == process.kind


def needs(version, process, pieces_by_size) -> dict:
    """Materials `process` needs for these pieces ({Size: pieces}), wastage included: {Material: quantity}."""
    out = {}
    if version is None:
        return out
    for line in version.lines.select_related("material", "material__unit").prefetch_related("size_overrides"):
        if not used_in(line, process):
            continue
        overrides = {o.size_id: o.qty_per_piece for o in line.size_overrides.all()}
        total = Decimal("0")
        for size, n in pieces_by_size.items():
            total += overrides.get(size.pk, line.qty_per_piece) * (1 + line.wastage_pct / 100) * n
        total = total.quantize(THREE)
        if total > 0:
            out[line.material] = out.get(line.material, Decimal("0")) + total
    return out


def unused_lines(version, processes) -> list:
    """Lines whose process is not among `processes` (a lot's route): their material will never be issued."""
    if version is None:
        return []
    return [l for l in version.lines.select_related("material", "process")
            if l.material.kind != "fabric" and not any(used_in(l, p) for p in processes)]
