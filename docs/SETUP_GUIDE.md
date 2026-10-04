# Setup and User Guide

**Part A (sections 0–18)** gets the ERP ready for operations. **Part B (sections 19–31)** is the day-to-day user guide: starting production, moving goods from process to process, paying fabricators, billing customers and recording receipts.

> **Open this guide any time** from the **?** icon in the top bar or **Help and user guide** in the menu. The icon opens the section for the screen you are on. Use the search box above the contents to find a word such as *challan* or *receipt*.

---

# Part A — Setup

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


---
---

# Part B — User guide: running operations

Part A prepared the masters. This part follows one lot from the production order to the customer's money in the bank. Examples continue from Part A: style `JGR-104`, route B, fabricators Gurpreet Garments and Royal Embroidery, customer Mehta Traders. Menu names and button labels are written as they appear on screen.

## 19. The whole journey on one page

| Stage | Screen | What changes |
| --- | --- | --- |
| 1 | Production → Production orders → New order → **Release order** | Order numbered; one **lot** per style and colour, each with its own copy of the route |
| 2 | Lot → **Issue fabric** | Rolls move from godown to cutting floor |
| 3 | Lot → **Cutting** → Make bundles and QR tags | Fabric cost goes into the lot; pieces become **bundles** with QR tags |
| 4 | **Move bundles** (in-house step) or **Challan** (fabricator step) | Bundle moves to the next step on the route |
| 5 | Challan → **Receive goods**, then **QC** | Accepted pieces become ready for the next step |
| 6 | Repeat 4–5 down the route | |
| 7 | Lot → **Pack into finished goods** | Pieces become saleable stock |
| 8 | Labour bills → **New labour bill**, then **Pay fabricator** on the posted bill | Fabricator paid for accepted pieces |
| 9 | Sale order → Packing list → **Invoice** (or Barcode billing) | Stock leaves, customer owes money |
| 10 | Posted invoice → **Receive payment** (or Accounts → Enter a voucher → Receipt) | Customer's bill settled |

**Rules the system enforces for you**

- Quantities always balance: pieces out of a step = pieces received at the next + loss + rejection + shortage.
- Moving a bundle **back** to an earlier step needs a reason.
- A fabricator is paid only for pieces that **pass QC**.
- Posted documents are never edited or deleted. You cancel them (with a reason) and enter a correct one.
- You only see and post in the factories assigned to you. Pick your factory in the top bar before posting.

**Who does what** (default roles; the owner can change them in Admin → Roles)

| Step | Role |
| --- | --- |
| Production order, route planning | Production Planner |
| Cutting, bundles, tags | Cutting Master |
| Move bundles, challans, receipts | Production Supervisor |
| QC | QC Checker |
| Labour bills and payments | Accountant |
| Over-receipt approval, closing an order | Owner |
| Sale orders, packing, invoices | Billing Clerk / Salesperson |
| Credit notes, receipts, cancelling invoices | Accountant |

Lot pages, fabric issue, cutting and QR tags are **not** menu items. Open the production order, then click the lot ("Lot … — status"). The lot page has the buttons: Issue fabric, Cutting, QR tags, Move bundles.

---

## 20. Start a production order

*Production → Production orders → New order.*

| Field | Example |
| --- | --- |
| Factory | LDH1 |
| Date | 05-10-2026 |
| Due date | 25-10-2026 |
| For | **Stock** (make for the shelf) or **Made to order** (for a customer order) |
| Order reference | Blank for stock. For made-to-order, the sale order number. Never type the customer's name; production staff must not see it |
| Remarks | Festive season lot |

**Lines** (one per style and colour; two blank rows are offered)

| Style | Colour | Total pieces | Size ratio |
| --- | --- | --- | --- |
| JGR-104 | Black | 300 | `S:1, M:2, L:2, XL:1` |
| JGR-104 | Navy | 120 | `M:2, L:2, XL:1` |

The ratio splits the total into whole pieces per size. Black becomes S 50, M 100, L 100, XL 50. Leftover pieces go to the largest remainders, and you see the result on the order.

Press **Save draft**. A draft can be edited; nothing else has happened yet.

