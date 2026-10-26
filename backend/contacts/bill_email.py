"""Auto-email a freshly saved sales bill to the customer.

Controlled by EmailSettings.auto_send_bills (per retail, superadmin-toggled).
Never raises: a mail problem must not fail or roll back a sale.
"""
import logging

from django.db import transaction
from django.utils.html import escape

logger = logging.getLogger(__name__)


def queue_bill_email(sale):
    """Queue the bill email for `sale` once its transaction commits.

    Returns True if a send was queued, False if skipped (toggle off, email
    disabled, or the customer has no email on file).
    """
    try:
        from mastersconfig.models import EmailSettings
        from contacts.tasks import send_email

        if not sale.retail_id:
            return False
        es = EmailSettings.objects.filter(retail_id=sale.retail_id).first()
        if es is None or not (es.is_enabled and es.auto_send_bills):
            return False
        to_email = (getattr(sale.ldgr, "email", "") or "").strip()
        if not to_email:
            return False

        shop = es.from_name or sale.retail.retail_name
        total = f"{sale.total_bill_value:,.2f}"
        date = sale.date1.strftime("%d-%m-%Y")
        subject = f"Your bill {sale.billno} from {shop}"
        body = (
            f"Dear {sale.ldgr.ac_name},\n\n"
            f"Thank you for shopping with {shop}.\n"
            f"Bill no: {sale.billno}\nDate: {date}\nBill amount: Rs. {total}\n\n"
            f"Regards,\n{shop}"
        )
        html = (
            f"<p>Dear {escape(sale.ldgr.ac_name)},</p>"
            f"<p>Thank you for shopping with {escape(shop)}.</p>"
            f"<table cellpadding='4'><tr><td>Bill no</td><td><b>{escape(sale.billno)}</b></td></tr>"
            f"<tr><td>Date</td><td>{date}</td></tr>"
            f"<tr><td>Bill amount</td><td><b>Rs. {total}</b></td></tr></table>"
            f"<p>Regards,<br>{escape(shop)}</p>"
        )
        retail_id = sale.retail_id
        transaction.on_commit(
            lambda: send_email.enqueue(retail_id, to_email, subject, body, "bill", html)
        )
        return True
    except Exception:
        logger.warning("could not queue bill email for sale %s", getattr(sale, "pk", None),
                       exc_info=True)
        return False
