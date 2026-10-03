"""Standard operating reports (E10.1, E10.2, BRD RPT-01, RPT-05, RPT-06) and today's figures for the home dashboard.
Read-only; every query is scoped to the factories the user may see."""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from inventory.models import StockBalance, StockMovement
from inventory.services.alerts import STOCKROOMS
from ledger.models import VoucherLine
from ledger.selectors import posted_lines, q2
from production.models import CuttingSize, StageMovement
from purchases.models import PurchaseInvoice, PurchaseInvoiceLine
from sales.models import SaleCreditNote, SaleCreditNoteLine, SaleInvoice, SaleInvoiceLine

ZERO = Decimal("0.00")
SALES_VIEWS = ("customer", "style", "day", "agent")


def _key(by, invoice, sku, on=None):
    if by == "style":
        return f"{sku.style.style_no} {sku.style.name}"
    if by == "day":
        return (on or invoice.date).isoformat()
    if by == "agent":
        return invoice.customer.agent.name if invoice.customer.agent_id else "No agent"
    return invoice.customer.name


def sales_report(*, user, factory=None, date_from, date_to, by="customer"):
    """Pieces, value and GST sold per customer, style, day or agent, less the pieces and value returned on credit notes."""
    by = by if by in SALES_VIEWS else "customer"
    rows = defaultdict(lambda: {"pieces": ZERO, "value": ZERO, "gst": ZERO, "returned_pieces": ZERO, "returned_value": ZERO})
    inv_qs = SaleInvoice.objects.for_user(user).filter(status="posted", date__range=(date_from, date_to))
    if factory is not None:
        inv_qs = inv_qs.filter(factory=factory)
    for l in SaleInvoiceLine.objects.filter(invoice__in=inv_qs).select_related("invoice__customer__agent", "sku__style"):
        r = rows[_key(by, l.invoice, l.sku)]
        r["pieces"] += l.qty
        r["value"] += l.amount
        r["gst"] += l.tax_amount
    notes = SaleCreditNote.objects.for_user(user).filter(status="posted", date__range=(date_from, date_to))
    if factory is not None:
        notes = notes.filter(factory=factory)
    for c in SaleCreditNoteLine.objects.filter(note__in=notes).select_related("note", "invoice_line__invoice__customer__agent", "invoice_line__sku__style"):
        r = rows[_key(by, c.invoice_line.invoice, c.invoice_line.sku, c.note.date)]
        r["returned_pieces"] += c.qty
        r["returned_value"] += c.amount
    out = []
    for key, r in sorted(rows.items(), key=lambda kv: (kv[0] if by == "day" else -kv[1]["value"], kv[0])):
        out.append({"key": key, **r, "net_pieces": r["pieces"] - r["returned_pieces"], "net_value": r["value"] - r["returned_value"]})
    total = {k: sum((r[k] for r in out), ZERO) for k in ("pieces", "value", "gst", "returned_pieces", "returned_value", "net_pieces", "net_value")}
    return {"rows": out, "total": total, "by": by}


def purchase_report(*, user, factory=None, date_from, date_to, by="vendor"):
    qs = PurchaseInvoice.objects.for_user(user).filter(status="posted", date__range=(date_from, date_to)).select_related("vendor")
    if factory is not None:
        qs = qs.filter(factory=factory)
    rows = defaultdict(lambda: {"bills": 0, "value": ZERO, "gst": ZERO, "payable": ZERO, "variances": 0})
    for inv in qs:
        r = rows[inv.date.strftime("%Y-%m") if by == "month" else inv.vendor.name]
        r["bills"] += 1
        r["value"] += inv.subtotal
        r["gst"] += inv.gst_total
        r["payable"] += inv.payable
        r["variances"] += PurchaseInvoiceLine.objects.filter(invoice=inv, rate_variance=True).count()
    out = [{"key": k, **v} for k, v in sorted(rows.items(), key=lambda kv: kv[0] if by == "month" else -kv[1]["value"])]
    total = {k: sum((r[k] for r in out), ZERO) for k in ("bills", "value", "gst", "payable", "variances")}
    return {"rows": out, "total": total, "by": by}


def finished_stock(*, user, factory=None, today=None, slow_days=60):
    """Finished goods on hand by SKU with the days since they came in and since one last sold (RPT-05)."""
    today = today or date.today()
    ids = user.allowed_factory_ids()
    bal = StockBalance.objects.filter(sku__isnull=False, location__loc_type__in=STOCKROOMS, qty__gt=0).select_related(
        "sku__style", "sku__colour", "sku__size", "factory")
    if ids is not None:
        bal = bal.filter(factory_id__in=ids)
    if factory is not None:
        bal = bal.filter(factory=factory)
    per_sku = defaultdict(lambda: {"qty": ZERO, "value": ZERO})
    for b in bal:
        per_sku[b.sku]["qty"] += b.qty
        per_sku[b.sku]["value"] += b.value
    rows = []
    for sku, v in per_sku.items():
        moves = StockMovement.objects.filter(sku=sku)
        if ids is not None:
            moves = moves.filter(factory_id__in=ids)
        last_in = moves.filter(qty__gt=0).exclude(movement_type="reversal").order_by("-date").values_list("date", flat=True).first()
        last_out = moves.filter(movement_type="issue").order_by("-date").values_list("date", flat=True).first()
        age = (today - last_in).days if last_in else None
        slow = last_out is None and (age or 0) >= slow_days or (last_out is not None and (today - last_out).days >= slow_days)
        rows.append({"sku": sku, "qty": v["qty"], "value": q2(v["value"]), "last_in": last_in, "last_out": last_out, "age": age, "slow": slow})
    rows.sort(key=lambda r: (not r["slow"], -(r["age"] or 0), str(r["sku"])))
    return {"rows": rows, "pieces": sum((r["qty"] for r in rows), ZERO), "value": sum((r["value"] for r in rows), ZERO),
            "slow_count": sum(1 for r in rows if r["slow"]), "slow_days": slow_days}


def today_figures(user, today):
    """The home dashboard's day: sales and collections, pieces cut and packed, receivables overdue (E10.1)."""
    out = {}
    can = user.has_screen_perm
    if can("sales.invoice", "view"):
        inv = SaleInvoice.objects.for_user(user).filter(status="posted", date=today)
        out["sales_today"] = inv.aggregate(s=Sum("total"))["s"] or ZERO
        out["invoices_today"] = inv.count()
    if can("ledger.report", "view"):
        cash = posted_lines(user, None, today, today).filter(voucher__voucher_type="receipt", ledger__group__name__in=("Cash-in-hand", "Bank Accounts"))
        out["collections_today"] = q2(cash.aggregate(d=Sum("debit"))["d"])
    if can("production.dashboard", "view"):
        cut = CuttingSize.objects.filter(entry__date=today, entry__in=_scoped(user, "production", "CuttingEntry"))
        out["cut_today"] = cut.aggregate(p=Sum("pieces"))["p"] or 0
        packed = StageMovement.objects.for_user(user).filter(kind="pack", at__date=today)
        out["packed_today"] = packed.aggregate(q=Sum("qty_in"))["q"] or 0
    return out


def _scoped(user, app, model):
    from django.apps import apps

    return apps.get_model(app, model).objects.for_user(user)
