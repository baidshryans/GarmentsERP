# Product Requirements Document — Garment Manufacturing ERP

Oct 3, 2026 · @Shryans Baid

## 1. Overview

This PRD turns the agreed business requirements (BRD v0.3) into a build specification: who uses the product, what each feature does, how it should behave, and what "done" looks like. It is written for the product owner, designers, developers and testers.

**Product vision.** One system in which a track pant manufacturer can follow every metre of fabric and every bundle from purchase to cash — across multiple factories and outside fabricators — with accounts and GST produced as a by-product of daily work rather than a separate job.

| Item | Detail |
| --- | --- |
| Product | Garment Manufacturing ERP (working name) |
| First customer | Track pant / jogger unit, Ludhiana, 10 fabricators |
| Source | BRD v0.3 — requirement IDs (SAL-, PRD-, JOB-, MOB-, ACC-, SYS- etc.) are referenced throughout |
| Version | PRD 0.3 — custom build on Django; GST and TDS optional per voucher |
| Prepared by | Actuaria LLP |

### How to read this document

- Section 4 defines the core objects every feature works with.
- Section 5 is the heart of the PRD: one epic per module, each with user stories and testable acceptance criteria.
- Section 6 defines the status lifecycle of every document and of a bundle.
- Section 9 says what ships in each release; anything not in Release 1 is out of the MVP.
- Section 10 recommends the development platform.

### Goals and non-goals

**Goals for Release 1:** replace the Excel challan, stock and production registers; get all 10 fabricators on the mobile app; bill with barcode and GST; produce complete books with factory-wise trial balance.

**Non-goals:** machine-level shop-floor tracking, own e-commerce store, multi-currency, HR beyond payroll statutory reports.

## 2. Personas

| Persona | Who they are | What they need most | Device |
| --- | --- | --- | --- |
| Owner | Runs the business; decides rates, credit and approvals | Daily picture of output, stock, dues and profit without asking anyone; approvals on the phone | Phone, sometimes desktop |
| Accountant | Keeps books, files GST and TDS | Entries that post themselves, every voucher type when manual work is needed, clean GST reports | Desktop |
| Production supervisor | Issues and receives work with fabricators and in-house lines | Know what is where, scan bundles in and out, chase late lots | Phone |
| Cutting master | Lays fabric and cuts | Quick entry of pieces cut per size and waste, print bundle QR tags | Shared desktop or tablet |
| Store keeper | Receives and issues fabric, trims, finished goods | Roll / lot-wise stock, simple issue and transfer screens | Desktop with scanner |
| Billing / dispatch clerk | Makes invoices and packing lists | Scan or grid entry, GST and e-way bill without retyping | Desktop with scanner |
| Salesperson / agent | Takes dealer orders, follows up | Catalogue on WhatsApp, quick order entry, customer dues | Phone |
| Fabricator | Outside stitching unit owner; often limited English and a basic Android phone | See bundles given, mark progress, see what they will be paid | Phone |
| System administrator | Sets up company, factories and users | Guided setup, simple user and permission management | Desktop |

## 3. Product principles and key design decisions

These decisions shape every feature. Changing any of them later is expensive, so they should be agreed with the owner now.

1. **One entry, many effects.** A document is entered once; stock, WIP, party ledgers and GL are updated from it. No user ever posts the same event twice.
2. **The bundle is the unit of the shop floor.** Every cut bundle gets a QR. Every move, receipt, rejection and payment of labour is recorded against bundles, then rolled up to lot, production order and style.
3. **A process step is not tied to a place.** Each step on a route is assigned at run time to an in-house factory or a subcontractor. The same step can be done in-house for one lot and outside for the next (PRD-13).
4. **Quantities always balance.** Every stage movement satisfies: out = in at next stage + recorded loss / rejection / shortage (BR-21). The system refuses unbalanced moves.
5. **Pay follows acceptance.** Labour — in-house piece-rate or subcontractor — is earned on pieces accepted at QC, never on self-reported completion (JOB-07).
6. **Factory is a dimension on everything.** Every transaction carries a factory; reports run per factory and consolidated (ACC-13).
7. **Configuration over code.** Tax slabs, rates, process routes, account groups, voucher series and permissions live in masters an admin can change.
8. **Nothing is deleted.** Posted documents are cancelled or reversed, with a full audit trail (BR-16).
9. **Tax is applied by choice, not forced.** The business may not be GST registered or a TDS deductor today. GST and TDS are switched on per company from an effective date, and even then tax on purchase, expense and journal vouchers is selected or entered by the user on each voucher; defaults are only suggestions.

## 4. Core data model

Every feature reads from a small set of masters, creates documents, and those documents post to ledgers. Reports never hold data of their own; they read the ledgers.

&#91;embedded content: core architecture · masters, documents, ledgers, outputs\]

