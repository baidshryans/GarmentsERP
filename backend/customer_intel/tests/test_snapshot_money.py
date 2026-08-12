"""
Guard against drift between the ORM bill expression and the model property.

`SalesVou.total_bill_value` is a Python property; `sales.expressions.sales_exprs`
is a SQL mirror of the same formula so aggregates can run in the database. If
someone edits one and not the other, every lifetime value silently goes wrong
and nothing else in the suite would notice. This test is the only thing standing
between that mistake and production.
"""

from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.test import TestCase

from customer_intel.models import CustomerProfileSnapshot
from customer_intel.services.snapshot import SnapshotBuilder
from customer_intel.tests.factories import make_customer, make_retail, make_sale
from sales.expressions import sales_exprs
from sales.models import SalesVou


class ExpressionMirrorsPropertyTests(TestCase):
    def test_expression_matches_property_across_varied_vouchers(self):
        retail = make_retail()
        customer = make_customer(retail, "Drift Check")

        # Deliberately awkward combinations: discounts, round-off in both
        # directions, IGST-free and GST-free rows.
        specs = [
            dict(mrp=100000, discount=0, cgst=1.5, sgst=1.5, round_off=0),
            dict(mrp=250000, discount=12500, cgst=1.5, sgst=1.5, round_off=0.4),
            dict(mrp=99999.99, discount=0.99, cgst=0, sgst=0, round_off=-0.5),
            dict(mrp=1, discount=0, cgst=1.5, sgst=1.5, round_off=0),
        ]
        for i, spec in enumerate(specs):
            make_sale(retail, customer, date(2026, 1, i + 1), billno=f"D{i}", **spec)

        bill = sales_exprs()["bill"]
        for voucher in SalesVou.objects.annotate(bv=bill):
            with self.subTest(bill=voucher.billno):
                self.assertAlmostEqual(
                    Decimal(str(voucher.total_bill_value or 0)),
                    Decimal(str(voucher.bv or 0)),
                    places=2,
                )

    def test_snapshot_lifetime_value_equals_python_sum(self):
        retail = make_retail()
        customer = make_customer(retail, "Sum Check")
        for i in range(4):
            make_sale(retail, customer, date(2026, 2, i + 1), mrp=50000 * (i + 1),
                      discount=1000, round_off=0.25, billno=f"S{i}")

        SnapshotBuilder(retail.id, today=date(2026, 6, 1)).run()

        snapshot = CustomerProfileSnapshot.objects.get(
            retail=retail, ledger=customer,
        )
        expected = sum(
            Decimal(str(v.total_bill_value or 0))
            for v in SalesVou.objects.filter(retail=retail, ldgr=customer)
        )
        self.assertAlmostEqual(
            Decimal(str(snapshot.lifetime_value)), expected, places=1,
        )

    def test_sale_return_expression_omits_missing_round_off_column(self):
        """
        SaleReturn shares the mrp/discount/GST shape but has no round_off
        column — asking for it raises FieldError, so the returns rollup must
        opt out. Regression guard for that specific crash.
        """
        from sales.models import SaleReturn

        retail = make_retail()
        customer = make_customer(retail, "Return Check")
        SaleReturn.objects.create(
            retail=retail, ldgr=customer, date1=date(2026, 3, 1), billno="R1",
            mrp=Decimal("10000"), discount=Decimal("0"), tcs_per=Decimal("0"),
            cgst_per=Decimal("1.5"), sgst_per=Decimal("1.5"), igst_per=Decimal("0"),
        )

        total = SaleReturn.objects.aggregate(
            t=Sum(sales_exprs(include_round_off=False)["bill"]),
        )["t"]
        self.assertAlmostEqual(Decimal(str(total)), Decimal("10300"), places=2)
