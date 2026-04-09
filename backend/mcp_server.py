"""
Jewel India ERP — MCP Server
=============================
Exposes ERP data as MCP tools for Claude Desktop, ChatGPT, and other AI clients.

Usage (stdio, for Claude Desktop):
    python mcp_server.py

Usage (SSE, for remote/ChatGPT):
    python mcp_server.py --sse --port 8100
"""

import os
import sys
import json
import datetime
from decimal import Decimal

# ---------------------------------------------------------------------------
# Django bootstrap — must happen before any model imports
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jewel_test.settings")

import django
django.setup()

# ---------------------------------------------------------------------------
# MCP SDK
# ---------------------------------------------------------------------------
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Jewel India ERP")

# ---------------------------------------------------------------------------
# Django model imports (after django.setup())
# ---------------------------------------------------------------------------
from mastersconfig.models import RetailMaster
from contacts.models import Ledger
from accounting.models import VoucherMain, VoucherDetail, LedgerOpenBalance, Account
from sales.models import SalesVou, SalesVouItem, CustomerOrder
from purchase.models import PurchaseVoucher
from inventory.models import BarcodeMain, BarcodeDetails
from manufacturing.models import KarigarIssueItem
from goldrates.models import GoldRates
import global_vars

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decimal(val):
    """Convert Decimal to float for JSON serialisation."""
    if isinstance(val, Decimal):
        return float(val)
    return val


def _get_retail(retail_code: str = None):
    """
    Resolve a RetailMaster instance.
    If retail_code is omitted/empty, returns the first retail (single-location setups).
    """
    if retail_code:
        try:
            return RetailMaster.objects.get(retail_code=retail_code)
        except RetailMaster.DoesNotExist:
            return None
    # Default: return first retail
    return RetailMaster.objects.first()


def _fmt_inr(amount):
    """Format amount in Indian style: ₹2,50,000."""
    if amount is None:
        return "₹0"
    amt = float(amount)
    if amt < 0:
        return f"-₹{abs(amt):,.2f}"
    return f"₹{amt:,.2f}"


# ---------------------------------------------------------------------------
# MCP Resource: list available retail locations
# ---------------------------------------------------------------------------

@mcp.resource("erp://retails")
def list_retails() -> str:
    """List all retail locations in the ERP. Use a retail_code in tool calls to target a specific location."""
    retails = RetailMaster.objects.all().values("retail_code", "retail_name", "city", "state__name")
    result = [
        {
            "retail_code": r["retail_code"],
            "name": r["retail_name"],
            "city": r["city"] or "",
            "state": r["state__name"] or "",
        }
        for r in retails
    ]
    return json.dumps(result, indent=2)


@mcp.resource("erp://modules")
def list_modules() -> str:
    """Overview of ERP modules and what data they contain."""
    return json.dumps({
        "accounting": "Journals, payments, receipts, trial balance, P&L, balance sheet, bank reconciliation",
        "sales": "Customer orders, sales vouchers, returns, GST registers, e-way bills",
        "purchase": "Purchase orders, purchase vouchers, returns, TDS/RCM registers",
        "inventory": "Barcoded stock, stock journals, stock transfers, raw materials, stock valuation",
        "manufacturing": "Karigar issue/receive, hallmark, refinery, melting, assay, repair job cards",
        "contacts": "Ledger accounts (customers, vendors, banks, karigar, etc.)",
        "goldrates": "Daily gold rates by purity",
        "mastersconfig": "Company, branch, retail, items, HSN, fiscal year masters",
    }, indent=2)


# ===================================================================
#  SALES TOOLS
# ===================================================================