### Key entities

| Entity | What it represents | Key fields | Relationships |
| --- | --- | --- | --- |
| Company | A legal entity with its own books | Name, GSTIN(s), PAN, FY | Has many factories |
| Factory | A physical unit | Address, GSTIN, in-house processes, numbering series | Has many locations; tagged on every transaction |
| Location | Godown, cutting floor, process area, showroom, dispatch, or a subcontractor's premises | Type, factory or party | Holds stock |
| Style | A design | Style no., product code, image, default route, BOM (versioned) | Has many SKUs |
| SKU | Style × colour × size | Barcode, MRP, price-list rates | Stock is held per SKU |
| Fabric roll / lot | A roll or dye lot of fabric | Roll no., lot / shade, GSM, width, kg / m | Stock held per roll; issued to cutting |
| Production order | An instruction to make goods, for stock or a sale order | Styles, size ratio, qty, due date | Has many lots |
| Lot | One cutting of one style and colour | Fabric used, route, cost | Has many bundles |
| Bundle | A tied set of cut pieces | QR, size, colour, qty, current stage, current location | Moves through stage movements |
| Route step | One process on a lot's route | Process, sequence, optional flag, assignment (in-house factory or subcontractor), rate | Belongs to a lot |
| Stage movement | Any move of bundles between stages or locations | From / to stage, from / to location, qty out, qty in, loss, reason | Posts to stock / WIP and labour ledgers |
| Job work challan | Issue and receipt document with a subcontractor | Party, bundles, trims, rates, expected date | A type of stage movement |
| Party | Customer, vendor, fabricator, agent, transporter | GST, terms, rates, credit | Has a ledger |
| Voucher | Any accounting document | Type, factory, date, lines (Dr / Cr) | Posts to GL |
| User / role | A login and its permissions | Roles, factories allowed | Audits every change |

## 5. Feature specifications

Each epic lists user stories with acceptance criteria that testers will use as pass / fail checks. "R1", "R2", "R3" give the release (Section 9). BRD references are shown under each epic heading.

### E1. Setup and administration

