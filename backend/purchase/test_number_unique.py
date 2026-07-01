"""
Tests that scoped UniqueConstraints on purchase voucher-number models
actually enforce uniqueness at the DB level.

Tests cover:
  - purchase.PurchaseVoucher (uniq_pv_number: retail, fiscal_year, voucher_type, billno)
  - purchase.PurchaseReturn  (uniq_pr_number)
  - purchase.PurchaseOrder   (uniq_po_number)
"""
from django.db import IntegrityError, transaction
from django.test import TestCase


def _make_retail():
    from mastersconfig.models import RetailMaster
    obj, _ = RetailMaster.objects.get_or_create(
        retail_code="PVTEST",
        defaults={"retail_name": "PV Test Retail", "address_line1": "Test"},
    )
    return obj


def _make_fy(retail):
    from mastersconfig.models import FiscalYearMaster
    obj, _ = FiscalYearMaster.objects.get_or_create(
        retail=retail,
        fy_code="24-25",
        defaults={"fy_start": "2024-04-01", "fy_end": "2025-03-31"},
    )
    return obj


def _make_ledger():
    from contacts.models import Ledger
    obj, _ = Ledger.objects.get_or_create(
        ac_name="PV Test Ledger",
        defaults={"display_name": "PV Test Ledger"},
    )
    return obj


class PurchaseVoucherUniqueTest(TestCase):
    """uniq_pv_number: (retail, fiscal_year, voucher_type, billno)."""

    def test_same_billno_same_type_raises(self):
        from purchase.models import PurchaseVoucher
        retail = _make_retail(); fy = _make_fy(retail); ldgr = _make_ledger()
        PurchaseVoucher.objects.create(
            billno="C-DUP", date1="2024-05-01", voucher_type="Customer",
            ldgr=ldgr, retail=retail, fiscal_year=fy,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PurchaseVoucher.objects.create(
                    billno="C-DUP", date1="2024-06-01", voucher_type="Customer",
                    ldgr=ldgr, retail=retail, fiscal_year=fy,
                )

    def test_same_billno_different_type_is_allowed(self):
        # Customer and Vendor may legitimately share a billno string (legacy).
        from purchase.models import PurchaseVoucher
        retail = _make_retail(); fy = _make_fy(retail); ldgr = _make_ledger()
        PurchaseVoucher.objects.create(
            billno="X-1", date1="2024-05-01", voucher_type="Customer",
            ldgr=ldgr, retail=retail, fiscal_year=fy,
        )
        PurchaseVoucher.objects.create(
            billno="X-1", date1="2024-05-01", voucher_type="Vendor",
            ldgr=ldgr, retail=retail, fiscal_year=fy,
        )
        self.assertEqual(PurchaseVoucher.objects.filter(retail=retail, billno="X-1").count(), 2)


class PurchaseReturnUniqueTest(TestCase):
    """uniq_pr_number: (retail, fiscal_year, billno)."""

    def test_duplicate_billno_raises_integrity_error(self):
        from purchase.models import PurchaseReturn
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        PurchaseReturn.objects.create(
            billno="PR-DUP", date1="2024-05-01",
            ldgr=ldgr, discount=0, narration="test",
            mode_of_transport="Road",
            retail=retail, fiscal_year=fy,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PurchaseReturn.objects.create(
                    billno="PR-DUP", date1="2024-06-01",
                    ldgr=ldgr, discount=0, narration="test2",
                    mode_of_transport="Road",
                    retail=retail, fiscal_year=fy,
                )

    def test_different_billno_is_allowed(self):
        from purchase.models import PurchaseReturn
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        PurchaseReturn.objects.create(
            billno="PR-001", date1="2024-05-01",
            ldgr=ldgr, discount=0, narration="a",
            mode_of_transport="Road",
            retail=retail, fiscal_year=fy,
        )
        PurchaseReturn.objects.create(
            billno="PR-002", date1="2024-06-01",
            ldgr=ldgr, discount=0, narration="b",
            mode_of_transport="Road",
            retail=retail, fiscal_year=fy,
        )
        self.assertEqual(PurchaseReturn.objects.filter(retail=retail).count(), 2)


class PurchaseOrderUniqueTest(TestCase):
    """uniq_po_number: (retail, fiscal_year, po_no)."""

    def test_duplicate_po_no_raises_integrity_error(self):
        from purchase.models import PurchaseOrder
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        PurchaseOrder.objects.create(
            date1="2024-05-01", po_type="Stock", po_no="PO-DUP",
            ldgr=ldgr, retail=retail, fiscal_year=fy,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PurchaseOrder.objects.create(
                    date1="2024-06-01", po_type="Stock", po_no="PO-DUP",
                    ldgr=ldgr, retail=retail, fiscal_year=fy,
                )
