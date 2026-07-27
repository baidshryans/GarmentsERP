"""
Catalog pricing — compute a live price for a Design, replicating the ERP's
sale-time formula (which today lives only in the frontend).

Price = gold value + making + stones, then GST on top.

  gold value : fine_wt × pure_gold_rate
               fine_wt = net_weight × effective_tunch / 100
               effective_tunch = PurityMaster.gw_per (+ B2B tunch markup)
               pure_gold_rate = latest GoldRates for that purity, converted back
               to a 100%-pure rate (GoldRates is stored per purity)
  making     : B2B  → the matched B2BPricelistMaking rule, resolved by
                      mastersconfig.b2b_pricing.resolve_b2b_making
                      (per_gram / val / tunch / per_nw, with a per-rule minimum
                       making charge expressed in grams)
               else → the design's stored making, less retail making_discount_pct
  stones     : stored design-detail amounts, less retail diamond_discount_pct
               (B2B per-packet overrides need a packet link, which design
                details don't carry, so they don't apply at design level)
  gst        : CATALOG_GST_PCT on (gold + making + stones)

Tier is implied by which pricelist is passed:
  - b2b_pricelist set    → B2B (wholesale) pricing
  - retail_pricelist set → retail pricing with discounts
  - neither              → plain retail (design's own making, no discount)

Limitations are intentional for v1 and documented inline; design details are
thinner than barcode details (no packet FK, no per-line grams), so stones rely
on stored amounts and gold weight uses the design net weight.
"""

from decimal import Decimal, ROUND_HALF_UP

from goldrates.models import GoldRates
from mastersconfig.b2b_pricing import (
    find_b2b_making_rule, pure_rate_from_purity_rate, resolve_b2b_making,
)

CATALOG_GST_PCT = Decimal("3")   # jewellery GST (1.5 CGST + 1.5 SGST)


def _D(v):
    return Decimal(str(v)) if v not in (None, "") else Decimal(0)


