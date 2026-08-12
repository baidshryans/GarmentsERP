"""
Inbound WhatsApp: customer replies and delivery receipts.

Two jobs:
  * `messages[]` — a customer wrote back. Match the sender to a Ledger, record
    it on the timeline, and honour STOP/UNSUBSCRIBE immediately.
  * `statuses[]` — a delivery receipt. Advance the matching CampaignRecipient
    and EngagementEvent by provider message id.

Idempotency matters more here than anywhere else in the app: Meta redelivers on
any non-200 and sometimes redelivers anyway, so every write is guarded by an
existence check on `provider_msg_id`.
"""

import logging

from django.utils import timezone

from contacts.crm_utils import clean_mobile, dial_code_for_retail
from contacts.models import Ledger
from customer_intel.models import (
    CampaignRecipient,
    CustomerSocialProfile,
    EngagementEvent,
    InboundWebhookLog,
)

logger = logging.getLogger(__name__)

# A reply containing one of these, and little else, is a withdrawal of consent.
# Kept deliberately tight: "please stop sending me the 10am ones" is a
# conversation for a human, not an automatic opt-out.
STOP_WORDS = {"stop", "unsubscribe", "opt out", "optout", "remove me", "band karo"}

STATUS_RANK = {"sent": 0, "delivered": 1, "read": 2, "failed": 3}


def is_stop_message(text):
    normalised = (text or "").strip().lower().strip(".!?")
    if not normalised or len(normalised) > 24:
        return False
    return normalised in STOP_WORDS


def find_ledger(retail, wa_number):
    """
    Resolve a WhatsApp sender to a customer.

    Returns (ledger, candidate_ids). When more than one customer shares the
    number the event is left unattached and the candidates are recorded —
    guessing would put one customer's message on another's file.
    """
    digits = "".join(c for c in str(wa_number or "") if c.isdigit())
    if not digits:
        return None, []

    dial = str(dial_code_for_retail(retail) or "")
    local = digits[len(dial):] if dial and digits.startswith(dial) else digits
    local = clean_mobile(local) or local
    if not local:
        return None, []

    from django.db.models import Q

    matches = list(
        Ledger.objects.filter(
            Q(mobile1=local) | Q(mobile2=local) | Q(mobile3=local) | Q(phone1=local),
            roles__role="CO",
        ).distinct()[:5]
    )
    if len(matches) == 1:
        return matches[0], [matches[0].id]
    return None, [m.id for m in matches]


def _handle_message(retail, message, provider):
    msg_id = message.get("id") or ""
    if msg_id and EngagementEvent.objects.filter(
        provider_msg_id=msg_id, direction="in",
    ).exists():
        return "duplicate"

    text = ((message.get("text") or {}).get("body")
            or (message.get("button") or {}).get("text") or "")
    ledger, candidates = find_ledger(retail, message.get("from"))

    EngagementEvent.objects.create(
        retail=retail,
        ledger=ledger,
        channel="whatsapp",
        direction="in",
        event_type="inbound_reply",
        body=text,
        status="received",
        to_address=str(message.get("from") or "")[:120],
        provider=provider,
        provider_msg_id=msg_id,
        occurred_at=timezone.now(),
        metadata={
            "candidates": candidates if ledger is None else [],
            "message_type": message.get("type", ""),
        },
    )

    # A reply inside a campaign window marks that recipient as having replied —
    # the strongest engagement signal the system gets.
    if ledger is not None:
        CampaignRecipient.objects.filter(
            ledger=ledger, status__in=["sent", "delivered", "read"],
        ).order_by("-sent_at").update(status="replied")

    if ledger is not None and is_stop_message(text):
        profile, _ = CustomerSocialProfile.objects.get_or_create(ledger=ledger)
        profile.opt_out_at = timezone.now()
        profile.opt_out_reason = f"Replied '{text.strip()[:60]}' on WhatsApp"
        profile.whatsapp_opt_in = False
        profile.email_opt_in = False
        profile.save()

        EngagementEvent.objects.create(
            retail=retail, ledger=ledger, channel="note", direction="sys",
            event_type="opt_out", subject="Opted out of marketing",
            body=profile.opt_out_reason, status="sent",
            occurred_at=timezone.now(),
        )
        return "opted_out"

    return "reply"


def _handle_status(retail, status_payload):
    """Advance delivery state, never backwards (receipts can arrive out of order)."""
    msg_id = status_payload.get("id") or ""
    new_status = (status_payload.get("status") or "").lower()
    if not msg_id or new_status not in STATUS_RANK:
        return "ignored"

    recipient = CampaignRecipient.objects.filter(provider_msg_id=msg_id).first()
    if recipient and recipient.status != "replied":
        if STATUS_RANK.get(new_status, -1) > STATUS_RANK.get(recipient.status, -1):
            recipient.status = new_status
            recipient.save(update_fields=["status"])

    event = EngagementEvent.objects.filter(
        provider_msg_id=msg_id, direction="out",
    ).first()
    if event and STATUS_RANK.get(new_status, -1) > STATUS_RANK.get(event.status, -1):
        event.status = new_status
        event.save(update_fields=["status"])
    return new_status


def process_payload(retail, payload, provider="meta"):
    """Walk a Meta Cloud API webhook body. Returns a counts dict."""
    counts = {"messages": 0, "statuses": 0, "duplicates": 0, "opt_outs": 0}

    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}

            for message in value.get("messages", []) or []:
                outcome = _handle_message(retail, message, provider)
                if outcome == "duplicate":
                    counts["duplicates"] += 1
                else:
                    counts["messages"] += 1
                    if outcome == "opted_out":
                        counts["opt_outs"] += 1

            for status_payload in value.get("statuses", []) or []:
                _handle_status(retail, status_payload)
                counts["statuses"] += 1

    return counts


def process_log(log_id):
    """Process one stored webhook payload and mark it done."""
    log = InboundWebhookLog.objects.select_related("retail").get(id=log_id)
    if log.processed:
        return {"skipped": "already processed"}

    try:
        counts = process_payload(log.retail, log.payload, log.provider or "meta")
        log.processed = True
        log.save(update_fields=["processed"])
        return counts
    except Exception as exc:
        log.error_message = str(exc)[:500]
        log.save(update_fields=["error_message"])
        logger.error("inbound webhook %s failed to parse", log_id, exc_info=True)
        raise