**Release order** (needs edit permission):

- The system reads the style's **current BOM** and **default route**. If a style has no BOM or no default route, release stops with a message. Fix the style (section 10) and release again.
- The order gets its number, and **one lot per line** is created (Black and Navy are two lots).
- Each lot gets **its own copy of the route**, with each step's in-house or fabricator setting, default party and rate.

Order statuses: Draft → Released → In production → Partly completed → Completed → Closed. Status updates itself from the lots.

**Made to order** is a label plus the reference. When you confirm a made-to-order **sale order** (section 26), the system raises a draft production order for you with the sale order number as the reference.

**Closing an order early** (Owner only): *Close and write off*, with a mandatory reason. Bundles still in progress are written off at lot cost. Use only for abandoned lots.

---

## 21. Plan the route of each lot

Open the lot page. The **Route** table shows #, Process, Where, Rate and Status (Pending, In progress, Done, Skipped). The route was copied from the style, so for most lots **you change nothing**.

Change only what differs for this lot, using the **Change…** menu on a step or the forms below it. Every change needs a **reason** and is logged under *Route changes* with date, user and reason.

| Need | How | Rule |
| --- | --- | --- |
| Give a step to a different fabricator | Change → **Reassign**: Where = Fabricator, choose the fabricator, rate, rework rate | The party must be marked as a fabricator |
| Do a step in-house instead | Reassign: Where = In-house, choose the factory | An in-house step cannot carry a fabricator |
| Skip washing on this lot | Change → **Skip** | Only optional steps can be skipped |
| Add a missing step | **Add a step**: process, after step no., where, rate, reason | Cannot be inserted before a step that has started |
| Change the order of steps | **Move a step**: step, new position, reason | No step in the range may have started |
| Remove a step | Change → Remove | Not allowed if a challan already exists for it |

A step that is In progress or Done cannot be changed. Issuing a challan to a fabricator automatically assigns a pending step to that fabricator and logs it.

---

## 22. Issue fabric and cut

### 22.1 Issue fabric

Lot page → **Issue fabric**. The page lists rolls in the factory godown with a balance: Roll, Fabric, Lot/shade, GSM, In store.

1. Enter the **Issue qty** against each roll you are sending to the cutting floor (in KG).
2. Press **Issue to cutting floor**.

Rules: quantity must be above zero and cannot exceed the roll's balance; only fabric can be issued; at least one roll. If you mix rolls from different shade lots you get a warning and the issue is flagged "Mixed shade lots". The lot status moves from Planned to Cutting.

### 22.2 Record the cutting

Lot page → **Cutting** → *Record a lay*.

| Field | Example |
| --- | --- |
| Date | 06-10-2026 |
| Pieces cut per size (planned shown beside each) | S 50, M 100, L 100, XL 50 |
| Per roll: Used | OLD-001: 24.000 |
| Per roll: Waste | 0.500 |
| Per roll: Remnant returned | 0.000 |
| Notes | Lay 1, black fleece |

Press **Record cutting**.

- Used and waste become the lot's fabric cost. Remnant goes back to the godown.
- You cannot use more than the roll holds on the cutting floor.
- **Variance against the BOM.** The screen shows "Against the BOM (X expected): N%". If you go beyond the tolerance set in Inventory settings (default 5%) you get a warning. It does not block you.

Each lay is numbered 1, 2, … You can record several lays for one lot.

### 22.3 Make bundles and print tags

Under the lay, enter **Pieces per bundle** (for example 20) and press **Make bundles and QR tags**.

- Bundles are made per size. The last bundle of a size may be smaller. They are numbered B001, B002, … across the lot.
- One lay can be bundled only once.
- Pieces now sit on the cutting floor with status **Cut**.

Lot page → **QR tags**: choose **A4 sheet**, **Thermal 4 x 2 in** or **Thermal 2 x 1 in** and press Print, or download the **ZPL** file for a Zebra-type printer. Each tag shows the QR, style, colour and size, quantity, bundle number and lot number. Attach a tag to every bundle. All later work is done by scanning it.

---

## 23. Move goods from one process to the next

The route decides what comes next. For each step ask: **is it in-house or with a fabricator?**