BRD: SYS-01 to SYS-10, MST-11 to MST-13, BR-23.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E1.1 | As an admin, I run a setup wizard on first install so the system is ready to use | Wizard asks company name, address, PAN, GST registration status (and GSTIN only if registered), TDS deductor status (and TAN if any), FY start, books-from date. Cannot be skipped. On finish, the seeded groups, ledgers and masters below exist and the admin lands on the home screen | R1 |
| E1.2 | As an accountant, I get a standard chart of accounts without building it | Primary groups seeded: Capital, Reserves, Secured / Unsecured Loans, Current Liabilities, Duties and Taxes, Sundry Creditors, Provisions, Fixed Assets, Investments, Current Assets, Stock-in-hand, Sundry Debtors, Cash-in-hand, Bank Accounts, Loans and Advances, Sales, Purchases, Direct / Indirect Incomes, Direct / Indirect Expenses. Each group has a nature (asset, liability, income, expense) and a P&L or balance sheet flag | R1 |
| E1.3 | As an accountant, I get garment-unit expense and tax ledgers ready | Seeded ledgers include cash, CGST / SGST / IGST input and output, TDS and TCS payable, round-off, job work charges, embroidery / printing / washing charges, wages, salaries, power and fuel, factory rent, freight inward and outward, packing material, repairs, staff welfare, office, telephone, bank charges, interest, depreciation. Tax ledgers are created in every case but used only when a user applies tax on a voucher. All are editable; a ledger with entries cannot be deleted, only deactivated | R1 |
| E1.4 | As an admin, I add factories | Each factory has name, address, GSTIN (own or company's), locations, in-house processes, voucher series. A new factory appears in every factory filter immediately | R1 |
| E1.5 | As an admin, I add users and control what they see | User has mobile, email, one or more roles and allowed factories. A user without access to Factory 2 sees no Factory 2 data in any list, report or search | R1 |
| E1.6 | As an admin, I create custom roles | Permissions per screen (view, create, edit, cancel, approve) and per sensitive field (cost, margin, customer phone). Changes take effect at the user's next action | R1 |
| E1.7 | As an admin, I deactivate a user | Deactivated user cannot log in; their history and audit entries remain | R1 |
| E1.8 | As an owner, I run a second company | Second company has its own books and GSTIN; consolidated reports available to users with access to both | R2 |
| E1.9 | As an admin, I set the business's tax status and change it later | Per company (and factory, if GSTINs differ): GST registered yes / no and TDS deductor yes / no, each with an effective date. Switching on from a date enables GST fields, invoice series, e-invoice / e-way bill and tax reports from that date only; earlier documents are untouched. While off, tax fields are hidden on sales documents and optional on purchases and journals | R1 |

### E2. Masters

BRD: MST-01 to MST-10, INV-04, BAR-07.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E2.1 | As a merchandiser, I create a style with its colours and sizes | Creating style JGR-104 with 3 colours and sizes S–XXL generates 15 SKUs, each with a unique barcode | R1 |
| E2.2 | As a merchandiser, I define the BOM | BOM lines: fabric (type, GSM, consumption per piece by size), trims with qty per piece, fixed charges. Saving a changed BOM on a style already produced warns and creates a new version; old lots keep the old version | R1 |
| E2.3 | As a merchandiser, I set the default process route | Route is an ordered list of processes, each marked mandatory or optional, with a default assignment (in-house factory or subcontractor) and rate | R1 |
| E2.4 | As a user, I search any master quickly | Type-ahead search by code, name or phone returns results as I type | R1 |
| E2.5 | As a merchandiser, I make a set (tracksuit = jacket + pant) | Set has its own SKU; selling it reduces both components' stock | R2 |

### E3. Contacts and CRM

BRD: CRM-01 to CRM-14.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E3.1 | As a billing clerk, I add a customer | Firm name and mobile mandatory; GSTIN validated for format and its state code sets the customer's State. A mobile already on another customer is rejected with that customer's name | R1 |
| E3.2 | As a billing clerk, I see credit status while ordering | Customer card shows credit limit, outstanding, overdue and days; an order that breaches the limit warns, or needs approval if configured | R1 |
| E3.3 | As a salesperson, I log a lead on my phone | Lead form opens in under 3 taps; can attach design photos; follow-up date creates a reminder notification on that day | R3 |
| E3.4 | As a salesperson, I mark a lead lost | Lost reason is required, from a list or free text; lost-reason report available | R3 |

### E4. Sales, pricing and dispatch

BRD: SAL-01 to SAL-15, PRC-01 to PRC-07, TAX-01 to TAX-08, ADV-01 to ADV-07.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E4.1 | As a billing clerk, I enter an order as a size-colour grid | Grid shows colours as rows and the style's sizes as columns; row and column totals update live; Tab moves cell to cell | R1 |
| E4.2 | As a billing clerk, I scan goods to bill them | Each scan adds 1 pc of that SKU at the customer's rate; repeated scans increase qty; unknown barcode shows an error sound and message | R1 |
| E4.3 | As a billing clerk, I get the right price without looking it up | Rate is taken in this order: customer-specific style rate → customer price list with quantity slab → last rate to this customer; discount % applied; user can change within their allowed limit | R1 |
| E4.4 | As a billing clerk, I apply GST correctly when it applies | If the company is GST registered, the invoice suggests a GST template from the HSN slab (by per-piece value) and place of supply (CGST + SGST or IGST); the user can change or remove it on the invoice, and the change is logged. If not registered, no GST is charged and the document prints without tax. Totals round as configured | R1 |
| E4.5 | As a billing clerk, I raise e-invoice and e-way bill from the invoice | Shown only when the company is registered and e-invoicing is switched on. One click sends data; IRN, QR and e-way bill no. are saved on the invoice and printed; failures show the portal's error message | R1 |
| E4.6 | As a dispatch clerk, I dispatch part of an order | Packing list by carton with pieces per size; invoice covers only packed qty; order shows balance pending | R1 |
| E4.7 | As a production planner, I see MTO orders without customer identity | MTO order creates a production requirement showing style, qty grid, due date; customer name and phone are hidden for production roles | R1 |
| E4.8 | As an accountant, I adjust an advance against invoices | Advance can be linked to an order; on invoicing, it is offered for adjustment; the bill prints advance adjusted and balance due | R2 |
| E4.9 | As a dispatch clerk, I send goods on sale-or-return | Approval challan moves stock to the customer's location; after X days a reminder appears; return brings stock back, conversion creates an invoice | R2 |
| E4.10 | As an owner, I run a quarterly dealer scheme | Scheme defines target and rebate; at period end the system computes rebates and drafts credit notes for approval | R3 |

### E5. Purchases

BRD: PUR-01 to PUR-10.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E5.1 | As a purchase officer, I raise a PO | PO above the approval limit goes to the owner and cannot be sent until approved; pending PO report shows ordered vs received | R1 |
| E5.2 | As a store keeper, I receive fabric roll by roll | GRN against PO captures per roll: roll no., lot / shade, GSM, width, kg and / or metres. Each roll gets a stock record and a printable roll label | R1 |
| E5.3 | As a store keeper, I record QC on receipt | Each roll or line marked accepted, rejected or accepted with remark; rejected qty goes to a debit-note draft | R1 |
| E5.4 | As an accountant, I book the vendor bill from the GRN | Purchase invoice pulls GRN lines and rates. On each bill the user selects the tax — none, a GST template, reverse charge, or tax lines entered by hand — and whether input credit is claimable; if not claimable, the GST is added to item cost. TDS is deducted only if selected on the bill; a rate that differs from the last purchase rate is flagged | R1 |

### E6. Inventory and barcoding

BRD: INV-01 to INV-13, BAR-01 to BAR-08.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E6.1 | As an owner, I see stock anywhere | Stock enquiry by SKU, style, fabric or location shows qty per location, including at subcontractors and in transit | R1 |
| E6.2 | As a store keeper, I transfer stock between locations or factories | Transfer voucher moves stock; between factories with different GSTINs it creates a delivery challan or tax invoice as configured, with e-way bill | R1 |
| E6.3 | As an owner, I am alerted on low stock | When an item's stock falls below its reorder level, the owner gets an in-app and WhatsApp alert, once per crossing | R1 |
| E6.4 | As a store keeper, I print tags in bulk | Filter (e.g. black joggers, size M), choose quantity, print on the configured label printer with the configured tag layout | R1 |
| E6.5 | As a store keeper, I count stock | Count sheet by location; scanned counts compared with book; variances posted only after approval | R2 |
| E6.6 | As a salesperson, I share a catalogue | Filter styles, choose fields, generate PDF or WhatsApp share, including out-of-stock designs | R3 |

### E7. Production and process routing

BRD: PRD-01 to PRD-18, BR-01 to BR-05, BR-10, BR-21, BR-22.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E7.1 | As a planner, I create a production order | For stock or from an MTO order; one order can hold several styles; size ratio and total qty entered once and spread across sizes; latest BOM and route auto-filled | R1 |
| E7.2 | As a planner, I decide where each step happens | On each lot's route, every step is assigned to an in-house factory or a subcontractor, with rate; default comes from the style, editable until the step starts | R1 |
| E7.3 | As a planner, I change a route mid-way | Steps not yet started can be added, removed, skipped (if optional), reordered or reassigned; the change is logged with user and reason | R1 |
| E7.4 | As a cutting master, I issue fabric and record cutting | Issue by scanning roll labels; system blocks issue above roll balance and warns if rolls of different shade lots are mixed in one lot. Cutting entry records lay, pieces per size, fabric used, waste, remnant returned | R1 |
| E7.5 | As a cutting master, I create bundles with QR tags | Bundles generated from pieces per size with a chosen bundle size; each bundle has a QR tag showing lot, style, colour, size, qty, bundle no.; tags print at once | R1 |
| E7.6 | As a supervisor, I move bundles to the next stage | Scan bundles, choose next stage (default = next on route); if the stage is in-house, select factory / line; if outside, a job work challan is created. Each move records qty out and qty received | R1 |
| E7.7 | As a supervisor, I send bundles back for rework | Choosing an earlier stage requires a reason; rework rate applies; rework qty shown separately in WIP and cost | R1 |
| E7.8 | As a supervisor, I split or merge bundles | A split creates child bundles with new QR tags and quantities that add up to the parent; merge allowed only for the same lot, colour and size | R2 |
| E7.9 | As a supervisor, I move a lot to another factory | Inter-factory transfer of WIP with a delivery challan; the next stage continues at the receiving factory | R1 |
| E7.10 | As an owner, I see where everything is | Production dashboard: WIP by stage, factory and subcontractor; late lots; lot ageing; daily cut / stitched / packed; search by order, style, lot or customer reference shows current stage of every bundle | R1 |
| E7.11 | As an owner, I know true lot cost | Lot cost = fabric issued at cost + trims + in-house labour + job work + value-add charges + share of overheads (R2); variance against BOM shown, alert beyond tolerance | R1 (overheads R2) |

### E8. Job work and the fabricator app

BRD: JOB-01 to JOB-12, MOB-01 to MOB-08, BR-17.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E8.1 | As a supervisor, I issue bundles to a fabricator | Challan auto-fills from scanned bundles: style, sizes, qty, trims issued per BOM, rate, expected date; prints in English with challan no. and QR; posts to the fabricator's material ledger | R1 |
| E8.2 | As a supervisor, I receive goods back in parts | Receive by scanning bundles; partial receipt allowed; receipt above issue needs approval; shortage and missing trims recorded against the fabricator | R1 |
| E8.3 | As a QC checker, I accept or reject pieces | For each received bundle: accepted, rejected (reason), rework. Only accepted pieces move on; rejected pieces go to rejects stock or rework | R1 |
| E8.4 | As an accountant, I raise the fabricator's labour bill | Bill computed from accepted pieces × applicable rate (per piece, per piece + add-ons, size-wise, or flat per lot), less deductions for rejection, shortage and missing trims; TDS deducted only if selected on the bill (the fabricator's default section is a suggestion); posts to fabricator's account | R1 |
| E8.5 | As a fabricator, I log in to my app | Login with mobile and OTP; English UI; sees only own bundles and ledger | R1 |
| E8.6 | As a fabricator, I see and update my bundles | Lists Pending, In progress, Done, overdue. Scanning a bundle QR opens it; status can move Pending → In progress → Done. "Done" notifies the supervisor and creates a pending receipt — no stock or pay changes yet | R1 |
| E8.7 | As a fabricator, I see what I will be paid | Earnings by day and period from accepted pieces and rates, with deductions; read-only | R1 |
| E8.8 | As an owner, I get a daily summary on WhatsApp | At the configured time (default 6 PM), per fabricator: bundles and pieces issued, Done, accepted, pending, overdue, earnings for the day | R1 |
| E8.9 | As a fabricator with weak signal, I can still update | Status changes made offline are saved on the phone and sync when back online; conflicts resolved in favour of the supervisor's entry | R2 |

