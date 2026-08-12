import logging

from django.core.mail import get_connection, EmailMultiAlternatives
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
    success, error, provider_msg_id = send_whatsapp(
        mobile, message, ldgr.ac_name, occasion, crm_settings,
    )

    CRMSendLog.objects.create(
        retail=retail, ledger_id=ldgr.id, customer_name=ldgr.ac_name,
        mobile=mobile, occasion=occasion,
        status="success" if success else "failed", error_message=error or "",
    )
    # Dual-write into the Customer 360 timeline. CRMSendLog stays authoritative
    # for now; retiring it is deferred until this has run for a release.
    _log_engagement(retail, ldgr, occasion, mobile, message, success, error,
                    provider_msg_id, crm_settings.provider)

    if not success and any(marker in (error or "") for marker in TRANSIENT_MARKERS):
        raise TransientSendError(error)


def _log_engagement(retail, ldgr, occasion, mobile, message, success, error,
                    provider_msg_id, provider):
    """
    Mirror an occasion send onto the engagement timeline.

    Wrapped in try/except on purpose: the timeline is a reporting surface, and
    a failure to record history must never turn a delivered message into a
    retried one.
    """
    try:
        from django.utils import timezone

        from customer_intel.models import EngagementEvent

        EngagementEvent.objects.create(
            retail=retail,
            ledger=ldgr,
            channel="whatsapp",
            direction="out",
            event_type=f"occasion_{occasion}" if occasion else "occasion",
            subject=(occasion or "").title(),
            body=message,
            status="sent" if success else "failed",
            error_message=(error or "")[:500],
            to_address=mobile,
            provider=provider or "",
            provider_msg_id=provider_msg_id or "",
            occurred_at=timezone.now(),
        )
    except Exception:
        logger.warning("could not mirror occasion send to the timeline",
                       exc_info=True)


@task()
def send_email(retail_id, to_email, subject, body, purpose="other", html_body=None):
    """Send one email via the retail's EmailSettings and log the outcome."""
    from mastersconfig.models import EmailSettings, EmailSendLog

    es = EmailSettings.objects.select_related("retail").filter(retail_id=retail_id).first()
    if es is None or not es.is_enabled:
        EmailSendLog.objects.create(
            retail_id=retail_id, to_email=to_email, subject=subject,
            purpose=purpose, status="skipped",
            error_message="Email not configured or disabled",
        )
        return

    from_addr = f"{es.from_name} <{es.from_email}>" if es.from_name else es.from_email
    try:
        connection = get_connection(
            host=es.host, port=es.port, username=es.username,
            password=es.password, use_tls=es.use_tls,
        )
        msg = EmailMultiAlternatives(subject, body, from_addr, [to_email], connection=connection)
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send()
    except Exception as exc:
        EmailSendLog.objects.create(
            retail=es.retail, to_email=to_email, subject=subject,
            purpose=purpose, status="failed", error_message=str(exc)[:500],
        )
        raise TransientSendError(str(exc))

    EmailSendLog.objects.create(
        retail=es.retail, to_email=to_email, subject=subject,
        purpose=purpose, status="sent",
    )
