import csv
import io
import os
import tempfile

from django.test import TestCase
from django.core.management import call_command
from contacts.models import Ledger
from inventory.models import Item


class ImportItemsLedgerTests(TestCase):
    def setUp(self):
        call_command("setup_account_groups")
        self.sale = Ledger.objects.create(
            id=5001, ac_name="Ornament Sales", display_name="Ornament Sales",
        )
        self.pur = Ledger.objects.create(
            id=5002, ac_name="Ornament Purchase", display_name="Ornament Purchase",
        )
        self.dir = tempfile.mkdtemp()

    def _run(self, rows):
        path = os.path.join(self.dir, "items.csv")
        cols = ["item_id", "short_code", "item", "grp", "sub_grp", "item_type",
                "uom", "purchase_ledger", "sale_ledger", "show_in_pcs_report", "hsn_no"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        call_command("importitems", path, stdout=io.StringIO(), stderr=io.StringIO())

    def test_item_links_by_id(self):
        self._run([{
            "item_id": "801", "short_code": "ORN", "item": "Ornament", "grp": "",
            "sub_grp": "", "item_type": "M", "uom": "Gm",
            "purchase_ledger": "5002", "sale_ledger": "5001",
            "show_in_pcs_report": "0", "hsn_no": "0",
        }])
        it = Item.objects.get(id=801)
        self.assertEqual(it.sale_ledger_id, 5001)
        self.assertEqual(it.purchase_ledger_id, 5002)

    def test_item_links_by_name(self):
        self._run([{
            "item_id": "802", "short_code": "ORN2", "item": "Ornament2", "grp": "",
            "sub_grp": "", "item_type": "M", "uom": "Gm",
            "purchase_ledger": "Ornament Purchase", "sale_ledger": "Ornament Sales",
            "show_in_pcs_report": "0", "hsn_no": "0",
        }])
        it = Item.objects.get(id=802)
        self.assertEqual(it.sale_ledger_id, 5001)
        self.assertEqual(it.purchase_ledger_id, 5002)
