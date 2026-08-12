"""
Assemble the Customer 360 payload for a single customer.

Everything here is composed from existing sources of truth rather than
recomputed — outstanding comes from the GL, transactions from the shared
customer-history service, approvals from the same definition the MCP tool uses.
Two places disagreeing about what a customer owes is worse than not showing it.
"""

from datetime import date

from contacts.crm_utils import days_until_this_year
from customer_intel.models import CustomerProfileSnapshot, CustomerSocialProfile
from sales.models import CustomerOrder, SalesApprovalItem, SalesVouItem

# How many recent line items the profile returns before pagination is needed.
LINE_ITEM_LIMIT = 100


def _snapshot_payload(snapshot):
    """The stored analytics, with cadence suppressed when it isn't trustworthy."""
    if snapshot is None:
        return None

    payload = {
        "confidence": snapshot.confidence,
        "confidence_reason": snapshot.confidence_reason,
        "scoring_basis": snapshot.scoring_basis,
        "computed_at": snapshot.computed_at,

        "first_purchase_date": snapshot.first_purchase_date,
        "last_purchase_date": snapshot.last_purchase_date,
        "days_since_last": snapshot.days_since_last,
        "purchase_count": snapshot.purchase_count,
        "purchase_count_all": snapshot.purchase_count_all,

        "gross_spend": snapshot.gross_spend,
        "returns_value": snapshot.returns_value,
        "net_spend": snapshot.net_spend,
        "lifetime_value": snapshot.lifetime_value,

        "r_score": snapshot.r_score,
        "f_score": snapshot.f_score,
        "m_score": snapshot.m_score,
        "rfm_cell": snapshot.rfm_cell,
        "rfm_segment": snapshot.rfm_segment,

        "avg_ticket": snapshot.avg_ticket,
        "median_ticket": snapshot.median_ticket,
        "min_ticket": snapshot.min_ticket,
        "max_ticket": snapshot.max_ticket,
        "p25_ticket": snapshot.p25_ticket,
        "p75_ticket": snapshot.p75_ticket,

        "preferences": {
            "category": snapshot.category_prefs,
            "purity": snapshot.purity_prefs,
            "metal_color": snapshot.metal_color_prefs,
            "design": snapshot.design_prefs,
            "stone": snapshot.stone_prefs,
        },

        "engagement_score": snapshot.engagement_score,
        "engagement_components": (snapshot.engagement_components or {}).get("components", []),
        "catalog_views_90d": snapshot.catalog_views_90d,
        "last_contacted_at": snapshot.last_contacted_at,
        "last_inbound_at": snapshot.last_inbound_at,
        "b2b": snapshot.b2b,
    }

    # Cadence and lapse are only emitted when there is enough history to mean
    # anything. Below 'medium' the frontend shows confidence_reason instead —
    # a made-up rhythm is worse than an honest blank.
    if snapshot.cadence_is_meaningful:
        payload["cadence"] = {
            "meaningful": True,
            "median_gap_days": snapshot.median_gap_days,
            "mean_gap_days": snapshot.mean_gap_days,
            "gap_basis": snapshot.gap_basis,
            "next_expected_date": snapshot.next_expected_date,
            "lapse_ratio": snapshot.lapse_ratio,
            "lapse_band": snapshot.lapse_band,
            "explainer": _cadence_explainer(snapshot),
        }
    else:
        payload["cadence"] = {
            "meaningful": False,
            "reason": snapshot.confidence_reason,
        }
    return payload


