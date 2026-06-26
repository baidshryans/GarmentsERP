# Multi-Country & Multi-Currency — Scalability Plan (Design Only)

> **Status: PLAN / NOT BUILT.** This document scopes what it would take to make Jewel India ERP work across countries, currencies, and tax regimes. It is a roadmap to inform a future build decision — no code here should be implemented until explicitly prioritised.

---

## 1. Goal

Today the ERP is **single-country (India), single-currency (INR), single-tax-regime (GST)**. The target end-state:

- A retail/company can be configured for **any country**, with that country's address shape, phone format, fiscal calendar, and number formatting.
- Transactions can be recorded and reported in **one or more currencies**, with exchange-rate handling.
- The tax engine is **pluggable** — GST is one implementation; VAT (UAE/EU), US sales tax, etc. are others.
- Gold/metal rates are **currency-aware** and unit-aware (g / tola / oz).

This is a large, multi-phase effort. The realistic strategy is **incremental**: make the system *configurable* first (country/locale/FY), then *currency-aware*, then *tax-pluggable* last (the hardest).

---

## 2. Current-State Assessment (where India/INR/GST is baked in)

A full reconnaissance was done across backend (Django) and frontend (React). Summary of coupling, hardest → easiest:

| Area | Where it lives | Coupling | Notes |
|------|----------------|----------|-------|
| **Tax = GST** | `mastersconfig` `Hsn` (cgst/sgst/igst), `GSTINMaster`, tax signals auto-creating 6 GST ledgers, GSTR1/2B/3B reports, sales/purchase serializers compute CGST/SGST/IGST as `@property` | **Very Hard** | GST is a first-class citizen across models, signals, serializers, and reports. The single biggest blocker. |
| **Amounts have no currency** | All money is `DecimalField(max_digits=15, decimal_places=2)` in `accounting`, `sales`, `purchase`, `goldscheme`, `goldrates`. No currency column anywhere. | **Hard** | Schema evolution required to carry currency + rate per transaction. |
| **Currency formatting** | ~322 frontend occurrences of `toLocaleString("en-IN", …)` and hardcoded `₹` (esp. print templates in `services/print/*`). | **Hard (volume)** | Mechanically simple but spread across the whole UI; needs a central formatter. |
| **Gold rate = INR/gram** | `goldrates/models.py` `rate` is `IntegerField`, implicit INR-per-gram; print shows `₹ … / gm`. | **Hard** | No currency or unit abstraction; no FX. |
| **Country/locale** | `STATES_OF_INDIA` (36 states) in `global_vars.py`, `State` FK pervasive; `pincode` (India shape); `+91` hardcoded in 5 WhatsApp senders; DD/MM/YYYY date parsing. | **Medium–Hard** | State FK is everywhere; phone code is a quick win (field already exists, unused). |
| **Fiscal year (Apr–Mar)** | `FiscalYearMaster` already stores explicit `fy_start`/`fy_end` per retail (good!). Hardcoded April-1 only in *fallback* paths: `accounting/fine_gold_service.py`, `accounting/views/reports.py:1421`, `ai_layer/services/nl_query.py`. | **Easy–Medium** | Mostly already configurable; only fallbacks assume Apr 1. |
| **Number naming (lakh/crore)** | No lakh/crore *words* are emitted — `en-IN` only does digit grouping (`2,00,000`). A few literal strings exist. | **Medium** | Just locale grouping; central formatter solves it. |

### Config infrastructure that already exists (build on this)
- **Singleton/per-retail settings pattern** is established: `SystemSettings` (server-wide), `HRSettings` (per-retail, already holds configurable statutory rates), `CRMSettings` (per-retail).
- **`FiscalYearMaster`** is already per-retail with explicit start/end dates.
- **`RetailMaster.default_country_code`** field already exists in the serializer but is **not used** by the WhatsApp senders — a propagation gap, not a missing field.
- **`backend/hardcode_audit_report.md`** already catalogues 16 hardcode findings (incl. `+91`, `Asia/Kolkata` timezone, Meta API version). This is a ready-made quick-win backlog.

---

## 3. Target Architecture

### 3.1 New core models (backend)

