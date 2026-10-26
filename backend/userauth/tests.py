from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from userauth.models import Role, Permission, UserRole
from sales.models import SalesVou

User = get_user_model()
MY_PERMS_URL = "/userauth/api/my-permissions/"


class MyPermissionsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_superuser_returns_is_superuser_true(self):
        su = User.objects.create_superuser("admin_mp", "a@a.com", "pw")
        self.client.force_authenticate(su)
        res = self.client.get(MY_PERMS_URL)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["is_superuser"])
        self.assertEqual(res.data["modules"], {})

    def test_user_without_role_returns_empty_modules(self):
        u = User.objects.create_user("norole", "n@n.com", "pw")
        self.client.force_authenticate(u)
        res = self.client.get(MY_PERMS_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, {"is_superuser": False, "modules": {}})

    def test_partial_permissions_reflected(self):
        u = User.objects.create_user("cashier", "c@c.com", "pw")
        role = Role.objects.create(name="Cashier")
        ct = ContentType.objects.get_for_model(SalesVou)
        Permission.objects.create(
            role=role, module=ct,
            can_list=True, can_get=True, can_post=False,
            can_put=False, can_patch=False, can_delete=False,
        )
        UserRole.objects.create(user=u, role=role)
        self.client.force_authenticate(u)
        res = self.client.get(MY_PERMS_URL)
        mods = res.data["modules"]
        self.assertTrue(mods["sales.salesvou"]["list"])
        self.assertFalse(mods["sales.salesvou"]["post"])

    def test_inline_child_inherits_parent_verbs(self):
        u = User.objects.create_user("inlineu", "i@i.com", "pw")
        role = Role.objects.create(name="SalesRole")
        ct = ContentType.objects.get_for_model(SalesVou)
        Permission.objects.create(
            role=role, module=ct,
            can_list=True, can_get=True, can_post=True,
            can_put=True, can_patch=True, can_delete=True,
        )
        UserRole.objects.create(user=u, role=role)
        self.client.force_authenticate(u)
        res = self.client.get(MY_PERMS_URL)
        # sales.salesvouitem inherits sales.salesvou per INLINE_MODEL_MAP
        self.assertIn("sales.salesvouitem", res.data["modules"])
        self.assertTrue(res.data["modules"]["sales.salesvouitem"]["post"])

    def test_requires_authentication(self):
        res = self.client.get(MY_PERMS_URL)
        self.assertEqual(res.status_code, 401)


class InlineModelMapIntegrityTest(TestCase):
    def test_every_label_is_a_real_content_type(self):
        from django.contrib.contenttypes.models import ContentType
        from userauth.permissions import INLINE_MODEL_MAP
        real = {f"{c.app_label}.{c.model}" for c in ContentType.objects.all()}
        bad = [(k, v) for k, v in INLINE_MODEL_MAP.items() if k not in real or v not in real]
        self.assertEqual(bad, [])
