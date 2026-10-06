# Guided steps for buying (piece 2c)

Date: 2026-10-06. Status: owner said to move forward with the next flows; built on `master` directly (owner's instruction).

## Problem

Buying fabric or trims crosses purchase order, approval, goods received with quality check, supplier bill and payment, each on its own screen with nothing saying what comes next.

## Design

Same pattern as Making and job work: a read-only guide service, a journey strip, one Next button, the same next step in list rows, and each save leading on. No model, URL-conf or migration change. Nothing about how stock, tax or vouchers are computed changes; tax stays optional (CLAUDE.md rule 3).

### 1. Journey

`purchases/services/guide.py` (read-only): `po_guide`, `grn_guide`, `invoice_guide`, `debitnote_guide`, each `(document, user, perms=None)` returning the shape the shared `templates/_journey.html` partial takes (`journey`, `primary`, `others`, `waiting`, `complete`, `closed`), plus `*_next` helpers for list rows.

One purchase journey, entered at whichever document exists:

`Ordered → Approved → Received → Checked → Billed → Paid`

A goods receipt without a purchase order starts at Received; a direct supplier bill (no goods receipt) starts at Billed. Each stage is done / now / to come, with quantities or amounts where they mean something (received of ordered, billed amount, amount still unpaid). The "Approved" stage is left out when the order did not need approval.

### 2. Next actions

Furthest-behind first; the first permitted one is the button, the rest are "Also waiting" links; "Waiting for: …" when the step is someone else's. Every action also requires view on its target screen.

| State | Label | Opens |
| --- | --- | --- |
| Order is a draft | Submit order | the order page (its submit action) |
| Order awaits approval | Approve order | the order page |
| Order approved or partly received, quantity still to come, no unposted goods receipt against it | Receive goods | new goods receipt against this order |
| A goods receipt is a draft with quality check not finished | Check quality | that goods receipt |
| A goods receipt has quality check done, not posted | Post goods received | that goods receipt |
| A posted goods receipt has rejected quantity not yet on a return | Return rejected goods to supplier | new return against that goods receipt |
| A posted goods receipt has accepted quantity not yet billed | Enter supplier bill | new supplier bill against that goods receipt |
| A supplier bill is a draft | Post supplier bill | that bill |
| A posted supplier bill has an amount unpaid | Pay *supplier* | Money paid, with the supplier chosen |
| A return is a draft | Post return | that return |
| Nothing left | none: "This purchase is complete." | |
| Cancelled or closed | none | |

The order's guide includes the actions of its goods receipts, their bills and returns; a goods receipt's guide includes its own and its bills' and returns'; a bill's guide its own. Where two guides offer an action for the same document it is the same label and URL, built by shared code.

"Pay supplier" must use the outstanding amount the ledger's bill-wise records hold; it is offered only to roles that may enter a payment.

### 3. Fewer steps

- **Save and submit** on the new-order form beside Save: creates and submits in one transaction through the existing services. If the order is within the approval limit it comes out approved, ready to receive against.
- **Accept all and post** on a goods receipt whose lines are all still pending quality check: marks every line accepted, finishes the quality check and posts, in one transaction through the existing services; if any part fails nothing is saved. Offered only to a role that could do each of the three steps separately. Line-by-line checking stays available for the cases with rejections.
- After a goods receipt is posted the page shows the Next button (Enter supplier bill, or Return rejected goods); after a bill is posted, Pay supplier.

### 4. Where it shows

- Order, goods receipt, supplier bill and return pages: journey and Next button at the top.
- Purchase orders, Goods received and Supplier bills lists: a "Next step" column (computed only for the rows shown, one permission memo per page).
- Home launchpad stays as it is (owner wants it short).
- Home "Needs your attention" lines for purchases link to the lists, where each row now has its Next step.

## Rules kept

Factory scoping through `for_user` in every caller; no link a role cannot open; read-only guide services; every voucher balanced and stock reconciled (autouse test fixture); posted documents never edited.

## Tests

One per table row; agreement between the order, goods-receipt and bill guides on shared documents; a role with no permitted action; a custom role with an action permission but not view; tests that follow each offered link and check the target really offers that step for that document; Save and submit, and Accept all and post, including full rollback on failure (no row, no number consumed, no stock movement); list columns. User guide updated.

## Out of scope

Selling (next piece); form simplification (piece 3); changes to approval limits, tax or costing.
