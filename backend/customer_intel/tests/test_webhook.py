"""
Inbound WhatsApp webhook.

This is the only unauthenticated endpoint in the app and it writes to the
customer timeline. The signature tests are not a formality — without them, any
host on the internet that discovers the URL could fabricate customer replies
and, via STOP handling, opt customers out at will.
"""

import hashlib
import hmac
import json
from datetime import date

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from customer_intel.models import (
    CampaignRecipient,
    CustomerSocialProfile,
    EngagementEvent,
    InboundWebhookLog,
)
from customer_intel.services.inbound import is_stop_message, process_payload
from customer_intel.tests.factories import make_customer, make_retail

APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"
URL_KEY = "abc123urlkey"


def sign(body_bytes, secret=APP_SECRET):
    return "sha256=" + hmac.new(
        secret.encode(), body_bytes, hashlib.sha256,
    ).hexdigest()


def message_payload(from_number="919000000001", text="Do you have bangles?",
                    msg_id="wamid.IN1"):
    return {"entry": [{"changes": [{"value": {"messages": [{
        "id": msg_id, "from": from_number, "type": "text",
        "text": {"body": text},
    }]}}]}]}


def status_payload(msg_id="wamid.OUT1", state="delivered"):
    return {"entry": [{"changes": [{"value": {"statuses": [{
        "id": msg_id, "status": state,
    }]}}]}]}


