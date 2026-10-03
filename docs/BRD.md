# Business Requirements Document — Garment Manufacturing ERP

Oct 1, 2026 · @Shryans Baid

## 1. Document control and how to review

This BRD restates, in business language, what the custom ERP must do for a track pants and joggers manufacturer and trader. Please confirm, correct or strike each requirement before design and build start; anything not confirmed here is treated as out of scope.

| Item | Detail |
| --- | --- |
| Document | Business Requirements Document (BRD) |
| Version | 0.3 — adds full accounting, first-install setup, multi-factory and flexible process routing |
| Source | Software Requirements Specification: Garment Manufacturing ERP |
| Prepared by | Actuaria LLP |
| Reviewer / approver | Business owner (name to be filled) |
| Next step | Owner marks up this document and answers Section 10; version 1.0 is issued for sign-off |

**How to review.** Each functional requirement carries an ID (for example SAL-06) and a priority:

- **Must** — the system is not usable for go-live without it.
- **Should** — important, but can follow in a later release if needed.
- **Could** — useful, deliver only if time and budget allow.

Please comment directly against any requirement ID that is wrong, missing detail, or at the wrong priority. Section 10 lists the decisions that block design; those need an answer first.

### Change log

| Version | Date | Change |
| --- | --- | --- |
| 0.3 | 2 Oct 2026 | Added: all accounting voucher types and factory-wise accounts (ACC-12 to ACC-19); first-install setup seeding account groups and ledgers, multiple factories and users (Section 6.14, SYS); every process selectable as in-house or subcontracted, and free movement of goods between stages and factories (PRD-13 to PRD-18). Related rules, masters, roles, acceptance tests and phasing updated. |
| 0.2 | 1 Oct 2026 | Client's fabricator-app note added (Section 2). Fabricator mobile app, bundle QR, daily WhatsApp summary and low-stock alert brought into scope and Phase 1. Open questions updated and new ones added (Section 10). |
| 0.1 | 1 Oct 2026 | First draft from the Garment ERP SRS |

## 2. Business background and objectives

The business, a track pant unit in Ludhiana (Punjab), manufactures and trades track pants, joggers and related knitwear in India, selling mainly B2B to wholesalers, distributors and retailers. It buys fabric and trims, cuts in-house, sends cut bundles to its 10 outside fabricators for stitching and value-add processes, finishes and packs goods, and dispatches against dealer and made-to-order (MTO) orders. It also buys finished goods for trading.

Today these activities are understood to run across separate Excel files (challans, stock register, production dashboard) and a separate accounting package. The ERP will replace them with one system where every challan, stock movement and invoice posts to inventory and accounts automatically.

### Business objectives

| # | Objective | How we will know it is met |
| --- | --- | --- |
| O1 | One integrated system for sales, purchase, inventory, production, job work and accounts | No parallel Excel registers for stock, challans or outstanding after go-live |
| O2 | Full control of fabric and trims from purchase to finished piece | Fabric ledger reconciles by roll / lot: received = issued + balance + cut waste + remnants |
| O3 | Visibility of every order and lot at every stage | Any order, style or lot can be traced to its current stage and fabricator in one search |
| O4 | Control over fabricators | Issued vs received, shortage, rejection and wastage reported per fabricator, with labour paid only on accepted pieces |
| O5 | Faster, error-free billing | Barcode scan and size-colour matrix entry; GST, e-invoice and e-way bill data generated automatically |
| O6 | Tight receivables management | Customer-wise outstanding and ageing, automated reminders, credit limit checks |
| O7 | Profit visibility | Profitability per style and Gross / Net Profit available mid-year without manual work |

### Client inputs received (1 Oct 2026)

The client shared a plan for a free no-code fabricator tracker built on Google Sheets and AppSheet, with a branded Android app or Glide as next options. It is a tool proposal, not a specification, but it confirms several requirements and shows the client's priorities: low cost, fabricators on mobile, and a simple daily view of output.

| Client said | What it tells us | Change in this BRD |
| --- | --- | --- |
| Free no-code app (Google Sheets + AppSheet); Flutter APK or Glide next | Cost-sensitive; wants something on fabricators' phones quickly | Fabricator mobile app brought into scope and Phase 1; Q16 asks whether the sheet is a stopgap or a substitute for the ERP |
| 10 fabricators, each with own login; app in English | Fabricator-facing access confirmed | Section 4 roles, MOB-01, NFR-10; Q8 partly answered |
| Five stages: Cutting → Fabricators → Iron / finishing → Stock → Dispatch | The client's view of the shop-floor flow; no separate QC or outside processes mentioned | Ironing named in the flow; Q17 confirms QC and value-add processes |
| QR scanner for bundles | The bundle is the unit tracked on the floor | Bundle QR made firm (BAR-02, PRD-06, MOB-02); Q3 partly answered |
| Status values: Pending, In Progress, Done | Simple three-state tracking per bundle | MOB-03 |
| Piece rate: Completed × 25 = Earning | Fabricators paid per piece; ₹25 is probably an example | MOB-05; Q4 partly answered; Q18 and Q19 confirm rates and the basis of pay |
| Daily WhatsApp summary of the 10 fabricators at 6 PM | Owner wants a daily push report, not only a dashboard | MOB-06; WhatsApp integration raised to Must; Q21 |
| Low-stock alert when Total\_Stock < 50 | Owner wants threshold alerts | INV-06 updated and raised to Must; Q20 asks stock of what |

## 3. Scope

The ERP covers thirteen modules that share one set of masters and post into one set of books. Items marked "to confirm" depend on the answers in Section 10.

### 3.1 In scope

