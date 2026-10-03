"""Fabricator reports (JOB-05, JOB-08, JOB-12): what each fabricator holds, what is short, and for how long."""
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from jobwork.models import ChallanBundle, ChallanTrim, JobWorkChallan, ReceiptLine, ReceiptTrim

OPEN = ("issued", "partly_received", "fully_received")


def fabricator_ledger(user, party, factory=None):
    """Two parts, as in JOB-05: (a) material and cut pieces issued, (b) goods in process, per challan."""
    qs = JobWorkChallan.objects.for_user(user).filter(party=party).exclude(status__in=("draft", "cancelled"))
    if factory is not None:
        qs = qs.filter(factory=factory)
    rows = []
    for ch in qs.select_related("lot", "step__process").prefetch_related("bundles", "trims__material"):
        issued = sum(b.qty_issued for b in ch.bundles.all())
        received = sum(b.qty_received for b in ch.bundles.all())
        short = sum(b.qty_shortage for b in ch.bundles.all())
        accepted = sum(b.qty_accepted for b in ch.bundles.all())
        rejected = sum(b.qty_rejected for b in ch.bundles.all())
        rows.append({
            "challan": ch, "issued": issued, "received": received, "shortage": short, "accepted": accepted,
            "rejected": rejected, "in_process": max(0, issued - received - short),
            "trims": [(t.material.name, t.qty_issued, t.qty_returned, t.qty_missing) for t in ch.trims.all()],
        })
    return rows


def shortage_report(user, factory=None):
    """Pieces and trims issued vs received, per fabricator (JOB-08)."""
    lines = ReceiptLine.objects.filter(shortage_qty__gt=0, challan_bundle__challan__in=JobWorkChallan.objects.for_user(user))
    trims = ReceiptTrim.objects.filter(qty_missing__gt=0, challan_trim__challan__in=JobWorkChallan.objects.for_user(user))
    if factory is not None:
        lines = lines.filter(challan_bundle__challan__factory=factory)
        trims = trims.filter(challan_trim__challan__factory=factory)
    out = {}
    for l in lines.select_related("challan_bundle__challan__party", "challan_bundle__bundle"):
        p = l.challan_bundle.challan.party
        row = out.setdefault(p.pk, {"party": p, "pieces": 0, "piece_value": Decimal("0"), "trims": []})
        row["pieces"] += l.shortage_qty
        row["piece_value"] += l.shortage_value
    for t in trims.select_related("challan_trim__challan__party", "challan_trim__material"):
        p = t.challan_trim.challan.party
        row = out.setdefault(p.pk, {"party": p, "pieces": 0, "piece_value": Decimal("0"), "trims": []})
        row["trims"].append((t.challan_trim.material.name, t.qty_missing))
    return list(out.values())


def ageing(user, today=None):
    """Material lying with each fabricator, by how many days since it was issued (JOB-12)."""
    today = today or date.today()
    qs = ChallanBundle.objects.filter(challan__in=JobWorkChallan.objects.for_user(user), challan__status__in=("issued", "partly_received"),
                                      qty_received=0, qty_shortage=0).select_related("challan__party", "challan__lot")
    buckets = {"0-7": 0, "8-15": 0, "16-30": 0, "31+": 0}
    per_party = {}
    for cb in qs:
        days = (today - cb.challan.date).days
        key = "0-7" if days <= 7 else "8-15" if days <= 15 else "16-30" if days <= 30 else "31+"
        buckets[key] += cb.qty_issued
        row = per_party.setdefault(cb.challan.party.pk, {"party": cb.challan.party, "pieces": 0, "oldest": 0})
        row["pieces"] += cb.qty_issued
        row["oldest"] = max(row["oldest"], days)
    return {"buckets": buckets, "parties": sorted(per_party.values(), key=lambda r: -r["oldest"])}
