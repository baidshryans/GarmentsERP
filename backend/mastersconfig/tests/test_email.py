from django.test import TestCase
from mastersconfig.models import RetailMaster, EmailSettings, EmailSendLog


class EmailSettingsModelTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(
            retail_name="Test",
            retail_code="T1",
            address_line1="1 Test St",
            phone="9999999999",
            bill_series="TST",
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
            address_line1="1 St", phone="9999999999", bill_series="R1S")
        log = EmailSendLog.objects.create(
            retail=retail, to_email="a@b.com", subject="Hi",
            purpose="otp", status="sent",
        )
        self.assertEqual(log.status, "sent")
        self.assertEqual(EmailSendLog.objects.filter(retail=retail).count(), 1)
