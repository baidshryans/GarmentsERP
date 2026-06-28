"""Core logic for importing the old ERP's barcode movement + split/merge tables.

Source-agnostic: every function takes plain row-dicts (from CSV or the legacy DB)
and writes Django models. Idempotent via the `legacy_key` field.
"""
import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date

# old code -> canonical code recognized by the stock report. Codes mapping to
# themselves are listed for documentation; OP-STK/EST/ISS-ST are history-only
# (ignored by the report's inflow/outflow math).
TRANS_TYPE_MAP = {
    "TRF-RR-OUT": "TRF-RR-OUT",
    "TRF-RR-IN": "TRF-RR-IN",
    "SALE": "SALE",
    "SALE-RET": "SALE-RET",
    "SALE-APPR": "SALE-APP",
    "APPR-RET": "SALE-APP-RET",
    "BAR-SPLT": "BAR-SPLIT",
    "BAR-SPLT-CRT": "BAR-SPLIT-CRT",
    "NEW-BAR": "CREATE-PUR",
    "PR": "PURCHASE-RET",
    "OP-STK": "OP-STK",
    "EST": "EST",
    "ISS-ST": "ISS-ST",
}


# A barcode is genesis'd exactly once. The legacy log sometimes holds a duplicate
# "New Create" row (re-save), which would double-count the piece as phantom stock
# at the create retail in the stock report.
CREATE_TYPES = ("CREATE-PUR", "CREATE-REC")


def map_trans_type(code):
    """(canonical_code, is_known). Unknown codes are returned verbatim with False."""
    code = (code or "").strip()
    if code in TRANS_TYPE_MAP:
        return TRANS_TYPE_MAP[code], True
    return code, False


def parse_dt(value):
    """Parse a date/datetime string to an aware datetime; now() on blank/unparseable."""
    if value in (None, ""):
        return timezone.now()
    s = str(value).strip()
    dt = parse_datetime(s)
    if dt is None:
        d = parse_date(s)
        if d is not None:
            dt = datetime.datetime(d.year, d.month, d.day)
    if dt is None:
        return timezone.now()
    if timezone.is_naive(dt):
        # Legacy values are date-only (midnight). Anchor to UTC so the calendar
        # date is stable regardless of the server/display timezone.
        dt = timezone.make_aware(dt, datetime.timezone.utc)
    return dt


def parse_d(value):
    """Parse to a date; today() on blank/unparseable."""
    if value in (None, ""):
        return timezone.now().date()
    s = str(value).strip()
    d = parse_date(s)
    if d is not None:
        return d
    dt = parse_datetime(s)
    return dt.date() if dt else timezone.now().date()


def build_lookups():
    """Return (barcodes_by_str, retails_by_code, users_by_name) — built once per run."""
    from inventory.models import BarcodeMain
    from mastersconfig.models import RetailMaster
    from django.contrib.auth import get_user_model

    barcodes = {b.barcode: b for b in BarcodeMain.objects.all()}
    retails = {r.retail_code: r for r in RetailMaster.objects.all()}
    users = {}
    for u in get_user_model().objects.all():
        full = f"{u.first_name} {u.last_name}".strip()
        if full:
            users.setdefault(full, u)
        users.setdefault(u.username, u)
    return barcodes, retails, users


def import_transactions(rows, barcodes, retails, users, *, apply):
    """Create BarcodeTransaction rows from legacy txn dicts. Idempotent on legacy_key."""
    from inventory.models import BarcodeTransaction

    stats = {"created": 0, "existing": 0, "unmatched": [], "unmapped": {}, "per_type": {}}
    for r in rows:
        bcode = str(r.get("barcode") or "").strip()
        bc = barcodes.get(bcode)
        if bc is None:
            stats["unmatched"].append(bcode)
            continue
        canon, known = map_trans_type(r.get("tran_type"))
        if not known:
            stats["unmapped"][canon] = stats["unmapped"].get(canon, 0) + 1
        stats["per_type"][canon] = stats["per_type"].get(canon, 0) + 1

        legacy_key = str(r["id"])
        if not apply:
            if BarcodeTransaction.objects.filter(legacy_key=legacy_key).exists():
                stats["existing"] += 1
            else:
                stats["created"] += 1
            continue

        retail = retails.get(str(r.get("rt_code") or "").strip())
        user = users.get(str(r.get("user_id") or "").strip())
        ip = str(r.get("ip") or "").strip() or "0.0.0.0"
        obj, created = BarcodeTransaction.objects.get_or_create(
            legacy_key=legacy_key,
            defaults=dict(
                barcode=bc, billno=str(r.get("billno") or "")[:50],
                trans_type=canon, user=user, ip_address=ip, retail=retail,
            ),
        )
        if created:
            # date has auto_now_add; override with the real legacy date via update()
            BarcodeTransaction.objects.filter(pk=obj.pk).update(date=parse_dt(r.get("date1")))
            stats["created"] += 1
        else:
            stats["existing"] += 1

    # Remove redundant duplicate transactions that would distort the stock report.
    if apply:
        from django.db.models import Count, Min
        removed = 0
        # 1. Exact duplicates — same barcode, type, bill AND timestamp. The legacy
        #    log records e.g. "Barcode Split" once per resulting child, which
        #    over-counts the parent's outflow (a barcode is split only once).
        for d in (BarcodeTransaction.objects
                  .values("barcode_id", "trans_type", "billno", "date")
                  .annotate(n=Count("id"), keep=Min("id")).filter(n__gt=1)):
            extra = BarcodeTransaction.objects.filter(
                barcode_id=d["barcode_id"], trans_type=d["trans_type"],
                billno=d["billno"], date=d["date"]).exclude(id=d["keep"])
            removed += extra.count()
            extra.delete()
        # 2. Duplicate genesis — a barcode is created once, but a re-save can log a
        #    second "New Create" with a different timestamp the exact pass misses.
        for d in (BarcodeTransaction.objects.filter(trans_type__in=CREATE_TYPES)
                  .values("barcode_id").annotate(n=Count("id"), keep=Min("id"))
                  .filter(n__gt=1)):
            extra = BarcodeTransaction.objects.filter(
                barcode_id=d["barcode_id"], trans_type__in=CREATE_TYPES).exclude(id=d["keep"])
            removed += extra.count()
            extra.delete()
        if removed:
            stats["deduped"] = removed
    return stats


