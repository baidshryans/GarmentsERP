"""
Public inbound webhook for WhatsApp.

This is the only unauthenticated endpoint in the app, and it writes to the
customer timeline. The HMAC signature check is therefore not optional and not
best-effort: an unsigned or wrongly-signed request is rejected outright, before
anything is parsed or stored.

Shape of a POST:
    verify signature → store raw payload → enqueue → return 200 immediately.
Meta retries aggressively on any non-200 response and will duplicate the
timeline if parsing is done inline and happens to be slow.
"""

import hashlib
import hmac
import json
import logging

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from customer_intel.models import InboundWebhookLog
from mastersconfig.models import CRMSettings

logger = logging.getLogger(__name__)


def _verify_signature(app_secret, raw_body, header_value):
    """
    Constant-time check of Meta's X-Hub-Signature-256.

    Returns False when the secret is unset — an unconfigured retail must not
    accept unsigned traffic just because it has not finished setup.
    """
    if not app_secret or not header_value:
        return False
    if not header_value.startswith("sha256="):
        return False
    expected = hmac.new(
        app_secret.encode("utf-8"), raw_body, hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, header_value[len("sha256="):])


@method_decorator(csrf_exempt, name="dispatch")
class WhatsAppWebhookView(APIView):
    """
    GET  /customer-intel/api/whatsapp/webhook/<url_key>/  — Meta's verification handshake
    POST /customer-intel/api/whatsapp/webhook/<url_key>/  — replies and delivery receipts
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "whatsapp_webhook"

    def _settings(self, url_key):
        if not url_key:
            return None
        return CRMSettings.objects.select_related("retail").filter(
            inbound_url_key=url_key, inbound_enabled=True,
        ).first()

    def get(self, request, url_key):
        """Meta's subscribe handshake: echo hub.challenge if the token matches."""
        settings = self._settings(url_key)
        if settings is None:
            return HttpResponse("Not found", status=404)

        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token") or ""
        challenge = request.query_params.get("hub.challenge") or ""

        if mode == "subscribe" and hmac.compare_digest(
            token, settings.webhook_verify_token or "",
        ):
            return HttpResponse(challenge, content_type="text/plain")
        return HttpResponse("Verification failed", status=403)

    def post(self, request, url_key):
        settings = self._settings(url_key)
        if settings is None:
            return HttpResponse("Not found", status=404)

        raw_body = request.body
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not _verify_signature(settings.app_secret, raw_body, signature):
            logger.warning(
                "rejected unsigned inbound webhook for retail %s", settings.retail_id,
            )
            return JsonResponse({"error": "Invalid signature"}, status=403)

        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            # Still a 200: a malformed body is not something Meta should retry.
            return JsonResponse({"status": "ignored"}, status=200)

        log = InboundWebhookLog.objects.create(
            retail=settings.retail, provider=settings.provider, payload=payload,
        )
        CRMSettings.objects.filter(id=settings.id).update(
            last_inbound_at=timezone.now(),
        )

        try:
            from customer_intel.tasks import process_inbound_webhook

            process_inbound_webhook.enqueue(log.id)
        except Exception:
            # The payload is safely stored; a queueing failure must not provoke
            # a retry storm. `process_pending_webhooks` can pick it up later.
            logger.error("could not enqueue inbound webhook %s", log.id, exc_info=True)

        return JsonResponse({"status": "received"}, status=200)
