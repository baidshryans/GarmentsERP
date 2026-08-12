"""
Backfill the engagement timeline from the legacy send logs.

`CRMSendLog` and `EmailSendLog` keep being written by the existing CRM paths —
this is additive, not a cutover. Retiring them is deferred until the new
timeline has been in production for at least one release.

Two things worth knowing about the source data:
  * `CRMSendLog.ledger_id` is a bare IntegerField, not a foreign key, so it can
    reference a ledger that has since been deleted. Orphans are checked against
    the live id set and imported with a null ledger rather than dropped.
  * `EmailSendLog` has no ledger reference at all, only `to_email`. Matching is
    by exact email within the same retail, and any address matching more than
    one ledger is left unattached — a wrong attribution is worse than none.
"""

from django.db import migrations

# Maps the legacy log's status vocabulary onto EngagementEvent.STATUS.
STATUS_MAP = {"success": "sent", "failed": "failed", "skipped": "skipped"}


def backfill(apps, schema_editor):
    CRMSendLog = apps.get_model("mastersconfig", "CRMSendLog")
    EmailSendLog = apps.get_model("mastersconfig", "EmailSendLog")
    EngagementEvent = apps.get_model("customer_intel", "EngagementEvent")
    Ledger = apps.get_model("contacts", "Ledger")

    live_ledger_ids = set(Ledger.objects.values_list("id", flat=True))

    events = []
    for log in CRMSendLog.objects.all().iterator():
        events.append(EngagementEvent(
            retail_id=log.retail_id,
            ledger_id=log.ledger_id if log.ledger_id in live_ledger_ids else None,
            channel="whatsapp",
            direction="out",
            event_type=f"occasion_{log.occasion}" if log.occasion else "occasion",
            subject=(log.occasion or "").title(),
            status=STATUS_MAP.get(log.status, "sent"),
            error_message=(log.error_message or "")[:500],
            to_address=(log.mobile or "")[:120],
            occurred_at=log.sent_at,
            metadata={"backfilled_from": "crm_send_log", "source_id": log.id,
                      "customer_name": log.customer_name or ""},
        ))

    # Email logs only carry an address; build an email → ledger map per retail
    # and skip anything ambiguous.
    email_owner = {}
    ambiguous = set()
    for ledger_id, email, retail_id in Ledger.objects.exclude(
        email__isnull=True
    ).exclude(email="").values_list("id", "email", "retail_code_id"):
        key = (retail_id, (email or "").strip().lower())
        if key in email_owner:
            ambiguous.add(key)
        else:
            email_owner[key] = ledger_id

    for log in EmailSendLog.objects.all().iterator():
        key = (log.retail_id, (log.to_email or "").strip().lower())
        ledger_id = None if key in ambiguous else email_owner.get(key)
        events.append(EngagementEvent(
            retail_id=log.retail_id,
            ledger_id=ledger_id,
            channel="email",
            direction="out",
            event_type=log.purpose or "other",
            subject=(log.subject or "")[:200],
            status=STATUS_MAP.get(log.status, "sent"),
            error_message=(log.error_message or "")[:500],
            to_address=(log.to_email or "")[:120],
            occurred_at=log.sent_at,
            metadata={"backfilled_from": "email_send_log", "source_id": log.id},
        ))

    EngagementEvent.objects.bulk_create(events, batch_size=500)


def unbackfill(apps, schema_editor):
    """Remove only the rows this migration created, identified by metadata."""
    EngagementEvent = apps.get_model("customer_intel", "EngagementEvent")
    EngagementEvent.objects.filter(
        metadata__backfilled_from__in=["crm_send_log", "email_send_log"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("customer_intel", "0001_initial"),
        ("mastersconfig", "0007_alter_b2bpricelisttunch_unique_together_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
