# Sample Issue & Receive — Verification Guide

This guide walks you through testing the new **Sample Issue** workflow and the
hardened **Job Work Receive** flow end-to-end. Use it as a checklist when you
sit down to validate the manufacturing module.

---

## 1. What changed (one-minute summary)

Before this release, a karigar job-issue form did double duty: it captured
brand-new jobs **and** piece re-issues (sample issues). That is now split:

- **Karigar Issue** (`/manufacturing/karigar-issue/...`) — only new jobs built
  from raw material + stones + customer orders / stock / repair.
- **Sample Issue** (`/manufacturing/sample-issue/...`) — **NEW** — the form
  you use when you hand a semi-finished / finished piece back out to a karigar
  for rework, polishing, stone setting, etc.

`UnBarcodedMain` is now the single catalogue of these pieces. Each piece has a
`kr_code` field that tracks who currently holds it; this is set automatically
when you save a Sample Issue and cleared when the piece comes back on a
Receive.

Two new business rules are enforced server-side:
- A Karigar Issue slip of type **Customer Order** cannot mix with Stock or
  Repair items (and vice-versa) — save is rejected at the serializer.
- A Receive line must reference **exactly one** of `ref_job_no` or
  `ref_sample_issue`, never both.

The **Subcontractor Ledger** report has been redesigned to show three clearly
separated sections: finished-account (piece weights), raw-gold-account (pure
weight), and labour-summary (making charges).

---

## 2. Before you start

1. Pick a test karigar ledger (e.g. "Test Karigar A") and at least one
   secondary karigar ("Test Karigar B") — you'll move a piece between them.
2. Make sure that karigar has a row in **Karigar Master** with
   `making_per_gm` set (e.g. ₹400/g). This drives the auto-labour feature.
3. Have one raw-gold ledger entry you can draw from, plus one customer-order
   item if you want to exercise the slip-type validator.

---

## 3. Happy path — new job → receive semi → sample-reissue → receive finished

### 3.1 Create a new Karigar Issue (job order)

1. Navigate to **Manufacturing → Karigar Issue → New**.
2. Set:
   - Slip type = **Stock**
   - Karigar = **Test Karigar A**
   - Add one item row: say a ring, 916 purity, 1 pc, 10g approx
3. Save.

✅ Expected: slip saved, slip no assigned, no sample-issue multi-select is
visible on the form (it was removed).

### 3.2 Attach a Gold Issue to that job

1. Open **Karigar Gold Issue → New**.
2. Reference the job from 3.1 and issue, e.g. 9g of 916 metal (conv ≈ 8.24g pure).

### 3.3 Receive the job as semi-finished

1. Open **Job Work Receive**.
2. Reference the Job Issue from 3.1.
3. Enter: pcs=1, gw=9.5, nw=9.3, finish_status = **unchecked (semi)**.
4. Leave `making` empty.
5. Save.

✅ Expected:
- Receive saved.
- An **UnBarcodedMain** row is created for the received piece (visible in
  `Inventory → Unbarcoded`). Its `created_from` = `KAR_REC`.
- The receive's `making_auto` = true, `making` ≈ rate × incremental_gw.
  - Example: if karigar rate is ₹400/g and incremental_gw = 9.3 − 8.24 = 1.06g,
    making ≈ ₹424.
- Check the making-charge voucher auto-posting — it still groups by purity
  and posts Dr Making Charge Paid / Cr Karigar, unchanged from before.

### 3.4 Sample-issue the piece to Karigar B

1. Navigate to **Manufacturing → Sample Issue → New**.
2. Set Karigar = **Test Karigar B**.
3. Click the Piece picker — it should list:
   - All pieces with `kr_code = NULL` **and**
   - Pieces currently held by Karigar B (none yet).
   - It must **not** show pieces held by Karigar A other than the one you just
     received (which now has `kr_code = NULL` because Karigar A returned it).
4. Pick the piece from 3.3. Item / purity / pcs / gw columns fill in read-only.
5. Add instructions ("Polish + stone set"), due date. Save.

✅ Expected:
- Sample Issue saved.
- The `UnBarcodedMain.kr_code` of the picked piece is now set to Karigar B
  (check via admin or the unbarcoded list — the picker will now hide this
  piece when the karigar filter is Karigar A).

