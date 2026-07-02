from datetime import date
from unittest.mock import patch
from django.test import TestCase, override_settings

from contacts.test_crm_recipients import make_retail, make_customer

IMMEDIATE = {"default": {"BACKEND": "django_tasks.backends.immediate.ImmediateBackend"}}


def make_settings(retail):
    from mastersconfig.models import CRMSettings
    return CRMSettings.objects.create(
        retail=retail, is_enabled=True, provider="webhook",
    )


@override_settings(TASKS=IMMEDIATE)
class SendOccasionMessageTests(TestCase):
    def test_success_writes_success_log(self):
        from contacts.tasks import send_occasion_message
        from mastersconfig.models import CRMSendLog

        retail = make_retail()
        settings = make_settings(retail)
        led = make_customer(retail, "Asha", dob=date(1990, 7, 2))

        with patch("contacts.tasks.send_whatsapp", return_value=(True, "")) as m:
            send_occasion_message.enqueue(settings.id, led.id, "birthday")

        m.assert_called_once()
        log = CRMSendLog.objects.get(ledger_id=led.id)
        self.assertEqual(log.status, "success")

    def test_no_mobile_writes_skipped_log(self):
        from contacts.tasks import send_occasion_message
        from mastersconfig.models import CRMSendLog

        retail = make_retail()
        settings = make_settings(retail)
        led = make_customer(retail, "NoPhone", dob=date(1990, 7, 2), mobile="")

        with patch("contacts.tasks.send_whatsapp") as m:
            send_occasion_message.enqueue(settings.id, led.id, "birthday")

        m.assert_not_called()
        log = CRMSendLog.objects.get(ledger_id=led.id)
        self.assertEqual(log.status, "skipped")

    def test_transient_failure_marks_result_failed(self):
        # A transient failure raises TransientSendError inside the task; the
        # backend captures it and marks the result FAILED (worker will retry).
        from contacts.tasks import send_occasion_message
        from django_tasks import TaskResultStatus

        retail = make_retail()
        settings = make_settings(retail)
        led = make_customer(retail, "Asha", dob=date(1990, 7, 2))

        with patch("contacts.tasks.send_whatsapp", return_value=(False, "Request timed out")):
            result = send_occasion_message.enqueue(settings.id, led.id, "birthday")

        self.assertEqual(result.status, TaskResultStatus.FAILED)

    def test_permanent_failure_succeeds_and_logs_failed(self):
        # A permanent failure does NOT raise: the task completes (SUCCESSFUL)
        # and records a 'failed' send log — no retry.
        from contacts.tasks import send_occasion_message
        from mastersconfig.models import CRMSendLog
        from django_tasks import TaskResultStatus

        retail = make_retail()
        settings = make_settings(retail)
        led = make_customer(retail, "Asha", dob=date(1990, 7, 2))

        with patch("contacts.tasks.send_whatsapp", return_value=(False, "Unknown provider: x")):
            result = send_occasion_message.enqueue(settings.id, led.id, "birthday")

        self.assertEqual(result.status, TaskResultStatus.SUCCESSFUL)
        self.assertEqual(CRMSendLog.objects.get(ledger_id=led.id).status, "failed")
