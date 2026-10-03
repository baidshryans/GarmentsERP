"""Read-only figures for the home dashboard (E10). Every query is factory-scoped for the user, and each
section is built only if the user's role may see that screen, so production roles never get money (BR-15)."""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from core.models import Factory
from jobwork.models import JobWorkChallan, Receipt
from ledger.models import Voucher
from production.models import Bundle, Lot, ProductionOrder
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
    cut = dict(Bundle.objects.filter(lot__in=lots).values_list("lot_id").annotate(s=Sum("original_qty")))
    rows = []
    for lot in lots:
        order = lot.order_line.order
        rows.append({
            "lot": lot, "order": order, "planned": lot.order_line.total_qty, "cut": cut.get(lot.pk, 0),
            "wip": wip.get(lot.pk, 0),
            "stages": ", ".join(f"{n} {q}" for n, q in sorted(stages[lot.pk].items(), key=lambda kv: -kv[1])) or "Not cut yet",
            "where": ", ".join(sorted(holders[lot.pk])) or "-",
            "late": bool(order.due_date and order.due_date < today),
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
    return data
