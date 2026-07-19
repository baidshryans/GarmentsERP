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


def _sales_exprs():
    """
    Database expressions for SalesVou monetary values.

    SalesVou has no stored bill_value/GST-amount columns — they are derived from
    mrp, discount, the per-cent GST rates and round_off (see the model's
    total_bill_value / cgst_amt properties). These ORM expressions mirror that
    formula so we can Sum/Avg/group in the database.

    Returns a dict of ExpressionWrapper objects: taxable, cgst, sgst, igst, bill.
    """
    from django.db.models import F, Value, DecimalField, ExpressionWrapper
    from django.db.models.functions import Coalesce

    dec = DecimalField(max_digits=20, decimal_places=4)
    z = Value(0, output_field=dec)
    hundred = Value(100, output_field=dec)

    taxable = Coalesce(F("mrp"), z) - Coalesce(F("discount"), z)
    cgst = taxable * Coalesce(F("cgst_per"), z) / hundred
    sgst = taxable * Coalesce(F("sgst_per"), z) / hundred
    igst = taxable * Coalesce(F("igst_per"), z) / hundred
    bill = taxable + cgst + sgst + igst + Coalesce(F("round_off"), z)

    return {
        "taxable": ExpressionWrapper(taxable, output_field=dec),
        "cgst": ExpressionWrapper(cgst, output_field=dec),
        "sgst": ExpressionWrapper(sgst, output_field=dec),
        "igst": ExpressionWrapper(igst, output_field=dec),
        "bill": ExpressionWrapper(bill, output_field=dec),
    }


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
