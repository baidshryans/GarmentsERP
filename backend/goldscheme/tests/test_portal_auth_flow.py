from django.test import TestCase
from mastersconfig.models import RetailMaster
from goldscheme.models import CustomerPortalAccount, CustomerPortalOTP


class OtpModelTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="o@x.com")

    def test_code_is_hashed_and_verifies(self):
        otp = CustomerPortalOTP.objects.create(account=self.acc)
        otp.set_code("123456")
        otp.save()
        self.assertNotEqual(otp.code_hash, "123456")
        self.assertTrue(otp.check_code("123456"))
        self.assertFalse(otp.check_code("000000"))
