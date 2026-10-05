# Garment Manufacturing ERP — build brief for Claude Code

Custom ERP for a track pant / jogger manufacturer and trader in Ludhiana, India: inventory, production with bundle tracking, job work with outside fabricators, sales, purchases, and full accounting — across multiple factories.

## Source documents (read before any work)

- `docs/BRD.md` — business requirements (v0.3). Requirement IDs: CRM-, SAL-, PRC-, TAX-, ADV-, PUR-, INV-, BAR-, PRD-, JOB-, MOB-, MST-, ACC-, RPT-, SYS-, BR- (business rules), NFR-.
- `docs/PRD.md` — product requirements (v0.3). Epics E1–E10 with user stories and acceptance criteria; lifecycles (Section 6); stack and build order (Section 10).

The PRD wins where the two differ. Do not invent requirements; if something is unclear, check the open questions (BRD Section 10, PRD Section 11) and ask me rather than guess.

## Stack

- Python 3.12+, Django 5.x, Django REST Framework
- Database: **SQLite for now**. Code must stay database-neutral so we can move to PostgreSQL later with a settings change and a data migration.
- Desktop UI: Django templates + HTMX; React only for the size-colour grid if HTMX is not enough
- Mobile: installable PWA on the same REST API (fabricator, supervisor, owner)
- Background jobs: start with Django management commands + cron; Celery/Redis later
- Model history / audit trail on every transactional model
- Tests: pytest + pytest-django

## Project layout (Django apps)

| App | Owns |
| --- | --- |
| `core` | Company, Factory, Location, User, Role, permissions, factory scoping, numbering series, period locks, setup wizard |
| `ledger` | Account groups, ledgers, vouchers, voucher lines, posting engine, bill-wise allocation, year-end |
| `tax` | GST / TDS switches with effective dates, tax templates, HSN and value slabs |
| `masters` | Style, SKU (style × colour × size), BOM (versioned), process, route template, parties, price lists |
| `inventory` | Stock movement ledger, rolls / lots, transfers, stock valuation, barcodes and labels |
| `production` | Production order, lot, route step, bundle, stage movement, cutting |
| `jobwork` | Job work challans, receipts, QC, labour rates and bills |
| `purchases` | PO, GRN with QC, purchase invoice, debit note |
| `sales` | Sale order, invoice, packing list, dispatch, credit note, advances |
| `reports` | Dashboards and reports (read-only over ledgers) |
| `api` | REST endpoints for the PWA |

## Non-negotiable rules

1. **Accounting**
   - Every voucher balances (debits = credits) and carries a factory, or it is not saved.
   - Posted vouchers are never edited or deleted — cancel or reverse only.
   - All money and quantities use `Decimal` (`DecimalField`), never float.
2. **One transaction per posting.** A source document, its stock movements and its GL voucher are saved inside one `transaction.atomic()` block. If any part fails, all of it rolls back.
3. **Tax is optional.** Nothing posts to GST or TDS ledgers unless the user selects a tax template or enters tax lines on that voucher. GST and TDS are independent of each other. Company switches have effective dates (PRD E1.9, E9.4).
4. **Quantities balance.** Every stage movement satisfies `qty_out = qty_in_next + loss + rejection + shortage` (BR-21). Moving back to an earlier stage requires a reason (BR-22).
5. **Pay follows acceptance.** Labour is computed only on QC-accepted pieces. A fabricator marking a bundle "Done" creates a pending receipt; it does not change stock or pay (MOB-03, JOB-07).
6. **Factory scoping is enforced on the server.** Every queryset for a user is filtered to their allowed factories; never rely on the UI to hide data (BR-23).
7. **Configuration over code.** Tax slabs, rates, routes, account groups, voucher series, print layouts and permissions live in the database, editable by an admin.
8. **Database-neutral.**
   - No raw SQL, PostgreSQL-only fields, or reliance on `select_for_update`, which SQLite ignores.
   - Generate document numbers with a counter table updated inside the posting transaction.
9. **Production data:** MTO customer name and phone are never exposed to production roles (BR-15).

## UI design — Excalidraw-inspired

The look and feel should resemble Excalidraw (excalidraw.com): calm, light, friendly, lots of white space, one violet accent. Take inspiration only — do not use Excalidraw's name, logo or assets.

Build the theme first as CSS custom properties in one file (`static/css/tokens.css`), with a dark theme on `[data-theme="dark"]`. Every template uses the tokens, never raw hex values.

**Colours (light theme)**

