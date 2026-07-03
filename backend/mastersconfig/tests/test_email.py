from unittest.mock import patch
from django.test import TestCase
from mastersconfig.models import RetailMaster, EmailSettings, EmailSendLog
from contacts.tasks import send_email


class EmailSettingsModelTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(
            retail_name="Test",
            retail_code="T1",
            address_line1="1 Test St",
            phone="9999999999",
        )

    def test_gmail_preset_fills_host_port_on_save(self):
        es = EmailSettings.objects.create(retail=self.retail, provider="gmail")
        es.refresh_from_db()
        self.assertEqual(es.host, "smtp.gmail.com")
        self.assertEqual(es.port, 587)
        self.assertTrue(es.use_tls)

    def test_auto_send_bills_defaults_false(self):
        es = EmailSettings.objects.create(retail=self.retail, provider="custom_smtp")
        self.assertFalse(es.auto_send_bills)


class EmailSendLogModelTest(TestCase):
    def test_create_log_row(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="R1",
            address_line1="1 St", phone="9999999999")
        log = EmailSendLog.objects.create(
            retail=retail, to_email="a@b.com", subject="Hi",
            purpose="otp", status="sent",
        )
        self.assertEqual(log.status, "sent")
        self.assertEqual(EmailSendLog.objects.filter(retail=retail).count(), 1)


class SendEmailTaskTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(retail_name="R", retail_code="R2",
            address_line1="1 St", phone="9999999999")

    def test_skipped_when_disabled(self):
        EmailSettings.objects.create(retail=self.retail, provider="custom_smtp", is_enabled=False)
        send_email.func(self.retail.id, "c@x.com", "S", "B", "otp")
        log = EmailSendLog.objects.get(retail=self.retail)
        self.assertEqual(log.status, "skipped")

    @patch("contacts.tasks.get_connection")
    def test_sent_logs_success(self, mock_conn):
        EmailSettings.objects.create(
            retail=self.retail, provider="gmail", is_enabled=True,
            username="u", password="p", from_email="shop@x.com", from_name="Shop",
        )
        send_email.func(self.retail.id, "c@x.com", "S", "B", "otp")
        log = EmailSendLog.objects.get(retail=self.retail)
        self.assertEqual(log.status, "sent")
        self.assertTrue(mock_conn.called)


from django.contrib.auth import get_user_model
from rest_framework.test import APIClient


class EmailSettingsApiTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(retail_name="R", retail_code="R3",
            address_line1="1 St", phone="9999999999")
        User = get_user_model()
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.super = User.objects.create_superuser("root", "r@x.com", "x")

    def _patch(self, user, es_id, payload):
        c = APIClient(); c.force_authenticate(user=user)
        return c.patch(f"/mastersconfig/api/email-settings/{es_id}/", payload, format="json")

    def test_non_superadmin_cannot_enable_auto_send_bills(self):
        es = EmailSettings.objects.create(retail=self.retail, provider="gmail")
        resp = self._patch(self.staff, es.id, {"auto_send_bills": True})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(EmailSettings.objects.get(retail=self.retail).auto_send_bills)

    def test_superadmin_can_enable_auto_send_bills(self):
        es = EmailSettings.objects.create(retail=self.retail, provider="gmail")
        resp = self._patch(self.super, es.id, {"auto_send_bills": True})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(EmailSettings.objects.get(retail=self.retail).auto_send_bills)
