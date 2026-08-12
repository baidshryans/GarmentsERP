"""
Campaign materialisation, throttling and consent.

The consent tests are the important ones. Marketing here is opt-out rather than
opt-in, which is only defensible if opting out actually stops messages — at
materialise time AND at send time, because a STOP can arrive while a campaign
is still draining.
"""

from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from customer_intel.models import (
    Campaign,
    CampaignRecipient,
    CustomerSocialProfile,
    EngagementEvent,
    Segment,
)
from customer_intel.services.campaigns import (
    claim_batch,
    drip,
    materialise,
    render_message,
    send_one,
)
from customer_intel.services.snapshot import SnapshotBuilder
from customer_intel.tests.factories import make_customer, make_retail, make_sale

IMMEDIATE = {"default": {"BACKEND": "django_tasks.backends.immediate.ImmediateBackend"}}
SENT_OK = (True, "", "wamid.OK")


def make_crm_settings(retail):
    from mastersconfig.models import CRMSettings

    return CRMSettings.objects.create(
        retail=retail, is_enabled=True, provider="webhook",
        webhook_url="https://example.invalid/send",
    )


class CampaignTestBase(TestCase):
    def setUp(self):
        self.retail = make_retail()
        make_crm_settings(self.retail)
        self.today = date(2026, 6, 1)

    def build(self, customers, definition=None, **campaign_kwargs):
        for ledger in customers:
            make_sale(self.retail, ledger, date(2026, 5, 1), mrp=100000,
                      billno=f"C{ledger.id}")
        SnapshotBuilder(self.retail.id, today=self.today).run()

        segment = Segment.objects.create(
            retail=self.retail, name=f"seg-{len(customers)}-{id(self)}",
            definition=definition or {"match": "all", "rules": []},
        )
        return Campaign.objects.create(
            retail=self.retail, name="Diwali preview", segment=segment,
            message_body="Hello {{customer_name}}, new arrivals are in.",
            **campaign_kwargs,
        )


class MaterialiseTests(CampaignTestBase):
    def test_creates_one_recipient_per_member(self):
        customers = [make_customer(self.retail, f"C{i}", mobile=f"90000000{i:02d}")
                     for i in range(3)]
        campaign = self.build(customers)

        counts = materialise(campaign)

        self.assertEqual(counts["total"], 3)
        self.assertEqual(campaign.recipients.filter(status="pending").count(), 3)

    def test_opted_out_customers_are_never_queued(self):
        keep = make_customer(self.retail, "Contactable", mobile="9000000001")
        gone = make_customer(self.retail, "Opted Out", mobile="9000000002")
        CustomerSocialProfile.objects.create(
            ledger=gone, opt_out_at=timezone.now(), whatsapp_opt_in=False,
        )
        campaign = self.build([keep, gone])

        materialise(campaign)

        self.assertEqual(
            campaign.recipients.get(ledger=gone).status, "opted_out",
        )
        self.assertEqual(campaign.recipients.get(ledger=keep).status, "pending")

    def test_customers_without_a_mobile_are_skipped(self):
        with_phone = make_customer(self.retail, "Has Phone", mobile="9000000001")
        without = make_customer(self.retail, "No Phone", mobile="")
        campaign = self.build([with_phone, without])

        materialise(campaign)

        self.assertEqual(campaign.recipients.get(ledger=without).status, "skipped")

    def test_is_idempotent_so_a_double_click_cannot_double_send(self):
        customers = [make_customer(self.retail, f"C{i}", mobile=f"90000000{i:02d}")
                     for i in range(3)]
        campaign = self.build(customers)

        materialise(campaign)
        second = materialise(campaign)

        self.assertTrue(second.get("already_materialised"))
        self.assertEqual(CampaignRecipient.objects.filter(campaign=campaign).count(), 3)

    def test_message_placeholders_are_rendered_per_customer(self):
        ledger = make_customer(self.retail, "Asha Patel", mobile="9000000001")
        campaign = self.build([ledger])

        materialise(campaign)

        recipient = campaign.recipients.get(ledger=ledger)
        self.assertIn("Asha Patel", recipient.rendered_message)
        self.assertNotIn("{{", recipient.rendered_message)


class RenderTests(TestCase):
    def test_unknown_placeholders_are_left_alone(self):
        retail = make_retail()
        ledger = make_customer(retail, "Meera", mobile="9000000001")

        out = render_message("Hi {{customer_name}} — {{unknown}}", ledger, retail)

        self.assertIn("Meera", out)
        self.assertIn("{{unknown}}", out)


