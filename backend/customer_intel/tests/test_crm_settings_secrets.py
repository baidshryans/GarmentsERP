"""
CRM provider secrets must not round-trip to the browser.

Before this, `CRMSettings.api_key` was serialised on every GET, so anyone who
could open the CRM settings page could lift the WhatsApp access token. These
tests pin the fix: secrets are write-only, a blank submission preserves the
stored value, and the UI learns only whether one is set.
"""

from django.core.cache import cache
from django.test import TestCase, override_settings

from customer_intel.tests.factories import make_retail, make_user

API_KEY = "EAAG-super-secret-token"
APP_SECRET = "meta-app-secret-value"


@override_settings(ALLOWED_HOSTS=["*"])
class CRMSettingsSecretTests(TestCase):
    def setUp(self):
        from mastersconfig.models import CRMSettings

        cache.clear()
        self.retail = make_retail()
        self.settings = CRMSettings.objects.create(
            retail=self.retail, provider="meta",
            api_key=API_KEY, app_secret=APP_SECRET,
            phone_number_id="123456789",
        )
        self.user = make_user("admin", retail=self.retail, superuser=True)

        from rest_framework.authtoken.models import Token

        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Token {token.key}"
        self.client.defaults["HTTP_X_RETAIL_ID"] = self.retail.retail_code
        self.url = "/mastersconfig/api/crm-settings/"

    def test_get_never_returns_the_secrets(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertNotIn(API_KEY, body)
        self.assertNotIn(APP_SECRET, body)

    def test_get_reports_whether_a_secret_is_stored(self):
        data = self.client.get(self.url).json()

        self.assertTrue(data["api_key_is_set"])
        self.assertTrue(data["app_secret_is_set"])

    def test_blank_secret_preserves_the_stored_value(self):
        """Saving the form without retyping the token must not wipe it."""
        from mastersconfig.models import CRMSettings

        response = self.client.patch(
            self.url,
            data={"api_key": "", "app_secret": "", "phone_number_id": "999"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        settings = CRMSettings.objects.get(id=self.settings.id)
        self.assertEqual(settings.api_key, API_KEY)
        self.assertEqual(settings.app_secret, APP_SECRET)
        self.assertEqual(settings.phone_number_id, "999")

    def test_a_new_secret_replaces_the_old_one(self):
        from mastersconfig.models import CRMSettings

        self.client.patch(
            self.url, data={"api_key": "replacement-token"},
            content_type="application/json",
        )

        self.assertEqual(
            CRMSettings.objects.get(id=self.settings.id).api_key,
            "replacement-token",
        )

    def test_webhook_path_is_blank_until_inbound_is_enabled(self):
        self.assertEqual(self.client.get(self.url).json()["webhook_path"], "")

    def test_enabling_inbound_mints_a_unique_webhook_path(self):
        from mastersconfig.models import CRMSettings

        self.client.patch(self.url, data={"inbound_enabled": True},
                          content_type="application/json")

        path = self.client.get(self.url).json()["webhook_path"]
        key = CRMSettings.objects.get(id=self.settings.id).inbound_url_key

        self.assertTrue(key)
        self.assertIn(key, path)
        self.assertTrue(path.startswith("/customer-intel/api/whatsapp/webhook/"))
