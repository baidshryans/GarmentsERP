# Setup and User Guide

**Part A (sections 0–18)** gets the ERP ready for operations. **Part B (sections 19–31)** is the day-to-day user guide: starting production, moving goods from process to process, paying fabricators, billing customers and recording receipts.

> **Open this guide any time** from the **?** icon in the top bar or **Help and user guide** in the menu. The icon opens the section for the screen you are on. Use the search box above the contents to find a word such as *challan* or *receipt*.

---

# Part A — Setup

For the owner, accountant and merchandiser. Follow the parts in order. Each master has a plain explanation, what to record, and filled-in examples taken from a track pant / jogger business in Ludhiana.

> **About the examples.** The firm, parties, GSTINs, rates and mobile numbers are made up so you can see the shape of the data. Replace every one with your real figures. GSTIN, PAN and TAN are checked for format, so use real numbers from your registration. Tax rates, HSN codes and TDS sections are starting points that **your accountant must confirm**.

**Menu paths** below are written like *Masters → Styles*. Some screens are only visible if your role allows them (Part 2).

**Home and the menu.** Home shows the everyday jobs as buttons grouped Buy, Make, Sell and Money, plus a "Needs your attention" list of what is waiting. The menu on the left holds the same screens grouped as Masters, Buy, Make, Sell, Stock, Money and Reports, with accountant and settings screens under More. Press Ctrl+K to find any screen by its new name or its old trade term (GRN, challan, debit note).

---

## 0. The order of setup

Later steps depend on earlier ones. Do not skip ahead.

| # | Step | Where | Who | Time |
| --- | --- | --- | --- | --- |
| 1 | Setup wizard: company, tax switches, financial year, first factory | `/setup/` (first login) | Owner | 15 min |
| 2 | More factories and locations | More → Settings → Factories | Administrator | 10 min |
| 3 | Roles and users | More → Settings → Roles, Users | Administrator | 30 min |
| 4 | Tax settings, HSN and GST slabs | More → Settings → Tax settings; Masters → Setup → HSN and GST slabs | Accountant | 20 min |
| 5 | Inventory settings | More → Settings → Inventory settings | Owner | 5 min |
| 6 | Chart of accounts: add bank accounts and your own ledgers | More → Accountant → Chart of accounts | Accountant | 30 min |
| 7 | Basic masters: units, sizes, colours, products, materials, processes | Masters | Merchandiser | 1–2 hours |
| 8 | Routes | Masters → Setup → Routes | Merchandiser + Production head | 30 min |
| 9 | Parties: suppliers, fabricators, customers, agents, transporters | Masters → Parties | Accountant / Purchase | 1–3 hours |
| 10 | Styles, SKUs and BOMs | Masters → Styles | Merchandiser | per style |
| 11 | Labour rates for each fabricator | Make → Labour rates | Production head + Accountant | 1 hour |
| 12 | Price lists | Masters → Price lists | Owner / Sales | 30 min |
| 13 | Opening balances and opening stock | More → Accountant → Opening balances, Opening stock | Accountant + Store Keeper | 1 day |
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
- **Active style list** with colours, sizes, and the accessories and packing materials each piece needs, by process.
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

*More → Settings → Factories.* One record per physical unit. Every voucher and stock movement belongs to a factory, and users only see the factories they are assigned to.

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

*More → Settings → Roles.* A role is a permission matrix: for each screen, tick **view / create / edit / cancel / approve**. A second block hides sensitive fields (customer phone, rates, cost) from the role.

The system supplies these. Copy and adjust rather than starting from blank.

| Role | Typical person | Can do |
| --- | --- | --- |
| Owner | Proprietor | Everything, including approvals |
| Administrator | IT / office manager | Company, factories, users, roles. Cannot post transactions |
| Accountant | Accountant | Vouchers, opening balances, books, tax settings, bills |
| Purchase Officer | Purchase | Purchase orders, suppliers |
| Merchandiser | Design / merchandising | Styles, BOM, routes, materials, price lists |
| Production Planner | Planner | Production orders and route planning |
| Production Supervisor | Floor supervisor | Move bundles, challans, receipts, QC |
| QC Checker | QC | Accept, reject, send back |
| Cutting Master | Cutting | Cutting entries, bundle tags |
| Store Keeper | Store | Goods received (GRN), transfers, opening stock, labels |
| Billing Clerk | Billing | Invoices, packing, dispatch |
| Salesperson | Sales | Orders and own customers |
| Fabricator | Outside stitcher | Own bundles and earnings on the mobile app |

Customer name and phone on made-to-order jobs are never shown to production roles, however you edit them.

### 3.3 Users

*More → Settings → Users → New.*

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

**HSN and slabs** (*Masters → Setup → HSN and GST slabs*). Each HSN has dated value slabs: the GST rate depends on the per-piece value.

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

*More → Settings → Inventory settings.*

| Setting | What it does | Suggested start |
| --- | --- | --- |
| Valuation method | **Weighted average** per item per factory, or **specific cost per fabric roll** | Weighted average. Choose specific roll only if rolls of the same fabric are bought at very different prices and you want exact cost per lot |
| Allow negative stock | Off blocks any issue above stock on hand | **Off** |
| PO approval limit | A PO above this value needs the owner's approval. 0 = every PO | `50000` |
| Cutting variance tolerance % | Pieces cut more or less than your estimate by more than this are flagged at cutting (22.1, 22.2) | `5` |
| Pieces per box | Pieces packed in one box. Packing then counts the boxes and prints a label for each (section 24). A style can have its own figure (10.1). Blank or 0 = boxes are not counted | Your usual box, for example `12` |

A change applies from that day. Earlier stock keeps its value.

---

## 6. Chart of accounts

*More → Accountant → Chart of accounts.* Seeded, editable. You need to **add your bank accounts and any party-specific or business-specific ledgers**.

**Add these ledgers**

| Ledger name | Group | Bill-wise |
| --- | --- | --- |
| HDFC Bank Current A/c 1234 | Bank Accounts | No |
| PNB Cash Credit A/c | Secured Loans | No |
| Machinery | Fixed Assets | No |
| Capital – Owner | Capital | No |
| Insurance | Indirect Expenses | No |
| Transport Inward – Fabric | Direct Expenses | No |

**Party ledgers.** Each customer, supplier and fabricator has a ledger: sundry debtors for customers, sundry creditors for suppliers and fabricators. Mark debtor and creditor groups **bill-wise** so payments can be matched to bills. The system links the right ledger when you save a party; override only for special cases.

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

- Choose the unit you **stock and issue** in. Fabric is almost always KG (or MTR if you buy by length). The style's material list (10.2) uses this unit.
- One code per distinct item. Different GSM, width or composition is a different material.
- The form asks for **Code**, **Name**, **Kind** and **Unit**. **Composition**, **GSM** and **Width (cm)** are under **More options** on the same form. A new material is active; the **Active** box appears when you edit one. The same holds for units, sizes, colours, products, processes, price lists and HSN codes: no Active box on a new one, and it shows on edit.
- Fabric is tracked **per roll** in stock, so colour and roll number are captured when the goods are received (GRN), not in the material name. If you buy the same cotton fleece in black and navy, make one material and record the colour per roll, or make `FAB-001-BLK` and `FAB-001-NVY` if your consumption differs by shade. Decide this once and stay consistent.

### 7.6 Processes

A process is a step of work. Each has a kind, which tells the system how to treat it.

| Code | Name | Kind |
| --- | --- | --- |
| CUT | Cutting | Cutting |
| STITCH | Stitching | Stitching |
| EMB | Embroidery | Value-add |
| PRINT | Printing | Value-add |
| PRINTEMB | Printing and embroidery | Value-add |
| WASH | Washing | Value-add |
| DYE | Dyeing | Value-add |
| IRON | Ironing and pressing | Finishing |
| FINISH | Thread cutting and finishing | Finishing |
| QC | Quality check | QC |
| PACK | Packing | Packing |

Add steps you actually use: `FLAT` Flatlock (Stitching), `BARTACK` Bartack and buttonhole (Stitching), `HEATPRESS` Heat transfer (Value-add).

Keep processes **coarse**. If one fabricator does stitching, flatlock and bartack in a single job at one rate, treat it as one process `STITCH`. Split only when different people do them or you pay separately. **Printing and embroidery** is seeded as one process for the same reason: use it when both are done together at one rate, in-house or outside.

**No loss allowed.** Tick this on a process where pieces cannot be lost, such as ironing (it is ticked on **Ironing and pressing** from the start). When bundles leave that step in-house, the Loss, Rejected and Short boxes are not offered and the system refuses a count: pieces out must equal pieces in. It applies to in-house moves only; a receipt from a fabricator can still be short.

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

### 8.2a Print first, stitch outside (seeded)

Cut in-house, printed and embroidered before stitching, stitched outside, ironed and packed in-house. There is no separate QC step: the stitched pieces are checked when they are received from the fabricator (23.4), and that check is the QC.

| Seq | Process | Mandatory | Assignment |
| --- | --- | --- | --- |
| 1 | Cutting | Yes | In-house |
| 2 | Printing and embroidery | Yes | In-house |
| 3 | Stitching | Yes | Subcontractor |
| 4 | Ironing and pressing | Yes | In-house |
| 5 | Packing | Yes | In-house |

Set a **Rate** on each in-house step you pay by the piece (cutting, printing and embroidery, ironing, packing): that rate times the pieces becomes in-house labour in the lot's cost. If a lot's printing and embroidery goes to an outside job worker, change that step to a fabricator on the lot (section 21) and send it by challan.

