from django.test import TestCase
from django.core.management import call_command
from mastersconfig.views import MySQLSyncView
from contacts.models import Ledger
from inventory.models import Item


class FakeCursor:
    """DictCursor stand-in returning preset rows per table (matched on the last
    whitespace-delimited token of the SQL, i.e. the table name)."""
    def __init__(self, tables):
        self.tables = tables
        self._table = None

    def execute(self, sql):
        self._table = sql.strip().split()[-1].strip("'\"")

    def fetchall(self):
        return self.tables.get(self._table, [])


class SyncItemLedgerTests(TestCase):
    def setUp(self):
        call_command("setup_account_groups")
        # A client sales ledger (as the ledger sync would create it), id 5001.
        self.sale = Ledger.objects.create(
            id=5001, ac_name="Ornament Sales", display_name="Ornament Sales",
        )
        self.pur = Ledger.objects.create(
            id=5002, ac_name="Ornament Purchase", display_name="Ornament Purchase",
        )

    def _sync_items(self, item_rows):
        cursor = FakeCursor({"hsn_master": [], "item_master": item_rows})
        return MySQLSyncView()._sync_item(cursor)

    def test_item_links_to_ledger_by_id(self):
        self._sync_items([{
            "item_id": "701", "short_code": "ORN", "item": "Ornament", "item_type": "M",
            "uom": "Gm", "hsn_no": None, "show_in_pcs_report": 0, "grp": None,
            "sub_grp": "", "purchase_ledger": "5002", "sale_ledger": "5001",
        }])
        it = Item.objects.get(id=701)
        self.assertEqual(it.sale_ledger_id, 5001)
        self.assertEqual(it.purchase_ledger_id, 5002)

    def test_item_links_to_ledger_by_name(self):
        self._sync_items([{
            "item_id": "702", "short_code": "ORN2", "item": "Ornament2", "item_type": "M",
            "uom": "Gm", "hsn_no": None, "show_in_pcs_report": 0, "grp": None,
            "sub_grp": "", "purchase_ledger": "Ornament Purchase", "sale_ledger": "Ornament Sales",
        }])
        it = Item.objects.get(id=702)
        self.assertEqual(it.sale_ledger_id, 5001)

    def test_unresolvable_ledger_is_null_and_counted(self):
        result = self._sync_items([{
            "item_id": "703", "short_code": "ORN3", "item": "Ornament3", "item_type": "M",
            "uom": "Gm", "hsn_no": None, "show_in_pcs_report": 0, "grp": None,
            "sub_grp": "", "purchase_ledger": "", "sale_ledger": "does-not-exist",
        }])
        it = Item.objects.get(id=703)
        self.assertIsNone(it.sale_ledger_id)
        self.assertIsNone(it.purchase_ledger_id)
        # sale_ledger was present but unresolvable -> counted; empty purchase not counted.
        self.assertEqual(result["unresolved_ledgers"], 1)
