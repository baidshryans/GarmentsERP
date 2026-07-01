"""
Tests for the check_number_dupes management command.

Seeds two colliding RefinaryIssue rows (same retail + fiscal_year + billno)
and asserts the command detects them (exit code 1).
Also asserts clean data → exit code 0.
"""
import sys
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from accounting.management.commands.check_number_dupes import MODEL_CHECKS


class CheckNumberDupesCommandTest(TestCase):
    """Integration test: seeds DB rows and runs the full command."""

    def _get_or_create_retail(self):
        from mastersconfig.models import RetailMaster
        obj, _ = RetailMaster.objects.get_or_create(
            retail_code="TEST01",
            defaults={
                "retail_name": "Test Retail",
                "address_line1": "Test Address",
            },
        )
        return obj

    def _get_or_create_fy(self, retail):
        from mastersconfig.models import FiscalYearMaster
        obj, _ = FiscalYearMaster.objects.get_or_create(
            retail=retail,
            fy_code="24-25",
            defaults={
                "fy_start": "2024-04-01",
                "fy_end": "2025-03-31",
            },
        )
        return obj

    def _get_or_create_ledger(self):
        from contacts.models import Ledger
        obj, _ = Ledger.objects.get_or_create(
            ac_name="Test Ledger",
            defaults={
                "display_name": "Test Ledger",
            },
        )
        return obj

    def _run_command(self):
        """Run check_number_dupes and return (stdout, stderr, exit_code)."""
        out = StringIO()
        err = StringIO()
        # Patch sys.exit so we can capture the exit code without stopping the test.
        captured_exit = []
        with patch.object(sys, "exit", side_effect=lambda code: captured_exit.append(code)):
            try:
                call_command("check_number_dupes", stdout=out, stderr=err)
            except SystemExit as e:
                captured_exit.append(e.code)
        exit_code = captured_exit[0] if captured_exit else 0
        return out.getvalue(), err.getvalue(), exit_code

    def test_detects_colliding_refinery_issue_rows(self):
        """Two RefinaryIssue rows with same retail+fiscal_year+billno → exit 1."""
        from manufacturing.models import RefinaryIssue
        retail = self._get_or_create_retail()
        fy = self._get_or_create_fy(retail)
        ldgr = self._get_or_create_ledger()

        # Create two rows with an identical scoped number.
        RefinaryIssue.objects.create(
            date1="2024-05-01",
            billno="RI-001",
            ldgr=ldgr,
            retail=retail,
            fiscal_year=fy,
        )
        RefinaryIssue.objects.create(
            date1="2024-06-01",
            billno="RI-001",   # same number — collision
            ldgr=ldgr,
            retail=retail,
            fiscal_year=fy,
        )

        stdout, _stderr, exit_code = self._run_command()
        self.assertEqual(exit_code, 1, "Expected exit code 1 when duplicates exist")
        self.assertIn("DUPE", stdout)
        self.assertIn("RefinaryIssue", stdout)
        self.assertIn("RI-001", stdout)

    def test_clean_data_exits_zero(self):
        """With no duplicate rows in any model → exit 0."""
        from manufacturing.models import RefinaryIssue
        retail = self._get_or_create_retail()
        fy = self._get_or_create_fy(retail)
        ldgr = self._get_or_create_ledger()

        # Unique numbers only.
        RefinaryIssue.objects.create(
            date1="2024-05-01",
            billno="RI-UNIQUE-A",
            ldgr=ldgr,
            retail=retail,
            fiscal_year=fy,
        )
        RefinaryIssue.objects.create(
            date1="2024-06-01",
            billno="RI-UNIQUE-B",
            ldgr=ldgr,
            retail=retail,
            fiscal_year=fy,
        )

        stdout, _stderr, exit_code = self._run_command()
        self.assertEqual(exit_code, 0, "Expected exit code 0 when no duplicates exist")
        self.assertIn("no duplicates", stdout)

    def test_model_checks_constant_is_non_empty(self):
        """Sanity check: MODEL_CHECKS must contain at least the expected entries."""
        model_paths = [entry[0] for entry in MODEL_CHECKS]
        self.assertIn("purchase.PurchaseVoucher", model_paths)
        self.assertIn("manufacturing.RefinaryIssue", model_paths)
        self.assertIn("manufacturing.RepairJobCard", model_paths)
        self.assertGreaterEqual(len(MODEL_CHECKS), 17)
