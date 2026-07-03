# Email Infrastructure + Portal Auth/Authz Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the ERP a reusable per-retail email capability and rebuild the customer-portal login on a secure, leak-proof identity model with email-OTP delivery.

**Architecture:** Email is a standalone unit (`EmailSettings` + `send_email` async task + `EmailSendLog`) mirroring the existing `CRMSettings`/`send_occasion_message`/`CRMSendLog` trio. Portal identity moves from "mobile string = identity" to an explicit `CustomerPortalAccount` that owns a stored set of `linked_ledgers`; every portal query reads that set instead of re-matching by phone. The OTP/password flow is rebuilt on top: userid = email or phone, OTP hashed at rest and delivered by email, with throttling and single-use consumption.

**Tech Stack:** Django 6.0 + DRF 3.17, `django-tasks` (DatabaseBackend), `django.core.mail` (SMTP), React portal. Tests run **one at a time** with `--noinput` (shared in-memory DB hangs — project convention).

**Reference spec:** `docs/superpowers/specs/2026-07-03-email-infra-portal-auth-rebuild-design.md`

---

## File Structure

**Phase A — Email (standalone, independently shippable):**
- Modify `backend/mastersconfig/models.py` — add `EmailSettings`, `EmailSendLog`
- Modify `backend/contacts/tasks.py` — add `send_email` task
- Create `backend/mastersconfig/tests/test_email.py`
- Modify `backend/mastersconfig/serializers.py` — `EmailSettingsSerializer`
- Modify `backend/mastersconfig/views.py` + `urls.py` — config endpoint with superadmin gate

**Phase B — Portal identity:**
- Modify `backend/goldscheme/models.py` — add `CustomerPortalAccount`, `account` FK on `CustomerPortalToken`
- Create `backend/goldscheme/management/commands/seed_portal_accounts.py`
- Modify `backend/goldscheme/portal_auth.py` — set `request.portal_account`; add `portal_ledgers()` helper
- Create `backend/goldscheme/tests/test_portal_identity.py`

**Phase C — Auth flow:**
- Modify `backend/goldscheme/models.py` — `CustomerPortalOTP` (account FK, hashed code, helpers)
- Create `backend/goldscheme/portal_otp.py` — OTP generate/hash/verify + throttle helpers
- Modify `backend/goldscheme/portal_serializers.py`, `portal_views.py`
- Create `backend/goldscheme/tests/test_portal_auth_flow.py`
- Modify `frontend/src/portal/pages/PortalLogin.jsx`, add `PortalSetPassword.jsx`, `portalApiService.js`, router

**Phase D — Data fixes:**
- Modify `backend/sales/views/quotations.py` (M2), `backend/goldscheme/services/payment.py` (M3), `backend/goldscheme/portal_views.py` (M4)
- Create `backend/goldscheme/tests/test_portal_data_fixes.py`

Phase A merges independently. Phases B→C→D are ordered (C depends on B's account model; D depends on B's `portal_ledgers`).

---

## Phase A — Email Infrastructure

### Task A1: `EmailSettings` model

**Files:**
- Modify: `backend/mastersconfig/models.py` (after `CRMSendLog`, ~line 850)
- Test: `backend/mastersconfig/tests/test_email.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/mastersconfig/tests/test_email.py
from django.test import TestCase
from mastersconfig.models import RetailMaster, EmailSettings


class EmailSettingsModelTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(retail_name="Test", retail_code="T1")

    def test_gmail_preset_fills_host_port_on_save(self):
        es = EmailSettings.objects.create(retail=self.retail, provider="gmail")
        es.refresh_from_db()
        self.assertEqual(es.host, "smtp.gmail.com")
        self.assertEqual(es.port, 587)
        self.assertTrue(es.use_tls)

    def test_auto_send_bills_defaults_false(self):
        es = EmailSettings.objects.create(retail=self.retail, provider="custom_smtp")
        self.assertFalse(es.auto_send_bills)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python manage.py test mastersconfig.tests.test_email.EmailSettingsModelTest --noinput`
Expected: FAIL — `ImportError: cannot import name 'EmailSettings'`

- [ ] **Step 3: Add the model**

```python
# backend/mastersconfig/models.py  (append after CRMSendLog)
class EmailSettings(models.Model):
    """Per-retail SMTP configuration for outbound email (OTP, bills, statements)."""
    PROVIDER_CHOICES = [
        ('gmail',       'Gmail (SMTP + app password)'),
        ('outlook',     'Outlook / Office365 (SMTP + app password)'),
        ('custom_smtp', 'Custom SMTP'),
    ]
    PRESETS = {
        'gmail':   {'host': 'smtp.gmail.com',        'port': 587, 'use_tls': True},
        'outlook': {'host': 'smtp-mail.outlook.com', 'port': 587, 'use_tls': True},
    }
    retail          = models.OneToOneField(RetailMaster, on_delete=models.CASCADE, related_name='email_settings')
    provider        = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='custom_smtp')
    host            = models.CharField(max_length=200, blank=True)
    port            = models.PositiveIntegerField(default=587)
    use_tls         = models.BooleanField(default=True)
    username        = models.CharField(max_length=200, blank=True)
    password        = models.CharField(max_length=600, blank=True, help_text="SMTP password / app password")
    from_email      = models.EmailField(blank=True)
    from_name       = models.CharField(max_length=200, blank=True)
    is_enabled      = models.BooleanField(default=False, help_text="Enable outbound email for this retail")
    auto_send_bills = models.BooleanField(default=False, help_text="Superadmin-only: email bills to customers on save")
    last_run_status = models.CharField(max_length=500, blank=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_settings'

    def __str__(self):
        return f"Email Settings — {self.retail.retail_name}"

    def save(self, *args, **kwargs):
        preset = self.PRESETS.get(self.provider)
        if preset:
            self.host = preset['host']
            self.port = preset['port']
            self.use_tls = preset['use_tls']
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Make + run migration, run test**

Run: `cd backend && python manage.py makemigrations mastersconfig && python manage.py test mastersconfig.tests.test_email.EmailSettingsModelTest --noinput`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/mastersconfig/models.py backend/mastersconfig/migrations backend/mastersconfig/tests/test_email.py
git commit -m "feat(email): EmailSettings per-retail SMTP config model"
```

---

### Task A2: `EmailSendLog` model

**Files:**
- Modify: `backend/mastersconfig/models.py` (after `EmailSettings`)
- Test: `backend/mastersconfig/tests/test_email.py`

- [ ] **Step 1: Add the failing test**

```python
# append to test_email.py
from mastersconfig.models import EmailSendLog

class EmailSendLogModelTest(TestCase):
    def test_create_log_row(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="R1")
        log = EmailSendLog.objects.create(
            retail=retail, to_email="a@b.com", subject="Hi",
            purpose="otp", status="sent",
        )
        self.assertEqual(log.status, "sent")
        self.assertEqual(EmailSendLog.objects.filter(retail=retail).count(), 1)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test mastersconfig.tests.test_email.EmailSendLogModelTest --noinput`
