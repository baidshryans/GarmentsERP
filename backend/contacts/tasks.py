import logging

from django_tasks import task

from contacts.whatsapp_sender import send_whatsapp

logger = logging.getLogger(__name__)

# Substrings send_whatsapp returns for transient failures (see its except clauses:
# "Request timed out", "Connection error: ...").
TRANSIENT_MARKERS = ("timed out", "Connection error")


class TransientSendError(Exception):
    """Raised on a transient WhatsApp failure.

    django-tasks 0.12's @task has no built-in max-attempts option, so raising
    this marks the task result FAILED (visible in the results table / admin) for
    operational retry, rather than triggering an automatic bounded retry.
    Permanent failures are logged with status='failed' and do NOT raise.
    """


@task()
def send_occasion_message(crm_settings_id, ledger_id, occasion):
    """Send one occasion message to one customer and log the outcome.

    Raises TransientSendError on transient gateway failures so the worker can
    retry; permanent failures are logged (status='failed') without raising.
    """
    from contacts.models import Ledger
    from contacts.crm_utils import get_mobile, build_message
    from mastersconfig.models import CRMSettings, CRMSendLog

    crm_settings = CRMSettings.objects.select_related("retail").get(id=crm_settings_id)
    ldgr = Ledger.objects.get(id=ledger_id)
    retail = crm_settings.retail

    mobile = get_mobile(ldgr)
    if not mobile:
        CRMSendLog.objects.create(
            retail=retail, ledger_id=ldgr.id, customer_name=ldgr.ac_name,
            mobile="", occasion=occasion, status="skipped",
            error_message="No mobile number on file",
        )
        return

    message = build_message(ldgr.ac_name, occasion, retail.retail_name)
    success, error = send_whatsapp(mobile, message, ldgr.ac_name, occasion, crm_settings)

    CRMSendLog.objects.create(
        retail=retail, ledger_id=ldgr.id, customer_name=ldgr.ac_name,
        mobile=mobile, occasion=occasion,
        status="success" if success else "failed", error_message=error or "",
    )

    if not success and any(marker in (error or "") for marker in TRANSIENT_MARKERS):
        raise TransientSendError(error)
