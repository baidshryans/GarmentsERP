# Clear flow: rates, narrations, locations, checks, delete — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One rate list as the only place costs are set, plain-sentence journal entries, three visible locations per factory, default whole-number and sanity checks, a true newest-first Delete, and a lot page that reads as a diary.

**Architecture:**
- Rates move into `jobwork.LabourRate`, with `party=NULL` meaning In-house. Every rate lookup goes through `jobwork/services/rates.py`.
- Narrations come from one module, `ledger/services/narration.py`.
- Delete reuses each document's existing undo / cancel, then **purges** both the original rows and the reversal rows with `core/services/purge.py`. Balances are unchanged by the purge, because a posting and its reversal net to zero.
- Locations are looked up by kind, not name.

**Tech Stack:** Python 3.12, Django 5, django-simple-history, HTMX templates, pytest + pytest-django.

**Spec:** `docs/superpowers/specs/2026-10-19-clear-flow-costs-locations-design.md`

## Global Constraints

- Python: `.venv/Scripts/python.exe`. Run tests with `.venv/Scripts/python.exe -m pytest -p no:cacheprovider <path>`. Run the full suite with `-n auto`.
- Decimal only for money and quantity; never float.
- Database-neutral: no raw SQL, no `select_for_update`. Every posting and every delete runs in one `transaction.atomic()`.
- Factory scoping on the server: `assert_factory_access` / `for_user` querysets.
- Business logic lives in services, not views or `save()`.
- Words on screen:
  - **Rates** (the screen)
  - **In-house** (the "who" for own staff)
  - **Godown**, **Ready Goods**, **Rejects** (never "Seconds", "Main Godown" or "Dispatch")
  - **Delete**, **Keep it**
- Money (rates, amounts) is shown only to users with cost rights (`can_cost`). Production roles see pieces only (BR-15).
- Every task that changes a screen updates the matching section of `docs/SETUP_GUIDE.md`. That file is the in-app Help.
- Commit on `master`, one commit per task, named by story ID. End each message with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Visual checks run on a throwaway DB (`DJANGO_DB_PATH`), never `db.sqlite3`. Any change to `static/js` gets a real browser check.
- After every test that posts, the trial balance tallies and stock reconciles. Use the existing helpers the acceptance tests use.

## Review Focus

1. **Delete in the middle of a lot's life.** Deleting the newest step on lot A must succeed even when lot B posted later movements of the same trim at the same godown. Average value adjusts, and nothing on lot B changes. Test in Task 11.
2. **Missing in-house rate on old data.** A factory whose processes had ₹0 or no route-step rate must still be able to cut, move and pack after the migration, using the ₹0 In-house rates the migration created. Test in Task 2.
3. **Whole-number check vs fabric.** A fabric issue of 58.4 m and a trim in kg must still be accepted. Only count-unit materials and SKUs are refused fractions. Test in Task 8.
4. **Delete of a step whose voucher was settled.** A labour bill paid by a payment must refuse delete and name the payment. Deleting the payment, then the bill, must work. Test in Task 12.
5. **A rename by the owner.** After the owner renames "Godown" to "Store 1", cutting, receipts and packing still find it. Test in Task 6.

---

## Part A — Rates (spec section 1)

### Task 1: LabourRate covers In-house, per piece only

**Files:**
- Modify: `jobwork/models.py:20-80` (`LabourRate`; delete `LabourRateAddon`, `LabourRateSize`)
- Modify: `jobwork/services/rates.py`, `jobwork/admin.py:21`
- Create: `jobwork/migrations/00xx_inhouse_rates.py` (schema + data)
- Test: `tests/test_rates.py` (new)

**Interfaces:**
- Produces:
  - `rates.find_rate(who: Party | None, process: Process, on_date: date) -> LabourRate | None`. `who=None` means In-house.
  - `rates.rate_for(who, process, on_date) -> LabourRate`. Raises `rates.MissingRate(BusinessRuleError)`.
  - `rates.source_text(rate: LabourRate) -> str`. Returns `"rate from 1 Oct 2026"`.
  - `rates.save_rate(*, who, process, effective_from, rate, pay_basis=PayBasis.ACCEPTED) -> LabourRate`.
  - `rates.update_rate(rate, *, rate_value, effective_from, pay_basis) -> LabourRate` and `rates.delete_rate(rate)`. The in-use guard is added in Task 4.

**Model changes:**
- `party` becomes nullable.
- Remove `rate_type`, `flat_amount`, `rework_rate`.
- Rename `base_rate` → `rate`, with verbose name "Rate per piece". Zero is allowed; negative is not.
- Constraints:
  - `uniq_labour_rate_date` on (party, process, effective_from) with `condition=Q(party__isnull=False)`
  - `uniq_inhouse_rate_date` on (process, effective_from) with `condition=Q(party__isnull=True)`
  - `labour_rate_non_negative` (`rate >= 0`)