### E9. Accounting and compliance

BRD: ACC-01 to ACC-19, TAX-06, BR-16, BR-20, BR-24.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E9.1 | As an accountant, I never re-enter operational documents | Sales, purchases, GRNs, job work bills, transfers and payroll post vouchers automatically with the right ledgers and factory; tax lines are included only as chosen on the source document; each voucher links back to its source document | R1 |
| E9.2 | As an accountant, I post any manual entry | Voucher types: payment, receipt, contra, journal, sales, purchase, debit note, credit note, stock journal. A voucher cannot be saved unless debits equal credits and a factory is set | R1 |
| E9.3 | As an accountant, I settle bills properly | Receipts and payments allocate against specific bills, as advance, or on account; outstanding is bill-wise | R1 |
| E9.4 | As an accountant, I choose the tax on each voucher | No tax is applied automatically on purchase, expense or journal vouchers. On each one the user picks a tax template (none, a GST rate and type, reverse charge, a TDS / TCS section) or adds tax ledger lines by hand; the system calculates amounts from the template, and the user can override them with a reason. Party defaults are suggestions only. GST set-off and TDS payment entries are passed manually, with a helper that proposes them when registered / deducting. Tax applied is shown on the voucher and in a tax register | R1 |
| E9.5 | As an owner, I see books per factory and combined | Trial balance, P&L and balance sheet filter by factory or all; drill down from TB to ledger to voucher to source document | R1 |
| E9.6 | As an accountant, I reconcile the bank | Mark cleared entries by date or import a bank statement; reconciliation statement shows uncleared items | R2 |
| E9.7 | As an accountant, I manage cheques and assets | Post-dated cheques with due reminders; bounced cheque reversal; fixed asset register with depreciation entries | R2 |
| E9.8 | As an accountant, I close the year | Year-end carries forward balances; prior year can be reopened to post audit adjustments, which flow into the new year's opening balances | R1 |
| E9.9 | As an accountant, I lock a period after filing | Locked periods cannot be edited without owner unlock; unlocks logged | R1 |
| E9.10 | As an accountant, I file GST and TDS | Available for periods when the company is registered / deducting. GSTR-1 data (B2B, B2C, HSN summary, credit notes) and GSTR-3B summary export; TDS / TCS reports; ITC-04 for job work | R1 (ITC-04 R2) |

