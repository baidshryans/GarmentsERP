"""Read-only figures for the home dashboard (E10). Every query is factory-scoped for the user, and each
section is built only if the user's role may see that screen, so production roles never get money (BR-15)."""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

from core.models import Factory
from jobwork.models import JobWorkChallan, Receipt
from ledger.models import Voucher
from production.models import Bundle, Lot, ProductionOrder
from production.services import guide
from purchases.models import Grn, PurchaseOrder
from inventory.models import StockAlert
from reports.services import standard
from sales.models import SaleInvoice, SaleOrder

ZERO = Decimal("0.00")


def production_overview(user, today):
    lots = Lot.objects.for_user(user).filter(status__in=("planned", "cutting", "in_production")).select_related(
        "style", "colour", "order_line__order")
    live = Bundle.objects.filter(status__in=Bundle.LIVE, lot__in=lots).select_related(
        "current_step__process", "location__party")
    wip, stages, holders, rework = defaultdict(int), defaultdict(lambda: defaultdict(int)), defaultdict(set), 0
    by_stage = defaultdict(int)
    for b in live:
        stage = b.current_step.process.name if b.current_step_id else "Cut, waiting"
        wip[b.lot_id] += b.qty
        stages[b.lot_id][stage] += b.qty
        by_stage[stage] += b.qty
        holders[b.lot_id].add(b.location.party.name if b.location.party_id else "In-house")
        if b.is_rework:
            rework += b.qty
    cut = dict(Bundle.objects.filter(lot__in=lots, split_from__isnull=True).values_list("lot_id").annotate(s=Sum("original_qty")))
    rows, perms = [], {}
    for lot in lots:
        order = lot.order_line.order
        rows.append({
            "lot": lot, "order": order, "planned": lot.order_line.total_qty, "cut": cut.get(lot.pk, 0),
            "wip": wip.get(lot.pk, 0),
            "stages": ", ".join(f"{n} {q}" for n, q in sorted(stages[lot.pk].items(), key=lambda kv: -kv[1])) or "Not cut yet",
            "where": ", ".join(sorted(holders[lot.pk])) or "-",
            "late": bool(order.due_date and order.due_date < today),
            "next": guide.lot_guide(lot, user, perms)["primary"],     # only an action this user's role may do, or None
        })
    rows.sort(key=lambda r: (not r["late"], r["order"].due_date or today.max, r["lot"].lot_no))
    orders = ProductionOrder.objects.for_user(user)
    return {
        "rows": rows, "wip_total": sum(wip.values()), "rework": rework,
        "open_lots": len(rows), "late_lots": sum(r["late"] for r in rows),
        "by_stage": sorted(by_stage.items(), key=lambda kv: -kv[1]),
        "orders_in_production": orders.filter(status__in=("released", "in_production", "partly_completed")).count(),
        "orders_to_release": orders.filter(status="draft").count(),
        "challans_out": JobWorkChallan.objects.for_user(user).filter(status__in=("issued", "partly_received")).count(),
        "awaiting_qc": Receipt.objects.for_user(user).filter(status="received").count(),
    }


def sales_overview(user, today):
    month = today.replace(day=1)
    inv = SaleInvoice.objects.for_user(user).filter(status="posted")
    orders = SaleOrder.objects.for_user(user)
    return {
        "month_sales": inv.filter(date__gte=month).aggregate(s=Sum("total"))["s"] or ZERO,
        "month_invoices": inv.filter(date__gte=month).count(),
        "open_orders": orders.filter(status__in=("confirmed", "partly_dispatched")).count(),
        "overdue_orders": orders.filter(status__in=("confirmed", "partly_dispatched"), due_date__lt=today).count(),
    }


def purchase_overview(user, today):
    pos = PurchaseOrder.objects.for_user(user)
    return {
        "open_pos": pos.filter(status__in=("approved", "partly_received")).count(),
        "pos_to_approve": pos.filter(status="pending_approval").count(),
        "grn_pending": Grn.objects.for_user(user).filter(status__in=("draft", "qc_done")).count(),
    }


def accounts_overview(user):
    posted = Voucher.objects.for_user(user).filter(status="posted")
    return {"voucher_count": posted.count(), "recent": posted.select_related("factory")[:6]}


# (section, figure, text for one, text for many, screen that deals with it, permission that screen needs)
ATTENTION = [
    ("production", "awaiting_qc", "receipt from a fabricator is waiting to be checked",
     "receipts from fabricators are waiting to be checked", "receipt_list", "jobwork.receipt"),
    ("production", "late_lots", "lot is past its due date", "lots are past their due date", "production_dashboard", "production.dashboard"),
    ("production", "orders_to_release", "production order is a draft, waiting to be released",
     "production orders are drafts, waiting to be released", "order_list", "production.order"),
    ("purchases", "pos_to_approve", "purchase order is waiting for approval",
     "purchase orders are waiting for approval", "po_list", "purchases.po"),
    ("purchases", "grn_pending", "goods receipt is not posted yet", "goods receipts are not posted yet", "grn_list",
     "purchases.grn"),
    ("sales", "overdue_orders", "sale order is past its due date", "sale orders are past their due date", "saleorder_list",
     "sales.order"),
    (None, "low_stock", "item is below its minimum stock", "items are below their minimum stock", "stock_alerts", "inventory.alerts"),
]


def attention_items(data, user):
    """What is waiting on the user, from the figures already gathered for them (so already factory-scoped).
    A line is offered only if the user may open the screen it leads to. Nothing waiting, no line."""
    items = []
    for section, figure, one, many, url_name, screen in ATTENTION:
        source = data if section is None else data.get(section)
        count = (source or {}).get(figure) or 0
        if count and user.has_screen_perm(screen, "view"):
            items.append({"count": count, "text": one if count == 1 else many, "url": reverse(url_name)})
    return items


def build_overview(user):
    today = timezone.localdate()
    can = user.has_screen_perm
    data = {
        "today": today,
        "factory_count": Factory.objects.for_user(user).filter(is_active=True).count(),
        "production": production_overview(user, today) if can("production.dashboard", "view") else None,
        "sales": sales_overview(user, today) if can("sales.invoice", "view") else None,
        "purchases": purchase_overview(user, today) if can("purchases.po", "view") else None,
        "accounts": accounts_overview(user) if can("ledger.voucher", "view") else None,
        "day": standard.today_figures(user, today),
        "low_stock": StockAlert.visible_to(user).filter(cleared_at__isnull=True).count() if can("inventory.alerts", "view") else None,
    }
    data["attention"] = attention_items(data, user)
    data["can_open_lot"] = can("production.lot", "view")
    return data