- `JobWorkChallan.rate_type` and `flat_amount` stay, for challans already issued as type D.

**Data migration** (runs before the fields are dropped; prints a report via `print()`):
- B → `rate = base_rate`. Add-ons are dropped.
- C → `rate = most common LabourRateSize.amount`.
- D → `is_active=False`, listed as "re-enter".

- [ ] **Step 1: Write failing tests**

```python
def test_inhouse_rate_found_with_who_none(process, day):
    r = rates.save_rate(who=None, process=process, effective_from=day, rate=D("1.50"))
    assert rates.rate_for(None, process, day) == r

def test_missing_rate_names_who_process_and_date(fabricator, process, day):
    with pytest.raises(rates.MissingRate, match=f"No rate for {fabricator.name} — {process.name} on {day:%d %b}. Add one on Rates."):
        rates.rate_for(fabricator, process, day)

def test_inhouse_missing_rate_message(process, day):
    with pytest.raises(rates.MissingRate, match=f"No rate for In-house — {process.name}"):
        rates.rate_for(None, process, day)

def test_later_rate_does_not_apply_before_its_date(fabricator, process, day):
    rates.save_rate(who=fabricator, process=process, effective_from=day, rate=D("12"))
    rates.save_rate(who=fabricator, process=process, effective_from=day + timedelta(days=5), rate=D("13"))
    assert rates.rate_for(fabricator, process, day + timedelta(days=4)).rate == D("12")

def test_zero_rate_allowed_negative_refused(process, day):
    rates.save_rate(who=None, process=process, effective_from=day, rate=D("0"))
    with pytest.raises(BusinessRuleError):
        rates.save_rate(who=None, process=process, effective_from=day + timedelta(days=1), rate=D("-1"))

def test_source_text(process):
    r = rates.save_rate(who=None, process=process, effective_from=date(2026, 10, 1), rate=D("1.50"))
    assert rates.source_text(r) == "rate from 1 Oct 2026"
```

- [ ] **Step 2:** Run `pytest tests/test_rates.py`. Expected: FAIL (`save_rate() got an unexpected keyword argument 'who'`).
- [ ] **Step 3:** Implement the model changes, the migration and the service functions above.
  - Delete `RateSpec` and `resolve`. Callers are fixed in Tasks 2–3.
  - Update `jobwork/admin.py` `list_display` to `("party", "process", "rate", "pay_basis", "effective_from", "is_active")`.
- [ ] **Step 4:** Run `pytest tests/test_rates.py`. Expected: PASS. Then `manage.py makemigrations --check` should report no changes.
- [ ] **Step 5:** Commit: `E8.3 one rate list: in-house rates, per piece only`.

### Task 2: Remove rates from routes and lots; migrate them; in-house work uses Rates

**Files:**
- Modify:
  - `masters/models.py:179` (drop `RouteStep.rate`)
  - `production/models.py:141-142` (drop `LotStep.rate`, `rework_rate`)
  - `masters/services/routes.py:28,46`, `masters/views.py:307` and the route template form
  - `production/services/orders.py:142`, `production/services/routes.py:113-127`, `production/views.py:288`, `templates/production/lot_detail.html` (rate inputs)
  - `production/services/cutting.py:170-173`, `production/services/bundles.py:285-295,455-465`
- Create: `production/migrations/00xx_rates_to_rate_list.py` (data then schema; depends on the Task 1 migration)
- Test: `tests/test_rates.py`, `tests/test_production.py`

**Interfaces:**
- Consumes: `rates.rate_for(None, process, date)`.
- Produces: `production.services.costing.inhouse_amount(step, pieces: int, date, *, rework: bool) -> tuple[Decimal, LabourRate]`. Returns amount 0 when `rework` is true; a reworked piece is never paid again. It raises `MissingRate` even for rework, so a missing rate is never silent. The callers pass the amount to today's `accrue_labour(amount=...)`; Task 3 changes that signature and updates these callers.

**Data migration:**
- For each Process used on any `RouteStep`: create an In-house rate at the most common `RouteStep.rate` (ties → the higher one). It is dated from the company's earliest `FinancialYear.start_date`, or `2000-01-01` if there is none.
- Every Process with no route-step rate gets a ₹0 In-house rate on the same date.
- For each subcontracted `LotStep` with a party and `rate > 0` whose (party, process) has no `LabourRate`: create one at `LotStep.rate`. Date it from that party + process's earliest challan date, else the FY start.
- Print conflicts: a process whose routes had more than one rate.

