# Hardcode Audit Report — Jewel India ERP Backend

> **Scope:** All Django apps under `d:\jewel-india-erp-main\backend\`
> **Apps Analysed:** `accounting`, `ai_layer`, `audit`, `carryforward`, `common`, `contacts`, `goldrates`, `goldscheme`, `hr`, `inventory`, `jewel_test`, `licensing`, `manufacturing`, `mastersconfig`, `purchase`, `sales`, `userauth`, `vendor_analytics`

---

##  Executive Summary

| Category | Severity | Count |
|---|---|---|
| Country / Region assumptions (India-only hardcodes) |  High | 6 |
| Third-party API versions & external URLs |  Medium | 3 |
| Statutory / payroll rates (PF, ESI, PT) |  Medium | 5 |
| Security & session limits |  Medium | 4 |
| App-identity strings |  Low | 2 |
| Configuration defaults in `settings.py` |  Low / Acceptable | 7 |
| Domain-specific constants (business logic) | ℹ Info | Many |

---

##  HIGH — India-Specific Hardcodes (Country/Region Assumptions)

> [!CAUTION]
> These are the most critical findings because they make the application **non-portable** to any other country or even to international customers of Indian retailers.

---

### 1. WhatsApp Country Prefix `91` Hardcoded in 5 Places

**Files & Lines:**

| File | Line | Code |
|---|---|---|
| `contacts/views.py:631` | 631 | `f"https://wa.me/91{mobile}?text=..."` |
| `contacts/whatsapp_sender.py:49` | 49 | `"to": f"91{mobile}"` (Meta Cloud API) |
| `contacts/whatsapp_sender.py:80` | 80 | `f"...whatsappNumber=91{mobile}"` (WATI) |
| `contacts/whatsapp_sender.py:108` | 108 | `"destination": f"91{mobile}"` (AiSensy) |
| `contacts/whatsapp_sender.py:139` | 139 | `"to": f"91{mobile}"` (Webhook) |

**Impact:** All CRM WhatsApp messages and click-to-chat URLs permanently add India's country code (`+91`) to every mobile number, regardless of the customer's actual country.

**Recommendation:**

```python
# In RetailMaster or CompanyMaster, add:
default_country_code = models.CharField(max_length=5, default='91')

# Then use:
country_code = getattr(retail, 'default_country_code', '91')
f"91{mobile}"  →  f"{country_code}{mobile}"
```

> [!NOTE]
> `contacts/serializers.py:19` already has `default_country_code` in `AllowedRetailSerializer` — this value should be propagated to the WhatsApp sender.

---

### 2. Timezone Hardcoded to `Asia/Kolkata`

**Files & Lines:**

| File | Line | Code |
|---|---|---|
| `jewel_test/settings.py:268` | 268 | `TIME_ZONE = 'Asia/Kolkata'` |
| `mastersconfig/scheduler.py:24` | 24 | `BackgroundScheduler(timezone='Asia/Kolkata')` |

**Impact:** The scheduler always fires CRM messages on IST time even if `settings.py` `TIME_ZONE` is later changed.

**Recommendation:**

```python
# mastersconfig/scheduler.py
from django.conf import settings
_scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
```

---

### 3. Language Code Hardcoded to `en-us`

**File:** `jewel_test/settings.py:266`

```python
LANGUAGE_CODE = 'en-us'
```

**Impact:** Acceptable for now, but should be configurable via `.env` if multi-language support is ever needed.

---

### 4. Professional Tax (PT) Slabs Hardcoded for Karnataka Only

**File:** `hr/services.py:4-15`

```python
# Karnataka Professional Tax slabs (monthly gross)
PT_SLABS_KA = [
    (Decimal('15000'), Decimal('0')),
    (Decimal('9999999'), Decimal('200')),
]
```

**Impact:** PT slabs differ by Indian state (e.g. Karnataka: ₹200/month above ₹15k; Maharashtra: tiered; AP: different). Any retail in a different state will compute wrong PT.

**Recommendation:** Store PT slabs in a database table keyed by state, or allow `RetailMaster` to specify the applicable state's PT slab set.

---

### 5. ESI Ceiling, PF Ceiling, and PF Rate Are Hardcoded

**File:** `hr/services.py:57-73`

```python
pf_ceiling   = Decimal('15000')          # EPFO ceiling (hardcoded)
pf_employee  = pf_base * Decimal('0.12') # 12% PF rate (hardcoded)
pf_employer  = pf_employee               # employer contribution (hardcoded)

