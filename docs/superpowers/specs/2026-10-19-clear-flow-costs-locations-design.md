# Clear flow: one rate list, plain journals, simple locations, delete — design

Date: 19 Oct 2026. Decisions are the owner's unless marked *(builder's call)*.

## Why

The owner followed a production order end to end and could not tell where costs were defined or calculated. He is a business person, not an ERP user: he knows his processes, not ERP concepts. Today:

- One process step's rate can live in three places (route template step, the lot's copy of it, a dated fabricator labour rate). Nothing says which was used.
- A separate rework rate exists and starts at 0; BOM "charges per piece" are shown but never posted.
- Locations are six auto-made names per factory that the code finds by exact name; stock moves between them invisibly.
- The lot page's "History" shows only route edits; "Corrections" is a row of unexplained links; "Change the route" stays open mid-production.
- Undo posts reversals, which he finds hard to predict. He wants a plain Delete.
- Journal narrations exist but are terse (no rate, no source of the rate).
- Pieces are whole numbers in most places but not all (stock movements, transfers, stock journals accept 3 decimals).

Success: a first-time user can open a lot, read what happened in order, see what each step cost and why, find the one screen where rates are set, delete a wrong entry and re-enter it, and never type 2.5 pieces.

## Goals

1. **One rate list** is the only place a process cost is defined.
2. **No rework rate, no BOM charges.**
3. **Journal entries read as plain sentences** with quantity × rate = amount and the rate's source.
4. **Three visible locations per factory**: Godown, Ready Goods, Rejects. Work in progress is shown by lot and step, not location.
5. **Delete, newest first**, truly removing the step and its journal entries.
6. **Lot page**: a lot diary replaces History and Corrections; the route is fixed after cutting except *who* does each step.
7. **Piece tags only after packing**; no bundle tags during production.
8. **Default logical checks** with plain messages.

## Non-goals

- No per-factory in-house rates now (same rate at all factories). The model must allow adding them later without rework.
- No salary / wage accounting for in-house workers (paid separately, as today).
- No mobile scanning (PWA already dropped).
- No change to sales, purchase or accounting screens beyond delete, narrations, locations and checks named here.

## Anti-goals (would make this a failure even if it works)

- Any screen still offering a rate field outside the Rates screen (route template, lot, challan line edit).
- A delete that leaves something behind the owner can see: a reversal entry, a "cancelled" voucher, a history row, a cost entry.
- A user having to pick a location to receive goods or pack.
- The word "Seconds" anywhere. It is **Rejects**.

## 1. Rates — the only place costs are defined

**Rate = who + process + rate per piece + effective from date.**

