"""
NLQueryService — natural language → ERP data using OpenAI function-calling.

Flow:
  1. User sends a plain-English question.
  2. We call OpenAI with 12 ERP-domain tools defined below.
  3. GPT decides which tool(s) to call and with what arguments.
  4. We execute each tool against the real database.
  5. GPT synthesises a final narrative response from the results.
  6. We return the response + metadata.
"""

import json
import datetime
from decimal import Decimal
from django.conf import settings
from django.db.models import Sum, Count, Q
from django.core.cache import cache

# OpenAI client (v1+ SDK)
from openai import OpenAI

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _fmt(value):
    """Format Decimal/float for JSON serialisation."""
    if isinstance(value, Decimal):
        return float(value)
    return value


# ---------------------------------------------------------------------------
# ERP Tool implementations
# ---------------------------------------------------------------------------

def _get_sales_summary(retail, from_date: str, to_date: str) -> dict:
    from sales.models import SalesVou
    from django.db.models import Sum, Count
    qs = SalesVou.objects.filter(retail=retail, date1__range=(from_date, to_date))
    agg = qs.aggregate(
        total=Sum('bill_value'),
        count=Count('id')
    )
    top_customers = (
        qs.values('ldgr__ac_name')
        .annotate(total=Sum('bill_value'))
        .order_by('-total')[:5]
    )
    return {
        'total_sales': _fmt(agg['total'] or 0),
        'invoice_count': agg['count'],
        'top_customers': [
            {'name': r['ldgr__ac_name'], 'amount': _fmt(r['total'] or 0)}
            for r in top_customers
        ],
        'period': f"{from_date} to {to_date}",
    }


def _get_purchase_summary(retail, from_date: str, to_date: str) -> dict:
    from purchase.models import PurchaseVoucher
    qs = PurchaseVoucher.objects.filter(retail=retail, date1__range=(from_date, to_date))
    agg = qs.aggregate(total=Sum('bill_value'), count=Count('id'))
    top_vendors = (
        qs.values('ldgr__ac_name')
        .annotate(total=Sum('bill_value'))
        .order_by('-total')[:5]
    )
    return {
        'total_purchases': _fmt(agg['total'] or 0),
        'invoice_count': agg['count'],
        'top_vendors': [
            {'name': r['ldgr__ac_name'], 'amount': _fmt(r['total'] or 0)}
            for r in top_vendors
        ],
        'period': f"{from_date} to {to_date}",
    }


def _get_ledger_balance(retail, ledger_name: str) -> dict:
    from contacts.models import Ledger
    from accounting.models import VoucherDetail, LedgerOpenBalance
    try:
        ledger = Ledger.objects.get(ac_name__iexact=ledger_name, retail_code=retail)
    except Ledger.DoesNotExist:
        # fuzzy search
        ledger = Ledger.objects.filter(
            ac_name__icontains=ledger_name, retail_code=retail
        ).first()
        if not ledger:
            return {'error': f'Ledger "{ledger_name}" not found.'}

    ob = LedgerOpenBalance.objects.filter(ldgr=ledger, retail=retail).first()
    ob_dr = float(ob.debit if ob else 0)
    ob_cr = float(ob.credit if ob else 0)

    txn = VoucherDetail.objects.filter(
        account=ledger, voucher_main__retail=retail
    ).aggregate(total_dr=Sum('debit'), total_cr=Sum('credit'))

    total_dr = ob_dr + float(txn['total_dr'] or 0)
    total_cr = ob_cr + float(txn['total_cr'] or 0)
    net = total_dr - total_cr

    return {
        'ledger': ledger.ac_name,
        'group': str(ledger.ac_group),
        'total_debit': round(total_dr, 2),
        'total_credit': round(total_cr, 2),
        'net_balance': round(abs(net), 2),
        'balance_type': 'Dr' if net >= 0 else 'Cr',
    }


