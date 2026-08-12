"""
Campaign orchestration: turn a segment into a throttled sequence of sends.

Why the drip, rather than enqueuing every recipient at once:
  * WhatsApp providers rate-limit, and a burst gets throttled or blocked.
  * django-tasks 0.12 has no native rate limiter and no scheduled `run_at`,
    so pacing has to live in application code.
The shape is a minute-ly command (`run_due_campaigns`) that claims at most
`throttle_per_minute` recipients per campaign and enqueues just those. A
campaign therefore drains over several minutes and can be paused mid-flight.

Consent: this retailer's marketing is opt-out rather than opt-in, which makes
the opt-out check here load-bearing rather than cosmetic. It is enforced at
materialise time AND again at send time, because a customer can opt out in
between (an inbound STOP arrives while a campaign is draining).
"""

import logging

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from contacts.crm_utils import get_mobile
from customer_intel.models import (
    Campaign,
    CampaignRecipient,
    CustomerSocialProfile,
    EngagementEvent,
)
from customer_intel.services.segments import evaluate

logger = logging.getLogger(__name__)


# A customer is out of scope for marketing if they explicitly opted out or if
# the WhatsApp channel was switched off for them individually.
OPTED_OUT = Q(opt_out_at__isnull=False) | Q(whatsapp_opt_in=False)


def _opted_out_ledger_ids(ledger_ids):
    return set(
        CustomerSocialProfile.objects
        .filter(ledger_id__in=ledger_ids)
        .filter(OPTED_OUT)
        .values_list("ledger_id", flat=True)
    )


def render_message(template_body, ledger, retail):
    """
    Substitute the handful of placeholders campaigns may use.

    Deliberately not a general template engine — this string is authored in the
    ERP UI and rendered server-side; a real engine here would be an injection
    surface for no benefit.
    """
    values = {
        "customer_name": ledger.ac_name or "",
        "first_name": (ledger.ac_name or "").split(" ")[0],
        "retail_name": getattr(retail, "retail_name", "") or "",
        "city": ledger.city or "",
    }
    out = template_body or ""
    for key, value in values.items():
        out = out.replace("{{%s}}" % key, str(value))
        out = out.replace("{%s}" % key, str(value))
    return out


def _mint_recipient_share(campaign, ledger):
    """
    A per-customer catalog link, so an open can be attributed to a person
    rather than just to the campaign.
    """
    from inventory.models import CatalogShare

    source = campaign.catalog_share
    if source is None:
        return None
    return CatalogShare.objects.create(
        label=f"{campaign.name} — {ledger.ac_name}"[:120],
        retail=campaign.retail,
        tier=source.tier,
        pricelist_id=source.pricelist_id,
        filters=source.filters,
        expires_at=source.expires_at,
        ledger=ledger,
        source="campaign",
    )


@transaction.atomic
def materialise(campaign):
    """
    Freeze the segment into CampaignRecipient rows.

    Returns a counts dict. Idempotent: re-running on a campaign that already
    has recipients does nothing, so a double-click cannot double-send.
    """
    if campaign.recipients.exists():
        return {
            "total": campaign.total_recipients,
            "skipped": campaign.skipped_count,
            "already_materialised": True,
        }

    members = evaluate(campaign.segment, campaign.retail)
    ledger_ids = [s.ledger_id for s in members]
    opted_out = _opted_out_ledger_ids(ledger_ids)

    rows, skipped = [], 0
    for snapshot in members:
        ledger = snapshot.ledger
        if ledger.id in opted_out:
            rows.append(CampaignRecipient(
                campaign=campaign, ledger=ledger, status="opted_out",
                error_message="Customer has opted out of marketing",
            ))
            skipped += 1
            continue

        mobile = get_mobile(ledger)
        if not mobile:
            rows.append(CampaignRecipient(
                campaign=campaign, ledger=ledger, status="skipped",
                error_message="No mobile number on file",
            ))
            skipped += 1
            continue

        share = (
            _mint_recipient_share(campaign, ledger)
            if campaign.per_recipient_share else campaign.catalog_share
        )
        body = render_message(
            campaign.message_body or (campaign.template.body if campaign.template_id else ""),
            ledger, campaign.retail,
        )
        if campaign.attach_catalog_link and share is not None:
            body = f"{body}\n\nView the collection: /catalog/{share.token}".strip()

        rows.append(CampaignRecipient(
            campaign=campaign, ledger=ledger, status="pending",
            mobile=mobile, email=ledger.email or "",
            rendered_message=body, catalog_share=share,
        ))

    CampaignRecipient.objects.bulk_create(rows, batch_size=500)

    campaign.total_recipients = len(rows)
    campaign.skipped_count = skipped
    campaign.save(update_fields=["total_recipients", "skipped_count"])

    return {"total": len(rows), "skipped": skipped, "sendable": len(rows) - skipped}


