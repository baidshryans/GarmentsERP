import csv
import io
import os
import tempfile

from django.test import TestCase
from django.core.management import call_command
from accounting.models import Account
from contacts.models import Ledger


class ImportaccsMappingTests(TestCase):
    """importaccs must land ledgers on the canonical standard tree and never
    create the legacy MG-*/GM-*/SG-* Account rows.

    The legacy CSVs use numeric ids; the DB codes those ids map to are
    prefixed by level (main->MG-, group master->GM-, subgroup->SG-). The
    ledger gr_code is "<mn_grp>-<group_master_id>[-<subgroup_id>]".
    """

    def setUp(self):
        call_command("setup_account_groups")
        self.dir = tempfile.mkdtemp()

    def _write(self, name, rows):
        with open(os.path.join(self.dir, name), "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows)

    def test_ledgers_land_on_standard_groups_no_legacy_rows(self):
        # main id 3 -> MG-3 -> INC; group master id 13 -> GM-13 -> INC-DIR-SAL.
        self._write("main_group.csv", [["id", "name"], ["3", "Income"]])
        self._write("group_master.csv", [["id", "name", "mn_grp"], ["13", "Sales Account", "3"]])
        self._write("subgroup_master.csv", [["id", "name", "grp", "mn_grp", "edit_delit"]])
        self._write("ledger_master.csv", [
            ["id", "ac_name", "gr_code", "mobile1", "ledger_type"],
            ["900100", "Ornament Sales", "3-13", "", ""],
        ])

        # Capture output via StringIO — importaccs emits emoji that the Windows
        # console (cp1252) can't encode when a test wraps the real stdout.
        call_command("importaccs", base_path=self.dir,
                     stdout=io.StringIO(), stderr=io.StringIO())

        led = Ledger.objects.get(id=900100)
        self.assertEqual(led.ac_group.code, "INC-DIR-SAL")
        # No legacy Account rows were created.
        self.assertFalse(Account.objects.filter(code="GM-13").exists())
        self.assertFalse(Account.objects.filter(code="MG-3").exists())
