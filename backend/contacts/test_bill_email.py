from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from contacts.bill_email import queue_bill_email
from mastersconfig.models import EmailSettings, RetailMaster


class QueueBillEmailTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(
            retail_name="Shop", retail_code="B1", address_line1="1 St", phone="9999999999")
        self.sale = SimpleNamespace(
            pk=1, retail_id=self.retail.id, retail=self.retail, billno="INV-1",
            date1=date(2026, 10, 26), total_bill_value=1234.5,
            ldgr=SimpleNamespace(email="cust@example.com", ac_name="Asha"))

    def _settings(self, **kw):
        defaults = dict(provider="gmail", is_enabled=True, auto_send_bills=True)
        defaults.update(kw)
        return EmailSettings.objects.create(retail=self.retail, **defaults)

    def _run(self):
        with patch("contacts.tasks.send_email") as task, \
                self.captureOnCommitCallbacks(execute=True):
            queued = queue_bill_email(self.sale)
        return queued, task.enqueue

    def test_sends_when_toggle_on(self):
        self._settings()
        queued, enq = self._run()
        self.assertTrue(queued)
        enq.assert_called_once()
        args = enq.call_args.args
        self.assertEqual(args[1], "cust@example.com")
        self.assertIn("INV-1", args[2])
        self.assertEqual(args[4], "bill")

    def test_skipped_when_toggle_off(self):
        self._settings(auto_send_bills=False)
        queued, enq = self._run()
        self.assertFalse(queued)
        enq.assert_not_called()

    def test_skipped_when_email_disabled(self):
        self._settings(is_enabled=False)
        self.assertFalse(self._run()[0])

    def test_skipped_without_settings_row(self):
        self.assertFalse(self._run()[0])

    def test_skipped_when_customer_has_no_email(self):
        self._settings()
        self.sale.ldgr.email = ""
        queued, enq = self._run()
        self.assertFalse(queued)
        enq.assert_not_called()