Expected: FAIL — cannot import `EmailSendLog`

- [ ] **Step 3: Add the model**

```python
# backend/mastersconfig/models.py  (append after EmailSettings)
class EmailSendLog(models.Model):
    """Audit log of every outbound email attempt."""
    STATUS_CHOICES  = [('sent', 'Sent'), ('failed', 'Failed'), ('skipped', 'Skipped')]
    PURPOSE_CHOICES = [('otp', 'OTP'), ('bill', 'Bill'), ('statement', 'Statement'), ('other', 'Other')]
    retail        = models.ForeignKey(RetailMaster, on_delete=models.CASCADE, related_name='email_logs')
    to_email      = models.EmailField()
    subject       = models.CharField(max_length=300)
    purpose       = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='other')
    sent_at       = models.DateTimeField(auto_now_add=True)
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES)
    error_message = models.CharField(max_length=500, blank=True)

    class Meta:
        db_table = 'email_send_log'
        ordering = ['-sent_at']
        indexes = [models.Index(fields=['retail', '-sent_at'], name='idx_email_log_retail_date')]

    def __str__(self):
        return f"{self.to_email} | {self.purpose} | {self.status} | {self.sent_at:%Y-%m-%d}"
```

- [ ] **Step 4: Migrate + run test**

Run: `cd backend && python manage.py makemigrations mastersconfig && python manage.py test mastersconfig.tests.test_email.EmailSendLogModelTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/mastersconfig/models.py backend/mastersconfig/migrations backend/mastersconfig/tests/test_email.py
git commit -m "feat(email): EmailSendLog audit model"
```

---

### Task A3: `send_email` async task

**Files:**
- Modify: `backend/contacts/tasks.py` (append)
- Test: `backend/mastersconfig/tests/test_email.py`

- [ ] **Step 1: Add failing test (patches SMTP so no real mail is sent)**

```python
# append to test_email.py
from unittest.mock import patch
from contacts.tasks import send_email

class SendEmailTaskTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(retail_name="R", retail_code="R2")

    def test_skipped_when_disabled(self):
        EmailSettings.objects.create(retail=self.retail, provider="custom_smtp", is_enabled=False)
        send_email(self.retail.id, "c@x.com", "S", "B", "otp")
        log = EmailSendLog.objects.get(retail=self.retail)
        self.assertEqual(log.status, "skipped")

    @patch("contacts.tasks.get_connection")
    def test_sent_logs_success(self, mock_conn):
        EmailSettings.objects.create(
            retail=self.retail, provider="gmail", is_enabled=True,
            username="u", password="p", from_email="shop@x.com", from_name="Shop",
        )
        send_email(self.retail.id, "c@x.com", "S", "B", "otp")
        log = EmailSendLog.objects.get(retail=self.retail)
        self.assertEqual(log.status, "sent")
        self.assertTrue(mock_conn.called)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test mastersconfig.tests.test_email.SendEmailTaskTest --noinput`
Expected: FAIL — cannot import `send_email`

- [ ] **Step 3: Implement the task**

```python
# backend/contacts/tasks.py  (append; TransientSendError already defined in this file)
from django.core.mail import get_connection, EmailMultiAlternatives
from django_tasks import task


@task()
def send_email(retail_id, to_email, subject, body, purpose="other", html_body=None):
    """Send one email via the retail's EmailSettings and log the outcome.

    Logs status='skipped' when email is not configured/enabled, 'sent' on
    success, 'failed' on a permanent error. Raises TransientSendError on a
    transient SMTP failure so the worker result shows FAILED for retry.
    """
    from mastersconfig.models import EmailSettings, EmailSendLog

    es = EmailSettings.objects.select_related("retail").filter(retail_id=retail_id).first()
    if es is None or not es.is_enabled:
        EmailSendLog.objects.create(
            retail_id=retail_id, to_email=to_email, subject=subject,
            purpose=purpose, status="skipped",
            error_message="Email not configured or disabled",
        )
        return

    from_addr = f"{es.from_name} <{es.from_email}>" if es.from_name else es.from_email
    try:
        connection = get_connection(
            host=es.host, port=es.port, username=es.username,
            password=es.password, use_tls=es.use_tls,
        )
        msg = EmailMultiAlternatives(subject, body, from_addr, [to_email], connection=connection)
        if html_body:
            msg.attach_alternative(html_body, "text/html")
        msg.send()
    except Exception as exc:  # noqa: BLE001 — classify below
        EmailSendLog.objects.create(
            retail=es.retail, to_email=to_email, subject=subject,
            purpose=purpose, status="failed", error_message=str(exc)[:500],
        )
        raise TransientSendError(str(exc))

    EmailSendLog.objects.create(
        retail=es.retail, to_email=to_email, subject=subject,
        purpose=purpose, status="sent",
    )
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test mastersconfig.tests.test_email.SendEmailTaskTest --noinput`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/contacts/tasks.py backend/mastersconfig/tests/test_email.py
git commit -m "feat(email): send_email async task with per-retail SMTP + audit log"
```

---

### Task A4: EmailSettings config API with superadmin gate on `auto_send_bills`

**Files:**
- Modify: `backend/mastersconfig/serializers.py`, `backend/mastersconfig/views.py`, `backend/mastersconfig/urls.py`
- Test: `backend/mastersconfig/tests/test_email.py`

- [ ] **Step 1: Add failing test**

```python
# append to test_email.py
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

class EmailSettingsApiTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(retail_name="R", retail_code="R3")
        User = get_user_model()
        self.staff = User.objects.create_user("staff", password="x", is_staff=True)
        self.super = User.objects.create_superuser("root", "r@x.com", "x")

    def _patch(self, user, payload):
        c = APIClient(); c.force_authenticate(user=user)
        return c.patch(f"/mastersconfig/api/email-settings/{self.retail.id}/", payload, format="json")

    def test_non_superadmin_cannot_enable_auto_send_bills(self):
        EmailSettings.objects.create(retail=self.retail, provider="gmail")
        resp = self._patch(self.staff, {"auto_send_bills": True})
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(EmailSettings.objects.get(retail=self.retail).auto_send_bills)

    def test_superadmin_can_enable_auto_send_bills(self):
        EmailSettings.objects.create(retail=self.retail, provider="gmail")
        resp = self._patch(self.super, {"auto_send_bills": True})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(EmailSettings.objects.get(retail=self.retail).auto_send_bills)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test mastersconfig.tests.test_email.EmailSettingsApiTest --noinput`
Expected: FAIL — 404 (route missing)

- [ ] **Step 3: Serializer + view + route**

```python
# backend/mastersconfig/serializers.py  (append)
from rest_framework import serializers
from .models import EmailSettings

class EmailSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSettings
        fields = ['id', 'retail', 'provider', 'host', 'port', 'use_tls', 'username',
                  'password', 'from_email', 'from_name', 'is_enabled', 'auto_send_bills',
                  'last_run_status', 'updated_at']
        read_only_fields = ['host', 'port', 'use_tls', 'last_run_status', 'updated_at']
        extra_kwargs = {'password': {'write_only': True}}
```

```python
# backend/mastersconfig/views.py  (append)
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import EmailSettings
from .serializers import EmailSettingsSerializer

class EmailSettingsViewSet(viewsets.ModelViewSet):
    queryset = EmailSettings.objects.all()
    serializer_class = EmailSettingsSerializer
    permission_classes = [IsAuthenticated]

    def update(self, request, *args, **kwargs):
        # auto_send_bills is superadmin-only
        if 'auto_send_bills' in request.data and not request.user.is_superuser:
            current = self.get_object().auto_send_bills
            if bool(request.data['auto_send_bills']) != current:
                return Response(
                    {'error': 'Only a superadmin can change auto_send_bills.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
        return super().update(request, *args, **kwargs)
```

```python
# backend/mastersconfig/urls.py  (register on the existing DRF router; if a
# router named `router` exists, add this line near the other registrations)
from .views import EmailSettingsViewSet
router.register(r'api/email-settings', EmailSettingsViewSet, basename='email-settings')
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test mastersconfig.tests.test_email.EmailSettingsApiTest --noinput`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/mastersconfig/serializers.py backend/mastersconfig/views.py backend/mastersconfig/urls.py backend/mastersconfig/tests/test_email.py
git commit -m "feat(email): EmailSettings config API with superadmin-gated auto_send_bills"
```

---

## Phase B — Portal Identity & Authorization

### Task B1: `CustomerPortalAccount` model

**Files:**
- Modify: `backend/goldscheme/models.py` (after `CustomerPortalCredential`)
- Test: `backend/goldscheme/tests/test_portal_identity.py`

- [ ] **Step 1: Failing test**

```python
# backend/goldscheme/tests/test_portal_identity.py
from django.test import TestCase
from mastersconfig.models import RetailMaster
from contacts.models import Ledger
from goldscheme.models import CustomerPortalAccount


class PortalAccountTest(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(retail_name="R", retail_code="R1")
        self.l1 = Ledger.objects.create(ac_name="Cust A", retail_code=self.retail)
        self.l2 = Ledger.objects.create(ac_name="Cust A2", retail_code=self.retail)

    def test_account_links_explicit_ledgers(self):
        acc = CustomerPortalAccount.objects.create(primary_email="a@x.com")
        acc.linked_ledgers.add(self.l1, self.l2)
        self.assertEqual(acc.linked_ledgers.count(), 2)

    def test_password_hashing_roundtrip(self):
        acc = CustomerPortalAccount(primary_email="a@x.com")
        acc.set_password("secret123")
        acc.save()
        self.assertTrue(acc.check_password("secret123"))
        self.assertFalse(acc.check_password("wrong"))
```

> Note: confirm `Ledger`'s required fields; adjust `Ledger.objects.create(...)` kwargs to satisfy NOT NULL columns (`retail_code` FK is required per `LedgerRole` usage).

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_identity.PortalAccountTest --noinput`
Expected: FAIL — cannot import `CustomerPortalAccount`

- [ ] **Step 3: Add the model**

```python
# backend/goldscheme/models.py  (append after CustomerPortalCredential)
class CustomerPortalAccount(models.Model):
    """Portal login identity. Owns an explicit set of linked ledgers — the sole
    basis for what the customer may see (never a live mobile match)."""
    primary_email  = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    phone          = models.CharField(max_length=20, blank=True, db_index=True)
    password_hash  = models.CharField(max_length=128, blank=True)
    is_active      = models.BooleanField(default=True)
    linked_ledgers = models.ManyToManyField('contacts.Ledger', related_name='portal_accounts', blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'customer_portal_account'

    def __str__(self):
        return f"Portal account {self.primary_email}"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return bool(self.password_hash) and check_password(raw_password, self.password_hash)
```

- [ ] **Step 4: Migrate + run test**

Run: `cd backend && python manage.py makemigrations goldscheme && python manage.py test goldscheme.tests.test_portal_identity.PortalAccountTest --noinput`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/models.py backend/goldscheme/migrations backend/goldscheme/tests/test_portal_identity.py
git commit -m "feat(portal): CustomerPortalAccount identity with explicit linked_ledgers"
```

---

### Task B2: Add `account` FK to `CustomerPortalToken`

**Files:**
- Modify: `backend/goldscheme/models.py` (`CustomerPortalToken`, ~line 362)
- Test: `backend/goldscheme/tests/test_portal_identity.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_identity.py
from goldscheme.models import CustomerPortalToken

class PortalTokenAccountTest(TestCase):
    def test_token_references_account(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RT")
        acc = CustomerPortalAccount.objects.create(primary_email="t@x.com")
        tok = CustomerPortalToken.objects.create(account=acc, retail=retail)
        self.assertEqual(tok.account_id, acc.id)
        self.assertIsNotNone(tok.expires_at)  # auto-set in save()
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_identity.PortalTokenAccountTest --noinput`
Expected: FAIL — `account` not a field; and `ledger`/`mobile` are currently required.

- [ ] **Step 3: Edit the model**

```python
# backend/goldscheme/models.py — in CustomerPortalToken, make ledger/mobile optional
# and add the account FK:
    account    = models.ForeignKey('goldscheme.CustomerPortalAccount', on_delete=models.CASCADE,
                                    related_name='tokens', null=True, blank=True)
    ledger     = models.ForeignKey('contacts.Ledger', on_delete=models.CASCADE,
                                    related_name='portal_tokens', null=True, blank=True)
    mobile     = models.CharField(max_length=20, blank=True)
```

- [ ] **Step 4: Migrate + run test**

Run: `cd backend && python manage.py makemigrations goldscheme && python manage.py test goldscheme.tests.test_portal_identity.PortalTokenAccountTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/models.py backend/goldscheme/migrations backend/goldscheme/tests/test_portal_identity.py
git commit -m "feat(portal): token references CustomerPortalAccount"
```

---

### Task B3: `seed_portal_accounts` bootstrap command

**Files:**
- Create: `backend/goldscheme/management/commands/seed_portal_accounts.py`
- Test: `backend/goldscheme/tests/test_portal_identity.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_identity.py
from django.core.management import call_command
from goldscheme.models import CustomerPortalCredential

class SeedPortalAccountsTest(TestCase):
    def test_creates_account_and_links_ledgers_by_mobile(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RS")
        led = Ledger.objects.create(ac_name="C", retail_code=retail, mobile1="9998887777", email="c@x.com")
        CustomerPortalCredential.objects.create(ledger=led, password_hash="x", is_active=True)
        call_command("seed_portal_accounts", "--apply")
        acc = CustomerPortalAccount.objects.get(primary_email="c@x.com")
        self.assertIn(led, acc.linked_ledgers.all())
```

> Confirm the `Ledger` email field name (`email`); adjust if different.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_identity.SeedPortalAccountsTest --noinput`
Expected: FAIL — Unknown command `seed_portal_accounts`

- [ ] **Step 3: Implement the command**

```python
# backend/goldscheme/management/commands/seed_portal_accounts.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from contacts.models import Ledger
from goldscheme.models import CustomerPortalCredential, CustomerPortalAccount


class Command(BaseCommand):
    help = "One-time: create CustomerPortalAccount rows from existing credentials, " \
           "linking ledgers by current mobile match. Idempotent. Use --apply to write."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist changes")

    @transaction.atomic
    def handle(self, *args, **opts):
        apply = opts["apply"]
        created = linked = skipped = 0
        for cred in CustomerPortalCredential.objects.select_related("ledger"):
            led = cred.ledger
            email = (getattr(led, "email", "") or "").strip().lower()
            if not email:
                skipped += 1
                self.stdout.write(f"SKIP (no email): {led.ac_name}")
                continue
            acc, is_new = CustomerPortalAccount.objects.get_or_create(
                primary_email=email,
                defaults={"password_hash": cred.password_hash,
                          "phone": getattr(led, "mobile1", "") or "",
                          "is_active": cred.is_active},
            )
            if is_new:
                created += 1
            # Link this ledger + any ledger sharing its mobile (old expansion, run once)
            mobiles = [m for m in [getattr(led, "mobile1", ""), getattr(led, "mobile2", ""),
                                   getattr(led, "phone1", "")] if m]
            q = Q(pk=led.pk)
            for m in mobiles:
                q |= Q(mobile1=m) | Q(mobile2=m) | Q(phone1=m)
            for match in Ledger.objects.filter(q):
                if match not in acc.linked_ledgers.all():
                    acc.linked_ledgers.add(match)
                    linked += 1
        self.stdout.write(self.style.SUCCESS(
            f"accounts_created={created} ledgers_linked={linked} skipped={skipped} apply={apply}"))
        if not apply:
            transaction.set_rollback(True)
            self.stdout.write("DRY RUN — rolled back. Re-run with --apply to persist.")
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_identity.SeedPortalAccountsTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/management/commands/seed_portal_accounts.py backend/goldscheme/tests/test_portal_identity.py
git commit -m "feat(portal): seed_portal_accounts bootstrap command"
```

---

### Task B4: `portal_auth` uses account; add `portal_ledgers()` helper

**Files:**
- Modify: `backend/goldscheme/portal_auth.py`
- Test: `backend/goldscheme/tests/test_portal_identity.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_identity.py
from goldscheme.portal_auth import portal_ledgers

class PortalLedgersHelperTest(TestCase):
    def test_returns_account_linked_ledgers(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RL")
        acc = CustomerPortalAccount.objects.create(primary_email="p@x.com")
        led = Ledger.objects.create(ac_name="C", retail_code=retail)
        acc.linked_ledgers.add(led)

        class Req:  # minimal stand-in
            portal_account = acc
        self.assertEqual(list(portal_ledgers(Req())), [led])
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_identity.PortalLedgersHelperTest --noinput`
Expected: FAIL — cannot import `portal_ledgers`

- [ ] **Step 3: Edit `portal_auth.py`**

```python
# In PortalTokenAuthentication.authenticate — change select_related and request attrs:
            token = CustomerPortalToken.objects.select_related(
                'account', 'retail', 'retail__active_fy'
            ).get(token=token_uuid)
        # ...after expiry check...
        request.retail = token.retail
        request.fiscal_year = getattr(token.retail, 'active_fy', None)
        request.portal_account = token.account
        request.portal_token = token
        return (token.account, token)


def portal_ledgers(request):
    """The set of ledgers the authenticated portal account may access."""
    account = getattr(request, 'portal_account', None)
    if account is None:
        from contacts.models import Ledger
        return Ledger.objects.none()
    return account.linked_ledgers.all()
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_identity.PortalLedgersHelperTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/portal_auth.py backend/goldscheme/tests/test_portal_identity.py
git commit -m "feat(portal): auth binds request to account; portal_ledgers() helper"
```

---

## Phase C — Auth Flow Rebuild

### Task C1: OTP model — account FK + hashed code + helpers

**Files:**
- Modify: `backend/goldscheme/models.py` (`CustomerPortalOTP`, ~line 341)
- Test: `backend/goldscheme/tests/test_portal_auth_flow.py`

- [ ] **Step 1: Failing test**

```python
# backend/goldscheme/tests/test_portal_auth_flow.py
from django.test import TestCase
from mastersconfig.models import RetailMaster
from goldscheme.models import CustomerPortalAccount, CustomerPortalOTP


class OtpModelTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="o@x.com")

    def test_code_is_hashed_and_verifies(self):
        otp = CustomerPortalOTP.objects.create(account=self.acc)
        otp.set_code("123456")
        otp.save()
        self.assertNotEqual(otp.code_hash, "123456")
        self.assertTrue(otp.check_code("123456"))
        self.assertFalse(otp.check_code("000000"))
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.OtpModelTest --noinput`
Expected: FAIL — no `account`/`set_code` on `CustomerPortalOTP`

- [ ] **Step 3: Edit the model**

```python
# backend/goldscheme/models.py — replace CustomerPortalOTP body:
class CustomerPortalOTP(models.Model):
    """Temporary hashed OTP for portal login/password verification."""
    account     = models.ForeignKey('goldscheme.CustomerPortalAccount', on_delete=models.CASCADE,
                                     related_name='otps', null=True, blank=True)
    mobile      = models.CharField(max_length=20, blank=True, db_index=True)  # legacy, unused going forward
    retail      = models.ForeignKey('mastersconfig.RetailMaster', on_delete=models.CASCADE, null=True, blank=True)
    code_hash   = models.CharField(max_length=128, blank=True)
    is_verified = models.BooleanField(default=False)
    attempts    = models.PositiveIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customer_portal_otp'

    def set_code(self, raw_code):
        from django.contrib.auth.hashers import make_password
        self.code_hash = make_password(raw_code)

    def check_code(self, raw_code):
        from django.contrib.auth.hashers import check_password
        return bool(self.code_hash) and check_password(raw_code, self.code_hash)

    @property
    def is_expired(self):
        minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 5)
        return timezone.now() > self.created_at + timedelta(minutes=minutes)
```

> The legacy `otp_code` column is dropped. Generate the migration; it will remove `otp_code` and add `account`/`code_hash`. Existing OTP rows are transient (5-min), so data loss is acceptable.

- [ ] **Step 4: Migrate + run test**

Run: `cd backend && python manage.py makemigrations goldscheme && python manage.py test goldscheme.tests.test_portal_auth_flow.OtpModelTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/models.py backend/goldscheme/migrations backend/goldscheme/tests/test_portal_auth_flow.py
git commit -m "feat(portal): OTP keyed to account, stored hashed"
```

---

### Task C2: OTP generation + throttle helpers

**Files:**
- Create: `backend/goldscheme/portal_otp.py`
- Test: `backend/goldscheme/tests/test_portal_auth_flow.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_auth_flow.py
from goldscheme.portal_otp import generate_otp_code, issue_otp, is_throttled

class OtpHelperTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="h@x.com")

    def test_generate_is_six_digits(self):
        code = generate_otp_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_issue_creates_hashed_otp_and_then_throttles(self):
        code = issue_otp(self.acc)
        otp = CustomerPortalOTP.objects.filter(account=self.acc).latest("created_at")
        self.assertTrue(otp.check_code(code))
        self.assertTrue(is_throttled(self.acc))  # second request inside cooldown blocked
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.OtpHelperTest --noinput`
Expected: FAIL — module `portal_otp` missing

- [ ] **Step 3: Implement helpers**

```python
# backend/goldscheme/portal_otp.py
import secrets
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from .models import CustomerPortalOTP

OTP_COOLDOWN_SECONDS = getattr(settings, 'OTP_COOLDOWN_SECONDS', 60)
OTP_HOURLY_CAP       = getattr(settings, 'OTP_HOURLY_CAP', 5)


def generate_otp_code():
    return f"{secrets.randbelow(1_000_000):06d}"


def is_throttled(account):
    now = timezone.now()
    recent = CustomerPortalOTP.objects.filter(
        account=account, created_at__gte=now - timedelta(seconds=OTP_COOLDOWN_SECONDS)
    ).exists()
    hourly = CustomerPortalOTP.objects.filter(
        account=account, created_at__gte=now - timedelta(hours=1)
    ).count()
    return recent or hourly >= OTP_HOURLY_CAP


def issue_otp(account):
    """Create a fresh hashed OTP for the account and return the raw code."""
    CustomerPortalOTP.objects.filter(account=account, is_verified=False).delete()
    code = generate_otp_code()
    otp = CustomerPortalOTP(account=account)
    otp.set_code(code)
    otp.save()
    return code
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.OtpHelperTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/portal_otp.py backend/goldscheme/tests/test_portal_auth_flow.py
git commit -m "feat(portal): secure OTP generation + per-account throttle helpers"
```

---

### Task C3: `request-otp` — userid resolution, throttle, email delivery

**Files:**
- Modify: `backend/goldscheme/portal_serializers.py`, `backend/goldscheme/portal_views.py`
- Test: `backend/goldscheme/tests/test_portal_auth_flow.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_auth_flow.py
from unittest.mock import patch
from rest_framework.test import APIClient
from contacts.models import Ledger

class RequestOtpTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="r@x.com", phone="9990001111")

    @patch("goldscheme.portal_views.send_email")
    def test_request_by_email_enqueues_email(self, mock_send):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/request-otp/", {"userid": "r@x.com"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_send.enqueue.called)

    @patch("goldscheme.portal_views.send_email")
    def test_request_by_phone_resolves_account(self, mock_send):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/request-otp/", {"userid": "9990001111"}, format="json")
        self.assertEqual(resp.status_code, 200)

    def test_unknown_userid_generic_response(self, ):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/request-otp/", {"userid": "nobody@x.com"}, format="json")
        self.assertEqual(resp.status_code, 200)  # generic to prevent enumeration (M1)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.RequestOtpTest --noinput`