| Token | Value | Use |
| --- | --- | --- |
| `--color-primary` | `#6965db` | Primary buttons, active tab, selected row, links, focus ring |
| `--color-primary-darker` | `#5b57d1` | Primary hover |
| `--color-primary-darkest` | `#4a47b1` | Primary pressed |
| `--color-primary-soft` | `#ececf4` | Secondary buttons, hover backgrounds, pills |
| `--color-primary-pale` | `#e0dfff` | Selected / highlighted rows, active filters |
| `--color-bg` | `#ffffff` | Page background (white) |
| `--color-surface` | `#ffffff` | Panels ("islands"), cards, dialogs |
| `--color-ink` | `#1b1b1f` | Body text |
| `--color-muted` | a mid grey | Secondary text, labels |
| `--color-hairline` | a light grey | Borders, table rules |
| `--color-success` / `--color-warning` / `--color-danger` | soft green / amber / red | Status pills only (Posted, Pending, Overdue, Rejected) |

Derive the dark theme from the same tokens: dark grey background, slightly lighter panels, the primary lightened for contrast. Check WCAG AA contrast for text and buttons in both themes.

**Typography**

- UI and all data: **Assistant** (Google Fonts) with a system-ui fallback. Body 14–16px; labels 12–13px, weight 600.
- Use tabular figures (`font-variant-numeric: tabular-nums`) in every table and amount field. Right-align amounts and quantities.
- **Assistant only, everywhere** — no handwriting or decorative font (owner's decision, Oct 2026: it must look professional).

**Shape and layout**

- Content sits in floating "island" panels on the white page background: radius about 8px, soft low shadow, no heavy borders.
- Compact top bar with icon buttons (with tooltips) and a left navigation rail grouped by module.
- Buttons: radius about 8px. Primary is violet with white text; secondary is the soft lavender with ink text; ghost buttons for low-emphasis actions.
- Inputs: light hairline border with a violet focus ring. Generous padding on mobile; compact density on desktop data-entry screens.
- Tables: hairline row dividers, a sticky header, pale-violet selected row, zebra striping off.
- Optional sketchy touch: rough.js-style hand-drawn outlines on empty-state illustrations and dashboard chart frames only — never on inputs or data.
- **Light by default, always, on a white background** (owner's decision, Oct 2026: a dark screen is unacceptable). The dark theme stays available only as an opt-in toggle; the system dark-mode preference is ignored.
- Print styles (invoices, challans, labels) are plain black on white in Assistant, with no theme colours.

**Mobile PWA:** same tokens; bottom tab bar (the fabricator app has 3 tabs); large tap targets of at least 44px; a full-width violet scan button.

## Build order

Work strictly in this order. Finish each step — with its tests passing — before starting the next.

1. **Foundations.**
   - Project skeleton and base UI: design tokens, base layout (top bar, nav rail, island panels), login, light / dark toggle.
   - `core` with users, roles, factories, permissions and numbering.
   - `ledger` posting engine.
   - Setup wizard seeding account groups, garment expense ledgers, tax ledgers and default masters (PRD E1.1–E1.9).
2. **Masters.** Styles, SKUs, BOM versions, processes, route templates, parties, price lists (E2).
3. **Inventory and purchases.** Stock movement ledger, roll / lot receipt with GRN and QC, purchase invoice with optional tax, transfers between locations and factories (E5, E6).
4. **Production and job work.**
   - Production orders, cutting and bundles with QR codes.
   - Route planning with each step in-house or subcontracted.
   - Stage moves, rework, inter-factory WIP.
   - Challans, QC, labour bills (E7, E8.1–E8.4).
5. **Mobile PWA.** Fabricator app (3 tabs), supervisor scan screens, daily summary job, low-stock alert (E8.5–E8.8, E6.3).
6. **Sales.** Orders with size-colour grid, barcode billing, optional GST, packing and dispatch, credit notes (E4). Stub e-invoice / e-way bill behind an interface until a GSP is chosen.
7. **Accounting screens and reports.**
   - All voucher types and bill-wise settlement.
   - Trial balance, P&L and balance sheet per factory and consolidated, with drill-down.
   - Year-end close and period locks.
   - Dashboards and the standard reports (E9, E10).

Release 1 scope is PRD Section 9.1. Do not build Release 2 or 3 items unless I ask.

## Definition of done (every story)

- Acceptance criteria from the PRD story are covered by tests.
- After any test that posts transactions, the trial balance tallies and stock reconciles.
- Migrations created and applied; admin registered for new models.
- Permission and factory-scoping checks included.
- No float arithmetic on money or quantity.

## Acceptance scenarios

Write an end-to-end test for each of BRD scenarios A1–A12 (BRD Section 11.1) as soon as the features they need exist, and keep them green.

## Help Section

Whenever there is any change in the project backend or frontend, check the help section of the ERP and update as needed. Hence you should also update the setup guide in the docs folder.

## Working style

- Before starting a step, give me a short plan: the models, services and screens you'll build, plus any questions. Wait for my go-ahead on step 1 and on any change to the data model.
- Put business logic in service functions, not in views or model `save()`. Posting goes through one service per document type.
- Keep commits small and named after the story ID (e.g. `E7.5 bundle creation and QR labels`).
- Flag anything in the BRD/PRD that looks contradictory instead of choosing silently.