### E10. Reports, dashboards and payroll

BRD: RPT-01 to RPT-10, ACC-10, Section 9 of the BRD.

| ID | User story | Acceptance criteria | Rel. |
| --- | --- | --- | --- |
| E10.1 | As an owner, I open a home dashboard | Today's sales, collections, output (cut / stitched / packed), WIP by stage, overdue receivables, low-stock items; tapping any tile opens the detail | R1 |
| E10.2 | As anyone with access, I run standard reports | All reports in BRD RPT-01 to RPT-09 available with filters for factory, date, party, style; export to Excel and PDF | R1 |
| E10.3 | As an owner, I see profit by style | Style profitability = sales value − (fabric + trims + labour + job work + overheads) per piece, by period | R2 |
| E10.4 | As an accountant, I run payroll | Monthly, daily-wage and piece-rate workers; piece-rate wages from in-house accepted output; PF, ESI and professional tax reports | R3 |

## 6. Document and bundle lifecycles

Every document moves through fixed statuses. Stock and accounts are affected only at the status marked "posts"; before that, the document can be edited, after it only cancelled or reversed.

| Document | Statuses in order | Posts at | Notes |
| --- | --- | --- | --- |
| Bundle | Cut → At stage (in-house or subcontractor) → Done by fabricator → Received → QC accepted / rejected / rework → … next stage … → Packed → Dispatched | Every receipt and QC result | Can go back to an earlier stage with a reason; can be split or merged |
| Production order | Draft → Released → In production → Partly completed → Completed → Closed | — (lots post) | Closing writes off remaining WIP after approval |
| Job work challan | Draft → Issued → Partly received → Fully received → Billed → Closed | Issued, each receipt | Over-receipt needs approval |
| Purchase order | Draft → Pending approval → Approved → Partly received → Received → Closed | — | Short-close allowed with reason |
| GRN | Draft → QC done → Posted | Posted | Rejected qty creates a debit-note draft |
| Sale order | Draft → Confirmed → Partly dispatched → Dispatched → Closed | — | MTO orders create production requirements on confirmation |
| Invoice | Draft → Posted → E-invoiced → Paid / part-paid | Posted | Cancel within the e-invoice window, otherwise credit note |
| Sale-or-return challan | Issued → Partly returned / invoiced → Closed | Issued, each return | Reminder after configured days |
| Voucher (manual) | Draft → Posted → (Reversed) | Posted | Locked periods block posting |