def _money(v):
    return float(Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _latest_gold_rate(purity):
    """Latest gold rate for a purity (selling_rate), falling back to the most
    recent rate of any purity if that purity has none."""
    gr = GoldRates.objects.filter(purity=purity).order_by("-date1").first()
    if gr is None:
        gr = GoldRates.objects.order_by("-date1").first()
    if gr is None:
        return Decimal(0)
    return _D(gr.selling_rate if gr.selling_rate else gr.rate)


def _is_gold(detail):
    return (detail.sub_item.uom or "").lower() == "gm"


def _is_stone(detail):
    return (detail.sub_item.item_type or "").upper() == "S" or (detail.sub_item.uom or "").lower() == "ct"


def compute_design_price(design, *, b2b_pricelist=None, retail_pricelist=None,
                         line_overrides=None):
    """Return a full price breakdown dict for a Design.

    line_overrides — optional {design_detail_id: {"rate": Decimal-able,
    "packet": Packet|None}} used by the catalog stone-swap simulator. An
    overridden line keeps its own pcs/ct but is repriced at the given rate
    (amt = rate × ct, falling back to rate × pcs like stored lines); when a
    packet is given the component line is labelled after it. Discounts and
    GST apply unchanged.
    """
    line_overrides = line_overrides or {}
    details = list(design.designdetails_set.select_related("sub_item", "metal_purity").all())

    # ── Determine the design's gold purity (first metal/gram line) ───────────
    gold_purity = None
    for d in details:
        if _is_gold(d) and d.metal_purity_id:
            gold_purity = d.metal_purity
            break
    if gold_purity is None:
        for d in details:
            if d.metal_purity_id:
                gold_purity = d.metal_purity
                break

    # Retail discount rule (per purity) resolved once.
    retail_rule = None
    if retail_pricelist is not None and gold_purity is not None:
        retail_rule = retail_pricelist.rules.filter(purity=gold_purity).first()
    making_disc = _D(retail_rule.making_discount_pct) if retail_rule else Decimal(0)
    diamond_disc = _D(retail_rule.diamond_discount_pct) if retail_rule else Decimal(0)

    component_lines = []

    # ── Gold value ────────────────────────────────────────────────────────────
    gold_weight = _D(design.nw) or _D(design.gw)
    gold_value = Decimal(0)
    gold_rate = Decimal(0)
    eff_tunch = Decimal(0)
    # One resolution drives both the gold line and the making line.  With no B2B
    # rule the helper returns the plain purity figures, so this path is shared.
    base_pct = _D(gold_purity.gw_per) if gold_purity is not None else Decimal(0)
    purity_rate = _latest_gold_rate(gold_purity) if gold_purity is not None else Decimal(0)
    # GoldRates is keyed by PurityMaster, so `purity_rate` is already the rate AT
    # that purity — convert back to a 100%-pure rate before applying any tunch.
    pure_rate = pure_rate_from_purity_rate(purity_rate, base_pct)
    b2b_rule = find_b2b_making_rule(b2b_pricelist, purity=gold_purity, item=design.item)
    b2b_res = resolve_b2b_making(
        b2b_rule, weight=gold_weight, base_purity_pct=base_pct, pure_gold_rate=pure_rate,
    )

    if gold_purity is not None and gold_weight > 0:
        eff_tunch = b2b_res["eff_tunch_pct"]
        gold_rate = b2b_res["gold_rate"]
        gold_value = b2b_res["gold_value"]
        _pn = (gold_purity.purity or "").strip()
        gold_label = f"Gold {_pn}K" if _pn.replace(".", "", 1).isdigit() else (f"Gold {_pn}".strip() or "Gold")
        component_lines.append({
            "kind": "gold",
            "name": gold_label,
            "weight_gm": float(gold_weight),
            "tunch": float(eff_tunch),
            "rate": _money(gold_rate),
            "amount": _money(gold_value),
        })

    # ── Stones / other components ──────────────────────────────────────────────
    stone_total = Decimal(0)
    for d in details:
        if _is_gold(d):
            continue
        override = line_overrides.get(d.id)
        name = d.sub_item.item_name
        if override is not None:
            qty = _D(d.ct) or _D(d.pcs)
            amt = _D(override.get("rate")) * qty
            packet = override.get("packet")
            if packet is not None:
                stone_name = packet.stone_item_id.item_name if packet.stone_item_id else name
                name = f"{stone_name} ({packet.pckt_no})"
        else:
            amt = _D(d.amt)
            if amt == 0:
                uom = (d.sub_item.uom or "").lower()
                qty = _D(d.ct) if uom == "ct" else _D(d.pcs)
                amt = _D(d.rate) * qty
        if diamond_disc and _is_stone(d):
            amt = amt * (Decimal(100) - diamond_disc) / Decimal(100)
        stone_total += amt
        component_lines.append({
            "kind": "stone" if _is_stone(d) else "other",
            "name": name,
            "pcs": d.pcs,
            "ct": float(_D(d.ct)),
            "amount": _money(amt),
            "detail_id": d.id,
            "overridden": override is not None,
        })

    # ── Making ─────────────────────────────────────────────────────────────────
    if b2b_res["making_value"] is not None:
        # A 'tunch' rule returns 0 here on purpose — it is charged via the gold rate.
        making_value = b2b_res["making_value"]
    else:
        making_value = _D(design.making)
        if making_value == 0 and _D(design.making_rate) > 0:
            making_value = _D(design.making_rate) * _D(design.gw)
        if making_disc:
            making_value = making_value * (Decimal(100) - making_disc) / Decimal(100)

    component_lines.append({"kind": "making", "name": "Making", "amount": _money(making_value)})

    # ── Totals ─────────────────────────────────────────────────────────────────
    taxable = gold_value + making_value + stone_total
    gst = taxable * CATALOG_GST_PCT / Decimal(100)
    total = taxable + gst

    return {
        "gold_purity": gold_purity.purity if gold_purity else None,
        "gold_weight": float(gold_weight),
        "gold_rate": _money(gold_rate),
        "gold_value": _money(gold_value),
        "making_value": _money(making_value),
        "stone_total": _money(stone_total),
        "taxable": _money(taxable),
        "gst_pct": float(CATALOG_GST_PCT),
        "gst": _money(gst),
        "total_price": _money(total),
        "component_lines": component_lines,
    }
