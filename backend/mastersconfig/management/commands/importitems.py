import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from mastersconfig.models import Item, ItemGroupMaster, Hsn
from contacts.models import Ledger


def _resolve_item_ledger(val):
    """CSV item ledger reference (id or name) -> the client's Ledger, or None.
    Numeric values resolve via legacy id / LedgerAlias; anything else by name."""
    from accounting.migration_utils import resolve_ledger
    s = (str(val).strip() if val is not None else '')
    if not s:
        return None
    if s.lstrip('-').replace('.', '', 1).isdigit():
        led = resolve_ledger(s)
        if led is not None:
            return led
    return Ledger.objects.filter(ac_name=s).first()


class Command(BaseCommand):
    help = 'Import Item data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    @transaction.atomic
    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                grp = (ItemGroupMaster.objects.filter(id=row['grp']).first()
                       if str(row.get('grp') or '').strip().isdigit() else None)
                purchase_ledger = _resolve_item_ledger(row.get('purchase_ledger'))
                sale_ledger = _resolve_item_ledger(row.get('sale_ledger'))
                hsn_no = Hsn.objects.get(id=int(row['hsn_no'])) if row['hsn_no'] != "0" else None

                Item.objects.update_or_create(
                    id=row['item_id'],
                    defaults={
                        'short_code': row['short_code'],
                        'item_name': row['item'],
                        'grp': grp,
                        'sub_grp': row['sub_grp'],
                        'item_type': row['item_type'],
                        'uom': row['uom'],
                        'purchase_ledger': purchase_ledger,
                        'sale_ledger': sale_ledger,
                        'show_in_pcs_report': bool(int(row['show_in_pcs_report'])),
                        'hsn_no': hsn_no,
                    }
                )
        self.stdout.write(self.style.SUCCESS('Item data imported successfully!'))