def _cadence_explainer(snapshot):
    """
    Plain-English sentence for the UI. The rule is that we never show a bare
    ratio — a salesperson must be able to see the arithmetic behind 'At risk'.
    """
    gap = snapshot.median_gap_days
    if not gap:
        return ""

    months = gap / 30.4
    rhythm = f"{months:.0f} month{'s' if round(months) != 1 else ''}" if months >= 1.5 \
        else f"{gap} days"

    basis = {
        "own": f"median of {snapshot.purchase_count_all} purchases",
        "blended": "own history blended with similar customers",
        "cohort": "typical for customers buying the same category",
    }.get(snapshot.gap_basis, "")

    sentence = f"Buys roughly every {rhythm}"
    if basis:
        sentence += f" ({basis})"
    if snapshot.days_since_last is not None:
        since_months = snapshot.days_since_last / 30.4
        since = (f"{since_months:.0f} months" if since_months >= 1.5
                 else f"{snapshot.days_since_last} days")
        sentence += f". Last purchase {since} ago"
    if snapshot.lapse_band:
        sentence += f" → {snapshot.lapse_band.replace('_', ' ').title()}"
    return sentence + "."


def _outstanding(retail, ledger_id):
    """
    The customer's GL position, never `SalesVou.due_amt`.

    accounting/receivables.py is explicit that due_amt has drifted from reality;
    the GL balance is the number the accounts team will quote.

    Its sign convention is debit-positive: a positive balance means the customer
    owes us, a negative one means we are holding their money (an advance). A raw
    signed number labelled "outstanding" reads as a data error to a salesperson,
    so the direction is made explicit here rather than left to the UI to infer.
    """
    try:
        from accounting.receivables import ledger_balances

        balances = ledger_balances(retail, [ledger_id])
        balance = balances.get(ledger_id) if isinstance(balances, dict) else balances
        balance = balance or 0
    except Exception:  # pragma: no cover - accounting shape varies by version
        return None

    amount = float(balance)
    if amount > 0:
        direction, label = "receivable", "Owes us"
    elif amount < 0:
        direction, label = "advance", "Advance held"
    else:
        direction, label = "settled", "Settled"

    return {
        "balance": round(amount, 2),
        "amount": round(abs(amount), 2),
        "direction": direction,
        "label": label,
    }


def _occasions(ledger, today=None):
    today = today or date.today()
    out = []
    for field, label in (("dob", "birthday"), ("anniversary", "anniversary")):
        value = getattr(ledger, field, None)
        if not value:
            continue
        out.append({
            "occasion": label,
            "date": value,
            "days_until": days_until_this_year(value.month, value.day, today),
        })
    return sorted(out, key=lambda o: o["days_until"])


def _line_items(retail, ledger_id, limit=LINE_ITEM_LIMIT):
    """
    What they actually bought, line by line — the detail the existing
    header-level history endpoint does not carry.
    """
    qs = (
        SalesVouItem.objects
        .filter(billno__retail=retail, billno__ldgr_id=ledger_id, ret_status=False)
        .select_related(
            "item", "item__grp", "barcode", "barcode__design", "barcode__purity",
            "billno",
        )
        .order_by("-billno__date1", "-id")[:limit]
    )
    return [{
        "id": row.id,
        "date": row.billno.date1 if row.billno_id else None,
        "bill_no": row.billno.billno if row.billno_id else "",
        "item": row.item.item_name if row.item_id else "",
        "category": (row.item.grp.item_group_name
                     if row.item_id and row.item.grp_id else ""),
        "design_no": (row.barcode.design.design_no
                      if row.barcode_id and row.barcode.design_id
                      else (row.barcode.design_code if row.barcode_id else "")),
        "purity": (str(row.barcode.purity.purity)
                   if row.barcode_id and row.barcode.purity_id else ""),
        "metal_color": row.barcode.metal_color if row.barcode_id else "",
        "pcs": row.pcs,
        "gw": row.gw,
        "making": row.making,
        "amount": row.amount,
    } for row in qs]


def _schemes(ledger):
    try:
        enrollments = ledger.scheme_enrollments.select_related("scheme").all()
    except AttributeError:  # pragma: no cover
        return []
    return [{
        "id": e.id,
        "enrollment_no": e.enrollment_no,
        "scheme": str(e.scheme) if e.scheme_id else "",
        "status": e.status,
        "start_date": e.start_date,
        "maturity_date": e.maturity_date,
        "installment_amount": e.installment_amount,
        "total_paid": e.total_paid,
        "payments_made": e.payments_made,
        "gold_accumulated_wt": e.gold_accumulated_wt,
    } for e in enrollments]