class ThrottleTests(CampaignTestBase):
    def test_claim_takes_exactly_the_throttle_size(self):
        customers = [make_customer(self.retail, f"C{i}", mobile=f"9000000{i:03d}")
                     for i in range(10)]
        campaign = self.build(customers, throttle_per_minute=4)
        materialise(campaign)

        first = claim_batch(campaign, campaign.throttle_per_minute)
        second = claim_batch(campaign, campaign.throttle_per_minute)

        self.assertEqual(len(first), 4)
        self.assertEqual(len(second), 4)
        self.assertEqual(set(first) & set(second), set(),
                         msg="the same recipient must not be claimed twice")
        self.assertEqual(campaign.recipients.filter(status="pending").count(), 2)

    def test_claiming_marks_rows_queued(self):
        customers = [make_customer(self.retail, f"C{i}", mobile=f"9000000{i:03d}")
                     for i in range(3)]
        campaign = self.build(customers)
        materialise(campaign)

        claim_batch(campaign, 3)

        self.assertEqual(campaign.recipients.filter(status="queued").count(), 3)


@override_settings(TASKS=IMMEDIATE)
class DripTests(CampaignTestBase):
    def test_drip_does_not_resend_an_already_claimed_recipient(self):
        customers = [make_customer(self.retail, f"C{i}", mobile=f"9000000{i:03d}")
                     for i in range(5)]
        campaign = self.build(customers, throttle_per_minute=5, status="running")
        materialise(campaign)

        with patch("contacts.whatsapp_sender.send_whatsapp", return_value=SENT_OK):
            first = drip(campaign.id)
            second = drip(campaign.id)

        self.assertEqual(first, 5)
        self.assertEqual(second, 0, "second pass had nothing left to claim")

    def test_campaign_completes_when_the_queue_drains(self):
        customers = [make_customer(self.retail, "Solo", mobile="9000000001")]
        campaign = self.build(customers, throttle_per_minute=5, status="running")
        materialise(campaign)

        with patch("contacts.whatsapp_sender.send_whatsapp", return_value=SENT_OK):
            drip(campaign.id)
            drip(campaign.id)

        campaign.refresh_from_db()
        self.assertEqual(campaign.status, "completed")
        self.assertIsNotNone(campaign.finished_at)


class SendTests(CampaignTestBase):
    def _one_claimed_recipient(self, ledger):
        campaign = self.build([ledger], status="running")
        materialise(campaign)
        ids = claim_batch(campaign, 1)
        return campaign, ids[0]

    def test_successful_send_records_the_provider_message_id(self):
        ledger = make_customer(self.retail, "Asha", mobile="9000000001")
        campaign, recipient_id = self._one_claimed_recipient(ledger)

        with patch("contacts.whatsapp_sender.send_whatsapp", return_value=SENT_OK):
            send_one(recipient_id)

        recipient = CampaignRecipient.objects.get(id=recipient_id)
        self.assertEqual(recipient.status, "sent")
        self.assertEqual(recipient.provider_msg_id, "wamid.OK")
        campaign.refresh_from_db()
        self.assertEqual(campaign.sent_count, 1)

    def test_send_writes_the_timeline_event(self):
        ledger = make_customer(self.retail, "Asha", mobile="9000000001")
        campaign, recipient_id = self._one_claimed_recipient(ledger)

        with patch("contacts.whatsapp_sender.send_whatsapp", return_value=SENT_OK):
            send_one(recipient_id)

        event = EngagementEvent.objects.get(ledger=ledger, event_type="campaign")
        self.assertEqual(event.campaign_id, campaign.id)
        self.assertEqual(event.direction, "out")

    def test_opting_out_mid_campaign_stops_the_send(self):
        """
        The case that makes opt-out marketing defensible: a STOP that arrives
        after materialise but before this recipient's turn.
        """
        ledger = make_customer(self.retail, "Changed Mind", mobile="9000000001")
        campaign, recipient_id = self._one_claimed_recipient(ledger)

        CustomerSocialProfile.objects.create(
            ledger=ledger, opt_out_at=timezone.now(), whatsapp_opt_in=False,
        )

        with patch("contacts.whatsapp_sender.send_whatsapp") as sender:
            send_one(recipient_id)

        sender.assert_not_called()
        self.assertEqual(
            CampaignRecipient.objects.get(id=recipient_id).status, "opted_out",
        )

    def test_failed_send_is_recorded_not_silently_dropped(self):
        ledger = make_customer(self.retail, "Asha", mobile="9000000001")
        campaign, recipient_id = self._one_claimed_recipient(ledger)

        with patch("contacts.whatsapp_sender.send_whatsapp",
                   return_value=(False, "Meta API 400: bad template", "")):
            send_one(recipient_id)

        recipient = CampaignRecipient.objects.get(id=recipient_id)
        self.assertEqual(recipient.status, "failed")
        self.assertIn("bad template", recipient.error_message)
        campaign.refresh_from_db()
        self.assertEqual(campaign.failed_count, 1)
