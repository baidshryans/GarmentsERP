import csv
from django.core.management.base import BaseCommand
from mastersconfig.models import Hsn  # Replace 'your_app' with the actual app name

class Command(BaseCommand):
    help = 'Import HSN data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                Hsn.objects.update_or_create(
                    id=row['id'],
                    defaults={
                        'hsn_no': row['hsn_no'],
                        'hsn_type': 'GD' if row['hsn_type'] == '0' else 'SR',
                        'cgst': row['hsn_per_cgst'],
                        'sgst': row['hsn_per'],
                        'igst': row['hsn_per_igst'],
                        'description': row['description'],
                    }
                )
        self.stdout.write(self.style.SUCCESS('HSN data imported successfully!'))