- [ ] **Step 1: Write failing tests**
  - `test_cutting_uses_inhouse_rate`: In-house Cutting rate ₹1.50; cut 240 pieces. The lot's LABOUR cost entry is ₹360.00.
  - `test_cutting_refused_without_inhouse_rate`: no In-house Cutting rate. `receive_cutting` raises `MissingRate`, and nothing is saved (no `CuttingEntry`, no `StockMovement`).
  - `test_rework_bundle_moving_on_accrues_nothing`: moving a rework bundle accrues ₹0 in-house labour.
  - `test_migration_creates_inhouse_and_zero_rates`: use `MigrationExecutor` to migrate back to before Tasks 1–2. Create two routes with Stitching at 10 and 10 and one at 12, a Packing step at 0, and a subcontracted LotStep (party P, Ironing, rate 3) with no LabourRate. Migrate forward. Assert:
    - In-house Stitching = 10
    - In-house Packing = 0
    - P / Ironing = 3
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
  - Remove every rate and rework-rate input from route and lot forms. `reassign_step` loses its `rate` and `rework_rate` parameters. `add_step` loses `rate`.
  - Packing, moves and cutting call `costing.inhouse_amount`.
  - The view shows `MissingRate` as a form error with a link to `rate_list`.
- [ ] **Step 4:** Run the tests above, then `tests/test_production.py tests/test_production_ui.py tests/test_step_view.py tests/test_process_materials.py`. Fix any test fixture that set `rate=` on route or lot steps: give it an In-house rate via `rates.save_rate` in `tests/prod_helpers.py`. Expected: PASS.
- [ ] **Step 5:** Commit: `E2.3 E7.2 rates live only on Rates; in-house work looks them up`.

### Task 3: Challans use Rates; rework never paid twice; cost entries carry their rate

**Files:**
- Modify:
  - `jobwork/services/challans.py:84-112`, `jobwork/services/receipts.py:211-215`
  - `production/models.py` (`LotCostEntry`: add `rate = FK(LabourRate, null=True, PROTECT)`, `qty = PositiveIntegerField(null=True)`)
  - `jobwork/models.py` (`JobWorkChallan`: add `labour_rate = FK(LabourRate, null=True, PROTECT)`, set on issue challans)
  - `production/services/costing.py` (`accrue_labour` takes `rate`, `qty`)
  - `jobwork/services/bills.py` (cost entries get `rate`, `qty`)
- Test: `tests/test_jobwork.py`, `tests/test_held_rework.py`

**Interfaces:**
- Consumes: `rates.rate_for(party, step.process, date)`.
- Produces:
  - `costing.accrue_labour(*, lot, factory, step, rate: LabourRate, qty: int, date, user, source, note) -> LotCostEntry`. Amount = `rate.rate * qty`.
  - `LotCostEntry.rate` and `.qty`, read by Task 4 (narrations) and Task 15 (diary).

**Rules:**
- Issue challan: `price = rate_for(party, process, date).rate` for every bundle. `rate_type="A"`.
- Rework challan:
  - `ACCEPTED` basis: `price = first_pass_line.rate`. The piece was not paid on the first pass.
  - `RECEIVED` basis: `price = 0`.
- Remove the "set a rate on the step" fallback text. `MissingRate` replaces it.

- [ ] **Step 1: Write failing tests**
  - `test_challan_price_from_rates`: rate ₹12 → every `ChallanBundle.rate == 12`.
  - `test_challan_refused_without_rate`: no rate → `MissingRate`, and no challan is created.
  - `test_rework_on_received_basis_paid_once`:
    1. Issue 10 pieces at ₹12 on RECEIVED.
    2. QC: 8 accepted, 2 rework. The first-pass pay is 10 pieces.
    3. Rework challan, 2 back, accepted.
    4. Bill total = 10 × 12 = ₹120.00.
  - `test_rework_on_accepted_basis_paid_once`: same as above on ACCEPTED. Bill total = (8 + 2) × 12 = ₹120.00.
  - `test_held_pieces_paid_once`: update the existing held-rework test so the total paid equals pieces × rate exactly once.
  - `test_cost_entry_records_rate_and_qty`: an in-house move of 240 at ₹1.50 → the entry has `rate` set, `qty == 240`, `amount == 360`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Then `grep -rn "rework_rate\|RateSpec\|rates.resolve" --include=*.py --include=*.html . | grep -v migrations` must return nothing.
- [ ] **Step 4:** Run `tests/test_jobwork.py tests/test_held_rework.py tests/test_jobwork_guide.py tests/test_acceptance.py`. Expected: PASS.
- [ ] **Step 5:** Commit: `E8.3 JOB-07 challans price from Rates; a reworked piece is paid once`.

### Task 4: Rates screen — the one place; BOM charges removed

**Files:**
- Modify:
  - `jobwork/views.py:343-390` (list, new, edit, delete)
  - `templates/jobwork/rate_*.html`, `config/urls.py`
  - `core/context_processors.py:47` (menu label "Rates")
  - `core/screens.py:52` ("Rates")
  - `masters/models.py:330` (delete `BomCharge`), `production/views.py:244` ("expected charges")
  - `docs/SETUP_GUIDE.md` ("Rates" section, rewritten)
- Create: `masters/migrations/00xx_remove_bomcharge.py`
- Test: `tests/test_rates.py` (screen tests)