@override_settings(ALLOWED_HOSTS=["*"])
class WebhookEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        from mastersconfig.models import CRMSettings

        self.retail = make_retail()
        self.settings = CRMSettings.objects.create(
            retail=self.retail, provider="meta", inbound_enabled=True,
            webhook_verify_token=VERIFY_TOKEN, app_secret=APP_SECRET,
            inbound_url_key=URL_KEY,
        )
        self.url = f"/customer-intel/api/whatsapp/webhook/{URL_KEY}/"

    def post(self, payload, signature=None):
        body = json.dumps(payload).encode()
        return self.client.post(
            self.url, data=body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=(
                signature if signature is not None else sign(body)
            ),
        )

    # ── verification handshake ────────────────────────────────────────────
    def test_verify_handshake_echoes_the_challenge(self):
        response = self.client.get(self.url, {
            "hub.mode": "subscribe",
            "hub.verify_token": VERIFY_TOKEN,
            "hub.challenge": "12345",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "12345")

    def test_verify_handshake_rejects_a_wrong_token(self):
        response = self.client.get(self.url, {
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "12345",
        })
        self.assertEqual(response.status_code, 403)

    def test_unknown_url_key_is_a_404(self):
        response = self.client.get("/customer-intel/api/whatsapp/webhook/nope/", {
            "hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN,
        })
        self.assertEqual(response.status_code, 404)

    def test_disabled_inbound_is_a_404(self):
        self.settings.inbound_enabled = False
        self.settings.save(update_fields=["inbound_enabled"])

        self.assertEqual(self.post(message_payload()).status_code, 404)

    # ── signature ─────────────────────────────────────────────────────────
    def test_bad_signature_is_rejected(self):
        response = self.post(message_payload(), signature="sha256=deadbeef")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(InboundWebhookLog.objects.count(), 0)

    def test_missing_signature_is_rejected(self):
        body = json.dumps(message_payload()).encode()
        response = self.client.post(self.url, data=body,
                                    content_type="application/json")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(InboundWebhookLog.objects.count(), 0)

    def test_unconfigured_app_secret_rejects_everything(self):
        """An unfinished setup must not accept unsigned traffic."""
        self.settings.app_secret = ""
        self.settings.save(update_fields=["app_secret"])

        body = json.dumps(message_payload()).encode()
        response = self.client.post(
            self.url, data=body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sign(body, secret=""),
        )
        self.assertEqual(response.status_code, 403)

    # ── happy path ────────────────────────────────────────────────────────
    def test_valid_signature_stores_the_payload_and_returns_200_fast(self):
        response = self.post(message_payload())

        self.assertEqual(response.status_code, 200)
        self.assertEqual(InboundWebhookLog.objects.count(), 1)

    def test_malformed_body_still_returns_200(self):
        """A bad body is not worth a Meta retry storm."""
        body = b"not json"
        response = self.client.post(
            self.url, data=body, content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sign(body),
        )
        self.assertEqual(response.status_code, 200)


class InboundProcessingTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.customer = make_customer(self.retail, "Asha", mobile="9000000001")

    def test_reply_is_attached_to_the_matching_customer(self):
        counts = process_payload(self.retail, message_payload(
            from_number="919000000001", text="Do you have bangles?",
        ))

        self.assertEqual(counts["messages"], 1)
        event = EngagementEvent.objects.get(direction="in")
        self.assertEqual(event.ledger_id, self.customer.id)
        self.assertEqual(event.body, "Do you have bangles?")

    def test_replaying_the_same_payload_creates_no_extra_events(self):
        payload = message_payload(msg_id="wamid.SAME")

        process_payload(self.retail, payload)
        second = process_payload(self.retail, payload)

        self.assertEqual(second["duplicates"], 1)
        self.assertEqual(EngagementEvent.objects.filter(direction="in").count(), 1)

    def test_unknown_number_does_not_crash_and_leaves_ledger_null(self):
        counts = process_payload(self.retail, message_payload(
            from_number="919999999999",
        ))

        self.assertEqual(counts["messages"], 1)
        event = EngagementEvent.objects.get(direction="in")
        self.assertIsNone(event.ledger_id)

    def test_ambiguous_number_is_left_unattached_with_candidates_recorded(self):
        """Attributing one customer's message to another is worse than none."""
        twin = make_customer(self.retail, "Twin", mobile="9000000001")

        process_payload(self.retail, message_payload(from_number="919000000001"))

        event = EngagementEvent.objects.get(direction="in")
        self.assertIsNone(event.ledger_id)
        self.assertCountEqual(
            event.metadata["candidates"], [self.customer.id, twin.id],
        )

    def test_stop_message_opts_the_customer_out(self):
        counts = process_payload(self.retail, message_payload(text="STOP"))

        self.assertEqual(counts["opt_outs"], 1)
        profile = CustomerSocialProfile.objects.get(ledger=self.customer)
        self.assertIsNotNone(profile.opt_out_at)
        self.assertFalse(profile.whatsapp_opt_in)

    def test_a_sentence_containing_stop_is_not_an_opt_out(self):
        """'don't stop sending, I love these' must not silence the customer."""
        process_payload(self.retail, message_payload(
            text="please don't stop sending me the new designs",
        ))

        self.assertFalse(
            CustomerSocialProfile.objects.filter(
                ledger=self.customer, opt_out_at__isnull=False,
            ).exists()
        )

    def test_stop_word_detection(self):
        self.assertTrue(is_stop_message("STOP"))
        self.assertTrue(is_stop_message("  unsubscribe "))
        self.assertTrue(is_stop_message("Stop."))
        self.assertFalse(is_stop_message("please stop sending these at 6am"))
        self.assertFalse(is_stop_message(""))


class DeliveryReceiptTests(TestCase):
    def setUp(self):
        from customer_intel.models import Campaign, Segment

        self.retail = make_retail()
        self.customer = make_customer(self.retail, "Asha", mobile="9000000001")
        segment = Segment.objects.create(
            retail=self.retail, name="all", definition={"match": "all", "rules": []},
        )
        self.campaign = Campaign.objects.create(
            retail=self.retail, name="Test", segment=segment,
        )
        self.recipient = CampaignRecipient.objects.create(
            campaign=self.campaign, ledger=self.customer, mobile="9000000001",
            status="sent", provider_msg_id="wamid.OUT1",
        )
        self.event = EngagementEvent.objects.create(
            retail=self.retail, ledger=self.customer, channel="whatsapp",
            direction="out", event_type="campaign", status="sent",
            provider_msg_id="wamid.OUT1", occurred_at=timezone.now(),
        )

    def test_delivery_receipt_advances_the_recipient(self):
        process_payload(self.retail, status_payload(state="delivered"))

        self.recipient.refresh_from_db()
        self.event.refresh_from_db()
        self.assertEqual(self.recipient.status, "delivered")
        self.assertEqual(self.event.status, "delivered")

    def test_receipts_never_move_status_backwards(self):
        """Receipts can arrive out of order; 'read' must not regress to 'sent'."""
        process_payload(self.retail, status_payload(state="read"))
        process_payload(self.retail, status_payload(state="sent"))

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, "read")

    def test_a_reply_outranks_a_later_delivery_receipt(self):
        self.recipient.status = "replied"
        self.recipient.save(update_fields=["status"])

        process_payload(self.retail, status_payload(state="delivered"))

        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, "replied")

    def test_unknown_message_id_is_ignored_quietly(self):
        counts = process_payload(self.retail, status_payload(msg_id="wamid.NOPE"))

        self.assertEqual(counts["statuses"], 1)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, "sent")
