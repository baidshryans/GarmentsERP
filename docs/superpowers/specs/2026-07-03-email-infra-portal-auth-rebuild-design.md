# Email Infrastructure + Portal Auth/Authz Rebuild — Design

**Date:** 2026-07-03
**Status:** Approved (design), pending implementation plan
**Author:** Brainstormed with baidshryans

## Context

The Jewel India ERP customer portal (`backend/goldscheme/portal_*.py`,
`frontend/src/portal/*`) is a gold-scheme portal: customers log in and view/pay
scheme enrollments. A read-only audit (2026-07-03) confirmed it works in a
dev/demo sense but is **not production-safe or fully wired**. The user chose to
"fix everything now," and to deliver login OTPs by **email**. Because the OTP
fix depends on email, this build merges three roadmap pieces into one cohesive
subsystem:

1. Email infrastructure (was piece #1)
2. Portal auth rebuild — email-or-phone userid, email OTP (was piece #3)
3. Portal data + authorization fixes from the audit

### Audit findings addressed here

| # | Sev | Issue | Evidence |
|---|-----|-------|----------|
| C1 | Critical | OTP only `print()`ed to console; no delivery → login unusable in prod | `portal_views.py:115-117` |
| C2 | Critical | Authorization re-expands access by mobile (`mobile1/2/phone1`), ignoring the token's ledger → shared-phone cross-customer access | `portal_views.py:254,314,373` → `_find_all_customer_ledgers` |
| H2 | High | No rate limiting on `request-otp` → OTP bombing / brute-force | `PortalRequestOTPView`, `AllowAny` |
| H3 | High | `set-password` needs only mobile+OTP, no old password → account takeover | `portal_views.py:234-236` |
| H4 | High | OTP marked verified *before* password check → burns OTP on typo, dead rows | `portal_views.py:175-176` vs `184` |
| H6 | High | `portalSetPassword` API exists but no UI page calls it → onboarding dead-ends | verified no caller |
| M2 | Med | `portal_customer_orders` scopes to single ledger vs all-ledgers elsewhere | `sales/views/quotations.py:222` |
| M3 | Med | Scheme with null `max_amount` → single payment unbounded | `services/payment.py:26` |
| M4 | Med | Dashboard GET mutates (`check_and_update_maturity` loop) + N+1 | `portal_views.py:261-263` |
| L1 | Low | OTP uses `random.randint` (Mersenne Twister), not `secrets` | `portal_views.py:109` |

### Explicitly out of scope

- Auto-send bills invoice-save hook (next piece; only the `auto_send_bills`
  flag is created here).
- Payment gateway (PhonePe / Paytm).
- Portal feature *expansion* (invoices/statements/order-status pages).
- Gmail/Outlook OAuth2 — this build uses **SMTP + app passwords**.

## A. Email infrastructure (new foundation)

Mirrors the existing `CRMSettings` / `send_occasion_message` / `CRMSendLog`
pattern in `mastersconfig` + `contacts`.

### `EmailSettings` model (`mastersconfig/models.py`)
`OneToOneField(RetailMaster)`. Fields:

- `provider` — choices `gmail` | `outlook` | `custom_smtp`
- `host`, `port`, `use_tls` — auto-filled for gmail/outlook presets, editable for custom
- `username`, `password` — SMTP creds (app password for gmail/outlook)
- `from_email`, `from_name`
- `is_enabled` — master toggle for this retail's email
- `auto_send_bills` — **superadmin-only** toggle, **default `False`**. Created
  here; the invoice hook that reads it is a later piece.
- `last_run_status` — runtime status string

Presets: choosing `gmail` fills `smtp.gmail.com:587 TLS`; `outlook` fills
`smtp-mail.outlook.com:587 TLS`. Both documented as requiring 2FA + app password.

### `send_email(...)` async task (`contacts/tasks.py`, `@task`)
Signature: `send_email(retail_id, to_email, subject, body, purpose, html_body=None)`.
- Loads the retail's `EmailSettings`; if missing/`is_enabled=False`, logs a
  skipped `EmailSendLog` and returns.
- Builds a per-retail connection via
  `django.core.mail.get_connection(host, port, username, password, use_tls)`.
- Sends `EmailMultiAlternatives`; writes an `EmailSendLog` row (status
  `sent`/`failed`, `error_message` on failure).
- Raises a transient error for retry-able SMTP failures (mirrors
  `TransientSendError` in the CRM task).

### `EmailSendLog` model (`mastersconfig/models.py`)
`ForeignKey(RetailMaster)`, `to_email`, `subject`, `purpose`
(`otp` | `bill` | `statement` | `other`), `sent_at`, `status`
(`sent` | `failed` | `skipped`), `error_message`.

### Django settings
No global SMTP creds committed. A safe default `EMAIL_BACKEND`
(console in dev) stays for framework mail; portal/business email always goes
through per-retail `send_email`.

## B. Portal identity & authorization (fixes C2)

### `CustomerPortalAccount` model (`goldscheme/models.py`)
The login identity, replacing "mobile string = identity".

- `primary_email` — unique, the canonical userid + OTP destination
- `email_verified` — bool
- `phone` — optional; alternate userid for lookup only (OTP still goes to email)
- `password` — PBKDF2 via `make_password`/`check_password`
- `is_active`
- `linked_ledgers` — `ManyToManyField(Ledger)`. **Explicit, stored** set.

**Authorization rule:** every portal data query reads
`account.linked_ledgers.all()`. No query ever re-matches by live mobile. Shared
phone numbers can no longer expand access. This is the C2 fix.

### Token change
`CustomerPortalToken` gains `account = ForeignKey(CustomerPortalAccount)` and
stops relying on the stored `mobile` for scoping. Auth sets
`request.portal_account`; a helper `portal_ledgers(request)` returns
`request.portal_account.linked_ledgers.all()`.

### One-time bootstrap command (`goldscheme/management/commands/`)
`seed_portal_accounts` — for each existing `CustomerPortalCredential`, create a
`CustomerPortalAccount` (email from the ledger if present, else flagged for
admin), and link ledgers whose current mobile matches (the *old* expansion
logic, run once). Idempotent, `--apply` flag. After this, linkage is explicit
and admin-adjustable via Django admin.

## C. Portal auth flow rebuild (fixes C1, H2, H3, H4, H6, L1)

### Userid resolution
`request-otp` / `verify-otp` / password-login accept a `userid` that is either
an **email** (matches `primary_email`) or a **phone** (matches `phone`).
Resolved to a `CustomerPortalAccount`. OTP is **always** sent to
`account.primary_email`.

### Two login modes
1. **Password:** `userid` + `password` → verify → issue token.
2. **Email OTP:** `request-otp(userid)` → `send_email(purpose='otp')` to the
   account email → `verify-otp(userid, otp)` → issue token.

### OTP hardening
- Generated with `secrets.randbelow` (fixes L1).
- **Stored hashed** (`make_password`) not plaintext (fixes the plaintext part
  of C1/H1); compared with `check_password`.
- 5-minute expiry (existing).
- Per-record 5-attempt cap (existing).
- **Request throttling (fixes H2):** per-account cooldown (min 60s between
  `request-otp`) + hourly cap (e.g. 5/hour). Implemented via a timestamp check
  on the latest OTP row and/or DRF throttle scope.

### Consumption ordering (fixes H4)
Verify OTP/password correctness **before** any state change; mark verified and
delete the OTP only on full success. A wrong password no longer burns the OTP.

### set-password / password change (fixes H3)
- First-time set (no active credential): allowed via a valid, single-use OTP —
  acceptable because the OTP was delivered to a verified email.
- Password **change while logged in**: requires the current password.
- OTP is deleted immediately after a successful set (single use).

### Onboarding UI (fixes H6)
Add a "Set / reset password" screen in `frontend/src/portal/pages` wired to the
existing `portalSetPassword` API, and a first-time onboarding path so a customer
with no credential is routed to set one instead of hitting a 403 dead-end.

## D. Portal data fixes (M2, M3, M4)

- **M2:** `portal_customer_orders` uses `portal_ledgers(request)` (the account's
  linked ledgers) and standard `authentication_classes` /
  `permission_classes`, removing the hand-rolled auth + bare `except`.
- **M3:** cap a single scheme payment at the remaining scheme value even when
  `scheme.max_amount` is null (compute remaining from scheme target minus paid).
- **M4:** remove `check_and_update_maturity` from the dashboard GET (maturity is
  updated by the existing maturity job / on write); prefetch
  `get_applicable_benefits` inputs to eliminate the per-enrollment N+1.

## Testing

Django tests run **one at a time** with `--noinput` (shared in-memory DB hangs
otherwise — project convention).

- Email connection is built from `EmailSettings`; `send_email` writes correct
  `EmailSendLog` rows for sent / failed / skipped.
- OTP: hashed at rest, expires at 5 min, throttle blocks a 2nd request inside
  the cooldown, 5-attempt cap trips.
- **C2 regression test:** two ledgers sharing a phone → account A cannot read or
  pay against account B's enrollments.
- Password change requires the old password; first-time set works via OTP.
- **M3:** payment exceeding remaining scheme value is rejected when
  `max_amount` is null.

## Component boundaries

- **Email** (`EmailSettings`, `send_email`, `EmailSendLog`) — knows SMTP; knows
  nothing about the portal. Reusable by bills/statements later.
- **Portal identity** (`CustomerPortalAccount`, `linked_ledgers`, token,
  `portal_ledgers()`) — the single source of "who is this and what may they
  see."
- **Portal auth flow** (views/serializers) — orchestrates OTP/password using the
  two above; holds no scoping logic of its own.
- **Portal data views** — consume `portal_ledgers()`; no auth logic inline.
