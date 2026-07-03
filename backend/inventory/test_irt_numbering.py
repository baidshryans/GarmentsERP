"""
Race-safe numbering for InterRetailTransferVoucher (IRT).

IRT is special: its number series is owned by the SOURCE retail (from_retail);
the model has no plain `retail` field. These tests cover:
  - authoritative, incrementing numbering via save_with_bill_number
  - peek/resync bootstrap scoped to from_retail
  - the scoped UniqueConstraint (from_retail, fiscal_year, voucher_no)
  - reclaim-on-delete of the latest number (view-layer, mirrored here)
"""
import datetime
from django.db import IntegrityError, transaction
from django.test import TestCase

from mastersconfig.models import RetailMaster, FiscalYearMaster
from inventory.models import InterRetailTransferVoucher as IRT
from accounting.utils import (
    save_with_bill_number, peek_next_bill_number, release_last_bill_number,
)


class IRTNumberingTests(TestCase):
    def setUp(self):
        self.src = RetailMaster.objects.create(
            retail_name="Source", retail_code="RSRC", address_line1="x",
            phone="1")
        self.dst = RetailMaster.objects.create(
            retail_name="Dest", retail_code="RDST", address_line1="y",
            phone="2")
        self.fy = FiscalYearMaster.objects.create(
            retail=self.src, fy_code="26-27",
            fy_start=datetime.date(2026, 4, 1), fy_end=datetime.date(2027, 3, 31))
        self.src.active_fy = self.fy
        self.src.save(update_fields=["active_fy"])

    def _new(self):
        return IRT(transfer_date=datetime.date(2026, 4, 15),
                   from_retail=self.src, to_retail=self.dst, fiscal_year=self.fy)

    def _issue(self):
        return save_with_bill_number(self._new(), self.src, "IRT",
                                     field="voucher_no", fy=self.fy)

    def test_numbers_increment_per_source_retail(self):
        a = self._issue()
        b = self._issue()
        self.assertTrue(a.voucher_no.endswith("00001"), a.voucher_no)
        self.assertTrue(b.voucher_no.endswith("00002"), b.voucher_no)

    def test_peek_reflects_existing_records(self):
        self._issue()  # ...00001
        self.assertTrue(peek_next_bill_number(self.src, "IRT", self.fy).endswith("00002"))

    def test_unique_constraint_blocks_same_source_number(self):
        a = self._issue()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                dup = self._new()
                dup.voucher_no = a.voucher_no
                dup.save()

    def test_same_number_different_source_retail_allowed(self):
        a = self._issue()
        other = IRT(transfer_date=datetime.date(2026, 4, 15),
                    from_retail=self.dst, to_retail=self.src,
                    fiscal_year=self.fy, voucher_no=a.voucher_no)
        other.save()  # different from_retail → allowed
        self.assertEqual(IRT.objects.filter(voucher_no=a.voucher_no).count(), 2)

    def test_reclaim_on_latest_delete(self):
        # Mirrors the viewset destroy: delete the latest, then release.
        self._issue()                 # 00001
        b = self._issue()             # 00002
        no, fr, fy = b.voucher_no, b.from_retail, b.fiscal_year
        b.delete()
        release_last_bill_number(fr, "IRT", no, fy)
        self.assertTrue(peek_next_bill_number(self.src, "IRT", self.fy).endswith("00002"))

    def test_non_latest_delete_leaves_gap(self):
        a = self._issue()             # 00001
        self._issue()                 # 00002
        no, fr, fy = a.voucher_no, a.from_retail, a.fiscal_year
        a.delete()                    # delete the FIRST (non-latest)
        release_last_bill_number(fr, "IRT", no, fy)  # no-op: not the latest
        # sequence unchanged → next is 00003 (gap at 00001 accepted)
        self.assertTrue(peek_next_bill_number(self.src, "IRT", self.fy).endswith("00003"))
