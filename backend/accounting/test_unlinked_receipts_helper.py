"""
unlinked_receipts_for_ledger() was extracted from UnlinkedReceiptsView so the
Sales Voucher edit form's hydration effect can get this data folded into the
GET /sales/api/sale-voucher/<id>/ response instead of firing a second,
sequential round-trip after the voucher loads (see project memory
project_fixed_asset_ledger_link.md — sales voucher edit-mode perf work).
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from accounting.models import ReferenceBills, VoucherDetail, VoucherMain
from accounting.views.vouchers import unlinked_receipts_for_ledger
from contacts.models import Ledger
from mastersconfig.models import RetailMaster


def make_retail(code="R001"):
    return RetailMaster.objects.create(
        retail_name=f"Store {code}", retail_code=code,
        address_line1="123 St", phone="9999",
    )


def make_ledger(name, id=None):
    kwargs = dict(ac_name=name, display_name=name)
    if id is not None:
        kwargs["id"] = id
    return Ledger.objects.create(**kwargs)


def make_receipt_voucher(retail, party_ledger, amount, voucher_no, voucher_type="RCPT-SALE"):
    vm = VoucherMain.objects.create(
        date=datetime.date(2026, 1, 1), voucher_no=voucher_no,
        narration="test receipt", amount=Decimal(amount),
        voucher_type=voucher_type, status="posted", retail=retail,
    )
    VoucherDetail.objects.create(
        voucher_main=vm, voucher_no=voucher_no, account=party_ledger,
        credit=Decimal(amount), voucher_type=voucher_type, status="posted",
    )
    return vm


class UnlinkedReceiptsForLedgerTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.party = make_ledger("Test Customer")

    def test_fully_unallocated_receipt_is_returned(self):
        vm = make_receipt_voucher(self.retail, self.party, "5000.00", "RCPT/1")

        rows = unlinked_receipts_for_ledger(self.retail, self.party.id)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], vm.id)
        self.assertEqual(rows[0]["amount_remaining"], 5000.0)

    def test_fully_allocated_receipt_is_excluded(self):
        vm = make_receipt_voucher(self.retail, self.party, "3000.00", "RCPT/2")
        ReferenceBills.objects.create(ldgr=self.party, voucher=vm, amount=Decimal("3000.00"))

        rows = unlinked_receipts_for_ledger(self.retail, self.party.id)

        self.assertEqual(rows, [])

    def test_partially_allocated_receipt_reports_remaining_only(self):
        vm = make_receipt_voucher(self.retail, self.party, "1000.00", "RCPT/3")
        ReferenceBills.objects.create(ldgr=self.party, voucher=vm, amount=Decimal("400.00"))

        rows = unlinked_receipts_for_ledger(self.retail, self.party.id)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["amount_remaining"], 600.0)

    def test_receipt_for_different_ledger_is_excluded(self):
        other_party = make_ledger("Other Customer")
        make_receipt_voucher(self.retail, other_party, "2000.00", "RCPT/4")

        rows = unlinked_receipts_for_ledger(self.retail, self.party.id)

        self.assertEqual(rows, [])
