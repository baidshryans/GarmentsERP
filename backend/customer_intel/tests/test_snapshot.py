"""
Snapshot builder behaviour, including the N+1 regression guard.

The nightly rebuild must cost a fixed number of queries regardless of how many
customers it processes. Without a test asserting that, a later change adding a
per-customer lookup would keep passing every other test while quietly turning a
one-second job into a twenty-minute one.
"""

from datetime import date, timedelta

from django.test import TestCase

from customer_intel.models import CustomerProfileSnapshot
from customer_intel.services.snapshot import SnapshotBuilder
from customer_intel.tests.factories import (
    make_customer,
    make_retail,
    make_sale,
    make_salesperson,
)


class QueryCountTests(TestCase):
    """Query count must not grow with customer count."""

    def _build_population(self, retail, count, with_sales):
        salesperson = make_salesperson(retail)
        for i in range(count):
            customer = make_customer(retail, f"C{i}", mobile=f"90000{i:05d}")
            if with_sales:
                make_sale(retail, customer, date(2026, 3, 1), mrp=10000,
                          billno=f"B{i}", salesperson=salesperson)

    def test_query_count_is_flat_across_population_sizes(self):
        small_retail = make_retail(name="Small", code="SM")
        self._build_population(small_retail, 5, with_sales=True)

        big_retail = make_retail(name="Big", code="BG")
        self._build_population(big_retail, 60, with_sales=True)

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as small:
            SnapshotBuilder(small_retail.id, today=date(2026, 6, 1)).run()
        with CaptureQueriesContext(connection) as big:
            SnapshotBuilder(big_retail.id, today=date(2026, 6, 1)).run()

        # A 12x bigger population must not cost meaningfully more queries.
        # Allow a small delta for extra write chunks only.
        self.assertLessEqual(
            len(big.captured_queries), len(small.captured_queries) + 3,
            msg=(f"query count grew with population size: "
                 f"{len(small.captured_queries)} → {len(big.captured_queries)}"),
        )

    def test_rebuild_stays_under_a_fixed_query_budget(self):
        retail = make_retail(name="Budget", code="BD")
        self._build_population(retail, 50, with_sales=True)

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            SnapshotBuilder(retail.id, today=date(2026, 6, 1)).run()

        self.assertLess(
            len(ctx.captured_queries), 25,
            msg=f"rebuild used {len(ctx.captured_queries)} queries",
        )


class ScopingTests(TestCase):
    def test_includes_globally_scoped_customers(self):
        """
        Every customer ledger in the live database has a null retail_code, so a
        strict equality scope would reduce the customer base to buyers only.
        """
        retail = make_retail()
        make_customer(retail=None, name="Global Customer")

        ids = SnapshotBuilder(retail.id).ledger_ids()

        self.assertEqual(len(ids), 1)

    def test_includes_customers_who_bought_here_but_registered_elsewhere(self):
        here = make_retail(name="Here", code="HR")
        elsewhere = make_retail(name="Elsewhere", code="EL")
        visitor = make_customer(elsewhere, "Visitor")
        make_sale(here, visitor, date(2026, 3, 1), mrp=5000)

        self.assertIn(visitor.id, SnapshotBuilder(here.id).ledger_ids())

    def test_excludes_customers_of_another_retail_with_no_sales_here(self):
        here = make_retail(name="Here", code="HR")
        elsewhere = make_retail(name="Elsewhere", code="EL")
        make_customer(elsewhere, "Stranger")

        self.assertEqual(SnapshotBuilder(here.id).ledger_ids(), [])


class SnapshotContentTests(TestCase):
    def test_non_buyer_gets_a_snapshot_with_no_confidence(self):
        retail = make_retail()
        customer = make_customer(retail, "Never Bought")

        SnapshotBuilder(retail.id, today=date(2026, 6, 1)).run()

        snapshot = CustomerProfileSnapshot.objects.get(ledger=customer)
        self.assertEqual(snapshot.purchase_count_all, 0)
        self.assertEqual(snapshot.confidence, "none")
        self.assertEqual(snapshot.lapse_band, "never")
        self.assertFalse(snapshot.cadence_is_meaningful)

    def test_single_purchase_customer_has_low_confidence(self):
        retail = make_retail()
        customer = make_customer(retail, "Bought Once")
        make_sale(retail, customer, date(2026, 5, 1), mrp=100000)

        SnapshotBuilder(retail.id, today=date(2026, 6, 1)).run()

        snapshot = CustomerProfileSnapshot.objects.get(ledger=customer)
        self.assertEqual(snapshot.purchase_count_all, 1)
        self.assertEqual(snapshot.confidence, "low")
        self.assertFalse(
            snapshot.cadence_is_meaningful,
            msg="a single purchase must not produce a usable buying rhythm",
        )

    def test_repeat_customer_gets_cadence(self):
        retail = make_retail()
        customer = make_customer(retail, "Regular")
        start = date(2024, 1, 1)
        for i in range(5):
            make_sale(retail, customer, start + timedelta(days=120 * i),
                      mrp=200000, billno=f"R{i}")

        SnapshotBuilder(retail.id, today=date(2026, 6, 1)).run()

        snapshot = CustomerProfileSnapshot.objects.get(ledger=customer)
        self.assertEqual(snapshot.confidence, "high")
        self.assertTrue(snapshot.cadence_is_meaningful)
        self.assertEqual(snapshot.median_gap_days, 120)
        self.assertEqual(snapshot.gap_basis, "own")
        self.assertIsNotNone(snapshot.next_expected_date)

    def test_rerun_updates_rather_than_duplicates(self):
        retail = make_retail()
        customer = make_customer(retail, "Twice Built")
        make_sale(retail, customer, date(2026, 5, 1), mrp=50000)

        SnapshotBuilder(retail.id, today=date(2026, 6, 1)).run()
        make_sale(retail, customer, date(2026, 5, 20), mrp=70000, billno="X2")
        SnapshotBuilder(retail.id, today=date(2026, 6, 1)).run()

        snapshots = CustomerProfileSnapshot.objects.filter(ledger=customer)
        self.assertEqual(snapshots.count(), 1)
        self.assertEqual(snapshots.first().purchase_count_all, 2)

    def test_returns_reduce_net_spend(self):
        from decimal import Decimal

        from sales.models import SaleReturn

        retail = make_retail()
        customer = make_customer(retail, "Returner")
        make_sale(retail, customer, date(2026, 5, 1), mrp=100000, cgst=0, sgst=0)
        SaleReturn.objects.create(
            retail=retail, ldgr=customer, date1=date(2026, 5, 10), billno="RR1",
            mrp=Decimal("40000"), discount=Decimal("0"), tcs_per=Decimal("0"),
            cgst_per=Decimal("0"), sgst_per=Decimal("0"), igst_per=Decimal("0"),
        )

        SnapshotBuilder(retail.id, today=date(2026, 6, 1)).run()

        snapshot = CustomerProfileSnapshot.objects.get(ledger=customer)
        self.assertAlmostEqual(float(snapshot.returns_value), 40000, places=1)
        self.assertAlmostEqual(float(snapshot.net_spend), 60000, places=1)