def _get_outstanding_debtors(retail, as_of_date: str) -> dict:
    from sales.models import SalesVou
    qs = SalesVou.objects.filter(
        retail=retail, date1__lte=as_of_date, due_amt__gt=0
    ).values('ldgr__ac_name').annotate(due=Sum('due_amt')).order_by('-due')[:10]
    total = SalesVou.objects.filter(
        retail=retail, date1__lte=as_of_date, due_amt__gt=0
    ).aggregate(t=Sum('due_amt'))['t'] or 0
    return {
        'as_of': as_of_date,
        'total_outstanding': _fmt(total),
        'top_debtors': [
            {'name': r['ldgr__ac_name'], 'due': _fmt(r['due'])} for r in qs
        ],
    }


def _get_outstanding_creditors(retail, as_of_date: str) -> dict:
    from purchase.models import PurchaseVoucher
    qs = PurchaseVoucher.objects.filter(
        retail=retail, date1__lte=as_of_date, due_amt__gt=0
    ).values('ldgr__ac_name').annotate(due=Sum('due_amt')).order_by('-due')[:10]
    total = PurchaseVoucher.objects.filter(
        retail=retail, date1__lte=as_of_date, due_amt__gt=0
    ).aggregate(t=Sum('due_amt'))['t'] or 0
    return {
        'as_of': as_of_date,
        'total_outstanding': _fmt(total),
        'top_creditors': [
            {'name': r['ldgr__ac_name'], 'due': _fmt(r['due'])} for r in qs
        ],
    }


def _get_gold_rates(retail) -> dict:
    from goldrates.models import GoldRates
    rates = GoldRates.objects.select_related('purity').order_by('-date1')[:20]
    seen = {}
    for r in rates:
        name = r.purity.purity if r.purity else 'Unknown'
        if name not in seen:
            seen[name] = r.rate
    return {'rates': [{'purity': k, 'rate_per_gram_inr': v} for k, v in seen.items()]}


