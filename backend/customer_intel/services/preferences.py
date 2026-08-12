"""
Per-customer buying-preference rollups.

Design rule: **one grouped query per dimension across a whole batch of ledgers**,
never one query per customer. Every function here takes a list of ledger ids and
returns {ledger_id: [...]}, so the nightly rebuild stays at a constant number of
queries regardless of customer count. `tests/test_snapshot.py` enforces this with
assertNumQueries.

Join notes (these are easy to get wrong):
  * Filter through `billno__retail`, NOT `SalesVouItem.retail` — the item-level
    retail column is nullable; the voucher header is authoritative.
  * Purity must come from `barcode__purity` (FK to PurityMaster).
    `SalesVouItem.purity` is a bare IntegerField, not a foreign key — reading it
    as a purity id yields garbage.
  * `SalesVouItemDetails.billno` is nullable; rows carrying only `main_item`
    need a second pass joined via `main_item__billno`.
"""

from collections import defaultdict

from django.db.models import Count, Sum

from sales.models import SalesVouItem, SalesVouItemDetails

# Preference lists are truncated to this many entries before being stored.
TOP_N = 10
TOP_N_STONE = 5


def _f(value):
    """Decimal/None → float, for JSON storage."""
    return float(value or 0)


def _rank(rows, key_fields, label_fn, top_n=TOP_N):
    """
    Turn grouped rows into {ledger_id: [{id,label,amount,pcs,gw,share}, ...]}.

    `share` is the row's amount as a fraction of that customer's total across
    the dimension, so it stays comparable between customers of different sizes.
    """
    by_ledger = defaultdict(list)
    for row in rows:
        by_ledger[row["billno__ldgr_id"]].append(row)

    out = {}
    for ledger_id, items in by_ledger.items():
        total = sum(_f(i.get("amt")) for i in items)
        entries = []
        for i in items:
            amount = _f(i.get("amt"))
            entries.append({
                "id": i.get(key_fields[0]),
                "label": label_fn(i),
                "amount": round(amount, 2),
                "pcs": _f(i.get("pcs")),
                "gw": round(_f(i.get("gw")), 3),
                "count": i.get("n", 0),
                "share": round(amount / total, 4) if total else 0.0,
            })
        entries.sort(key=lambda e: e["amount"], reverse=True)
        out[ledger_id] = entries[:top_n]
    return out


def _base_items(retail_id, ledger_ids, window_start=None):
    """Sold metal/making lines for a batch of customers, returns excluded."""
    qs = SalesVouItem.objects.filter(
        billno__retail_id=retail_id,
        billno__ldgr_id__in=ledger_ids,
        ret_status=False,
    )
    if window_start:
        qs = qs.filter(billno__date1__gte=window_start)
    return qs


def category_prefs(retail_id, ledger_ids, window_start=None):
    """
    What kinds of jewellery this customer buys.

    Prefers the coarse `Item.grp` (ItemGroupMaster) bucket, but falls back to the
    item itself when the group link is missing — which is the norm rather than
    the exception: in the live database every row in `item_master` has a null
    `grp_id`, while `item_name` carries the real signal ("Lab Diamond Ladies
    Ring", "Gold Mangalsutra"). Each entry records which level it came from so
    the UI can label it truthfully.
    """
    rows = (
        _base_items(retail_id, ledger_ids, window_start)
        .exclude(item__isnull=True)
        .values(
            "billno__ldgr_id", "item_id", "item__item_name", "item__short_code",
            "item__grp_id", "item__grp__item_group_name",
        )
        .annotate(amt=Sum("amount"), pcs=Sum("pcs"), gw=Sum("gw"), n=Count("id"))
        .order_by()
    )

    # Roll up to group level where a group exists, item level where it doesn't.
    merged = defaultdict(lambda: defaultdict(
        lambda: {"amt": 0.0, "pcs": 0.0, "gw": 0.0, "n": 0, "label": "", "level": ""}
    ))
    for row in rows:
        ledger_id = row["billno__ldgr_id"]
        if row.get("item__grp_id"):
            key = ("group", row["item__grp_id"])
            label = row.get("item__grp__item_group_name") or "Uncategorised"
        else:
            key = ("item", row["item_id"])
            label = (row.get("item__item_name")
                     or row.get("item__short_code") or "Uncategorised")
        bucket = merged[ledger_id][key]
        bucket["amt"] += _f(row.get("amt"))
        bucket["pcs"] += _f(row.get("pcs"))
        bucket["gw"] += _f(row.get("gw"))
        bucket["n"] += row.get("n", 0)
        bucket["label"] = label
        bucket["level"] = key[0]

    out = {}
    for ledger_id, buckets in merged.items():
        total = sum(b["amt"] for b in buckets.values())
        entries = [{
            "id": key[1],
            "level": b["level"],
            "label": b["label"],
            "amount": round(b["amt"], 2),
            "pcs": b["pcs"],
            "gw": round(b["gw"], 3),
            "count": b["n"],
            "share": round(b["amt"] / total, 4) if total else 0.0,
        } for key, b in buckets.items()]
        entries.sort(key=lambda e: e["amount"], reverse=True)
        out[ledger_id] = entries[:TOP_N]
    return out


