"""The owner's daily fabricator summary (E8.8): per fabricator, what was issued, received and accepted today, what is still
with them, what is overdue, and what they earned. Built per factory by `manage.py daily_summary` at the configured time
(cron, default 6 PM) and kept. It is a screen and a ready-to-send text; sending it on WhatsApp needs the WhatsApp
integration, which is not built yet. "Done" marks from a fabricator's phone do not exist in this build, so they are
not part of it."""
from datetime import date
from decimal import Decimal

from django.db import transaction

from core.scoping import assert_factory_access
from jobwork.models import ChallanBundle, DailySummary, DailySummaryRow, QcResult, ReceiptLine

ZERO = Decimal("0.00")
POSTED = ("issued", "partly_received", "fully_received", "billed", "closed")
OPEN = ("issued", "partly_received")


@transaction.atomic
def build_summary(factory, on_date: date, *, user=None) -> DailySummary:
    """(Re)build one day for one factory. Safe to repeat: the day is replaced, never doubled."""
    if user is not None:
        assert_factory_access(user, factory)
    rows = {}

    def row(party):
        return rows.setdefault(party.pk, {"party": party, "issued_bundles": 0, "issued_pcs": 0, "received_pcs": 0,
                                          "accepted_pcs": 0, "pending_pcs": 0, "overdue_pcs": 0, "earnings": ZERO})

    for cb in ChallanBundle.objects.filter(challan__factory=factory, challan__date=on_date, challan__status__in=POSTED
                                           ).select_related("challan__party"):
        r = row(cb.challan.party)
        r["issued_bundles"] += 1
        r["issued_pcs"] += cb.qty_issued
    for rl in ReceiptLine.objects.filter(receipt__factory=factory, receipt__date=on_date).exclude(
            receipt__status="pending_approval").select_related("receipt__challan__party"):
        row(rl.receipt.challan.party)["received_pcs"] += rl.qty_received
    for qc in QcResult.objects.filter(line__receipt__factory=factory, checked_at__date=on_date).select_related(
            "line__receipt__challan__party"):
        r = row(qc.line.receipt.challan.party)
        r["accepted_pcs"] += qc.accepted
        r["earnings"] += (qc.accepted * qc.rate).quantize(Decimal("0.01"))
    for cb in ChallanBundle.objects.filter(challan__factory=factory, challan__status__in=OPEN).select_related("challan__party"):
        left = max(0, cb.qty_issued - cb.qty_received - cb.qty_shortage)
        if left:
            r = row(cb.challan.party)
            r["pending_pcs"] += left
            if cb.challan.expected_date and cb.challan.expected_date < on_date:
                r["overdue_pcs"] += left

    summary, _ = DailySummary.objects.get_or_create(factory=factory, date=on_date)
    summary.rows.all().delete()
    for r in sorted(rows.values(), key=lambda r: r["party"].name):
        DailySummaryRow.objects.create(summary=summary, **r)
    summary.save()  # touches generated_at
    return summary


def as_text(summary: DailySummary) -> str:
    """The summary as a short plain message, ready to paste or send."""
    lines = [f"{summary.factory.name}: fabricators, {summary.date:%d %b %Y}"]
    rows = list(summary.rows.select_related("party"))
    if not rows:
        lines.append("Nothing issued, received or pending.")
    for r in rows:
        lines.append(f"{r.party.name}: issued {r.issued_pcs} pcs in {r.issued_bundles} bundles, received {r.received_pcs}, "
                     f"accepted {r.accepted_pcs}, pending {r.pending_pcs}, overdue {r.overdue_pcs}, earned Rs {r.earnings}")
    return "\n".join(lines)


def totals(summary: DailySummary) -> dict:
    rows = list(summary.rows.all())
    keys = ("issued_bundles", "issued_pcs", "received_pcs", "accepted_pcs", "pending_pcs", "overdue_pcs")
    out = {k: sum(getattr(r, k) for r in rows) for k in keys}
    out["earnings"] = sum((r.earnings for r in rows), ZERO)
    return out