# ESI — only if gross ≤ 21000
esi_employee = gross_salary * Decimal('0.0075')   # 0.75% (hardcoded)
esi_employer = gross_salary * Decimal('0.0325')   # 3.25% (hardcoded)
esi_ceiling  = Decimal('21000')                   # ₹21,000/month (inline)
```

Also in `mastersconfig/management/commands/seed_demo_data.py:1387-1395`:

```python
min(emp_data["basic"] * D("0.12"), D("1800"))
```

**Impact:** When the government revises EPFO/ESIC rates or ceilings, all payroll calculations will be wrong until the code is updated and redeployed.

**Recommendation:** Move these to a `PayrollSettings` model or `HRSettings`, configurable per retail:

```python
class HRSettings(models.Model):
    pf_employee_rate  = models.DecimalField(default=Decimal('0.12'), ...)
    pf_ceiling        = models.DecimalField(default=Decimal('15000'), ...)
    esi_employee_rate = models.DecimalField(default=Decimal('0.0075'), ...)
    esi_employer_rate = models.DecimalField(default=Decimal('0.0325'), ...)
    esi_ceiling       = models.DecimalField(default=Decimal('21000'), ...)
```

---

### 6. Payroll Working Days Hardcoded to 26

**File:** `hr/services.py:42,89`

```python
pay_basis = Decimal('26')   # line 42
'working_days': 26,         # line 89 — returned in slip dict
```

**Impact:** Some companies use 30 or 31 days per month for salary proration. This is a business policy, not a law.

**Recommendation:** Add `working_days_basis` field to `SalaryStructure` or `HRSettings`.

---

##  MEDIUM — Third-Party API Versions & External URLs

---

### 7. Meta (Facebook) Graph API Version Hardcoded as `v20.0`

**File:** `contacts/whatsapp_sender.py:42`

```python
url = f"https://graph.facebook.com/v20.0/{settings.phone_number_id}/messages"
```

**Impact:** When Meta deprecates API v20.0 (typically 2 years after release), messages will silently fail.

**Recommendation:**

```python
# In CRMSettings model or settings.py:
META_API_VERSION = config('META_GRAPH_API_VERSION', default='v20.0')
url = f"https://graph.facebook.com/{META_API_VERSION}/{settings.phone_number_id}/messages"
```

---

### 8. AiSensy Campaign API URL Hardcoded

**File:** `contacts/whatsapp_sender.py:104`

```python
url = "https://backend.aisensy.com/campaign/t1/api/v2"
```

**Impact:** If AiSensy changes their API URL or version, this will break without a code change.

**Recommendation:** Move to settings or `CRMSettings` model as `aisensy_api_url`.

---

### 9. AiSensy Source Identifier Hardcoded as `"JEWEL_ERP"`

**File:** `contacts/whatsapp_sender.py:111`

```python
"source": "JEWEL_ERP",
```

**Impact:** For white-label or multi-product deployments, the source identifier should be configurable.

**Recommendation:**

```python
"source": getattr(django_settings, 'AISENSY_SOURCE_ID', 'JEWEL_ERP'),
```

---

##  MEDIUM — Security & Session Limits

---

### 10. OTP Expiry Hardcoded to 5 Minutes

**File:** `goldscheme/models.py:353`

```python
return timezone.now() > self.created_at + timedelta(minutes=5)
```

**Impact:** Not configurable. Some deployments may need a shorter (high-security) or longer (poor connectivity) window.

**Recommendation:** Add `OTP_EXPIRY_MINUTES = config('OTP_EXPIRY_MINUTES', default=5, cast=int)` to settings.

---

### 11. OTP Brute-Force Limit Hardcoded to 5 Attempts

**File:** `goldscheme/portal_views.py:157`

```python
if otp_record.attempts >= 5:
```

**Recommendation:** Make configurable via `OTP_MAX_ATTEMPTS = config('OTP_MAX_ATTEMPTS', default=5, cast=int)` in settings.

---

### 12. Portal Token Expiry Hardcoded to 24 Hours

**File:** `goldscheme/models.py:378`

```python
self.expires_at = timezone.now() + timedelta(hours=24)
```

**Impact:** Customer portal sessions always expire after exactly 24 hours. Some deployments may want shorter or longer sessions.

**Recommendation:** `PORTAL_TOKEN_EXPIRY_HOURS = config('PORTAL_TOKEN_EXPIRY_HOURS', default=24, cast=int)`

---

##  LOW — App-Identity Strings

---

### 13. Minimum Password Length Hardcoded to 8

**File:** `userauth/views.py:204`

```python
if len(new_password) < 8:
    return Response({'detail': 'New password must be at least 8 characters.'}, status=400)
