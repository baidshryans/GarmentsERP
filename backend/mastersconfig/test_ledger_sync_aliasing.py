from django.test import TestCase
from django.core.management import call_command
from mastersconfig.views import MySQLSyncView
from mastersconfig.models import RetailMaster, CompanyMaster
from contacts.models import Ledger, LedgerAlias


class FakeCursor:
    """Minimal DictCursor stand-in: returns preset dict rows per table."""
    def __init__(self, tables):
        self.tables = tables
        self._table = None

    def execute(self, sql):
        # sql is always "SELECT * FROM <table>"
        self._table = sql.strip().split()[-1]

    def fetchall(self):
        return self.tables.get(self._table, [])


class LedgerSyncAliasingTests(TestCase):
    def setUp(self):
        call_command("setup_account_groups")
        # seed_system_ledgers creates trading ledgers (Ornament Sales, ...) per
        # CompanyMaster, so a company must exist for the sales-fold test.
        CompanyMaster.objects.create(company_name="Test Co")
        RetailMaster.objects.create(
            retail_code="R001", retail_name="HO", address_line1="x", phone="1",
        )
        call_command("setup_tds_initial_data")
        call_command("seed_hr_ledgers")
        call_command("seed_system_ledgers")

    def _sync(self, ledger_rows):
        cursor = FakeCursor({
            "main_group": [], "group_master": [], "subgroup_master": [],
            "ledger_master": ledger_rows,
        })
        return MySQLSyncView()._sync_ledger(cursor)

    def test_legacy_tds_folds_onto_seeded_section_ledger(self):
        seeded = Ledger.objects.get(ac_name="TDS Payable u/s 194C")
        self._sync([{"ldgr_code": "7932", "ac_name": "T.D.S_94C", "ac_grp": "Expense Payable"}])
        alias = LedgerAlias.objects.filter(legacy_code="7932").first()
        self.assertIsNotNone(alias)
        self.assertEqual(alias.ledger_id, seeded.id)
        # No duplicate ledger created under the legacy code.
        self.assertFalse(Ledger.objects.filter(id=7932).exists())

    def test_legacy_pf_folds_onto_seeded_pf_ledger(self):
        seeded = Ledger.objects.get(ac_name="PF Payable")
        self._sync([{"ldgr_code": "2103", "ac_name": "Provident Fund (Employee)", "ac_grp": "Expense Payable"}])
        alias = LedgerAlias.objects.filter(legacy_code="2103").first()
        self.assertIsNotNone(alias)
        self.assertEqual(alias.ledger_id, seeded.id)

    def test_legacy_sales_ledger_is_created_not_folded(self):
        # Commodity sales ledgers are the client's own now (not seeded), so a legacy
        # sales ledger is created under the legacy group; the chart finalize later
        # regroups it. It must NOT be aliased away.
        self._sync([{"ldgr_code": "2012", "ac_name": "Ornament Sales", "ac_grp": "Sales Account"}])
        self.assertFalse(LedgerAlias.objects.filter(legacy_code="2012").exists())
        self.assertTrue(Ledger.objects.filter(id=2012).exists())