- *Who* is either an outside fabricator (a party) or **In-house**. In-house means "our own people, any factory". The model leaves room for a factory-specific in-house rate later. For now there is no factory field; it is a nullable party where null means in-house *(builder's call on the exact shape)*.
- Builds on the existing `jobwork.LabourRate` (dated, per party and process), which keeps its pay basis (accepted at QC / every piece received, CLAUDE.md rule 5).
- The rate in force on the work's date is the one used. A later-dated rate does not change work already recorded.
- **Remove rate fields** from: `RouteStep.rate`, `LotStep.rate`, `LotStep.rework_rate`, and every form or screen showing them (route template, lot "Change the route", challan).
- **Missing rate blocks the work.** No challan, in-house stage move, cutting or packing is saved when no rate exists for that who + process + date. The message names what is missing and links to the Rates screen, for example: *"No rate for Ramesh Stitching — Stitching on 19 Oct. Add one on Rates."*
- **Snapshot.** The rate used is still frozen on the record (challan line, cost entry) so later rate edits never change history.
- Rates can be **edited and deleted** on the Rates screen while no work has used them. A used rate can only be superseded by a new dated rate, and the screen says why.
- **Plain per-piece rates only.**
  - The rate types "per piece plus add-ons", "size-wise" and "flat per lot" are removed from the Rates screen and from new work.
  - Challans that already froze one of those types keep it until they are billed.
  - Migration *(builder's call)*: an add-on rate becomes its base per-piece rate, with add-ons dropped. A size-wise rate becomes its most common size rate. A flat-per-lot rate cannot be converted and is listed for the owner to re-enter. All three are reported in the migration output.
- **A reworked piece is never paid again.** On either pay basis, a piece is paid once at the challan's frozen rate.
  - Pieces sent back for rework and returned are not paid a second time.
  - Held-for-rework pieces that come back later are paid once, when they first count as paid under the basis.
  - The `rework_rate` field and the "rework at the rework rate alone" rule both go.
  - Rework stays visible as its own count, per the 15 Oct decision.
- **₹0 rates are allowed** *(builder's call)* for processes done by salaried staff, so "missing rate" never forces a made-up number. Migration creates a ₹0 In-house rate for any process with no route-step rate, and reports it.
- **Migration covers fabricators too** *(builder's call)*. Where a subcontracted route or lot step was paid through the route-rate fallback, create a fabricator rate from that step's rate, dated from the earliest challan that used it. Then no work is blocked on release.
- **BOM charges**: remove `BomCharge` and the "expected charges" display.
- **Migration of existing rates** *(builder's call; flag if ambiguous)*:
  - Each distinct process's route-step rate becomes an In-house rate, dated from the company's earliest data.
  - Where routes disagree on a process's rate, use the most common one and list the conflicts in the migration output for the owner.
  - Existing frozen rates on challans and cost entries are untouched.

**In-house labour accounting stays as today:** Dr Work-in-Progress / Cr Labour Absorbed (WIP), since wages are paid separately.

## 2. Plain journal entries

Every voucher a production or job work step posts gets a narration that reads as a sentence. Each line has a line narration too. Pattern: *what · who · lot · quantity × rate = amount · (rate from date)*. Examples:

- Fabric issue (if it posts): *"Fabric issued to lot L-12: Roll R-45, 60.00 m"*
- Cutting fabric: *"Fabric cut for lot L-12, Cutting 1: 58.40 m, ₹8,760"*
- In-house labour: *"Cutting in-house at Factory 1, lot L-12: 240 pieces × ₹1.50 = ₹360 (rate from 1 Oct 2026)"*
- Materials: *"Trims used at Stitching, lot L-12: zips 240, thread 4 cones, ₹1,120"*
- Job work bill: *"Stitching by Ramesh, lot L-12: 240 pieces × ₹12 = ₹2,880 (rate from 1 Oct 2026); TDS ₹29"*
- Packing to finished goods: *"Lot L-12: 230 pieces packed into Ready Goods at ₹96.40 a piece"*
- Inter-factory: *"Lot L-12 moved from Factory 1 to Factory 2: 240 pieces, ₹18,200 of work in progress"*

Each voucher also links back to the step that made it, and the step to its voucher(s), so the owner can click from a journal entry to the lot diary and back.

**Late labour bills** (posted after the lot is packed stay in WIP): **out of scope for this build** *(builder's call)*. Moving them into finished goods needs a stock revaluation and a sold / unsold split. It is a separate follow-up.

## 3. Locations

Each factory shows **three** locations:

| Location | Holds | Default for |
| --- | --- | --- |
| **Godown** | Fabric, trims, consumables, everything received | Every purchase / GRN, trims returned by fabricators, fabric remnants, sales returns of good pieces |
| **Ready Goods** | Packed finished pieces only | Packing; sales and dispatch take from here |
| **Rejects** | Rejected pieces kept (not scrapped) | QC "keep as rejects"; shown only once it holds something |

- The existing "Main Godown" becomes **Godown** and "Dispatch" becomes **Ready Goods** (rename existing rows; the physical area is one).
- **Defaults are filled in** on every form. A location select appears only if the factory has more than one location of that kind.
- **Internal locations** (cutting floor, process area, in transit, at fabricator) stay as bookkeeping but are **never shown or chosen**. Work in progress is described by lot and step: *"Lot L-12 · 240 pieces · at Stitching · with Ramesh"* or *"… on the way to Factory 2"*.
- **Stop finding locations by name.** Locations are found by kind (godown / ready goods / rejects / internal kinds) per factory, so renaming one breaks nothing. A factory may add another location (for example a second store), but never has to.
- **QC rejects** offer two choices each time: **Keep as rejects** (to Rejects stock) or **Scrap** (written off with the narration above).
  - Rejects stock stays quantity-only, as today: the pieces' cost stays in the lot and is carried by its good pieces.
  - Scrap is recorded as a loss with no voucher of its own, as today.
  - Selling from Rejects is **out of scope now** *(builder's call)*. It is a later piece of work, because it needs a stock choice on the sales bill and a value for rejected pieces.
- A **"Where is my stock"** view per factory: Godown, Ready Goods and Rejects by item, and work in progress by lot → step → with whom.

## 4. Delete — newest first, truly removed

The owner's decision, overriding CLAUDE.md rule 1 ("posted vouchers are never edited or deleted") and the "model history on every transactional model" stack note for this case. Update CLAUDE.md to say so.

**What can be deleted:**
- every recorded production / job work step: fabric issue, cutting (and its bundles), stage move, count, split, challan, receipt, approval, QC, packing
- labour bills
- hand-made entries: payments, receipts, journals, contra, and other voucher-type documents
- *(builder's call: the owner did not answer, but asked for flexible edits and deletes throughout)* sales and purchase documents too: sales bills, credit notes, packing lists and dispatches, goods received (GRN), supplier bills and debit notes. Each follows the same dependency rule. For example, a GRN whose rolls were issued can't be deleted until that fabric issue is.
  - E-invoice and e-way bill stubs: an invoice with an IRN or e-way bill number recorded is refused, with a message to cancel it on the portal first.

**Shared stock and multi-lot documents *(builder's call)*:**
- Deleting a step removes its stock movement and voucher at their original value. Later entries on other lots or SKUs are not revalued or rewritten. Average value at that location adjusts by the removed amount.
- Trial balance and stock value still agree, because both sides lose the same amount.
- A labour bill or payment covering several lots is deleted whole. The confirmation lists every lot it covers.

**Rules:**
- **Newest first per lot.** Only the latest step on a lot shows **Delete**. Earlier steps show: *"To delete this cutting, first delete: Challan JW-14 to Ramesh, then Move to Stitching"*, each item linked.
- A step something else depends on (a labour bill that used a QC result, a payment settled against a bill, a sale of packed pieces) must have that dependant deleted first, with the same message.
- **Confirmation page** lists exactly what goes, in plain words: *"Deleting this will: put 240 pieces back on challan JW-14 with Ramesh; remove ₹2,880 of stitching cost from lot L-12; delete journal entry JV-88."* Then **Delete** / **Keep it**.
- **What delete removes, in one `transaction.atomic()`:**
  - the step's working rows
  - its stock movements, with stock balances recomputed
  - its cost entries
  - its voucher(s) and voucher lines
  - bill-wise allocations
  - every history / audit row for all of these
  - the `ProductionAction` record

  No reversal voucher, no "undone" marker, nothing for any user (including an auditor) to find.
- After deleting, the user lands back on the lot with the previous state restored, ready to re-enter.
- **Guardrails *(builder's call, owner did not object)*:**
  - delete is refused inside a locked period
  - delete is refused while a payment is settled against the entry; the payment must be deleted first
- **Permission:** whoever may record a step may delete it (same as today's undo rule).
- **Numbers:** a deleted document's number is not reused; gaps in a series are accepted *(builder's call)*.
- **Replace undo.** The undo page, reversal-date choice and "undone" state go. Existing reversed pairs already in the data are left as they are.
- **Trial balance and stock must still reconcile** after any delete (tests).

## 5. Lot page

- **Lot diary** replaces "History" (route edits only) and "Corrections" (shortcut links). One list, oldest to newest, every recorded step in plain words, for example:
  - *14 Oct · Fabric issued: 2 rolls, 120 m · Suresh*
  - *14 Oct · Cut 240 pieces into 12 bundles · Suresh*
  - *15 Oct · Sent 240 pieces to Ramesh for Stitching (challan JW-14) · Suresh*

  Each line links to its record and voucher. The newest carries **Delete**. Money appears only for roles that may see cost (BR-15 / existing `can_cost`).
- **"Step by step" table stays** (pieces and cost per step). Its rate column shows the rate actually used and its source (*"Ramesh, from 1 Oct"*).
- **Route:**
  - Before cutting, the route is editable on the lot: add, remove, skip and reorder steps, with no rate fields.
  - After the first cutting, the "Change the route" panel disappears. The processes are fixed.
  - *Who* does a step is chosen when the work is sent: the fabricator on the challan, or in-house on the move.
  - The route's in-house / fabricator assignment becomes a default suggestion only.
- **Tags:**
  - No bundle QR tags during production. Remove the "Print their QR tags now" redirect after cutting and the tag link before packing.
  - Moves, challans and receipts pick bundles from a list (already possible).
  - After packing, the lot page offers **Print tags**: piece tags (style, colour, size, barcode), one per packed piece by size and colour, using the existing tag print. Box labels stay with packing.

## 6. Default checks

All with a plain message naming the field and the limit.

- **Whole pieces everywhere.** Validate in services (not only views), including `StockMovement`, `StockBalance`, `StockTransferLine` and `StockJournalLine` for piece items. Fabric and other measured materials keep decimals; the item's unit decides.
- **Quantities balance** (BR-21): out = into next + loss + rejects + shortage + held. Already enforced; clearer messages.
- **Can't exceed what exists:**
  - fabric issued ≤ roll balance
  - pieces sent ≤ bundle pieces
  - received + short + held ≤ sent
  - sold ≤ Ready Goods stock
  - transfer ≤ stock at source
- **Missing rate** blocks the work (section 1).
- **Dates:**
  - not in a locked period
  - not in the future
  - a receipt is not before its challan
  - QC is not before its receipt
  - a bill is not before its pieces were checked
- **Money:**
  - no negative rates or prices
  - a labour bill can't exceed the checked pieces × rate

## Constraints

- CLAUDE.md rules still apply except where section 4 overrides them:
  - Decimal only
  - one atomic transaction per posting
  - factory scoping on the server
  - tax optional
  - database-neutral (no raw SQL)
  - no MTO customer details to production roles
- Business logic in services; one service per document type.
- The help section and `docs/` setup guide are updated for every screen change (Rates, locations, delete, lot diary, tags).
- Tests per CLAUDE.md definition of done; acceptance tests A1–A12 stay green, with tests that relied on undo / reversal rewritten for delete.
- Owner's dev DB is real data: visual checks on a throwaway DB; JavaScript changes get a real browser check.
- Commit on `master`, small commits named by story ID.

## Left to the builder

- Order of work. A suggested order: rates (1) → narrations (2) → locations (3) → checks (6) → delete (4) → lot page (5), since the lot diary and delete share the step list.
- Exact model shape for in-house rates and the location "kind" lookup.
- How "Where is my stock" is laid out.