An installation set up before this route existed gets it by running `python manage.py seed_defaults` once. Nothing already there is changed, and a style uses the route only when you choose it as the style's default route.

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
- Do not leave out packing: it is what lets finished goods reach stock and billing. A QC step is needed only for a check you do in-house as its own stage; pieces back from a fabricator are always checked on the receipt.

---

## 9. Parties

*Masters → Parties → New.* One record per firm. A party can have several roles at once, for example a supplier who is also a customer.

The form asks first for what is needed every time: the **Firm name**, a **Mobile**, and **This party is a** Customer, Supplier or Fabricator (tick all that apply). When GST is switched on for the company (section 4) the **GSTIN** is asked there too. Everything else is under **More options** on the same form. That section opens by itself when something inside is filled in or has an error, so nothing you entered is ever hidden.

### 9.1 Fields

| Field | Notes |
| --- | --- |
| Firm name | The firm's name |
| This party is a | Customer, Supplier, Fabricator (tick all that apply) |
| Mobile | **Required**, 10 digits. A duplicate customer mobile is rejected |
| GSTIN | In view when the company is GST-registered, otherwise under More options. The format is validated; its state code sets the State, which drives CGST+SGST vs IGST |
| *Under More options:* | |
| Contact person | |
| Other mobile, landline, email | |
| PAN, TDS section | TDS section is a suggestion only. TDS applies only when chosen on a bill |
| Category | Wholesaler, Distributor, Retailer, Online, Walk-in, Institutional. For customers |
| Price list | For customers. See Part 12 |
| Discount % | Default discount |
| Credit limit, credit days | Warn when exceeded |
| Payment terms | Free text |
| Agent, Transporter | Default agent and transporter for this customer |
| Destination | Delivery city |
| This party is also an | Agent, Transporter |
| Active | Ticked. Untick to stop using the party |
| Addresses | Billing, shipping, with city, state, pincode |
| Special rates | Customer-specific rate per style or product, with a start date |

Party codes (`P0001`, `P0002` …) are generated for you.

### 9.2 Vendor — fabric supplier

| Field | Value |
| --- | --- |
| Firm name | Sri Ram Textiles |
| This party is a | Supplier |
| Contact / Mobile | Ramesh Gupta / `9811100022` |
| GSTIN | `03AAAAA1111A1Z5` |
| State | Punjab |
| Credit days | 30 |
| Payment terms | 30 days from invoice, RTGS |

### 9.3 Vendor — trims

| Field | Value |
| --- | --- |
| Firm name | Bharat Trims and Labels |
| This party is a | Supplier |
| Mobile | `9815500033` |
| GSTIN | `03BBBBB2222B1Z7` |
| Credit days | 15 |

### 9.4 Fabricator (job worker)

