import csv
from django.core.management.base import BaseCommand
from mastersconfig.models import SalesPersonMaster, RetailMaster  # Replace with actual app name

class Command(BaseCommand):
    help = 'Import SalesPersonMaster data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('salesperson_csv', type=str, help='Path to the SalesPersonMaster CSV file')

    def handle(self, *args, **kwargs):
        salesperson_csv = kwargs['salesperson_csv']
        
        # Import SalesPersonMaster
        with open(salesperson_csv, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # retail_master = RetailMaster.objects.filter(rt_code=row['rt_code']).first()
                retail_master = RetailMaster.objects.filter(id=1).first()
                SalesPersonMaster.objects.update_or_create(
                    id=int(row['id']),
                    defaults={
                        'salesperson_name': row['s_name'],
                        'retail': retail_master
                    }
                )
        self.stdout.write(self.style.SUCCESS('SalesPersonMaster data imported successfully!'))
