from django.test import TestCase
from django.core.management import call_command
from mastersconfig.models import TDSSectionMaster, RetailMaster


class TdsSeedSectionsTests(TestCase):
    def setUp(self):
        call_command("setup_account_groups")
        # setup_tds_initial_data creates per-retail ledgers, so a retail must exist.
        RetailMaster.objects.create(
            retail_code="R001", retail_name="HO", address_line1="x", phone="1",
            bill_series="A",
        )

    def test_new_sections_seeded_and_linked(self):
        call_command("setup_tds_initial_data")
        for code in ("194A", "192B", "195"):
            sec = TDSSectionMaster.objects.filter(section_code=code).first()
            self.assertIsNotNone(sec, f"section {code} not seeded")
            self.assertIsNotNone(sec.ledger, f"section {code} has no linked ledger")
            self.assertEqual(sec.ledger.ac_name, f"TDS Payable u/s {code}")

    def test_existing_sections_untouched(self):
        call_command("setup_tds_initial_data")
        self.assertTrue(TDSSectionMaster.objects.filter(section_code="194C").exists())
