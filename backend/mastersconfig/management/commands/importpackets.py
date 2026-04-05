import csv
from django.core.management.base import BaseCommand
from django.utils import timezone
from mastersconfig.models import Packet, Item, Colors, Shapes, PacketGroup  # Replace with actual app names

class Command(BaseCommand):
    help = 'Import Packet data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file = kwargs['csv_file']
        with open(csv_file, newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                stone_item, _ = Item.objects.get_or_create(id=int(row['stone_id']))
                color = Colors.objects.filter(id=int(row['color_id'])).first()
                shape = Shapes.objects.filter(id=int(row['shape_id'])).first()
                packet_group = PacketGroup.objects.first()  # Modify as needed
                
                Packet.objects.update_or_create(
                    pckt_no=row['pckt_no'],
                    defaults={
                        'packet_group': packet_group,
                        'stone_item_id': stone_item,
                        'cut': row.get('cut_id', ''),
                        'clarity': row.get('quality_id', ''),
                        'color': color,
                        'shape': shape,
                        'seives': row.get('seives_id', ''),
                        'is_solitaire': row['solitare'] == 'Y',
                        'rate_for_retail': int(float(row['rate_for_retail'])),
                        'rate_for_wholesale': int(float(row['rate_for_wholesale'])),
                        'is_customer_stone': row['customer'] == '1',
                        'created_date': timezone.now(),
                    }
                )
        self.stdout.write(self.style.SUCCESS('Packet data imported successfully!'))