| Next step is… | Use | Section |
| --- | --- | --- |
| In-house (ironing, finishing, QC, packing) | **Move bundles** | 23.1 |
| With a fabricator (stitching, embroidery, washing…) | **Job work challan**, then **Receive** and **QC** | 23.2 – 23.4 |

Bundle statuses you will see: Cut → At stage → Received, awaiting QC → Ready for next stage → … → Packed. Also Awaiting rework and Written off.

### 23.1 In-house move

*Production → Move bundles.*

1. Choose the **Lot** and press **Show bundles**.
2. **Scan** each bundle's QR (or type its number) in the scan box and press Enter. Scanning only ticks the row; everything is checked when you save.
3. For any bundle with pieces that did not arrive, fill **Loss**, **Rejected** or **Short** on its row.
4. Pick **Move to stage** (shown as "5. Ironing and pressing — in-house").
5. **At factory**: leave as "Stage default", or choose another factory to send the goods there (inter-factory move).
6. Press **Move selected bundles**.

What the system checks:

- The target step must be in-house. For a fabricator step it tells you to issue a challan instead; the link "Issue to a fabricator instead" takes you there.
- Mandatory steps in between cannot be skipped. Only optional steps can be skipped, and skipped steps cannot be targets.
- Only one lot at a time.
- A bundle with a fabricator must be received first. A bundle waiting for rework cannot move until it has been reworked.
- **Balance:** pieces leaving = pieces arriving + loss + rejected + short. Loss and short are removed from stock; rejected pieces go to the factory's **Rejects** location. A bundle with nothing left is Written off.
- **Going back:** moving to a step at or before the bundle's completed step counts as moving back. It needs a **Reason** and flags the bundle as rework.
- Inter-factory moves carry the lot's cost to the receiving factory automatically.
- When a bundle leaves an in-house step that has a rate, labour is added to the lot cost.

### 23.2 Issue to a fabricator (challan)

*Production → Job work → Challans → New challan* (or the link from Move bundles).

1. Choose **Lot**, **Kind** (Job work, or Rework for pieces sent back) and the **Step**, then **Show bundles**.
2. Choose the **Fabricator**, Date and **Expected back by**.
3. Scan or tick the bundles to send. Only eligible bundles not already on an open challan are listed.
4. Press **Save challan** (it is saved as a Draft).

The challan fills in the **rate** from the fabricator's labour rate (section 11), falling back to the step's rate. If neither exists you see "There is no labour rate for X on PROCESS. Add one under Labour rates, or set a rate on the step". For stitching it also lists the **trims** the BOM needs for these pieces, including wastage. A challan covers one lot.

If the same lot is already open with another fabricator you get a warning and must tick "Yes, issue this lot to another fabricator too".

On the challan page:

- **Issue challan.** The challan is numbered, bundles move to the fabricator's location, trims leave the godown, and the step is assigned to that fabricator.
- **Print** the challan to send with the goods. It carries a QR and lists the bundles and trims.
- **Discard draft** if you made it by mistake.

Challan statuses: Draft → Issued → Partly received → Fully received → Billed. (Cancelled if a draft is discarded.)

### 23.3 Receive the goods

Challan page → **Receive goods**.

| Field | Example |
| --- | --- |
| Date | 12-10-2026 |
| Receive into | Process Area |
| Counted, per bundle | the pieces actually counted, with the tick box |
| Trims: Returned / Missing | 0 / 10 |

Press **Receive**. Scanning the bundle tags ticks the rows.

- Counted **less than** issued records a **shortage**. It is valued at lot cost and recoverable on the labour bill.
- Counted **more than** issued is an **over-receipt**. Nothing moves, and the receipt waits for the owner. The owner opens the receipt and presses **Approve over-receipt**. Until then QC is blocked.
- A bundle cannot be received twice.
- After posting, the receipt is numbered, bundles become "Received, awaiting QC", returned trims go back to stock and missing trims become a deduction.

> A fabricator saying "done" does **not** change stock or pay. Only your receipt and QC do. (The fabricator mobile app is planned and is not available yet.)

### 23.4 Quality check (QC)