@mcp.tool()
def get_sales_summary(from_date: str, to_date: str, retail_code: str = "") -> str:
    """Get total sales value, invoice count, and top 5 customers for a date range.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional, defaults to first retail)
    """
    from django.db.models import Sum, Count
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    qs = SalesVou.objects.filter(retail=retail, date1__range=(from_date, to_date))
    agg = qs.aggregate(total=Sum("bill_value"), count=Count("id"))
    top = (
        qs.values("ldgr__ac_name")
        .annotate(total=Sum("bill_value"))
        .order_by("-total")[:5]
    )
    return json.dumps({
        "period": f"{from_date} to {to_date}",
        "total_sales": _decimal(agg["total"] or 0),
        "invoice_count": agg["count"],
        "top_customers": [
            {"name": r["ldgr__ac_name"], "amount": _decimal(r["total"] or 0)} for r in top
        ],
    }, indent=2)


@mcp.tool()
def get_top_customers(from_date: str, to_date: str, retail_code: str = "") -> str:
    """Get top 10 customers by purchase value for a date range.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum, Count
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    qs = (
        SalesVou.objects.filter(retail=retail, date1__range=(from_date, to_date))
        .values("ldgr__ac_name")
        .annotate(total=Sum("bill_value"), count=Count("id"))
        .order_by("-total")[:10]
    )
    return json.dumps({
        "period": f"{from_date} to {to_date}",
        "top_customers": [
            {"name": r["ldgr__ac_name"], "amount": _decimal(r["total"] or 0), "invoices": r["count"]}
            for r in qs
        ],
    }, indent=2)


@mcp.tool()
def get_outstanding_debtors(as_of_date: str = "", retail_code: str = "") -> str:
    """Get customers with outstanding receivables (money owed to us).

    Args:
        as_of_date: As-of date (YYYY-MM-DD, defaults to today)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})
    if not as_of_date:
        as_of_date = str(datetime.date.today())

    qs = (
        SalesVou.objects.filter(retail=retail, date1__lte=as_of_date, due_amt__gt=0)
        .values("ldgr__ac_name")
        .annotate(due=Sum("due_amt"))
        .order_by("-due")[:10]
    )
    total = SalesVou.objects.filter(
        retail=retail, date1__lte=as_of_date, due_amt__gt=0
    ).aggregate(t=Sum("due_amt"))["t"] or 0

    return json.dumps({
        "as_of": as_of_date,
        "total_outstanding": _decimal(total),
        "top_debtors": [{"name": r["ldgr__ac_name"], "due": _decimal(r["due"])} for r in qs],
    }, indent=2)


@mcp.tool()
def get_customer_history(customer_name: str, retail_code: str = "") -> str:
    """Get purchase history for a specific customer.

    Args:
        customer_name: Customer/ledger name (partial match supported)
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    ledger = Ledger.objects.filter(ac_name__icontains=customer_name, retail_code=retail).first()
    if not ledger:
        return json.dumps({"error": f"Customer '{customer_name}' not found."})

    invoices = SalesVou.objects.filter(retail=retail, ldgr=ledger).order_by("-date1")[:20]
    return json.dumps({
        "customer": ledger.ac_name,
        "invoices": [
            {
                "date": str(inv.date1),
                "voucher_no": inv.voucher_no,
                "bill_value": _decimal(inv.bill_value),
                "due_amount": _decimal(inv.due_amt),
            }
            for inv in invoices
        ],
    }, indent=2)


# ===================================================================
#  PURCHASE TOOLS
# ===================================================================

@mcp.tool()
def get_purchase_summary(from_date: str, to_date: str, retail_code: str = "") -> str:
    """Get total purchases, invoice count, and top 5 vendors for a date range.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum, Count
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    qs = PurchaseVoucher.objects.filter(retail=retail, date1__range=(from_date, to_date))
    agg = qs.aggregate(total=Sum("bill_value"), count=Count("id"))
    top = (
        qs.values("ldgr__ac_name")
        .annotate(total=Sum("bill_value"))
        .order_by("-total")[:5]
    )
    return json.dumps({
        "period": f"{from_date} to {to_date}",
        "total_purchases": _decimal(agg["total"] or 0),
        "invoice_count": agg["count"],
        "top_vendors": [
            {"name": r["ldgr__ac_name"], "amount": _decimal(r["total"] or 0)} for r in top
        ],
    }, indent=2)