def reconcile_op_stk(rows, barcodes, retails, *, apply):
    """Set BarcodeMain.op_stk=True only for barcodes that have an OP-STK legacy row;
    set False for other barcodes present in the legacy data. Barcodes absent from the
    data are left untouched."""
    present = {}          # barcode_str -> set(trans_type)
    op_retail_for = {}    # barcode_str -> RetailMaster (from its OP-STK row)
    for r in rows:
        b = str(r.get("barcode") or "").strip()
        ttype = (r.get("tran_type") or "").strip()
        present.setdefault(b, set()).add(ttype)
        if ttype == "OP-STK":
            op_retail_for[b] = retails.get(str(r.get("rt_code") or "").strip())

    stats = {"set_true": 0, "set_false": 0, "missing": 0}
    for b, types in present.items():
        bm = barcodes.get(b)
        if bm is None:
            stats["missing"] += 1
            continue
        is_op = "OP-STK" in types
        if is_op:
            if not bm.op_stk:
                stats["set_true"] += 1
            if apply:
                bm.op_stk = True
                if op_retail_for.get(b) is not None:
                    bm.op_retail = op_retail_for[b]
                bm.save(update_fields=["op_stk", "op_retail"])
        else:
            if bm.op_stk:
                stats["set_false"] += 1
                if apply:
                    bm.op_stk = False
                    bm.save(update_fields=["op_stk"])
    return stats


def mark_consumed_barcodes(*, apply):
    """Barcodes whose name carries the #SPL / #MER marker are consumed parents of a
    split/merge and must not count as stock — flag them op_stk=False, stk_status=False.

    The legacy split/merge tables store the pre-rename id, so these often aren't
    linked as a BarcodeSplitMerge.old_barcode; the name marker is the reliable signal.
    """
    from django.db.models import Q
    from inventory.models import BarcodeMain

    qs = BarcodeMain.objects.filter(Q(barcode__icontains="#SPL") | Q(barcode__icontains="#MER"))
    n = qs.filter(Q(op_stk=True) | Q(stk_status=True)).count()
    if apply:
        qs.update(op_stk=False, stk_status=False)
    return {"consumed_marked": n}


def import_split_merge(rows, kind, barcodes, retails, *, apply):
    """Create BarcodeSplitMerge rows. kind is 'Split' or 'Merge'. legacy_key is
    namespaced ('split:<id>' / 'merge:<id>') since the two legacy tables share ids."""
    from inventory.models import BarcodeSplitMerge

    prefix = kind.lower()
    stats = {"created": 0, "existing": 0, "skipped_both_missing": 0, "unmatched_new": []}
    for r in rows:
        old = barcodes.get(str(r.get("old_barcode") or "").strip())
        new = barcodes.get(str(r.get("new_barcode") or "").strip())
        if old is None and new is None:
            stats["skipped_both_missing"] += 1
            continue
        if new is None:
            stats["unmatched_new"].append(str(r.get("new_barcode") or ""))

        legacy_key = f"{prefix}:{r['id']}"
        if not apply:
            if BarcodeSplitMerge.objects.filter(legacy_key=legacy_key).exists():
                stats["existing"] += 1
            else:
                stats["created"] += 1
            continue

        retail = retails.get(str(r.get("rt_code") or "").strip())
        obj, created = BarcodeSplitMerge.objects.get_or_create(
            legacy_key=legacy_key,
            defaults=dict(transaction_type=kind, old_barcode=old,
                          new_barcode=new, retail=retail),
        )
        if created:
            BarcodeSplitMerge.objects.filter(pk=obj.pk).update(date1=parse_d(r.get("date1")))
            stats["created"] += 1
        else:
            stats["existing"] += 1
    return stats
