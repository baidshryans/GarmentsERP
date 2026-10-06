# Guided steps for selling (piece 2d)

Date: 2026-10-06. Status: owner said to move forward with the next flows; built on `master` directly.

## Problem

Selling crosses sale order, confirmation, packing, bill and collection, each on its own screen. Quick billing already covers the counter sale in one screen; this piece guides the order-based sale.

## Design

Same pattern as Making, job work and buying: read-only guide service, journey strip, one Next button, the same next step in list rows, each save leading on. No model, URL-conf or migration change. Nothing about how stock, cost of goods, tax or vouchers are computed changes; GST stays optional and waivable per bill (CLAUDE.md rule 3).

### 1. Journey

`sales/services/guide.py` (read-only): `order_guide`, `packing_guide`, `invoice_guide`, `creditnote_guide`, each `(document, user, perms=None)` returning the shape `templates/_journey.html` takes, plus `*_next` helpers for list rows.

`Ordered → Confirmed → Packed → Billed → Paid`

A bill made by quick billing (no order) starts at Billed. Stages show quantities or amounts where they mean something (packed of ordered, bill total, amount still to receive).

### 2. Next actions

Furthest-behind first; first permitted is the button, the rest "Also waiting"; "Waiting for: …" when it is someone else's step. Every action also requires view on its target.

| State | Label | Opens |
| --- | --- | --- |
| Order is a draft | Confirm order | the order page |
| Order confirmed or partly dispatched, quantity still to pack, no draft packing list for it | Pack goods | new packing list for this order |
| A packing list is a draft | Finish packing | that packing list |
| A packing list is packed, not billed | Make bill | that packing list (its bill action) |
| A bill is a draft | Post bill | that bill |
| A posted bill has an amount still to receive | Receive money from *customer* | Money received, with the customer, amount and bill reference filled |
| A return (credit note) is a draft | Post return | that return |
| Nothing left | none: "This sale is complete." | |
| Cancelled or closed | none | |

The order's guide includes its packing lists' and bills' actions; a packing list's guide its own and its bill's; a bill's guide its own and its draft returns'. Shared builders so the same document gets the same label and URL everywhere.

For a made-to-order sale order whose goods are not yet in stock, "Pack goods" is still the named step if the packing screen allows it; if packing cannot proceed for lack of stock, the guide says "Waiting for: goods from production" and offers no link. The implementer must establish from the code how made-to-order orders relate to production orders and stock before building this row, and report it.

Customer names appear on sales screens only. Nothing here may add a customer name or phone to any production screen (BR-15).

### 3. Fewer steps

- **Save and confirm** on the new sale-order form beside Save: creates and confirms in one transaction through the existing services.
- **Finish packing and make bill** on a draft packing list: finalises the packing and creates the draft bill in one transaction through the existing services, then opens the bill so tax can be chosen or waived before posting. Posting stays a separate, deliberate step.
- After a bill is posted the page shows the Next button, Receive money.

### 4. Where it shows

- Sale order, packing list, bill and return pages: journey and Next button at the top.
- Sale orders, Packing and dispatch, and Bills lists: a "Next step" column (rows shown only; one permission memo per page).
- Home launchpad unchanged.

## Rules kept

Factory scoping through `for_user`; no link a role cannot open; read-only guide; every voucher balanced and stock reconciled (autouse fixture); posted bills never edited; credit limits and price-list rules untouched.

## Tests

One per table row; agreement between guides on shared documents; a role with no permitted action; a custom role with an action permission but not view; link-following tests; both step-savers with full rollback on a late failure (no row, no number consumed, no stock movement, no voucher); list columns; a test that no production page gains a customer name. User guide updated.

## Out of scope

Form simplification (piece 3); e-invoice and e-way bill (still stubbed); changes to pricing, credit limit or tax logic.
