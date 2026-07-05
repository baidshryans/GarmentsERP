import inspect
from django.test import TestCase
from mastersconfig.views import MySQLSyncView


class SyncOrderTests(TestCase):
    def test_ledger_syncs_before_item(self):
        src = inspect.getsource(MySQLSyncView.post)
        i_ledger = src.index("'ledger' in tables_requested")
        i_item = src.index("'item' in tables_requested")
        self.assertLess(
            i_ledger, i_item,
            "ledger must sync before item so items can resolve their ledgers",
        )