**Interfaces:**
- Produces `rates.in_use(rate) -> bool`: True when any `JobWorkChallan.labour_rate` or `LotCostEntry.rate` points at it (both added in Task 3). `update_rate` and `delete_rate` raise `BusinessRuleError` when it is true.

**Screen:**
- One table, grouped by process, with columns: Who (fabricator name or "In-house"), Rate per piece, Pays on, From, Edit / Delete.
- "Add a rate" form fields:
  - Who: select with "In-house" first, then fabricators
  - Process
  - Rate per piece
  - Pays on: shown only for fabricators
  - From date
- Edit and Delete only while `rates.in_use(rate)` is false. Otherwise the row says: *"Used on work already recorded. To change it, add a new rate from a later date."*

- [ ] **Step 1: Write failing tests**
  - `test_rates_screen_lists_inhouse_first_and_hides_money_from_production_role`
  - `test_edit_and_delete_refused_once_used`
  - `test_menu_says_Rates`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Remove the add-on and size-wise inputs and their JS. Drop `BomCharge` and its admin and forms.
- [ ] **Step 4:** Run the screen tests and `tests/test_forms_ui.py tests/test_guide.py`. Expected: PASS. Browser check on a throwaway DB: add an In-house rate and a fabricator rate, and edit an unused rate.
- [ ] **Step 5:** Commit: `E8.3 Rates screen is the one place costs are set`.

## Part B — Plain journal entries (spec section 2)

### Task 5: One narration module, used at every production and job work posting

**Files:**
- Create: `ledger/services/narration.py`
- Modify these posting sites (narration and line narrations only):
  - `production/services/cutting.py:207`
  - `production/services/costing.py:67,90`
  - `production/services/materials.py:102`
  - `production/services/bundles.py:495`
  - `production/services/orders.py:196`
  - `jobwork/services/challans.py:206`
  - `jobwork/services/receipts.py:170`
  - `jobwork/services/bills.py:172`
- Modify: `templates/ledger/voucher_detail.html` (link "Made by: <step summary> on lot L-12" back to the lot, via `source_type` / `source_id` or the `ProductionActionItem` that holds the voucher)
- Test: `tests/test_narration.py` (new)

**Interfaces:**
- Produces pure functions returning `str` (max 500 characters). Amounts use the Indian grouping `₹2,880`; add `narration.money(Decimal) -> str` if no helper exists.
  - `fabric_cut(lot, cutting_no, metres, amount)`
  - `inhouse_labour(process, factory, lot, qty, rate)`
  - `materials_used(process, lot, lines, amount)`
  - `materials_to_fabricator(party, lot, lines)`
  - `trims_returned(party, lot)`
  - `labour_bill(bill, lines, tds)`
  - `packed(lot, qty, per_piece)`
  - `moved_between_factories(lot, from_f, to_f, qty, amount)`
  - `wip_written_off(lot, order)`

- [ ] **Step 1: Write failing tests.** Copy the exact strings from spec section 2, for example:

```python
def test_inhouse_labour():
    assert narration.inhouse_labour(cutting, factory1, lot, 240, rate_150_from_1oct) == \
        "Cutting in-house at Factory 1, lot L-12: 240 pieces × ₹1.50 = ₹360 (rate from 1 Oct 2026)"

def test_labour_bill_one_lot():
    assert narration.labour_bill(bill, [(lot, stitching, 240, rate_12_from_1oct)], tds=D("29")) == \
        "Stitching by Ramesh, lot L-12: 240 pieces × ₹12 = ₹2,880 (rate from 1 Oct 2026); TDS ₹29"

def test_packed():
    assert narration.packed(lot, 230, D("96.40")) == "Lot L-12: 230 pieces packed into Ready Goods at ₹96.40 a piece"
```

  A bill covering several lots joins one clause per lot with "; ". The TDS clause is omitted when TDS is zero.
  Plus one integration test, `test_cutting_voucher_reads_as_sentence`: post a cutting and check that `Voucher.narration` equals `narration.fabric_cut(...)`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement and wire every posting site above. Whole-rupee amounts print without paise (`₹360`). Others print two places (`₹1.50`, `₹96.40`).
- [ ] **Step 4:** Run `tests/test_narration.py`, then the full production and job work tests. Expected: PASS.
- [ ] **Step 5:** Commit: `ACC E7 E8 plain-sentence narrations on production and job work entries`.

## Part C — Locations (spec section 3)

### Task 6: Find locations by kind; rename to Godown and Ready Goods

**Files:**
- Modify:
  - `core/models.py:126-150` (`Location.Type.DISPATCH` label → "Ready goods"; add `Location.VISIBLE_TYPES = ("godown", "dispatch", "rejects", "showroom")`; add a manager method `visible()`)
  - `core/services/factories.py` (all `*_location` helpers)
