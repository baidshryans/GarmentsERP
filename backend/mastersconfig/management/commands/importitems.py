import csv
from django.core.management.base import BaseCommand
from mastersconfig.models import Item, ItemGroupMaster, Hsn  # Replace 'your_app' with the actual app name
from contacts.models import Ledger

class Command(BaseCommand):
    help = 'Import Item data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                grp = ItemGroupMaster.objects.filter(id=row['grp']).first()
                # purchase_ledger = Ledger.objects.filter(id= row['purchase_ledger'] ).first() if row['purchase_ledger'] else None
                purchase_ledger = Ledger.objects.filter(id= 1031 ).first() if row['purchase_ledger'] else None
                # sale_ledger = Ledger.objects.filter(id=row['sale_ledger']).first() if row['sale_ledger'] else None
                sale_ledger = Ledger.objects.filter(id=1012).first() if row['sale_ledger'] else None
                print(row['hsn_no'])
                hsn_no = Hsn.objects.get(id=int(row['hsn_no'])) if row['hsn_no']!="0" else None

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