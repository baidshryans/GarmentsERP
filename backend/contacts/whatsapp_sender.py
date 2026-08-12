import requests
import logging
import json as _json

from django.conf import settings as django_settings
from contacts.crm_utils import dial_code_for_retail

logger = logging.getLogger(__name__)


def _resolve_template(occasion, settings, template_name=None):
    """
    Which provider template to send.

    An explicit `template_name` (campaigns) wins; otherwise fall back to the
    occasion-keyed templates configured for birthdays and anniversaries.
    """
    if template_name:
        return template_name
    return (
        settings.birthday_template_name if occasion == 'birthday'
        else settings.anniversary_template_name
    )


def send_whatsapp(mobile, message, customer_name, occasion, settings,
                  template_name=None, template_params=None):
    """
    Send a WhatsApp message via the configured provider.

    Args:
        template_name: explicit provider template to use. Occasion greetings
            leave this None and get the configured birthday/anniversary
            template; campaigns pass their own.
        template_params: ordered body substitutions. Defaults to
            [customer_name] when not given.

    Returns (success: bool, error_message: str, provider_msg_id: str).

    The provider message id is what later correlates delivery receipts and
    customer replies back to the send that caused them — without it, an inbound
    webhook cannot tell which campaign a reply belongs to.
    """
    provider = settings.provider
    params = list(template_params) if template_params else [customer_name]
    try:
        if provider == 'meta':
            return _send_meta(mobile, customer_name, occasion, settings,
                              template_name, params)
        elif provider == 'wati':
            return _send_wati(mobile, customer_name, occasion, settings,
                              template_name, params)
        elif provider == 'aisensy':
            return _send_aisensy(mobile, customer_name, occasion, settings,
                                 template_name, params)
        elif provider == 'webhook':
            return _send_webhook(mobile, message, customer_name, occasion,
                                 settings, template_name, params)
        else:
            return False, f"Unknown provider: {provider}", ""
    except requests.exceptions.Timeout:
        return False, "Request timed out", ""
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {e}", ""
    except Exception as e:
        logger.error("WhatsApp send error", exc_info=True)
        return False, str(e), ""


def _send_meta(mobile, customer_name, occasion, settings,
               template_name=None, params=None):
    """Meta Cloud API — requires pre-approved message templates."""
    template = _resolve_template(occasion, settings, template_name)
    if not settings.phone_number_id or not settings.api_key:
        return False, "Meta: phone_number_id and api_key are required", ""
    api_version = getattr(django_settings, 'META_GRAPH_API_VERSION', 'v20.0')
    dial = dial_code_for_retail(getattr(settings, 'retail', None))
    url = f"https://graph.facebook.com/{api_version}/{settings.phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": f"{dial}{mobile}",
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": "en"},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": str(p)}
                    for p in (params or [customer_name])
                ],
            }],
        },
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        messages = data.get('messages') or []
        if messages:
            return True, "", messages[0].get('id', "")
        return False, f"Meta unexpected response: {resp.text[:300]}", ""
    return False, f"Meta API {resp.status_code}: {resp.text[:300]}", ""


def _send_wati(mobile, customer_name, occasion, settings,
               template_name=None, params=None):
    """WATI API — uses settings.webhook_url as the WATI server base URL."""
    template = _resolve_template(occasion, settings, template_name)
    base_url = (settings.webhook_url or "").rstrip('/')
    if not base_url:
        return False, "WATI: set webhook_url to your WATI server URL (e.g. https://live-server-XXXXX.wati.io)", ""
    if not settings.api_key:
        return False, "WATI: api_key (Bearer token) is required", ""
    dial = dial_code_for_retail(getattr(settings, 'retail', None))
    url = f"{base_url}/api/v1/sendTemplateMessage?whatsappNumber={dial}{mobile}"
    headers = {"Authorization": f"Bearer {settings.api_key}", "Content-Type": "application/json"}
    payload = {
        "template_name": template,
        "broadcast_name": f"crm_{occasion or 'campaign'}_{mobile}",
        "parameters": [
            {"name": str(i + 1), "value": str(p)}
            for i, p in enumerate(params or [customer_name])
        ],
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        if data.get('result'):
            return True, "", str(data.get('id') or data.get('messageId') or "")
        return False, f"WATI error: {resp.text[:300]}", ""
    return False, f"WATI API {resp.status_code}: {resp.text[:300]}", ""


def _send_aisensy(mobile, customer_name, occasion, settings,
                  template_name=None, params=None):
    """AiSensy Campaign API."""
    template = _resolve_template(occasion, settings, template_name)
    if not settings.api_key:
        return False, "AiSensy: api_key is required", ""
    dial = dial_code_for_retail(getattr(settings, 'retail', None))
    url = getattr(django_settings, 'AISENSY_API_URL', 'https://backend.aisensy.com/campaign/t1/api/v2')
    # The historical occasion path sent a hardcoded "20" (the discount percent
    # in the greeting template); campaigns supply their own parameters.
    body_params = (
        [str(p) for p in params]
        if template_name else [customer_name, "20"]
    )
    payload = {
        "apiKey": settings.api_key,
        "campaignName": template,
        "destination": f"{dial}{mobile}",
        "userName": customer_name,
        "templateParams": body_params,
        "source": getattr(django_settings, 'AISENSY_SOURCE_ID', 'JEWEL_ERP'),
        "media": {},
        "buttons": [],
        "carouselCards": [],
        "location": {},
    }
    resp = requests.post(url, json=payload, timeout=15)
    if 200 <= resp.status_code < 300:
        msg_id = ""
        try:
            msg_id = str(resp.json().get("messageId") or "")
        except Exception:
            pass
        return True, "", msg_id
    return False, f"AiSensy API {resp.status_code}: {resp.text[:300]}", ""


def _send_webhook(mobile, message, customer_name, occasion, settings,
                  template_name=None, params=None):
    """Generic HTTP POST webhook — fully user-defined URL and headers."""
    if not settings.webhook_url:
        return False, "Webhook URL is not configured", ""
    headers = {"Content-Type": "application/json"}
    if settings.webhook_headers:
        try:
            extra = (
                _json.loads(settings.webhook_headers)
                if isinstance(settings.webhook_headers, str)
                else settings.webhook_headers
            )
            headers.update(extra)
        except Exception:
            pass
    dial = dial_code_for_retail(getattr(settings, 'retail', None))
    payload = {
        "to": f"{dial}{mobile}",
        "mobile": mobile,
        "message": message,
        "customer_name": customer_name,
        "occasion": occasion,
        "template_name": template_name or "",
        "template_params": [str(p) for p in (params or [])],
    }
    resp = requests.post(settings.webhook_url, json=payload, headers=headers, timeout=15)
    if 200 <= resp.status_code < 300:
        msg_id = ""
        try:
            msg_id = str(resp.json().get("id") or resp.json().get("message_id") or "")
        except Exception:
            pass
        return True, "", msg_id
    return False, f"Webhook {resp.status_code}: {resp.text[:300]}", ""
