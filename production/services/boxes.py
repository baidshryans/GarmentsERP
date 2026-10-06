"""Boxes at packing. The pieces per box are a setting: on the style, or the company's when the style has none.
Packing works out how many boxes the packed pieces fill, one SKU to a box, with a short last box for what is left
over. Stock stays in pieces; a box is only a count and a label.
"""
from dataclasses import dataclass

from masters.services.styles import pieces_per_box


@dataclass
class BoxLine:
    sku: object
    pieces: int
    per_box: int
    full_boxes: int
    short_box_qty: int      # pieces in the last, part-filled box; 0 when the pieces fill whole boxes

    @property
    def boxes(self):
        return self.full_boxes + (1 if self.short_box_qty else 0)


def plan(qty_by_sku, company) -> list:
    """Boxes for {SKU: pieces}. SKUs whose style (and the company) has no pieces per box are left out."""
    lines = []
    for sku, pieces in qty_by_sku.items():
        per = pieces_per_box(sku.style, company)
        if per > 0 and pieces > 0:
            lines.append(BoxLine(sku, pieces, per, pieces // per, pieces % per))
    return sorted(lines, key=lambda l: (l.sku.style.style_no, str(l.sku.colour), l.sku.size.sort_order))


def plan_for_bundles(bundles, company) -> list:
    qty = {}
    for b in bundles:
        qty[b.sku] = qty.get(b.sku, 0) + b.qty
    return plan(qty, company)


def describe(lines) -> str:
    """'8 boxes of 12 and 1 short box of 4', for the message after packing. Empty when there are no boxes."""
    by_size = {}
    for l in lines:
        by_size[l.per_box] = by_size.get(l.per_box, 0) + l.full_boxes
    parts = [f"{n} box{'es' if n != 1 else ''} of {per}" for per, n in sorted(by_size.items()) if n]
    short = [l.short_box_qty for l in lines if l.short_box_qty]
    if len(short) == 1:
        parts.append(f"1 short box of {short[0]}")
    elif short:
        parts.append(f"{len(short)} short boxes ({', '.join(str(n) for n in short)} pieces)")
    return " and ".join(parts)


def labels_for(entry) -> list:
    """One label per box of a pack entry: [{'sku', 'qty', 'no', 'total', 'short', 'entry'}], numbered per SKU."""
    out = []
    for line in entry.lines.select_related("sku__style", "sku__colour", "sku__size"):
        total = line.boxes
        for no in range(1, line.full_boxes + 1):
            out.append({"sku": line.sku, "qty": line.pieces_per_box, "no": no, "total": total, "short": False, "entry": entry})
        if line.short_box_qty:
            out.append({"sku": line.sku, "qty": line.short_box_qty, "no": total, "total": total, "short": True, "entry": entry})
    return out
