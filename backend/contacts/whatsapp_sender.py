import requests
import logging
import json as _json

from django.conf import settings as django_settings
from contacts.crm_utils import dial_code_for_retail

logger = logging.getLogger(__name__)


def send_whatsapp(mobile, message, customer_name, occasion, settings):
    """
    Send a WhatsApp message via the configured provider.
    Returns (success: bool, error_message: str).
    """
    provider = settings.provider
    try:
        if provider == 'meta':
            return _send_meta(mobile, customer_name, occasion, settings)
        elif provider == 'wati':
            return _send_wati(mobile, customer_name, occasion, settings)
        elif provider == 'aisensy':
            return _send_aisensy(mobile, customer_name, occasion, settings)
        elif provider == 'webhook':
            return _send_webhook(mobile, message, customer_name, occasion, settings)
        else:
            return False, f"Unknown provider: {provider}"
    except requests.exceptions.Timeout:
        return False, "Request timed out"
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {e}"
    except Exception as e:
        logger.error("WhatsApp send error", exc_info=True)
        return False, str(e)


def _send_meta(mobile, customer_name, occasion, settings):
    """Meta Cloud API — requires pre-approved message templates."""
    template_name = (
        settings.birthday_template_name if occasion == 'birthday'
        else settings.anniversary_template_name
    )
    if not settings.phone_number_id or not settings.api_key:
        return False, "Meta: phone_number_id and api_key are required"
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
            "name": template_name,
            "language": {"code": "en"},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": customer_name}],
            }],
        },
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        if data.get('messages'):
            return True, ""
        return False, f"Meta unexpected response: {resp.text[:300]}"
    return False, f"Meta API {resp.status_code}: {resp.text[:300]}"


def _send_wati(mobile, customer_name, occasion, settings):
    """WATI API — uses settings.webhook_url as the WATI server base URL."""
    template_name = (
        settings.birthday_template_name if occasion == 'birthday'
        else settings.anniversary_template_name
    )
    base_url = (settings.webhook_url or "").rstrip('/')
    if not base_url:
        return False, "WATI: set webhook_url to your WATI server URL (e.g. https://live-server-XXXXX.wati.io)"
    if not settings.api_key:
        return False, "WATI: api_key (Bearer token) is required"
    dial = dial_code_for_retail(getattr(settings, 'retail', None))
    url = f"{base_url}/api/v1/sendTemplateMessage?whatsappNumber={dial}{mobile}"
    headers = {"Authorization": f"Bearer {settings.api_key}", "Content-Type": "application/json"}
    payload = {
        "template_name": template_name,
        "broadcast_name": f"crm_{occasion}_{mobile}",
        "parameters": [{"name": "1", "value": customer_name}],
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code == 200:
        data = resp.json()
        if data.get('result'):
            return True, ""
        return False, f"WATI error: {resp.text[:300]}"
    return False, f"WATI API {resp.status_code}: {resp.text[:300]}"


def _send_aisensy(mobile, customer_name, occasion, settings):
    """AiSensy Campaign API."""
    template_name = (
        settings.birthday_template_name if occasion == 'birthday'
        else settings.anniversary_template_name
    )
    if not settings.api_key:
        return False, "AiSensy: api_key is required"
    dial = dial_code_for_retail(getattr(settings, 'retail', None))
    url = getattr(django_settings, 'AISENSY_API_URL', 'https://backend.aisensy.com/campaign/t1/api/v2')
    payload = {
        "apiKey": settings.api_key,
        "campaignName": template_name,
        "destination": f"{dial}{mobile}",
        "userName": customer_name,
        "templateParams": [customer_name, "20"],
        "source": getattr(django_settings, 'AISENSY_SOURCE_ID', 'JEWEL_ERP'),
        "media": {},
        "buttons": [],
        "carouselCards": [],
        "location": {},
    }
    resp = requests.post(url, json=payload, timeout=15)
    if 200 <= resp.status_code < 300:
        return True, ""
    return False, f"AiSensy API {resp.status_code}: {resp.text[:300]}"


def _send_webhook(mobile, message, customer_name, occasion, settings):
    """Generic HTTP POST webhook — fully user-defined URL and headers."""
    if not settings.webhook_url:
        return False, "Webhook URL is not configured"
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
    }
    resp = requests.post(settings.webhook_url, json=payload, headers=headers, timeout=15)
    if 200 <= resp.status_code < 300:
        return True, ""
    return False, f"Webhook {resp.status_code}: {resp.text[:300]}"
