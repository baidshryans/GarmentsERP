import csv
from django.core.management.base import BaseCommand
from contacts.models import Ledger
from mastersconfig.models import Item



class Command(BaseCommand):
    help = 'Import ITEM_MASTER data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:  
               purchaseledger,_=Ledger.objects.get_or_create(ac_name=row['Purchase_ledger_ac_name'])
               print("pl name : ",row['Purchase_ledger_ac_name'])
               print("sl name : ",row['Sale_ledger_ac_name'])
               saleledger,_=Ledger.objects.get_or_create(ac_name=row['Sale_ledger_ac_name'])
               print("short code",row['short_code'])
               item,_=Item.objects.get_or_create(short_code=row['short_code'])
               item.purchase_ledger=purchaseledger
               item.sale_ledger=saleledger
               item.save()

        self.stdout.write(self.style.SUCCESS(' item_master data imported successfully!'))       
               