### Bundle status on the fabricator app

The fabricator sees only three statuses — Pending, In progress, Done — which map to the bundle's "At stage" and "Done by fabricator" states. Only the supervisor's receipt and QC move the bundle further.

## 7. UX and screen requirements

### Desktop (office, store, billing)

- Keyboard-first billing and voucher entry: every field reachable by Tab, save with a shortcut, no mouse needed.
- Size-colour grid wherever quantities are entered by style (orders, invoices, production orders, purchases of finished goods).
- Scanner input works in any quantity screen without clicking into a field first.
- Every list has search, filters (factory, date, party, status), column choice and Excel export.
- Every report drills down to the document; every document links to its vouchers and source.
- Sensitive fields (cost, margin, customer phone) are hidden, not just greyed, for roles without permission.

### Mobile (owner, supervisor, salesperson, fabricator)

- Installable app on Android (and iOS for owner / sales); works on low-cost Android phones and screens around 5.5 inches.
- Large tap targets, QR scanning from the camera, minimal typing.
- Fabricator app: three tabs only — My bundles, Scan, Earnings. English UI with icons and numbers doing most of the work.
- Supervisor app: Issue, Receive, QC, Move, Lot search.
- Owner app: dashboard, approvals queue, outstanding, stock, daily summary.

### Key screens for Release 1

| # | Screen | Primary users |
| --- | --- | --- |
| 1 | Setup wizard | Admin |
| 2 | Home dashboard | Owner |
| 3 | Style, SKU, BOM and route master | Merchandiser |
| 4 | GRN with roll entry and QC | Store |
| 5 | Production order and route planner | Planner |
| 6 | Cutting entry and bundle / QR printing | Cutting master |
| 7 | Issue / receive / QC / move (desktop and mobile) | Supervisor |
| 8 | Job work challan and labour bill | Supervisor, Accounts |
| 9 | Fabricator app (3 tabs) | Fabricator |
| 10 | Sale order and invoice with grid and scanning | Billing |
| 11 | Packing list and dispatch | Dispatch |
| 12 | Voucher entry (all types) | Accounts |
| 13 | Ledger, trial balance, P&L, balance sheet with drill-down | Accounts, Owner |
| 14 | Users, roles and factories | Admin |

## 8. Integrations and non-functional requirements

### 8.1 Integrations

| Integration | Direction | Used for | Rel. |
| --- | --- | --- | --- |
| GST e-invoice (IRP via a GSP) | Out / in | IRN and signed QR on B2B invoices and credit notes | R1, used only if GST registered and above the e-invoice threshold |
| E-way bill (NIC via a GSP) | Out / in | E-way bills for invoices, job work challans and inter-factory transfers | R1, used when an e-way bill is required |
| GSTIN lookup | In | Validate customer and vendor GSTIN, fetch legal name and state | R1 |
| WhatsApp Business API | Out | Daily fabricator summary, low-stock alerts, invoices, statements, reminders, catalogues | R1 (alerts and summary), R3 (rest) |
| SMS / OTP gateway | Out | Login OTP for mobile users | R1 |
| Barcode / QR scanners and label printers | Device | Billing, receiving, bundle tags, roll labels | R1 |
| Bank statement import (CSV / Excel) | In | Bank reconciliation | R2 |
| Excel import templates | In | Opening data and masters migration | R1 |

### 8.2 Non-functional requirements

| Area | Requirement |
| --- | --- |
| Scale (first customer) | 2–5 factories, 30–50 users including 10+ fabricators, about 500 active SKUs, about 200 invoices and 1,000 bundle moves per day — to be confirmed with BRD Q14 |
| Performance | Scan-to-line under 1 second; invoice save under 2 seconds; standard reports for a month under 5 seconds |
| Availability | Cloud hosted, 99.5% monthly uptime; mobile apps tolerate short outages (offline queue in R2) |
| Security | HTTPS everywhere; OTP or password with lockout; role and factory permissions enforced on the server, not only in the UI |
| Audit | Every create, edit, cancel, approve and login logged with user, time and before / after values; logs cannot be edited |
| Backup | Automated daily backup with 30-day retention and off-site copy; restore tested every quarter; images stored separately |
| Data residency | Data hosted in India |
| Data ownership | All data exportable to Excel / CSV at any time |
| Maintainability | Tax slabs, rates, routes, account groups, permissions and print layouts configurable without code changes |
| Printing | A4 / A5 invoices and challans; 2-inch and 4-inch thermal labels for tags and rolls |