*Production → Job work → Receipts and QC →* open the receipt. For every bundle fill:

| Field | Meaning |
| --- | --- |
| Accepted | Pieces that pass |
| Rejected | Pieces that fail |
| Rework (whole bundle) | Send the entire bundle back for rework |
| Reject reason | Required if any piece is rejected |
| Rejected go to | **Rejects stock** (kept) or **Scrapped** (written off as loss) |

Press **Save QC**. The rules:

- Accepted + Rejected + Rework must equal the pieces received.
- If rework is above zero, accepted must be zero. The whole bundle goes back.
- QC is recorded once per bundle.

Results:

- **No rework:** the bundle becomes **Ready for next stage** and the step counts as complete for it. Move it on (23.1, or a new challan).
- **Rework:** the bundle becomes **Awaiting rework**. It cannot move until you issue a **Rework challan** (Kind = Rework) for it. The fabricator is then paid the rework rate.
- **Rejected:** goes to the Rejects location (or is scrapped).
- When every bundle on the receipt has QC, the receipt is **QC done**.

Only **accepted pieces are payable**.

### 23.5 A complete example: route B, lot JGR-104 Black

| Step | What the user does | Bundle status after |
| --- | --- | --- |
| 1 Cutting | Issue fabric, record the lay, make bundles, print tags | Cut |
| 2 Embroidery (Royal Embroidery) | New challan for all bundles, issue, print. Later: Receive, then QC (say 296 accepted, 4 rejected) | Ready for next stage |
| 3 Stitching (Gurpreet Garments) | New challan, issue. Later: Receive, then QC | Ready for next stage |
| 4 Ironing (in-house) | Move bundles to "Ironing and pressing"; enter Loss on a row if a piece was damaged | At stage |
| 5 Quality check (in-house) | Move bundles to "Quality check" | At stage |
| 6 Packing (in-house) | Move bundles to "Packing" | At stage |
| 7 Finished goods | Pack into finished goods (section 24) | Packed |

---

## 24. Pack into finished goods

When bundles reach the packing step, open the lot page → box **Pack into finished goods**.

1. Tick the bundles ("These bundles have reached packing").
2. Choose **Receive into** (default: the factory's Dispatch location).
3. Press **Pack**.

The pieces become **finished goods stock** at that location, valued at the lot's cost per piece (fabric + trims + labour). Each bundle becomes **Packed**. The message reads "N pieces packed into finished goods."

Rules: bundles must be in one factory and one lot, must have reached the packing step, and must have no rework pending. Locations such as transit, rejects and fabricator premises are not offered.

The lot becomes **Completed** when none of its bundles is still live; packed, written-off and scrapped bundles all count as finished. When every lot is complete the order is **Completed**.

### Tracking at any time

- **Production → Dashboard:** Cut today, Stitched today, Packed today; work in progress by stage and by factory; pieces with fabricators; late lots (past the due date); oldest open lots.
- The **Where is it?** box searches by order number, style number, lot number or order reference and lists each bundle with size, pieces, current stage, location and status.

---

## 25. Pay the fabricator

### 25.1 Labour bill

*Production → Labour → Labour bills → New labour bill.*

1. Choose **Fabricator** and **Factory**, then **Show what is payable**.
2. The screen lists **accepted QC pieces not yet paid**: Challan, Lot, Bundle, Accepted, Rate, Amount. It also lists the **deductions** it found: shortage of pieces (at lot cost) and missing trims (at unit cost).
3. Set the **Bill date**. Choose a **TDS** template, or **No TDS**.
4. Press **Save draft and review**.

Example: Gurpreet Garments, stitching at ₹26 per piece.

| Item | Amount |
| --- | --- |
| 296 accepted pieces × ₹26.00 | ₹7,696.00 |
| Shortage: 3 pieces | − ₹750.00 |
| Missing trims: 10 labels | − ₹8.50 |
| **Amount before TDS** | **₹6,937.50** |
| TDS 194C at 1% (if chosen) | − ₹69.38 |
| **Net payable** | **₹6,868.12** |

Your figures will differ; the arithmetic is the point: earned − deductions, then TDS on that figure.

Details:

- Flat-rate (type D) challans pay in proportion to accepted pieces over pieces issued.
- Errors you may meet: the fabricator has no payable ledger; nothing is payable; deductions are more than earned.
- On the draft, check the numbers, then press **Post bill** (or **Discard draft**).

**What posting does:** the bill is added to the lot's cost as job work; the net amount becomes owed to the fabricator (due date = bill date + the fabricator's credit days); TDS goes to TDS Payable; the challans become **Billed** once everything is received, QC'd and paid with no rework open.

