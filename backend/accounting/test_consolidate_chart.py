from decimal import Decimal
from django.test import TestCase
from django.core.management import call_command
from accounting.models import Account, VoucherMain, VoucherDetail
from contacts.models import Ledger


class ConsolidateChartTests(TestCase):
    def setUp(self):
        call_command("setup_account_groups")
        # Build a minimal legacy tree: MG-3 -> GM-13 (Sales) with a ledger + txn.
        self.mg3 = Account.objects.create(code="MG-3", name="Income", parent=None)
        self.gm13 = Account.objects.create(code="GM-13", name="Sales Account", parent=self.mg3)
        self.led = Ledger.objects.create(
            id=900001, ac_name="Ornament Sales", display_name="Ornament Sales",
            ac_group=self.gm13,
        )
        vm = VoucherMain.objects.create(
            voucher_type="SALE", voucher_no="T-1", date="2026-07-01",
            narration="Test sale", amount=Decimal("1000"),
        )
        VoucherDetail.objects.create(
            voucher_main=vm, voucher_no="T-1", voucher_type="SALE",
            account=self.led, debit=Decimal("0"), credit=Decimal("1000"),
        )

    def test_dry_run_changes_nothing(self):
        call_command("consolidate_chart_of_accounts")  # no --apply
        self.led.refresh_from_db()
        self.assertEqual(self.led.ac_group_id, self.gm13.id)
        self.assertTrue(Account.objects.filter(code="GM-13").exists())

    def test_apply_remaps_ledger_and_deletes_legacy_group(self):
        std_sales = Account.objects.get(code="INC-DIR-SAL")
        call_command("consolidate_chart_of_accounts", "--apply")
        self.led.refresh_from_db()
        self.assertEqual(self.led.ac_group_id, std_sales.id)
        self.assertFalse(Account.objects.filter(code="GM-13").exists())
        self.assertFalse(Account.objects.filter(code="MG-3").exists())

    def test_apply_preserves_voucher_amounts(self):
        before = VoucherDetail.objects.count()
        call_command("consolidate_chart_of_accounts", "--apply")
        self.assertEqual(VoucherDetail.objects.count(), before)

    def test_idempotent_second_apply_is_noop(self):
        call_command("consolidate_chart_of_accounts", "--apply")
        call_command("consolidate_chart_of_accounts", "--apply")  # must not raise
        self.assertEqual(Ledger.objects.get(id=900001).ac_group.code, "INC-DIR-SAL")

    def test_missing_standard_target_aborts(self):
        # Remove a standard target the map points at; the pre-check must abort
        # before mutating anything.
        Account.objects.filter(code="INC-DIR-SAL").delete()
        with self.assertRaises(Exception):
            call_command("consolidate_chart_of_accounts", "--apply")
        self.assertEqual(Ledger.objects.get(id=900001).ac_group.code, "GM-13")

    def test_unmapped_legacy_group_with_ledgers_aborts(self):
        stray = Account.objects.create(code="GM-777", name="Mystery", parent=self.mg3)
        Ledger.objects.create(
            id=900002, ac_name="Mystery Ldgr", display_name="Mystery Ldgr",
            ac_group=stray,
        )
        with self.assertRaises(Exception):
            call_command("consolidate_chart_of_accounts", "--apply")
        # Nothing committed: original legacy ledger untouched.
        self.assertEqual(Ledger.objects.get(id=900001).ac_group.code, "GM-13")