### 3.5 Receive the piece back from Karigar B (finished)

1. Open **Job Work Receive**.
2. Reference the Sample Issue from 3.4 via `ref_sample_issue` /
   `ref_sample_issue_item` (backend accepts both).
3. gw = 9.7, nw = 9.6, finish_status = **checked (finished)**.
4. Save.

✅ Expected:
- `SampleIssueItem.rec_status` flipped to true.
- The original piece's `kr_code` is cleared (back in the shop).
- A new `UnBarcodedMain` row is created for the received piece, and the
  **original** piece's `.next` FK chains to it (traceability).
- `making` auto-computed from incremental gw. If gw actually went up (added
  metal during stone setting), incremental > 0 and you'll be charged for it;
  if it went down, incremental = 0 (floored) and making = 0 — the
  difference is captured as loss / less_gw.

---

## 4. Slip-type validation (should-fail cases)

Try these — they should all be rejected at save:

1. **Mixing**: on a Karigar Issue, set slip_type = Customer Order but leave
   one item row's `customer_order_item` blank. → Expect 400 with
   "every line to reference a customer order item".
2. **Reverse**: slip_type = Stock with one item having `customer_order_item`
   populated. → Expect 400 with "cannot contain customer-order items".
3. **Receive**: submit a receive line with **both** `ref_job_no` and
   `ref_sample_issue` set. → Expect "either a Job Issue or a Sample Issue,
   not both".

---

## 5. Subcontractor Ledger (new report)

1. Navigate to **Manufacturing → Reports → Subcontractor Ledger** (route:
   `SubcontractorLedger.jsx`).
2. Select Karigar = **Test Karigar B**, no date filter, click **Run**.

✅ Expected sections (stacked):

**Finished / Semi-finished Account** (weight-based)
- Opening row (should be 0 if this is a fresh karigar).
- A `SAMPLE_OUT` row for the piece you issued in 3.4 with `out_gw = 10.0g`.
- A `RECEIVE_FINISHED` row for the piece you got back in 3.5 with `in_gw = 9.7g`.
- Totals: `in_gw=9.7, out_gw=10.0, closing=-0.3g` → karigar still owes 0.3g
  (they returned less than they took out — that's the loss).

**Raw Gold Account** (pure weight)
- Empty (Karigar B didn't get a direct gold issue in this scenario).

**Labour Summary**
- One row for the receive with incremental_gw, rate, amount, auto=✓.

Flip the karigar dropdown to **Test Karigar A**:
- Finished account shows the 3.3 receive as `RECEIVE_SEMI`, no SAMPLE_OUT rows.
- Raw gold account shows the 3.2 gold issue as `GOLD_ISSUE` and the 3.3
  receive's incremental as `GOLD_RECEIVE_INCREMENTAL`.
- Labour summary shows the 3.3 receive.

---

## 6. Conversion hardening (optional spot check)

1. Find any barcode in stock. Hit **Convert to Unbarcoded** once.
2. Hit it again with the same barcode. → Should fail with **409** ("already
   converted"). The form should toast the error instead of reloading.
3. Check the resulting `UnBarcodedMain`: its `source_barcode` FK points back
   to the original barcode row; `created_from = 'BAR_CONV'`.

---

## 7. Known current limits (intentional follow-ups)

- The job-work receive form frontend hasn't been fully extended with an
  "Against Job" vs "Against Sample" radio — the backend accepts either, but
  UI-side you'll submit `ref_sample_issue` via the API directly (or Postman)
  until the receive form is updated.
- Legacy columns `KarigarIssueItem.issued_sample_items` (M2M) and
  `source_receive_item` (FK) are **still in the schema** but unused in new
  writes. They'll be backfilled & dropped once you've verified production
  data is clean.
- Manufacturing loss is surfaced in the Labour Summary row (`loss_gw`) and in
  `less_gw` on the receive — no journal entry is posted for it (by design).

---

## 8. Rollback

All migrations are reversible via Django's built-in migrate-back. Specifically:

```
python manage.py migrate inventory 0005
python manage.py migrate manufacturing 0003
```

This undoes the UnBarcodedMain lineage changes and the SampleIssue tables.
Frontend changes are additive (new files) plus trims to karigarissue — safe
to `git revert` per commit.