@mcp.tool()
def get_outstanding_creditors(as_of_date: str = "", retail_code: str = "") -> str:
    """Get vendors with outstanding payables (money we owe).

    Args:
        as_of_date: As-of date (YYYY-MM-DD, defaults to today)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})
    if not as_of_date:
        as_of_date = str(datetime.date.today())

    qs = (
        PurchaseVoucher.objects.filter(retail=retail, date1__lte=as_of_date, due_amt__gt=0)
        .values("ldgr__ac_name")
        .annotate(due=Sum("due_amt"))
        .order_by("-due")[:10]
    )
    total = PurchaseVoucher.objects.filter(
        retail=retail, date1__lte=as_of_date, due_amt__gt=0
    ).aggregate(t=Sum("due_amt"))["t"] or 0

    return json.dumps({
        "as_of": as_of_date,
        "total_outstanding": _decimal(total),
        "top_creditors": [{"name": r["ldgr__ac_name"], "due": _decimal(r["due"])} for r in qs],
    }, indent=2)


# ===================================================================
#  ACCOUNTING TOOLS
# ===================================================================

@mcp.tool()
def get_ledger_balance(ledger_name: str, retail_code: str = "") -> str:
    """Get the current debit/credit balance for a specific ledger account.

    Args:
        ledger_name: Name of the ledger account (partial match supported)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    ledger = Ledger.objects.filter(ac_name__icontains=ledger_name, retail_code=retail).first()
    if not ledger:
        return json.dumps({"error": f"Ledger '{ledger_name}' not found."})

    ob = LedgerOpenBalance.objects.filter(ldgr=ledger, retail=retail).first()
    ob_dr = float(ob.debit if ob else 0)
    ob_cr = float(ob.credit if ob else 0)

    txn = VoucherDetail.objects.filter(
        account=ledger, voucher_main__retail=retail
    ).aggregate(total_dr=Sum("debit"), total_cr=Sum("credit"))

    total_dr = ob_dr + float(txn["total_dr"] or 0)
    total_cr = ob_cr + float(txn["total_cr"] or 0)
    net = total_dr - total_cr

    return json.dumps({
        "ledger": ledger.ac_name,
        "group": str(ledger.ac_group),
        "total_debit": round(total_dr, 2),
        "total_credit": round(total_cr, 2),
        "net_balance": round(abs(net), 2),
        "balance_type": "Dr" if net >= 0 else "Cr",
    }, indent=2)


@mcp.tool()
def get_trial_balance_summary(from_date: str, to_date: str, retail_code: str = "") -> str:
    """Get trial balance totals (total debits and credits) for a period.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    txn = VoucherDetail.objects.filter(
        voucher_main__retail=retail,
        voucher_main__date__range=(from_date, to_date),
    ).aggregate(total_dr=Sum("debit"), total_cr=Sum("credit"))

    return json.dumps({
        "period": f"{from_date} to {to_date}",
        "total_debit": _decimal(txn["total_dr"] or 0),
        "total_credit": _decimal(txn["total_cr"] or 0),
        "balanced": abs(float(txn["total_dr"] or 0) - float(txn["total_cr"] or 0)) < 0.01,
    }, indent=2)


@mcp.tool()
def get_cash_position(retail_code: str = "") -> str:
    """Get current balances of all cash and bank accounts.

    Args:
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    results = []
    cash_ledgers = Ledger.objects.filter(retail_code=retail, type__in=["Cash", "Bank"])
    for ledger in cash_ledgers:
        ob = LedgerOpenBalance.objects.filter(ldgr=ledger, retail=retail).first()
        ob_dr = float(ob.debit if ob else 0)
        ob_cr = float(ob.credit if ob else 0)
        txn = VoucherDetail.objects.filter(
            account=ledger, voucher_main__retail=retail
        ).aggregate(dr=Sum("debit"), cr=Sum("credit"))
        total_dr = ob_dr + float(txn["dr"] or 0)
        total_cr = ob_cr + float(txn["cr"] or 0)
        net = total_dr - total_cr
        results.append({
            "account": ledger.ac_name,
            "type": ledger.type,
            "balance": round(abs(net), 2),
            "balance_type": "Dr" if net >= 0 else "Cr",
        })

    return json.dumps({"cash_and_bank_accounts": results}, indent=2)


