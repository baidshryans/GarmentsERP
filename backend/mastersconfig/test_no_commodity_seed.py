from django.test import TestCase
from django.core.management import call_command
from mastersconfig.models import CompanyMaster
from contacts.models import Ledger


class NoCommoditySeedTests(TestCase):
    def setUp(self):
        call_command("setup_account_groups")
        CompanyMaster.objects.create(company_name="Test Co")
        call_command("seed_system_ledgers")

    def test_commodity_ledgers_not_seeded(self):
        for name in ("Gold Sales", "Ornament Sales", "Blue Sapphire Sales", "Diamond Purchase"):
            self.assertFalse(
                Ledger.objects.filter(ac_name=name, is_system=True).exists(),
                f"commodity ledger {name!r} should no longer be seeded",
            )

    def test_functional_ledgers_still_seeded(self):
        # Making Charge Received / Sales Discount come from the FK operational list,
        # not _TRADING_LEDGERS, so they must still exist.
        self.assertTrue(Ledger.objects.filter(ac_name="Making Charge Received", is_system=True).exists())
        self.assertTrue(Ledger.objects.filter(ac_name="Sales Discount", is_system=True).exists())
