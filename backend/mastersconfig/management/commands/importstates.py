import csv
from django.core.management.base import BaseCommand
from mastersconfig.models import State  # Replace with actual app name

class Command(BaseCommand):
    help = 'Import State data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('state_csv', type=str, help='Path to the State CSV file')

    def handle(self, *args, **kwargs):
        state_csv = kwargs['state_csv']
        
        # Import State data
        with open(state_csv, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                State.objects.update_or_create(
                    id=int(row['id']),
                    defaults={
                        'name': row['state'],
                        'type': row['type'],
                        'tin': int(row['tin']),
                        'code': row['code']
                    }
                )
        self.stdout.write(self.style.SUCCESS('State data imported successfully!'))