Expected: FAIL — serializer expects `mobile`, view prints instead of emailing

- [ ] **Step 3: Serializers + view**

```python
# backend/goldscheme/portal_serializers.py — replace request/verify/set serializers:
class PortalRequestOTPSerializer(serializers.Serializer):
    userid = serializers.CharField(max_length=254)  # email or phone

class PortalVerifyOTPSerializer(serializers.Serializer):
    userid = serializers.CharField(max_length=254)
    otp = serializers.CharField(max_length=6, min_length=4)

class PortalPasswordLoginSerializer(serializers.Serializer):
    userid = serializers.CharField(max_length=254)
    password = serializers.CharField(max_length=128)

class PortalSetPasswordSerializer(serializers.Serializer):
    userid = serializers.CharField(max_length=254)
    otp = serializers.CharField(max_length=6, min_length=4)
    new_password = serializers.CharField(max_length=128, min_length=6)
```

```python
# backend/goldscheme/portal_views.py — add near the top-level imports:
from contacts.tasks import send_email
from .portal_otp import issue_otp, is_throttled
from .models import CustomerPortalAccount

def _resolve_account(userid):
    userid = (userid or "").strip()
    if "@" in userid:
        return CustomerPortalAccount.objects.filter(primary_email__iexact=userid, is_active=True).first()
    return CustomerPortalAccount.objects.filter(phone=userid, is_active=True).first()
```