@mcp.tool()
def get_day_book(from_date: str, to_date: str, retail_code: str = "") -> str:
    """Get all vouchers (journal entries) for a date range with their debit/credit lines.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    vouchers = (
        VoucherMain.objects.filter(date__range=(from_date, to_date), retail=retail)
        .prefetch_related("transactions__account")
        .order_by("date", "voucher_no")[:100]  # Limit to 100 vouchers
    )

    total_debit = Decimal("0")
    total_credit = Decimal("0")
    result = []
    for v in vouchers:
        lines = []
        for t in v.transactions.all():
            lines.append({
                "account": t.account.ac_name,
                "debit": _decimal(t.debit),
                "credit": _decimal(t.credit),
            })
            total_debit += t.debit
            total_credit += t.credit
        result.append({
            "date": str(v.date),
            "voucher_no": v.voucher_no,
            "voucher_type": v.voucher_type,
            "narration": v.narration or "",
            "amount": _decimal(v.amount),
            "lines": lines,
        })

    return json.dumps({
        "period": f"{from_date} to {to_date}",
        "voucher_count": len(result),
        "total_debit": _decimal(total_debit),
        "total_credit": _decimal(total_credit),
        "vouchers": result,
    }, indent=2)


@mcp.tool()
def get_profit_and_loss(from_date: str, to_date: str, retail_code: str = "") -> str:
    """Get Profit & Loss statement for a date range. Shows sales, COGS, expenses, and net profit.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    # Reuse the existing P&L calculation from accounting views
    from accounting.views import calcuate_pnl
    data = calcuate_pnl(start_date=from_date, end_date=to_date, retail=retail)

    # Convert Decimals for JSON
    clean = {}
    for k, v in data.items():
        if isinstance(v, Decimal):
            clean[k] = float(v)
        elif isinstance(v, (list, dict)):
            clean[k] = json.loads(json.dumps(v, default=str))
        else:
            clean[k] = v

    return json.dumps(clean, indent=2, default=str)


