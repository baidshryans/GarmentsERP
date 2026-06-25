from datetime import date

from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from sales.models import CustomerOrder, CustomerOrderItems
from purchase.models import PurchaseVoucherItems
from inventory.models import BarcodeMain
from goldrates.models import PurityMaster
from sales.serializers import _customer_order_item_lock, _prime_co_item_locks


class LockStateBatchingTests(TestCase):
    """The customer-order list serializes per-item lock state. Computing it
    per-row walks several barcode-sourcing chains (an N+1). `_prime_co_item_locks`
    batches that across the whole page. These tests pin that the batched result
    is byte-identical to the per-row result, and that batched query count is
    bounded (does not grow per item)."""

    N = 12

    @classmethod
    def setUpTestData(cls):
        from django.db.models.signals import post_save
        # Mute post_save side effects (raw-material / ledger sync) during fixture
        # creation — this test exercises only the read-path lock logic.
        saved_receivers = post_save.receivers
        post_save.receivers = []
        post_save.sender_receivers_cache.clear()
        try:
            purity = PurityMaster.objects.create(purity="22K", gw_per=1)
            cls.item_ids = []
            for i in range(cls.N):
                co = CustomerOrder.objects.create(date1=date(2026, 1, 1), order_no=f"CO-T{i:03d}")
                coi = CustomerOrderItems.objects.create(order_no=co, sl_no=1, making_type="PerGram")
                # Chain C: direct CO -> PV line, then a barcode off that PV line.
                pvi = PurchaseVoucherItems.objects.create(sl_no=1, customer_order_item=coi)
                BarcodeMain.objects.create(barcode=f"BC-T{i:03d}", purity=purity, pur_voucher=pvi)
                cls.item_ids.append(coi.id)
        finally:
            post_save.receivers = saved_receivers
            post_save.sender_receivers_cache.clear()

    def _fresh_items(self):
        # Fresh instances each call so no _lock_cache leaks between measurements.
        # Prefetch the relation managers the lock walk reads, mirroring the real
        # list queryset — prefetch runs here (via list()), so the per-row vs
        # batched capture below isolates the barcode-chain queries that remain.
        return list(
            CustomerOrderItems.objects
            .filter(id__in=self.item_ids)
            .prefetch_related(
                "purchaseorderitems_set__po_slip",
                "karigarissueitem_set__issue_slip",
                "purchasevoucheritems_set__billno",
            )
            .order_by("id")
        )

    def test_batched_matches_per_row(self):
        per_row = {it.id: _customer_order_item_lock(it) for it in self._fresh_items()}

        batched_items = self._fresh_items()
        _prime_co_item_locks(batched_items)
        batched = {it.id: _customer_order_item_lock(it) for it in batched_items}

        self.assertEqual(per_row, batched)
        # Sanity: the fixture actually exercises a non-trivial (non-'unlocked')
        # state, otherwise the chains would short-circuit and prove nothing.
        self.assertTrue(all(v[0] == "billed" for v in batched.values()), batched)

    def test_batched_query_count_is_bounded(self):
        with CaptureQueriesContext(connection) as per_row_ctx:
            for it in self._fresh_items():
                _customer_order_item_lock(it)

        items = self._fresh_items()
        with CaptureQueriesContext(connection) as batched_ctx:
            _prime_co_item_locks(items)

        per_row_q = len(per_row_ctx.captured_queries)
        batched_q = len(batched_ctx.captured_queries)
        # Per-row grows with N; batched is a small fixed handful regardless of N.
        self.assertLess(batched_q, per_row_q)
        self.assertLessEqual(batched_q, 6)