## 9. Release plan and success measures

### 9.1 Releases

| Release | Contents | Exit criteria |
| --- | --- | --- |
| R1 — Core operations (MVP) | E1 setup and admin; E2 masters; E3 customer master and credit; E4 orders, grid entry, scanning, GST, e-invoice, e-way bill, dispatch; E5 purchases; E6 stock, transfers, tags, low-stock alert; E7 production, routing, bundles, stage moves, inter-factory WIP, dashboard; E8 job work, labour bills, fabricator app, daily WhatsApp summary; E9 all vouchers, factory-wise books, GST and TDS reports, year-end; E10 dashboard and standard reports | BRD acceptance scenarios A1–A7 and A10–A12 pass on client data; Excel registers frozen; all 10 fabricators active on the app |
| R2 — Control and depth | Advances, sale-or-return, multiple companies, set SKUs, bundle split / merge, stock count, offline mobile, bank reconciliation, cheques and fixed assets, ITC-04, overhead absorption, style profitability | Scenarios A8 and A9 pass; month-end close done in the system without manual workbooks |
| R3 — Growth | CRM and leads, dealer schemes, catalogue sharing, WhatsApp statements and reminders, payroll, customer portal, marketplace sync (if confirmed) | Sales team logging leads daily; payroll run for one full month |

### 9.2 Success measures

| Measure | Target 3 months after R1 go-live |
| --- | --- |
| Parallel Excel registers still in use | Zero |
| Fabricators updating bundles on the app | All 10, at least daily |
| Fabric reconciliation by lot (received = issued + balance + waste + remnant) | Within 1% for every closed lot |
| Time to find the stage of any order | Under 30 seconds |
| Invoices with GST or e-way bill errors | Under 1% |
| Month-end books closed | Within 7 days of month end |
| Labour paid on pieces not accepted at QC | Zero |

## 10. Platform and technical approach

**Decision: a custom ERP built on Django**, the same stack as the team's existing ERP work, so patterns, components and know-how carry over. A packaged base (Frappe / ERPNext, Odoo) was considered and set aside in favour of full control over data model, workflows and UX. The trade-off is that accounting, tax and compliance are now ours to build and maintain, so they get the most design and test effort.

### 10.1 Technology stack

| Layer | Choice | Why |
| --- | --- | --- |
| Backend | Python, Django, Django REST Framework | Team familiarity; mature ORM, admin, auth; REST API serves desktop and mobile alike |
| Database | SQLite to start (development and pilot); PostgreSQL before multi-user production | Zero setup for the first build. Using only database-neutral Django ORM features keeps the later switch a settings change plus data migration. SQLite allows one writer at a time, so move before many users scan and post at once |
| Background jobs | Celery with Redis | Daily 6 PM WhatsApp summary, low-stock alerts, e-invoice / e-way bill calls, report exports |
| Desktop UI | Django templates with HTMX (or React for the heaviest screens such as the size-colour grid) | Fast, keyboard-first data entry without a heavy front-end build |
| Mobile | Installable PWA on the same API; Flutter only if a Play Store app or deep offline use is confirmed (BRD Q22) | One codebase for fabricator, supervisor and owner apps |
| Printing and labels | HTML-to-PDF for invoices and challans; ZPL / TSPL templates for thermal QR labels | Configurable layouts; direct printing to label printers |
| Audit trail | Model history on every transactional table | Before / after values for every change (BR-16) |
| Hosting | Cloud server in India, database (SQLite file at first, managed PostgreSQL later), automated backups; separate staging and production | Data residency, recovery |
| Integrations | GSP API for e-invoice and e-way bill; WhatsApp Business API provider; SMS / OTP gateway | Only paths available for these services |

### 10.2 Core engines we must build (and get right first)

These replace what a packaged ERP would have given us. They are built and tested before any feature screens that depend on them.