```
Country
  code (ISO 3166-1 alpha-2)        e.g. IN, AE, US, GB
  name
  default_currency  -> Currency
  phone_dial_code                  e.g. 91, 971, 1
  address_schema (json)            which fields + labels + validation (pincode vs zip)
  date_format                      e.g. DD/MM/YYYY
  number_grouping                  'indian' (lakh) | 'western' (thousand)
  fiscal_year_start_month (1-12)   India=4, calendar=1
  tax_regime -> TaxRegime

Currency
  code (ISO 4217)                  INR, AED, USD, GBP
  symbol                           ₹, د.إ, $, £
  decimal_places                   2 (3 for some)
  symbol_position                  prefix | suffix

ExchangeRate
  from_currency -> Currency
  to_currency   -> Currency
  rate (Decimal)
  as_of_date
  (unique: from, to, as_of_date)

Region / SubDivision   (generalises the India-only `State`)
  country -> Country
  code, name
  # GST place-of-supply logic becomes a regime-specific concern
```

`RetailMaster` gains: `country -> Country`, `base_currency -> Currency` (a.k.a. *functional/reporting currency*).

### 3.2 Tax engine (the hard part) — strategy pattern

Replace the hardwired GST computation with a **TaxRegime abstraction**:

```
TaxRegime (abstract / registry)
  - name                          'IN_GST', 'AE_VAT', 'US_SALES_TAX', 'NONE'
  - compute_tax(line, parties) -> [ {component, rate, amount}, … ]
  - ledger_accounts()  -> which tax ledgers to auto-create
  - report_definitions() -> which statutory reports apply
```

- **IN_GST** implementation wraps the existing `Hsn` cgst/sgst/igst logic + the 6-ledger signal + GSTR1/2B/3B — i.e. today's behaviour, refactored behind the interface. *Nothing changes for existing Indian retails.*
- **AE_VAT** / **EU_VAT**: single-rate VAT, one input + one output ledger, VAT-return report.
- **US_SALES_TAX**: destination-based, origin/nexus rules (likely defer / integrate a 3rd-party rate service like TaxJar/Avalara).
- Tax **components** stored per transaction line as rows (not fixed cgst/sgst/igst columns), so any regime fits.

This is deliberately the **last** phase — it touches sales, purchase, accounting, signals, and every statutory report.

### 3.3 Money handling

Two viable approaches — recommend **(B)**:

- **(A) Transaction-currency + reporting-currency on every row.** Add `currency` + `fx_rate_to_base` to each monetary document header; store both original and base-currency amounts. Most correct, heaviest migration.
- **(B) Phase it:** First make the *base/reporting* currency configurable per retail (single-currency-per-company, just not hardcoded INR). This unlocks "ERP runs in AED for a Dubai store" with **minimal schema change** (mostly formatting + a `Currency` FK on `RetailMaster`). *Then* later add true multi-currency transactions (foreign-currency invoices, FX gain/loss) for businesses that need it.

Most jewellery retailers operate in one currency per location, so **(B)** delivers 90% of the value for 20% of the risk.

### 3.4 Frontend formatting

- Introduce a single `useMoney()` / `formatMoney(value, { currency, locale })` helper and a `CurrencyContext` seeded from the active retail's country/currency.
- Replace the ~322 ad-hoc `toLocaleString("en-IN")` / `₹` usages with the helper (mechanical, scriptable codemod).
- Print/PDF templates (`services/print/*`) take currency symbol + locale from context instead of literal `₹`.
- A `formatDate()` helper driven by `country.date_format`.

---

## 4. Phased Roadmap

Ordered by value-to-risk. Each phase is independently shippable and leaves the system working for India throughout.

### Phase 0 — Quick wins / de-hardcode (low risk, ~1 week)
*Drains the existing `hardcode_audit_report.md` backlog. No behaviour change for India.*
- Use `RetailMaster.default_country_code` in all 5 WhatsApp senders instead of literal `91`.
- Parameterise scheduler timezone (`Asia/Kolkata` → `settings.TIME_ZONE`).
- Move Meta API version / provider URLs to settings.
- Centralise the April-1 fiscal fallbacks to read from `FiscalYearMaster`.