@mcp.tool()
def get_balance_sheet(as_of_date: str = "", retail_code: str = "") -> str:
    """Get Balance Sheet as of a date. Shows assets, liabilities, and net worth.

    Args:
        as_of_date: As-of date (YYYY-MM-DD, defaults to today)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum, F, DecimalField
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})
    if not as_of_date:
        as_of_date = str(datetime.date.today())

    # Transaction balances by account group
    txn_by_group = {}
    for row in VoucherDetail.objects.filter(
        voucher_main__date__lte=as_of_date, voucher_main__retail=retail
    ).values("account__ac_group").annotate(balance=Sum(F("debit")) - Sum(F("credit"))):
        gid = row["account__ac_group"]
        if gid is not None:
            txn_by_group[gid] = row["balance"] or Decimal(0)

    # Opening balances by account group
    ob_by_group = {}
    for row in LedgerOpenBalance.objects.filter(retail=retail).values(
        "ldgr__ac_group"
    ).annotate(balance=Sum(F("debit") - F("credit"), output_field=DecimalField())):
        gid = row["ldgr__ac_group"]
        if gid is not None:
            ob_by_group[gid] = row["balance"] or Decimal(0)

    # Build account tree
    all_accounts = list(Account.objects.all())
    children_map = {}
    account_by_id = {}
    for acc in all_accounts:
        account_by_id[acc.id] = acc
        pid = acc.parent_id
        if pid not in children_map:
            children_map[pid] = []
        children_map[pid].append(acc)

    def get_descendants(parent_id):
        result = []
        for child in children_map.get(parent_id, []):
            result.append(child)
            result.extend(get_descendants(child.id))
        return result

    def get_balance(account):
        return txn_by_group.get(account.id, Decimal(0)) + ob_by_group.get(account.id, Decimal(0))

    def get_group_balance(group_name):
        parent = next((a for a in all_accounts if a.name == group_name), None)
        if not parent:
            return {"total": 0, "accounts": []}
        descendants = get_descendants(parent.id)
        total = Decimal(0)
        accounts = []
        for acc in descendants:
            bal = get_balance(acc)
            if bal != 0:
                accounts.append({"name": acc.name, "balance": _decimal(bal)})
            total += bal
        return {"total": _decimal(total), "accounts": accounts}

    assets = get_group_balance("Assets")
    liabilities = get_group_balance("Liabilities")

    # Add net profit to liabilities side
    from accounting.views import calcuate_pnl
    pnl = calcuate_pnl("2000-01-01", as_of_date, retail=retail)
    net_profit = float(pnl.get("net_profit", 0))
    liabilities["total"] = _decimal(Decimal(str(liabilities["total"])) + Decimal(str(net_profit)))

    return json.dumps({
        "as_of": as_of_date,
        "assets": assets,
        "liabilities": liabilities,
        "net_profit_added_to_liabilities": net_profit,
    }, indent=2, default=str)


@mcp.tool()
def search_ledgers(query: str, retail_code: str = "") -> str:
    """Search for ledger accounts by name. Useful for finding exact account names.

    Args:
        query: Search text (partial name match)
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    ledgers = Ledger.objects.filter(
        ac_name__icontains=query, retail_code=retail
    ).select_related("ac_group")[:20]

    return json.dumps({
        "query": query,
        "results": [
            {
                "name": l.ac_name,
                "group": l.ac_group.name if l.ac_group else "",
                "type": l.type or "",
                "code": l.ldgr_code or "",
            }
            for l in ledgers
        ],
    }, indent=2)