| # | Module | Covers |
| --- | --- | --- |
| M1 | Contacts and CRM | Customer / lead master, lead tracking, follow-ups, WhatsApp communication |
| M2 | Sales and order management | Stock sales, MTO orders, sale-or-return, returns, dealer bulk orders, dispatch |
| M3 | Pricing | Price lists, customer discounts, quantity slabs |
| M4 | GST and statutory compliance | HSN-linked GST, CGST / SGST / IGST, e-invoice, e-way bill, GSTR-1 / 3B support, TDS / TCS, cash limit alerts |
| M5 | Advances, credit and dealer schemes | Customer advances, credit notes, scheme rebates, statements |
| M6 | Purchases | Fabric (roll / lot), trims, finished goods, packing material, POs, GRN with QC, debit notes |
| M7 | Inventory and catalogue | Raw material, WIP, finished goods, rejects; transfers; reorder levels; BOM; catalogue |
| M8 | Barcoding and tagging | SKU barcodes, tag printing, bulk printing, reissue |
| M9 | Production management | Production orders, cutting, bundles, process routing with each step in-house or subcontracted, stage-to-stage and inter-factory movement, dashboard |
| M10 | Job work (fabricator) management | Job work challans, partial receipts, labour rates, deductions, shortage and rework; fabricator mobile app with bundle QR scanning |
| M11 | Masters | Product, style, fabric, colour, size, trims, process, HSN, ledgers |
| M12 | Accounting, payroll and reports | Double-entry accounts with all voucher types, factory-wise and consolidated books, ledgers, ageing, P&L, balance sheet, GST reports, PF / ESI / PT, MIS |
| M13 | System setup and administration | First-install wizard seeding account groups, ledgers and defaults; companies, factories, users, roles and permissions; numbering series |

### 3.2 Out of scope (unless the owner adds them)

- Machine-level shop-floor tracking (line balancing, operator-wise SAM / efficiency) — production is tracked at bundle and lot level only.
- Own e-commerce storefront; marketplace order sync (Amazon, Flipkart, Myntra) unless confirmed in Section 10.
- Full HR administration beyond payroll statutory reports (recruitment, appraisals, leave workflows).
- Multi-currency export invoicing — all transactions are in INR.
- A separately branded Play Store app, unless confirmed in Section 10 (Q22).

### 3.3 To confirm

- Retail showroom and online sales (POS-style billing) — or B2B only.
- Whether any job work income is earned (stitching for others).
- Barcode level: bundle QR is confirmed; whether SKU barcodes for billing and carton labels are also needed.
- Whether the Google Sheets / AppSheet tracker is a stopgap until go-live or the client's preferred route (Q16).

## 4. Stakeholders and user roles

Access is role-based: each user sees only the screens, fields and actions their role needs. The owner should confirm the roles below and name the people in each.

| Role | Main tasks in the ERP | Key restrictions | Mobile access |
| --- | --- | --- | --- |
| Owner / Director | Approvals, dashboards, profitability, all reports | None | Yes |
| Accounts | Vouchers, receipts, payments, GST, TDS, payroll, year-end | Cannot edit production quantities | No |
| Sales / agent | Leads, follow-ups, quotations, sale orders, catalogue sharing, own customer outstanding | Sees own customers only; no cost or margin fields | Yes |
| Billing / dispatch | Invoices, packing lists, e-way bill, LR / transporter entry | Cannot change rates beyond allowed discount | Optional |
| Purchase | POs, vendor rates, GRN entry | PO above set value needs owner approval | No |
| Store / godown | Fabric and trims receipt, issue, transfers, stock counts | Cannot see sale prices | Optional |
| Cutting master | Lay details, pieces cut per size, cut waste, remnants | Production screens only | Optional |
| Production supervisor | Bundle issue / receipt with fabricators, stage updates, QC results | Sees order specs, not customer name or phone | Yes |
| QC / ironing and finishing | Accept / reject pieces, rework issue, ironing and finishing output | QC screens only | Optional |
| Fabricator (external) | Scan bundle QR, update bundle status, view own pending bundles, earnings and ledger | Own bundles only; cannot change issued quantities or rates | Yes — 10 fabricators, own logins (confirmed) |
| Customer / dealer (external) | View ledger, dues, statements via WhatsApp or portal | Read-only, own data only | Via WhatsApp |
| System administrator | First-install setup, companies, factories, users, roles and permissions, numbering series, backups | Cannot post transactions unless also given an operating role | No |

**Rule carried from the SRS:** on an MTO order, production users see style, quantity, size / colour and delivery date, but never the customer's name or phone number.

**Multiple factories and users.** The business can add any number of factories and users. Each user is given one or more roles and access to one or more factories, and sees only the data of the factories assigned (owner and accounts can be given all).

## 5. End-to-end business process

The ERP links four cycles — buy, make, job work and sell — through one stock and one set of books, so no step is re-entered in a separate register.

&#91;embedded content: end-to-end process · purchase, production, job work, sales\]

A made-to-order sale order raises a production order directly; ready-stock orders bill from finished goods. Pieces rejected at QC go back to the fabricator as rework, and labour is paid only on accepted pieces.

Optional value-add processes (embroidery, printing, washing, dyeing) sit between cutting and finishing and can run through several issue and receive cycles with different vendors. Every step shown — cutting, stitching, value-add, ironing, finishing, packing — can be run in-house at any of the business's factories or sent to a subcontractor, and goods can move forward, skip optional steps, go back for rework, or move between factories.

## 6. Functional requirements

Requirements are grouped by module. Priority reflects our reading of the SRS; the owner should change any that are wrong.

### 6.1 Contacts and CRM (CRM)

| ID | Requirement | Priority |
| --- | --- | --- |
| CRM-01 | Customer master with mandatory Firm Name and Mobile; optional contact person, two alternate mobiles, landline, email | Must |
| CRM-02 | One billing address and multiple shipping addresses per customer | Must |
| CRM-03 | GSTIN, PAN and State captured; State decides CGST + SGST or IGST automatically | Must |
| CRM-04 | Customer category: Wholesaler, Distributor, Retailer, Online Seller, Walk-in, Institutional | Must |
| CRM-05 | Assigned price list and customer discount %, auto-applied at billing and editable within limits | Must |
| CRM-06 | Credit limit, credit days and payment terms per customer, with a warning when a new order breaches them | Must |
| CRM-07 | Reference / care-of / agent, transporter preference and destination | Should |
| CRM-08 | One mobile number maps to only one customer across all outlets and godowns; duplicates blocked | Must |
| CRM-09 | Birthday / anniversary and "notify for new designs" flag for greetings and launches | Could |
| CRM-10 | Mobile-friendly lead entry: product interest, reference, season / occasion, designs (style no. or photo), expected quantity, competitor quoted, closing probability (1–3 stars), notes | Must |
| CRM-11 | Predefined lead sources: Reference, Trade fair, Agent, WhatsApp / social, Marketplace, Walk-in, Cold call, Repeat customer | Should |
| CRM-12 | Lost reason from a predefined list plus free text | Should |
| CRM-13 | Follow-up reminder to the salesperson on the due date | Must |
| CRM-14 | WhatsApp sending of catalogues, price lists, order confirmations, dispatch updates and payment reminders | Should |

