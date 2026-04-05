import csv
from django.core.management.base import BaseCommand
from mastersconfig.models import Colors  # Replace with actual app name

class Command(BaseCommand):
    help = 'Import Colors data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('colors_csv', type=str, help='Path to the Colors CSV file')

    def handle(self, *args, **kwargs):
        colors_csv = kwargs['colors_csv']
        
        # Import Colors
        with open(colors_csv, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                Colors.objects.update_or_create(
                    id=int(row['id']),
                    defaults={'color_name': row['name']}
                )
        self.stdout.write(self.style.SUCCESS('Colors data imported successfully!'))
