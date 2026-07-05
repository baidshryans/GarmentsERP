from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from mastersconfig.views import MySQLSyncView
from accounting.models import Account, VoucherMain, VoucherDetail
from contacts.models import Ledger


class SyncChartFinalizeTests(TestCase):
    """After the MySQL sync rebuilds the legacy MG/GM/SG chart, the finalize step
    must collapse it onto the standard tree so the P&L reads real figures."""

    def setUp(self):
        call_command("setup_account_groups")
        # Legacy Sales Account group (GM-13) with a sales ledger + a credit posting,
        # mirroring what _sync_ledger reconstructs from the old ERP.
        mg3 = Account.objects.create(code="MG-3", name="Income", parent=None)
        gm13 = Account.objects.create(code="GM-13", name="Sales Account", parent=mg3)
        self.led = Ledger.objects.create(
            id=920001, ac_name="Ornament Sales", display_name="Ornament Sales",
            ac_group=gm13,
        )
        vm = VoucherMain.objects.create(
            date=date(2026, 4, 1), voucher_no="F-1", narration="sale",
            amount=Decimal("1000"), voucher_type="SALE",
        )
        VoucherDetail.objects.create(
            voucher_main=vm, voucher_no="F-1", voucher_type="SALE",
            account=self.led, debit=Decimal("0"), credit=Decimal("1000"),
        )

    def test_finalize_moves_ledger_to_standard_group_and_clears_legacy(self):
        result = MySQLSyncView()._finalize_chart_of_accounts()
        self.assertEqual(result["status"], "ok")
        self.led.refresh_from_db()
        self.assertEqual(self.led.ac_group.code, "INC-DIR-SAL")
        self.assertFalse(Account.objects.filter(code="GM-13").exists())
        self.assertFalse(Account.objects.filter(code="MG-3").exists())

    def test_pnl_sees_sales_after_finalize(self):
        from accounting.views.reports import calcuate_pnl
        MySQLSyncView()._finalize_chart_of_accounts()
        d = calcuate_pnl(start_date="2026-04-01", end_date="2026-07-05", retail_ids=None)
        self.assertEqual(d["sales_revenue"], Decimal("1000"))