### 6.2 Sales and order management (SAL)

| ID | Requirement | Priority |
| --- | --- | --- |
| SAL-01 | Find a customer by name or phone when starting a bill or order | Must |
| SAL-02 | Sale types: ready stock, made to order (MTO), sale-or-return / consignment, sales return / rejection (credit note) | Must |
| SAL-03 | Scan barcode / QR at billing to pull style, colour, size and rate | Must |
| SAL-04 | Size-colour matrix entry: colours as rows, sizes (S–XXL) as columns, on one screen | Must |
| SAL-05 | Invoice shows style no., description, HSN, size / colour breakup, pieces, rate, discount, taxable value, GST, transport details, e-invoice / e-way bill fields | Must |
| SAL-06 | Salesperson / agent, style no., order reference and remarks on each order, for commission and performance reports | Must |
| SAL-07 | Bulk dealer orders with partial dispatch and a pending-order (order book) report | Must |
| SAL-08 | Packing list by carton with piece count per size | Must |
| SAL-09 | Transporter and LR number recorded against each dispatch | Must |
| SAL-10 | Sale-or-return: goods sent on approval, follow-up reminder after X days, then return or convert to invoice | Should |
| SAL-11 | MTO order creates a production requirement visible to production without customer identity | Must |
| SAL-12 | Historical rate report per customer and per style | Should |
| SAL-13 | Show / hide selected fields (cost, internal codes) on the customer copy | Should |
| SAL-14 | Daily sales report with style thumbnails, quantity and value | Should |
| SAL-15 | Customer-wise outstanding and ageing visible at order entry | Must |

### 6.3 Pricing (PRC)

| ID | Requirement | Priority |
| --- | --- | --- |
| PRC-01 | Price lists: MRP, Wholesale, Distributor, Retail and customer-specific special lists | Must |
| PRC-02 | Selling price = base rate per piece (by style and size) − customer discount + other charges (packing, freight) | Must |
| PRC-03 | Rate per customer per style, or per customer per category | Must |
| PRC-04 | Quantity slab pricing (e.g. 100+ pcs, 500+ pcs) | Should |
| PRC-05 | Same style may carry different prices for different customers | Must |
| PRC-06 | Price changes apply only to orders created after the change | Must |
| PRC-07 | Last rate auto-applied on repeat orders, editable at billing | Must |

### 6.4 GST and statutory compliance (TAX)

**Tax is optional and chosen per voucher.** The business may not currently be GST registered or a TDS deductor. GST and TDS are switched on per company from an effective date. Even when switched on, the system only suggests tax: on sales the user can change the suggested GST, and on every purchase, expense and journal voucher the user selects the GST template, reverse charge or TDS section, or enters tax lines by hand. Nothing is posted to tax ledgers unless chosen. The requirements below apply once GST is switched on.

| ID | Requirement | Priority |
| --- | --- | --- |
| TAX-01 | GST rate suggested from the item's HSN code, changeable on each document | Must |
| TAX-02 | Value-based GST slabs for apparel (rate depends on sale value per piece) held as configurable slabs in the HSN master, not hard-coded | Must |
| TAX-03 | Tax rate changes in the master apply to future bills only | Must |
| TAX-04 | CGST + SGST for intra-state and IGST for inter-state, decided by customer State | Must |
| TAX-05 | E-invoice (IRN / QR) and e-way bill data generated from the invoice | Must (if turnover requires) |
| TAX-06 | GSTR-1 and GSTR-3B support reports; TDS / TCS reports | Must |
| TAX-07 | Alert when cash receipts from a party cross a configurable limit in a financial year | Must |
| TAX-08 | GST on job work challans (goods sent to and received from fabricators) tracked for ITC-04 purposes | Should |

### 6.5 Advances, credit and dealer schemes (ADV)

| ID | Requirement | Priority |
| --- | --- | --- |
| ADV-01 | Record customer advances, either general or against a specific order | Must |
| ADV-02 | Adjust advances against one or more invoices, with the trail printed on the final bill | Must |
| ADV-03 | Credit notes for returns, rejections, rate differences and discounts | Must |
| ADV-04 | Dealer schemes — volume- or period-based (e.g. quarterly target rebate) — calculated and posted automatically | Should |
| ADV-05 | Customer statement (ledger, due dates, outstanding) shareable on WhatsApp or a portal | Should |
| ADV-06 | Reports: expected collections this week / month; overdue parties | Must |
| ADV-07 | Interest on overdue receivables at a configurable rate | Could |

### 6.6 Purchases (PUR)

| ID | Requirement | Priority |
| --- | --- | --- |
| PUR-01 | Purchase types: fabric, trims and accessories, finished goods (trading), packing material | Must |
| PUR-02 | Fabric purchase by kg or metre with roll-wise entry: roll no., GSM, width, shade / lot no., shrinkage % | Must |
| PUR-03 | Shade / dye-lot tracking mandatory on fabric, carried through to cutting so one order is not cut from mixed lots | Must |
| PUR-04 | Trims bought per piece, gross, metre or kg, with unit conversion | Must |
| PUR-05 | Finished goods purchase by style and size-colour matrix, rate per piece, tax | Must |
| PUR-06 | Last purchase rate per vendor per item auto-fetched; variance flagged when the rate changes | Must |
| PUR-07 | Purchase orders with an approval workflow and a pending-PO report | Must |
| PUR-08 | GRN with QC on receipt: fabric defects, shortage, shade variation | Must |
| PUR-09 | Purchase return / debit note | Must |
| PUR-10 | Vendor master with GST details, payment terms and rate contracts | Must |

