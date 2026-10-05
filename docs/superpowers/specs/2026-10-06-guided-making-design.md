# Guided steps for Making (piece 2a)

Date: 2026-10-06. Status: approved in conversation.

## Problem

Taking a lot from order to finished goods crosses eight screens. Each screen works, but nothing tells a first-time user which comes next, and after each save the user must find their own way back.

## Design

No model, URL, migration or posting change. One read-only service works out where a lot is and what it needs; templates show it; a few redirects follow it.

### 1. Journey strip

At the top of the lot page: `Order → Fabric → Cut → [each route step that is not skipped and is not a cutting step] → Finished goods`.

Each stage is done, now or to come, and shows the pieces sitting there. A subcontracted step shows the fabricator's name.

### 2. Next actions

Worked out on the server from the lot's real state, furthest-behind pieces first. The first one the user may do is the single primary button; any others are listed below it as smaller links.

| Lot state | Label | Opens | Permission |
| --- | --- | --- | --- |
| No fabric issued, nothing cut | Issue fabric | `lot_fabric` | `production.cutting` create |
| Fabric issued, nothing cut | Record cutting | `lot_cutting` | `production.cutting` create |
| A lay is cut but not bundled | Make bundles | `lot_cutting` | `production.cutting` create |
| Bundles cut or ready, next step in-house | Move to *process* | `move_bundles?lot=&back=1` | `production.move` create |
| Bundles in-house at a stage, a later step exists | Move to *next process* | same | same |
| Bundles cut, ready or at a stage, next step subcontracted | Send to *fabricator* for *process* | `challan_new?lot=&step=` | `jobwork.challan` create |
| A draft challan exists for the lot | Issue challan to *fabricator* | `challan_detail` | `jobwork.challan` edit |
| Bundles with a fabricator | Receive from *fabricator* | `receipt_new` for that challan | `jobwork.receipt` create |
| A receipt waits for the owner's approval | Approve over-receipt | `receipt_detail` | `jobwork.receipt` approve |
| Received, awaiting QC | Check received pieces | `receipt_detail` | `jobwork.qc` create |
| Pieces awaiting rework | Send back for rework | `challan_new?lot=&kind=rework` | `jobwork.challan` create |
| Bundles ready to pack | Pack into finished goods | `lot_detail#pack` | `production.move` create |
| Lot completed | none: "This lot is complete." | | |
| Lot closed | none | | |

If there are actions but the user may do none of them, the page says "Waiting for: *label*" instead of a button. An action never appears as a link the user would get a 403 on.

### 3. Each step leads to the next

- Releasing an order with exactly one lot opens that lot (when the user may view lots).
- Fabric issue already continues to cutting; making bundles already continues to tags. The tags, cutting and fabric screens gain a "Back to lot" button.
- The move screen returns to the lot only when opened from a lot's Next button (`back=1`); opened from the menu it stays put, so a supervisor can keep scanning.
- Challan and receipt pages gain a "Back to lot" button. When the last line of a receipt is checked, QC returns to the lot.
- Every lot link or redirect is given only to users who may view lots.

### 4. Lighter lot page

Visible: journey, next actions, the three figures, bundles (with packing). Folded under closed `<details>`: "Route and rates", "Lot cost", "History". The four header buttons reduce to "Print tags" (when bundles exist) and the order link; fabric, cutting and move stay reachable from a "More" row of ghost buttons for corrections.

### 5. Next step outside the lot page

- Production orders list: a "Next step" column. Draft order: a Release button (edit permission). Order with one live lot: that lot's primary action. Several lots: "Open".
- Order page: each lot line shows its primary action beside the lot button.
- Home "Items in production": a last column with the lot's primary action.

## Rules kept

- Factory scoping: the service reads only through the lot it is given, and every caller fetches lots with `for_user`.
- BR-15: the service returns labels, counts and URLs only; fabricator names are the only party names.
- Read-only: the service never writes.

## Tests

One test per row of the table; a lot with bundles spread over two stages; a role with no permitted action; the release, move (`back=1` and without) and QC redirects; a second-factory user gets 404 on the lot. Trial balance and stock reconcile after every posting test (autouse fixture).

## Out of scope

Job work, buying and selling flows as their own guided pieces; form simplification (piece 3).
