# Barcode Opening Import — Testing Checklist

Coverage map for the Barcode Opening Data Import feature (`backend/inventory/api_views.py` + `frontend/src/components/MasterImport/BarcodeOpeningUploadCard.jsx`).

## Automated Backend Tests

Run from `backend/`:

```
python manage.py test inventory.tests.test_barcode_opening_import -v 2
```

Expected: **48 tests pass**. The suite covers:

### CSV parser (`parse_csv_file`)
- [x] Returns `(row_num, row_dict)` tuples starting at row 2
- [x] Raises on missing required columns
- [x] Raises on empty file
- [x] Raises on header-only file
- [x] Strips UTF-8 BOM and whitespace from header field names
- [x] Skips completely empty data rows
- [x] Raises when row count exceeds `MAX_ROWS` (10,000)

### Foreign-key matchers
- [x] `match_purity` — exact numeric, karat suffix, strip-K, append-K, case-insensitive, invalid, empty, ambiguous
- [x] `match_retail_code` — valid, invalid, empty (matches `RetailMaster.retail_code`)
- [x] `match_item_name` — valid, invalid, empty, ambiguous (`item_name` is not unique)
- [x] `match_packet` — by integer ID, by `pckt_no`, empty returns None, invalid raises

### Numeric parsers
- [x] `parse_decimal_field` — valid, too many decimal places, invalid string, empty/None, NaN rejected, ±Infinity rejected
- [x] `parse_integer_field` — valid, invalid (non-integer string, float string), empty

### Validate endpoint (`POST /inventory/api/barcode-opening/validate/`)
- [x] Success returns preview with row counts and existing barcodes
- [x] Missing file returns 400
- [x] Invalid purity returns 400 with error list
- [x] Duplicate barcode in upload is flagged
- [x] Details barcode not in main CSV or DB is flagged
- [x] Pre-existing barcode is reported in preview
- [x] Unauthenticated request returns 401/403

### Import endpoint (`POST /inventory/api/barcode-opening/import/`)
- [x] Creates new barcode with `op_stk=True` and `op_retail` set to the matched retail
- [x] `conflict_action='error'` blocks existing barcodes
- [x] `conflict_action='skip'` skips existing barcodes AND their details rows
- [x] `conflict_action='update'` replaces details (counted as `details_replaced`) and updates main fields
- [x] Atomic rollback on validation failure (no partial inserts)
- [x] Invalid `conflict_action` returns 400

## Manual Testing — UI Flow

1. Start backend: `python manage.py runserver`
2. Start frontend: `cd frontend && npm run dev`
3. Sign in and navigate to `http://localhost:5173/setup/import-data`
4. Find the "Barcode Opening Stock" section.

### Test plan

- [ ] **Initial render** — Card shows two file-drop zones (Main CSV, Details CSV) + two "Download Template" buttons + "Upload & Validate" button disabled.
- [ ] **Download templates** — Both buttons download CSVs with header + 1 example row. Filenames `barcode_main_template.csv` and `barcode_details_template.csv`.
- [ ] **Upload & Validate (clean)** — Pick fixtures from `backend/inventory/tests/fixtures/`, click Upload. Expect spinner → preview card showing valid row counts (3 main, 4 details), no existing barcodes, no conflict-action radios.
- [ ] **Import (clean)** — Click Import. Expect spinner → success card with Created=3, Updated=0, Skipped=0, Details created=4.
- [ ] **Database verification** — In Django shell or admin: `BarcodeMain.objects.filter(op_stk=True).count()` ≥ 3. Each row has `op_retail` matching the retail code from CSV.
- [ ] **Conflict detection (validate)** — Re-upload the same files. Validation should now report `existing_barcodes_count: 3` with `["B001", "B002", "B003"]` listed. Three conflict-action radios appear with "Error" preselected.
- [ ] **Conflict action: Error** — With error selected, click Import. Expect ERROR state with message about existing barcodes.
- [ ] **Conflict action: Skip** — From PREVIEW state again, select Skip and import. Expect success card with Created=0, Updated=0, Skipped=3, Details created=0.
- [ ] **Conflict action: Update** — Modify `barcode_main_test.csv` so B001's `value` is `20000.00`. Re-upload, select Update, import. Expect Created=0, Updated=3, Skipped=0, Details replaced=4 (old details deleted), Details created=4 (new ones inserted). Verify `BarcodeMain.objects.get(barcode='B001').value == Decimal('20000.00')`.

### Edge cases worth manual sanity

- [ ] CSV with UTF-8 BOM (Excel exports) — pre-fixture by saving fixture as "CSV UTF-8 (Comma delimited)" from Excel
- [ ] Decimal field with too many places — change `5.500` to `5.5001` in main CSV → expect validation error pointing to `gross_weight has 4 decimal places (max 3)`
- [ ] Non-existent purity — change `18` to `99` → expect validation error for that row
- [ ] `quantity_pieces=` left blank → expect validation error (required field)
- [ ] `MAX_ROWS` enforcement — generate a CSV with 10,001 data rows → expect error mentioning the cap

### Packet matching (optional)

Packet rows must pre-exist. Add one for testing:
```
python manage.py shell -c "from mastersconfig.models import Packet; Packet.objects.create(pckt_no='PKT-TEST-001', is_solitaire=False, rate_for_retail=100, is_customer_stone=False)"
```
Then edit a details fixture row to set `packet_number=PKT-TEST-001` or the row's integer ID, re-upload, verify the imported `BarcodeDetails` row has the correct `packet_id`.

## Known Limitations

- **QR generation per save** — Each new BarcodeMain triggers a PNG render to disk. Large imports (>500 rows) take noticeably longer. The 10,000-row `MAX_ROWS` cap is a hard upper bound.
- **No frontend unit tests** — The project's only testing framework is Cypress (e2e). Backend coverage compensates.
- **Race condition on update** — If two users upload the same barcode at the same time, the second one's `transaction.atomic()` will roll back cleanly. Concurrent _different_ barcodes work fine.

## Files Reference

- Backend models: `backend/inventory/models.py` (BarcodeMain, BarcodeDetails)
- CSV utilities: `backend/inventory/csv_parsers.py`
- API views: `backend/inventory/api_views.py`
- URLs: `backend/inventory/urls.py`
- Backend tests: `backend/inventory/tests/test_barcode_opening_import.py`
- Sample fixtures: `backend/inventory/tests/fixtures/barcode_main_test.csv`, `barcode_details_test.csv`
- Frontend API: `frontend/src/services/api/masters.js` (last 4 exports)
- Frontend component: `frontend/src/components/MasterImport/BarcodeOpeningUploadCard.jsx`
- Frontend integration: `frontend/src/components/MasterImport/ImportDataPage.jsx`