### 6.7 Inventory and catalogue (INV)

Stock is held in four categories, each by location:

| Category | Includes | Tracked by |
| --- | --- | --- |
| Raw material | Fabric rolls / lots, rib, trims, packing material | Roll / lot, kg or metre, piece |
| Work in progress | Cut panels, bundles at each process, goods with fabricators | Production order, bundle, process, fabricator |
| Finished goods | Ready garments | Style, colour, size, location |
| Rejects / seconds / remnants | Rejected pieces, seconds, fabric remnants, cut waste | Source order, fabricator, kg / pieces |

| ID | Requirement | Priority |
| --- | --- | --- |
| INV-01 | Live stock across all four categories by location (godown, cutting, fabricator, showroom, dispatch) | Must |
| INV-02 | Stock transfer between locations with transfer vouchers | Must |
| INV-03 | Fabric ledger per roll / lot: received, issued to cutting, balance, cut waste, remnants | Must |
| INV-04 | Style BOM: fabric (type, GSM, consumption per piece), rib / cuff, drawcord, elastic, zipper, label, thread, polybag, carton, and fixed charges (embroidery, printing, washing) | Must |
| INV-05 | Last-used BOM and job work rates auto-populate a new production order for the same style | Must |
| INV-06 | Min / max and reorder levels for raw materials and finished styles, with approval before production is released; alert to the owner when stock falls below the set level (client example: 50) | Must |
| INV-07 | Wastage / rejection tracked per fabricator against an acceptable limit; alert and penalty when exceeded | Must |
| INV-08 | Stock reports: style / colour / size-wise, location-wise, ageing, slow-moving | Must |
| INV-09 | Prompt (and block, per settings) on negative stock | Must |
| INV-10 | Image catalogue filterable by category, fabric, colour, size, price range and availability; shows designs even when out of stock | Should |
| INV-11 | Catalogue export to PDF and WhatsApp share, choosing which fields to show | Should |
| INV-12 | Same style can hold different cost and selling prices by source (own production vs purchased) | Must |
| INV-13 | Periodic physical stock count with variance posting after approval | Should |

### 6.8 Barcoding and tagging (BAR)

| ID | Requirement | Priority |
| --- | --- | --- |
| BAR-01 | Numeric barcode (configurable length) per SKU = style + colour + size | Must |
| BAR-02 | Barcodes generated when a production lot is completed, when finished goods are purchased, per bundle as a QR tag printed at cutting (confirmed by client), and per carton if enabled | Must |
| BAR-03 | Order-specific goods may carry the order number on the tag | Should |
| BAR-04 | Bulk printing after a filter (e.g. all black joggers, size M) | Must |
| BAR-05 | Configurable tag layout per product type: style, size, colour, MRP, brand, fabric, wash care, barcode | Must |
| BAR-06 | Reissue barcode for returns and re-packing | Should |
| BAR-07 | Style hierarchy Style → Colour → Size; sets (e.g. tracksuit = jacket + pant) with separate or linked barcodes and a set description on the bill | Should |
| BAR-08 | Style image attached (compressed in the app, original kept on server disk so backups stay small) | Should |

### 6.9 Production management (PRD)

| ID | Requirement | Priority |
| --- | --- | --- |
| PRD-01 | Production order for own stock or against a buyer order (MTO) | Must |
| PRD-02 | Order specs: style, fabric, colour, size ratio, total quantity, expected delivery, finish, trims, special instructions | Must |
| PRD-03 | One production order may hold several styles (e.g. Order 101: 101(a) Jogger, 101(b) Track pant), each issued to different fabricators | Must |
| PRD-04 | Fabric issue to cutting by roll, from available stock only | Must |
| PRD-05 | Cutting entry: lay details, pieces cut per size, fabric consumed, cut waste, remnant returned to store | Must |
| PRD-06 | Bundle / ticket system: each bundle has a number, size, colour and quantity and a printed QR tag, and moves through processes; scanning the QR updates its stage | Must |
| PRD-07 | Configurable process route per style; optional embroidery, printing, washing and dyeing with multiple issue / receive cycles | Must |
| PRD-08 | Ironing and finishing (thread cutting, pressing), QC, packing and barcode before dispatch | Must |
| PRD-09 | Acceptable BOM variance (e.g. fabric consumption ±x%) with alerts when exceeded | Should |
| PRD-10 | Track the stage of any lot or order by order no., style or customer reference | Must |
| PRD-11 | Production dashboard: orders by stage, pending at each fabricator, lot ageing, late / completed / upcoming orders, daily cut-stitched-packed output | Must |
| PRD-12 | Alert when production lead time exceeds the customer's promised delivery date | Should |
| PRD-13 | Every process (cutting, stitching, embroidery, printing, washing, dyeing, ironing, finishing, packing) can be done in-house at any factory or subcontracted to a job worker. The choice is made per production order, per lot or per bundle, and can differ for the same process across lots | Must |
| PRD-14 | In-house steps record factory, line or worker, output and labour (piece-rate or daily wage); subcontracted steps use job work challans (JOB). Both are costed into the lot so style costing is the same either way | Must |
| PRD-15 | Default process route per style, editable per lot: add, remove, skip or reorder steps | Must |
| PRD-16 | Goods can move between any stages: forward, skipping optional steps, or back to an earlier stage (rework, re-wash, re-press). Bundles can be split and merged. Each movement is recorded with a voucher, and quantities in and out of each stage balance | Must |
| PRD-17 | Transfer of fabric, trims, WIP and finished goods between factories by stock transfer / delivery challan, with e-way bill where required; a stage started in one factory can continue in another or at a subcontractor | Must |
| PRD-18 | WIP visible at any time by factory, stage, subcontractor, style and order, with in-house vs subcontracted split | Must |

### 6.10 Job work / fabricator management (JOB)

