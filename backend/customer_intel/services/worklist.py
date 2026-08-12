"""
The daily call list: who to contact today, and why.

Design rules that matter:

  * **Every row carries its reason in plain English.** A ranked list with no
    justification gets ignored by salespeople, correctly.
  * **Computed on read.** An order that turned "ready" five minutes ago has to
    show up now, so this cannot be a nightly table. RFM and cadence are read
    from the snapshot; everything time-sensitive is queried live.
  * **Recently contacted customers are suppressed.** Without this the same
    high-value name tops the list every morning forever and staff stop looking.
  * **Confidence gates the predictive reasons.** `due_to_buy` and `lapse_risk`
    are only emitted where there is enough purchase history to mean anything;
    on a thin dataset the list is legitimately driven by orders, schemes and
    receivables instead.
"""

from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Q

from contacts.crm_utils import days_until_this_year
from customer_intel.models import CustomerProfileSnapshot, EngagementEvent

# Don't resurface a customer for this long after someone contacted them.
SUPPRESS_DAYS = 7

# Base weight per reason, before the customer-value multiplier.
REASONS = {
    "occasion_today": 100,
    "order_ready": 95,
    "scheme_matured": 90,
    "approval_overdue": 85,
    "scheme_payment_overdue": 80,
    "catalog_intent": 75,
    "occasion_soon": 70,
    "receivable_overdue": 70,
    "lapse_risk": 65,
    "due_to_buy": 60,
    "incomplete_profile": 40,
}

OCCASION_HORIZON_DAYS = 14
APPROVAL_OVERDUE_DAYS = 15
DUE_TO_BUY_WINDOW_DAYS = 10
CATALOG_INTENT_DAYS = 7


class _Collector:
    """Accumulates reasons per ledger, keeping the strongest first."""

    def __init__(self):
        self.by_ledger = defaultdict(list)

    def add(self, ledger_id, code, text, due_date=None, action=None):
        if not ledger_id:
            return
        self.by_ledger[ledger_id].append({
            "code": code,
            "text": text,
            "priority": REASONS.get(code, 10),
            "due_date": due_date,
            "action": action or "call",
        })


def _snapshots(retail):
    return {
        s.ledger_id: s
        for s in CustomerProfileSnapshot.objects
        .filter(retail=retail).select_related("ledger")
    }


def _recently_contacted(retail, today):
    since = today - timedelta(days=SUPPRESS_DAYS)
    return set(
        EngagementEvent.objects
        .filter(retail=retail, direction="out", occurred_at__date__gte=since)
        .exclude(ledger__isnull=True)
        .values_list("ledger_id", flat=True)
    )


def _add_occasions(collector, snapshots, today):
    for ledger_id, snapshot in snapshots.items():
        ledger = snapshot.ledger
        for value, label in ((ledger.dob, "Birthday"), (ledger.anniversary, "Anniversary")):
            if not value:
                continue
            days = days_until_this_year(value.month, value.day, today)
            if days == 0:
                collector.add(ledger_id, "occasion_today", f"{label} is today",
                              due_date=today, action="wish")
            elif days <= OCCASION_HORIZON_DAYS:
                collector.add(ledger_id, "occasion_soon",
                              f"{label} in {days} day{'s' if days != 1 else ''}",
                              due_date=today + timedelta(days=days), action="wish")


def _add_orders(collector, retail, today):
    from sales.models import CustomerOrder

    for order in CustomerOrder.objects.filter(
        retail=retail, delivery_status="ready",
    ).select_related("ldgr"):
        collector.add(
            order.ldgr_id, "order_ready",
            f"Order {order.order_no} is ready for collection",
            due_date=order.delivery_date, action="call",
        )


def _add_schemes(collector, retail, today):
    from goldscheme.models import SchemeEnrollment

    horizon = today + timedelta(days=7)
    for enrollment in SchemeEnrollment.objects.filter(
        Q(maturity_date__lte=horizon) | Q(status__iexact="MATURED"),
    ).exclude(status__iexact="REDEEMED").select_related("customer"):
        collector.add(
            enrollment.customer_id, "scheme_matured",
            f"Savings scheme {enrollment.enrollment_no} matures "
            f"{enrollment.maturity_date or 'soon'}",
            due_date=enrollment.maturity_date, action="call",
        )


def _add_approvals(collector, retail, today):
    """
    Items still out on approval. Same outstanding definition the MCP tool and
    the customer profile use — `SalesApprovalItem.ret_status=False`.
    """
    from sales.models import SalesApprovalItem

    cutoff = today - timedelta(days=APPROVAL_OVERDUE_DAYS)
    rows = (
        SalesApprovalItem.objects
        .filter(ret_status=False, retail=retail, billno__date1__lte=cutoff)
        .select_related("billno")
        .values("billno__ldgr_id", "billno__date1")
    )
    worst = {}
    for row in rows:
        ledger_id = row["billno__ldgr_id"]
        issued = row["billno__date1"]
        if ledger_id and issued and (ledger_id not in worst or issued < worst[ledger_id]):
            worst[ledger_id] = issued
    for ledger_id, issued in worst.items():
        collector.add(
            ledger_id, "approval_overdue",
            f"Goods on approval since {issued} ({(today - issued).days} days)",
            due_date=issued, action="call",
        )


