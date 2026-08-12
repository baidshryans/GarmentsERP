"""
Reusable database expressions for sales voucher monetary values.

`SalesVou` has no stored bill_value / GST-amount columns — they are derived at
read time from mrp, discount, the per-cent GST rates and round_off (see the
model's `total_bill_value` / `cgst_amt` properties). The expressions here mirror
that formula so callers can Sum / Avg / group in the database instead of pulling
rows into Python.

IMPORTANT: these expressions and `sales.models.SalesVou.total_bill_value` must
stay in agreement. If you change one, change the other — `customer_intel` has a
regression test (`test_snapshot_money.py`) that asserts they still match.
"""

from django.db.models import DecimalField, ExpressionWrapper, F, Value
from django.db.models.functions import Coalesce


def sales_exprs(include_round_off=True):
    """
    Return ORM expressions mirroring SalesVou's derived monetary properties.

    Args:
        include_round_off: set False for models that share the mrp/discount/GST
            shape but have no `round_off` column — notably `SaleReturn`.
            Passing True against such a model raises FieldError.

    Returns a dict of ExpressionWrapper objects keyed:
        taxable, cgst, sgst, igst, bill
    """
    dec = DecimalField(max_digits=20, decimal_places=4)
    z = Value(0, output_field=dec)
    hundred = Value(100, output_field=dec)

    taxable = Coalesce(F("mrp"), z) - Coalesce(F("discount"), z)
    cgst = taxable * Coalesce(F("cgst_per"), z) / hundred
    sgst = taxable * Coalesce(F("sgst_per"), z) / hundred
    igst = taxable * Coalesce(F("igst_per"), z) / hundred
    bill = taxable + cgst + sgst + igst
    if include_round_off:
        bill = bill + Coalesce(F("round_off"), z)

    return {
        "taxable": ExpressionWrapper(taxable, output_field=dec),
        "cgst": ExpressionWrapper(cgst, output_field=dec),
        "sgst": ExpressionWrapper(sgst, output_field=dec),
        "igst": ExpressionWrapper(igst, output_field=dec),
        "bill": ExpressionWrapper(bill, output_field=dec),
    }