| ID | Requirement | Priority |
| --- | --- | --- |
| JOB-01 | Job work challan to issue cut panels and trims; challan auto-fills style, size, quantity, rate and expected date | Must |
| JOB-02 | Receipt of stitched goods against the challan, with partial receipts | Must |
| JOB-03 | Every challan must reference a production order | Must |
| JOB-04 | Warning if a lot already open with one fabricator is issued to a second fabricator | Must |
| JOB-05 | Fabricator ledger in two parts: (a) material / cut pieces issued, (b) goods in process | Must |
| JOB-06 | Labour rate types per fabricator: A per piece; B per piece + add-ons (embroidery, finishing); C size-wise; D flat per lot | Must |
| JOB-07 | Labour paid only on pieces accepted at QC, with deductions for rejection, shortage and missing trims | Must |
| JOB-08 | Shortage / loss report per fabricator: pieces and trims issued vs received | Must |
| JOB-09 | Rework: rejected pieces re-issued with rework charges | Must |
| JOB-10 | Later processes (washing, embroidery) issued to different vendors at their own rates | Must |
| JOB-11 | Fabricator bill / labour statement generated from accepted quantities, posted to the fabricator's account with TDS where applicable | Must |
| JOB-12 | Ageing of material lying with each fabricator | Should |

### 6.10A Fabricator mobile app (MOB) — added from client inputs

| ID | Requirement | Priority |
| --- | --- | --- |
| MOB-01 | Individual mobile login for each fabricator (10 at present), English interface | Must |
| MOB-02 | Scan a bundle's QR to open it: style, colour, size, quantity, challan no. and expected date | Must |
| MOB-03 | Update bundle status: Pending → In progress → Done. "Done" raises a pending receipt for the supervisor to count and QC; it does not add to stock by itself | Must |
| MOB-04 | Fabricator sees own pending, due-today and overdue bundles | Must |
| MOB-05 | Earnings view by day and period: accepted pieces × piece rate, less deductions; rates come from the ERP and cannot be edited on the app | Must |
| MOB-06 | Daily WhatsApp summary to the owner at a set time (client asked for 6 PM): per fabricator — bundles and pieces issued, done, accepted, pending, and earnings | Must |
| MOB-07 | Supervisor view of all fabricators' bundle status, with the same QR scan to receive goods | Must |
| MOB-08 | Usable on low-cost Android phones; entries made without signal sync when the connection returns | Should |

**Basis of pay.** The client's formula pays on pieces marked Completed. This BRD keeps JOB-07: pay is calculated on pieces accepted at QC, so a fabricator cannot be paid for pieces still short, rejected or not yet received. Q19 asks the owner to confirm.

### 6.11 Masters (MST)

| ID | Master | Key contents | Priority |
| --- | --- | --- | --- |
| MST-01 | Product | Internal codes: TRK Track pant, JGR Jogger, TSH T-shirt, SET Tracksuit | Must |
| MST-02 | Design / style | Style no., image, BOM, rates; version history kept when a re-made style's BOM changes (latest overwrites after a warning) | Must |
| MST-03 | Fabric | Type, composition, GSM, width | Must |
| MST-04 | Colour and size | Colours; sizes S–XXL, free size, kids sizes | Must |
| MST-05 | Trims | Zipper, elastic, drawcord, label, tag, thread, polybag, carton, with units | Must |
| MST-06 | Process | Cutting, stitching, embroidery, printing, washing, pressing, etc. | Must |
| MST-07 | HSN / tax | HSN codes and value-based GST slabs | Must |
| MST-08 | Ledgers | Customer, vendor, fabricator (with codes), agent, transporter | Must |
| MST-09 | Discount | Discount by customer type | Should |
| MST-10 | Style archive | Discontinued styles remain searchable with full history | Should |
| MST-11 | Company and factory | Company GSTIN(s), PAN, FY; factories with address, GSTIN, godowns / process areas, in-house processes available, numbering series | Must |
| MST-12 | Chart of accounts | Account groups (multi-level) and ledgers, seeded at first install (SYS-02, SYS-03) and fully editable | Must |
| MST-13 | Voucher type and numbering | Voucher types with prefix / series per factory and FY (separate tax-invoice series from the GST effective date); custom voucher types based on standard ones | Must |

### 6.12 Accounting and payroll (ACC)

| ID | Requirement | Priority |
| --- | --- | --- |
| ACC-01 | Double-entry accounting in INR; every invoice, purchase, challan bill, receipt and payment posts automatically | Must |
| ACC-02 | Quantity tracking alongside value for fabric where required | Must |
| ACC-03 | Analytical split: B2B vs retail, MTO vs stock sales, job work income, scrap / remnant sales | Must |
| ACC-04 | Daybook; Trial Balance with drill-down to ledgers and vouchers; ledger filters | Must |
| ACC-05 | Combined ledger for a party across outlets | Must |
| ACC-06 | Debtors and creditors ageing (30 / 60 / 90 days, 6 months, 1 year) | Must |
| ACC-07 | Gross and Net Profit and ratios available mid-year; current FY vs last FY comparison | Must |
| ACC-08 | Automatic carry-forward at year end; process to update opening balances after the prior year's audit | Must |
| ACC-09 | Negative cash, stock and ledger prompts | Must |
| ACC-10 | Payroll for monthly, daily-wage and piece-rate workers; PF, ESI and professional tax reports | Should |
| ACC-11 | Bank reconciliation | Should |
| ACC-12 | All voucher types: payment, receipt, contra, journal, sales, purchase, debit note, credit note, stock journal, job work bill, payroll; manual entries alongside automatic postings | Must |
| ACC-13 | Every entry tagged to a factory (and optional cost centre); trial balance, P&L and balance sheet per factory and consolidated | Must |
| ACC-14 | Bill-wise settlement for parties: against reference, new reference, advance, on account | Must |
| ACC-15 | Tax entries: GST input / output and set-off, reverse charge, TDS / TCS deduction on payments and receipts, GST on job work | Must |
| ACC-16 | Cheques and bank: post-dated cheques, cheque printing, bounced cheque reversal | Should |
| ACC-17 | Inter-factory and inter-company entries (stock transfers, expenses paid on behalf) with matching entries in both books | Must |
| ACC-18 | Fixed asset register (machines, equipment) with depreciation entries; recurring entries and provisions (rent, salaries payable) | Should |
| ACC-19 | Balance sheet, cash flow and fund flow reports | Must |

### 6.13 Reports (RPT)