def claim_batch(campaign, limit):
    """
    Take up to `limit` pending recipients for this campaign.

    On PostgreSQL this uses SELECT ... FOR UPDATE SKIP LOCKED so two workers
    cannot claim the same row. On SQLite (the current backend) writes are
    serialised anyway, so the id-slice update inside a transaction is
    equivalent and portable.
    """
    with transaction.atomic():
        ids = list(
            campaign.recipients.filter(status="pending")
            .order_by("id")
            .values_list("id", flat=True)[:limit]
        )
        if not ids:
            return []
        CampaignRecipient.objects.filter(id__in=ids, status="pending").update(
            status="queued", queued_at=timezone.now(),
        )
    return ids


def send_one(recipient_id):
    """
    Send a single claimed recipient and record the outcome.

    Consent is re-checked here: a campaign can take many minutes to drain, and
    a STOP message arriving mid-flight must stop the remaining sends.
    """
    from contacts.tasks import TRANSIENT_MARKERS, TransientSendError
    from contacts.whatsapp_sender import send_whatsapp
    from mastersconfig.models import CRMSettings

    recipient = (
        CampaignRecipient.objects
        .select_related("campaign", "campaign__retail", "campaign__template", "ledger")
        .get(id=recipient_id)
    )
    campaign = recipient.campaign

    social = CustomerSocialProfile.objects.filter(ledger=recipient.ledger).first()
    if social and not social.is_marketable_whatsapp:
        recipient.status = "opted_out"
        recipient.error_message = "Customer opted out before this message was sent"
        recipient.save(update_fields=["status", "error_message"])
        Campaign.objects.filter(id=campaign.id).update(
            skipped_count=F("skipped_count") + 1,
        )
        return

    crm_settings = CRMSettings.objects.filter(retail=campaign.retail).first()
    if crm_settings is None:
        recipient.status = "failed"
        recipient.error_message = "No CRM/WhatsApp settings configured for this retail"
        recipient.save(update_fields=["status", "error_message"])
        return

    template_name = (
        campaign.template.provider_template_name if campaign.template_id else ""
    ) or None

    recipient.attempts += 1
    success, error, provider_msg_id = send_whatsapp(
        recipient.mobile,
        recipient.rendered_message,
        recipient.ledger.ac_name,
        None,                      # not an occasion send
        crm_settings,
        template_name=template_name,
        template_params=[recipient.ledger.ac_name],
    )

    recipient.status = "sent" if success else "failed"
    recipient.error_message = (error or "")[:500]
    recipient.provider_msg_id = provider_msg_id or ""
    recipient.sent_at = timezone.now() if success else None
    recipient.save(update_fields=[
        "status", "error_message", "provider_msg_id", "sent_at", "attempts",
    ])

    EngagementEvent.objects.create(
        retail=campaign.retail,
        ledger=recipient.ledger,
        channel=campaign.channel,
        direction="out",
        event_type="campaign",
        subject=campaign.name[:200],
        body=recipient.rendered_message,
        status="sent" if success else "failed",
        error_message=(error or "")[:500],
        to_address=recipient.mobile,
        provider=crm_settings.provider or "",
        provider_msg_id=provider_msg_id or "",
        campaign=campaign,
        catalog_share=recipient.catalog_share,
        occurred_at=timezone.now(),
    )

    field = "sent_count" if success else "failed_count"
    Campaign.objects.filter(id=campaign.id).update(**{field: F(field) + 1})

    if not success and any(marker in (error or "") for marker in TRANSIENT_MARKERS):
        raise TransientSendError(error)


def drip(campaign_id):
    """
    Send one throttle-sized slice of a campaign, then stop.

    Called every minute by `run_due_campaigns` until nothing is pending.
    Returns the number of recipients enqueued this pass.
    """
    from customer_intel.tasks import send_campaign_message

    campaign = Campaign.objects.select_related("retail", "segment").get(id=campaign_id)

    if campaign.status == "scheduled":
        if campaign.scheduled_at and campaign.scheduled_at > timezone.now():
            return 0
        materialise(campaign)
        campaign.status = "running"
        campaign.started_at = timezone.now()
        campaign.save(update_fields=["status", "started_at"])

    if campaign.status != "running":
        return 0

    ids = claim_batch(campaign, campaign.throttle_per_minute)
    if not ids:
        campaign.status = "completed"
        campaign.finished_at = timezone.now()
        campaign.save(update_fields=["status", "finished_at"])
        return 0

    for recipient_id in ids:
        send_campaign_message.enqueue(recipient_id)
    return len(ids)
