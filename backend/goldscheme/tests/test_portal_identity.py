from django.test import TestCase
from mastersconfig.models import RetailMaster
from contacts.models import Ledger
from goldscheme.models import CustomerPortalAccount
from goldscheme.models import CustomerPortalToken


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
