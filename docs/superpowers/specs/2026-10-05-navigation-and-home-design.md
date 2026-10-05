# Navigation and home redesign (piece 1 of 3)

Date: 2026-10-05. Status: approved in conversation, awaiting written review.

## Problem

A first-time user who knows the garment business but not the ERP cannot find where to go. The menu has about 75 entries in 10 groups named after ERP modules, uses jargon (GRN, Challan, Contra), and the home screen shows numbers but offers nothing to do.

Designed for: the owner, who does every job. Role-trimmed views fall out of the existing permission checks.

This is piece 1 of three. Piece 2 (fewer steps per job) and piece 3 (lighter forms) get their own specs. This piece changes no entry form, merges no screens and changes no data model.

## Home: a job launchpad

Heading "What do you want to do?" followed by five islands of large buttons. Each button opens an existing screen.

| Island | Button | Opens (url name) |
| --- | --- | --- |
| Buy | Order fabric / material | `po_new` |
| Buy | Receive goods | `grn_new` |
| Buy | Enter a supplier bill | `invoice_new` |
| Make | Start a production order | `order_new` |
| Make | Cut a lot | `order_list` (pick the order, then cut) |
| Make | Send to fabricator | `challan_new` |
| Make | Receive from fabricator | `receipt_new` |
| Sell | Take an order | `saleorder_new` |
| Sell | Make a bill | `billing` |
| Sell | Pack and dispatch | `packing_new` |
| Money | Money received | `voucher_receipt` |
| Money | Money paid | `voucher_payment` |
| Money | Who owes me | `ageing_debtors` |
| Money | Whom I owe | `ageing_creditors` |
| Masters | New style | `style_new` |
| Masters | New material | `material_new` |
| Masters | New party | `party_new` |

A button is shown only if the user's role permits that screen, using the same check as the menu. An island with no permitted buttons is not shown.

**Needs your attention** sits below the islands: one line per pending item, each linking to the screen where it is dealt with. Lines with a zero count are omitted; if none remain, show "Nothing is waiting on you."

- Receipts from fabricators awaiting QC
- Lots past the order due date
- Draft production orders waiting to release
- Purchase orders to approve
- Goods receipts not yet posted
- Sale orders past due
- Items below minimum stock

All counts are factory-scoped on the server, reusing what `build_overview` already computes.

**Today at a glance** follows: the current stat tiles reduced to one row, then the items-in-production table. The "Active factories", "Posted vouchers" tiles and the recent-vouchers table are removed from home (still available under Money > All entries).

## Menu: nine groups in business words

| Group | Entries |
| --- | --- |
| Home | Home |
| Masters | Styles, Materials, Parties, Price lists; sub-heading **Setup**: Routes, Processes, Units / sizes / colours, HSN and GST slabs; Import from Excel |
| Buy | Purchase orders, Goods received, Supplier bills, Returns to supplier |
| Make | Production dashboard, Production orders, Move bundles, Sent to fabricators, Received from fabricators, Labour bills, Labour rates |
| Sell | Sale orders, Packing and dispatch, Bills, Quick billing (barcode), Returns from customer |
| Stock | Stock, Fabric rolls, Transfers, Low stock, Reorder levels, Print tags |
| Money | Money received, Money paid, Party accounts (ledger statement), All entries (voucher list) |
| Reports | Sales, Purchases, Finished stock, Fabricator reports, Daily summary, Who owes me, Whom I owe, Profit and loss, Balance sheet; sub-heading **GST**: GSTR-1, GSTR-3B, Tax register |
| More | sub-heading **Accountant**: Ledgers, Chart of accounts, Journal, Contra, Sales / Purchase vouchers, Debit / Credit note vouchers, Trial balance, Day book, Ledger book, Opening balances, Period locks, Year-end, Stock journal, Opening stock. Sub-heading **Settings**: Factories, Users, Roles, Tax / Inventory / Sales settings, Reset database. Help and user guide. |

Masters stays a top-level group, as today (owner's decision). No screen is removed from the menu.

## Wording

Renamed in the menu, launchpad and page titles only:

| Was | Now |
| --- | --- |
| Goods receipt (GRN) | Goods received |
| Purchase invoices | Supplier bills |
| Debit notes | Returns to supplier |
| Challans | Sent to fabricators |
| Receipts and QC | Received from fabricators |
| Sale invoices | Bills |
| Barcode billing | Quick billing (barcode) |
| Credit notes | Returns from customer |
| Receivables / Payables ageing | Who owes me / Whom I owe |

Printed documents keep their formal names (Challan, Tax Invoice, Credit Note, Debit Note). Document number prefixes and model names do not change.

Ctrl+K search matches the new label and the old term: each menu entry carries optional aliases ("GRN", "challan", "debit note", "invoice"...).

## Implementation

- `core/context_processors.py`: restructure `NAV`; entries gain an optional aliases tuple that flows into `nav_index`; update `ICONS` and `PREFIXES` to the new group names.
- `core/home_actions.py` (new): `HOME_ACTIONS` definition and `home_actions(user)` returning permitted islands and buttons.
- Overview service: add `attention_items(user)` returning `[{label, count, url}]`, built from existing queries.
- `templates/core/home.html`: rewritten. Tokens only, island panels, action buttons at least 44px tall, Assistant font.
- `static/css/base.css`: launchpad grid and action-button styles.
- Page `<h1>` titles on the renamed list screens updated to match.
- `docs/SETUP_GUIDE.md` and help anchors updated where they name menu paths.

## Tests

- Launchpad shows only actions the role permits; an island with none is hidden.
- Attention list counts respect factory scoping; zero-count lines are omitted.
- Every url name present in the old `NAV` is present in the new one.
- Search index contains old-term aliases.
- Existing UI tests asserting old menu labels are updated.

## Out of scope

Merging or chaining screens (piece 2), simplifying forms (piece 3), any model or posting change, mobile PWA.