def purity_prefs(retail_id, ledger_ids, window_start=None):
    """Which metal purities (22kt, 18kt, …) — always via BarcodeMain.purity."""
    rows = (
        _base_items(retail_id, ledger_ids, window_start)
        .exclude(barcode__purity__isnull=True)
        .values("billno__ldgr_id", "barcode__purity_id", "barcode__purity__purity")
        .annotate(amt=Sum("amount"), pcs=Sum("pcs"), gw=Sum("gw"), n=Count("id"))
        .order_by()
    )
    return _rank(
        rows,
        ["barcode__purity_id"],
        lambda r: str(r.get("barcode__purity__purity") or "").strip() or "Unknown",
    )


def metal_color_prefs(retail_id, ledger_ids, window_start=None):
    """Yellow / white / rose preference, where the barcode recorded it."""
    rows = (
        _base_items(retail_id, ledger_ids, window_start)
        .exclude(barcode__metal_color__isnull=True)
        .exclude(barcode__metal_color="")
        .values("billno__ldgr_id", "barcode__metal_color")
        .annotate(amt=Sum("amount"), pcs=Sum("pcs"), gw=Sum("gw"), n=Count("id"))
        .order_by()
    )
    by_ledger = defaultdict(list)
    for row in rows:
        by_ledger[row["billno__ldgr_id"]].append(row)

    out = {}
    for ledger_id, items in by_ledger.items():
        total = sum(_f(i["amt"]) for i in items)
        entries = [{
            "id": None,
            "label": i["barcode__metal_color"],
            "amount": round(_f(i["amt"]), 2),
            "pcs": _f(i["pcs"]),
            "gw": round(_f(i["gw"]), 3),
            "count": i["n"],
            "share": round(_f(i["amt"]) / total, 4) if total else 0.0,
        } for i in items]
        entries.sort(key=lambda e: e["amount"], reverse=True)
        out[ledger_id] = entries[:TOP_N]
    return out


def design_prefs(retail_id, ledger_ids, window_start=None):
    """
    Which designs they gravitate to. Falls back to the `design_code` string when
    the BarcodeMain.design FK was never backfilled for that row.
    """
    rows = (
        _base_items(retail_id, ledger_ids, window_start)
        .values(
            "billno__ldgr_id",
            "barcode__design_id",
            "barcode__design__design_no",
            "barcode__design__item_desc",
            "barcode__design_code",
        )
        .annotate(amt=Sum("amount"), pcs=Sum("pcs"), gw=Sum("gw"), n=Count("id"))
        .order_by()
    )
    rows = [r for r in rows if r.get("barcode__design_id") or r.get("barcode__design_code")]

    def label(r):
        no = r.get("barcode__design__design_no") or r.get("barcode__design_code") or "?"
        desc = r.get("barcode__design__item_desc")
        return f"{no} — {desc}" if desc else str(no)

    return _rank(rows, ["barcode__design_id"], label)


