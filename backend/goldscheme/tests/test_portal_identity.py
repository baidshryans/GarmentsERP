from django.test import TestCase
from django.core.management import call_command
from mastersconfig.models import RetailMaster
from contacts.models import Ledger
from goldscheme.models import CustomerPortalAccount
from goldscheme.models import CustomerPortalToken
from goldscheme.models import CustomerPortalCredential


class PortalAccountTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(retail_name="R", retail_code="R1",
            address_line1="1 St", phone="9999999999", bill_series="B1S")
        self.l1 = Ledger.objects.create(ac_name="Cust A", display_name="Cust A",
            retail_code=self.retail)
        self.l2 = Ledger.objects.create(ac_name="Cust A2", display_name="Cust A2",
            retail_code=self.retail)

    def test_account_links_explicit_ledgers(self):
        acc = CustomerPortalAccount.objects.create(primary_email="a@x.com")
        acc.linked_ledgers.add(self.l1, self.l2)
        self.assertEqual(acc.linked_ledgers.count(), 2)

    def test_password_hashing_roundtrip(self):
        acc = CustomerPortalAccount(primary_email="a@x.com")
        acc.set_password("secret123")
        acc.save()
        self.assertTrue(acc.check_password("secret123"))
        self.assertFalse(acc.check_password("wrong"))


class PortalTokenAccountTest(TestCase):
    def test_token_references_account(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RT",
            address_line1="1 St", phone="9999999999", bill_series="RTS")
        acc = CustomerPortalAccount.objects.create(primary_email="t@x.com")
        tok = CustomerPortalToken.objects.create(account=acc, retail=retail)
        self.assertEqual(tok.account_id, acc.id)
        self.assertIsNotNone(tok.expires_at)  # auto-set in save()


class SeedPortalAccountsTest(TestCase):
    def test_creates_account_and_links_ledgers_by_mobile(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RS",
            address_line1="1 St", phone="9999999999", bill_series="RSS")
        led = Ledger.objects.create(ac_name="C", display_name="C", retail_code=retail,
            mobile1="9998887777", email="c@x.com")
        CustomerPortalCredential.objects.create(ledger=led, password_hash="x", is_active=True)
        call_command("seed_portal_accounts", "--apply")
        acc = CustomerPortalAccount.objects.get(primary_email="c@x.com")
        self.assertIn(led, acc.linked_ledgers.all())


from goldscheme.portal_auth import portal_ledgers

class PortalLedgersHelperTest(TestCase):
    def test_returns_account_linked_ledgers(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RL",
            address_line1="1 St", phone="9999999999", bill_series="RLS")
        acc = CustomerPortalAccount.objects.create(primary_email="p@x.com")
        led = Ledger.objects.create(ac_name="C", display_name="C", retail_code=retail)
        acc.linked_ledgers.add(led)

        class Req:
            portal_account = acc
        self.assertEqual(list(portal_ledgers(Req())), [led])