| ID | Report | Priority |
| --- | --- | --- |
| RPT-01 | Sales: daily, by customer, style and agent, with thumbnails | Must |
| RPT-02 | Order book: pending, partially dispatched, late | Must |
| RPT-03 | Production: stage-wise WIP, fabricator-wise pending, wastage and rejection | Must |
| RPT-04 | Fabric: stock by roll / lot, consumption vs BOM, remnants | Must |
| RPT-05 | Finished stock: style / colour / size, ageing, slow-moving | Must |
| RPT-06 | Purchase: vendor-wise, pending POs, rate variance | Must |
| RPT-07 | Receivables and payables with ageing; expected collections | Must |
| RPT-08 | Profitability per style: fabric + job work + trims + overheads vs selling price | Must |
| RPT-09 | Agent / salesperson performance and commission | Should |
| RPT-10 | Export of any report to Excel and PDF | Must |

### 6.14 System setup and administration (SYS)

| ID | Requirement | Priority |
| --- | --- | --- |
| SYS-01 | First-install wizard: company name, address, GSTIN(s), PAN, financial year start, books beginning date, base currency (INR) | Must |
| SYS-02 | Wizard seeds a standard chart of account groups: Capital, Reserves, Loans (secured / unsecured), Current Liabilities, Duties and Taxes, Sundry Creditors, Provisions, Fixed Assets, Investments, Current Assets, Stock-in-hand, Sundry Debtors, Cash-in-hand, Bank Accounts, Loans and Advances, Sales, Purchases, Direct Incomes, Indirect Incomes, Direct Expenses, Indirect Expenses | Must |
| SYS-03 | Wizard seeds default ledgers: cash; GST input and output (CGST, SGST, IGST); TDS / TCS payable; round-off; and expense ledgers for a garment unit — job work / stitching charges, embroidery and printing charges, washing charges, wages, salaries, power and fuel, factory rent, freight inward, freight outward, packing material, repairs and maintenance, staff welfare, office expenses, telephone and internet, bank charges, interest, depreciation | Must |
| SYS-04 | Wizard also seeds default masters: units of measure, sizes, processes, voucher types and numbering, GST slabs | Must |
| SYS-05 | Everything seeded can be renamed, regrouped, added to or deactivated; ledgers with entries cannot be deleted | Must |
| SYS-06 | Add any number of factories, each with its own godowns, process areas, in-house processes and numbering series | Must |
| SYS-07 | Add multiple companies / GSTINs where the business runs more than one entity, with consolidated reporting | Should |
| SYS-08 | Add any number of users; each user gets one or more roles and access to selected factories | Must |
| SYS-09 | Custom roles with permissions per screen, field (e.g. hide cost) and action (view, create, edit, cancel, approve) | Must |
| SYS-10 | Deactivate users without losing their history; login activity log | Must |

## 7. Business rules, controls and validations

These rules are enforced by the system, not left to user discipline. "Block" means the entry cannot be saved; "Warn" means the user can proceed after acknowledging; "Approve" means a supervisor or owner must approve.

| ID | Rule | Control |
| --- | --- | --- |
| BR-01 | Quantity and fabric weight cannot be zero on any issue | Block |
| BR-02 | Fabric issue cannot exceed available stock of that roll / lot | Block |
| BR-03 | Received quantity cannot exceed issued quantity on a challan | Approve |
| BR-04 | Every job work challan must reference a production order | Block |
| BR-05 | Same lot issued to a second fabricator while the first challan is open | Warn |
| BR-06 | One mobile number per customer | Block |
| BR-07 | Order exceeds customer credit limit or customer has overdue bills | Warn (Approve if configured) |
| BR-08 | Discount at billing above the user's allowed limit | Approve |
| BR-09 | Negative stock, cash or ledger balance | Warn or Block (configurable) |
| BR-10 | Fabric consumption or wastage outside the BOM tolerance | Warn and report |
| BR-11 | Fabricator wastage / rejection above the acceptable limit | Warn and apply penalty per rate agreement |
| BR-12 | Price and tax rate changes apply to future documents only | System rule |
| BR-13 | Purchase rate differs from last rate for the same vendor and item | Warn and flag in report |
| BR-14 | Cash receipts from a party cross the yearly limit | Warn |
| BR-15 | Production users never see MTO customer name or phone | System rule |
| BR-16 | Saved invoices cannot be deleted, only cancelled or reversed with a credit note; all edits are audit-logged | System rule |
| BR-17 | Labour is payable only on QC-accepted pieces | System rule |
| BR-18 | Style BOM change on a re-made style keeps the previous version | Warn |
| BR-19 | Purchase orders above a set value | Approve |
| BR-20 | Locked periods (after GST filing or audit) cannot be edited without owner unlock | Block |
| BR-21 | Every stage movement balances: quantity out = quantity received at the next stage + recorded loss, rejection or shortage | Block |
| BR-22 | Moving goods back to an earlier stage needs a reason (rework, re-wash, correction) | Block without reason |
| BR-23 | Users see and post only in the factories assigned to them | System rule |
| BR-24 | Every voucher must balance (debits = credits) and carry a factory | Block |

## 8. Non-functional requirements and integrations

### 8.1 Non-functional requirements

Targets below are proposed starting points; the owner should confirm user counts and volumes so they can be sized.

| ID | Area | Requirement |
| --- | --- | --- |
| NFR-01 | Access | Web application on desktop; mobile app for fabricators and supervisors (confirmed); mobile-friendly screens for sales |
| NFR-02 | Security | Individual logins, role-based access to screens and fields, password policy, optional OTP login |
| NFR-03 | Audit trail | Who created, edited, approved or cancelled every document, with before / after values |
| NFR-04 | Performance | Billing scan and invoice save feel instant to the user; standard reports open within a few seconds at expected volumes |
| NFR-05 | Availability and backup | Daily automatic backup with off-site copy; tested restore; style images stored separately to keep backups small |
| NFR-06 | Multi-location | Multiple factories, each with its own godowns and process areas, plus showroom and dispatch points; multiple companies / GSTINs supported (SYS-06, SYS-07) |
| NFR-07 | Usability | Size-colour grid entry, barcode scanning, keyboard shortcuts for billing, minimal typing on mobile |
| NFR-08 | Printing | Invoices, challans, packing lists and barcode tags on standard A4 / A5 and thermal label printers |
| NFR-09 | Data ownership | All data belongs to the business and can be exported to Excel at any time |
| NFR-10 | Language | English interface, including the fabricator app (confirmed by client); regional-language labels on challans optional |

