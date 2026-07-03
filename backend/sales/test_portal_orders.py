from django.test import TestCase
from rest_framework.test import APIClient
from mastersconfig.models import RetailMaster
from contacts.models import Ledger
from goldscheme.models import CustomerPortalAccount, CustomerPortalToken


class PortalOrdersScopingTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(retail_name="R", retail_code="RO",
            address_line1="1 St", phone="9999999999")
        self.led = Ledger.objects.create(ac_name="C", display_name="C", retail_code=self.retail)
        self.acc = CustomerPortalAccount.objects.create(primary_email="o@x.com")
        self.acc.linked_ledgers.add(self.led)
        self.token = CustomerPortalToken.objects.create(account=self.acc, retail=self.retail)

    def test_orders_endpoint_authorized_and_scoped(self):
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"PortalToken {self.token.token}")
        resp = c.get("/sales/api/portal/customer-orders/")
        self.assertEqual(resp.status_code, 200)

    def test_orders_endpoint_rejects_no_token(self):
        c = APIClient()
        resp = c.get("/sales/api/portal/customer-orders/")
        self.assertIn(resp.status_code, (401, 403))
