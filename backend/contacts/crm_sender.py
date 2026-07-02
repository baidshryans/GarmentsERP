import logging
from datetime import date

logger = logging.getLogger(__name__)


def find_due_recipients(crm_settings, today):
    """
    Return a list of (ledger_id, occasion) tuples whose birthday/anniversary
    falls on `today` for this retail. Pure query — does no sending.

    Customers are scoped by ``retail_code`` (the FK used for retail scoping of
    Ledger throughout contacts/views.py), not a nonexistent ``retail`` field.
    """
    from contacts.models import Ledger

    customers = Ledger.objects.filter(
        retail_code=crm_settings.retail, roles__role='CO'
    ).distinct().exclude(
        dob__isnull=True, anniversary__isnull=True
    ).only('id', 'dob', 'anniversary')

    recipients = []
    for ldgr in customers:
        if ldgr.dob and ldgr.dob.month == today.month and ldgr.dob.day == today.day:
            recipients.append((ldgr.id, 'birthday'))
        if ldgr.anniversary and ldgr.anniversary.month == today.month and ldgr.anniversary.day == today.day:
            recipients.append((ldgr.id, 'anniversary'))
    return recipients


def send_occasions_for_retail(crm_settings):
    """
    Query today's birthdays/anniversaries for the given retail and send WhatsApp messages.
    Updates crm_settings.last_send_date and last_run_status.
    Called by the APScheduler job.
    """
    from contacts.models import Ledger
    from contacts.crm_utils import clean_mobile, get_mobile, build_message
    from contacts.whatsapp_sender import send_whatsapp
    from mastersconfig.models import CRMSendLog

    retail = crm_settings.retail
    retail_name = retail.retail_name
    today = date.today()

    customers = Ledger.objects.filter(
        retail=retail, roles__role='CO'
    ).distinct().exclude(
        dob__isnull=True, anniversary__isnull=True
    ).only('id', 'ac_name', 'mobile1', 'mobile2', 'mobile3', 'phone1', 'dob', 'anniversary')

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for ldgr in customers:
        occasions_today = []
        if ldgr.dob and ldgr.dob.month == today.month and ldgr.dob.day == today.day:
            occasions_today.append('birthday')
        if ldgr.anniversary and ldgr.anniversary.month == today.month and ldgr.anniversary.day == today.day:
            occasions_today.append('anniversary')

        for occasion in occasions_today:
            mobile = get_mobile(ldgr)
            if not mobile:
                CRMSendLog.objects.create(
                    retail=retail,
                    ledger_id=ldgr.id,
                    customer_name=ldgr.ac_name,
                    mobile='',
                    occasion=occasion,
                    status='skipped',
                    error_message='No mobile number on file',
                )
                skipped_count += 1
                continue

            message = build_message(ldgr.ac_name, occasion, retail_name)
            success, error = send_whatsapp(mobile, message, ldgr.ac_name, occasion, crm_settings)

            CRMSendLog.objects.create(
                retail=retail,
                ledger_id=ldgr.id,
                customer_name=ldgr.ac_name,
                mobile=mobile,
                occasion=occasion,
                status='success' if success else 'failed',
                error_message=error,
            )

            if success:
                sent_count += 1
                logger.info(f"CRM [{retail_name}]: Sent {occasion} to {ldgr.ac_name} ({mobile})")
            else:
                failed_count += 1
                logger.warning(f"CRM [{retail_name}]: Failed {occasion} for {ldgr.ac_name}: {error}")

    status_msg = f"Sent: {sent_count}, Failed: {failed_count}, Skipped (no mobile): {skipped_count}"
    crm_settings.last_send_date = today
    crm_settings.last_run_status = status_msg
    crm_settings.save(update_fields=['last_send_date', 'last_run_status'])
    logger.info(f"CRM [{retail_name}]: {status_msg}")