- Create: `core/migrations/00xx_location_names.py` (data: per factory, "Main Godown" → "Godown", "Dispatch" → "Ready Goods")
- Modify tests: replace `Location.objects.get(factory=..., name="Main Godown")` / `name="Dispatch"` with `godown_location(factory)` / `ready_goods_location(factory)` across `tests/`.
- Test: `tests/test_locations.py` (new)

**Interfaces:**
- Produces:
  - `factories.location_of(factory, loc_type) -> Location`: the first active location of that type, by id. One is created with the default name if none exists.
  - `godown_location`, `ready_goods_location` (`dispatch_location` kept as an alias), `rejects_location`, `cutting_location`, `process_location` and `transit_location` all delegate to it.
  - `DEFAULT_LOCATIONS` names: Godown, Cutting Floor, Process Area, Ready Goods, In Transit, Rejects.

- [ ] **Step 1: Write failing tests**
  - `test_renamed_godown_still_found`: rename the godown "Store 1". `godown_location(f)` returns it, and a GRN posts there.
  - `test_new_factory_gets_godown_ready_goods_rejects`
  - `test_migration_renames_existing`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. `_get` by name is deleted.
- [ ] **Step 4:** Run the full suite (`-n auto`). Expected: PASS.
- [ ] **Step 5:** Commit: `E1.4 locations found by kind; Godown and Ready Goods`.

### Task 7: Only Godown / Ready Goods / Rejects on screen; defaults filled; "Where is my stock"

**Files:**
- Modify the location selects at:
  - `inventory/views.py:256,496`
  - `masters/views.py:511`
  - `purchases/views.py:304,718`
  - `production/views.py:266`
  - `sales` billing / packing views
  - their templates
- Modify: the QC form template (`templates/jobwork/qc*.html`): the reject choice is labelled **Keep as rejects** / **Scrap**.
- Create: `inventory/services/where.py`, `inventory/views.py: WhereIsStock`, `templates/inventory/where.html`, URL `where_stock`, menu entry under Stock: "Where is my stock".
- Modify: `docs/SETUP_GUIDE.md` (Locations section rewritten: three places, defaults, WIP by lot)
- Test: `tests/test_locations.py`

**Interfaces:**
- Produces `where.summary(user, factory) -> dict`:
  - `places`: `[(Location, [(item, qty, value_or_None)])]` for visible locations with stock
  - `wip`: `[(lot, step_name, with_whom: str, pieces: int)]`, where `with_whom` is a fabricator name, "Factory 1", or "on the way to Factory 2"

**Screen rules:**
- A location select is rendered only when the factory has more than one visible location that could apply. Otherwise a hidden input carries the default:
  - receipts and GRN → godown
  - packing → ready goods
  - billing → ready goods
- Internal types (cutting, process, transit, fabricator) never appear in a select or a stock list.
- Rejects is listed only when its balance is non-zero.

