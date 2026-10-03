# Setup Guide — getting the ERP ready for operations

For the owner, accountant and merchandiser. Follow the parts in order. Each master has a plain explanation, what to record, and filled-in examples taken from a track pant / jogger business in Ludhiana.

> **About the examples.** The firm, parties, GSTINs, rates and mobile numbers are made up so you can see the shape of the data. Replace every one with your real figures. GSTIN, PAN and TAN are checked for format, so use real numbers from your registration. Tax rates, HSN codes and TDS sections are starting points that **your accountant must confirm**.

**Menu paths** below are written like *Masters → Styles*. Some screens are only visible if your role allows them (Part 2).

---

## 0. The order of setup

Later steps depend on earlier ones. Do not skip ahead.

| # | Step | Where | Who | Time |
| --- | --- | --- | --- | --- |
| 1 | Setup wizard: company, tax switches, financial year, first factory | `/setup/` (first login) | Owner | 15 min |
| 2 | More factories and locations | Admin → Factories | Administrator | 10 min |
| 3 | Roles and users | Admin → Roles, Users | Administrator | 30 min |
| 4 | Tax settings, HSN and GST slabs | Tax | Accountant | 20 min |
| 5 | Inventory settings | Settings → Inventory | Owner | 5 min |
| 6 | Chart of accounts: add bank accounts and your own ledgers | Accounts → Chart of accounts | Accountant | 30 min |
| 7 | Basic masters: units, sizes, colours, products, materials, processes | Masters | Merchandiser | 1–2 hours |
| 8 | Routes | Masters → Routes | Merchandiser + Production head | 30 min |
| 9 | Parties: vendors, fabricators, customers, agents, transporters | Masters → Parties | Accountant / Purchase | 1–3 hours |
| 10 | Styles, SKUs and BOMs | Masters → Styles | Merchandiser | per style |
| 11 | Labour rates for each fabricator | Job work → Rates | Production head + Accountant | 1 hour |
| 12 | Price lists | Masters → Price lists | Owner / Sales | 30 min |
| 13 | Opening balances and opening stock | Accounts → Opening, Inventory → Opening stock | Accountant + Store Keeper | 1 day |
| 14 | Dry run with one real lot | Part 14 | Everyone | 1 day |

You can load parties, styles, materials, opening stock and opening balances from Excel (Part 13) instead of typing them.

---

## 1. Before you start: collect this information

Having it on one sheet makes setup a single sitting.

- **Company:** legal name, trade name, address, PAN, GSTIN (if registered), TAN (if you deduct TDS).
- **Dates:** the date your books begin in this ERP (opening balances are dated this day; nothing earlier can be posted). Most Indian firms start the financial year in April, and the cleanest start is 1 April.
- **Factories:** every unit that cuts, finishes, stores or dispatches goods. Name, address, GSTIN if separate.
- **People:** who will log in, what each does, which factory each works in.
- **Last year's trial balance** and **party-wise outstanding** lists (receivable and payable, bill by bill).
- **Stock count:** fabric rolls (roll number, weight or metres, lot, rate), trims, and finished goods by style, colour and size.
- **Active style list** with colours, sizes, fabric consumption and trims.
- **Fabricator list** with the rate each is paid for each process.

---

## 2. Setup wizard (first login)

Opens by itself on first login. Four steps, then a review page. Nothing is saved until you confirm the review.

| Step | Field | Example | Notes |
| --- | --- | --- | --- |
| Company | Name | `Ludhiana Knitwear` | Short name used on screens |
| | Legal name | `Ludhiana Knitwear Private Limited` | Appears on invoices |
| | Address, city, state, pincode | `Focal Point, Phase 5` / Ludhiana / Punjab / 141010 | State decides CGST+SGST vs IGST |
| | PAN | `ABCDE1234F` | |
| Tax | GST registered | ticked | Untick if not registered; you can switch it on later with a date |
| | GSTIN | `03ABCDE1234F1Z5` | The first two digits must match the company state (03 = Punjab) |
| | GST applies from | `01-04-2026` | Blank = the books start date |
| | Deducts TDS | ticked | Needed if you pay fabricators above the TDS threshold |
| | TAN | `JLDA12345B` | |
| Year | Financial year starts in | April | |
| | Books begin on | `01-04-2026` | Cannot be changed casually; opening balances use it |
| Factory | Short code | `LDH1` | Letters and digits only. Appears in every document number |
| | Name | `Ludhiana Unit 1` | |
| | State, GSTIN | Punjab / blank | Blank GSTIN uses the company's |

**Finishing the wizard automatically creates:**

- Chart of accounts: groups and ledgers for garment work, including Cash, Job Work Charges, Embroidery/Printing/Washing Charges, GST and TDS ledgers, stock ledgers (raw material, WIP, with fabricators, finished goods, rejects), purchases and sales ledgers.
- Default masters: units, sizes, colours, products, processes and one standard route (Part 7, 8).
- HSN codes 6103, 6104, 6109, 6110, 6112 with value slabs, and GST / TDS templates.
- Twelve system roles (Part 3).
- For your first factory: default locations and document number series.