### 8.2 Integrations

| Integration | Purpose | Priority |
| --- | --- | --- |
| GST e-invoice portal (via GSP / IRP API) | Generate IRN and signed QR on invoices | Must, if turnover requires |
| E-way bill portal | Generate e-way bills from invoices and job work challans | Must |
| WhatsApp Business API | Daily 6 PM fabricator summary to the owner (Must, Phase 1); catalogues, order confirmations, dispatch updates, statements, payment reminders | Must |
| SMS / email | OTPs, alerts, statements | Should |
| Barcode scanners and label printers | Billing, receipts, dispatch, tag printing | Must |
| Bank statement import | Faster bank reconciliation | Could |
| Tally or existing accounting software | Export or one-time migration, if accounts stay in Tally during transition | To confirm |
| Online marketplaces | Order and stock sync | To confirm (see Section 10) |

## 9. Data migration, assumptions, constraints and risks

### 9.1 Data migration

| Data | Current source (to confirm) | Approach |
| --- | --- | --- |
| Customers, vendors, fabricators, agents, transporters | Accounting software / Excel | Cleaned and loaded through import templates; duplicate mobiles resolved first |
| Style master with images and BOMs | Excel / design files | Loaded for active styles; discontinued styles as archive |
| Opening stock — fabric by roll / lot, trims, finished goods | Stock register (Excel) | Physical count on cut-over date, then loaded |
| Open WIP — material with fabricators | Challan register (Excel) | Each open challan re-entered as an opening challan, reconciled with each fabricator |
| Open sale orders and POs | Excel / registers | Loaded as open documents |
| Opening ledger balances and outstanding bills | Accounting software | Bill-wise outstanding loaded as at cut-over; finalised after audit (ACC-08) |
| Price lists and customer rates | Excel | Loaded per customer / category |

If the client puts the Google Sheet tracker into use before go-live (tabs 1\_CUTTING, 2\_FABRICATORS\_10, 3\_IRON\_FINISHING, 4\_STOCK, 5\_DISPATCH), it becomes the migration source for bundles open with fabricators, ironing and finishing WIP, and stock. Its columns will be mapped to the ERP import templates, and its bundle QR numbers kept so printed tags still scan.

### 9.2 Assumptions

- All transactions are in INR within India.
- Any process can run in-house or through a subcontractor; at present cutting is in-house and stitching is through 10 outside fabricators (count confirmed by client).
- Production is tracked at bundle and lot level, not per operator or machine.
- The business will nominate a single point of contact who can take decisions during build and testing.
- Users will have internet access at the office, godown and cutting unit; mobile users will have smartphones.
- Masters and opening data will be provided and verified by the business before go-live.

### 9.3 Constraints

- GST, e-invoice and e-way bill rules change from time to time; the system keeps rates and slabs in masters so changes need configuration, not code.
- E-invoice depends on the turnover threshold notified by GST authorities and on a GSP / IRP connection.
- WhatsApp messages require an approved WhatsApp Business API account and message templates.

### 9.4 Key risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Fabricators and staff resist new challan discipline | WIP and fabric balances become unreliable | Simple mobile screens, printed challans, training, and owner enforcement from day one |
| Opening stock and WIP not reconciled at cut-over | Wrong balances carried for months | Physical count and fabricator-wise confirmation before go-live |
| Requirements keep changing during build | Delays and cost overrun | Sign-off on this BRD; change requests logged and estimated separately |
| Styles and BOMs not documented | Production orders cannot auto-populate | Load active styles first; capture BOMs from the first few production runs |
| Parallel Excel or AppSheet use continues | Two versions of the truth | Fixed date after which Excel registers and the AppSheet tracker are frozen |
| Fabricators mark bundles Done before work is finished or counted | Overstated output and labour overpaid | "Done" only raises a pending receipt; pay and stock move only after supervisor count and QC (MOB-03, JOB-07) |
| Client settles on a free no-code tracker instead of the ERP | No link to fabric ledger, GST, billing or accounts; data re-entered in several places | Agree its role now (Q16); if used, treat it as a stopgap and design the ERP to take over its data and QR tags |

## 10. Decisions needed from the business owner

These answers change the design, so we need them before build starts. Please fill the "Owner's answer" column.

| # | Question | Why it matters | Owner's answer |
| --- | --- | --- | --- |
| Q1 | Is retail (showroom or online) in scope, or B2B only? | Decides whether POS-style billing, MRP-based retail pricing and marketplace sync are built |  |
| Q2 | Is cutting done in-house, and is stitching done only through outside fabricators? Any in-house stitching lines? | Decides in-house production screens and piece-rate payroll | Partly answered: any step can be in-house or subcontracted (PRD-13). Still to list: which steps run where today. |
| Q3 | Barcode level: per SKU only, or also per bundle and per carton? | Affects tag printing, dispatch scanning and hardware | Partly answered: bundle-level QR, scanned by fabricators. Still to confirm: SKU barcodes for billing and carton labels. |
| Q4 | Is labour paid per piece only, or also by size, weight or flat per lot? Which fabricators use which method? | Confirms rate types A–D (JOB-06) | Partly answered: per piece (client example ₹25 per piece). See Q18 and Q19. |
| Q5 | Are fabric rolls tracked individually by roll number, or in bulk by lot? | Roll-level tracking gives tighter control but needs roll tags and more entry |  |
| Q6 | Is e-invoicing mandatory for your turnover today? | Decides whether IRP integration is needed at go-live |  |
| Q7 | Which existing Excel systems (challan, stock register, production dashboard, others) must be migrated, and can you share samples? | Sets migration scope and report formats |  |
| Q8 | Who needs mobile access: sales team, supervisors, fabricators? How many users in each role? | Sizes licences, mobile screens and training | Partly answered: 10 fabricators, each with own login, in English. Still to confirm: sales team and supervisor users. |
| Q9 | How many locations (godowns, cutting unit, showroom) and how many GSTINs / companies? | Multi-location and multi-company set-up | Partly answered: multiple factories and users required. Still to list: factories, their GSTINs, and whether there is more than one company. |
| Q10 | Which accounting software is used today, and should it be replaced at go-live or run in parallel for a period? | Cut-over plan for accounts |  |
| Q11 | Do you sell on online marketplaces, and should orders and stock sync automatically? | Integration scope |  |
| Q12 | Do you earn any job work income by stitching for others? | Adds job-work-in billing and stock of customer-owned material |  |
| Q13 | Approval limits: discount % per role, PO value needing approval, credit limit override rights | Configures BR-07, BR-08, BR-19 |  |
| Q14 | Typical volumes: styles active, orders per month, invoices per day, fabricators | Sizing and performance testing | Partly answered: 10 fabricators. Other volumes pending. |
| Q15 | Target go-live date and any season deadline to avoid | Phasing and cut-over timing |  |