def _pending_orders(retail, ledger_id):
    qs = CustomerOrder.objects.filter(
        ldgr_id=ledger_id, retail=retail,
        delivery_status__in=["pending", "ready", "partial_return"],
    ).order_by("-date1")
    return [{
        "id": o.id,
        "order_no": o.order_no,
        "date": o.date1,
        "delivery_date": o.delivery_date,
        "delivery_status": o.delivery_status,
        "est_amount": o.est_amount,
        "advance_amt": o.advance_amt,
        "advance_available": o.advance_available,
    } for o in qs]


def _approvals(retail, ledger_id, today=None):
    """
    Jewellery out on approval that has not come back — live loss exposure.

    Outstanding is defined at the *item* level (`ret_status=False`), exactly as
    the `get_approval_items_outstanding` MCP tool defines it. SalesApproval has
    no header-level status column, and the ERP has no approval-to-sale link, so
    an approval that became a sale must have been recorded as a return first.
    """
    today = today or date.today()
    qs = (
        SalesApprovalItem.objects
        .filter(ret_status=False, retail=retail, billno__ldgr_id=ledger_id)
        .select_related("billno", "barcode", "item")
        .order_by("billno__date1")
    )
    return [{
        "id": it.id,
        "approval_no": it.billno.billno if it.billno_id else "",
        "date": it.billno.date1 if it.billno_id else None,
        "days_outstanding": (
            (today - it.billno.date1).days
            if it.billno_id and it.billno.date1 else None
        ),
        "barcode": str(it.barcode) if it.barcode_id else "",
        "item": it.item.item_name if it.item_id else "",
        "pcs": it.pcs,
        "gw": it.gw,
        "amount": it.amount,
    } for it in qs]


def build_profile(retail, ledger, today=None):
    """
    Full Customer 360 payload.

    `ledger` is a Ledger instance; the caller is responsible for having applied
    retail scoping and for masking identity fields (see contacts.masking) before
    serialising to a user who lacks the unmasked-customer permission.
    """
    snapshot = CustomerProfileSnapshot.objects.filter(
        retail=retail, ledger=ledger,
    ).first()
    social = CustomerSocialProfile.objects.filter(ledger=ledger).first()

    return {
        "ledger": {
            "id": ledger.id,
            "ac_name": ledger.ac_name,
            "display_name": ledger.display_name,
            "salutation": ledger.salutation,
            "mobile": ledger.mobile1,
            "email": ledger.email,
            "city": ledger.city,
            "state": ledger.state,
            "gst": ledger.gst,
            "pan": ledger.pan,
            "dob": ledger.dob,
            "anniversary": ledger.anniversary,
            "b2b": ledger.b2b,
        },
        "profile_complete": bool(ledger.mobile1 and ledger.dob and ledger.anniversary),
        "snapshot": _snapshot_payload(snapshot),
        "occasions": _occasions(ledger, today),
        "outstanding": _outstanding(retail, ledger.id),
        "line_items": _line_items(retail, ledger.id),
        "schemes": _schemes(ledger),
        "pending_orders": _pending_orders(retail, ledger.id),
        "approvals": _approvals(retail, ledger.id, today),
        "has_portal_account": ledger.portal_accounts.exists(),
        "consent": {
            "whatsapp_opt_in": social.whatsapp_opt_in if social else True,
            "email_opt_in": social.email_opt_in if social else True,
            "opted_out": bool(social and social.opt_out_at),
            "opt_out_at": social.opt_out_at if social else None,
            "gender": social.gender if social else "",
            "instagram": social.instagram if social else "",
            "facebook": social.facebook if social else "",
            "preferred_language": social.preferred_language if social else "en",
            "notes": social.notes if social else "",
        },
    }