To undo a posted bill, use **Cancel bill** with a reason. It reverses the entries and frees the pieces to be billed again.

### 25.2 Pay the money

Open the posted labour bill. It shows **Outstanding** and a **Pay fabricator** button. The button opens a **Payment voucher** with the fabricator, the amount still open and the bill reference already filled in. **Nothing is posted until you press Post.**

| Field | Example |
| --- | --- |
| Paid from | HDFC Bank Current A/c 1234 (you choose; the screen cannot know) |
| Paid to | Gurpreet Garments (filled in) |
| Amount | 6,868.12 (filled in; change it for a part payment) |
| Bill | **Against bill** (filled in) |
| Reference | The labour bill number (filled in) |

Choose **Paid from**, check the figures, and **Post payment voucher**. Afterwards the bill shows **Settled**. A part payment leaves the rest as **Outstanding**.

Pick the **factory in the top bar** that the bill belongs to before you post. The Payment voucher posts to the factory you are working in.

The same works for vendors: a posted purchase invoice has **Pay vendor**. Section 27 explains the Bill options.

---

## 26. Sell: order, pack, invoice

### 26.1 Sales settings (once)

*Admin → Settings → Sales settings.*

| Setting | Meaning | Suggested |
| --- | --- | --- |
| Invoice total | No rounding, or round to the nearest rupee (the difference posts to Round Off) | Round to nearest rupee |
| Discount limit % | Higher discounts need the "Discount above the limit" permission | 10 |
| E-invoicing is switched on | Shows the e-invoice and e-way bill buttons | Off until a provider is chosen |
| E-way bill needed from invoice value | | 50,000 |

### 26.2 Sale order

*Sales → Sale orders → New order.*

| Field | Example |
| --- | --- |
| Customer | Mehta Traders |
| Factory | LDH1 |
| Date / Due by | 08-10-2026 / 22-10-2026 |
| Type | **Ready stock** or **Made to order** |
| Remarks | |

Use **Add a style** to pick `JGR-104`. A grid appears with colours as rows and sizes as columns. Type pieces in each cell; row and column totals update. Each style has one **Rate** and one **Disc %**.

| Colour | S | M | L | XL | XXL |
| --- | --- | --- | --- | --- | --- |
| Black | 24 | 48 | 48 | 24 | 12 |
| Navy | 12 | 24 | 24 | 12 | 0 |

Leave **Rate** on "auto". It is found in this order, and the source is shown beside it:

1. The customer's **special rate** for the style (or its product).
2. The customer's **price list**, with the quantity slab (here 120+ pieces gets ₹365); a size-specific row beats a style-wide one.
3. The last invoice rate to this customer for the style.
4. Otherwise "No rate found; enter one."

Discount defaults to the customer's standing discount. Above the discount limit it is refused unless you have the permission.

Press **Save draft**, review, then **Confirm order**. Confirming gives the order its number. For **Made to order** it also raises a draft production order (section 20) with the sale order number as reference and no customer name.

Order statuses: Draft → Confirmed → Partly dispatched → Fully invoiced. Also Closed and Cancelled.

- Only a Draft can be edited.
- **Close the balance** short-closes an order, with a reason, when a customer will not take the rest.
- **Cancel order** needs a reason once confirmed, and is blocked while a live packing list or invoice exists.
- **Credit limit:** it is stored on the customer but is **not enforced**; nothing is blocked. To see what a customer already owes, choose them on a **Sales voucher** or **Journal voucher** (section 28): the outstanding amount appears beside the choice. The receivables ageing (section 29) shows it for every customer.
- Ready-stock orders reserve nothing at order time. Stock is checked when you finalise the packing list.

