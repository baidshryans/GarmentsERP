"""Request-free catalog PDF building, callable from a view or a background task."""
from django.utils import timezone


def build_catalog_pdf_bytes(params, retail_id, fmt):
    """Build a catalog PDF from plain params (a dict) and a retail id.

    Returns (pdf_bytes, filename). No request object involved so it can run in
    a worker. ``params.get(key)`` mirrors ``request.GET.get(key)``.
    """
    from mastersconfig.models import RetailMaster
    from inventory.catalog_pricing import compute_design_price
    from inventory.catalog_pdf import build_catalog_pdf
    from inventory.views import (
        _apply_catalog_filters, _base_design_qs, _resolve_pricelists, _tier_label,
    )

    if fmt not in ("summary", "detailed", "quotation"):
        fmt = "summary"

    retail = RetailMaster.objects.filter(pk=retail_id).first() if retail_id else None
    qs = _apply_catalog_filters(_base_design_qs(retail), params.get)

    tier = params.get("tier", "retail")
    b2b_pl = retail_pl = None
    ledger_id = params.get("ledger")
    if ledger_id:
        from contacts.models import Ledger
        ldg = Ledger.objects.filter(pk=ledger_id).first()
        if ldg:
            if tier == "b2b":
                b2b_pl = ldg.b2b_pricelist
            else:
                retail_pl = ldg.retail_discount_pricelist
    b2b_pl2, retail_pl2 = _resolve_pricelists(tier, params.get("pricelist"))
    b2b_pl, retail_pl = (b2b_pl2 or b2b_pl), (retail_pl2 or retail_pl)

    designs = list(qs.order_by("design_no", "id")[:300])
    rows = []
    for d in designs:
        price = compute_design_price(d, b2b_pricelist=b2b_pl, retail_pricelist=retail_pl)
        cover = next((im for im in d.images.all() if im.is_primary), None) or next(iter(d.images.all()), None)
        img_path = None
        if cover:
            try:
                img_path = cover.image.path
            except Exception:
                img_path = None
        rows.append({
            "design_no": d.design_no + (f"-{d.variation_suffix}" if d.variation_suffix else ""),
            "item_name": d.item.item_name if d.item else "",
            "gw": float(d.gw or 0), "nw": float(d.nw or 0),
            "in_stock_count": sum(1 for b in d.barcodes.all() if b.stk_status),
            "image_path": img_path,
            "price": price,
        })

    meta = {
        "title": "Quotation" if fmt == "quotation" else "Catalog",
        "tier_label": _tier_label(b2b_pl, retail_pl),
        "date": timezone.localtime().strftime("%d %b %Y"),
        "count": len(rows),
    }
    return build_catalog_pdf(fmt, rows, meta), f"catalog_{fmt}.pdf"