1. **Posting engine (general ledger).** Vouchers with lines; every line has ledger, factory, debit or credit, and reference to its source document. Posted vouchers are immutable — corrections by reversal only. Debits must equal credits in the same database transaction that saves the voucher. All amounts in fixed-point decimal.
2. **Chart of accounts and setup wizard.** Hierarchical groups with nature (asset, liability, income, expense); seed data for groups and garment ledgers loaded by the wizard (E1.1–E1.3); bill-wise sub-ledgers for parties.
3. **Tax engine (optional by design).** Company-level GST and TDS switches with effective dates; tax templates (GST rate and type, reverse charge, TDS / TCS section) that are applied only when chosen on a voucher; manual tax lines allowed; claimable vs non-claimable input GST. GST and TDS are independent of each other.
4. **Stock and WIP engine.** A single movement ledger for every quantity change (receipt, issue, transfer, stage move, consumption, production, sale, return), per SKU / roll / bundle and location; valuation method fixed at setup (weighted average recommended); every stock posting raises its GL posting in the same transaction.
5. **Routing and bundle engine.** Lots, route steps, bundles and stage movements with the balance rule (BR-21); in-house or subcontracted per step; split / merge; inter-factory moves.
6. **Permissions engine.** Roles with screen, action and field permissions, plus factory scoping enforced in every query on the server.
7. **Numbering and period control.** Voucher series per factory and FY; period locks; year-end close and reopen.

### 10.3 Reuse from existing work

Where the jewellery ERP already has working parts, port them rather than rewrite: barcode generation and label printing, GST invoice formats, job work issue / receive (the karigar flow maps to the fabricator flow), user and role handling. Each reused part is re-tested against this PRD's acceptance criteria.

### 10.4 Build order

| Step | Build | Why first |
| --- | --- | --- |
| 1 | Posting engine, chart of accounts, setup wizard, permissions, numbering | Everything else posts through these |
| 2 | Masters (styles, SKUs, BOM, routes, parties, factories) | Needed by every document |
| 3 | Stock engine; purchases and GRN with rolls | Raw material must exist before production |
| 4 | Production, cutting, bundles, routing, job work, labour bills | The product's core difference |
| 5 | Fabricator / supervisor PWA, WhatsApp summary, low-stock alert | Depends on bundles and job work |
| 6 | Sales, invoicing, dispatch; tax engine; e-invoice / e-way bill | Revenue side |
| 7 | Accounting screens, reports, dashboards, year-end | Reads everything above |

### 10.5 Engineering ground rules

- Every posting (stock and GL) happens in one database transaction with its source document; a failure rolls back both.
- An automated test suite reproduces BRD acceptance scenarios A1–A12 and runs on every change; trial balance must tally and stock must reconcile after every scenario.
- Accounting and tax logic is reviewed against worked examples by a qualified accountant before Release 1.
- GST and e-invoice rules live in configuration (slabs, HSN, thresholds, templates), not code.
- Migrations are reversible; production data is backed up before every release.
- Database-neutral code from day one: no raw SQL or PostgreSQL-only fields; money and quantities as Decimal; every posting inside one atomic transaction; document numbering that does not rely on row locks (which SQLite ignores). Switch to PostgreSQL when concurrent users grow or before production go-live, after the scenario tests pass on both.

## 11. Dependencies, risks and open questions

### 11.1 Open questions that affect the build

These come from BRD Section 10 and must be answered before the stories they affect are finalised.

| BRD Q | Question | Affects |
| --- | --- | --- |
| Q1 | Retail / online in scope? | POS billing screen, marketplace sync |
| Q3 | SKU barcodes and carton labels as well as bundle QR? | E4.2, E6.4 |
| Q6 | Is e-invoicing mandatory now? | E4.5 timing |
| Q14 | Volumes: SKUs, invoices, bundles, users | Hosting size, performance tests |
| Q16 | Is the AppSheet tracker a stopgap? | Migration (open bundles, QR numbers) |
| Q17 | QC step before ironing; outside processes used? | Default routes |
| Q18, Q19 | Actual rates; pay on QC acceptance confirmed? | E8.4 labour bill engine |
| Q22 | Branded Play Store app needed? | PWA vs Flutter |
| New | Is the business GST registered today? Does it deduct TDS (has a TAN)? Is there a plan or date to register? | E1.9 starting settings, E4.4, E4.5, E5.4, E9.4, E9.10, which integrations go live in R1 |

### 11.2 Dependencies

- GSP account for e-invoice and e-way bill APIs.
- WhatsApp Business API account and approved message templates.
- Label printers and scanners bought and installed before user training.
- Client to provide masters, opening stock by roll / lot, open challans and opening balances in the import templates.

### 11.3 Product risks

| Risk | Mitigation |
| --- | --- |
| Bundle-level tracking feels like extra work on the floor | QR scans instead of typing; supervisor app does moves in bulk; measure time per move in pilot |
| Fabricators do not adopt the app | Three-tab design, OTP login, earnings visible to them — the main reason to open it |
| Errors in the custom posting or tax engine produce wrong books | Build and test the engines first (Section 10.2); automated scenario tests that check trial balance and stock reconciliation; accountant review before go-live |
| Scope creep from Release 2 and 3 into the MVP | Change requests assessed against the release plan and success measures |