```

**Impact:** Django's `AUTH_PASSWORD_VALIDATORS` already enforces `MinimumLengthValidator` (configurable in `settings.py`), but this view does a secondary inline check with a hardcoded `8`. These can diverge if the settings validator is changed.

**Recommendation:** Remove the inline check and rely solely on Django's validators, or read from settings:

```python
from django.conf import settings
min_len = next(
    (v.get('OPTIONS', {}).get('min_length', 8)
     for v in settings.AUTH_PASSWORD_VALIDATORS
     if 'MinimumLength' in v['NAME']),
    8
)
```

---

### 14. Login-Log Page Size Hardcoded to 50

**File:** `userauth/views.py:667` and `audit/views.py:233`

```python
page_size = 50
```

**Impact:** Inconsistent with the global `PAGE_SIZE = 10` in `settings.py` REST_FRAMEWORK config. Should use the framework pagination or a shared constant.

---

### 15. Backup Filename Prefix Hardcoded as `jewel_erp_backup`

**File:** `userauth/views.py:470`

```python
backup_filename = f'jewel_erp_backup_{timestamp}.sqlite3'
```

**Impact:** Minor — cosmetic. For white-label deployments the backup filename should reflect the client's brand.

**Recommendation:** `APP_NAME = config('APP_NAME', default='jewel_erp')`

---

### 16. AI Model Defaults in `settings.py`

**File:** `jewel_test/settings.py:100-101`

```python
AI_NL_MODEL     = config('AI_NL_MODEL',     default='gpt-4o-mini')
AI_VISION_MODEL = config('AI_VISION_MODEL', default='gpt-4o')
```

> [!NOTE]
>  **Acceptable** — both values are already env-var driven. The `default=` values are safe fallbacks, not hardcodes in the problematic sense. No action required unless the defaults should be removed entirely.

---

## ℹ INFO — Acceptable / By-Design Constants

The following items were inspected and are **not** problematic hardcodes — they are domain constants, fixed business rules, or properly env-var-backed settings.

| File | Value | Reason Acceptable |
|---|---|---|
| `global_vars.py` | `STATES_OF_INDIA` list | Static reference data for India-specific ERP |
| `global_vars.py` | `CUSTOMER_TYPE` / `VoucherType` | Business domain constants — correct pattern |
| `mastersconfig/signals.py` | `_GST_REGISTERS`, `_OPERATIONAL_LEDGERS`, `_TRADING_LEDGERS`, `_MISC_LEDGERS` | Seed data for ledger auto-creation — must be in code |
| `jewel_test/settings.py` | `SECRET_KEY`, `DEBUG`, `DATABASES`, `REDIS_URL` | All properly loaded via `config()` / `.env` |
| `jewel_test/settings.py` | `MYSQL_SYNC_CONFIG` defaults (`127.0.0.1`, `root`) | Dev-only defaults, overridden in prod via `.env` |
| `jewel_test/settings.py` | `AUDIT_RETENTION` timedeltas | Reasonable defaults for audit log retention |
| `contacts/views.py` | `FA_ASSET_GROUP_CODES`, `_IT_BLOCK_TO_FA_GROUP` | Fixed asset classification codes — correct as constants |
| `contacts/views.py` | `PER_RETAIL_GROUP_CODES = {'CA-CSH', 'CA-BNK', 'CA-BNK-OD'}` | Account group codes — internal constants |
| `contacts/views.py` | `_SAMPLE_ROWS` (CSV upload sample data) | Template rows for CSV download — correct as code constants |
| `contacts/models.py` | `TYPE_CHOICES` / `PARTY_TYPES` / `NON_PERSONAL_TYPES` | Domain enums — correct pattern |
| `mastersconfig/views.py` | `fallback.get('host', '127.0.0.1')` | Dev-only fallback inside MySQL sync, overridden by UI/env |
| `goldscheme/models.py` | `SchemeMaster.tenure_months = 11` | Model field default — changeable per scheme |
| `ai_layer/views.py` | `MAX_FILE_SIZE = 10 * 1024 * 1024` | Clearly named constant — acceptable |
| `licensing/middleware.py` | `EXEMPT_PREFIXES` | Fixed URL routing rules — correct pattern |

---

##  Summary Table — All Findings

| # | App | File | Description | Severity |
|---|---|---|---|---|
| 1 | contacts | `views.py:631` + `whatsapp_sender.py:49,80,108,139` | India `+91` prefix hardcoded in 5 places |  High |
| 2 | mastersconfig, jewel_test | `scheduler.py:24`, `settings.py:268` | `Asia/Kolkata` timezone duplicated in scheduler |  Medium |
| 3 | jewel_test | `settings.py:266` | `LANGUAGE_CODE = 'en-us'` not env-backed |  Low |
| 4 | hr | `services.py:4-15` | Karnataka PT slabs only — other states wrong |  High |
| 5 | hr | `services.py:60-73` | PF/ESI rates & ceilings (12%, 0.75%, 0.0325%, ₹15k, ₹21k) |  High |
| 6 | hr | `services.py:42,89` | Working days basis = 26 (non-configurable) |  Medium |
| 7 | contacts | `whatsapp_sender.py:42` | Meta Graph API `v20.0` hardcoded |  Medium |
| 8 | contacts | `whatsapp_sender.py:104` | AiSensy API URL hardcoded |  Medium |
| 9 | contacts | `whatsapp_sender.py:111` | AiSensy `source` = `"JEWEL_ERP"` hardcoded |  Low |
| 10 | goldscheme | `models.py:353` | OTP expiry = 5 min (non-configurable) |  Medium |
| 11 | goldscheme | `portal_views.py:157` | OTP max attempts = 5 (non-configurable) |  Medium |
| 12 | goldscheme | `models.py:378` | Portal token expiry = 24 hrs (non-configurable) | Medium |
| 13 | userauth | `views.py:204` | Min password length = 8 (duplicates validator) | Low |
| 14 | userauth, audit | `views.py:667`, `audit/views.py:233` | Login log / audit page_size = 50 (bypasses pagination settings) |  Low |
| 15 | userauth | `views.py:470` | Backup filename prefix `jewel_erp_backup` |  Low |
| 16 | jewel_test | `settings.py:100-101` | AI model names — acceptable with env-var defaults |  OK |

---

##  Recommended Action Plan

###  Immediate (Before Production)

> [!IMPORTANT]
> These fixes are critical and should be addressed before any production deployment.

1. **Fix WhatsApp country code (Finding #1)** — Read `default_country_code` from `RetailMaster` (already exists in the model) and use it in all 5 places in `whatsapp_sender.py` and `views.py`.

2. **Fix HR payroll rates (Findings #4, #5, #6)** — Add `pf_employee_rate`, `pf_ceiling`, `esi_employee_rate`, `esi_employer_rate`, `esi_ceiling`, `working_days_basis` to `HRSettings` model. Seed defaults matching current values so existing behaviour is unchanged.

3. **Fix scheduler timezone (Finding #2)** — Replace `'Asia/Kolkata'` literal in `scheduler.py` with `settings.TIME_ZONE`.

---

###  Short-term (Next Sprint)

4. **Parameterise Meta API version (Finding #7)** — Add `META_GRAPH_API_VERSION` to env/settings.

5. **Parameterise AiSensy URL & source (Findings #8, #9)** — Add `aisensy_api_url` to `CRMSettings` model.

6. **Portal security settings (Findings #10, #11, #12)** — Add `OTP_EXPIRY_MINUTES`, `OTP_MAX_ATTEMPTS`, `PORTAL_TOKEN_EXPIRY_HOURS` to `settings.py` backed by env vars.

---

###  Nice-to-Have

7. Remove duplicate password length check (Finding #13).
8. Align log page sizes with DRF pagination settings (Finding #14).
9. Make backup filename prefix configurable (Finding #15).


