import csv
from django.core.management.base import BaseCommand
from mastersconfig.models import Shapes  # Replace 'mastersconfig' with the actual app name if different

class Command(BaseCommand):
    help = 'Import Shapes data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                Shapes.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        'shape_name': row['name'],
                        'shape_code': row['short_code'],
                    }
                )
        self.stdout.write(self.style.SUCCESS('Shapes data imported successfully!'))