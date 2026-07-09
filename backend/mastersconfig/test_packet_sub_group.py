from django.db import IntegrityError, transaction
from django.test import TestCase

from mastersconfig.models import Packet, PacketGroup, PacketSubGroup


class PacketSubGroupModelTest(TestCase):
    def setUp(self):
        self.diamond = PacketGroup.objects.create(packet_group_name="Diamond")
        self.ruby = PacketGroup.objects.create(packet_group_name="Ruby")

    def test_str_includes_parent_group(self):
        sg = PacketSubGroup.objects.create(packet_group=self.diamond, packet_sub_group_name="Small")
        self.assertEqual(str(sg), "Diamond / Small")

    def test_same_name_allowed_under_different_groups(self):
        PacketSubGroup.objects.create(packet_group=self.diamond, packet_sub_group_name="Small")
        # Should not raise — same sub group name, different parent group.
        PacketSubGroup.objects.create(packet_group=self.ruby, packet_sub_group_name="Small")
        self.assertEqual(PacketSubGroup.objects.filter(packet_sub_group_name="Small").count(), 2)

    def test_duplicate_name_rejected_within_same_group(self):
        PacketSubGroup.objects.create(packet_group=self.diamond, packet_sub_group_name="Small")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PacketSubGroup.objects.create(packet_group=self.diamond, packet_sub_group_name="Small")

    def test_deleting_sub_group_does_not_delete_packet(self):
        sg = PacketSubGroup.objects.create(packet_group=self.diamond, packet_sub_group_name="Small")
        pkt = Packet.objects.create(
            packet_group=self.diamond, packet_sub_group=sg, pckt_no="DIA-001",
            is_solitaire=False, rate_for_retail=100, is_customer_stone=False,
        )
        sg.delete()
        pkt.refresh_from_db()
        self.assertIsNone(pkt.packet_sub_group)

    def test_deleting_group_cascades_to_sub_group(self):
        sg = PacketSubGroup.objects.create(packet_group=self.diamond, packet_sub_group_name="Small")
        self.diamond.delete()
        self.assertFalse(PacketSubGroup.objects.filter(pk=sg.pk).exists())
