import logging
from datetime import date, datetime

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


def _today():
    return date.today()


def _now_time():
    return datetime.now().time()


class Command(BaseCommand):
    help = "Enqueue CRM occasion messages that are due this minute."

    def handle(self, *args, **options):
        from mastersconfig.models import CRMSettings
        from contacts.crm_sender import find_due_recipients
        from contacts.tasks import send_occasion_message

        today = _today()
        now = _now_time()

        due_settings = CRMSettings.objects.select_related("retail").filter(is_enabled=True)
        enqueued = 0
        for settings in due_settings:
            t = settings.send_time
            if t is None or t.hour != now.hour or t.minute != now.minute:
                continue
            if settings.last_send_date == today:
                continue

            recipients = find_due_recipients(settings, today)
            for ledger_id, occasion in recipients:
                send_occasion_message.enqueue(settings.id, ledger_id, occasion)
                enqueued += 1

            settings.last_send_date = today
            settings.save(update_fields=["last_send_date"])
            logger.info("run_due_crm: retail=%s enqueued=%d", settings.retail_id, len(recipients))

        self.stdout.write(f"run_due_crm: enqueued {enqueued} message(s)")