| Field | Value |
| --- | --- |
| Firm name | Gurpreet Garments |
| This party is a | Fabricator |
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
| Firm name | Mehta Traders |
| This party is a | Customer |
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
| Firm name | Walk-in Customer |
| This party is a | Customer |
| Mobile | `9876500099` (the shop counter's number; each customer mobile must be unique) |
| Category | Walk-in |
| Price list | Retail MRP |
| Credit limit | 0 (cash sale) |

### 9.7 Agent and transporter

| Firm name | This party is also an (More options) | Mobile | Note |
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
| HSN code | 6103 |
| Default route | Route B — Jogger with embroidered logo |
| MRP | 699 |
| Pieces per box | 12 (blank = the company's setting, section 5) |
| Colours | Black, Navy, Grey Melange |
| Sizes | S, M, L, XL, XXL |
| Image | Photo (optional; a thumbnail is made) |

Style no, Name, Product, Default route, Colours and Sizes are asked every time. **Description**, **MRP**, **Pieces per box**, **Image** and **Archived** are under **More options**; so is **HSN code**, unless GST is switched on for the company, when it is asked every time.

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

### 10.2 BOM (materials by process)

*Style → BOM.* The **accessories and packing materials one piece needs, and the process that uses each**. The input of a process is the pieces coming from the step before (tracked as bundles, so you never list them) plus these materials. The list is **optional**: an order can be released for a style that has none, and you then enter materials by hand when you send or move bundles.

**Fabric is not on the list.** You do not give fabric per piece in kg or metres. When you issue fabric to cutting you enter the pieces you expect from it, and after cutting the system compares the pieces actually cut with that estimate (22.1, 22.2). The material box does not offer fabric, and fabric lines on lists made before October 2026 are ignored and dropped the next time the list is saved.

The BOM is **versioned**: a change creates a new version and the old one is kept, so an old lot keeps the list it started with.

Each line has:

| Field | Meaning |
| --- | --- |
| Material | From the material master (trims, accessories, packing material) |
| Used in | The process that uses it: Stitching, Embroidery, Thread cutting and finishing, Packing and so on. Left as "By kind of material" it means Stitching for a trim and Packing for a packing material. Cutting cannot be chosen |
| Quantity per piece | In the material's unit |
| Wastage % | Allowance added on top |
| Size overrides | Different quantity for a size that uses more or less |

You can also add **per-piece charges** (not materials): a fixed amount per piece for a process, for example embroidery or washing, which the cost includes. A **Version note** (why this changed) is under **More options** at the bottom.

**BOM example — style JGR-104, version 1**

| Material | Used in | Unit | Qty / piece | Wastage % | Size override |
| --- | --- | --- | --- | --- | --- |
| Drawcord flat 12 mm | Stitching | MTR | 1.2000 | 2 | |
| Elastic 1.5 inch | Stitching | MTR | 0.7500 | 2 | XXL 0.8500 |
| Eyelet metal 8 mm | Stitching | PCS | 2.0000 | 0 | |
| Brand main label woven | Stitching | PCS | 1.0000 | 0 | |
| Sewing thread 40/2 | Stitching | CONE | 0.0100 | 5 | |
| Embroidery thread | Embroidery | CONE | 0.0050 | 5 | |
| Care label | Thread cutting and finishing | PCS | 1.0000 | 0 | |
| Polybag 10x14 | Packing | PCS | 1.0000 | 0 | |

Charges per piece (informational costing):

| Description | Process | Amount (₹/pc) |
| --- | --- | --- |
| Logo embroidery | Embroidery | 8.00 |

**How the list is used.** It only fills the screen in; what leaves the store is what you confirm.

- **A fabricator's step:** the challan lists the materials of that step's process for the bundles on it, and you can change them while it is a draft (23.2).
- **An in-house step:** when you move bundles into the step you are shown its materials to check before the move is saved (23.1).
- **Packing:** packing materials are asked for when you pack into finished goods (section 24), not when bundles reach the packing step.
- A bundle coming back to a step it has already been through (rework) is filled in as zero, so nothing is issued twice unless you type it.
- If a material is used in a process that a lot's route does not have, nothing fills it in. The lot page says so under **Not on this route**; add it by hand where it is really used, or choose the right process on the list.
- When two steps of a route are the same kind (two stitching processes), choose the process on each line. A line left as "By kind of material" is filled in at every step of that kind.


---

## 11. Labour rates (what each fabricator is paid)

*Make → Labour rates → New.* A rate is for one **fabricator + process**, with a start date. The first field is labelled **Fabricator or supplier**, because a supplier who also does job work can have a rate. Both start on "Choose…": the rate is not saved until you pick them ("Choose the fabricator or supplier.", "Choose the process."). A new rate never changes bills already made; it applies to challans issued after its date.

**Pay on.** Every rate says which pieces the fabricator is paid for. It is fixed on each challan when the challan is made, so changing the rate later never changes a challan already out.

| Pay on | What is paid | Rework | Pieces not returned (shortage) |
| --- | --- | --- | --- |
| **Pieces accepted at QC** (the default) | Only pieces that pass QC | Paid when the redone pieces pass: the rate plus the rework rate | Offered as a deduction, ticked |
| **Pieces received back** | Every piece that comes back, rejected or not. The loss on rejected pieces is yours | The first pass is already paid, so redone pieces earn the rework rate alone (nothing, if it is 0) | Offered as a deduction, **not** ticked: lost pieces are yours unless you tick it |

A fabricator who has no labour rate is paid the lot step's own rate, on accepted pieces.

There are four rate types. Choose one under **Rate type**; the form then shows only that type's fields.

| Rate type | Use when | What you enter |
| --- | --- | --- |
| **Per piece** | One rate per piece for the process | Rate per piece |
| **Per piece plus extras** | A rate per piece plus extras (flatlock, pocket, bartack) | Rate per piece and named extras per piece |
| **Different rate per size** | The rate depends on size | A rate for each size |
| **Fixed amount per lot** | A fixed amount for the lot (washing, dyeing) | Fixed amount per lot |

Every rate can also have a **rework rate per piece**: what the fabricator is paid to redo a rejected piece. It is under **More options**.

**Examples**

| Fabricator | Process | Rate type | Details | From |
| --- | --- | --- | --- | --- |
| Gurpreet Garments | Stitching | Per piece | ₹26.00 per piece, rework ₹6.00 | 01-04-2026 |
| Sharma Stitching | Stitching | Per piece | ₹25.00 per piece, **pay on pieces received back**, rework ₹0 | 01-04-2026 |
| Gurpreet Garments | Stitching | Per piece plus extras | ₹24.00 per piece + Flatlock ₹3.00 + Bartack ₹1.50 | 01-04-2026 |
| Gurpreet Garments | Stitching (kids) | Different rate per size | 4-6Y ₹16, 6-8Y ₹18, 8-10Y ₹20 | 01-04-2026 |
| Royal Embroidery | Embroidery | Per piece | ₹8.00 per piece | 01-04-2026 |
| Shree Wash House | Washing | Fixed amount per lot | ₹4,500 per lot, rework ₹5.00 | 01-04-2026 |

If a fabricator's stitching rate goes to ₹28 from 1 July 2026, add a **new** rate dated `01-07-2026`. Do not edit the old one.

**Deductions at billing.** When the labour bill is made, the screen offers the shortage of pieces and the missing trims it found, and you can optionally apply TDS. You tick what to take off on each bill; the owner can also waive a deduction for good (25.1). These are not stored on the rate.

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

*More → Accountant → Opening balances.* Enter or import last closing balances as at the day before the books begin.

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

*More → Accountant → Opening stock.* Choose factory and location, then enter lines or import Excel.

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
- **Print roll labels** (*Stock → Fabric rolls → label*) and stick them on the rolls, so scanning works from day one.
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

1. **Purchase fabric.** *Buy → Purchase orders → New purchase order*, then **Save and submit**. From there follow the violet Next button on each page: **Receive goods** (into Main Godown, with roll numbers and weights) → **Check quality** → **Post goods received** → **Enter supplier bill** → **Post supplier bill** → **Pay …** (section 19 lists every step). Check the roll balance in *Stock → Stock*.
2. **Create a production order** for `JGR-104`, Black, 20 pieces each of M and L, and release it. Route B is copied into the lot.
3. **Plan the route.** On the lot page open **Route and rates** and check each step; assign stitching to Gurpreet Garments and embroidery to Royal Embroidery.
4. **Issue fabric** by roll (the lot's Next button), with the pieces you expect from it. The roll balance reduces.
5. **Cut.** Enter pieces per size, fabric used and waste. Compare the pieces cut with the estimate you gave when issuing the fabric. Make bundles, then print the tags.
6. **Issue a challan** to the embroiderer with the bundles; print it. On route B embroidery is a mandatory step, so it is the Next button (Send to … for Embroidery). On a route where embroidery is optional, such as the seeded route A, it is not the Next button: it appears as the smaller link "Send to … for Embroidery (optional)" under **Also waiting**.
7. **Receive** the work back (Next: Receive from …; enter a small shortage to see how it is handled), then **QC** (Next: Check received pieces): accept most, reject one.
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
- [ ] Suppliers, fabricators, customers, agents, transporters entered with mobile numbers and GSTIN/PAN
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
| Add a factory or location | More → Settings → Factories | Number series are created automatically |
| Permissions | More → Settings → Roles | Check with a test user |
| Tax switches | More → Settings → Tax settings | Effective-dated |
| Inventory rules | More → Settings → Inventory settings | Applies from that day |

Every master and transaction keeps a history of who changed what and when.


---
---

# Part B — User guide: running operations

Part A prepared the masters. This part follows one lot from the production order to the customer's money in the bank. Examples continue from Part A: style `JGR-104`, route B, fabricators Gurpreet Garments and Royal Embroidery, customer Mehta Traders. Menu names and button labels are written as they appear on screen.

## 19. The whole journey on one page

| Stage | Screen | What changes |
| --- | --- | --- |
| 1 | Make → Production orders → New order → **Release order** (or **Release** in the list) | Order numbered; one **lot** per style and colour, each with its own copy of the route |
| 2 | Lot → Next button **Issue fabric** | Rolls move from godown to cutting floor |
| 3 | Lot → Next button **Record cutting**, then **Make bundles** (continues to the tags) | Fabric cost goes into the lot; pieces become **bundles** with QR tags, less any pieces lost in cutting |
| 4 | Lot → Next button **Move to …** (in-house step) or **Send to … for …** (fabricator step) | Bundle moves to the next step on the route |
| 5 | Lot → Next button **Receive from …**, then **Check received pieces** | Accepted pieces become ready for the next step; pieces for rework become a bundle of their own and go back |
| 6 | Repeat 4–5 down the route | |
| 7 | Lot → Next button **Pack into finished goods** | Pieces become saleable stock, counted into boxes when pieces per box is set |
| 8 | Challan → Next button **Make labour bill for …** (or Labour bills → **New labour bill**), then **Pay fabricator** on the posted bill | Fabricator paid for the pieces his rate pays: accepted, or received |
| 9 | Sell → Sale orders → New order → **Save and confirm**, then the Next button on each page: **Pack goods** → **Finish packing and make bill** → **Post bill** (or Quick billing for a counter sale) | Stock leaves, customer owes money |
| 10 | Posted bill → Next button **Receive money from …** (or Money → Money received) | Customer's bill settled |

**Rules the system enforces for you**

- Quantities always balance: pieces out of a step = pieces received at the next + loss + rejection + shortage.
- Moving a bundle **back** to an earlier step needs a reason.
- A fabricator is paid by the terms of his labour rate: for pieces that **pass QC**, or for every piece **received back**. No piece is paid twice.
- A step marked **no loss allowed** (ironing) lets no piece be lost in-house.
- Posted documents are never edited or deleted. You cancel them (with a reason) and enter a correct one.
- You only see and post in the factories assigned to you. Pick your factory in the top bar before posting.

**Who does what** (default roles; the owner can change them in More → Settings → Roles)

| Step | Role |
| --- | --- |
| Production order, route planning | Production Planner |
| Cutting, bundles, tags | Cutting Master |
| Move bundles, challans, receipts | Production Supervisor |
| QC | QC Checker |
| Labour bills and payments | Accountant |
| Over-receipt approval, closing an order | Owner |
| Sale orders, packing, bills, returns from customers | Billing Clerk / Salesperson (orders only) |
| Receipts, cancelling bills and returns | Accountant |

Lot pages, fabric issue, cutting and tags are **not** menu items. Open the production order, then click the lot ("Lot … — status"). Releasing an order that has one lot opens that lot directly.

The lot page tells you what to do next. At the top is a **journey strip**: Order, Fabric, Cut, each step of the route, then Finished goods. Each stage is shown as done, now or to come, with the pieces sitting there, the fabricator's name on outside steps, and an "optional" tag on steps that can be skipped. An optional step stays on the strip while bundles could still go to it; once every bundle is past it, the strip keeps it only if bundles really went there (showing those pieces, then done) and drops it if nobody used it. Below it is one violet **Next** button naming what the lot needs, for example Issue fabric, Record cutting, Make bundles, Move to a stage, Send to a fabricator, Receive from a fabricator, Check received pieces or Pack into finished goods. The Next button points at the next mandatory step. Optional steps, and any other pending actions when bundles are spread over several stages, are listed beside it as smaller links under **Also waiting**. If the next step belongs to another role, the page says **Waiting for:** and the step instead of a button. A finished lot says "This lot is complete." **Route and rates**, **Lot cost** and **History** are folded sections; click one to open it. A **Corrections** row keeps Fabric issue, Cutting and Move bundles reachable if you need to go back, and the header keeps **Print tags**. Fabric issue, cutting, tags, challan and receipt pages have a **Back to lot** button.

Challans and receipts guide you the same way (section 23.2). On Home, **Receive from fabricator** opens *Sent to fabricators* on the **Out with fabricators** tab: only the challans that are issued or partly received, each with a **Receive from …** button in its **Next step** column.

**Buying guides you the same way.** The purchase order, goods received, supplier bill and return pages open with one journey strip, **Ordered → Approved → Received → Checked → Billed → Paid**, and one violet Next button. **Approved** appears only on an order above the approval limit. Goods received without an order start at Received; a direct supplier bill (no goods received) starts at Billed. The strip shows how much has come ("60 of 100"), the amount billed and the amount still unpaid. The lists *Buy → Purchase orders*, *Goods received* and *Supplier bills* have a **Next step** column with the same button on every row, so you can work straight down a list.

| Where the purchase is | Next button | What it opens |
| --- | --- | --- |
| New order | **Save and submit** on the form (or **Save draft**, then **Submit order**) | The order gets its number. Up to the approval limit it is approved at once |
| Order above the approval limit | **Approve order** (owner) | The order page; **Send back** returns it to draft with a reason |
| Order approved, goods still to come | **Receive goods** | A new goods received entry with the order's pending lines filled in |
| Goods received saved, not checked | **Check quality** | The goods received page. If everything is fine press **Accept all and post**: every line is accepted and the goods come into stock in one step. If something is rejected, mark it, press **Finish QC**, then **Post goods received**. **Accept all and post** is offered only while nothing has been recorded; if you typed a rejection or a remark and press it, nothing is posted, what you typed is saved, and the page asks you to press **Finish QC** (or clear it to accept everything). Pressing Enter in a field presses **Save QC** |
| Goods received checked, not posted | **Post goods received** | Accepted goods come into stock; rejected goods get a draft return automatically |
| Goods posted, no bill yet | **Enter supplier bill** | The new bill form for that supplier, with these goods ticked. Other goods of the same supplier that are not billed yet are listed unticked. Quantity already on another draft bill is left out, and the form says which draft holds it ("1 line is already on draft bill …"); post or discard that draft first. **Save draft and review** |
| Bill saved as a draft | **Post supplier bill** | The bill page. Tax is added only if you chose it on the bill |
| The supplier billed goods you rejected | **Return rejected goods to supplier** | The draft return; **Post return** sets their value against the bill that billed them, so the bill shows less unpaid (bill 10,000, return 2,000: the bill then shows 8,000). It is offered only after that bill is posted, and before paying |
| Bill posted, amount unpaid | **Pay** and the supplier's name | *Money paid* with the supplier, the amount left to pay and the bill reference filled in. Choose **Paid from** and post. A part payment leaves the rest on the button. A posted return of rejected goods has already reduced the bill, so the amount is what is really left |
| A return of goods already in stock, saved as a draft | **Post return** | The return page (*Buy → Returns to supplier*) |
| Nothing left | Order and goods received pages: "This purchase is complete." Bill page: "This supplier bill is paid." Return page: "This return is posted." | |

- The order page shows the steps of all its goods received and bills; the goods received page shows its own and its bills'; the bill page shows its own. The same step has the same name and opens the same screen wherever you see it.
- While a goods received entry of an order is still unchecked or unposted, the order's Next button points at that one. A second delivery can still be received: the order page keeps a plain **Receive goods** button in its header for as long as goods are still to come.
- If the supplier bills only what you accepted, the draft return for the rejected goods simply waits; the purchase is complete without it. The return page says it is waiting for the supplier's bill. If everything was rejected, the goods received page shows that waiting message instead of "complete".
- **What a return does to the bill.** A return of rejected goods reduces the bill it relates to: the **Outstanding** figure in the bill's header, *Whom I owe* and the Pay button all show the bill less the return. If the return covers two bills, each is reduced by its own share. If the bill was already paid (in full or in part), the part it no longer has open goes on the supplier's account in your favour instead. Cancelling the return puts the bill back.
- A return of goods **already in stock** (*Buy → Returns to supplier*) is not tied to a bill: it stays on the supplier's account for the accountant to settle (a Payment or Journal with the Bill options, section 27). When you pay a bill, the Next button's note mentions any amount the supplier has on account.
- Returns of rejected goods posted **before this change** are not altered: they still sit on the supplier's account and the bill's header still shows the full amount. For those the Pay button asks for the bill less the return ("10000.00 on bill … less 2000.00 returned: 8000.00 is left to pay") and the bill page explains the difference in one line under the Next button. Pay the amount on the button.
- On the new order form **Save draft** comes first, so pressing Enter in a field saves a draft; **Save and submit** is the violet button.
- A short-closed order asks for no more goods, but what it did receive is still billed and paid from its Next button.
- If the next step belongs to another role the page says **Waiting for:** and the step. The default roles: Purchase Officer orders, Store Keeper receives and checks, Accountant enters bills and pays, Owner approves.
- **The buying forms ask only for what is needed every time.** *Purchase order:* Supplier, Date and the items; **Expected by** and **Notes** are under **More options**. *Goods received (GRN):* Supplier, Receive into, Date and the items; the supplier's challan no. and date and Notes are under More options. *Supplier bill:* Supplier's bill no., Bill date, the received goods to bill, and one **GST** choice that starts on "No tax". The GST template, the by-hand amounts and the input credit tick appear only for the choice that uses them, inside **Tax (GST / TDS)**, where **Deduct TDS** also sits; that section opens when you choose a GST option. The Booking date (today unless you change it) and Notes are under More options. *Return to supplier:* Supplier, Date, Reason and the items; GST on the return is under **Tax (GST)**. A folded section opens by itself when something inside is filled in or has an error.
- **The supplier must be chosen.** On a purchase order, goods received and a return to supplier the **Supplier** starts on "Choose…" (it is filled in for you when you receive against a purchase order). Saving without one is refused with "Choose the supplier." and everything you typed is kept. The same rule holds for the **Customer** on a sale order and on quick billing, and for the **Fabricator** when you send to a fabricator or add a labour rate.
- **Editing a draft goods received** saves a change of supplier and of the supplier's challan date. One received against a purchase order keeps that order's supplier, shown as fixed text.
- **Enter supplier bill** makes the bill in the factory chosen in the top bar. If another factory is chosen, you are sent back to the goods received page with a message; choose the right factory and press the button again.

**Selling guides you the same way.** The sale order, packing list, bill and return pages open with one journey strip, **Ordered → Confirmed → Packed → Billed → Paid**, and one violet Next button. A bill made by Quick billing has no order and starts at Billed. The strip shows the pieces ordered, how many are packed ("20 of 60"; a draft packing list does not count yet), the amount billed and the amount still to receive. The lists *Sell → Sale orders*, *Packing and dispatch* and *Bills* have a **Next step** column with the same button on every row. Section 26 has the details of each screen.

| Where the sale is | Next button | What it opens |
| --- | --- | --- |
| New order | **Save and confirm** on the form (or **Save draft**, then **Confirm order**) | The order gets its number; a made-to-order order also raises its production requirement |
| Order confirmed, pieces still to pack | **Pack goods** | A new packing list for that order, showing what is left to pack |
| Packing list saved as a draft | **Finish packing** | The packing list. **Finish packing and make bill** finishes the list and drafts its bill in one step, then opens the bill; **Finish packing** alone only finishes the list |
| Packing list finished, no bill yet | **Make bill** | The packing list; the button drafts the bill for the packed pieces and opens it |
| Bill saved as a draft | **Post bill** | The bill. Choose or waive GST first if you need to (**Change the GST on this bill** → **Update GST**), then post |
| Bill posted, money still to come | **Receive money from** and the customer's name | *Money received* with the customer, the amount still to receive and the bill reference filled in. Choose **Received in** and post. A part payment leaves the rest on the button |
| A return saved as a draft | **Post return** | The return (*Sell → Returns from customer*). Posting it reduces what is to be received on its bill |
| Nothing left | Order page: "This sale is complete." Packing list: "This packing list is billed and paid." Bill: "This bill is settled." Return: "This return is posted." | |

- The order page shows the steps of all its packing lists and bills; the packing list shows its own and its bill's; the bill shows its own and its draft returns'. The same step has the same name and opens the same screen wherever you see it.
- What is furthest behind comes first: with pieces still to pack and a finished list waiting for its bill, the Next button is **Pack goods** and **Make bill** is listed under **Also waiting**.
- While a packing list of an order is a draft, the order's Next button points at that one. A second packing list can still be started: the order page keeps a plain **Pack goods** button in its header for as long as pieces are on no packing list.
- **Made to order.** Until some of the ordered pieces are in finished stock at the factory, the order page says **Waiting for: goods from production** and gives no button; the Sale orders list says the same on that row. The pills under "Where the pieces are in production" show how far they are. Once production packs them into finished goods (section 24) the Next button becomes **Pack goods**. Production screens never show the customer. The order waits only while its production order can still deliver: once that production order is completed or closed and nothing is in stock, the Next button is **Pack goods** with the note below, and **Close the balance** is there if the pieces will never come.
- **Nothing in stock.** Pieces already on another finished packing list that is not billed yet do not count as stock, exactly as when you finish a list. When none of the pieces still to pack is in stock, **Pack goods** is still offered (for a ready-stock order, and for a made-to-order order whose production is over) with the note "None of these pieces is in finished stock yet; the list can be saved but not finished."
- **Money the customer already has with you.** If the customer has an advance or a credit on account, the Receive money button still asks for the whole bill, and its note adds "This customer also has … on account from advances or returns." Receive the difference, or set the advance against the bill with the Bill options (section 27). When nothing is left to receive on a bill and the customer still has such money, the bill page and the return page say "… is held on the customer's account. Adjust it against the next bill, or refund it from Money paid."
- **Drafts that can no longer be posted.** A draft return whose bill was cancelled says "Its bill was cancelled. Discard this draft return." A draft bill whose packing list is no longer a finished one says "Its packing list was cancelled. Discard this draft bill." Neither offers posting; press **Discard draft**.
- **What a return does to the bill.** A posted return is set against its bill: the **Outstanding** figure in the bill's header and the Receive money button both show the bill less the return (bill 30,000, return 2,000: 28,000 to receive). If the bill was already paid, the credit goes on the customer's account instead and the bill asks for nothing more.
- The amount on the Receive money button is the same figure as **Outstanding** in the bill's header. The header also has a plain **Receive money** button that opens the same voucher.
- On the new order form **Save draft** comes first, so pressing Enter in a field saves a draft; **Save and confirm** is the violet button and is offered only to roles that may confirm orders. Editing a draft has **Save draft** only.
- An order closed with **Close the balance** asks for no more packing, but what was sent is still billed and collected from its Next button.
- If the next step belongs to another role the page says **Waiting for:** and the step, and names of documents you may not open are shown as plain text instead of links. The default roles: Salesperson takes and confirms orders, Billing Clerk packs, bills and posts returns, Accountant receives the money.

---

## 20. Start a production order

*Make → Production orders → New order.*

| Field | Example |
| --- | --- |
| Factory | LDH1 |
| Date | 05-10-2026 |
| Due by | 25-10-2026 |
| For | **Stock** (make for the shelf) or **Made to order** (for a customer order) |
| Order reference | Blank for stock. For made-to-order, the sale order number. Never type the customer's name; production staff must not see it |
| Notes | Festive season lot |

**For**, **Order reference** and **Notes** are under **More options**. Left alone, the order is for stock. On a draft you can change all three, including **For**.

**Lines** (one per style and colour; two blank rows are offered)

| Style | Colour | Total pieces | Size ratio |
| --- | --- | --- | --- |
| JGR-104 | Black | 300 | `S:1, M:2, L:2, XL:1` |
| JGR-104 | Navy | 120 | `M:2, L:2, XL:1` |

The ratio splits the total into whole pieces per size. Black becomes S 50, M 100, L 100, XL 50. Leftover pieces go to the largest remainders, and you see the result on the order.

Press **Save draft**. A draft can be edited; nothing else has happened yet. In the production orders list the **Next step** column shows **Release** for a draft, the lot's next action once it is released, or **Open** when the order has several lots. The order page shows each lot's next action beside the lot, and Home's **Items in production** table has the same column.

**Release order** (needs edit permission):

- The system reads the style's **current BOM** and **default route**. If a style has no default route, release stops with a message. Fix the style (section 10) and release again. A style with **no BOM** is released all the same, with a note that no accessories will be filled in for it: you enter them by hand when bundles go to a process (10.2).
- The order gets its number, and **one lot per line** is created (Black and Navy are two lots).
- Each lot gets **its own copy of the route**, with each step's in-house or fabricator setting, default party and rate.

Order statuses: Draft → Released → In production → Partly completed → Completed → Closed. Status updates itself from the lots.

**Made to order** is a label plus the reference. When you confirm a made-to-order **sale order** (section 26), the system raises a draft production order for you with the sale order number as the reference.

**Closing an order early** (Owner only): *Close and write off*, with a mandatory reason. Bundles still in progress are written off at lot cost. Use only for abandoned lots.

---

## 21. Plan the route of each lot

Open the lot page and go to **Route and rates**. While the lot is still Planned it is already open for anyone who may change the route; later, click it to unfold. The table shows #, Process, Where, Rate and Status (Pending, In progress, Done, Skipped). The route was copied from the style, so for most lots **you change nothing**.

Change only what differs for this lot, using the **Change…** menu on a step or the forms below it. Every change needs a **reason** and is logged under **History** on the lot page with date, user and reason.

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

Lot page → Next button **Issue fabric** (or **Fabric issue** in the Corrections row). The page lists rolls in the factory godown with a balance: Roll, Fabric, Lot/shade, GSM, In store.

1. Enter the **Issue qty** against each roll you are sending to the cutting floor (in KG).
2. Enter **Pieces you expect from this fabric**: your own estimate for the fabric on this issue, for example 150 pieces from 60 kg. It is optional; leave it empty and no comparison is made.
3. Press **Issue to cutting floor**.

Rules: quantity must be above zero and cannot exceed the roll's balance; only fabric can be issued; at least one roll. If you mix rolls from different shade lots you get a warning and the issue is flagged "Mixed shade lots". The lot status moves from Planned to Cutting. After you save you go straight on to cutting.

**Your estimate.** The page shows **Planned pieces**, **Fabric with the lot** and, once an issue carries an estimate, **Your estimate so far**. If the estimate is fewer than planned it says how many pieces short, so you can issue more before cutting. Each issue in "Issued so far" shows its own "estimated N pieces". Estimates of several issues add up. Fabric you send back as a remnant is taken out of the estimate in proportion, so you are judged only on the fabric you kept. The system never works the pieces out from kg per piece: the figure is yours.

### 22.2 Record the cutting

Lot page → Next button **Record cutting** (or **Cutting** in the Corrections row) → *Record a lay*.

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
- **Pieces cut against your estimate.** Under each lay: "By your estimate the fabric burnt should give N pieces · cut N" and "Pieces cut against the estimate: N%". Example: you expected 150 pieces from 60 kg, the lay burnt 43 kg (used plus waste), so it should give 107; you cut 100, which is −6.54%. Beyond the tolerance set in Inventory settings (default 5%), over or under, you get a warning. It does not block you. With no estimate on the fabric issue there is no comparison.
- The lot page shows **Planned**, **Estimated from fabric** and **Cut** side by side.
- If the cutting step has a **rate** and is in-house, that rate times the pieces cut is added to the lot's cost as in-house labour.

Each lay is numbered 1, 2, … You can record several lays for one lot.

### 22.3 Make bundles and print tags

Under the lay, enter **Pieces per bundle** (for example 20). If pieces were lost or spoiled in cutting, enter them per size in **Lost in cutting**. Then press **Make bundles and QR tags**. After you save you go straight on to the tags.

- Pieces lost in cutting are left out of the bundles, and can be no more than the pieces cut of that size. Their fabric stays in the lot's cost, and the cutting rate is still paid on every piece cut. The lot page shows **Lost in cutting**.
- Bundles are made per size. The last bundle of a size may be smaller. They are numbered B001, B002, … across the lot.
- One lay can be bundled only once.
- Pieces now sit on the cutting floor with status **Cut**.

Lot page → **Print tags** (also shown after making bundles): choose **A4 sheet**, **Thermal 4 x 2 in** or **Thermal 2 x 1 in** and press Print, or download the **ZPL** file for a Zebra-type printer. Each tag shows the QR, style, colour and size, quantity, bundle number and lot number. Attach a tag to every bundle. All later work is done by scanning it.

---

## 23. Move goods from one process to the next

The route decides what comes next. For each step ask: **is it in-house or with a fabricator?**

| Next step is… | Use | Section |
| --- | --- | --- |
| In-house (ironing, finishing, QC, packing) | **Move bundles** (Next button **Move to …**) | 23.1 |
| With a fabricator (stitching, embroidery, washing…) | **Job work challan** (Next button **Send to … for …**), then **Receive** and **QC** | 23.2 – 23.4 |

Bundle statuses you will see: Cut → At stage → Received, awaiting QC → Ready for next stage → … → Packed. Also Awaiting rework and Written off.

### 23.1 In-house move

*Make → Move bundles*, or the lot's Next button **Move to …**.

1. Choose the **Lot** and press **Show bundles**.
2. **Scan** each bundle's QR (or type its number) in the scan box and press Enter. Scanning only ticks the row; everything is checked when you save.
3. For any bundle with pieces that did not arrive, fill **Loss**, **Rejected** or **Short** on its row.
4. Pick **Move to stage** (shown as "5. Ironing and pressing — in-house"). When you came from the lot's Next button, the stage it named is already chosen. The **Next stage** column on each row names where that bundle goes next: the next mandatory step after where the bundle actually is, the same step the lot's Next button names. A bundle sitting at Stitching shows the step after Stitching, and optional steps are passed over. Only when no mandatory step is left does it show the next optional step. Two cases cannot be moved from this screen, and the column says so: **With fabricator** for a bundle that is out on a challan (receive it first, 23.3), and the stage name followed by **(by challan)** when the next stage is done by a fabricator (issue a challan, 23.2).
5. **At factory**: leave as "Stage default", or choose another factory to send the goods there (inter-factory move).
6. Press **Move selected bundles**.
7. **Materials for the stage.** If the style's list has materials for this stage (10.2), a second page shows them with the quantity worked out for the pieces you are moving. Change a quantity to what is really handed over, clear it to leave a material out, or add another material in the empty rows, then press **Move to …**. The materials leave the factory's Main Godown and go into the lot's cost in the same save as the move; if stock is short the move is refused and nothing is saved (unless negative stock is allowed in Inventory settings). **Cancel** takes you back with nothing moved. To issue materials that are not on the list, tick **Issue materials from the store with this move** before pressing Move. A stage with nothing on the list, and no tick, moves straight away as before. The lot page lists what was issued under **Materials used in-house**.

What the system checks:

- The target step must be in-house. For a fabricator step it tells you to issue a challan instead; the link "Issue to a fabricator instead" takes you there.
- Mandatory steps in between cannot be skipped. Only optional steps can be skipped, and skipped steps cannot be targets.
- Only one lot at a time.
- A bundle with a fabricator must be received first. A bundle waiting for rework cannot move until it has been reworked.
- **Balance:** pieces leaving = pieces arriving + loss + rejected + short. Loss and short are removed from stock; rejected pieces go to the factory's **Rejects** location. A bundle with nothing left is Written off.
- **Going back:** moving to a step at or before the bundle's completed step counts as moving back. It needs a **Reason** and flags the bundle as rework.
- When you open the screen from the lot's Next button, saving returns you to the lot. When you open it from the menu it stays on the screen, so you can keep scanning.
- Inter-factory moves carry the lot's cost to the receiving factory automatically.
- When a bundle leaves an in-house step that has a rate, labour is added to the lot cost, on the pieces that pass. A bundle sent back is paid the step's rework rate for the stage it redoes, then the normal rate again once it moves on.
- **No loss allowed.** For a bundle at a step marked so (ironing), the three boxes are replaced by "No loss allowed at this stage".
- **Only take out loss, do not move.** When pieces are lost at an in-house step and the next step is a fabricator's, fill Loss, Rejected or Short, type a **Reason** and press this button. The pieces come out of the bundle where it stands. Do this before the challan: a challan sends whatever is in the bundle, and the fabricator would otherwise be shown short.

### 23.2 Issue to a fabricator (challan)

*Make → Sent to fabricators* (the challan list) *→ Send to fabricator*, Home → **Send to fabricator**, the lot's Next button **Send to … for …**, or the link from Move bundles.

1. Choose the **Lot** and the **Step**, then **Show bundles**. The form is for normal job work, so it does not ask the kind. **Kind** (Job work, or Rework for pieces sent back) is under **More options**, and the lot's **Send back for rework** link opens the form with Rework already chosen. For Rework the step starts on the one the first waiting bundle came back from.
2. Choose the **Fabricator**, Date and **Expected by**. The fabricator starts on "Choose…" unless the step already has one; without one the form is refused with "Choose the fabricator." and your ticks are kept. **Notes** are under More options.
3. Scan or tick the bundles to send. Only eligible bundles not already on an open challan are listed. For Kind = Rework, only the bundles waiting for rework **at the chosen step** are listed.
4. Press **Save and issue** to save the challan and hand the bundles over in one step. It opens the issued challan, ready to **Print**. If issuing fails, nothing is saved and the form comes back with your bundles still ticked. Or press **Save** to keep a Draft, where you can change the materials going with the bundles, and issue later. Save and issue sends the materials exactly as the list fills them in. Save and issue shows only if your role may issue challans.

**Rework goes back on its own step.** A bundle sent back by QC waits at the step of the challan it came back on, and a rework challan can only be made for that step. If you pick another step the system refuses with "Bundle … is waiting for rework at …, not …". The lot's **Send back for rework** link opens the form on the right step.

The challan fills in the **rate** from the fabricator's labour rate (section 11), falling back to the step's rate. If neither exists you see "There is no labour rate for X on PROCESS. Add one under Labour rates, or set a rate on the step". It also lists the **materials** the style's list has for this step's process (10.2) for these pieces, including wastage: accessories for stitching, embroidery thread for embroidery, and so on. A bundle going back to a step it has been through adds nothing. A challan covers one lot.

If the same lot is already open with another fabricator you get a warning and must tick "Yes, issue this lot to another fabricator too".

The challan page tells you what to do next, like the lot page. At the top is a **journey strip**: Draft, Issued, Received, Checked, Billed. Each stage is shown as done, now or to come, with the pieces issued, received and accepted. Below it is one violet **Next** button:

| The challan is… | Next button | Opens |
| --- | --- | --- |
| A draft | **Issue challan to …** | The Issue challan button on the same page |
| Issued or partly received, with pieces still out | **Receive from …** | The receipt form (23.3) |
| Waiting on an over-receipt | **Approve over-receipt** | The receipt (owner only) |
| Received, with bundles not yet checked | **Check received pieces** | The receipt, for QC (23.4) |
| Checked, with a bundle QC sent back | **Send back for rework** | The rework challan form, on this lot and step |
| Checked, with payable pieces not yet on a labour bill | **Make labour bill for …** | New labour bill with the fabricator chosen (25.1) |
| Accepted pieces on a draft labour bill | **Post labour bill** | The draft bill, to check and post |
| Billed, or nothing left to do (everything rejected, or reworked on its own challan and paid) | none: "This challan is finished." | |
| Cancelled | none: "This challan was cancelled." | |

What is furthest behind comes first; anything else pending is listed as smaller links under **Also waiting**. If the next step belongs to another role, the page says **Waiting for:** and the step instead of a button. Where the lot page and the challan page both offer a step (issue, receive, approve, check, send back for rework), it is the same button opening the same screen. Labour bills are offered on the challan, the receipt and the lists, not on the lot. Once a bundle sent back is on a draft rework challan, the first challan stops asking for it; issue the draft instead. The receipt page shows the same strip and button for its challan, so after QC the next receipt or the labour bill is one click away. The lists *Sent to fabricators* and *Received from fabricators* have a **Next step** column with the same button on every row. *Sent to fabricators* has an **Out with fabricators** tab for the challans that are issued or partly received.

On the challan page:

- **Materials going with the bundles** (draft only). The table is filled in from the style's list. Change a quantity to what is really being sent, clear it to leave the material out, or add a material in the empty rows. **Save materials** keeps the draft; **Issue challan** issues with what is on the screen. A style with no list starts empty, and you can still add materials here.
- **Issue challan.** The challan is numbered, bundles move to the fabricator's location, the materials leave the godown into the lot's cost, and the step is assigned to that fabricator. (**Save and issue** on the new-challan form does this for you.)
- **Print** the challan to send with the goods. It carries a QR and lists the bundles and the materials issued.
- **Discard draft** if you made it by mistake.

Challan statuses: Draft → Issued → Partly received → Fully received → Billed. (Cancelled if a draft is discarded.)

### 23.3 Receive the goods

Lot page or challan page → Next button **Receive from …**, Home → **Receive from fabricator** and the row's **Receive from …** button, or Challan page → **Receive goods**.

| Field | Example |
| --- | --- |
| Date | 12-10-2026 |
| Receive into | Process Area. Filled in for you; it is under **More options** if you need to change it |
| Counted, per bundle | the pieces actually counted, with the tick box |
| Trims: Returned / Missing | 0 / 10 |

Press **Receive**. Scanning the bundle tags ticks the rows.

- Counted **less than** issued records a **shortage**. It is valued at lot cost and recoverable on the labour bill.
- Counted **more than** issued is an **over-receipt**. Nothing moves, and the receipt waits for the owner. The owner opens the receipt and presses **Approve over-receipt**. Until then QC is blocked.
- A bundle cannot be received twice. A bundle counted on an over-receipt that still waits for approval is not listed again and cannot be received again ("Bundle … is on a receipt waiting for the owner's approval"); approve that receipt first.
- After posting, the receipt is numbered, bundles become "Received, awaiting QC", returned trims go back to stock and missing trims become a deduction.

> A fabricator saying "done" does **not** change stock or pay. Only your receipt and QC do. (The fabricator mobile app is planned and is not available yet.)

### 23.4 Quality check (QC)

*Make → Received from fabricators* (receipts and QC) *→* open the receipt, or use the Next button **Check received pieces** on the lot, the challan or the receipt list. For every bundle fill:

| Field | Meaning |
| --- | --- |
| Accepted | Pieces that pass |
| Rejected | Pieces that fail |
| Rework (send back) | Pieces to send back to the fabricator to be redone |
| Reject reason | Required if any piece is rejected |
| Rejected go to | **Rejects stock** (kept) or **Scrapped** (written off as loss) |

Press **Save QC**. The rules:

- Accepted + Rejected + Rework must equal the pieces received.
- Accepted and rework can be mixed. The rework pieces are then **split into a bundle of their own**, numbered after the first (B002 gives B002-R1), so the accepted pieces move on without waiting. The receipt shows "as bundle B002-R1" with a link to **print its tag**; put that tag on the pieces going back. With nothing accepted, the whole bundle goes back as it is.
- QC is recorded once per bundle.

Results:

- **No rework:** the bundle becomes **Ready for next stage** and the step counts as complete for it. Move it on (23.1, or a new challan).
- **Rework:** the bundle (or the split bundle) becomes **Awaiting rework**. It cannot move until you issue a **Rework challan** for it (the **Send back for rework** link, or Send to fabricator with Kind = Rework under More options), on the same step it came back from. The form opens on the fabricator who did the step. When it comes back and passes, it moves on like any other bundle; it stays a separate bundle to the end. What the rework pays follows the rate's **Pay on** (section 11).
- **Rejected:** goes to the Rejects location (or is scrapped).
- When every bundle on the receipt has QC, the receipt is **QC done**, and checking the last line returns you to the lot. If your role cannot open lots you stay on the receipt, where the Next button names what comes next.

What is payable follows the challan's **Pay on**: the accepted pieces, or every piece received (section 11).

### 23.5 A complete example: route B, lot JGR-104 Black

| Step | What the user does | Bundle status after |
| --- | --- | --- |
| 1 Cutting | Issue fabric, record the lay, make bundles, print tags | Cut |
| 2 Embroidery (Royal Embroidery) | Send to fabricator for all bundles, issue, print. Later: Receive, then QC (say 296 accepted, 4 rejected) | Ready for next stage |
| 3 Stitching (Gurpreet Garments) | Send to fabricator, issue. Later: Receive, then QC | Ready for next stage |
| 4 Ironing (in-house) | Move bundles to "Ironing and pressing"; enter Loss on a row if a piece was damaged | At stage |
| 5 Quality check (in-house) | Move bundles to "Quality check" | At stage |
| 6 Packing (in-house) | Move bundles to "Packing" | At stage |
| 7 Finished goods | Pack into finished goods (section 24) | Packed |

---

## 24. Pack into finished goods

When bundles reach the packing step, open the lot page and press the Next button **Pack into finished goods**, which takes you to the **Pack into finished goods** box under Bundles.

1. Tick the bundles ("These bundles have reached packing").
2. Choose **Receive into** (default: the factory's Dispatch location).
3. Press **Pack**.
4. **Packing materials.** If the style's list has packing materials (10.2), a second page shows them for the pieces being packed, for example 102 polybags for 100 pieces at 2% wastage. Change, clear or add as on a move (23.1), then press **Pack**. They leave the Main Godown into the lot's cost first, so the finished pieces carry their cost. To use packing materials that are not on the list, tick **Issue packing materials that are not on the style's list** before pressing Pack.

The pieces become **finished goods stock** at that location, valued at the lot's cost per piece (fabric + accessories and packing + labour). Each bundle becomes **Packed**. The message reads "N pieces packed into finished goods."

**Boxes.** When **Pieces per box** is set (on the style, or the company's in Inventory settings), boxing and packing are one step:

- Before you press Pack, the box shows what the ticked bundles fill, per size: "M 2 boxes of 12 + a short box of 9".
- One size and colour to a box. What is left over after the full boxes goes in a **short box**.
- After packing the message adds the boxes ("33 pieces packed into finished goods: 2 boxes of 12 and 1 short box of 9"), and **Packed into boxes** on the lot page lists each packing with **Print box labels**.
- A box label shows the style, colour and size, the pieces in that box, "Box 2 of 3", "Short box" where it applies, the SKU barcode, the lot and the date.
- Stock stays in **pieces**. A box is a count and a label, so pack the bundles of a size together to get the fewest short boxes.

Rules: bundles must be in one factory and one lot, must have reached the packing step, and must have no rework pending. Locations such as transit, rejects and fabricator premises are not offered.

The lot becomes **Completed** when none of its bundles is still live; packed, written-off and scrapped bundles all count as finished. When every lot is complete the order is **Completed**.

### Tracking at any time

- **Make → Production dashboard:** Cut today, Stitched today, Packed today; work in progress by stage and by factory; pieces with fabricators; late lots (past the due date); oldest open lots.
- **Home → Items in production** lists each open lot with its **Next step**.
- The **Where is it?** box searches by order number, style number, lot number or order reference and lists each bundle with size, pieces, current stage, location and status.

---

## 25. Pay the fabricator

### 25.1 Labour bill

*Make → Labour bills → New labour bill*, or the Next button **Make labour bill for …** on a challan or receipt whose accepted pieces are not on a bill yet. The button opens this screen with the fabricator already chosen. The bill is always made in the factory chosen in the top bar; **Factory** on this screen only shows it and is not a choice. If the challan belongs to another factory (or "All factories" is active), the button takes you back to the challan with "These pieces are in …. Choose it in the top bar, then press the button again."

1. Choose the **Fabricator** (the **Factory** shown is the one active in the top bar), then **Show what is payable**.
2. The screen lists the **checked pieces not yet paid**: Challan, Lot, Bundle, Accepted, **Pieces paid**, Rate, Amount. Pieces paid is the accepted pieces, or every piece received when the rate pays on pieces received (marked "received"). It also lists the **deductions** it found: shortage of pieces (at lot cost) and missing trims (at unit cost).
3. Set the **Bill date**. To deduct TDS or add notes, open **More options** and choose a **TDS** template; left alone it is **No TDS**.
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

- Challans on a **Fixed amount per lot** rate pay in proportion to the pieces paid over pieces issued.
- **Deductions.** A ticked line is taken off this bill. An unticked line stays pending and is offered again on the next bill. A shortage on a challan paid on pieces received starts **unticked**; everything else starts ticked.
- **We bear this… → Waive for good.** The owner can waive a pending deduction with a reason. It is then never offered again, and nothing is posted: the loss stays in the lot's cost and is carried by the pieces that are left.
- Errors you may meet: the fabricator has no payable ledger; nothing is payable; deductions are more than earned.
- On the draft, check the numbers, then press **Post bill** (or **Discard draft**). While a bill is a draft, the challans on it show the Next button **Post labour bill**, which opens it.

**What posting does:** the bill is added to the lot's cost as job work; the net amount becomes owed to the fabricator (due date = bill date + the fabricator's credit days); TDS goes to TDS Payable; the challans become **Billed** once everything is received, QC'd and paid with no rework open.

To undo a posted bill, use **Cancel bill** with a reason. It reverses the entries and frees the pieces to be billed again.

### 25.2 Pay the money

Open the posted labour bill. It shows **Outstanding** and a **Pay fabricator** button. The button opens **Money paid** with the fabricator, the amount still open and the bill reference already filled in. **Nothing is posted until you press Post.**

| Field | Example |
| --- | --- |
| Paid from | HDFC Bank Current A/c 1234 (you choose; the screen cannot know) |
| Paid to | Gurpreet Garments (filled in) |
| Amount | 6,868.12 (filled in; change it for a part payment) |
| Bill | **Against bill** (filled in) |
| Reference | The labour bill number (filled in) |

Choose **Paid from**, check the figures, and **Post payment**. Afterwards the bill shows **Settled**. A part payment leaves the rest as **Outstanding**.

Pick the **factory in the top bar** that the bill belongs to before you post. Money paid posts to the factory you are working in.

The same works for suppliers: a posted supplier bill shows **Outstanding**, its Next button is **Pay** and the supplier's name, and the header has a plain **Pay supplier** button for the same step (section 19). Section 27 explains the Bill options.

---

## 26. Sell: order, pack, invoice

### 26.1 Sales settings (once)

*More → Settings → Sales settings.*

| Setting | Meaning | Suggested |
| --- | --- | --- |
| Bill total | No rounding, or round to the nearest rupee (the difference posts to Round Off) | Round to nearest rupee |
| Discount limit % | Higher discounts need the "Discount above the limit" permission | 10 |
| E-invoicing is switched on | Shows the e-invoice and e-way bill buttons | Off until a provider is chosen |
| E-way bill needed from bill value | | 50,000 |

### 26.2 Sale order

*Sell → Sale orders → New order.*

| Field | Example |
| --- | --- |
| Customer | Mehta Traders |
| Factory | LDH1 |
| Date / Due by | 08-10-2026 / 22-10-2026 |
| Type | **Ready stock** or **Made to order** |
| Notes | Under **More options** |

The **Customer** starts on "Choose…". Saving without one is refused with "Choose the customer." and the styles and pieces you typed are kept.

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

Press **Save and confirm** to take the order and confirm it in one step, or **Save draft**, review, then **Confirm order** on the order page. Confirming gives the order its number. For **Made to order** it also raises a draft production order (section 20) with the sale order number as reference and no customer name. If confirming fails, nothing is saved and the form comes back with what you typed.

The order page then shows the journey strip and its Next button (section 19): **Pack goods**, or for a made-to-order order whose pieces are not in stock yet, **Waiting for: goods from production**.

Order statuses: Draft → Confirmed → Partly dispatched → Fully invoiced. Also Closed and Cancelled.

- Only a Draft can be edited.
- **Close the balance** short-closes an order, with a reason, when a customer will not take the rest.
- **Cancel order** needs a reason once confirmed, and is blocked while a live packing list or bill exists.
- **Credit limit:** it is stored on the customer but is **not enforced**; nothing is blocked. To see what a customer already owes, choose them on a **Sales voucher** or **Journal voucher** (section 28): the outstanding amount appears beside the choice. The receivables ageing (section 29) shows it for every customer.
- Ready-stock orders reserve nothing at order time. Stock is checked when you finish the packing list.

*Sell → Sale orders → Order book* shows open orders with their pending balance, for the factory chosen in the top bar (every factory of yours when "All factories" is chosen). "Orders waiting to be packed" on *Packing and dispatch* follows the same rule.

### 26.3 Packing and dispatch

The order's Next button **Pack goods** (also a plain button in the order's header), or *Sell → Packing and dispatch*, then **Pack** beside the order.

| Field | Example |
| --- | --- |
| Pack from | Dispatch (LDH1) |
| Date | 15-10-2026 |
| Transporter | Jai Mata Roadlines |
| LR / docket no., LR date | 44821, 15-10-2026 |
| Vehicle no. | PB10AB1234 |

Pack from and Date are asked every time. Transporter, LR / docket no., LR date, Vehicle no. and Notes are under **Transport details**: open it when the goods are booked with a transporter. It opens by itself when any of them is filled in.

In the **Pieces in each carton** grid, rows are order lines with "Left to pack" and columns are cartons (two to start; **Add a carton** up to 30). When pieces per box is set, **Fill cartons from pieces per box** fills the grid for what is left to pack, one size to a carton, up to 30 cartons; change any figure before saving. Fill what goes in each carton. No carton may be empty, and you cannot pack more than is left on the order.

**Save draft** opens the packing list. There, **Finish packing and make bill** finishes the list and drafts the bill for the packed pieces in one step, then opens the bill (26.4). **Finish packing** only finishes the list; its Next button is then **Make bill**. Finishing checks stock at that location (less pieces on other packed lists that are not billed yet) and numbers the list. If the pieces are not in stock, or the bill cannot be drafted, nothing changes: the list stays a draft and the message says why. Status: Draft → Packed → Invoiced.

Then **Print list** and **Carton labels**. Carton codes look like `C000123-01`; scanning one at billing adds the whole carton. A finished list cannot be reopened: cancel it (with a reason) and pack again. A list that has a bill, draft or posted, cannot be cancelled: the page says "Discard or cancel its bill before cancelling this packing list." Discard the draft bill (or cancel the posted one) first. **Discard** cancels a draft list.

A role that packs but does not bill sees only **Finish packing**; the page then says **Waiting for: Make bill**.

### 26.4 Invoice

On screen a sale invoice is called a **bill**; the printed document is still the Tax Invoice.

**From a packing list:** press **Finish packing and make bill** on a draft list, or **Make bill** on a Packed list. A draft bill is made for the packed pieces at the order's rates and discounts, with GST as suggested (below), and the bill opens. Transporter, LR and vehicle carry over. Check it, change or waive the GST if needed, then **Post bill**.

**Counter sale by scanning:** *Sell → Quick billing (barcode).*

1. Choose the **Customer** (it starts on "Choose…"; a bill is refused with "Choose the customer." until one is picked), **Goods leave from** (location) and **Date**. The **Factory** shown is the one in the top bar.
2. Scan each item's barcode in the scan box and press Enter. One scan adds one piece; a carton code adds the whole carton. "Unknown barcode" means the code is not a SKU or carton.
3. The rate and discount fill from the pricing lookup. Check Rate, Disc % and Amount on every row; the footer shows Pieces and Before GST.
4. Choose the GST option (below). **Notes** are under **More options**.
5. **Post bill**, or **Save as draft** to check first. Pressing Enter in a field saves a draft.

**GST on the bill** (only if GST is switched on for the factory and date; otherwise "no tax is charged"):

| Option | When to use |
| --- | --- |
| **From the HSN slab and place of supply (suggested)** | Normal. Each line's per-piece value picks the slab from the style's HSN (for example up to ₹2,500 → 5%, above → 18%). Customer's state against factory state decides CGST + SGST or IGST |
| **One GST template for all items** | Special case; needs a reason if it differs from the suggestion |
| **No GST on this bill** | Needs a reason; the suggestion is kept in the bill's log |

If a style has no HSN code, or its HSN has no slab for the value and date, GST cannot be suggested. From a packing list (**Make bill** or **Finish packing and make bill**) the message names the style and where to put it right, for example "JGR-104 has no HSN code. Set it in Masters → Styles, then make the bill again." or "JGR-104: HSN 6112 has no GST slab for this value and date. Add it in Masters → Setup → HSN and GST slabs, then make the bill again." Nothing is saved, and the bill cannot be drafted until the master is fixed (section 4). In Quick billing the message is "The style has no HSN code; set it, or choose a GST template or no GST for this invoice.": there you can also pick one of the other GST options. On a draft, **Change the GST on this bill** → **Update GST** re-works the tax.

Amount per line = quantity × rate × (100 − disc%) ÷ 100. The due date = bill date + the customer's credit days (Mehta Traders: 45).

**Post bill** does all of this at once, or none of it:

- Numbers the bill.
- Takes the pieces out of stock at the chosen location.
- Debits the customer as a **new bill** in the books (reference = the bill number, due date as above).
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
| **Bill total** | **₹45,070.00** |

After posting, the bill's Next button is **Receive money from** and the customer's name (section 27).

**Bill list and print.** *Sell → Bills* has tabs All, Draft, Posted, Cancelled and a **Next step** column. Open a bill → **Print** gives the tax invoice with QR, carton count and tax breakup. The bill page names its order, packing list and accounting voucher, as links when your role may open them.

**Discard draft** removes a draft. A posted bill is never edited.

**Cancel bill** (Accountant; reason required) reverses the stock and the entries, rolls the order back and returns the packing list to Packed. It is blocked if a return has been posted against it or an e-invoice number was generated.

**E-invoice and e-way bill.** If switched on in Sales settings and the buyer has a GSTIN, a posted taxed bill shows **Send e-invoice and e-way bill**. This version uses a **stand-in that makes test numbers only**; it does not contact the government portal. Do not use those numbers for real consignments until a real provider is connected.

### 26.5 Returns: credit note

On screen a credit note is called a **return from customer**. Open the posted bill → **Return from customer**. *Sell → Returns from customer* lists them.

| Field | Example |
| --- | --- |
| Date | Not before the bill date |
| Goods come back to | Main Godown |
| Reason | Required. "6 pieces wrong colour" |
| Returning | Quantity per line, up to "Can be returned" |

**Save draft** → **Post return** (the return's Next button; the bill and the order show it as their Next button too). The pieces come back into stock at their original cost, sales returns and GST are reversed pro rata, and the customer is credited: first against that bill's open amount, any excess **on account**. So after a return the bill's **Outstanding** and its Receive money button show the bill less the return. If the bill was already paid, the return page and the bill page say how much is held on the customer's account. **Cancel return** needs a reason. If the bill itself is cancelled while a return is still a draft, the draft can no longer be posted; the page says so and you discard it.

---

## 27. Receive the customer's money

**The quick way.** Open the posted bill (or its order or packing list). The Next button is **Receive money from** and the customer's name; the bill's header shows **Outstanding** and a plain **Receive money** button that does the same. Either opens **Money received** with the customer, the amount still to receive and the bill reference already filled in. Choose **Received in** (cash or bank), check the amount, add notes if you want (under **More options**) and press **Post receipt**. The bill then shows **Settled** and "This bill is settled." If the customer pays only part, enter that amount; the rest stays Outstanding and stays on the button. A role that may not enter vouchers sees **Waiting for: Receive money from …** instead.

**Any time.** *Money → Money received.* Needs the Accountant role and a **single factory chosen in the top bar** (the form does not ask for it). Post it in the factory the bill belongs to.

| Field | Example |
| --- | --- |
| Date | 28-11-2026 |
| Received in | HDFC Bank Current A/c 1234 (only cash and bank ledgers are offered) |
| Received from | Mehta Traders. The amount outstanding appears under the name |
| Amount | 45,070.00 |
| Bill | **Against bill** |
| Reference | The invoice number (pick from the list of open bills; the outstanding amount fills in) |
| Notes (under **More options**) | RTGS UTR 1234567890 |

Press **Post receipt**. The receipt is numbered and the customer's bill is settled.

**Bill**, **Reference** and **Due** take no space on Money received and Money paid until a row uses a ledger that keeps bills (a customer, supplier or fabricator). They appear as soon as you choose one.

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

- Money received: ₹44,500 against the invoice.
- Journal voucher: debit "Discount Allowed", or a "TDS Receivable" ledger you create (section 6; none is seeded), ₹570; credit the customer ₹570 against the same bill.

Your accountant must confirm which ledger fits each case.

---

## 28. Other money vouchers

*Money → Money paid* and *Money → Money received* are the everyday ones; Contra and Journal are under *More → Accountant*.

| Voucher | Use | Example |
| --- | --- | --- |
| **Payment** | Money out of cash or bank to a supplier, fabricator or expense | Pay Sri Ram Textiles ₹2,10,000 against bill `PI/4471` |
| **Receipt** | Money into cash or bank | Section 27 |
| **Contra** | Cash ↔ bank | Deposit ₹50,000 cash into HDFC |
| **Journal** | Any balanced entry between ledgers | Adjustments, TDS and discounts |

*More → Accountant* also has manual **Sales**, **Purchase**, **Debit note** and **Credit note** vouchers. They are value-only: **no stock moves**. Prefer the document screens (bills, goods received, supplier bills) whenever goods are involved.

**See what a party owes as you enter.** When you choose a customer or supplier on a **Sales voucher** (and the other party vouchers), or choose a ledger on a **Journal**, **Payment** or **Receipt**, a note appears beneath it, for example *Outstanding ₹1,20,000.00 Dr (owes you) in 2 open bills · advance ₹5,000.00 Cr*. Dr means they owe you, Cr means you owe them. For an ordinary ledger such as a bank account it shows the balance. This is **information only**; it never stops you from posting.

A supplier bill posts what you owe the supplier (reference = their bill number, with due date). Open the posted supplier bill and press its Next button (**Pay** and the supplier's name) or **Pay supplier** in the header, or use Money paid with **Against bill**.

---

## 29. See what is owed and check the books

| Question | Screen |
| --- | --- |
| Who owes me, and how overdue? | Reports → **Who owes me** (receivables ageing). Buckets: Not due, 1–30, 31–60, 61–90, 91–180, 181–365, Over a year; plus Outstanding and Advance / on account. Each open bill is listed with its age. Click a party for its statement |
| Whom do I owe? | Reports → **Whom I owe** (payables ageing) |
| All dealings with one party | Money → **Party accounts** (ledger statement): choose the ledger and date range; opening balance, each entry, running balance; Excel export |
| What happened today? | More → Accountant → **Day book** (filter by factory, dates, voucher type) |
| Is everything balanced? | More → Accountant → **Trial balance** (debits must equal credits) |
| Profit and position | Reports → **Profit and loss**, **Balance sheet** |
| Find a voucher | Money → **All entries** (all vouchers) (filter by factory, type, status, number) |
| Sales summary | Reports → **Sales** |
| Finished goods stock | Reports → **Finished stock** |
| GST filing data | Reports → GST → **GSTR-1 data**, **GSTR-3B summary**, **Tax register** |
| Fabricators | Reports → **Fabricator reports**, **Daily summary** |

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
| "no material list on the style" after releasing | The style has no BOM. The order is released anyway | Nothing is filled in for it: add materials by hand on the challan, the move or at packing, or add the BOM (10.2) for the next order |
| "is fabric and is not listed here" | You tried to put fabric on a style's BOM | Leave fabric off; enter the pieces you expect when you issue it to cutting (22.1) |
| "Not on this route" on the lot page | The style's list uses a material in a process the lot's route does not have | Add the material by hand where it is used, or correct "Used in" on the list (10.2) |
| "no default route" | The style has no default route | Set it on the style |
| "is done by a fabricator: issue a job work challan instead" | You tried to move into a fabricator step | Use Send to fabricator |
| "Moving back to an earlier stage needs a reason" | The target is at or before the bundle's completed step | Type the reason, or pick the right step |
| "pieces waiting for rework; finish that first" | QC sent the bundle back | Issue a Rework challan |
| "is waiting for rework at …, not …" | The rework challan is for a different step than the one the bundle came back from | Make the rework challan for the step named first |
| "There is no labour rate for X…" | No rate for that fabricator and process | Add it in Labour rates, dated on or before the challan date |
| Receipt shows "Over-receipt, needs approval" | Counted more than issued | Owner approves, or recount |
| Nothing payable on a labour bill | No checked, unpaid pieces | Complete QC first |
| "… allows no loss" | The bundle is at a step marked no loss allowed | Move it with no count. If pieces really are lost, untick **No loss allowed** on the process |
| "the pieces lost cannot be more than the N cut" | Lost in cutting is above the pieces cut of that size | Correct the figure |
| "These bundles first went out on different pay terms" | One rework challan mixes bundles paid on accepted and on received pieces | Make a separate rework challan for each |
| "Pick a single factory in the top bar before entering a voucher" | Voucher entry needs one factory | Switch factory in the top bar |
| "No rate found; enter one" | No customer rate, price list or last invoice rate | Add a price list rate (section 12) or type the rate |
| "only X available at <location>" when finishing packing | Not enough stock at that location | Move or pack stock there first |
| A wrong posted document | Posted documents are never edited | Cancel with a reason, then enter a correct one |

---

## 31. What is not available yet

- **Wages of in-house workers:** in-house piece rates go into the lot's cost only. No worker is recorded and no wage is owed in the books; pay wages with a Payment voucher.
- **Boxed stock:** boxes are counted and labelled at packing, but stock is kept in pieces.
- **Fabricator mobile app** ("Done" marking, earnings): planned; the fabricator role has no screens yet. Your staff do receipts and QC.
- **E-invoice and e-way bill:** only a stand-in that makes test numbers.
- **Credit limit** on customers: stored but deliberately **not enforced**. The outstanding amount is shown when you choose a party on a Sales voucher or Journal.
- **Discount and TDS on receipts:** use a Journal voucher (section 27.1).
- **Stock reservation** for ready-stock orders: none at order time; stock is checked at packing.
