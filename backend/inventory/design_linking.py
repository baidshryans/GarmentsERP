"""
Link barcodes to their Design.

A design's identity is **(item, design_no)** â€” company-global, NOT scoped by
retail. A bracelet `/1` and a ring `/1` are different designs; the same
item + design_no in any branch is the same design.

This helper is the single source of truth, reused by:
  - the `seed_designs` management command (backfill / repair existing barcodes)
  - `BarCodeMainSerializer` create/update (auto-link new & edited barcodes)
"""

from django.db import transaction

from inventory.models import BarcodeMain, BarcodeDetails, DesignMain, DesignDetails


def _build_design_details(design, barcode):
    """Create DesignDetails for a freshly-created design from the barcode's
    BarcodeDetails (stone / gold lines). metal_purity is PROTECT (non-null)."""
    for bd in BarcodeDetails.objects.filter(barcode=barcode).select_related("item", "purity", "packet"):
        metal_purity = bd.purity or barcode.purity
        if metal_purity is None:
            continue
        DesignDetails.objects.create(
            design_no=design,
            sub_item=bd.item,
            metal_purity=metal_purity,
            packet=bd.packet,
            pcs=bd.pcs or 0,
            ct=bd.ct or 0,
            rate=int(bd.rate or 0),
            amt=int(bd.amt or 0),
        )


def get_or_create_design_for_barcode(barcode):
    """Return the DesignMain for this barcode, matching by (item, design_no) only
    â€” never retail. Creates the design (and its DesignDetails) if missing.
    Returns None when the barcode has no item or a blank design_code."""
    if barcode.item_id is None:
        return None
    code = (barcode.design_code or "").strip()
    if not code:
        return None

    with transaction.atomic():
        design, created = DesignMain.objects.get_or_create(
            item=barcode.item,
            design_no=code,
            defaults={
                "item_desc": (barcode.item.item_name if barcode.item else "")[:100],
                "pcs": barcode.pcs or 1,
                "gw": barcode.gw or 0,
                "nw": barcode.nw or 0,
                "making": barcode.making_val or 0,
                "making_type": barcode.making_type or "",
                "kr_code": barcode.kr_code,
                "making_rate": 0,
                "retail": barcode.retail,   # informational only â€” not part of identity
            },
        )
        if created:
            _build_design_details(design, barcode)
    return design