```python
# Replace PortalRequestOTPView.post body:
    def post(self, request):
        ser = PortalRequestOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        account = _resolve_account(ser.validated_data['userid'])
        # Always return a generic OK to prevent user enumeration (M1)
        generic = Response({'success': True,
                            'message': 'If an account exists, an OTP has been emailed.'})
        if account is None:
            return generic
        if is_throttled(account):
            return Response({'error': 'Please wait before requesting another OTP.'},
                            status=status.HTTP_429_TOO_MANY_REQUESTS)
        code = issue_otp(account)
        retail_id = account.linked_ledgers.values_list('retail_code', flat=True).first()
        send_email.enqueue(
            retail_id, account.primary_email, "Your login OTP",
            f"Your one-time password is {code}. It expires in 5 minutes.", "otp",
        )
        return generic
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.RequestOtpTest --noinput`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/portal_serializers.py backend/goldscheme/portal_views.py backend/goldscheme/tests/test_portal_auth_flow.py
git commit -m "feat(portal): request-otp resolves email/phone, throttles, emails OTP"
```

---

### Task C4: `verify-otp` — hashed compare, correct ordering, issue token

**Files:**
- Modify: `backend/goldscheme/portal_views.py`
- Test: `backend/goldscheme/tests/test_portal_auth_flow.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_auth_flow.py
from goldscheme.models import CustomerPortalToken
from goldscheme.portal_otp import issue_otp

class VerifyOtpTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="v@x.com")

    def test_valid_otp_issues_token(self):
        code = issue_otp(self.acc)
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/verify-otp/",
                      {"userid": "v@x.com", "otp": code}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json())
        self.assertEqual(CustomerPortalToken.objects.filter(account=self.acc).count(), 1)

    def test_wrong_otp_does_not_consume(self):
        issue_otp(self.acc)
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/verify-otp/",
                      {"userid": "v@x.com", "otp": "000000"}, format="json")
        self.assertEqual(resp.status_code, 400)
        # OTP still present and not verified (H4 fix)
        otp = CustomerPortalOTP.objects.get(account=self.acc)
        self.assertFalse(otp.is_verified)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.VerifyOtpTest --noinput`
Expected: FAIL — old view expects password + mobile

- [ ] **Step 3: Rewrite `PortalVerifyOTPView.post`**

```python
    def post(self, request):
        ser = PortalVerifyOTPSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        account = _resolve_account(ser.validated_data['userid'])
        if account is None:
            return Response({'error': 'Invalid OTP.'}, status=status.HTTP_400_BAD_REQUEST)

        otp = CustomerPortalOTP.objects.filter(
            account=account, is_verified=False
        ).order_by('-created_at').first()
        if otp is None or otp.is_expired:
            return Response({'error': 'OTP expired. Please request a new one.'},
                            status=status.HTTP_400_BAD_REQUEST)

        max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
        if not otp.check_code(ser.validated_data['otp'].strip()):
            otp.attempts += 1
            if otp.attempts >= max_attempts:
                otp.delete()
                return Response({'error': 'Too many failed attempts. Request a new OTP.'},
                                status=status.HTTP_429_TOO_MANY_REQUESTS)
            otp.save()
            return Response({'error': f'Invalid OTP. {max_attempts - otp.attempts} attempt(s) left.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Success — consume OTP (single use), issue token
        otp.delete()
        retail = None
        led = account.linked_ledgers.select_related('retail_code').first()
        if led is not None:
            retail = led.retail_code
        token = CustomerPortalToken.objects.create(account=account, retail=retail)
        return Response({'success': True, 'token': str(token.token),
                         'customer_name': account.primary_email})
```

> `retail` on the token is now nullable (Task B2). If your `Ledger` FK to retail is not named `retail_code`, adjust `select_related`/attribute.

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.VerifyOtpTest --noinput`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/portal_views.py backend/goldscheme/tests/test_portal_auth_flow.py
git commit -m "feat(portal): verify-otp hashed compare, no-consume-on-fail, issues token"
```

---

### Task C5: password-login endpoint

**Files:**
- Modify: `backend/goldscheme/portal_views.py`, `backend/goldscheme/urls.py`
- Test: `backend/goldscheme/tests/test_portal_auth_flow.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_auth_flow.py
class PasswordLoginTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="pw@x.com")
        self.acc.set_password("secret123"); self.acc.save()

    def test_correct_password_issues_token(self):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/login/",
                      {"userid": "pw@x.com", "password": "secret123"}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("token", resp.json())

    def test_wrong_password_401(self):
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/login/",
                      {"userid": "pw@x.com", "password": "nope"}, format="json")
        self.assertEqual(resp.status_code, 401)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.PasswordLoginTest --noinput`
Expected: FAIL — 404 (route missing)

- [ ] **Step 3: Add view + route**

```python
# backend/goldscheme/portal_views.py
from .portal_serializers import PortalPasswordLoginSerializer

class PortalPasswordLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        ser = PortalPasswordLoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        account = _resolve_account(ser.validated_data['userid'])
        if account is None or not account.check_password(ser.validated_data['password']):
            return Response({'error': 'Invalid credentials.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        led = account.linked_ledgers.select_related('retail_code').first()
        retail = led.retail_code if led is not None else None
        token = CustomerPortalToken.objects.create(account=account, retail=retail)
        return Response({'success': True, 'token': str(token.token),
                         'customer_name': account.primary_email})
```

```python
# backend/goldscheme/urls.py — add alongside the other portal routes:
    path('api/portal/login/', PortalPasswordLoginView.as_view()),
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.PasswordLoginTest --noinput`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/portal_views.py backend/goldscheme/urls.py backend/goldscheme/tests/test_portal_auth_flow.py
git commit -m "feat(portal): password login endpoint"
```

---

### Task C6: `set-password` — OTP single-use; logged-in change requires old password

**Files:**
- Modify: `backend/goldscheme/portal_views.py`
- Test: `backend/goldscheme/tests/test_portal_auth_flow.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_auth_flow.py
class SetPasswordTest(TestCase):
    def setUp(self):
        self.acc = CustomerPortalAccount.objects.create(primary_email="sp@x.com")

    def test_first_time_set_via_otp(self):
        code = issue_otp(self.acc)
        c = APIClient()
        resp = c.post("/goldscheme/api/portal/set-password/",
                      {"userid": "sp@x.com", "otp": code, "new_password": "brandnew1"},
                      format="json")
        self.assertEqual(resp.status_code, 200)
        self.acc.refresh_from_db()
        self.assertTrue(self.acc.check_password("brandnew1"))
        self.assertFalse(CustomerPortalOTP.objects.filter(account=self.acc).exists())  # single use

    def test_change_while_logged_in_requires_old_password(self):
        self.acc.set_password("orig123"); self.acc.save()
        token = CustomerPortalToken.objects.create(account=self.acc)
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"PortalToken {token.token}")
        resp = c.post("/goldscheme/api/portal/change-password/",
                      {"old_password": "wrong", "new_password": "changed99"}, format="json")
        self.assertEqual(resp.status_code, 400)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.SetPasswordTest --noinput`
Expected: FAIL — old view uses mobile; change-password route missing

- [ ] **Step 3: Rewrite `set-password`; add `change-password`**

```python
# backend/goldscheme/portal_views.py — PortalSetPasswordView.post:
    def post(self, request):
        ser = PortalSetPasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        account = _resolve_account(ser.validated_data['userid'])
        if account is None:
            return Response({'error': 'Invalid request.'}, status=status.HTTP_400_BAD_REQUEST)
        otp = CustomerPortalOTP.objects.filter(account=account, is_verified=False)\
            .order_by('-created_at').first()
        if otp is None or otp.is_expired or not otp.check_code(ser.validated_data['otp'].strip()):
            return Response({'error': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        otp.delete()  # single use
        account.set_password(ser.validated_data['new_password'])
        account.is_active = True
        account.email_verified = True
        account.save()
        return Response({'success': True, 'message': 'Password set. You can now log in.'})


class PortalChangePasswordView(APIView):
    authentication_classes = [PortalTokenAuthentication]
    permission_classes = [IsPortalAuthenticated]

    def post(self, request):
        account = request.portal_account
        old = request.data.get('old_password', '')
        new = request.data.get('new_password', '')
        if len(new) < 6:
            return Response({'error': 'New password too short.'}, status=status.HTTP_400_BAD_REQUEST)
        if not account.check_password(old):
            return Response({'error': 'Current password is incorrect.'},
                            status=status.HTTP_400_BAD_REQUEST)
        account.set_password(new); account.save()
        return Response({'success': True, 'message': 'Password changed.'})
```

```python
# backend/goldscheme/urls.py — add:
    path('api/portal/change-password/', PortalChangePasswordView.as_view()),
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.SetPasswordTest --noinput`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/portal_views.py backend/goldscheme/urls.py backend/goldscheme/tests/test_portal_auth_flow.py
git commit -m "feat(portal): OTP-based set-password (single use) + logged-in change-password"
```

---

### Task C7: Update remaining portal views to use `portal_ledgers` (C2 leak closed)

**Files:**
- Modify: `backend/goldscheme/portal_views.py` (dashboard, enrollment, pay)
- Test: `backend/goldscheme/tests/test_portal_auth_flow.py`

- [ ] **Step 1: Failing regression test (the C2 scenario)**

```python
# append to test_portal_auth_flow.py
from mastersconfig.models import RetailMaster
from contacts.models import Ledger
from goldscheme.models import CustomerPortalToken

class C2LeakTest(TestCase):
    def test_shared_phone_does_not_leak_other_account_data(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RC")
        # Two ledgers share a phone but belong to different accounts
        led_a = Ledger.objects.create(ac_name="A", retail_code=retail, mobile1="9998887777")
        led_b = Ledger.objects.create(ac_name="B", retail_code=retail, mobile1="9998887777")
        acc_a = CustomerPortalAccount.objects.create(primary_email="a@x.com")
        acc_a.linked_ledgers.add(led_a)  # A only
        token = CustomerPortalToken.objects.create(account=acc_a, retail=retail)
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"PortalToken {token.token}")
        resp = c.get("/goldscheme/api/portal/dashboard/")
        self.assertEqual(resp.status_code, 200)
        names = [row.get("ledger_name") for row in resp.json().get("enrollments", [])]
        self.assertNotIn("B", names)  # B's data must never appear
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.C2LeakTest --noinput`
Expected: FAIL — dashboard still uses `_find_all_customer_ledgers(mobile)`

- [ ] **Step 3: Replace ledger resolution in all three views**

```python
# backend/goldscheme/portal_views.py — in PortalDashboardView.get,
# PortalEnrollmentDetailView.get, PortalPayInstallmentView.post, replace:
#     mobile = request.portal_token.mobile
#     customer_ledgers = _find_all_customer_ledgers(mobile)
# with:
        from .portal_auth import portal_ledgers
        customer_ledgers = portal_ledgers(request)
```

> Delete `_find_customer_by_mobile` / `_find_all_customer_ledgers` once no callers remain (grep first). Keep the response key names (`ledger_name` etc.) as they already are; adjust the test's key if the real key differs.

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_auth_flow.C2LeakTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/portal_views.py backend/goldscheme/tests/test_portal_auth_flow.py
git commit -m "fix(portal): scope all data views to account.linked_ledgers (closes C2 leak)"
```

---

### Task C8: Frontend — userid login (email/phone), OTP + password modes, set-password screen

**Files:**
- Modify: `frontend/src/portal/api/portalApiService.js`, `frontend/src/portal/pages/PortalLogin.jsx`
- Create: `frontend/src/portal/pages/PortalSetPassword.jsx`
- Modify: portal router (where portal routes are registered)

- [ ] **Step 1: Update the API service**

```javascript
// frontend/src/portal/api/portalApiService.js — replace the auth calls:
export function portalRequestOtp({ userid }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/request-otp/", { userid }));
}
export function portalVerifyOtp({ userid, otp }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/verify-otp/", { userid, otp }));
}
export function portalPasswordLogin({ userid, password }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/login/", { userid, password }));
}
export function portalSetPassword({ userid, otp, new_password }) {
  return wrap(portalApiClient.post("/goldscheme/api/portal/set-password/", { userid, otp, new_password }));
}
```

- [ ] **Step 2: Rework `PortalLogin.jsx`**

Replace the mobile field with a `userid` field (label "Email or phone"), and add a mode toggle: "Login with password" vs "Login with email OTP". Password mode calls `portalPasswordLogin`; OTP mode calls `portalRequestOtp` then `portalVerifyOtp`. On success store the returned `token` exactly as today. Add a "First time / forgot password?" link routing to `/portal/set-password`.

```javascript
// key handler shapes (adapt to existing component state/JSX):
const doPasswordLogin = async () => {
  const res = await portalPasswordLogin({ userid, password });
  if (res.token) { saveToken(res.token); navigate("/portal/dashboard"); }
  else setError(res.error || "Login failed");
};
const requestOtp = async () => {
  const res = await portalRequestOtp({ userid });
  if (res.success) setStep(2); else setError(res.error || "Could not send OTP");
};
const verifyOtp = async () => {
  const res = await portalVerifyOtp({ userid, otp });
  if (res.token) { saveToken(res.token); navigate("/portal/dashboard"); }
  else setError(res.error || "Invalid OTP");
};
```

- [ ] **Step 3: Create `PortalSetPassword.jsx`**

A three-field flow: enter `userid` → request OTP (`portalRequestOtp`) → enter OTP + new password → `portalSetPassword`. On success, redirect to `/portal/login` with a "Password set — please log in" message. Register the route `/portal/set-password` in the portal router (public, outside the auth guard).

- [ ] **Step 4: Verify build**

Run: `cd frontend && npm run build`
Expected: build succeeds, no unresolved imports.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/portal
git commit -m "feat(portal): email/phone login, OTP+password modes, set-password screen"
```

---

## Phase D — Portal Data Fixes

### Task D1: M2 — `portal_customer_orders` uses account ledgers + real auth classes

**Files:**
- Modify: `backend/sales/views/quotations.py` (~line 200-222)
- Test: `backend/goldscheme/tests/test_portal_data_fixes.py`

- [ ] **Step 1: Failing test**

```python
# backend/goldscheme/tests/test_portal_data_fixes.py
from django.test import TestCase
from rest_framework.test import APIClient
from mastersconfig.models import RetailMaster
from contacts.models import Ledger
from goldscheme.models import CustomerPortalAccount, CustomerPortalToken


class OrdersScopingTest(TestCase):
    def test_orders_endpoint_authorized_and_scoped(self):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RO")
        led = Ledger.objects.create(ac_name="C", retail_code=retail)
        acc = CustomerPortalAccount.objects.create(primary_email="o@x.com")
        acc.linked_ledgers.add(led)
        token = CustomerPortalToken.objects.create(account=acc, retail=retail)
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"PortalToken {token.token}")
        resp = c.get("/sales/api/portal/orders/")   # adjust to the real route
        self.assertEqual(resp.status_code, 200)

    def test_orders_endpoint_rejects_no_token(self):
        c = APIClient()
        resp = c.get("/sales/api/portal/orders/")
        self.assertEqual(resp.status_code, 401)
```

> Confirm the real route path for `portal_customer_orders` in `sales/urls.py` and update both requests.

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_data_fixes.OrdersScopingTest --noinput`
Expected: FAIL — endpoint uses hand-rolled auth, wrong scoping / no 401

- [ ] **Step 3: Convert to DRF auth + account scoping**

```python
# backend/sales/views/quotations.py — replace the manual auth block in
# portal_customer_orders with proper DRF decorators and account scoping:
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from goldscheme.portal_auth import PortalTokenAuthentication, IsPortalAuthenticated, portal_ledgers

@api_view(["GET"])
@authentication_classes([PortalTokenAuthentication])
@permission_classes([IsPortalAuthenticated])
def portal_customer_orders(request):
    ledgers = portal_ledgers(request)
    orders = CustomerOrder.objects.filter(ldgr__in=ledgers).order_by("-id")
    # ... keep existing serialization of `orders` ...
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_data_fixes.OrdersScopingTest --noinput`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/sales/views/quotations.py backend/goldscheme/tests/test_portal_data_fixes.py
git commit -m "fix(portal): orders endpoint uses account ledgers + DRF auth (M2)"
```

---

### Task D2: M3 — cap single payment at remaining scheme value when `max_amount` is null

**Files:**
- Modify: `backend/goldscheme/services/payment.py` (`validate_payment`, ~line 13-30)
- Test: `backend/goldscheme/tests/test_portal_data_fixes.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_data_fixes.py — build minimal scheme+enrollment; adjust
# required fields to your models. Assert an over-cap payment is rejected.
from goldscheme.services.payment import validate_payment

class PaymentCapTest(TestCase):
    def test_payment_above_remaining_value_rejected_when_no_max(self):
        enrollment = self._make_enrollment(tenure_months=11, installment_amount=1000,
                                            payments_made=10, max_amount=None)
        errors = validate_payment(enrollment, amount=5000)  # remaining = 1 * 1000
        self.assertTrue(any("remaining" in e.lower() or "exceeds" in e.lower() for e in errors))

    # _make_enrollment: create Scheme + SchemeEnrollment with the given fields.
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_data_fixes.PaymentCapTest --noinput`
Expected: FAIL — no remaining-value cap

- [ ] **Step 3: Add the cap in `validate_payment`**

```python
# backend/goldscheme/services/payment.py — inside validate_payment, after the max_amount check:
    if scheme.max_amount and amount > scheme.max_amount:
        errors.append(f"Payment ₹{amount} exceeds maximum ₹{scheme.max_amount}.")
    elif not scheme.max_amount and scheme.scheme_type != 'LUMPSUM':
        remaining_value = scheme.installment_amount * enrollment.remaining_installments
        if remaining_value and amount > remaining_value:
            errors.append(
                f"Payment ₹{amount} exceeds the remaining scheme value ₹{remaining_value}.")
```

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_data_fixes.PaymentCapTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/services/payment.py backend/goldscheme/tests/test_portal_data_fixes.py
git commit -m "fix(portal): cap payment at remaining scheme value when max_amount null (M3)"
```

---

### Task D3: M4 — remove maturity mutation from dashboard GET + kill N+1

**Files:**
- Modify: `backend/goldscheme/portal_views.py` (`PortalDashboardView.get`, ~line 251-263)
- Test: `backend/goldscheme/tests/test_portal_data_fixes.py`

- [ ] **Step 1: Failing test**

```python
# append to test_portal_data_fixes.py
from unittest.mock import patch

class DashboardNoWriteTest(TestCase):
    @patch("goldscheme.portal_views.check_and_update_maturity")
    def test_dashboard_get_does_not_mutate_maturity(self, mock_maturity):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RD")
        led = Ledger.objects.create(ac_name="C", retail_code=retail)
        acc = CustomerPortalAccount.objects.create(primary_email="d@x.com")
        acc.linked_ledgers.add(led)
        token = CustomerPortalToken.objects.create(account=acc, retail=retail)
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"PortalToken {token.token}")
        resp = c.get("/goldscheme/api/portal/dashboard/")
        self.assertEqual(resp.status_code, 200)
        mock_maturity.assert_not_called()  # M4: no writes on GET
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_data_fixes.DashboardNoWriteTest --noinput`
Expected: FAIL — GET still calls `check_and_update_maturity`

- [ ] **Step 3: Remove the write loop; prefetch benefits**

```python
# backend/goldscheme/portal_views.py — in PortalDashboardView.get, delete the
# loop that calls check_and_update_maturity(e). Maturity is already updated by
# the maturity job / on write. Prefetch to avoid N+1:
        enrollments = SchemeEnrollment.objects.filter(
            customer__in=customer_ledgers
        ).select_related('scheme', 'customer').order_by('-id')
        # (removed: for e in enrollments.filter(status='ACTIVE'): check_and_update_maturity(e))
```

> If `get_applicable_benefits(e)` issues per-enrollment queries, batch it or accept it for now with a comment; the primary M4 fix is removing writes on GET. Keep the existing response shape.

- [ ] **Step 4: Run test**

Run: `cd backend && python manage.py test goldscheme.tests.test_portal_data_fixes.DashboardNoWriteTest --noinput`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/goldscheme/portal_views.py backend/goldscheme/tests/test_portal_data_fixes.py
git commit -m "fix(portal): dashboard GET no longer mutates maturity; prefetch (M4)"
```

---

## Final verification

- [ ] **Run each test module one at a time** (project convention — shared in-memory DB hangs if batched):

```bash
cd backend
python manage.py test mastersconfig.tests.test_email --noinput
python manage.py test goldscheme.tests.test_portal_identity --noinput
python manage.py test goldscheme.tests.test_portal_auth_flow --noinput
python manage.py test goldscheme.tests.test_portal_data_fixes --noinput
```

- [ ] **Run the bootstrap on real data (dry run first):**

```bash
cd backend && python manage.py seed_portal_accounts        # dry run, rolls back
cd backend && python manage.py seed_portal_accounts --apply
```

- [ ] **Frontend build:** `cd frontend && npm run build`
- [ ] **Django system check:** `cd backend && python manage.py check`
- [ ] **Manual smoke (with a real EmailSettings row + running worker):** request OTP by email → receive → verify → dashboard shows only linked ledgers → set/change password.

---

## Notes carried from the spec

- **Field-name confirmations before coding:** `Ledger` email field (`email`?), `Ledger`→retail FK name (`retail_code`), `SchemeEnrollment.customer` FK name, `CustomerOrder.ldgr` field, and the real route paths in `goldscheme/urls.py` and `sales/urls.py`. Each task flags where to confirm.
- **Out of scope (later pieces):** auto-send bills invoice hook (reads `EmailSettings.auto_send_bills`), PhonePe/Paytm gateway, portal feature expansion.
- **Legacy cleanup:** once C7 lands and greps show no callers, delete `_find_customer_by_mobile` / `_find_all_customer_ledgers` and the legacy `mobile`/`ledger` reliance on the token.
