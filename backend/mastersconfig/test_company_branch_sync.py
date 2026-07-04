from django.test import TestCase
from mastersconfig.views import MySQLSyncView
from mastersconfig.models import CompanyMaster, State


class FakeCursor:
    """Minimal stand-in for a pymysql DictCursor over canned tables."""
    def __init__(self, tables):
        self._tables = tables            # {"COMPANY": [ {..row..}, ... ]}
        self._rows = []

    def execute(self, sql):
        # sql looks like: SELECT * FROM <table>
        table = sql.strip().split()[-1]
        if table not in self._tables:
            raise Exception(f"no such table: {table}")
        self._rows = self._tables[table]

    def fetchall(self):
        return self._rows


class SyncCompanyTests(TestCase):
    def setUp(self):
        self.view = MySQLSyncView()
        State.objects.create(name="West Bengal", code="19", type="state", tin=19)

    def test_creates_company_with_mapped_fields(self):
        cur = FakeCursor({"COMPANY": [{
            "comp_code": 1, "name": "Acme Jewels", "addr": "12 MG Road",
            "pin": "700001", "state": "West Bengal", "country": "India",
            "pan": "AAAPL1234C", "tan": "CALA00000B", "cin": "U36911WB2009PTC012345",
        }]})
        result = self.view._sync_company(cur)
        self.assertEqual(result["created"], 1)
        c = CompanyMaster.objects.get(company_name="Acme Jewels")
        self.assertEqual(c.legal_name, "Acme Jewels")
        self.assertEqual(c.address, "12 MG Road")
        self.assertEqual(c.pincode, "700001")
        self.assertEqual(c.pan, "AAAPL1234C")
        self.assertEqual(c.tan, "CALA00000B")
        self.assertEqual(c.cin, "U36911WB2009PTC012345")
        self.assertEqual(c.state.name, "West Bengal")

    def test_upsert_is_idempotent(self):
        cur = FakeCursor({"COMPANY": [{"comp_code": 1, "name": "Acme Jewels"}]})
        self.view._sync_company(cur)
        result = self.view._sync_company(cur)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(CompanyMaster.objects.filter(company_name="Acme Jewels").count(), 1)

    def test_missing_table_soft_errors(self):
        cur = FakeCursor({})
        result = self.view._sync_company(cur)
        self.assertEqual(result["created"], 0)
        self.assertTrue(result["errors"])