*Sales → Sale orders → Order book* shows open orders with their pending balance.

### 26.3 Packing and dispatch

*Sales → Packing and dispatch*, then **Pack** beside the order (or **Pack and dispatch** on the order).

| Field | Example |
| --- | --- |
| Pack from | Dispatch (LDH1) |
| Date | 15-10-2026 |
| Transporter | Jai Mata Roadlines |
| LR / docket no, LR date | 44821, 15-10-2026 |
| Vehicle no | PB10AB1234 |

In the **Pieces in each carton** grid, rows are order lines with "Left to pack" and columns are cartons (two to start; **Add a carton** up to 30). Fill what goes in each carton. No carton may be empty, and you cannot pack more than is left on the order.

**Save draft**, then **Finalise the list**. Finalising checks stock at that location (less pieces on other packed-but-not-invoiced lists) and numbers the list. Status: Draft → Packed → Invoiced.

Then **Print list** and **Carton labels**. Carton codes look like `C000123-01`; scanning one at billing adds the whole carton. A finalised list cannot be reopened: cancel it (with a reason) and pack again.

### 26.4 Invoice

**From a packing list:** on a Packed list press **Create invoice for the packed pieces**. A draft invoice is made at the order's rates and discounts. Transporter, LR and vehicle carry over.

**Counter sale by scanning:** *Sales → Barcode billing.*

1. Choose **Customer**, **Factory**, **Goods leave from** (location) and **Date**.
2. Scan each item's barcode in the scan box and press Enter. One scan adds one piece; a carton code adds the whole carton. "Unknown barcode" means the code is not a SKU or carton.
3. The rate and discount fill from the pricing lookup. Check Rate, Disc % and Amount on every row; the footer shows Pieces and Before GST.
4. Choose the GST option (below) and add notes.
5. **Post invoice**, or **Save as draft** to check first.

**GST on the invoice** (only if GST is switched on for the factory and date; otherwise "no tax is charged"):

| Option | When to use |
| --- | --- |
| **From the HSN slab and place of supply (suggested)** | Normal. Each line's per-piece value picks the slab from the style's HSN (for example up to ₹2,500 → 5%, above → 18%). Customer's state against factory state decides CGST + SGST or IGST |
| **One GST template for all items** | Special case; needs a reason if it differs from the suggestion |
| **No GST on this invoice** | Needs a reason; the suggestion is kept in the invoice log |

If a style has no HSN or no slab you get an error naming the style. Fix it in the masters (section 4) and retry. On a draft, **Change the GST on this invoice** → **Update GST** re-works the tax.

Amount per line = quantity × rate × (100 − disc%) ÷ 100. The due date = invoice date + the customer's credit days (Mehta Traders: 45).

**Post invoice** does all of this at once, or none of it:

- Numbers the invoice.
- Takes the pieces out of stock at the chosen location.
- Debits the customer as a **new bill** (reference = invoice number, due date as above).
- Credits sales and GST output, adjusts rounding, and books cost of goods sold against finished goods stock.
- Updates the order and packing list status.

Example: Mehta Traders, 120 pieces.

| Item | Amount |
| --- | --- |
| 120 pieces × ₹365 | ₹43,800.00 |
| Discount 2% | − ₹876.00 |
| Taxable value | ₹42,924.00 |
| IGST 5% (Delhi customer, Punjab factory) | ₹2,146.20 |
| Round off | − ₹0.20 |
| **Invoice total** | **₹45,070.00** |

**Invoice list and print.** *Sales → Sale invoices* has tabs All, Draft, Posted, Cancelled. Open an invoice → **Print** gives the tax invoice with QR, carton count and tax breakup. The invoice page links to its order, packing list and accounting voucher.

**Discard draft** removes a draft. A posted invoice is never edited.

**Cancel invoice** (Accountant; reason required) reverses the stock and the entries, rolls the order back and returns the packing list to Packed. It is blocked if a credit note exists on it or an e-invoice number was generated.

**E-invoice and e-way bill.** If switched on in Sales settings and the buyer has a GSTIN, a posted taxed invoice shows **Send e-invoice and e-way bill**. This version uses a **stand-in that makes test numbers only**; it does not contact the government portal. Do not use those numbers for real consignments until a real provider is connected.

