from django.test import TestCase
from django.core.management import call_command
from accounting.models import Account
from contacts.models import Ledger


class SetupAccountGroupsSafetyTests(TestCase):
    def test_group_with_ledgers_and_no_valid_ancestor_is_not_orphaned(self):
        call_command("setup_account_groups")
        # A stray group whose parent chain has no valid ancestor.
        stray_root = Account.objects.create(code="ZZ-ROOT", name="Stray", parent=None)
        stray = Account.objects.create(code="ZZ-CHILD", name="Stray Child", parent=stray_root)
        led = Ledger.objects.create(id=900200, ac_name="Stray Ledger",
                                    display_name="Stray Ledger", ac_group=stray)

        call_command("setup_account_groups")

        led.refresh_from_db()
        # The ledger must NOT be orphaned to ac_group=None.
        self.assertIsNotNone(led.ac_group_id)
        self.assertTrue(Account.objects.filter(id=led.ac_group_id).exists())
