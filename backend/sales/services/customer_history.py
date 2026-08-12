"""
Customer transaction history — the union of sales, returns, orders and approvals
for one ledger.

Extracted from `CustomerPurchaseHistoryView` so that both the REST endpoint
(`/sales/api/customer-history/`) and the Customer 360 profile
(`customer_intel.services.profile`) build the same rows from one definition.
Behaviour is intentionally unchanged from the original view.

Note on `amount`: for Sale/Return rows this is `mrp` (not the tax-inclusive bill
total), with tax reported separately. That is the original contract the frontend
depends on — do not "fix" it here without updating the consumers.
"""

from contacts.models import Ledger
from sales.models import CustomerOrder, SaleReturn, SalesApproval, SalesVou


def _bill_value(row):
    """SalesVou / SaleReturn: mrp is a real DB field, taxable = mrp - discount."""
    mrp = float(row.get("mrp") or 0)
    disc = float(row.get("discount") or 0)
    taxable = mrp - disc
    cgst = taxable * float(row.get("cgst_per") or 0) / 100
    sgst = taxable * float(row.get("sgst_per") or 0) / 100
    igst = taxable * float(row.get("igst_per") or 0) / 100
    return round(mrp, 2), round(cgst + sgst + igst, 2)


def _approval_bill_value(row):
    """SalesApproval: taxable_value is the real DB field (there is no mrp column)."""
    taxable = float(row.get("taxable_value") or 0)
    disc = float(row.get("discount") or 0)
    base = taxable - disc
    cgst = base * float(row.get("cgst_per") or 0) / 100
    sgst = base * float(row.get("sgst_per") or 0) / 100
    igst = base * float(row.get("igst_per") or 0) / 100
    total = round(base + cgst + sgst + igst, 2)
    return total, round(cgst + sgst + igst, 2)


def build_customer_history(retail, ledger_id, from_date=None, to_date=None):
    """
    Return {'ledger': {...}, 'summary': {...}, 'transactions': [...]} for one
    customer, newest first.

    Args:
        retail:    RetailMaster instance (or pk) to scope documents to.
        ledger_id: Ledger pk.
        from_date: optional inclusive lower bound on date1 (date or 'YYYY-MM-DD').
        to_date:   optional inclusive upper bound on date1.
    """
    date_filter = {}
    if from_date:
        date_filter["date1__gte"] = from_date
    if to_date:
        date_filter["date1__lte"] = to_date

    money_fields = ("id", "date1", "mrp", "cgst_per", "sgst_per", "igst_per", "discount")

    sales = SalesVou.objects.filter(
        ldgr_id=ledger_id, retail=retail, **date_filter
    ).values("billno", *money_fields)

    returns = SaleReturn.objects.filter(
        ldgr_id=ledger_id, retail=retail, **date_filter
    ).values("billno", *money_fields)

    orders = CustomerOrder.objects.filter(
        ldgr_id=ledger_id, retail=retail, **date_filter
    ).values("id", "order_no", "date1", "est_amount")

    approvals = SalesApproval.objects.filter(
        ldgr_id=ledger_id, retail=retail, **date_filter
    ).values(
        "id", "billno", "date1", "taxable_value",
        "cgst_per", "sgst_per", "igst_per", "discount",
    )

    rows = []
    for r in sales:
        amt, tax = _bill_value(r)
        rows.append({"doc_type": "Sale", "doc_no": r["billno"], "date": str(r["date1"]),
                     "id": r["id"], "amount": amt, "tax": tax})
    for r in returns:
        amt, tax = _bill_value(r)
        rows.append({"doc_type": "Return", "doc_no": r["billno"], "date": str(r["date1"]),
                     "id": r["id"], "amount": amt, "tax": tax})
    for r in orders:
        rows.append({"doc_type": "Order", "doc_no": r["order_no"], "date": str(r["date1"]),
                     "id": r["id"], "amount": float(r["est_amount"] or 0), "tax": 0})
    for r in approvals:
        amt, tax = _approval_bill_value(r)
        rows.append({"doc_type": "Approval", "doc_no": r["billno"], "date": str(r["date1"]),
                     "id": r["id"], "amount": amt, "tax": tax})

    rows.sort(key=lambda x: x["date"], reverse=True)

    total_sales = sum(r["amount"] for r in rows if r["doc_type"] == "Sale")
    total_returns = sum(r["amount"] for r in rows if r["doc_type"] == "Return")

    try:
        ledger = Ledger.objects.get(pk=ledger_id)
        ledger_info = {
            "id": ledger.id,
            "ac_name": ledger.ac_name,
            "gst": ledger.gst or "",
            "mobile": ledger.mobile1 or "",
        }
    except Ledger.DoesNotExist:
        ledger_info = {}

    return {
        "ledger": ledger_info,
        "summary": {
            "total_sales": round(total_sales, 2),
            "total_returns": round(total_returns, 2),
            "net": round(total_sales - total_returns, 2),
            "order_count": sum(1 for r in rows if r["doc_type"] == "Order"),
        },
        "transactions": rows,
    }
