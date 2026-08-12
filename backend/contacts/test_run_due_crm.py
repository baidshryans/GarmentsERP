from datetime import date, time
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.management import call_command

from contacts.test_crm_recipients import make_retail, make_customer

IMMEDIATE = {"default": {"BACKEND": "django_tasks.backends.immediate.ImmediateBackend"}}

CMD = "contacts.management.commands.run_due_crm"


@override_settings(TASKS=IMMEDIATE)
class RunDueCrmTests(TestCase):
    def _settings(self, retail, send_time=time(9, 0), last_send_date=None):
        from mastersconfig.models import CRMSettings
        return CRMSettings.objects.create(
            retail=retail, is_enabled=True, provider="webhook",
            send_time=send_time, last_send_date=last_send_date,
        )

    def test_enqueues_due_recipient_and_stamps_date(self):
        retail = make_retail()
        settings = self._settings(retail)
        make_customer(retail, "Asha", dob=date(1990, 7, 2))
        today = date(2026, 7, 2)

        with patch("contacts.tasks.send_whatsapp", return_value=(True, "", "wamid.TEST")) as m, \
             patch(CMD + "._today", return_value=today), \
             patch(CMD + "._now_time", return_value=time(9, 0)):
            call_command("run_due_crm")

        m.assert_called_once()
        settings.refresh_from_db()
        self.assertEqual(settings.last_send_date, today)

    def test_idempotent_when_already_sent_today(self):
        today = date(2026, 7, 2)
        retail = make_retail()
        self._settings(retail, last_send_date=today)
        make_customer(retail, "Asha", dob=date(1990, 7, 2))

        with patch("contacts.tasks.send_whatsapp", return_value=(True, "", "wamid.TEST")) as m, \
             patch(CMD + "._today", return_value=today), \
             patch(CMD + "._now_time", return_value=time(9, 0)):
            call_command("run_due_crm")

        m.assert_not_called()

    def test_skips_when_time_not_matched(self):
        today = date(2026, 7, 2)
        retail = make_retail()
        self._settings(retail, send_time=time(9, 0))
        make_customer(retail, "Asha", dob=date(1990, 7, 2))

        with patch("contacts.tasks.send_whatsapp", return_value=(True, "", "wamid.TEST")) as m, \
             patch(CMD + "._today", return_value=today), \
             patch(CMD + "._now_time", return_value=time(10, 30)):
            call_command("run_due_crm")

        m.assert_not_called()
