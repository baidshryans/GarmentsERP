"""
Sales voucher edit-mode perf: the edit form used to fetch unlinked advance
receipts via a second, sequential round-trip (GET /accounting/api/
unlinked-receipts/?ldgr_id=...) fired only after the voucher itself loaded,
because it needs obj.ldgr which is only known once the voucher response
arrives. Folding this into SalesVouSerializer eliminates that round-trip.
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounting.models import ReferenceBills, VoucherDetail, VoucherMain
from contacts.models import Ledger
from mastersconfig.models import RetailMaster, SalesPersonMaster
from sales.models import SalesVou
from sales.serializers import SalesVouSerializer


def make_retail(code="R001"):
    return RetailMaster.objects.create(
        retail_name=f"Store {code}", retail_code=code,
        address_line1="123 St", phone="9999",
    )


def make_sale_voucher(retail, ldgr, sales_person, billno):
    return SalesVou.objects.create(
        date1=datetime.date(2026, 1, 1), billno=billno,
        ldgr=ldgr, sales_person=sales_person,
        place_of_supply="Test State", retail=retail,
    )


class UnlinkedReceiptsFieldTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.customer = Ledger.objects.create(ac_name="Test Customer", display_name="Test Customer")
        self.sp = SalesPersonMaster.objects.create(salesperson_name="Test SP", retail=self.retail)

    def test_unlinked_receipt_for_the_voucher_customer_is_included(self):
        sv = make_sale_voucher(self.retail, self.customer, self.sp, "S/1")
        vm = VoucherMain.objects.create(
            date=datetime.date(2026, 1, 1), voucher_no="RCPT/1", narration="advance",
            amount=Decimal("2000.00"), voucher_type="RCPT-SALE", status="posted",
            retail=self.retail,
        )
        VoucherDetail.objects.create(
            voucher_main=vm, voucher_no="RCPT/1", account=self.customer,
            credit=Decimal("2000.00"), voucher_type="RCPT-SALE", status="posted",
        )

        data = SalesVouSerializer(sv).data

        self.assertIn("unlinked_receipts", data)
        self.assertEqual(len(data["unlinked_receipts"]), 1)
        self.assertEqual(data["unlinked_receipts"][0]["id"], vm.id)
        self.assertEqual(data["unlinked_receipts"][0]["amount_remaining"], 2000.0)

    def test_no_receipts_returns_empty_list(self):
        sv = make_sale_voucher(self.retail, self.customer, self.sp, "S/2")

        data = SalesVouSerializer(sv).data

        self.assertEqual(data["unlinked_receipts"], [])

    def test_receipt_for_a_different_customer_is_excluded(self):
        sv = make_sale_voucher(self.retail, self.customer, self.sp, "S/3")
        other_customer = Ledger.objects.create(ac_name="Other Customer", display_name="Other Customer")
        vm = VoucherMain.objects.create(
            date=datetime.date(2026, 1, 1), voucher_no="RCPT/2", narration="advance",
            amount=Decimal("500.00"), voucher_type="RCPT-SALE", status="posted",
            retail=self.retail,
        )
        VoucherDetail.objects.create(
            voucher_main=vm, voucher_no="RCPT/2", account=other_customer,
            credit=Decimal("500.00"), voucher_type="RCPT-SALE", status="posted",
        )

        data = SalesVouSerializer(sv).data

        self.assertEqual(data["unlinked_receipts"], [])
