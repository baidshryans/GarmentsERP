import csv
from django.core.management.base import BaseCommand
from mastersconfig.models import ItemGroupMaster  # Replace 'your_app' with the actual app name

class Command(BaseCommand):
    help = 'Import Item Group Master data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                ItemGroupMaster.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        'item_group_name': row['name'],
                        'short_code': row['short_code'],
                    }
                )
        self.stdout.write(self.style.SUCCESS('Item Group Master data imported successfully!'))