### 26.5 Returns: credit note

Open the posted invoice → **Credit note** (or *Sales → Credit notes*).

| Field | Example |
| --- | --- |
| Date | Not before the invoice date |
| Goods come back to | Main Godown |
| Reason | Required. "6 pieces wrong colour" |
| Returning | Quantity per line, up to "Can be returned" |

**Save draft** → **Post credit note**. The pieces come back into stock at their original cost, sales returns and GST are reversed pro rata, and the customer is credited: first against that invoice's open bill, any excess **on account**. **Cancel credit note** needs a reason.

---

## 27. Receive the customer's money

**The quick way.** Open the posted sale invoice. It shows **Outstanding** and a **Receive payment** button. The button opens a **Receipt voucher** with the customer, the amount still open and the invoice reference already filled in. Choose **Received in** (cash or bank), check the amount, add a narration and press **Post receipt voucher**. The invoice then shows **Settled**. If the customer pays only part, enter that amount; the rest stays Outstanding.

**Any time.** *Accounts → Enter a voucher → Receipt.* Needs the Accountant role and a **single factory chosen in the top bar** (the form does not ask for it). Post it in the factory the invoice belongs to.

| Field | Example |
| --- | --- |
| Date | 28-11-2026 |
| Received in | HDFC Bank Current A/c 1234 (only cash and bank ledgers are offered) |
| Received from | Mehta Traders. The amount outstanding appears under the name |
| Amount | 45,070.00 |
| Bill | **Against bill** |
| Reference | The invoice number (pick from the list of open bills; the outstanding amount fills in) |
| Narration | RTGS UTR 1234567890 |

Press **Post receipt voucher**. The receipt is numbered and the customer's bill is settled.

**Bill options on every row**

| Option | Use when |
| --- | --- |
| **Against bill** | The customer is paying a specific invoice. You cannot settle more than is outstanding, and a fully paid bill cannot be paid again |
| **On account** | Money received without naming a bill. Settle it later |
| **Advance** | Money received before an invoice exists |
| **New bill** | Opening a fresh reference (rare, for old balances) |

One receipt can carry several rows, so one cheque can settle several invoices: **Add row** per invoice.

Rules: the account in a row cannot be the same as the cash or bank account (use a **Contra** voucher to move money between your own accounts); amounts are positive with at most two decimals; the date must be valid and not in a locked period.

**Fixing a mistake.** A posted receipt cannot be edited. Open it → **Cancel** with a reason (it makes a reversing entry), then enter the right one.

### 27.1 When the customer deducts TDS or takes a discount

The Receipt screen has no TDS or discount fields; every row is a credit to a party. As far as the code shows, the way to record the difference is a **Journal** voucher. Example: the customer pays ₹44,500 against a ₹45,070 invoice and deducts ₹570.

- Receipt voucher: ₹44,500 against the invoice.
- Journal voucher: debit "Discount Allowed", or a "TDS Receivable" ledger you create (section 6; none is seeded), ₹570; credit the customer ₹570 against the same bill.

Your accountant must confirm which ledger fits each case.

---

## 28. Other money vouchers

*Accounts → Enter a voucher.*

| Voucher | Use | Example |
| --- | --- | --- |
| **Payment** | Money out of cash or bank to a vendor, fabricator or expense | Pay Sri Ram Textiles ₹2,10,000 against bill `PI/4471` |
| **Receipt** | Money into cash or bank | Section 27 |
| **Contra** | Cash ↔ bank | Deposit ₹50,000 cash into HDFC |
| **Journal** | Any balanced entry between ledgers | Adjustments, TDS and discounts |

*Accounts → Sales and purchase entries* has manual **Sales**, **Purchase**, **Debit note** and **Credit note** vouchers. They are value-only: **no stock moves**. Prefer the document screens (invoices, GRN, purchase invoices) whenever goods are involved.