def _get_stock_summary(retail) -> dict:
    from inventory.models import BarcodeMain
    qs = (
        BarcodeMain.objects.filter(retail=retail, stk_status=True)
        .values('item__item_name')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    total = BarcodeMain.objects.filter(retail=retail, stk_status=True).count()
    return {
        'total_barcodes_in_stock': total,
        'by_item': [
            {'item': r['item__item_name'], 'count': r['count']} for r in qs[:15]
        ],
    }


def _get_cash_position(retail) -> dict:
    from accounting.models import VoucherDetail, LedgerOpenBalance
    from contacts.models import Ledger
    results = []
    cash_ledgers = Ledger.objects.filter(
        retail_code=retail,
        type__in=['Cash', 'Bank']
    )
    for ledger in cash_ledgers:
        ob = LedgerOpenBalance.objects.filter(ldgr=ledger, retail=retail).first()
        ob_dr = float(ob.debit if ob else 0)
        ob_cr = float(ob.credit if ob else 0)
        txn = VoucherDetail.objects.filter(
            account=ledger, voucher_main__retail=retail
        ).aggregate(dr=Sum('debit'), cr=Sum('credit'))
        total_dr = ob_dr + float(txn['dr'] or 0)
        total_cr = ob_cr + float(txn['cr'] or 0)
        net = total_dr - total_cr
        results.append({
            'account': ledger.ac_name,
            'type': ledger.type,
            'balance': round(abs(net), 2),
            'balance_type': 'Dr' if net >= 0 else 'Cr',
        })
    return {'cash_and_bank_accounts': results}


def _get_gst_summary(retail, from_date: str, to_date: str) -> dict:
    from sales.models import SalesVou
    from purchase.models import PurchaseVoucher
    sales = SalesVou.objects.filter(
        retail=retail, date1__range=(from_date, to_date)
    ).aggregate(
        cgst=Sum('cgst_value'), sgst=Sum('sgst_value'), igst=Sum('igst_value')
    )
    purchases = PurchaseVoucher.objects.filter(
        retail=retail, date1__range=(from_date, to_date)
    ).aggregate(
        cgst=Sum('cgst_value'), sgst=Sum('sgst_value'), igst=Sum('igst_value')
    )
    return {
        'period': f"{from_date} to {to_date}",
        'output_gst': {
            'cgst': _fmt(sales['cgst'] or 0),
            'sgst': _fmt(sales['sgst'] or 0),
            'igst': _fmt(sales['igst'] or 0),
        },
        'input_gst': {
            'cgst': _fmt(purchases['cgst'] or 0),
            'sgst': _fmt(purchases['sgst'] or 0),
            'igst': _fmt(purchases['igst'] or 0),
        },
    }


def _get_karigar_jobs_status(retail) -> dict:
    from manufacturing.models import KarigarIssueItem
    total = KarigarIssueItem.objects.filter(retail=retail).count()
    open_jobs = KarigarIssueItem.objects.filter(retail=retail, rec_status=False).count()
    closed_jobs = total - open_jobs
    return {
        'total_jobs': total,
        'open_jobs': open_jobs,
        'closed_jobs': closed_jobs,
    }


def _get_top_customers(retail, from_date: str, to_date: str) -> dict:
    from sales.models import SalesVou
    qs = (
        SalesVou.objects.filter(retail=retail, date1__range=(from_date, to_date))
        .values('ldgr__ac_name')
        .annotate(total=Sum('bill_value'), count=Count('id'))
        .order_by('-total')[:10]
    )
    return {
        'period': f"{from_date} to {to_date}",
        'top_customers': [
            {'name': r['ldgr__ac_name'], 'amount': _fmt(r['total'] or 0), 'invoices': r['count']}
            for r in qs
        ],
    }


def _get_trial_balance_summary(retail, from_date: str, to_date: str) -> dict:
    from accounting.models import VoucherDetail, LedgerOpenBalance
    from contacts.models import Ledger
    txn = VoucherDetail.objects.filter(
        voucher_main__retail=retail,
        voucher_main__date__range=(from_date, to_date)
    ).aggregate(total_dr=Sum('debit'), total_cr=Sum('credit'))
    return {
        'period': f"{from_date} to {to_date}",
        'total_debit': _fmt(txn['total_dr'] or 0),
        'total_credit': _fmt(txn['total_cr'] or 0),
        'balanced': abs(float(txn['total_dr'] or 0) - float(txn['total_cr'] or 0)) < 0.01,
    }


# ---------------------------------------------------------------------------
# Tool dispatch table
# ---------------------------------------------------------------------------

TOOL_DISPATCH = {
    'get_sales_summary': lambda retail, args: _get_sales_summary(retail, args['from_date'], args['to_date']),
    'get_purchase_summary': lambda retail, args: _get_purchase_summary(retail, args['from_date'], args['to_date']),
    'get_ledger_balance': lambda retail, args: _get_ledger_balance(retail, args['ledger_name']),
    'get_outstanding_debtors': lambda retail, args: _get_outstanding_debtors(retail, args.get('as_of_date', str(datetime.date.today()))),
    'get_outstanding_creditors': lambda retail, args: _get_outstanding_creditors(retail, args.get('as_of_date', str(datetime.date.today()))),
    'get_gold_rates': lambda retail, args: _get_gold_rates(retail),
    'get_stock_summary': lambda retail, args: _get_stock_summary(retail),
    'get_cash_position': lambda retail, args: _get_cash_position(retail),
    'get_gst_summary': lambda retail, args: _get_gst_summary(retail, args['from_date'], args['to_date']),
    'get_karigar_jobs_status': lambda retail, args: _get_karigar_jobs_status(retail),
    'get_top_customers': lambda retail, args: _get_top_customers(retail, args['from_date'], args['to_date']),
    'get_trial_balance_summary': lambda retail, args: _get_trial_balance_summary(retail, args['from_date'], args['to_date']),
}


# ---------------------------------------------------------------------------
# OpenAI tool definitions
# ---------------------------------------------------------------------------

DATE_PARAMS = {
    "from_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
    "to_date": {"type": "string", "description": "End date in YYYY-MM-DD format"},
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": "Get total sales, invoice count and top customers for a date range.",
            "parameters": {"type": "object", "properties": DATE_PARAMS, "required": ["from_date", "to_date"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_purchase_summary",
            "description": "Get total purchases, invoice count and top vendors for a date range.",
            "parameters": {"type": "object", "properties": DATE_PARAMS, "required": ["from_date", "to_date"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ledger_balance",
            "description": "Get the current debit/credit balance for a specific ledger account.",
            "parameters": {
                "type": "object",
                "properties": {"ledger_name": {"type": "string", "description": "Name of the ledger account"}},
                "required": ["ledger_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_outstanding_debtors",
            "description": "Get list of customers with outstanding receivables (money owed to us).",
            "parameters": {
                "type": "object",
                "properties": {"as_of_date": {"type": "string", "description": "As-of date in YYYY-MM-DD format"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_outstanding_creditors",
            "description": "Get list of vendors with outstanding payables (money we owe).",
            "parameters": {
                "type": "object",
                "properties": {"as_of_date": {"type": "string", "description": "As-of date in YYYY-MM-DD format"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gold_rates",
            "description": "Get the current gold rates per gram for all purities.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_summary",
            "description": "Get current inventory stock count by item type.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cash_position",
            "description": "Get current balances of all cash and bank accounts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_gst_summary",
            "description": "Get output GST collected (from sales) and input GST paid (from purchases) for a period.",
            "parameters": {"type": "object", "properties": DATE_PARAMS, "required": ["from_date", "to_date"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_karigar_jobs_status",
            "description": "Get summary of karigar (artisan) job orders — open vs closed.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_customers",
            "description": "Get top customers by purchase value for a date range.",
            "parameters": {"type": "object", "properties": DATE_PARAMS, "required": ["from_date", "to_date"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trial_balance_summary",
            "description": "Get total debits and credits (trial balance check) for a period.",
            "parameters": {"type": "object", "properties": DATE_PARAMS, "required": ["from_date", "to_date"]},
        },
    },
]


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------

def run_nl_query(retail, user, query_text: str) -> dict:
    """
    Execute a natural-language ERP query.
    Returns: {response, tool_calls, tokens_used}
    """
    client = _get_client()
    today = str(datetime.date.today())
    retail_name = getattr(retail, 'retail_name', str(retail))

    system_prompt = (
        f"You are an AI assistant for {retail_name}, a jewellery business using Jewel India ERP. "
        f"Today's date is {today}. "
        "You have access to tools that query real-time business data. "
        "Always call the relevant tool(s) BEFORE answering — never guess data. "
        "Use Indian number formatting where appropriate (e.g. ₹2,50,000 = 2.5 lakh). "
        "Be concise and professional. "
        "If a date range is needed and the user didn't specify one, use the current financial year "
        f"(April 1 to {today})."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": query_text},
    ]

    tool_calls_log = []
    tokens_used = 0

    # First call — let GPT decide which tools to invoke
    response = client.chat.completions.create(
        model=settings.AI_NL_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
    )
    tokens_used += response.usage.total_tokens if response.usage else 0

    assistant_msg = response.choices[0].message
    messages.append(assistant_msg)

    # Execute any tool calls
    if assistant_msg.tool_calls:
        for tc in assistant_msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments)
            tool_calls_log.append({'tool': fn_name, 'args': fn_args})

            try:
                if fn_name in TOOL_DISPATCH:
                    result = TOOL_DISPATCH[fn_name](retail, fn_args)
                else:
                    result = {'error': f'Unknown tool: {fn_name}'}
            except Exception as e:
                result = {'error': str(e)}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

        # Second call — synthesise the final answer
        final_response = client.chat.completions.create(
            model=settings.AI_NL_MODEL,
            messages=messages,
        )
        tokens_used += final_response.usage.total_tokens if final_response.usage else 0
        final_text = final_response.choices[0].message.content
    else:
        final_text = assistant_msg.content or "I couldn't find any relevant data for that query."

    return {
        'response': final_text,
        'tool_calls': tool_calls_log,
        'tokens_used': tokens_used,
    }