def stone_prefs(retail_id, ledger_ids, window_start=None):
    """
    Diamond/stone attribute preferences via SalesVouItemDetails → Packet.

    Two passes because `SalesVouItemDetails.billno` is nullable — some rows only
    carry `main_item`, and joining via `main_item__billno` picks those up.
    Merged on the way out.
    """
    dims = {
        "shape": "packet__shape__shape_name",
        "clarity": "packet__clarity",
        "color": "packet__color__color_name",
        "cut": "packet__cut",
        "group": "packet__packet_group__packet_group_name",
    }

    # {ledger_id: {dim: {label: {"ct":x, "amount":y, "count":n}}}}
    acc = defaultdict(lambda: defaultdict(lambda: defaultdict(
        lambda: {"ct": 0.0, "amount": 0.0, "count": 0}
    )))
    solitaire = defaultdict(lambda: {"count": 0, "ct": 0.0})

    for ledger_path, extra_filter in (
        ("billno__ldgr_id", {"billno__retail_id": retail_id, "billno__ldgr_id__in": ledger_ids}),
        ("main_item__billno__ldgr_id", {
            "billno__isnull": True,
            "main_item__billno__retail_id": retail_id,
            "main_item__billno__ldgr_id__in": ledger_ids,
        }),
    ):
        qs = SalesVouItemDetails.objects.filter(packet__isnull=False, **extra_filter)
        if window_start:
            date_path = ("billno__date1__gte" if ledger_path == "billno__ldgr_id"
                         else "main_item__billno__date1__gte")
            qs = qs.filter(**{date_path: window_start})

        rows = (
            qs.values(ledger_path, "packet__is_solitaire", *dims.values())
            .annotate(ct=Sum("ct"), amt=Sum("amount"), n=Count("id"))
            .order_by()
        )
        for row in rows:
            ledger_id = row[ledger_path]
            if ledger_id is None:
                continue
            for dim, path in dims.items():
                label = row.get(path)
                if not label:
                    continue
                bucket = acc[ledger_id][dim][str(label).strip()]
                bucket["ct"] += _f(row.get("ct"))
                bucket["amount"] += _f(row.get("amt"))
                bucket["count"] += row.get("n", 0)
            if row.get("packet__is_solitaire"):
                solitaire[ledger_id]["count"] += row.get("n", 0)
                solitaire[ledger_id]["ct"] += _f(row.get("ct"))

    out = {}
    for ledger_id, dim_map in acc.items():
        result = {}
        for dim, labels in dim_map.items():
            total = sum(v["amount"] for v in labels.values())
            entries = [{
                "label": label,
                "ct": round(v["ct"], 3),
                "amount": round(v["amount"], 2),
                "count": v["count"],
                "share": round(v["amount"] / total, 4) if total else 0.0,
            } for label, v in labels.items()]
            entries.sort(key=lambda e: e["amount"], reverse=True)
            result[dim] = entries[:TOP_N_STONE]
        if ledger_id in solitaire:
            result["solitaire"] = {
                "count": solitaire[ledger_id]["count"],
                "ct": round(solitaire[ledger_id]["ct"], 3),
            }
        out[ledger_id] = result
    return out


def build_all(retail_id, ledger_ids, window_start=None):
    """
    All preference dimensions for a batch, as
    {ledger_id: {category, purity, metal_color, design, stone}}.

    Costs a fixed 6 queries regardless of how many ledgers are in the batch.
    """
    cat = category_prefs(retail_id, ledger_ids, window_start)
    pur = purity_prefs(retail_id, ledger_ids, window_start)
    col = metal_color_prefs(retail_id, ledger_ids, window_start)
    des = design_prefs(retail_id, ledger_ids, window_start)
    stn = stone_prefs(retail_id, ledger_ids, window_start)

    return {
        ledger_id: {
            "category": cat.get(ledger_id, []),
            "purity": pur.get(ledger_id, []),
            "metal_color": col.get(ledger_id, []),
            "design": des.get(ledger_id, []),
            "stone": stn.get(ledger_id, {}),
        }
        for ledger_id in ledger_ids
    }