def _add_receivables(collector, retail, snapshots):
    try:
        from accounting.receivables import ledger_balances

        balances = ledger_balances(retail, list(snapshots))
    except Exception:
        return
    for ledger_id, balance in (balances or {}).items():
        amount = float(balance or 0)
        if amount > 0:
            collector.add(
                ledger_id, "receivable_overdue",
                f"Owes ₹{amount:,.0f}", action="call",
            )


def _add_catalog_intent(collector, retail, today):
    from customer_intel.models import CatalogViewEvent

    since = today - timedelta(days=CATALOG_INTENT_DAYS)
    seen = (
        CatalogViewEvent.objects
        .filter(retail=retail, occurred_at__date__gte=since)
        .exclude(ledger__isnull=True)
        .values_list("ledger_id", flat=True)
        .distinct()
    )
    for ledger_id in seen:
        collector.add(
            ledger_id, "catalog_intent",
            "Browsed the catalog in the last week", action="call",
        )


def _add_predictive(collector, snapshots, today):
    """
    Cadence-driven reasons — only where the snapshot says the cadence means
    something. On a thin dataset these simply do not fire, which is correct.
    """
    for ledger_id, snapshot in snapshots.items():
        if not snapshot.cadence_is_meaningful:
            continue

        if snapshot.next_expected_date:
            delta = (snapshot.next_expected_date - today).days
            if abs(delta) <= DUE_TO_BUY_WINDOW_DAYS:
                collector.add(
                    ledger_id, "due_to_buy",
                    f"Usually buys about now (every "
                    f"{snapshot.median_gap_days} days)",
                    due_date=snapshot.next_expected_date, action="call",
                )

        if snapshot.lapse_band == "at_risk":
            collector.add(
                ledger_id, "lapse_risk",
                f"Overdue to buy — last purchase {snapshot.days_since_last} days ago",
                action="call",
            )


def _add_incomplete_profiles(collector, snapshots, today):
    """Customers worth chasing for the details the CRM cannot work without."""
    recent = today - timedelta(days=180)
    for ledger_id, snapshot in snapshots.items():
        if not snapshot.last_purchase_date or snapshot.last_purchase_date < recent:
            continue
        ledger = snapshot.ledger
        missing = [
            label for value, label in (
                (ledger.mobile1, "mobile"), (ledger.dob, "date of birth"),
                (ledger.anniversary, "anniversary"),
            ) if not value
        ]
        if missing:
            collector.add(
                ledger_id, "incomplete_profile",
                f"Recent customer, missing {', '.join(missing)}",
                action="capture",
            )


def build_worklist(retail, today=None, limit=100, include_contacted=False):
    """
    Ranked list of customers to contact today.

    Score = strongest reason's base weight × (1 + how valuable this customer is
    relative to the branch's 90th percentile). A champion and a one-off buyer
    with the same reason are not equally worth a phone call.
    """
    today = today or date.today()
    snapshots = _snapshots(retail)
    if not snapshots:
        return []

    collector = _Collector()
    _add_occasions(collector, snapshots, today)
    _add_orders(collector, retail, today)
    _add_schemes(collector, retail, today)
    _add_approvals(collector, retail, today)
    _add_receivables(collector, retail, snapshots)
    _add_catalog_intent(collector, retail, today)
    _add_predictive(collector, snapshots, today)
    _add_incomplete_profiles(collector, snapshots, today)

    suppressed = set() if include_contacted else _recently_contacted(retail, today)

    spends = sorted(float(s.net_spend or 0) for s in snapshots.values())
    p90 = spends[int(len(spends) * 0.9)] if spends else 0

    rows = []
    for ledger_id, reasons in collector.by_ledger.items():
        if ledger_id in suppressed or ledger_id not in snapshots:
            continue
        snapshot = snapshots[ledger_id]
        ledger = snapshot.ledger

        reasons.sort(key=lambda r: r["priority"], reverse=True)
        top = reasons[0]

        value = float(snapshot.net_spend or 0)
        multiplier = 1 + (min(1.0, value / p90) if p90 else 0)

        rows.append({
            "ledger_id": ledger_id,
            "ac_name": ledger.ac_name,
            "mobile": ledger.mobile1 or "",
            "city": ledger.city or "",
            "lifetime_value": snapshot.lifetime_value,
            "rfm_segment": snapshot.rfm_segment,
            "confidence": snapshot.confidence,
            "reason_code": top["code"],
            "reason": top["text"],
            "action": top["action"],
            "due_date": top["due_date"],
            "other_reasons": [r["text"] for r in reasons[1:4]],
            "priority_score": round(top["priority"] * multiplier, 1),
            "last_contacted_at": snapshot.last_contacted_at,
        })

    rows.sort(key=lambda r: r["priority_score"], reverse=True)
    return rows[:limit]