### Phase 1 — Locale & formatting layer (frontend-heavy, medium)
- Add `Currency` + `Country` models (seed IN/INR; no FK enforcement yet).
- Build `formatMoney` / `formatDate` helpers + `CurrencyContext`.
- Codemod the ~322 frontend currency sites + print templates to use the helper. India output stays identical (`₹`, en-IN).
- **Outcome:** UI is currency-symbol/locale-driven, not hardcoded — even though there's still only INR.

### Phase 2 — Configurable base currency & country per retail (medium)
- `RetailMaster.country` + `RetailMaster.base_currency`.
- Generalise `State` → `Region(country)`; keep Indian states as seed data.
- Address-shape + phone-format + number-grouping driven by `Country`.
- FY start month from `Country.fiscal_year_start_month` (defaults Apr for IN, Jan elsewhere).
- **Outcome:** A non-India store can run end-to-end in its own currency/locale **if** it doesn't need GST-style tax. Gold rate now carries a currency.

### Phase 3 — Pluggable tax engine (large, highest risk)
- Extract `TaxRegime` interface; refactor existing GST into `IN_GST` behind it (regression-test heavily against current invoices/GSTR reports).
- Move tax from fixed cgst/sgst/igst columns to per-line tax-component rows.
- Implement at least one second regime (recommend `AE_VAT` or a simple single-rate VAT) as proof.
- Make statutory reports regime-scoped (GSTR* only show for IN_GST).

**Decomposition & timing (decided 2026-06-26):** Phase 3 splits into **3a** and **3b/3c**, which age differently:
- **3a — TaxRegime abstraction + GST golden regression net (do near-term).** Centralise today's GST math behind a `TaxRegime` interface (`IN_GST` only) *behind the existing cgst/sgst/igst columns* — no schema change, no data migration, behaviour-preserving. Plus golden-file fixtures snapshotting current invoice + GSTR-1/2B/3B output. This is cheap insurance that gets *more* expensive the longer it waits (the GST logic accretes edge cases/reports over time), and it carries near-zero risk. Worth doing while GST behaviour is well-understood.
- **3b/3c — component-row storage + 2nd regime (defer until a concrete non-GST market exists).** Moving tax to per-line component rows is the schema change that requires a data migration. The migration is a **deterministic 1:1 backfill** (each line's cgst/sgst/igst_per → up to 3 component rows; run on staging, assert per-invoice totals vs the 3a golden snapshots, then prod) and historical invoices are immutable — *or* avoid historical backfill entirely with **dual-read** (old/IN_GST invoices stay on columns, new regimes use rows; additive). So waiting does **not** create a scary migration — volume makes it slower, not riskier. Build only when a real second-tax-regime company (e.g. UAE VAT) is on the horizon; tax regime is a company-level attribute (pairs with company-level base_currency from Phase 2).
- **Outcome:** ERP supports a second tax regime; GST untouched for Indian clients.

### Phase 4 — True multi-currency transactions (optional, demand-driven)
- Foreign-currency invoices/purchases with `ExchangeRate`, base-currency posting, FX revaluation, and realised/unrealised FX gain-loss ledgers.
- Multi-currency gold rate (rate per currency, or convert via FX).
- **Outcome:** A single company can transact in multiple currencies. Only build if a real customer needs it.

---

## 5. Effort & Sequencing Notes

- **Do not start with tax.** Phases 0–2 deliver a genuinely multi-country-*capable* product (for VAT-free or simple-tax markets) at modest risk. Phase 3 is where the cost concentrates.
- **Regression safety net first.** Before Phase 3, lock in golden-file tests for current GST invoices and GSTR1/2B/3B output — the refactor must be provably behaviour-preserving for India.
- **Migrations are additive.** Every new model/column should be nullable with India-equivalent defaults so existing data and the running Indian deployment are never broken.
- **Gold/metal units** (g vs tola vs oz) ride along with Phase 2's country config — add a `weight_unit` to country/retail and a conversion helper.

---

## 6. Out of Scope (for this plan)
- Language/i18n translation of the UI (separate effort; can layer on later).
- Country-specific statutory *filing* integrations (e-invoicing portals, VAT e-filing) beyond report generation.
- Per-country chart-of-accounts templates (worth considering during Phase 2 but not required).

---

*Prepared as a scoping document. Recommend revisiting before any build kickoff to confirm which target markets/currencies are actually in demand — that decides how far down Phases 3–4 are worth going.*