Everything created is editable. Re-running the seeders only adds what is missing and never overwrites your edits.

---

## 3. Factories, locations, roles and users

### 3.1 Factories and locations

*Admin → Factories.* One record per physical unit. Every voucher and stock movement belongs to a factory, and users only see the factories they are assigned to.

Each new factory gets these locations automatically. Add more with **Add location**.

| Location | Type | What it is for |
| --- | --- | --- |
| Main Godown | Godown | Fabric and trims store |
| Cutting Floor | Cutting floor | Fabric issued for cutting, cut pieces |
| Process Area | Process area | In-house stitching / finishing WIP |
| Dispatch | Dispatch | Finished goods ready to ship |
| In Transit | In transit | Stock moving between factories |
| Rejects | Rejects | QC rejects and remnants |

**Examples of extra locations**

| Factory | Location | Type |
| --- | --- | --- |
| LDH1 | Finished Goods Store | Godown |
| LDH1 | Trims Rack | Godown |
| LDH2 | Main Godown | Godown |
| LDH1 | Showroom | Showroom |

Do **not** create locations for fabricators. A location "At <fabricator name>" is created by the system the first time work is issued to them.

**Example factories**

| Code | Name | City | State | GSTIN |
| --- | --- | --- | --- | --- |
| LDH1 | Ludhiana Unit 1 (cutting, finishing, dispatch) | Ludhiana | Punjab | blank (uses company's) |
| LDH2 | Ludhiana Unit 2 (stitching floor) | Ludhiana | Punjab | `03ABCDE1234F2Z4` |

Use more than one factory only if they need separate books, stock or users. If in doubt, start with one.

### 3.2 Roles

*Admin → Roles.* A role is a permission matrix: for each screen, tick **view / create / edit / cancel / approve**. A second block hides sensitive fields (customer phone, rates, cost) from the role.

The system supplies these. Copy and adjust rather than starting from blank.

| Role | Typical person | Can do |
| --- | --- | --- |
| Owner | Proprietor | Everything, including approvals |
| Administrator | IT / office manager | Company, factories, users, roles. Cannot post transactions |
| Accountant | Accountant | Vouchers, opening balances, books, tax settings, bills |
| Purchase Officer | Purchase | POs, vendors |
| Merchandiser | Design / merchandising | Styles, BOM, routes, materials, price lists |
| Production Planner | Planner | Production orders and route planning |
| Production Supervisor | Floor supervisor | Move bundles, challans, receipts, QC |
| QC Checker | QC | Accept, reject, send back |
| Cutting Master | Cutting | Cutting entries, bundle tags |
| Store Keeper | Store | GRN, transfers, opening stock, labels |
| Billing Clerk | Billing | Invoices, packing, dispatch |
| Salesperson | Sales | Orders and own customers |
| Fabricator | Outside stitcher | Own bundles and earnings on the mobile app |

Customer name and phone on made-to-order jobs are never shown to production roles, however you edit them.

### 3.3 Users

*Admin → Users → New.*

| Field | Example |
| --- | --- |
| Username | `rajinder.store` |
| Name | Rajinder Singh |
| Mobile | `9876500011` |
| Roles | Store Keeper |
| All factories | off |
| Allowed factories | LDH1 |
| Password | Strong; the user changes it at first login |

**Suggested starting users**

| Person | Role(s) | Factories |
| --- | --- | --- |
| Owner | Owner | All |
| Office manager | Administrator | All |
| Accountant | Accountant | All |
| Merchandiser | Merchandiser | All |
| Store keeper, Unit 1 | Store Keeper | LDH1 |
| Cutting master | Cutting Master | LDH1 |
| Supervisor, Unit 2 | Production Supervisor | LDH2 |
| QC checker | QC Checker | LDH1, LDH2 |

Fabricators and sales staff get users later, when their screens are released.

---

## 4. Tax settings

*Tax.* Tax is optional and independent. GST and TDS are separate switches, each with an effective date. Nothing posts to a tax ledger unless a tax template is picked or tax lines are entered on that document.

**Settings to confirm**

| Setting | Example |
| --- | --- |
| GST registered, from | Yes, `01-04-2026` |
| TDS deductor, from | Yes, `01-04-2026` |

**HSN and slabs** (*Masters → HSN codes*). Each HSN has dated value slabs: the GST rate depends on the per-piece value.

| HSN | Description | Slab (per piece) | GST | From |
| --- | --- | --- | --- | --- |
| 6103 | Men's trousers and shorts, knitted | up to ₹2,500 | 5% | 22-09-2025 |
| 6103 | | above ₹2,500 | 18% | 22-09-2025 |
| 6112 | Track suits | up to ₹2,500 | 5% | 22-09-2025 |
| 6109 | T-shirts, knitted | up to ₹2,500 | 5% | 22-09-2025 |

Add an HSN for any product you sell that is not listed. A rate change is a **new dated slab**, not an edit, so old invoices stay correct.

**Tax templates** already seeded:

- GST at 0, 5, 12, 18% — intra-state (CGST+SGST), inter-state (IGST), and each with reverse charge.
- TDS 194C 1% (individual / HUF), 194C 2% (others), 194Q 0.1%.

Add a template for any rate or section you use that is missing. Confirm every rate with your accountant.

---

## 5. Inventory settings

*Settings → Inventory.*

| Setting | What it does | Suggested start |
| --- | --- | --- |
| Valuation method | **Weighted average** per item per factory, or **specific cost per fabric roll** | Weighted average. Choose specific roll only if rolls of the same fabric are bought at very different prices and you want exact cost per lot |
| Allow negative stock | Off blocks any issue above stock on hand | **Off** |
| PO approval limit | A PO above this value needs the owner's approval. 0 = every PO | `50000` |
| BOM variance tolerance % | Fabric used more or less than the BOM by more than this is flagged at cutting | `5` |

A change applies from that day. Earlier stock keeps its value.

---

## 6. Chart of accounts

*Accounts → Chart of accounts.* Seeded, editable. You need to **add your bank accounts and any party-specific or business-specific ledgers**.

**Add these ledgers**

| Ledger name | Group | Bill-wise |
| --- | --- | --- |
| HDFC Bank Current A/c 1234 | Bank Accounts | No |
| PNB Cash Credit A/c | Secured Loans | No |
| Machinery | Fixed Assets | No |
| Capital – Owner | Capital | No |
| Insurance | Indirect Expenses | No |
| Transport Inward – Fabric | Direct Expenses | No |

**Party ledgers.** Each customer, vendor and fabricator has a ledger: sundry debtors for customers, sundry creditors for vendors and fabricators. Mark debtor and creditor groups **bill-wise** so payments can be matched to bills. The system links the right ledger when you save a party; override only for special cases.

Do not delete or rename system ledgers (for example `Raw Material Stock`, `Job Work Charges`, `Goods Received Not Billed`, `Opening Balance Difference`). The posting engine finds them by a hidden key, but renaming them confuses reports.

---

## 7. Basic masters

*Masters →* the item named below. Most are small lists that were seeded; check them and add your own.

### 7.1 Units

| Code | Name | Type |
| --- | --- | --- |
| PCS | Pieces | count |
| DZN | Dozen | count |
| KG | Kilogram | weight |
| MTR | Metre | length |

Seeded conversions: 1 DZN = 12 PCS, 1 GRS = 144 PCS, 1 KG = 1000 GM, 1 MTR = 100 CM. Add one if you buy in a unit not listed, e.g. `CONE` / `Cone` (count).

### 7.2 Sizes

Order matters; it is the order shown on grids and labels.

| Code | Name | Sort |
| --- | --- | --- |
| S | S | 1 |
| M | M | 2 |
| L | L | 3 |
| XL | XL | 4 |
| XXL | XXL | 5 |
| 4-6Y | 4-6Y | 8 |

Seeded: S to XXL, FREE, and kids sizes 2-4Y to 12-14Y. Add `3XL` after XXL if you make it.

### 7.3 Colours

Seeded: Black, Navy, Grey Melange, Charcoal, White, Maroon, Royal Blue, Bottle Green. Add your own, for example `Olive Green` (code `OLV`), `Mustard`, `Sky Blue`. Use one spelling per colour; `Navy` and `Navy Blue` become two colours.

### 7.4 Products (categories)

| Code | Name |
| --- | --- |
| TRK | Track pant |
| JGR | Jogger |
| TSH | T-shirt |
| SET | Tracksuit |

Code is up to 5 characters. Add `SHR` Shorts, `HOD` Hoodie if you make them.

### 7.5 Materials (fabric, trims, packing)

The raw items you buy and consume. Not finished goods.

| Code | Name | Kind | Unit | Composition | GSM | Width (cm) |
| --- | --- | --- | --- | --- | --- | --- |
| FAB-001 | Cotton fleece 280 GSM | Fabric | KG | 80% cotton 20% polyester | 280 | 180 |
| FAB-002 | Interlock 180 GSM | Fabric | KG | 100% cotton | 180 | 170 |
| FAB-003 | Rib 1x1 (cuff / waistband) | Fabric | KG | 95% cotton 5% lycra | 240 | 90 |
| TRM-001 | Drawcord flat 12 mm black | Trim | MTR | Polyester | | |
| TRM-002 | Elastic 1.5 inch | Trim | MTR | | | |
| TRM-003 | Brand main label woven | Trim | PCS | | | |
| TRM-004 | Care label | Trim | PCS | | | |
| TRM-005 | Eyelet metal 8 mm | Trim | PCS | | | |
| TRM-006 | Sewing thread 40/2 black | Trim | CONE | Polyester | | |
| PKG-001 | Polybag 10x14 | Packing | PCS | | | |
| PKG-002 | Carton 5-ply medium | Packing | PCS | | | |

Rules:

- Choose the unit you **stock and issue** in. Fabric is almost always KG (or MTR if you buy by length). Everything in the BOM uses this unit.
- One code per distinct item. Different GSM, width or composition is a different material.
- Fabric is tracked **per roll** in stock, so colour and roll number are captured at GRN, not in the material name. If you buy the same cotton fleece in black and navy, make one material and record the colour per roll, or make `FAB-001-BLK` and `FAB-001-NVY` if your consumption differs by shade. Decide this once and stay consistent.

### 7.6 Processes

A process is a step of work. Each has a kind, which tells the system how to treat it.

| Code | Name | Kind |
| --- | --- | --- |
| CUT | Cutting | Cutting |
| STITCH | Stitching | Stitching |
| EMB | Embroidery | Value-add |
| PRINT | Printing | Value-add |
| WASH | Washing | Value-add |
| DYE | Dyeing | Value-add |
| IRON | Ironing and pressing | Finishing |
| FINISH | Thread cutting and finishing | Finishing |
| QC | Quality check | QC |
| PACK | Packing | Packing |

Add steps you actually use: `FLAT` Flatlock (Stitching), `BARTACK` Bartack and buttonhole (Stitching), `HEATPRESS` Heat transfer (Value-add).

Keep processes **coarse**. If one fabricator does stitching, flatlock and bartack in a single job at one rate, treat it as one process `STITCH`. Split only when different people do them or you pay separately.

---

## 8. Routes

### 8.1 What a route is

A route is the **default sequence of processes** a style goes through. When a production order is released, each lot copies the style's route. The planner can then change it for that lot: assign a step to in-house or to a fabricator, skip an optional step, add a step. A route only has to be right *most of the time*.

Each route step records:

| Field | Meaning |
| --- | --- |
| Sequence | 1, 2, 3 … the order work happens |
| Process | From the process master |
| Mandatory | Ticked: cannot be skipped. Unticked: optional, the planner decides per lot |
| Assignment | **In-house** (your own factory) or **Subcontractor** (outside fabricator) |
| Default factory | For in-house steps: which factory normally does it |
| Default party | For subcontract steps: the usual fabricator. Leave blank if you choose per lot |
| Rate | Default rate per piece, shown to the planner as a starting figure |

The default only pre-fills the lot. It never locks it.

Quantity is tracked **bundle by bundle** through the route. At every move, `quantity out = quantity received at next step + loss + rejection + shortage`. Moving a bundle back to an earlier step always needs a reason.

### 8.2 Route A — Standard track pant (seeded)

Cut in-house, stitched outside, finished in-house.

| Seq | Process | Mandatory | Assignment | Default factory | Default party | Rate (₹/pc) |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Cutting | Yes | In-house | LDH1 | | 0 |
| 2 | Stitching | Yes | Subcontractor | | Gurpreet Garments | 26.00 |
| 3 | Embroidery | No | Subcontractor | | | 0 |
| 4 | Printing | No | Subcontractor | | | 0 |
| 5 | Washing | No | Subcontractor | | | 0 |
| 6 | Ironing and pressing | Yes | In-house | LDH1 | | 0 |
| 7 | Thread cutting and finishing | Yes | In-house | LDH1 | | 0 |
| 8 | Quality check | Yes | In-house | LDH1 | | 0 |
| 9 | Packing | Yes | In-house | LDH1 | | 0 |

Optional steps (embroidery, printing, washing) are ticked per lot by the planner.

### 8.3 Route B — Jogger with embroidered logo

Logo embroidered on cut panels before stitching, so embroidery comes before stitching.

| Seq | Process | Mandatory | Assignment | Default party | Rate |
| --- | --- | --- | --- | --- | --- |
| 1 | Cutting | Yes | In-house (LDH1) | | 0 |
| 2 | Embroidery | Yes | Subcontractor | Royal Embroidery | 8.00 |
| 3 | Stitching | Yes | Subcontractor | Gurpreet Garments | 28.00 |
| 4 | Flatlock | No | Subcontractor | Gurpreet Garments | 4.00 |
| 5 | Ironing and pressing | Yes | In-house (LDH1) | | 0 |
| 6 | Quality check | Yes | In-house (LDH1) | | 0 |
| 7 | Packing | Yes | In-house (LDH1) | | 0 |

### 8.4 Route C — Fully in-house

Cutting and stitching on your own floors (LDH2 stitches).

| Seq | Process | Mandatory | Assignment | Default factory |
| --- | --- | --- | --- | --- |
| 1 | Cutting | Yes | In-house | LDH1 |
| 2 | Stitching | Yes | In-house | LDH2 |
| 3 | Finishing | Yes | In-house | LDH2 |
| 4 | Quality check | Yes | In-house | LDH2 |
| 5 | Packing | Yes | In-house | LDH1 |

Goods moving from LDH1 to LDH2 are an **inter-factory transfer** and are valued automatically; you do not set up anything extra.

### 8.5 Route D — Washed jogger (wash before finishing)

| Seq | Process | Mandatory | Assignment | Default party | Rate |
| --- | --- | --- | --- | --- | --- |
| 1 | Cutting | Yes | In-house (LDH1) | | 0 |
| 2 | Stitching | Yes | Subcontractor | Gurpreet Garments | 27.00 |
| 3 | Washing | Yes | Subcontractor | Shree Wash House | 9.00 |
| 4 | Ironing and pressing | Yes | In-house (LDH1) | | 0 |
| 5 | Quality check | Yes | In-house (LDH1) | | 0 |
| 6 | Packing | Yes | In-house (LDH1) | | 0 |

### 8.6 How to design your routes

1. Walk your floor. Write down, for your best-selling style, every step the cloth passes through from fabric to carton.
2. Merge steps done by the same person at the same rate into one process.
3. Mark a step **mandatory** if no lot of that style may skip it.
4. Decide in-house versus subcontract by what happens **normally**.
5. Start with **2–4 routes** (one per garment family or finish). Do not make one per style. Different styles share routes.
6. Set the style's default route on the style (Part 10).

**What not to do**

- Do not put a new route in for every fabricator. Use "Default party" or choose at planning time.
- Do not use the route rate as the fabricator's pay agreement. Pay is set in **Labour rates** (Part 11). Keep both in agreement.
- Do not leave out QC or packing. They are what lets finished goods reach stock and billing.

---

## 9. Parties

*Masters → Parties → New.* One record per firm. A party can have several roles at once, for example a vendor who is also a customer.

### 9.1 Fields

| Field | Notes |
| --- | --- |
| Name | The firm's name |
| Contact person | |
| Roles | Customer, Vendor, Fabricator, Agent, Transporter (tick all that apply) |
| Mobile | **Required**, 10 digits. A duplicate customer mobile is rejected |
| Landline, email | |
| GSTIN, PAN, State | State drives CGST+SGST vs IGST. GSTIN format is validated |
| Category | Wholesaler, Distributor, Retailer, Online, Walk-in, Institutional. For customers |
| Price list | For customers. See Part 12 |
| Discount % | Default discount |
| Credit limit, credit days | Warn when exceeded |
| Payment terms | Free text |
| Agent, Transporter | Default agent and transporter for this customer |
| Destination | Delivery city |
| TDS section | A suggestion only. TDS applies only when chosen on a bill |
| Addresses | Billing, shipping, with city, state, pincode |
| Special rates | Customer-specific rate per style or product, with a start date |

Party codes (`P0001`, `P0002` …) are generated for you.

### 9.2 Vendor — fabric supplier

| Field | Value |
| --- | --- |
| Name | Sri Ram Textiles |
| Roles | Vendor |
| Contact / Mobile | Ramesh Gupta / `9811100022` |
| GSTIN | `03AAAAA1111A1Z5` |
| State | Punjab |
| Credit days | 30 |
| Payment terms | 30 days from invoice, RTGS |

### 9.3 Vendor — trims

| Field | Value |
| --- | --- |
| Name | Bharat Trims and Labels |
| Roles | Vendor |
| Mobile | `9815500033` |
| GSTIN | `03BBBBB2222B1Z7` |
| Credit days | 15 |

### 9.4 Fabricator (job worker)

| Field | Value |
| --- | --- |
| Name | Gurpreet Garments |
| Roles | Fabricator |
| Contact / Mobile | Gurpreet Singh / `9876511144` |
| GSTIN | blank (unregistered) |
| PAN | `ABCPG1234H` (needed if TDS will be deducted) |
| State | Punjab |
| TDS section | 194C (suggestion) |
| Payment terms | Weekly, on QC-accepted pieces |

Create the **labour rates** for the fabricator next (Part 11), so their work can be priced.

Other fabricators in the examples: `Royal Embroidery` (embroidery, Mobile `9876522255`), `Shree Wash House` (washing, `9876533366`).

### 9.5 Wholesale customer

| Field | Value |
| --- | --- |
| Name | Mehta Traders |
| Roles | Customer |
| Contact / Mobile | Rakesh Mehta / `9876543210` |
| GSTIN | `07ABCDE1234F1Z5` |
| State | Delhi |
| Category | Wholesaler |
| Price list | Wholesale |
| Discount % | 2 |
| Credit limit / days | ₹3,00,000 / 45 |
| Agent | Sunil Agencies |
| Transporter | Jai Mata Roadlines |
| Destination | Delhi |

### 9.6 Walk-in / retail customer

| Field | Value |
| --- | --- |
| Name | Walk-in Customer |
| Roles | Customer |
| Mobile | `9876500099` (the shop counter's number; each customer mobile must be unique) |
| Category | Walk-in |
| Price list | Retail MRP |
| Credit limit | 0 (cash sale) |

### 9.7 Agent and transporter

| Name | Roles | Mobile | Note |
| --- | --- | --- | --- |
| Sunil Agencies | Agent | `9810011177` | Commission handled as an expense |
| Jai Mata Roadlines | Transporter | `9814488899` | Used on packing and dispatch |

---

## 10. Styles, SKUs and BOMs

### 10.1 Style

*Masters → Styles → New.* A style is a design: its number, product, colours and sizes. **A SKU is one colour and one size of a style**, with its own barcode. Select colours and sizes on the style and every combination gets a SKU and barcode automatically.

| Field | Example |
| --- | --- |
| Style no. | `JGR-104` (unique) |
| Product | Jogger |
| Name | Cuffed jogger, fleece |
| Description | Elastic waist with drawcord, ribbed cuffs, two side pockets |
| HSN | 6103 |
| Default route | Route B — Jogger with embroidered logo |
| MRP | 699 |
| Colours | Black, Navy, Grey Melange |
| Sizes | S, M, L, XL, XXL |
| Image | Photo (optional; a thumbnail is made) |

This creates **3 colours × 5 sizes = 15 SKUs**. For example:

| SKU | Barcode (auto) |
| --- | --- |
| JGR-104 / Black / M | `0000000014` |
| JGR-104 / Navy / L | `0000000023` |

Barcodes are plain sequential numbers; the length is configurable. You can set a SKU-level MRP when it differs from the style.

More example styles:

| Style no. | Name | Product | HSN | Colours | Sizes | MRP |
| --- | --- | --- | --- | --- | --- | --- |
| `TRK-201` | Plain track pant, interlock | Track pant | 6103 | Black, Navy, Charcoal | S–XXL | 549 |
| `TSH-310` | Round neck T-shirt | T-shirt | 6109 | White, Black, Maroon | S–XL | 399 |
| `SET-401` | Tracksuit, zipper jacket | Tracksuit | 6112 | Navy, Black | M–XXL | 1,299 |
| `JGR-105K` | Kids jogger | Jogger | 6104 | Black, Navy | 4-6Y, 6-8Y, 8-10Y | 449 |

Discontinued styles are **archived**, not deleted, and stay searchable with full history.

### 10.2 BOM (bill of materials)

*Style → BOM.* How much of each raw material **one piece** needs. The BOM is **versioned**: a change creates a new version and the old one is kept, so an old lot still costs against the BOM it used.

Each line has:

| Field | Meaning |
| --- | --- |
| Material | From the material master |
| Quantity per piece | In the material's unit |
| Wastage % | Allowance for cutting loss, added on top |
| Size overrides | Different quantity for a size that uses more or less |

You can also add **per-piece charges** (not materials): a fixed amount per piece for a process, for example embroidery or washing, which the cost includes.

**BOM example — style JGR-104, version 1**

| Material | Unit | Qty / piece | Wastage % | Size override |
| --- | --- | --- | --- | --- |
| Cotton fleece 280 GSM | KG | 0.4200 | 4 | S 0.3800, L 0.4500, XL 0.4800, XXL 0.5200 |
| Rib 1x1 | KG | 0.0400 | 3 | |
| Drawcord flat 12 mm | MTR | 1.2000 | 2 | |
| Elastic 1.5 inch | MTR | 0.7500 | 2 | |
| Eyelet metal 8 mm | PCS | 2.0000 | 0 | |
| Brand main label woven | PCS | 1.0000 | 0 | |
| Care label | PCS | 1.0000 | 0 | |
| Sewing thread 40/2 | CONE | 0.0100 | 5 | |
| Polybag 10x14 | PCS | 1.0000 | 0 | |

Charges per piece (informational costing):

| Description | Process | Amount (₹/pc) |
| --- | --- | --- |
| Logo embroidery | Embroidery | 8.00 |

Reading this: the base quantity applies to sizes M, and sizes listed in *size overrides* use their own figure. Fabric required for a lot is `qty per piece × pieces cut × (1 + wastage)`, and the cutting screen compares what was actually used with this and flags anything beyond your tolerance (Part 5).

**To work out fabric per piece**, cut and weigh one finished garment per size, add the wastage you normally lose in the lay, and round to 4 decimals. A close estimate is fine; the system shows actual versus BOM after your first few lots, and you refine.

**Cost check.** With fabric at ₹190/kg: `0.42 × 190 = ₹79.80` plus rib and trims. This is why accurate rates in opening stock and GRN matter.

---

## 11. Labour rates (what each fabricator is paid)

*Job work → Rates → New.* A rate is for one **fabricator + process**, with a start date. A new rate never changes bills already made; it applies to challans issued after its date. Labour is paid **only on QC-accepted pieces**.

There are four rate types.

| Type | Use when | What you enter |
| --- | --- | --- |
| **A. Per piece** | One rate per piece for the process | Rate per piece |
| **B. Per piece plus add-ons** | A base rate plus extras (flatlock, pocket, bartack) | Base rate and named add-ons per piece |
| **C. Size-wise** | The rate depends on size | A rate for each size |
| **D. Flat per lot** | A fixed amount for the lot (washing, dyeing) | Flat amount per lot |

Every rate can also have a **rework rate per piece**: what the fabricator is paid to redo a rejected piece.

**Examples**

| Fabricator | Process | Type | Details | From |
| --- | --- | --- | --- | --- |
| Gurpreet Garments | Stitching | A | ₹26.00 per piece, rework ₹6.00 | 01-04-2026 |
| Gurpreet Garments | Stitching | B | Base ₹24.00 + Flatlock ₹3.00 + Bartack ₹1.50 | 01-04-2026 |
| Gurpreet Garments | Stitching (kids) | C | 4-6Y ₹16, 6-8Y ₹18, 8-10Y ₹20 | 01-04-2026 |
| Royal Embroidery | Embroidery | A | ₹8.00 per piece | 01-04-2026 |
| Shree Wash House | Washing | D | ₹4,500 per lot, rework ₹5.00 | 01-04-2026 |

If a fabricator's stitching rate goes to ₹28 from 1 July 2026, add a **new** rate dated `01-07-2026`. Do not edit the old one.

**Deductions at billing.** When the labour bill is made, you can deduct shortage of pieces, missing trims, rejection penalty, or other amounts, and optionally apply TDS. These are entered per bill, not stored on the rate.

---

## 12. Price lists

*Masters → Price lists.* Selling rates by customer type. A price list has a name, a kind, and dated rates per style.

| Price list | Kind | Used for |
| --- | --- | --- |
| Wholesale | Wholesale | Wholesalers, distributors |
| Retail MRP | Retail | Showroom, walk-in |
| Dealer | Wholesale | Large dealers on better rate |

**Rates inside a list**

| Style | Size | Min qty | Rate (₹) | From |
| --- | --- | --- | --- | --- |
| JGR-104 | all sizes | 1 | 380 | 01-04-2026 |
| JGR-104 | all sizes | 120 | 365 | 01-04-2026 |
| JGR-104 | XXL | 1 | 395 | 01-04-2026 |
| TRK-201 | all sizes | 1 | 295 | 01-04-2026 |

- **Min qty** is a quantity slab: the rate applies from that many pieces (here 120 pieces or more gets ₹365).
- Leave **Size** empty to apply to all sizes, or fill it for a size surcharge.
- A **customer-specific special rate** on the party overrides the list for that customer and style.

A rate change is a new row with a new start date.

---

## 13. Opening balances and opening stock

Load these **last**, once everything above exists, and **on the books-begin date**.

### 13.1 Opening balances (money)

*Accounts → Opening balances.* Enter or import last closing balances as at the day before the books begin.

| Ledger | Debit | Credit | Reference | Due date |
| --- | --- | --- | --- | --- |
| Cash | 25,000 | | | |
| HDFC Bank Current A/c 1234 | 4,80,000 | | | |
| Machinery | 12,00,000 | | | |
| Capital – Owner | | 18,00,000 | | |
| Mehta Traders | 1,20,000 | | INV/25-26/0412 | 15-04-2026 |
| Mehta Traders | 80,000 | | INV/25-26/0431 | 30-04-2026 |
| Sri Ram Textiles | | 2,10,000 | PI/4471 | 20-04-2026 |

- Debtors and creditors need a **bill reference** per open bill, so payments can be matched to them later. The reference does not need to match any system number; use the original bill number.
- Total debits must equal total credits. Any difference is put in `Opening Balance Difference`, which should be **zero** when you finish. If it is not, your list is incomplete.
- Stock is **not** entered here. Enter stock in 13.2; it posts its own value.

### 13.2 Opening stock

*Inventory → Opening stock.* Choose factory and location, then enter lines or import Excel.

**Fabric — one row per roll**

| item | qty | rate | roll_no | lot | gsm | width_cm | length_m |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FAB-001 | 24.500 | 190 | OLD-001 | L3 | 280 | 180 | |
| FAB-001 | 26.200 | 190 | OLD-002 | L3 | 280 | 180 | |
| FAB-002 | 31.000 | 165 | OLD-003 | L1 | 180 | 170 | |
| FAB-003 | 8.400 | 240 | OLD-004 | R2 | 240 | 90 | |

**Trims and packing — quantity and rate, no roll**

| item | qty | rate |
| --- | --- | --- |
| TRM-001 | 800 | 2.40 |
| TRM-003 | 5000 | 0.85 |
| PKG-001 | 3000 | 1.20 |

**Finished goods — use the SKU barcode**

| item | qty | rate |
| --- | --- | --- |
| 0000000014 | 60 | 310 |
| 0000000023 | 48 | 310 |

Notes:

- `qty` is in the item's unit and `rate` is cost per unit. Fabric roll quantity is the actual weighed quantity.
- **Print roll labels** (*Inventory → Rolls → label*) and stick them on the rolls, so scanning works from day one.
- Count and enter physical stock on the **same day**, otherwise the first movements will not match what is on the shelf.

---

## 14. Importing from Excel

*Import* (in the menu). Five templates: **Parties, Styles, Materials, Opening stock, Opening balances**. Download the template from the screen, fill it, upload.

- Run **Check only** first. It validates everything and saves nothing.
- The import is **all or nothing**: if any row is wrong the file is rejected with row numbers. Fix and upload again.
- Rows are validated by the same rules as the screens.

| Template | Columns | Example row |
| --- | --- | --- |
| Parties | name, roles, mobile, contact_person, email, gstin, pan, category, credit_limit, credit_days, discount_pct | `Mehta Traders`, `customer`, `9876543210`, `Rakesh Mehta`, , `07ABCDE1234F1Z5`, , `wholesaler`, `300000`, `45`, `2` |
| Styles | style_no, name, product, colours, sizes, hsn, mrp, description | `JGR-104`, `Cuffed jogger`, `JGR`, `Black, Navy, Grey Melange`, `S, M, L, XL, XXL`, `6103`, `699` |
| Materials | code, name, kind, unit, composition, gsm, width_cm | `FAB-001`, `Cotton fleece 280 GSM`, `fabric`, `KG`, `80% cotton 20% polyester`, `280`, `180` |
| Opening stock | item, qty, rate, roll_no, lot, gsm, width_cm, length_m | `FAB-001`, `120`, `190`, `OLD-9`, `L3`, `280`, `180` |
| Opening balances | ledger, debit, credit, reference, due_date | `Cash`, `5000` |

Rules for the sheet:

- `roles`: customer, vendor, fabricator, agent, transporter, comma-separated.
- `category`: wholesaler, distributor, retailer, online, walkin, institutional.
- Styles: `product` and `sizes` must already exist; `colours` may be new. Every colour–size pair becomes a SKU and barcode.
- Materials: `kind` is fabric, trim or packing; `unit` is an existing unit code.
- Opening stock: fabric needs a `roll_no` on every row.
- Opening balances: `ledger` must match the ledger name exactly. Debtors and creditors need `reference` and optionally `due_date` in `YYYY-MM-DD`.
- BOMs, routes, labour rates and price lists are entered on screen, not imported.

---

## 15. Dry run — prove the setup before real work

Run one small lot through the whole system. This is the same flow as BRD scenarios A1–A3 and A10.

1. **Purchase fabric.** Purchase order → GRN into Main Godown with roll numbers and weights → QC → purchase invoice. Check the roll balance in *Inventory → Stock*.
2. **Create a production order** for `JGR-104`, Black, 20 pieces each of M and L, and release it. Route B is copied into the lot.
3. **Plan the route.** Check each step; assign stitching to Gurpreet Garments and embroidery to Royal Embroidery.
4. **Issue fabric** by roll. The roll balance reduces.
5. **Cut.** Enter pieces per size, fabric used and waste. Compare with the BOM variance shown. Create bundles and print QR tags.
6. **Issue a challan** to the embroiderer with the bundles; print it.
7. **Receive** the work back (enter a small shortage to see how it is handled), then **QC**: accept most, reject one.
8. **Move** accepted bundles through the next steps to Packing. Try moving one bundle backwards to see that a reason is required.
9. **Labour bill** for the fabricator. Check the amount is rate × **accepted** pieces, with any deduction and TDS shown.
10. **Reports.** Open the trial balance (it must tally) and the stock report (it must match the physical count).

If any figure looks wrong, fix the master (rate, BOM, route) and repeat. **Cancel** the dry-run documents afterwards. Do not edit or delete posted ones; cancelling reverses them cleanly.

---

## 16. Go-live checklist

- [ ] Company, GST/TDS settings and financial year correct
- [ ] All factories created, locations match physical places
- [ ] Every user created, with the correct role and factory
- [ ] Bank accounts and own ledgers added
- [ ] Units, sizes, colours, products, materials, processes checked
- [ ] 2–4 routes created and attached to styles
- [ ] Vendors, fabricators, customers, agents, transporters entered with mobile numbers and GSTIN/PAN
- [ ] Active styles, SKUs and BOMs entered
- [ ] Labour rates entered for every fabricator and process they do
- [ ] Price lists entered and attached to customers
- [ ] Opening balances posted; `Opening Balance Difference` is zero
- [ ] Opening stock entered and matches the physical count
- [ ] Roll labels printed and stuck on rolls
- [ ] Dry run completed; trial balance tallies; stock reconciles
- [ ] Dry-run documents cancelled
- [ ] Backup taken (copy of the database file) before the first real transaction

---

## 17. Common mistakes

| Mistake | Effect | Fix |
| --- | --- | --- |
| Two spellings of one colour | Two colours, split stock and reports | Use one; archive the other |
| Wrong unit on a material | BOM and stock in different units | Fix before any stock is entered; after that, create a new material |
| Fabricator has no labour rate | Work cannot be priced | Add a rate dated on or before the challan date |
| Rate dated after the challan date | Rate not applied to that challan | Date it from the start of your books |
| Duplicate customer mobile | Rejected on save | Search for the existing party first |
| Opening balances do not tally | Amount in `Opening Balance Difference` | Find the missing ledger |
| Stock entered a few days after the books start date | First movements do not match the shelf | Count and enter on the same day |
| Editing a posted document | Not allowed | Cancel it and make a correct one |
| One route for every style | Maintenance burden | Share 2–4 routes across styles |

---

## 18. Where to change things later

| To change | Go to | Notes |
| --- | --- | --- |
| A rate (labour, selling, GST) | Add a **new dated row** | Old documents keep the old rate |
| A BOM | New version on the style | Old lots keep the old version |
| A route | Edit the route | Existing lots keep their copy |
| Add a factory or location | Admin → Factories | Number series are created automatically |
| Permissions | Admin → Roles | Check with a test user |
| Tax switches | Tax | Effective-dated |
| Inventory rules | Settings → Inventory | Applies from that day |

Every master and transaction keeps a history of who changed what and when.
