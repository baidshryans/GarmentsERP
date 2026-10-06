# Guided steps for job work (piece 2b)

Date: 2026-10-06. Status: owner said "proceed" on the outline; built on branch `ui-guided-jobwork`.

## Problem

Sending work to a fabricator and getting it back crosses five screens (new challan, challan, receipt, QC, labour bill). The lot page now names the next step for a lot, but someone working from the job-work screens, a challan in hand, gets no such help.

## Design

No model, URL or migration change. Labour is still computed only on QC-accepted pieces (CLAUDE.md rule 5); nothing about posting changes except that an existing service call (issue) can be made from the new-challan form.

### 1. Challan journey and next step

`jobwork/services/guide.py`, read-only, `challan_guide(challan, user, perms=None)` returning the same shape as `production.services.guide.lot_guide`: `journey`, `primary`, `others`, `waiting`, `complete`.

Journey: `Draft → Issued → Received → Checked → Billed`, each done / now / to come, with piece counts where they mean something (issued, received, accepted).

| Challan state | Label | Opens | Permission (plus view on the target) |
| --- | --- | --- | --- |
| Draft | Issue challan | `challan_detail` (the issue button) | `jobwork.challan` edit |
| Issued or partly received, pieces still out and not on a pending over-receipt | Receive from *fabricator* | `receipt_new` | `jobwork.receipt` create |
| A receipt awaits approval | Approve over-receipt | `receipt_detail` | `jobwork.receipt` approve |
| A receipt has unchecked lines | Check received pieces | `receipt_detail` | `jobwork.qc` create |
| Accepted pieces not yet on a labour bill | Make labour bill for *fabricator* | `bill_new` with the fabricator chosen | `jobwork.bill` create |
| Billed or closed, nothing left | none: "This challan is finished." | | |
| Cancelled | none | | |

Ordering: what is furthest behind first, as in the lot guide. If actions exist but the user may do none, `waiting` names the first.

The lot guide (`production/services/guide.py`) and the challan guide must agree: where both offer an action for the same challan or receipt, it is the same label and URL. Share the code rather than copy it.

### 2. Where it shows

- Challan page: journey strip and Next button at the top (reuse the journey partial and CSS from the lot page).
- Receipt page: the challan's guide, so after QC the next step (another receipt, or the labour bill) is one click.
- Challan list and receipt list: a "Next step" column.
- Home launchpad "Receive from fabricator": opens `challan_list?status=issued` (and partly received) so each row's Next step is Receive.

### 3. One step fewer

The new-challan form gets a second submit, "Save and issue", next to the existing save-as-draft. It creates the challan and issues it in one transaction through the existing services (`create_challan`, then `issue_challan`); if issuing fails, nothing is saved. It then opens the challan page, ready to print. Needs `jobwork.challan` create and edit; without edit only the draft button shows.

### 4. Fixes carried on this branch

- Move screen "Next stage" column names the next mandatory step after where the bundle actually is (the same rule as the lot guide's button), not the first step after `completed_seq`.
- A rework challan may only take rework bundles whose current step is the challan's step: enforced in `create_challan` (a `BusinessRuleError` naming the bundle and its step) and reflected in the new-challan form, which lists only the rework bundles of the chosen step.

## Rules kept

Factory scoping through `for_user` in every caller; no link a role cannot open; BR-15 (fabricator names only); read-only guide service; every voucher still balanced (autouse test fixture).

## Tests

One per row of the table; lot guide and challan guide agree on a shared challan; "Save and issue" success and rollback on failure; list columns; Home link; the two fixes; a test that follows each offered link to its target. User guide updated.