- [ ] **Step 1: Write failing tests**
  - `test_grn_form_has_no_location_select_with_one_godown`
  - `test_location_selects_never_list_internal_kinds` (render each form, assert "Cutting Floor", "Process Area", "In Transit" and "At " are absent)
  - `test_where_is_my_stock_shows_lot_step_and_fabricator`
  - `test_where_hides_values_from_production_role`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/test_locations.py`, the purchases, sales and inventory UI tests, and a browser check of GRN, packing and "Where is my stock". Expected: PASS.
- [ ] **Step 5:** Commit: `E6 INV three visible locations, defaults, where is my stock`.

## Part D — Default checks (spec section 6)

### Task 8: Whole pieces enforced in services

**Files:**
- Modify:
  - `inventory/services/stock.py:59-65` (`_qty` gains `item`)
  - `inventory/services/transfers.py`, `inventory/services/journal.py:74`, `inventory/services/opening.py:48`
  - `production/services/bundles.py` (`move_bundles`, `count_bundles`, `split_bundle`)
  - `jobwork/services/receipts.py` (`create_receipt`, `record_qc`)
- Create: `core/checks.py`
- Test: `tests/test_checks.py` (new)

**Interfaces:**
- Produces:
  - `core.checks.whole(value, what: str) -> int`. Raises `BusinessRuleError(f"{what} must be a whole number of pieces.")`.
  - `core.checks.counts_whole(item) -> bool`. True for SKUs and for materials whose `unit.kind == "count"`.

- [ ] **Step 1: Write failing tests**
  - `test_stock_movement_of_sku_refuses_fraction` (2.5 → error)
  - `test_count_material_refuses_fraction` (zips 10.5)
  - `test_fabric_metres_accept_fraction` (58.4 m roll issue)
  - `test_kg_material_accepts_fraction`
  - `test_move_bundles_refuses_fraction_when_called_directly`
  - `test_transfer_line_refuses_fraction_for_sku`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Call `whole` in every service listed above.
- [ ] **Step 4:** Run `tests/test_checks.py` and the inventory tests. Expected: PASS.
- [ ] **Step 5:** Commit: `NFR whole pieces checked in every service`.

### Task 9: Limits, dates and money checks with plain messages

**Files:**
- Modify: `core/checks.py`, and the services named in each test below
- Test: `tests/test_checks.py`

**Interfaces:**
- Produces:
  - `core.checks.not_future(day, what)`. Message: `f"{what} cannot be in the future."`
  - `core.checks.not_before(day, earlier, what, earlier_what)`. Message: `f"{what} cannot be dated before {earlier_what} ({earlier:%d %b %Y})."`
  - `core.checks.not_negative(value, what)`

Each test asserts the exact message from the interface. Tests that exist already only get the message assertion added.
- [ ] **Step 1: Write failing tests**
  - `test_fabric_issue_over_roll_balance_refused`
  - `test_challan_more_than_bundle_refused`
  - `test_receipt_more_than_sent_refused`
  - `test_sale_more_than_ready_goods_refused`
  - `test_transfer_more_than_source_refused`
  - `test_future_dated_step_refused`
  - `test_receipt_before_challan_refused`
  - `test_qc_before_receipt_refused`
  - `test_bill_before_qc_refused`
  - `test_negative_price_refused`
  - `test_bill_cannot_exceed_checked_pieces_times_rate`
- [ ] **Step 2:** Run them. Expected: the new ones FAIL.
- [ ] **Step 3:** Implement the missing checks only.
- [ ] **Step 4:** Run the full suite (`-n auto`). Expected: PASS.
- [ ] **Step 5:** Commit: `NFR default limit, date and money checks`.

## Part E — Delete (spec section 4)

### Task 10: The purge engine

**Files:**
- Create: `core/services/purge.py`
- Test: `tests/test_purge.py` (new), `tests/deletion_helpers.py` (new)

**Interfaces:**
- Produces:
  - `purge.movements(qs)`: deletes StockMovement rows via queryset `.delete()`, bypassing `StockMovement.delete`. It does not touch balances; callers only purge sets that net to zero per (location, item, roll). It asserts that netting and raises `PurgeError` otherwise.
  - `purge.vouchers(qs)`: deletes vouchers, their lines and `BillAllocation`s via queryset delete, bypassing `Voucher.delete`. It asserts each voucher's reversal is in the same set, or that the voucher is a draft. One exception: `delete_voucher` (Task 13) purges a lone posted voucher.
  - `purge.history(model, pks)`: deletes `model.history` rows for those ids, including the "-" rows created by the delete itself.
  - `purge.history_since(model, pk, since: datetime)`: deletes history rows of a kept row from that time on, for rows put back by an undo.
- `tests/deletion_helpers.py`:
  - `books(company) -> dict`: ledger balances, stock balances and roll balances.
  - `assert_no_trace(source_type, source_id)`: no StockMovement, Voucher or history row refers to it.

- [ ] **Step 1: Write failing tests**
  - `test_purge_pair_leaves_balances_unchanged`
  - `test_purge_refuses_unbalanced_set`
  - `test_history_rows_gone_including_delete_marker`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Document at the top of the module: the owner's decision of 19 Oct 2026, the only place posted rows are removed.
- [ ] **Step 4:** Run `tests/test_purge.py`. Expected: PASS.
- [ ] **Step 5:** Commit: `SYS purge engine for owner-approved deletes`.

### Task 11: Delete a production or job work step (replaces undo)

**Files:**
- Modify:
  - `production/services/actions.py` (add `delete_step`; `blockers` gains newest-first; `listed` / `for_docs` mark `can`)
  - `production/views.py:511` (`StepUndo` → `StepDelete`), `config/urls.py:208` (`step_delete`)
  - `templates/production/step_undo.html` → `step_delete.html`
  - `templates/production/_steps_recorded.html`, `_step_events.html`, `cutting.html:36,50`, `fabric_issue.html:25`
  - `CLAUDE.md` (rule 1: add "except Delete of a step or document, which removes it and its entries entirely (owner's decision, 19 Oct 2026)"; history note likewise)
- Test: rewrite `tests/test_step_undo.py` → `tests/test_step_delete.py`

**Interfaces:**
- Consumes: Task 10 `purge.*`; the existing `actions.undo`.
- Produces:
  - `actions.delete_step(action, *, user) -> None`.
  - `actions.consequences(action) -> list[str]`: the plain sentences for the confirmation page, for example "put 240 pieces back on challan JW-14 with Ramesh", "remove ₹2,880 of stitching cost from lot L-12", "delete journal entry JV-88". The money sentences are left out for users without cost rights.

**`delete_step` algorithm**, inside one `transaction.atomic()`:
1. Check the period is open on `action.date`. Check `blockers`. Newest-first: any later, not-undone action on the same lot gives `f"To delete this {kind}, first delete: {later summaries, newest first, joined by ', then '}."`
2. `undo(action, user=user, reason="Deleted", date=action.date)`. This posts reversals and restores rows.
3. Collect:
   - the action's MOVEMENT, VOUCHER and COST items
   - the reversal movements and cost entries with `source=action`
   - the reversal vouchers via `Voucher.reverses`
4. Purge the movements, the vouchers and the `LotCostEntry` rows (queryset delete).
5. Hard-delete the voided bundles and cancelled challans this action created, with their lines.
6. Purge history: of every created row, and `history_since(action.created_at)` for changed rows.
7. Delete the `ProductionActionItem` rows and the `ProductionAction`.

- [ ] **Step 1: Write failing tests**
  - `test_delete_cutting_leaves_no_trace_and_books_as_before`: `books()` before the cutting equals `books()` after the delete, and `assert_no_trace` passes.
  - `test_only_newest_step_can_be_deleted_and_message_names_later_steps`: the message text is exact.
  - `test_delete_challan_then_cutting_then_reenter`
  - `test_delete_refused_in_locked_period`
  - `test_delete_qc_on_billed_line_names_the_bill`
  - `test_delete_newest_on_lot_a_while_lot_b_used_same_trim_later`: Review Focus 1. Lot B's movements and vouchers are untouched, and the trial balance tallies.
  - `test_confirmation_lists_consequences_and_hides_money_from_production_role`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Remove the undo view, the reversal-date field and the "Undo" / "Edit" pair. The button is **Delete**, and the confirmation page has **Delete** / **Keep it**. After deleting, redirect to the lot with the message "Deleted. You can enter it again now."
- [ ] **Step 4:** Run `tests/test_step_delete.py`, `tests/test_acceptance.py` and `tests/test_held_rework.py`. Expected: PASS. Then grep `templates` for "Undo" and expect no hits on production or job work screens.
- [ ] **Step 5:** Commit: `E7 E8 delete a recorded step, newest first, with its entries`.

### Task 12: Delete labour bills

**Files:**
- Modify: `jobwork/services/bills.py:232`, the bill detail view and template
- Create: `ledger/services/settlement.py`
- Test: `tests/test_jobwork.py`

**Interfaces:**
- Produces:
  - `bills.delete_bill(bill, *, user)`: runs `cancel_bill(reason="Deleted")`, then purges the bill's voucher and reversal, its negative cost entries and history, then deletes the bill. The bill's QC results become unbilled again.
  - `ledger.services.settlement.settled_against(voucher) -> list[Voucher]`: posted vouchers with an `AGAINST` allocation on the same ledger whose reference equals a `NEW` reference this voucher opened.

- [ ] **Step 1: Write failing tests**
  - `test_delete_paid_bill_refused_names_payment`: Review Focus 4. The message is `f"Payment {number} is settled against this bill. Delete the payment first."`
  - `test_delete_bill_covering_two_lots_lists_both_on_confirmation`
  - `test_delete_bill_leaves_no_trace`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `tests/test_jobwork.py`. Expected: PASS.
- [ ] **Step 5:** Commit: `JOB delete a labour bill with its entries`.

### Task 13: Delete hand-made vouchers

**Files:**
- Create: `ledger/services/deletion.py`
- Modify: the voucher detail view and template, `config/urls.py` (`voucher_delete`)
- Test: `tests/test_settlement_crud.py`, `tests/test_posting.py`

**Interfaces:**
- Produces `deletion.delete_voucher(voucher, *, user)`. It is allowed only when:
  - `voucher.source_type == ""` (hand-made)
  - the period is open
  - `settled_against(voucher)` is empty

  The voucher, its lines, allocations and history are purged. A voucher made by a document refuses with `f"This entry was made by {doc}. Delete {doc} instead."`

- [ ] **Step 1: Write failing tests**
  - `test_delete_payment_frees_the_bill`
  - `test_delete_journal_leaves_no_trace`
  - `test_delete_document_voucher_refused`
  - `test_delete_in_locked_period_refused`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Replace the "Reverse" button on hand-made vouchers with **Delete**.
- [ ] **Step 4:** Run the ledger tests. Expected: PASS.
- [ ] **Step 5:** Commit: `ACC delete hand-made entries`.

### Task 14: Delete sales and purchase documents

**Files:**
- Modify (add `delete_*` beside each `cancel_*`):
  - `purchases/services/grn.py:311`, `purchases/services/invoices.py:374`, `purchases/services/debit_notes.py:243`
  - `sales/services/invoices.py:361`, `sales/services/credit_notes.py:178`, `sales/services/packing.py:127`, `sales/services/orders.py:127`
  - `inventory/services/journal.py:121`, `inventory/services/transfers.py`
  - each detail view and template (Cancel → Delete with the confirmation page)
- Test: `tests/test_purchases.py`, `tests/test_sales.py`, `tests/test_stock_journal.py`

**Interfaces:**
- Pattern for each document: `delete_<doc>(doc, *, user)` calls the existing `cancel_<doc>(reason="Deleted")`, which keeps its dependency refusals. It then purges every StockMovement and Voucher whose source is the document (originals and reversals), purges history, and deletes the document and its lines.
  - A cancel service whose reversal movements carry a different source must be changed to use the document as source, so the purge finds them.
  - Sales orders, which post nothing, are simply deleted when they have no packing or invoice.
- A sales invoice with an IRN or e-way bill number refuses: `"This bill has an e-invoice / e-way bill. Cancel it on the portal first."`

- [ ] **Step 1: Write failing tests.** For each document: `test_delete_<doc>_leaves_no_trace_and_books_as_before`, plus:
  - `test_delete_grn_refused_while_its_roll_was_issued`
  - `test_delete_invoice_with_irn_refused`
  - `test_delete_packing_refused_while_invoiced`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement, one document at a time.
- [ ] **Step 4:** Run the purchases, sales, inventory and acceptance tests. Expected: PASS.
- [ ] **Step 5:** Commit: `PUR SAL INV delete documents with their entries`. If the diff is large, use one commit per app.

## Part F — Lot page and tags (spec section 5)

### Task 15: Lot diary; route fixed after cutting

**Files:**
- Create: `production/services/diary.py`, `templates/production/_lot_diary.html`
- Modify:
  - `production/views.py:240-270` (context)
  - `templates/production/lot_detail.html:38-81` (remove "History", "Corrections" and "Change the route" after cutting)
  - `production/services/routes.py` (refuse changes after cutting)
  - `production/services/step_view.py` (rate column shows `rates.source_text` and who)
  - `docs/SETUP_GUIDE.md` ("The lot page")
- Test: `tests/test_production_ui.py`, `tests/test_diary.py` (new)

**Interfaces:**
- Produces `diary.entries(lot, user) -> list[DiaryEntry]`, oldest first. `DiaryEntry(date, text: str, who: str, link: str | None, voucher_links: list[tuple[str, str]], can_delete: bool, action: ProductionAction)`.
  - Text pattern, for example `"Cut 240 pieces into 12 bundles"` or `"Sent 240 pieces to Ramesh for Stitching (challan JW-14)"`.
  - Money is only in `voucher_links`, which are empty for users without cost rights.
  - `can_delete` is true only on the newest entry, and only when `may_undo` allows it.
- `routes.add_step`, `skip_step`, `remove_step`, `reorder_step` and `reassign_step` raise `BusinessRuleError("The route is fixed once cutting has started. Choose who does a step when you send the work.")` when `lot.cuttings.exists()`.

- [ ] **Step 1: Write failing tests**
  - `test_diary_lists_every_step_oldest_first_with_who`
  - `test_only_newest_diary_entry_has_delete`
  - `test_route_panel_hidden_after_cutting_and_service_refuses`
  - `test_lot_page_has_no_History_or_Corrections_heading`
  - `test_step_table_shows_rate_source`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests and a browser check of a lot page on a throwaway DB. Expected: PASS.
- [ ] **Step 5:** Commit: `E7.11 lot diary; route fixed after cutting`.

### Task 16: No bundle tags in production; piece tags after packing

**Files:**
- Modify:
  - `production/views.py:464-485` (cutting no longer redirects to `lot_tags`; the message drops "Print their QR tags now")
  - `templates/production/cutting.html:50` ("Make bundles" without "and QR tags")
  - `templates/production/lot_detail.html` (no tag link before packing; **Print tags** after packing)
  - `inventory/views.py: TagPrint` (accepts `?lot=<pk>`)
  - `docs/SETUP_GUIDE.md`
- Test: `tests/test_production_ui.py`

**Interfaces:**
- Produces `production.services.bundles.packed_counts(lot) -> dict[SKU, int]`: pieces packed per SKU, read from `PackEntryLine`. `TagPrint` with `?lot=` prints one tag per packed piece.

- [ ] **Step 1: Write failing tests**
  - `test_cutting_does_not_send_to_tags`
  - `test_lot_page_offers_print_tags_only_after_packing`
  - `test_print_tags_for_lot_prints_one_per_packed_piece`
  - `test_lot_tags_url_refuses_before_packing`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `E7.5 BAR piece tags after packing; no bundle tags in production`.

### Task 17: Final pass

- [ ] **Step 1:** Run the full suite: `.venv/Scripts/python.exe -m pytest -p no:cacheprovider -n auto`. Expected: all PASS, including acceptance A1–A12.
- [ ] **Step 2:** Read `docs/SETUP_GUIDE.md` start to finish. Check it has no mention of route rates, rework rate, add-on or size-wise rates, BOM charges, Undo, Main Godown, Dispatch (as a location), Seconds or bundle QR tags. Then run `grep -rn "rework_rate\|Main Godown\|Undo\b" templates docs/SETUP_GUIDE.md` and expect nothing.
- [ ] **Step 3:** Commit any guide fixes: `Help: guide matches the rate list, locations and delete`.
