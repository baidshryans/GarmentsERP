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
from django.apps import apps as _django_apps

# Bootstrap Django only if it hasn't been configured yet. This lets the module be
# imported from an already-running Django process (e.g. the ERP chat's shared tool
# registry) without triggering a second, reentrant setup().
if not _django_apps.ready:
    django.setup()

# ---------------------------------------------------------------------------
# MCP SDK
# ---------------------------------------------------------------------------
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Jewel India ERP")

# ---------------------------------------------------------------------------
# Django model imports (after django.setup())
# ---------------------------------------------------------------------------
from mastersconfig.models import RetailMaster, FiscalYearMaster
from contacts.models import Ledger
from accounting.models import VoucherMain, VoucherDetail, LedgerOpenBalance, Account
from sales.models import SalesVou, SalesVouItem, CustomerOrder, SalesApprovalItem
from purchase.models import PurchaseVoucher
from inventory.models import BarcodeMain, BarcodeDetails, BarcodeTransaction
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


def _sales_exprs():
    """
    Database expressions for SalesVou monetary values.

    Thin wrapper over sales.expressions.sales_exprs(), which is the single
    definition shared with customer_intel and anything else that needs to
    aggregate bill values in SQL. Imported lazily because this module is
    imported before django.setup() in some entry paths.
    """
    from sales.expressions import sales_exprs

    return sales_exprs()


