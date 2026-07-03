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


from goldscheme.portal_otp import generate_otp_code, issue_otp, is_throttled


class OtpHelperTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="h@x.com")

    def test_generate_is_six_digits(self):
        code = generate_otp_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_issue_creates_hashed_otp_and_then_throttles(self):
        code = issue_otp(self.acc)
        otp = CustomerPortalOTP.objects.filter(account=self.acc).latest("created_at")
        self.assertTrue(otp.check_code(code))
        self.assertTrue(is_throttled(self.acc))  # second request inside cooldown blocked


from unittest.mock import patch
from rest_framework.test import APIClient

class RequestOtpTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="r@x.com", phone="9990001111")

    @patch("goldscheme.portal_views.send_email")
    def test_request_by_email_enqueues_email(self, mock_send):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/request-otp/", {"userid": "r@x.com"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_send.enqueue.called)

    @patch("goldscheme.portal_views.send_email")
    def test_request_by_phone_resolves_account(self, mock_send):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/request-otp/", {"userid": "9990001111"}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_unknown_userid_generic_response(self):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/request-otp/", {"userid": "nobody@x.com"}, format="json")
        self.assertEqual(resp.status_code, 200)  # generic to prevent enumeration


from goldscheme.models import CustomerPortalToken
from goldscheme.portal_otp import issue_otp

class VerifyOtpTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="v@x.com")

    def test_valid_otp_issues_token(self):
        code = issue_otp(self.acc)
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/verify-otp/",
                      {"userid": "v@x.com", "otp": code}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json())
        self.assertEqual(CustomerPortalToken.objects.filter(account=self.acc).count(), 1)

    def test_wrong_otp_does_not_consume(self):
        issue_otp(self.acc)
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/verify-otp/",
                      {"userid": "v@x.com", "otp": "000000"}, format="json")
        self.assertEqual(resp.status_code, 400)
        otp = CustomerPortalOTP.objects.get(account=self.acc)
        self.assertFalse(otp.is_verified)


class PasswordLoginTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="pw@x.com")
        self.acc.set_password("secret123"); self.acc.save()

    def test_correct_password_issues_token(self):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/login/",
                      {"userid": "pw@x.com", "password": "secret123"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json())

    def test_wrong_password_401(self):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/login/",
                      {"userid": "pw@x.com", "password": "nope"}, format="json")
        self.assertEqual(resp.status_code, 401)


class SetPasswordTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="sp@x.com")

    def test_first_time_set_via_otp(self):
        code = issue_otp(self.acc)
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/set-password/",
                      {"userid": "sp@x.com", "otp": code, "new_password": "brandnew1"},
                      format="json")
        self.assertEqual(resp.status_code, 200)
        self.acc.refresh_from_db()
        self.assertTrue(self.acc.check_password("brandnew1"))
        self.assertFalse(CustomerPortalOTP.objects.filter(account=self.acc).exists())  # single use

    def test_change_while_logged_in_requires_old_password(self):
        self.acc.set_password("orig123"); self.acc.save()
        token = CustomerPortalToken.objects.create(account=self.acc)
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"PortalToken {token.token}")
        resp = c.post("/goldscheme/api/portal/change-password/",
                      {"old_password": "wrong", "new_password": "changed99"}, format="json")
        self.assertEqual(resp.status_code, 400)


from datetime import date, timedelta
from contacts.models import Ledger, LedgerRole
from goldscheme.models import SchemeMaster, SchemeEnrollment


class C2LeakTest(TestCase):
    """Two customers share a phone; only one is linked to the portal account.
    The other's data must never surface (C2 authorization leak regression)."""

    def test_shared_phone_does_not_leak_other_account_data(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RC",
            address_line1="1 St", phone="9999999999", bill_series="RCS")
        led_a = Ledger.objects.create(ac_name="A", display_name="A",
            retail_code=retail, mobile1="9998887777")
        led_b = Ledger.objects.create(ac_name="B", display_name="B",
            retail_code=retail, mobile1="9998887777")
        # Both hold a CO role so mobile-expansion (old logic) would match both.
        LedgerRole.objects.create(ledger=led_a, role='CO')
        LedgerRole.objects.create(ledger=led_b, role='CO')

        # led_b has an enrollment whose scheme name is "B" — the only source of "B".
        scheme = SchemeMaster.objects.create(name="B", scheme_code="SCB",
            scheme_type="INSTALLMENT", gold_price_mode="ACCUMULATED", retail=retail)
        SchemeEnrollment.objects.create(
            enrollment_no="ENB1", scheme=scheme, customer=led_b, retail=retail,
            start_date=date.today(), maturity_date=date.today() + timedelta(days=330),
            installment_amount=1000, status='ACTIVE')

        acc_a = CustomerPortalAccount.objects.create(primary_email="a@x.com")
        acc_a.linked_ledgers.add(led_a)  # A only
        token = CustomerPortalToken.objects.create(
            account=acc_a, retail=retail, mobile="9998887777")
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"PortalToken {token.token}")
        resp = c.get("/goldscheme/api/portal/dashboard/")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        # Nothing belonging to led_b (ac_name / scheme name "B") may appear.
        self.assertNotIn("B", str(body))