### New questions raised by the client's inputs

| # | Question | Why it matters | Owner's answer |
| --- | --- | --- | --- |
| Q16 | Is the Google Sheets / AppSheet tracker a stopgap until the ERP goes live, or is it being considered instead of the ERP? | A no-code tracker has no fabric ledger, GST, billing or accounts; this sets scope, cost and timeline expectations |  |
| Q17 | Between fabricators and ironing, is there a QC check? Are outside processes (embroidery, printing, washing) used? | The client's flow lists only cutting, fabricators, ironing / finishing, stock and dispatch |  |
| Q18 | Is ₹25 the actual stitching rate? Is it the same for all 10 fabricators, all styles and all sizes? | Decides which rate types (JOB-06) are needed and how earnings are calculated |  |
| Q19 | Should fabricators be paid on pieces they mark Done, or on pieces accepted at QC (our recommendation)? | Paying on self-reported completion invites over-claiming |  |
| Q20 | Low-stock alert below 50: stock of what — finished pieces per SKU, per style, all finished goods, or raw material? One level for all items? | Defines the alert rule in INV-06 |  |
| Q21 | Who receives the 6 PM WhatsApp summary, and what must it show? Is a WhatsApp Business account in place? | Report content, recipients and integration set-up |  |
| Q22 | Is a branded Play Store app ("YourBrand Factory App") required, or is an installable mobile web app enough? | A store app adds publishing, updates and maintenance cost |  |
| Q23 | Is the business GST registered today, and does it deduct TDS (has a TAN)? Is there a plan or date to register? | Decides starting tax settings, invoice format, and whether e-invoice, e-way bill and GST reports are needed at go-live |  |

## 11. Acceptance, phasing and sign-off

### 11.1 Acceptance scenarios

The system is accepted when these end-to-end scenarios run correctly on the business's own data, with stock and accounts reconciling after each.

| # | Scenario | Pass criteria |
| --- | --- | --- |
| A1 | Create a production order and issue fabric by roll for cutting | Roll balance reduces; cutting entry records pieces per size, consumption, waste and remnant; variance vs BOM shown |
| A2 | Issue cut bundles to a fabricator and receive partially | Challan prints with order reference; fabricator ledger shows issued, received and pending; second-fabricator warning fires on re-issue |
| A3 | QC and labour bill | Rejected pieces deducted; labour bill raised only on accepted pieces with TDS; rework challan created |
| A4 | Scan barcodes at billing | Style, colour, size and rate fill automatically; GST slab and CGST / SGST vs IGST correct; e-invoice and e-way bill data generated |
| A5 | Create an MTO sale order and trace it by order number | Production sees specs without customer identity; stage visible at every step until dispatch |
| A6 | Enter a price list rate and apply a customer discount | Correct rate and discount on a new order; old orders unchanged |
| A7 | Dealer bulk order with partial dispatch | Packing list by carton; LR recorded; order book shows balance pending |
| A8 | Advance, invoice and credit note | Advance adjusted with trail on bill; credit note reduces outstanding; ageing updates |
| A9 | Month-end | Trial Balance, P&L, GSTR-1 / 3B support and style profitability reports produce without manual adjustment |
| A10 | Fresh install, add two factories and users | Wizard seeds account groups, ledgers and default masters; users see only their assigned factory |
| A11 | One lot: cut in-house at Factory 1, stitched by a subcontractor, ironed at Factory 2, sent back for re-press | Each move recorded and balanced; WIP correct by factory and stage; lot cost includes in-house labour and job work |
| A12 | Post one of each voucher type, including a manual journal and a contra | Factory-wise and consolidated trial balance, P&L and balance sheet tally |

### 11.2 Suggested phasing

We recommend going live in three releases so the core stock-to-cash cycle is stable before the extras are added. The owner can move items between phases.

| Phase | Scope | Rationale |
| --- | --- | --- |
| 1 — Core operations | First-install setup, factories, users and roles, masters, purchases with GRN, inventory and fabric ledger, production orders, cutting, bundles, job work challans, fabricator mobile app with bundle QR, daily 6 PM WhatsApp summary, low-stock alert, sales and billing with barcode, GST / e-way bill, accounting | Replaces the Excel challan and stock registers, any interim AppSheet tracker and the billing process, and puts the client's top priority — fabricators on mobile — in the first release |
| 2 — Control and visibility | Production dashboard, fabricator labour bills and deductions, wastage limits, dealer schemes, advances, ageing and collection reports, style profitability | Adds the controls once data is flowing reliably |
| 3 — Growth | CRM and lead tracking on mobile, WhatsApp integration, catalogue sharing, payroll, customer portal, marketplace sync (if confirmed) | Customer-facing and convenience features |

### 11.3 Sign-off

By signing, the business owner confirms that Sections 3 to 9, as marked up, are the agreed requirements and that Section 10 has been answered. Changes after sign-off follow a change request process with impact on cost and timeline.

| Role | Name | Signature | Date |
| --- | --- | --- | --- |
| Business owner |  |  |  |
| Prepared by (Actuaria LLP) | Shryans Baid |  |  |