# Ledger account-groups that represent liquid funds (cash & bank).
_CASH_BANK_GROUPS = ["Cash-in-Hand", "Bank Accounts", "Bank OD Accounts"]


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
        "manufacturing": "Karigar issue/receive, hallmark, refinery, melting, repair job cards",
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

    bill = _sales_exprs()["bill"]
    qs = SalesVou.objects.filter(retail=retail, date1__range=(from_date, to_date))
    agg = qs.aggregate(total=Sum(bill), count=Count("id"))
    top = (
        qs.values("ldgr__ac_name")
        .annotate(total=Sum(bill))
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
        .annotate(total=Sum(_sales_exprs()["bill"]), count=Count("id"))
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
    cash_ledgers = Ledger.objects.filter(
        retail_code=retail, ac_group__name__in=_CASH_BANK_GROUPS
    ).select_related("ac_group")
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
            "type": ledger.ac_group.name if ledger.ac_group else "",
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
                "display_name": l.display_name or l.ac_name,
                "group": l.ac_group.name if l.ac_group else "",
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

    se = _sales_exprs()
    sales = SalesVou.objects.filter(
        retail=retail, date1__range=(from_date, to_date)
    ).aggregate(cgst=Sum(se["cgst"]), sgst=Sum(se["sgst"]), igst=Sum(se["igst"]))

    # PurchaseVoucher stores GST amounts as real columns (cgst/sgst/igst).
    purchases = PurchaseVoucher.objects.filter(
        retail=retail, date1__range=(from_date, to_date)
    ).aggregate(cgst=Sum("cgst"), sgst=Sum("sgst"), igst=Sum("igst"))

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

    barcodes = BarcodeMain.objects.filter(
        retail=retail, stk_status=True
    ).select_related("purity")
    if purity_filter:
        barcodes = barcodes.filter(purity__purity__icontains=purity_filter)

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
            "purity": str(bc.purity) if bc.purity else "",
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

    # Try sales first (invoices are identified by billno)
    sale = SalesVou.objects.filter(retail=retail, billno=voucher_no).select_related("ldgr").first()
    if sale:
        # On SalesVouItem, billno is a FK back to the SalesVou header.
        items = SalesVouItem.objects.filter(retail=retail, billno=sale).select_related("barcode")
        return json.dumps({
            "type": "Sales Invoice",
            "voucher_no": sale.billno,
            "date": str(sale.date1),
            "customer": sale.ldgr.ac_name if sale.ldgr else "",
            "bill_value": _decimal(sale.total_bill_value),
            "due_amount": _decimal(sale.due_amt),
            "items": [
                {
                    "barcode": str(item.barcode) if item.barcode else "",
                    "amount": _decimal(item.amount),
                }
                for item in items[:20]
            ],
        }, indent=2, default=str)

    # Try purchase
    purchase = PurchaseVoucher.objects.filter(retail=retail, billno=voucher_no).select_related("ldgr").first()
    if purchase:
        return json.dumps({
            "type": "Purchase Invoice",
            "voucher_no": purchase.billno,
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
    active_fy = getattr(retail, 'active_fy', None)
    fy_start = active_fy.fy_start if active_fy else datetime.date(today.year if today.month >= 4 else today.year - 1, 4, 1)

    # Today's sales
    today_sales = SalesVou.objects.filter(
        retail=retail, date1=today
    ).aggregate(total=Sum(_sales_exprs()["bill"]), count=Count("id"))

    # FY sales
    fy_sales = SalesVou.objects.filter(
        retail=retail, date1__range=(fy_start, today)
    ).aggregate(total=Sum(_sales_exprs()["bill"]))

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


# ===================================================================
#  COMPARISON / MULTI-PERIOD TOOLS
# ===================================================================

@mcp.tool()
def compare_profit_and_loss(
    period1_from: str,
    period1_to: str,
    period2_from: str,
    period2_to: str,
    retail_code: str = "",
) -> str:
    """Compare Profit & Loss statements across two periods (e.g. two financial years).

    Returns both periods side-by-side with absolute and percentage change.

    Args:
        period1_from: Period 1 start date (YYYY-MM-DD)
        period1_to:   Period 1 end date   (YYYY-MM-DD)
        period2_from: Period 2 start date (YYYY-MM-DD)
        period2_to:   Period 2 end date   (YYYY-MM-DD)
        retail_code:  Retail location code (optional)
    """
    from accounting.views import calcuate_pnl
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    def _pnl(start, end):
        data = calcuate_pnl(start_date=start, end_date=end, retail=retail)
        return {k: float(v) if isinstance(v, Decimal) else v for k, v in data.items()}

    p1 = _pnl(period1_from, period1_to)
    p2 = _pnl(period2_from, period2_to)

    def _change(v1, v2):
        try:
            v1f, v2f = float(v1), float(v2)
            diff = v2f - v1f
            pct = (diff / v1f * 100) if v1f != 0 else None
            return {"period1": round(v1f, 2), "period2": round(v2f, 2),
                    "change": round(diff, 2), "change_pct": round(pct, 2) if pct is not None else None}
        except (TypeError, ValueError):
            return {"period1": v1, "period2": v2}

    numeric_keys = ["total_income", "total_direct_expense", "gross_profit",
                    "total_indirect_expense", "net_profit"]
    comparison = {}
    for key in numeric_keys:
        comparison[key] = _change(p1.get(key, 0), p2.get(key, 0))

    return json.dumps({
        "period1": f"{period1_from} to {period1_to}",
        "period2": f"{period2_from} to {period2_to}",
        "comparison": comparison,
        "period1_detail": p1,
        "period2_detail": p2,
    }, indent=2, default=str)


@mcp.tool()
def compare_balance_sheet(
    date1: str,
    date2: str,
    retail_code: str = "",
) -> str:
    """Compare Balance Sheet at two different dates (e.g. end of two financial years).

    Returns assets and liabilities for both dates with the movement.

    Args:
        date1:       First as-of date  (YYYY-MM-DD)
        date2:       Second as-of date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum, F, DecimalField
    from accounting.views import calcuate_pnl
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    def _build_bs(as_of_date):
        txn_by_group = {}
        for row in VoucherDetail.objects.filter(
            voucher_main__date__lte=as_of_date, voucher_main__retail=retail
        ).values("account__ac_group").annotate(balance=Sum(F("debit")) - Sum(F("credit"))):
            gid = row["account__ac_group"]
            if gid is not None:
                txn_by_group[gid] = row["balance"] or Decimal(0)

        ob_by_group = {}
        for row in LedgerOpenBalance.objects.filter(retail=retail).values(
            "ldgr__ac_group"
        ).annotate(balance=Sum(F("debit") - F("credit"), output_field=DecimalField())):
            gid = row["ldgr__ac_group"]
            if gid is not None:
                ob_by_group[gid] = row["balance"] or Decimal(0)

        all_accounts = list(Account.objects.all())
        children_map = {}
        for acc in all_accounts:
            pid = acc.parent_id
            children_map.setdefault(pid, []).append(acc)

        def get_descendants(pid):
            result = []
            for child in children_map.get(pid, []):
                result.append(child)
                result.extend(get_descendants(child.id))
            return result

        def group_total(group_name):
            parent = next((a for a in all_accounts if a.name == group_name), None)
            if not parent:
                return 0.0
            total = Decimal(0)
            for acc in get_descendants(parent.id):
                total += txn_by_group.get(acc.id, Decimal(0)) + ob_by_group.get(acc.id, Decimal(0))
            return float(total)

        pnl = calcuate_pnl("2000-01-01", as_of_date, retail=retail)
        net_profit = float(pnl.get("net_profit", 0))
        assets = group_total("Assets")
        liabilities = group_total("Liabilities") + net_profit
        return {"assets": round(assets, 2), "liabilities": round(liabilities, 2),
                "net_profit": round(net_profit, 2)}

    bs1 = _build_bs(date1)
    bs2 = _build_bs(date2)

    def _chg(v1, v2):
        diff = round(v2 - v1, 2)
        pct = round(diff / v1 * 100, 2) if v1 != 0 else None
        return {"date1": v1, "date2": v2, "change": diff, "change_pct": pct}

    return json.dumps({
        "date1": date1,
        "date2": date2,
        "assets":      _chg(bs1["assets"],      bs2["assets"]),
        "liabilities": _chg(bs1["liabilities"], bs2["liabilities"]),
        "net_profit":  _chg(bs1["net_profit"],  bs2["net_profit"]),
        "balance_sheet_date1": bs1,
        "balance_sheet_date2": bs2,
    }, indent=2)


@mcp.tool()
def compare_sales(
    period1_from: str,
    period1_to: str,
    period2_from: str,
    period2_to: str,
    retail_code: str = "",
) -> str:
    """Compare sales performance across two periods — total, count, average ticket, and top customers.

    Args:
        period1_from: Period 1 start date (YYYY-MM-DD)
        period1_to:   Period 1 end date   (YYYY-MM-DD)
        period2_from: Period 2 start date (YYYY-MM-DD)
        period2_to:   Period 2 end date   (YYYY-MM-DD)
        retail_code:  Retail location code (optional)
    """
    from django.db.models import Sum, Count, Avg
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    def _stats(from_d, to_d):
        qs = SalesVou.objects.filter(retail=retail, date1__range=(from_d, to_d))
        agg = qs.aggregate(
            total=Sum(_sales_exprs()["bill"]),
            count=Count("id"),
            avg=Avg(_sales_exprs()["bill"]),
        )
        top = list(
            qs.values("ldgr__ac_name")
            .annotate(amt=Sum(_sales_exprs()["bill"]))
            .order_by("-amt")[:5]
        )
        return {
            "total": float(agg["total"] or 0),
            "count": agg["count"],
            "avg_ticket": round(float(agg["avg"] or 0), 2),
            "top_customers": [{"name": r["ldgr__ac_name"], "amount": float(r["amt"] or 0)} for r in top],
        }

    s1 = _stats(period1_from, period1_to)
    s2 = _stats(period2_from, period2_to)

    def _chg(v1, v2):
        diff = round(v2 - v1, 2)
        pct = round(diff / v1 * 100, 2) if v1 != 0 else None
        return {"period1": round(v1, 2), "period2": round(v2, 2), "change": diff, "change_pct": pct}

    return json.dumps({
        "period1": f"{period1_from} to {period1_to}",
        "period2": f"{period2_from} to {period2_to}",
        "total_sales":  _chg(s1["total"], s2["total"]),
        "invoice_count": _chg(s1["count"], s2["count"]),
        "avg_ticket":   _chg(s1["avg_ticket"], s2["avg_ticket"]),
        "period1_detail": s1,
        "period2_detail": s2,
    }, indent=2)


@mcp.tool()
def get_monthly_sales_trend(year: int, retail_code: str = "") -> str:
    """Get month-by-month sales figures for a calendar or financial year.

    Args:
        year:        Calendar year (e.g. 2025). Returns Apr–Mar for that financial year.
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    # Financial year: Apr year → Mar year+1
    fy_start = datetime.date(year, 4, 1)
    fy_end   = datetime.date(year + 1, 3, 31)

    monthly = []
    cursor = fy_start
    while cursor <= fy_end:
        month_end = (cursor.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
        if month_end > fy_end:
            month_end = fy_end
        total = SalesVou.objects.filter(
            retail=retail, date1__range=(cursor, month_end)
        ).aggregate(t=Sum(_sales_exprs()["bill"]))["t"] or 0
        monthly.append({
            "month": cursor.strftime("%b %Y"),
            "from": str(cursor),
            "to": str(month_end),
            "sales": round(float(total), 2),
        })
        cursor = month_end + datetime.timedelta(days=1)

    fy_total = sum(m["sales"] for m in monthly)
    return json.dumps({
        "financial_year": f"FY {year}-{str(year + 1)[-2:]}",
        "total": round(fy_total, 2),
        "monthly": monthly,
    }, indent=2)


# ===================================================================
#  FINANCIAL-YEAR-AWARE COMPARISON TOOLS
# ===================================================================

@mcp.tool()
def list_financial_years(retail_code: str = "") -> str:
    """List all financial years configured in the ERP for a retail location.

    Use the fy_code values (e.g. "24-25") as inputs to compare_pnl_by_fy
    and compare_balance_sheet_by_fy.

    Args:
        retail_code: Retail location code (optional, defaults to first retail)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    fys = FiscalYearMaster.objects.order_by("fy_start")
    return json.dumps({
        "retail": retail.retail_name,
        "financial_years": [
            {
                "fy_code": fy.fy_code,
                "label": f"FY {fy.fy_code}",
                "from": str(fy.fy_start),
                "to": str(fy.fy_end),
                "is_closed": fy.is_closed,
            }
            for fy in fys
        ],
    }, indent=2)


def _resolve_fy(fy_code: str, retail) -> dict | None:
    """Return the FiscalYearMaster row for a given fy_code, or None."""
    return FiscalYearMaster.objects.filter(fy_code=fy_code).first()


@mcp.tool()
def compare_pnl_by_fy(
    fy_code1: str,
    fy_code2: str,
    retail_code: str = "",
) -> str:
    """Compare Profit & Loss statements across two financial years.

    Pass the fy_code values from list_financial_years (e.g. "23-24" and "24-25").
    Returns a structured comparison with absolute and percentage change for every
    P&L line: gross sales, sales returns, purchases, COGS, gross profit,
    direct expenses, indirect expenses, and net profit.

    Args:
        fy_code1:    First financial year code  (e.g. "23-24")
        fy_code2:    Second financial year code (e.g. "24-25")
        retail_code: Retail location code (optional)
    """
    from accounting.views import calcuate_pnl

    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    fy1 = _resolve_fy(fy_code1, retail)
    fy2 = _resolve_fy(fy_code2, retail)
    missing = [c for c, f in [(fy_code1, fy1), (fy_code2, fy2)] if f is None]
    if missing:
        return json.dumps({"error": f"Financial year(s) not found: {', '.join(missing)}. Use list_financial_years to see available codes."})

    def _pnl(fy):
        raw = calcuate_pnl(start_date=str(fy.fy_start), end_date=str(fy.fy_end), retail=retail)
        return {k: float(v) if isinstance(v, Decimal) else v for k, v in raw.items()}

    p1 = _pnl(fy1)
    p2 = _pnl(fy2)

    def _row(key):
        v1 = float(p1.get(key, 0) or 0)
        v2 = float(p2.get(key, 0) or 0)
        diff = round(v2 - v1, 2)
        pct  = round(diff / v1 * 100, 2) if v1 != 0 else None
        return {
            f"fy_{fy_code1}": round(v1, 2),
            f"fy_{fy_code2}": round(v2, 2),
            "change":         diff,
            "change_pct":     pct,
        }

    comparison = {
        "gross_sales":            _row("gross_sales"),
        "sales_returns":          _row("sales_return"),
        "net_sales_revenue":      _row("sales_revenue"),
        "opening_stock":          _row("opening_stock"),
        "purchases":              _row("purchases"),
        "purchase_returns":       _row("purchase_returns"),
        "closing_stock":          _row("closing_stock"),
        "cogs":                   _row("cogs"),
        "gross_profit":           _row("gross_profit"),
        "direct_expenses":        _row("direct_expenses_total"),
        "indirect_expenses":      _row("indirect_expenses_total"),
        "total_expenses":         _row("total_expenses"),
        "net_profit":             _row("net_profit"),
    }

    return json.dumps({
        "comparison_type": "Profit & Loss — Year on Year",
        "fy1": {"code": fy_code1, "period": f"{fy1.fy_start} to {fy1.fy_end}"},
        "fy2": {"code": fy_code2, "period": f"{fy2.fy_start} to {fy2.fy_end}"},
        "line_items": comparison,
        "note": "change = fy2 − fy1. Positive change_pct on net_profit means improvement.",
    }, indent=2)


@mcp.tool()
def compare_balance_sheet_by_fy(
    fy_code1: str,
    fy_code2: str,
    retail_code: str = "",
) -> str:
    """Compare Balance Sheets at the closing dates of two financial years.

    Pass the fy_code values from list_financial_years (e.g. "23-24" and "24-25").
    The balance sheet is evaluated as of the last day of each FY (fy_end).
    Returns assets, liabilities, and net-worth side-by-side with movement.

    Args:
        fy_code1:    First financial year code  (e.g. "23-24")
        fy_code2:    Second financial year code (e.g. "24-25")
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum, F, DecimalField
    from accounting.views import calcuate_pnl

    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    fy1 = _resolve_fy(fy_code1, retail)
    fy2 = _resolve_fy(fy_code2, retail)
    missing = [c for c, f in [(fy_code1, fy1), (fy_code2, fy2)] if f is None]
    if missing:
        return json.dumps({"error": f"Financial year(s) not found: {', '.join(missing)}. Use list_financial_years to see available codes."})

    all_accounts = list(Account.objects.all())
    children_map: dict = {}
    for acc in all_accounts:
        children_map.setdefault(acc.parent_id, []).append(acc)

    def _descendants(pid):
        result = []
        for child in children_map.get(pid, []):
            result.append(child)
            result.extend(_descendants(child.id))
        return result

    def _build_bs(as_of_date_str: str):
        # Transaction balances up to as_of_date
        txn = {}
        for row in VoucherDetail.objects.filter(
            voucher_main__date__lte=as_of_date_str, voucher_main__retail=retail
        ).values("account__ac_group").annotate(bal=Sum(F("debit")) - Sum(F("credit"))):
            if row["account__ac_group"] is not None:
                txn[row["account__ac_group"]] = row["bal"] or Decimal(0)

        # Opening balances (always from ob table, FY-independent)
        ob = {}
        for row in LedgerOpenBalance.objects.filter(retail=retail).values(
            "ldgr__ac_group"
        ).annotate(bal=Sum(F("debit") - F("credit"), output_field=DecimalField())):
            if row["ldgr__ac_group"] is not None:
                ob[row["ldgr__ac_group"]] = row["bal"] or Decimal(0)

        def group_total(group_name):
            parent = next((a for a in all_accounts if a.name == group_name), None)
            if not parent:
                return Decimal(0), []
            total = Decimal(0)
            accounts = []
            for acc in _descendants(parent.id):
                bal = txn.get(acc.id, Decimal(0)) + ob.get(acc.id, Decimal(0))
                if bal != 0:
                    accounts.append({"name": acc.name, "balance": round(float(bal), 2)})
                total += bal
            return total, accounts

        assets_total, assets_detail       = group_total("Assets")
        liabilities_total, liab_detail    = group_total("Liabilities")

        # Add retained earnings (cumulative net profit up to as_of_date)
        pnl = calcuate_pnl("2000-01-01", as_of_date_str, retail=retail)
        net_profit = float(pnl.get("net_profit", 0) or 0)
        liabilities_total += Decimal(str(net_profit))

        return {
            "as_of":           as_of_date_str,
            "assets":          round(float(assets_total), 2),
            "assets_detail":   assets_detail,
            "liabilities":     round(float(liabilities_total), 2),
            "liabilities_detail": liab_detail,
            "net_profit":      round(net_profit, 2),
        }

    bs1 = _build_bs(str(fy1.fy_end))
    bs2 = _build_bs(str(fy2.fy_end))

    def _row(key):
        v1 = bs1[key]
        v2 = bs2[key]
        diff = round(v2 - v1, 2)
        pct  = round(diff / v1 * 100, 2) if v1 != 0 else None
        return {
            f"fy_{fy_code1}": v1,
            f"fy_{fy_code2}": v2,
            "change":         diff,
            "change_pct":     pct,
        }

    return json.dumps({
        "comparison_type": "Balance Sheet — Year on Year",
        "fy1": {"code": fy_code1, "closing_date": str(fy1.fy_end)},
        "fy2": {"code": fy_code2, "closing_date": str(fy2.fy_end)},
        "summary": {
            "total_assets":      _row("assets"),
            "total_liabilities": _row("liabilities"),
            "net_profit":        _row("net_profit"),
        },
        "fy1_detail": bs1,
        "fy2_detail": bs2,
        "note": "Liabilities include cumulative net profit (retained earnings).",
    }, indent=2)


# ===================================================================
#  RISK & RECEIVABLES
# ===================================================================

@mcp.tool()
def get_approval_items_outstanding(retail_code: str = "") -> str:
    """Jewellery given to customers on approval that has not come back yet —
    live loss exposure. Shows each item, the customer holding it, and for how long.

    Note: the ERP has no approval-to-sale link, so an approval that became a sale
    must have been recorded as a return first; anything still flagged outstanding
    is genuinely not returned.

    Args:
        retail_code: Retail location code (optional)
    """
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    today = datetime.date.today()
    outstanding = (
        SalesApprovalItem.objects.filter(ret_status=False, retail=retail)
        .select_related("billno", "billno__ldgr", "barcode", "item")
        .order_by("billno__date1")
    )

    items, by_customer = [], {}
    for it in outstanding:
        header = it.billno
        issued_on = header.date1 if header else None
        days = (today - issued_on).days if issued_on else None
        customer = header.ldgr.ac_name if header and header.ldgr else ""
        items.append({
            "approval_no": header.billno if header else "",
            "date": str(issued_on) if issued_on else "",
            "days_outstanding": days,
            "customer": customer,
            "barcode": str(it.barcode) if it.barcode else "",
            "item": it.item.item_name if it.item else "",
            "pcs": it.pcs,
            "gross_wt": _decimal(it.gw),
            "amount": _decimal(it.amount),
        })
        agg = by_customer.setdefault(
            customer, {"customer": customer, "items": 0, "gross_wt": 0.0, "amount": 0.0}
        )
        agg["items"] += 1
        agg["gross_wt"] += float(it.gw or 0)
        agg["amount"] += float(it.amount or 0)

    for agg in by_customer.values():
        agg["gross_wt"] = round(agg["gross_wt"], 3)
        agg["amount"] = round(agg["amount"], 2)

    return json.dumps({
        "as_of": str(today),
        "outstanding_items": len(items),
        "total_exposure": round(sum(i["amount"] or 0 for i in items), 2),
        "total_gross_wt": round(sum(i["gross_wt"] or 0 for i in items), 3),
        "by_customer": sorted(by_customer.values(), key=lambda r: -r["amount"]),
        "items": items,
    }, indent=2, default=str)


@mcp.tool()
def get_receivables_aging(as_of_date: str = "", retail_code: str = "") -> str:
    """Outstanding customer receivables split into ageing buckets
    (0-30, 31-60, 61-90, 90+ days) per customer.

    Balances come from the general ledger (the authoritative source), then each
    balance is aged FIFO against its debit postings, newest first. Any remainder
    that predates the transaction history is treated as opening balance and
    reported in the 90+ bucket.

    Args:
        as_of_date: As-of date (YYYY-MM-DD, defaults to today)
        retail_code: Retail location code (optional)
    """
    from decimal import Decimal as D
    from accounting.receivables import ledger_balances_for_groups, DEBTOR_GROUPS
    from contacts.models import Ledger

    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    as_of = (
        datetime.date.fromisoformat(as_of_date)
        if as_of_date
        else datetime.date.today()
    )

    balances = ledger_balances_for_groups(retail, DEBTOR_GROUPS, as_of=as_of)
    owing = {lid: bal for lid, bal in balances.items() if bal > 0}
    if not owing:
        return json.dumps({
            "as_of": str(as_of),
            "total_receivable": 0,
            "customers": [],
            "note": "No customer has a debit balance as of this date.",
        }, indent=2)

    names = dict(
        Ledger.objects.filter(id__in=owing.keys()).values_list("id", "ac_name")
    )

    bucket_bounds = [(0, 30), (31, 60), (61, 90), (91, None)]
    bucket_labels = ["0-30", "31-60", "61-90", "90+"]
    totals = [D("0")] * 4
    rows = []

    for ledger_id, balance in owing.items():
        debits = (
            VoucherDetail.objects.filter(
                account_id=ledger_id, voucher_main__retail=retail,
                voucher_main__date__lte=as_of, debit__gt=0,
            )
            .values("voucher_main__date", "debit")
            .order_by("-voucher_main__date")
        )

        remaining = balance
        buckets = [D("0")] * 4
        for entry in debits:
            if remaining <= 0:
                break
            applied = min(remaining, entry["debit"])
            remaining -= applied
            age = (as_of - entry["voucher_main__date"]).days
            for idx, (low, high) in enumerate(bucket_bounds):
                if age >= low and (high is None or age <= high):
                    buckets[idx] += applied
                    break
        if remaining > 0:  # older than recorded history — opening balance
            buckets[3] += remaining

        for idx in range(4):
            totals[idx] += buckets[idx]

        rows.append({
            "customer": names.get(ledger_id, f"Ledger {ledger_id}"),
            "outstanding": _decimal(balance),
            **{bucket_labels[i]: _decimal(buckets[i]) for i in range(4)},
        })

    rows.sort(key=lambda r: -(r["outstanding"] or 0))
    return json.dumps({
        "as_of": str(as_of),
        "total_receivable": _decimal(sum(owing.values())),
        "buckets": {bucket_labels[i]: _decimal(totals[i]) for i in range(4)},
        "customers": rows,
    }, indent=2, default=str)


@mcp.tool()
def get_ledger_statement(ledger_name: str, from_date: str, to_date: str, retail_code: str = "") -> str:
    """Full transaction statement for one ledger account: opening balance, every
    entry with a running balance, and the closing balance.

    Args:
        ledger_name: Ledger account name (partial match allowed)
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    from accounting.receivables import ledger_balances
    from contacts.models import Ledger

    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    # Many ledgers are global (retail_code is NULL) rather than branch-scoped,
    # so match this retail OR unscoped ledgers.
    from django.db.models import Q
    scope = Q(retail_code=retail) | Q(retail_code__isnull=True)
    ledger = (
        Ledger.objects.filter(scope, ac_name__iexact=ledger_name).first()
        or Ledger.objects.filter(scope, ac_name__icontains=ledger_name).first()
    )
    if not ledger:
        return json.dumps({
            "error": f"Ledger '{ledger_name}' not found.",
            "hint": "Use search_ledgers to find the exact name.",
        })

    start = datetime.date.fromisoformat(from_date)
    opening = ledger_balances(
        retail, [ledger.id], as_of=start - datetime.timedelta(days=1)
    ).get(ledger.id, 0)

    entries = (
        VoucherDetail.objects.filter(
            account=ledger, voucher_main__retail=retail,
            voucher_main__date__range=(from_date, to_date),
        )
        .select_related("voucher_main")
        .order_by("voucher_main__date", "id")
    )

    running = float(opening or 0)
    transactions = []
    total_debit = total_credit = 0.0
    for entry in entries:
        voucher = entry.voucher_main
        debit = float(entry.debit or 0)
        credit = float(entry.credit or 0)
        running += debit - credit
        total_debit += debit
        total_credit += credit
        transactions.append({
            "date": str(voucher.date),
            "voucher_no": voucher.voucher_no,
            "voucher_type": voucher.voucher_type,
            "narration": voucher.narration or "",
            "debit": round(debit, 2),
            "credit": round(credit, 2),
            "balance": round(running, 2),
        })

    return json.dumps({
        "ledger": ledger.ac_name,
        "group": ledger.ac_group.name if ledger.ac_group else "",
        "period": f"{from_date} to {to_date}",
        "opening_balance": _decimal(opening or 0),
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2),
        "closing_balance": round(running, 2),
        "transaction_count": len(transactions),
        "transactions": transactions,
        "note": "Positive balance = debit (customer owes us).",
    }, indent=2, default=str)


@mcp.tool()
def get_pending_customer_orders(retail_code: str = "", limit: int = 30) -> str:
    """Customer orders not yet delivered, with age and committed weight.

    Args:
        retail_code: Retail location code (optional)
        limit: Maximum orders to list (default 30)
    """
    from django.db.models import Sum
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    today = datetime.date.today()
    pending = (
        CustomerOrder.objects.filter(retail=retail)
        .exclude(delivery_status__in=["delivered", "cancelled", "returned"])
        .select_related("ldgr")
        .order_by("date1")
    )

    totals = pending.aggregate(
        wt=Sum("items__gw"), making=Sum("items__making_amt")
    )

    orders = []
    for order in pending[: max(1, int(limit or 30))]:
        line = order.items.aggregate(wt=Sum("gw"), making=Sum("making_amt"), pcs=Sum("pcs"))
        orders.append({
            "order_no": order.order_no,
            "date": str(order.date1),
            "days_pending": (today - order.date1).days if order.date1 else None,
            "customer": order.ldgr.ac_name if order.ldgr else "",
            "delivery_status": order.delivery_status,
            "promised_date": str(order.delivery_date) if order.delivery_date else "",
            "pcs": line["pcs"] or 0,
            "gross_wt": _decimal(line["wt"] or 0),
            "making_amount": _decimal(line["making"] or 0),
        })

    return json.dumps({
        "as_of": str(today),
        "pending_orders": pending.count(),
        "total_gross_wt": _decimal(totals["wt"] or 0),
        "total_making_amount": _decimal(totals["making"] or 0),
        "orders": orders,
        "note": (
            "Order value (est_amount) is unpopulated in this database, so weight "
            "and making charges are shown instead. Ageing uses the order date, as "
            "promised delivery dates are unreliable in legacy rows."
        ),
    }, indent=2, default=str)


# ===================================================================
#  STOCK INTELLIGENCE
# ===================================================================

# BarcodeTransaction.trans_type values that mean "this barcode entered stock".
_STOCK_ENTRY_TYPES = ["CREATE-PUR", "OP-STK"]


def _barcode_entry_date_subquery():
    """
    Earliest stock-entry date per barcode.

    BarcodeMain.created_date is unusable for ageing — the legacy import stamped
    every row with the same date. BarcodeTransaction carries the real timeline.
    """
    from django.db.models import OuterRef, Subquery
    return Subquery(
        BarcodeTransaction.objects
        .filter(barcode=OuterRef("pk"), trans_type__in=_STOCK_ENTRY_TYPES)
        .order_by("date")
        .values("date")[:1]
    )


@mcp.tool()
def get_dead_stock(min_days: int = 90, retail_code: str = "", limit: int = 30) -> str:
    """Find slow-moving stock: barcoded items still unsold after a number of days.
    Shows the capital locked up in them.

    Args:
        min_days: Minimum days held to count as dead stock (default 90)
        retail_code: Retail location code (optional)
        limit: Maximum items to list (default 30)
    """
    from django.db.models import Sum, Count
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    from django.utils import timezone

    today = datetime.date.today()
    cutoff_date = today - datetime.timedelta(days=max(0, int(min_days or 0)))
    # BarcodeTransaction.date is an aware DateTimeField; compare against an aware
    # datetime at the end of the cutoff day rather than a naive date.
    cutoff = timezone.make_aware(
        datetime.datetime.combine(cutoff_date, datetime.time.max)
    )

    in_stock = BarcodeMain.objects.filter(retail=retail, stk_status=True)
    aged = (
        in_stock.annotate(entry_date=_barcode_entry_date_subquery())
        .filter(entry_date__isnull=False, entry_date__lte=cutoff)
        .order_by("entry_date")
    )

    rows = []
    for bc in aged.select_related("item", "design")[: max(1, int(limit or 30))]:
        entry = bc.entry_date
        entry_date = entry.date() if hasattr(entry, "date") else entry
        rows.append({
            "barcode": bc.barcode,
            "item": bc.item.item_name if bc.item else "",
            "design_no": bc.design.design_no if bc.design else "",
            "entry_date": str(entry_date),
            "days_held": (today - entry_date).days,
            "gross_wt": _decimal(bc.gw),
            "value": _decimal(bc.total_amount),
        })

    dead_totals = aged.aggregate(value=Sum("total_amount"), wt=Sum("gw"), n=Count("id"))
    all_totals = in_stock.aggregate(value=Sum("total_amount"), n=Count("id"))

    # Ageing is bounded by how far back the transaction history goes.
    oldest = (
        in_stock.annotate(entry_date=_barcode_entry_date_subquery())
        .filter(entry_date__isnull=False)
        .order_by("entry_date")
        .values_list("entry_date", flat=True)
        .first()
    )
    max_age = None
    if oldest:
        oldest_date = oldest.date() if hasattr(oldest, "date") else oldest
        max_age = (today - oldest_date).days

    return json.dumps({
        "as_of": str(today),
        "threshold_days": min_days,
        "oldest_stock_age_days": max_age,
        "dead_stock_items": dead_totals["n"] or 0,
        "capital_locked": _decimal(dead_totals["value"] or 0),
        "dead_gross_wt": _decimal(dead_totals["wt"] or 0),
        "total_stock_items": all_totals["n"] or 0,
        "total_stock_value": _decimal(all_totals["value"] or 0),
        "items": rows,
        "note": (
            "Ageing is measured from the first stock-entry transaction "
            "(CREATE-PUR / OP-STK), not the barcode's created_date."
        ),
    }, indent=2, default=str)


@mcp.tool()
def get_inventory_turnover(from_date: str, to_date: str, retail_code: str = "") -> str:
    """Stock turnover by item: cost of goods sold vs the value still in stock,
    showing which categories actually move and which tie up capital.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
    """
    from django.db.models import Sum, Count
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    # Cost comes from the acquisition value of the exact barcode that sold.
    sold = (
        SalesVouItem.objects.filter(
            retail=retail,
            billno__date1__range=(from_date, to_date),
            billno__ret_status=False,
        )
        .values("item__item_name")
        .annotate(cogs=Sum("barcode__total_amount"), revenue=Sum("amount"), units=Sum("pcs"))
    )
    sold_map = {r["item__item_name"]: r for r in sold}

    stock = (
        BarcodeMain.objects.filter(retail=retail, stk_status=True)
        .values("item__item_name")
        .annotate(stock_value=Sum("total_amount"), stock_units=Count("id"))
    )
    stock_map = {r["item__item_name"]: r for r in stock}

    results = []
    for name in set(sold_map) | set(stock_map):
        s = sold_map.get(name, {})
        k = stock_map.get(name, {})
        cogs = float(s.get("cogs") or 0)
        revenue = float(s.get("revenue") or 0)
        stock_value = float(k.get("stock_value") or 0)
        results.append({
            "item": name or "(unspecified)",
            "units_sold": s.get("units") or 0,
            "revenue": round(revenue, 2),
            "cogs": round(cogs, 2),
            "gross_margin": round(revenue - cogs, 2),
            "margin_pct": round((revenue - cogs) / revenue * 100, 2) if revenue else None,
            "stock_value": round(stock_value, 2),
            "stock_units": k.get("stock_units") or 0,
            "turns": round(cogs / stock_value, 2) if stock_value else None,
        })

    results.sort(key=lambda r: -(r["revenue"] or 0))
    return json.dumps({
        "period": f"{from_date} to {to_date}",
        "items": results,
        "note": (
            "No historical stock snapshots exist, so 'turns' uses closing stock "
            "value as the denominator rather than average stock. Revenue and COGS "
            "are ex-tax line values."
        ),
    }, indent=2, default=str)


@mcp.tool()
def get_design_performance(from_date: str, to_date: str, retail_code: str = "", limit: int = 15) -> str:
    """Best and worst performing designs by revenue, with units still in stock.

    Args:
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        retail_code: Retail location code (optional)
        limit: How many designs to show at each end (default 15)
    """
    from django.db.models import Sum, Count
    retail = _get_retail(retail_code)
    if not retail:
        return json.dumps({"error": f"Retail '{retail_code}' not found."})

    top_n = max(1, int(limit or 15))

    sold = list(
        SalesVouItem.objects.filter(
            retail=retail,
            billno__date1__range=(from_date, to_date),
            billno__ret_status=False,
            barcode__design__isnull=False,
        )
        .values("barcode__design__design_no", "barcode__design__item__item_name")
        .annotate(units=Sum("pcs"), revenue=Sum("amount"), gross_wt=Sum("gw"))
        .order_by("-revenue")
    )

    # Unsold stock per design.
    stock = (
        BarcodeMain.objects.filter(retail=retail, stk_status=True, design__isnull=False)
        .values("design__design_no")
        .annotate(n=Count("id"), value=Sum("total_amount"))
    )
    stock_map = {r["design__design_no"]: r for r in stock}

    def _shape(r):
        design_no = r["barcode__design__design_no"]
        k = stock_map.get(design_no, {})
        return {
            "design_no": design_no,
            "item": r["barcode__design__item__item_name"] or "",
            "units_sold": r["units"] or 0,
            "revenue": _decimal(r["revenue"] or 0),
            "gross_wt": _decimal(r["gross_wt"] or 0),
            "units_in_stock": k.get("n", 0),
            "stock_value": _decimal(k.get("value") or 0),
        }

    performers = [_shape(r) for r in sold]

    # Designs sitting in stock that sold nothing at all in the period.
    sold_codes = {r["barcode__design__design_no"] for r in sold}
    never_sold = [
        {
            "design_no": code,
            "units_in_stock": v.get("n", 0),
            "stock_value": _decimal(v.get("value") or 0),
        }
        for code, v in stock_map.items()
        if code not in sold_codes
    ]
    never_sold.sort(key=lambda r: -(r["stock_value"] or 0))

    return json.dumps({
        "period": f"{from_date} to {to_date}",
        "designs_sold": len(performers),
        "best_sellers": performers[:top_n],
        "weakest_sellers": performers[-top_n:][::-1] if len(performers) > top_n else [],
        "in_stock_never_sold": never_sold[:top_n],
        "note": (
            "Barcodes with no linked design are excluded. Some legacy design_no "
            "values are short stubs from the old import."
        ),
    }, indent=2, default=str)


# ===================================================================
#  READ-ONLY SQL — ad-hoc queries beyond the pre-built tools
# ===================================================================
#
# Safety model (defence in depth — every layer independently sufficient):
#   1. The connection is opened with SQLite's `mode=ro` URI, so the driver
#      itself refuses any write. This is the hard guarantee.
#   2. Only a single statement is accepted, and it must start with SELECT/WITH.
#   3. Mutating keywords are rejected outright.
#   4. The query is wrapped in an outer LIMIT so a runaway SELECT can't dump
#      the whole database.
#   5. A progress handler aborts anything exceeding the time budget.

_SQL_MAX_ROWS = 500
_SQL_TIMEOUT_SECONDS = 10

_SQL_FORBIDDEN_WORDS = (
    "insert", "update", "delete", "drop", "alter", "create", "replace",
    "truncate", "attach", "detach", "pragma", "vacuum", "reindex",
    "begin", "commit", "rollback", "savepoint",
)


def _readonly_sqlite_connection():
    """Open a genuinely read-only connection to the Django SQLite database."""
    import sqlite3
    import pathlib
    from django.conf import settings

    db_path = pathlib.Path(str(settings.DATABASES["default"]["NAME"])).as_posix()
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)

    # Abort long-running queries: the handler fires every N VM instructions and
    # a non-zero return interrupts the statement.
    import time
    deadline = time.monotonic() + _SQL_TIMEOUT_SECONDS

    def _abort_if_slow():
        return 1 if time.monotonic() > deadline else 0

    conn.set_progress_handler(_abort_if_slow, 10000)
    return conn


def _validate_select(sql: str):
    """Return (safe_sql, error). Only a single SELECT/WITH statement passes."""
    import re

    statement = (sql or "").strip().rstrip(";").strip()
    if not statement:
        return None, "Empty query."
    if ";" in statement:
        return None, "Only a single statement is allowed (remove the ';')."

    lowered = statement.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return None, "Only SELECT queries are allowed (or WITH ... SELECT)."

    for word in _SQL_FORBIDDEN_WORDS:
        if re.search(rf"\b{word}\b", lowered):
            return None, f"Forbidden keyword in a read-only query: '{word}'."

    return statement, None


@mcp.tool()
def list_database_tables() -> str:
    """List all database tables with their row counts. Use this first to discover
    what data exists before writing a query with run_readonly_sql.
    """
    conn = _readonly_sqlite_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        tables = [row[0] for row in cur.fetchall()]
        out = []
        for name in tables:
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{name}"')
                out.append({"table": name, "rows": cur.fetchone()[0]})
            except Exception:
                out.append({"table": name, "rows": None})
    finally:
        conn.close()

    populated = [t for t in out if (t["rows"] or 0) > 0]
    return json.dumps({
        "table_count": len(out),
        "tables_with_data": len(populated),
        "tables": sorted(out, key=lambda t: -(t["rows"] or 0)),
    }, indent=2)


@mcp.tool()
def describe_table(table_name: str) -> str:
    """Show the columns, types and foreign keys of a table, so you can write a
    correct SQL query against it.

    Args:
        table_name: Exact table name (get it from list_database_tables)
    """
    import re
    if not re.fullmatch(r"[A-Za-z0-9_]+", table_name or ""):
        return json.dumps({"error": "Invalid table name."})

    conn = _readonly_sqlite_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        if not cur.fetchone():
            return json.dumps({"error": f"Table '{table_name}' does not exist."})

        cur.execute(f'PRAGMA table_info("{table_name}")')
        columns = [
            {
                "name": r[1],
                "type": r[2],
                "not_null": bool(r[3]),
                "primary_key": bool(r[5]),
            }
            for r in cur.fetchall()
        ]

        cur.execute(f'PRAGMA foreign_key_list("{table_name}")')
        foreign_keys = [
            {"column": r[3], "references": f"{r[2]}.{r[4]}"} for r in cur.fetchall()
        ]

        cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
        row_count = cur.fetchone()[0]
    finally:
        conn.close()

    return json.dumps({
        "table": table_name,
        "row_count": row_count,
        "columns": columns,
        "foreign_keys": foreign_keys,
    }, indent=2)


@mcp.tool()
def run_readonly_sql(sql: str, max_rows: int = 100) -> str:
    """Run a read-only SELECT query against the ERP database for questions the
    other tools don't cover. Writes are impossible — the connection is opened
    read-only and anything but a single SELECT is rejected.

    Discover the schema with list_database_tables and describe_table first.
    Note: monetary values on sales vouchers are NOT stored — compute them as
    (mrp - discount) plus GST derived from cgst_per/sgst_per/igst_per, plus
    round_off.

    Args:
        sql: A single SELECT statement (WITH ... SELECT is also allowed)
        max_rows: Maximum rows to return (default 100, hard cap 500)
    """
    statement, error = _validate_select(sql)
    if error:
        return json.dumps({"error": error})

    limit = max(1, min(int(max_rows or 100), _SQL_MAX_ROWS))

    conn = _readonly_sqlite_connection()
    try:
        cur = conn.cursor()
        # Outer LIMIT guarantees the cap regardless of the inner query.
        cur.execute(f"SELECT * FROM ({statement}) LIMIT {limit}")
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = [
            {col: _decimal(val) for col, val in zip(columns, record)}
            for record in cur.fetchall()
        ]
    except Exception as exc:
        return json.dumps({
            "error": f"{type(exc).__name__}: {exc}",
            "hint": "Check table and column names with describe_table.",
        }, indent=2)
    finally:
        conn.close()

    return json.dumps({
        "columns": columns,
        "row_count": len(rows),
        "truncated": len(rows) >= limit,
        "rows": rows,
    }, indent=2, default=str)


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