**See what a party owes as you enter.** When you choose a customer or vendor on a **Sales voucher** (and the other party vouchers), or choose a ledger on a **Journal**, **Payment** or **Receipt**, a note appears beneath it, for example *Outstanding ₹1,20,000.00 Dr (owes you) in 2 open bills · advance ₹5,000.00 Cr*. Dr means they owe you, Cr means you owe them. For an ordinary ledger such as a bank account it shows the balance. This is **information only**; it never stops you from posting.

A purchase invoice posts the vendor's bill (reference = their invoice number, with due date). Open the posted invoice and press **Pay vendor**, or use a Payment voucher with **Against bill**.

---

## 29. See what is owed and check the books

| Question | Screen |
| --- | --- |
| Who owes me, and how overdue? | Reports → Ageing → **Receivables ageing**. Buckets: Not due, 1–30, 31–60, 61–90, 91–180, 181–365, Over a year; plus Outstanding and Advance / on account. Each open bill is listed with its age. Click a party for its statement |
| Whom do I owe? | Reports → Ageing → **Payables ageing** |
| All dealings with one party | Accounts → Books → **Ledger statement**: choose the ledger and date range; opening balance, each entry, running balance; Excel export |
| What happened today? | Accounts → Books → **Day book** (filter by factory, dates, voucher type) |
| Is everything balanced? | Accounts → Books → **Trial balance** (debits must equal credits) |
| Profit and position | Accounts → Books → **Profit and loss**, **Balance sheet** |
| Find a voucher | Accounts → **All vouchers** (filter by factory, type, status, number) |
| Sales summary | Reports → **Sales** |
| Finished goods stock | Reports → **Finished stock** |
| GST filing data | Reports → GST → **GSTR-1 data**, **GSTR-3B summary**, **Tax register** |
| Fabricators | Production → Reports → **Fabricator reports**, **Daily summary** |

**Daily and weekly habits**

| When | Who | Check |
| --- | --- | --- |
| Daily | Supervisor | Production Dashboard: late lots, bundles stuck at a stage, receipts waiting for QC |
| Daily | Store keeper | Fabric stock against the physical count, trims running low |
| Daily | Accountant | Day book; trial balance tallies |
| Weekly | Accountant | Labour bills for accepted pieces; payments to fabricators; receivables ageing |
| Weekly | Owner | Approve over-receipts; ageing over 60 days |
| Monthly | Accountant | GST reports, then lock the period after filing |

---

## 30. If something looks wrong

| Message or problem | What it means | What to do |
| --- | --- | --- |
| "no BOM yet; define it before releasing" | The style has no BOM | Add the BOM (section 10), release again |
| "no default route" | The style has no default route | Set it on the style |
| "is done by a fabricator: issue a job work challan instead" | You tried to move into a fabricator step | Use New challan |
| "Moving back to an earlier stage needs a reason" | The target is at or before the bundle's completed step | Type the reason, or pick the right step |
| "pieces waiting for rework; finish that first" | QC sent the bundle back | Issue a Rework challan |
| "There is no labour rate for X…" | No rate for that fabricator and process | Add it in Labour rates, dated on or before the challan date |
| Receipt shows "Over-receipt, needs approval" | Counted more than issued | Owner approves, or recount |
| Nothing payable on a labour bill | No QC-accepted unpaid pieces | Complete QC first |
| "Pick a single factory in the top bar before entering a voucher" | Voucher entry needs one factory | Switch factory in the top bar |
| "No rate found; enter one" | No customer rate, price list or last invoice rate | Add a price list rate (section 12) or type the rate |
| "only X available at <location>" when finalising packing | Not enough stock at that location | Move or pack stock there first |
| A wrong posted document | Posted documents are never edited | Cancel with a reason, then enter a correct one |

---

## 31. What is not available yet

- **Fabricator mobile app** ("Done" marking, earnings): planned; the fabricator role has no screens yet. Your staff do receipts and QC.
- **E-invoice and e-way bill:** only a stand-in that makes test numbers.
- **Credit limit** on customers: stored but deliberately **not enforced**. The outstanding amount is shown when you choose a party on a Sales voucher or Journal.
- **Discount and TDS on receipts:** use a Journal voucher (section 27.1).
- **Stock reservation** for ready-stock orders: none at order time; stock is checked at packing.