@mcp.tool()
def get_gst_summary(from_date: str, to_date: str, retail_code: str = "") -> str:
    """Get GST summary — output GST (from sales) and input GST (from purchases) for a period.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    sales = SalesVou.objects.filter(
        retail=retail, date1__range=(from_date, to_date)
    ).aggregate(cgst=Sum("cgst_value"), sgst=Sum("sgst_value"), igst=Sum("igst_value"))

    purchases = PurchaseVoucher.objects.filter(
        retail=retail, date1__range=(from_date, to_date)
    ).aggregate(cgst=Sum("cgst_value"), sgst=Sum("sgst_value"), igst=Sum("igst_value"))

    return json.dumps({
        "period": f"{from_date} to {to_date}",
        "output_gst": {
            "cgst": _decimal(sales["cgst"] or 0),
            "sgst": _decimal(sales["sgst"] or 0),
            "igst": _decimal(sales["igst"] or 0),
        },
        "input_gst": {
            "cgst": _decimal(purchases["cgst"] or 0),
            "sgst": _decimal(purchases["sgst"] or 0),
            "igst": _decimal(purchases["igst"] or 0),
        },
    }, indent=2)


# ===================================================================
#  INVENTORY TOOLS
# ===================================================================

@mcp.tool()
def get_stock_summary(retail_code: str = "") -> str:
    """Get current inventory stock count by item type.

    Args:
        retail_code: Retail location code (optional)
    """
    from django.db.models import Count
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    qs = (
        BarcodeMain.objects.filter(retail=retail, stk_status=True)
        .values("item__item_name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    total = BarcodeMain.objects.filter(retail=retail, stk_status=True).count()

    return json.dumps({
        "total_barcodes_in_stock": total,
        "by_item": [{"item": r["item__item_name"], "count": r["count"]} for r in qs[:15]],
    }, indent=2)


@mcp.tool()
def get_stock_valuation(retail_code: str = "", item_filter: str = "", purity_filter: str = "") -> str:
    """Get stock valuation — list barcoded items in stock with their values.

    Args:
        retail_code: Retail location code (optional)
        item_filter: Filter by item ID (optional)
        purity_filter: Filter by purity (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    barcodes = BarcodeMain.objects.filter(retail=retail, stk_status=True)
    if purity_filter:
        barcodes = barcodes.filter(purity=purity_filter)

    stock_data = []
    total_value = Decimal("0")
    for bc in barcodes[:50]:  # Limit to 50 items
        val = bc.total_amount or Decimal("0")
        total_value += val
        stock_data.append({
            "barcode": bc.barcode,
            "pcs": bc.pcs,
            "gross_wt": _decimal(bc.gw),
            "net_wt": _decimal(bc.nw),
            "purity": bc.purity,
            "making_value": _decimal(bc.making_val),
            "total_value": _decimal(val),
        })

    return json.dumps({
        "items_shown": len(stock_data),
        "total_value": _decimal(total_value),
        "stock": stock_data,
    }, indent=2)


# ===================================================================
#  GOLD RATES
# ===================================================================

@mcp.tool()
def get_gold_rates() -> str:
    """Get current gold rates per gram for all purities."""
    rates = GoldRates.objects.select_related("purity").order_by("-date1")[:20]
    seen = {}
    for r in rates:
        name = r.purity.purity if r.purity else "Unknown"
        if name not in seen:
            seen[name] = {"rate_per_gram": _decimal(r.rate), "date": str(r.date1)}
    return json.dumps({"gold_rates": list(seen.values())}, indent=2)


# ===================================================================
#  MANUFACTURING TOOLS
# ===================================================================

@mcp.tool()
def get_karigar_jobs_status(retail_code: str = "") -> str:
    """Get summary of karigar (artisan) job orders — open vs closed.

    Args:
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    total = KarigarIssueItem.objects.filter(retail=retail).count()
    open_jobs = KarigarIssueItem.objects.filter(retail=retail, rec_status=False).count()
    return json.dumps({
        "total_jobs": total,
        "open_jobs": open_jobs,
        "closed_jobs": total - open_jobs,
    }, indent=2)


# ===================================================================
#  AD-HOC QUERY TOOL
# ===================================================================

@mcp.tool()
def get_invoice_details(voucher_no: str, retail_code: str = "") -> str:
    """Look up a specific sales or purchase invoice by voucher number.

    Args:
        voucher_no: The voucher/invoice number to look up
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    # Try sales first
    sale = SalesVou.objects.filter(retail=retail, voucher_no=voucher_no).first()
    if sale:
        items = SalesVouItem.objects.filter(sales_vou=sale)
        return json.dumps({
            "type": "Sales Invoice",
            "voucher_no": sale.voucher_no,
            "date": str(sale.date1),
            "customer": sale.ldgr.ac_name if sale.ldgr else "",
            "bill_value": _decimal(sale.bill_value),
            "due_amount": _decimal(sale.due_amt),
            "items": [
                {
                    "barcode": str(item.barcode) if hasattr(item, "barcode") and item.barcode else "",
                    "amount": _decimal(item.amount) if hasattr(item, "amount") else 0,
                }
                for item in items[:20]
            ],
        }, indent=2, default=str)

    # Try purchase
    purchase = PurchaseVoucher.objects.filter(retail=retail, voucher_no=voucher_no).first()
    if purchase:
        return json.dumps({
            "type": "Purchase Invoice",
            "voucher_no": purchase.voucher_no,
            "date": str(purchase.date1),
            "vendor": purchase.ldgr.ac_name if purchase.ldgr else "",
            "bill_value": _decimal(purchase.bill_value),
            "due_amount": _decimal(purchase.due_amt),
        }, indent=2, default=str)

    return json.dumps({"error": f"Invoice '{voucher_no}' not found."})


@mcp.tool()
def get_dashboard_summary(retail_code: str = "") -> str:
    """Get a quick dashboard summary — today's sales, pending orders, stock count, cash position.

    Args:
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum, Count
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    today = datetime.date.today()
    fy_start = datetime.date(today.year if today.month >= 4 else today.year - 1, 4, 1)

    # Today's sales
    today_sales = SalesVou.objects.filter(
        retail=retail, date1=today
    ).aggregate(total=Sum("bill_value"), count=Count("id"))

    # FY sales
    fy_sales = SalesVou.objects.filter(
        retail=retail, date1__range=(fy_start, today)
    ).aggregate(total=Sum("bill_value"))

    # Stock count
    stock_count = BarcodeMain.objects.filter(retail=retail, stk_status=True).count()

    # Outstanding receivables
    receivables = SalesVou.objects.filter(
        retail=retail, due_amt__gt=0
    ).aggregate(total=Sum("due_amt"))

    # Outstanding payables
    payables = PurchaseVoucher.objects.filter(
        retail=retail, due_amt__gt=0
    ).aggregate(total=Sum("due_amt"))

    return json.dumps({
        "date": str(today),
        "retail": retail.retail_name,
        "today_sales": _decimal(today_sales["total"] or 0),
        "today_invoice_count": today_sales["count"],
        "fy_sales": _decimal(fy_sales["total"] or 0),
        "stock_barcodes": stock_count,
        "total_receivables": _decimal(receivables["total"] or 0),
        "total_payables": _decimal(payables["total"] or 0),
    }, indent=2)


# ===================================================================
#  GOLD SCHEME TOOLS
# ===================================================================

@mcp.tool()
def get_scheme_summary(retail_code: str = "") -> str:
    """Get gold scheme dashboard KPIs — active enrollments, total collections, upcoming maturities.

    Args:
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    from goldscheme.services.reports import scheme_summary
    return json.dumps(scheme_summary(retail), indent=2, default=str)


@mcp.tool()
def get_scheme_enrollments(customer_name: str = "", status_filter: str = "", retail_code: str = "") -> str:
    """List gold scheme enrollments, optionally filtered by customer name or status.

    Args:
        customer_name: Filter by customer name (partial match, optional)
        status_filter: Filter by status: ACTIVE, MATURED, REDEEMED, CANCELLED (optional)
        retail_code: Retail location code (optional)
    """
    from goldscheme.models import SchemeEnrollment
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    qs = SchemeEnrollment.objects.filter(retail=retail).select_related('customer', 'scheme')
    if customer_name:
        qs = qs.filter(customer__ac_name__icontains=customer_name)
    if status_filter:
        qs = qs.filter(status=status_filter.upper())

    enrollments = []
    for e in qs[:30]:
        enrollments.append({
            "enrollment_no": e.enrollment_no,
            "customer": e.customer.ac_name,
            "scheme": e.scheme.name,
            "scheme_type": e.scheme.scheme_type,
            "start_date": str(e.start_date),
            "maturity_date": str(e.maturity_date),
            "installment_amount": _decimal(e.installment_amount),
            "total_paid": _decimal(e.total_paid),
            "payments_made": e.payments_made,
            "gold_accumulated_wt": _decimal(e.gold_accumulated_wt),
            "status": e.status,
            "months_completed": e.months_completed,
        })

    return json.dumps({"count": len(enrollments), "enrollments": enrollments}, indent=2)


@mcp.tool()
def get_scheme_maturity_calendar(from_date: str, to_date: str, retail_code: str = "") -> str:
    """List gold scheme enrollments maturing within a date range.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    from goldscheme.services.reports import maturity_calendar
    return json.dumps(maturity_calendar(retail, from_date, to_date), indent=2, default=str)


@mcp.tool()
def get_scheme_overdue_payments(retail_code: str = "") -> str:
    """Find gold scheme enrollments with missed/overdue installment payments.

    Args:
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    from goldscheme.services.reports import overdue_payments
    return json.dumps(overdue_payments(retail), indent=2, default=str)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Jewel India ERP MCP Server")
    parser.add_argument("--sse", action="store_true", help="Run with SSE transport (for remote clients)")
    parser.add_argument("--port", type=int, default=8100, help="Port for SSE transport (default: 8100)")
    args = parser.parse_args()

    if args.sse:
        mcp.run(transport="sse", host="0.0.0.0", port=args.port)
    else:
        mcp.run()
