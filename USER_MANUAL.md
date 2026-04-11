# Jewel India ERP - User Manual

**Version:** 1.0
**Last Updated:** April 2026
**Audience:** First-time clients, store managers, accountants, and administrators

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Requirements](#2-system-requirements)
3. [Installation & Setup Guide](#3-installation--setup-guide)
4. [First-Time Configuration (ERP Setup Wizard)](#4-first-time-configuration-erp-setup-wizard)
5. [Master Data Setup](#5-master-data-setup)
6. [CRM & Ledger Management](#6-crm--ledger-management)
7. [Sales Module](#7-sales-module)
8. [Purchase Module](#8-purchase-module)
9. [Manufacturing Module](#9-manufacturing-module)
10. [Inventory & Barcode Management](#10-inventory--barcode-management)
11. [Financial Accounting](#11-financial-accounting)
12. [GST & Tax Compliance](#12-gst--tax-compliance)
13. [Fixed Assets & Depreciation](#13-fixed-assets--depreciation)
14. [Gold Scheme Management](#14-gold-scheme-management)
15. [HR & Payroll](#15-hr--payroll)
16. [Reports](#16-reports)
17. [Settings & Administration](#17-settings--administration)
18. [Customer Portal](#18-customer-portal)
19. [Best Practices](#19-best-practices)
20. [Troubleshooting](#20-troubleshooting)
21. [Glossary](#21-glossary)
22. [Migrating from an Existing ERP](#22-migrating-from-an-existing-erp)
23. [AI Assistant & MCP Server Setup](#23-ai-assistant--mcp-server-setup)

---

## 1. Introduction

### What is Jewel India ERP?

Jewel India ERP is a comprehensive enterprise resource planning system designed specifically for the Indian jewellery retail industry. It covers the entire business lifecycle - from purchasing raw materials and manufacturing jewellery, to selling finished products, managing inventory with barcode tracking, handling complex GST-compliant accounting, and running gold savings schemes for customers.

### Key Features

| Module | Capabilities |
|--------|-------------|
| **Sales** | Estimates, customer orders, sales invoices, returns, approvals, e-way bills |
| **Purchases** | Purchase orders, purchase invoices, returns, vendor management |
| **Manufacturing** | Karigar (artisan) job work issue/receive, stone handling, hallmarking, refinery, melting |
| **Inventory** | Barcode-based tracking, stock transfer between locations, raw material management, stock journals |
| **Accounting** | Double-entry bookkeeping, receipt/payment/journal/contra vouchers, bank reconciliation |
| **GST Compliance** | Auto-computed CGST/SGST/IGST, GSTR-1, GSTR-3B, GSTR-2B reconciliation, TDS/TCS registers |
| **Gold Schemes** | Monthly installment, gold accumulation, lump sum schemes with tiered benefits |
| **HR & Payroll** | Employee management, salary structure, slip generation, PF/ESI/PT compliance |
| **Fixed Assets** | Asset master, WDV/SLM depreciation, IT Act block rates |
| **CRM** | Customer/vendor ledger, purchase history, birthday/anniversary tracking, WhatsApp automation |
| **Multi-Location** | Multi-company, multi-branch, multi-retail support with data isolation |
| **Licensing** | Module-level licensing per company subscription |

### Architecture Overview

- **Backend:** Django + Django REST Framework (Python)
- **Frontend:** React with ShadCN UI components (Tailwind CSS)
- **Database:** SQLite (development) / PostgreSQL (production recommended)
- **Authentication:** Token-based (per user)
- **Multi-Tenancy:** Retail-level data isolation via `X-RETAIL-ID` header

---

## 2. System Requirements

### Server Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10 / Ubuntu 20.04 | Ubuntu 22.04 LTS |
| **Python** | 3.10+ | 3.12 |
| **Node.js** | 18.x | 20.x LTS |
| **RAM** | 4 GB | 8 GB+ |
| **Disk** | 10 GB | 50 GB+ (for media/attachments) |
| **Database** | SQLite (dev) | PostgreSQL 15+ (production) |

### Client Requirements

- Modern web browser: Chrome 90+, Firefox 90+, Edge 90+, Safari 15+
- Minimum screen resolution: 1280 x 720
- Stable internet connection (for multi-location setups)

---

## 3. Installation & Setup Guide

### Step 1: Clone the Repository

```bash
git clone <repository-url> "Jewel India ERP"
cd "Jewel India ERP"
```

### Step 2: Backend Setup

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Environment Configuration

Create a `.env` file in the `backend/` directory:

```env
# Required
SECRET_KEY=your-secret-key-here-generate-a-strong-one
DEBUG=True

# Hosts (comma-separated)
ALLOWED_HOSTS=localhost,127.0.0.1

# CORS (comma-separated origins for frontend)
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Optional: AI Layer
OPENAI_API_KEY=sk-your-openai-key
AI_NL_MODEL=gpt-4o-mini
AI_VISION_MODEL=gpt-4o

# Optional: MySQL sync for legacy data import
# MYSQL_SYNC_HOST=localhost
# MYSQL_SYNC_PORT=3306
# MYSQL_SYNC_DB=legacy_db
# MYSQL_SYNC_USER=root
# MYSQL_SYNC_PASSWORD=password
```

> **Security Note:** Never commit `.env` files to version control. Keep your SECRET_KEY private.

### Step 4: Database Setup & Migrations

```bash
# Run all migrations
python manage.py migrate

# Set up the default chart of accounts
python manage.py setup_account_groups

# Create a superuser (admin account)
python manage.py createsuperuser
```

You will be prompted for:
- Username (e.g., `admin`)
- Email address
- Password (must be strong)

### Step 5: Seed the App Registry (Licensing)

The app registry is auto-seeded on first API access. Alternatively:

```bash
python manage.py seed_app_registry
```

### Step 6: Start the Backend Server

```bash
python manage.py runserver
```

The backend API will be available at `http://127.0.0.1:8000/`.

### Step 7: Frontend Setup

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:5173/`.

### Step 8: Initial Login

1. Open `http://localhost:5173/config` in your browser
2. Enter the backend URL: `http://127.0.0.1:8000/`
3. Click **Save & Continue**
4. You will be redirected to the login page
5. Enter your superuser credentials
6. The ERP Setup Wizard will launch automatically on first login

---

## 4. First-Time Configuration (ERP Setup Wizard)

The Setup Wizard guides you through mandatory configuration. **You must complete all steps before using the ERP.**

### Step 1: Company Setup

Navigate to **Settings > ERP Setup Wizard** or it auto-launches on first login.

| Field | Description | Example |
|-------|-------------|---------|
| Company Name | Legal name as per PAN | "Jewel India Pvt Ltd" |
| PAN | Permanent Account Number | "AABCJ1234K" |
| TAN | Tax Deduction Account Number | "DELJ12345K" |
| CIN | Corporate Identity Number (if applicable) | "U74999DL2020PTC123456" |
| GSTIN | Primary GST number | "07AABCJ1234K1Z5" |
| Address | Registered office address | Full address |
| Cash Receipt Limit | Sec 269ST limit (default: 1,99,999) | 199999 |
| Cash Payment Limit | Sec 40A(3) limit (default: 10,000) | 10000 |

### Step 2: Branch Setup

Branches represent state-level groupings.

| Field | Description | Example |
|-------|-------------|---------|
| Branch Name | Descriptive name | "Delhi Branch" |
| State | Indian state | "Delhi" |
| Company | Parent company | "Jewel India Pvt Ltd" |

### Step 3: Retail Location Setup

Retail locations are individual stores or showrooms. All transactions are isolated per retail.

| Field | Description | Example |
|-------|-------------|---------|
| Retail Name | Store name | "Jewel India - Karol Bagh" |
| Retail Code | Unique code (used in X-RETAIL-ID) | "R001" |
| Branch | Parent branch | "Delhi Branch" |
| Bill Series Prefix | Prefix for bill numbering | "R001" |
| Email | Store email | "karolbagh@jewelindia.com" |
| Cash Ledger | Default cash account | Auto-created |

### Step 4: GSTIN Master

When you save a GSTIN, the system automatically creates **6 GST ledger accounts**:
- Input CGST, Input SGST, Input IGST
- Output CGST, Output SGST, Output IGST

Plus **6 RCM (Reverse Charge) ledger accounts** if applicable.

### Step 5: Fiscal Year

| Field | Description | Example |
|-------|-------------|---------|
| FY Code | Short identifier | "26-27" |
| Start Date | Always April 1 in India | "2026-04-01" |
| End Date | Always March 31 | "2027-03-31" |
| Retail | Which location this FY belongs to | "R001" |

> **Important:** Activate the fiscal year on the retail master after creating it.

### Step 6: User Management

Create user accounts for your staff:

1. Go to **Settings > User Management**
2. Click **Add User**
3. Assign a role (Admin, Manager, Operator, etc.)
4. Assign retail location access (users can access multiple locations)

---

## 5. Master Data Setup

Master data must be configured before creating transactions. Navigate to the **Setup** menu.

### 5.1 Chart of Accounts

The chart of accounts is pre-seeded with standard Indian accounting groups:

| Code | Group Name |
|------|-----------|
| **A** | Assets |
| **FA** | Fixed Assets |
| **CA** | Current Assets |
| **L** | Liabilities |
| **CL** | Current Liabilities |
| **I** | Income |
| **E** | Expenses |
| **DI** | Direct Income |
| **II** | Indirect Income |
| **DE** | Direct Expenses |
| **IE** | Indirect Expenses |

Navigate to **Setup > Chart of Accounts** to view or add custom account groups.

### 5.2 HSN (Harmonized System Nomenclature)

HSN codes are mandatory for GST compliance.

| Field | Description | Example |
|-------|-------------|---------|
| HSN Code | Standard HSN/SAC code | "7113" |
| Description | Item description | "Gold Jewellery" |
| CGST % | Central GST rate | 1.50 |
| SGST % | State GST rate | 1.50 |
| IGST % | Interstate GST rate | 3.00 |

Common jewellery HSN codes:
- **7113** - Articles of jewellery (Gold, Silver, Platinum)
- **7108** - Gold (unwrought, semi-manufactured)
- **7102** - Diamonds (unworked or simply sawn)
- **7103** - Precious stones
- **7117** - Imitation jewellery

### 5.3 Items

| Field | Description | Example |
|-------|-------------|---------|
| Short Code | Unique identifier | "GOLD22K" |
| Item Name | Display name | "Gold 22K" |
| Item Type | Metal / Raw / Stone / Coin / Other | "Metal" |
| UOM | Unit of Measure (Gm/Pcs/Ct) | "Gm" |
| HSN | Linked HSN code | "7113" |
| Purchase Ledger | Default ledger for purchases | "Purchase - Gold" |
| Sale Ledger | Default ledger for sales | "Sales - Gold" |

### 5.4 Purity Master

Define gold/silver purity levels:

| Purity Name | Karat | Fine % |
|-------------|-------|--------|
| 24K | 24 | 99.9% |
| 22K | 22 | 91.6% |
| 18K | 18 | 75.0% |
| 14K | 14 | 58.5% |

### 5.5 Packets (Stone/Diamond)

Packets define stone specifications for pricing:

| Field | Description | Example |
|-------|-------------|---------|
| Packet Group | Category | "Natural Diamonds" |
| Stone Item | Linked item | "Diamond - Natural" |
| Shape | Cut shape | "Round Brilliant" |
| Color | Stone color | "D" |
| Clarity | Clarity grade | "VVS1" |
| Sieve | Sieve size | "0.90-1.00" |
| Retail Rate | Per-carat rate for retail | 85000 |
| Wholesale Rate | Per-carat rate for wholesale | 72000 |
| Solitaire | Is this a solitaire? | Yes/No |

### 5.6 TDS & TCS Sections

Configure Tax Deducted/Collected at Source sections:

**Common TDS Sections:**
- **194A** - Interest (10%)
- **194C** - Contractor payment (1-2%)
- **194H** - Commission/brokerage (5%)
- **194Q** - Purchase of goods (0.1%)

**Common TCS Sections:**
- **206C(1H)** - Sale of goods above threshold (0.1%)

### 5.7 Sales Person Master

| Field | Description | Example |
|-------|-------------|---------|
| Name | Salesperson name | "Rahul Sharma" |
| Ledger | Linked commission ledger | "Commission - Rahul" |
| Commission Rate | Percentage | 2.5 |
| Commission On | Base for calculation | "Net Amount" |
| Deduct Discount | Deduct customer discount? | Yes |
| Apply on B2B | Apply to wholesale? | No |

---

## 6. CRM & Ledger Management

### 6.1 Understanding Ledgers

In Jewel India ERP, every entity (customer, vendor, bank, expense account) is a **Ledger**. Ledgers can have multiple roles:

| Role | Code | Description |
|------|------|-------------|
| Customer | CO | Retail/wholesale buyers |
| Vendor | VD | Suppliers of finished goods |
| Dealer | DL | B2B wholesale partners |
| Karigar | KR | Artisans / manufacturers |
| Bank | BA | Bank accounts |
| Cash | CA | Cash accounts |
| Sundry Creditors | SC | Amounts payable |
| Sundry Debtors | SD | Amounts receivable |
| Refinery | REF | Refinery houses |
| Melting House | MLT | Melting service providers |
| Hallmark | HM | Hallmarking centres |
| Income | INC | Income accounts |
| Expense | EXP | Expense accounts |

### 6.2 Creating a Ledger

1. Navigate to **CRM > Ledger**
2. Click **New Ledger**
3. Fill in the required fields:
   - **Account Name**: Display name (e.g., "Ravi Jewellers")
   - **Account Group**: Classification (e.g., Sundry Debtors)
   - **Roles**: Assign one or more roles (Customer, Vendor, etc.)
   - **GSTIN**: Customer's/vendor's GST number (for GST invoicing)
   - **State**: State of the party (for IGST vs CGST/SGST determination)
   - **Contact details**: Mobile, email, address
4. **Documents**: Upload PAN card, Aadhar, GST certificate, etc.

### 6.3 Customer History

Navigate to **CRM > Customer History** to view:
- All past purchases by a customer
- Payment history and outstanding dues
- Gold scheme enrollments
- Customer order history

---

## 7. Sales Module

### 7.1 Sales Workflow

```
Estimate (optional)
    |
    v
Customer Order (with advance receipt)
    |
    v
Sales Approval (optional, for high-value sales)
    |
    v
Sales Voucher (Invoice / Bill)
    |
    v
Sales Return (if needed)
```

### 7.2 Creating an Estimate

1. Navigate to **Sales > Estimate**
2. Select customer and add items
3. System auto-calculates gold value, making charges, stone value, GST
4. Save or print the estimate
5. Estimate can be converted to a Customer Order

### 7.3 Customer Orders

Customer orders represent advance bookings, often with a fixed gold rate option.

1. Navigate to **Sales > Customer Order**
2. Click **New Order**
3. Select customer, add items with specifications:
   - Pieces, gross weight, purity
   - Making charges, other charges
4. **Fixed Gold Rate**: Lock the gold rate at the time of ordering
5. **Advance Receipt**: Record advance payment (creates an RCPT voucher automatically)

### 7.4 Sales Invoice (Sales Voucher)

1. Navigate to **Sales > Sales Voucher**
2. Click **New Sale**
3. **Scan barcodes** or manually add items
4. System auto-computes:
   - Gold value (weight x rate x purity)
   - Making charges
   - Stone value
   - GST (CGST+SGST for intra-state, IGST for inter-state)
   - Round-off
5. **Payment Methods**:
   - Cash (limited to Sec 269ST ceiling per FY per customer)
   - Bank transfer / UPI / Card
   - Old Gold adjustment (auto-creates purchase voucher)
   - Advance deduction (from customer order)
6. **Save & Print** the invoice

### 7.5 Sales Return

1. Navigate to **Sales > Sales Return**
2. Select the original sales voucher
3. Choose items being returned
4. System auto-reverses:
   - Inventory (barcodes return to stock)
   - Accounting entry (credit note)
   - Salesperson commission (reversal created)

### 7.6 E-Way Bills

For inter-state sales above the threshold, e-way bills are required.

1. Navigate to **Sales > E-Way Bills**
2. Select the sales voucher
3. Fill in transport details
4. Generate or cancel e-way bills

---

## 8. Purchase Module

### 8.1 Purchase Workflow

```
Purchase Order (to Karigar / Vendor)
    |
    v
Purchase Voucher (Invoice from vendor)
    |
    v
Purchase Return (if defective)
```

### 8.2 Purchase Order

1. Navigate to **Purchases > Purchase Order**
2. Select the order type:
   - **Customer Order**: Linked to a specific customer order
   - **Stock**: General stock purchase
   - **Repair**: Repair job
3. Add items with specifications
4. Save and send to karigar/vendor

### 8.3 Purchase Voucher (Invoice)

1. Navigate to **Purchases > Purchase Voucher**
2. Click **New Purchase**
3. Select vendor/karigar ledger
4. Add items received:
   - Scan barcodes or enter manually
   - Weight, purity, rate, making charges
5. **TDS**: System auto-calculates TDS if applicable
6. **RCM**: For purchases from unregistered dealers, Reverse Charge Mechanism applies
7. System auto-creates:
   - Accounting entry (Dr Purchase A/c, Cr Vendor A/c)
   - Inventory entry (barcodes move to stock)
   - Raw material transaction (if raw materials)

### 8.4 Purchase Return

1. Navigate to **Purchases > Purchase Return**
2. Select original purchase voucher
3. Choose items being returned
4. System reverses inventory and accounting entries

### 8.5 Customer Purchase (Old Gold)

When customers bring old gold for exchange:

1. Navigate to **Purchases > Customer Purchase**
2. Enter gold details (weight, purity, rate)
3. Amount is adjusted against the sales bill

---

## 9. Manufacturing Module

### 9.1 Manufacturing Workflow

The manufacturing module tracks the complete lifecycle of jewellery creation:

```
Gold Issue to Karigar
    |
    v
Stone Issue to Karigar
    |
    v
Karigar receives and manufactures
    |
    v
Job Work Receive (finished item)
    |
    v
Stone Return (unused stones)
    |
    v
Hallmark Issue → Hallmark Receive
    |
    v
Ready for Sale (barcode generated)
```

### 9.2 Issue Operations

#### Job Work Issue
Issue raw gold and components to a karigar for manufacturing.

1. Navigate to **Manufacturing > Issue > Job Work**
2. Select karigar (artisan)
3. Add items to issue:
   - Gold (item, weight, purity)
   - Customer order reference (if applicable)
   - Design/sketch attachment
4. Save to create the issue slip

#### Gold Issue
Dedicated gold issuance to karigars (separate from job work items).

1. Navigate to **Manufacturing > Issue > Gold Issue**
2. Select karigar, item, weight, purity
3. Save the issuance

#### Stone Issue
Issue diamonds/precious stones to karigars for setting.

1. Navigate to **Manufacturing > Issue > Stone Issue**
2. Select karigar and stone packets
3. Specify pieces, carats
4. Save the stone issue

#### Other Issues
- **Hallmark Issue**: Send items for BIS hallmarking
- **Refinery Issue**: Send scrap/old gold to refinery
- **Melting Issue**: Send items for melting
- **Assay Issue**: Send for purity testing

### 9.3 Receive Operations

#### Job Work Receive
Receive finished items from karigars.

1. Navigate to **Manufacturing > Receive > Job Work Receive**
2. Select karigar and the original issue slip
3. Enter received item details:
   - Gross weight, net weight
   - Stone details
   - Loss (gold loss during manufacturing)
   - Making charges
4. System auto-generates:
   - **Barcode** for the finished item
   - **Inventory entry** (item enters stock)
   - **Raw material deduction** (gold consumed)

#### Stone Return
Receive unused stones back from karigar.

#### Hallmark Receive
Record hallmarked items received back, including HUID numbers.

### 9.4 Repair Jobs

Track customer repair requests:

1. Navigate to **Manufacturing > Repair > Repair Job Cards**
2. Create a repair job with customer details
3. Track issue and receive of the repair item
4. Record charges and completion

---

## 10. Inventory & Barcode Management

### 10.1 Barcode System

Every finished jewellery piece in Jewel India ERP has a unique **13-digit barcode** with an auto-generated QR code. Barcodes are the primary unit of inventory tracking.

**Barcode contains:**
- Item type (Gold, Diamond, Silver, etc.)
- Gross weight, net weight
- Purity (22K, 18K, etc.)
- Making value, other charges
- Stone details (packets, carats)
- Total value
- Karigar code, design code
- Stock status

### 10.2 Barcode Operations

#### Viewing Inventory
Navigate to **Inventory > Barcode Management > List** to see all barcodes in stock.

#### Barcode Split
Split one barcode into two (e.g., detaching a pendant from a set):

1. Navigate to **Inventory > Barcode Management > Split**
2. Select the barcode to split
3. The new barcode will be `<original>A`
4. Adjust weights and values for each piece

#### Barcode Merge
Combine two barcodes into one (e.g., assembling a set):

1. Navigate to **Inventory > Barcode Management > Merge**
2. Select barcodes to merge
3. A new barcode is generated with combined details

#### Barcode History
View the complete transaction trail of any barcode:

1. Navigate to **Inventory > Barcode History**
2. Search by barcode number
3. See all movements: creation, sale, return, transfer, etc.

### 10.3 Stock Transfer (Inter-Location)

Transfer inventory between retail locations:

1. Navigate to **Inventory > Stock Transfer**
2. Click **New Transfer**
3. Select destination retail location
4. Add barcodes to transfer
5. **Send**: Dispatches items (barcodes enter "in transit" state)
6. **Receive** (at destination): Accepts items into destination stock

### 10.4 Stock Journal

Manual stock adjustments for discrepancies:

1. Navigate to **Inventory > Stock Journal**
2. Select **Issue** (reduce stock) or **Receive** (add stock)
3. Add items with quantities
4. Provide remarks (reason for adjustment)

### 10.5 Design Management

Track jewellery designs for manufacturing:

1. Navigate to **Inventory > Design**
2. Create designs with specifications:
   - Design number, item type
   - Weight, making charges, loss rate
   - Stone composition
3. Attach documents: sketches, CAD files, photos

### 10.6 Raw Material Inventory

Track raw materials (unfinished gold, loose stones):

1. View balances at **Inventory > Reports > Raw Material Balance**
2. View transaction ledger at **Inventory > Reports > Raw Material Ledger**
3. Balances update automatically from purchases, manufacturing, and sales

---

## 11. Financial Accounting

### 11.1 Double-Entry Bookkeeping

Jewel India ERP follows strict double-entry accounting:
- Every transaction has equal debits and credits
- The system validates balance before saving any voucher
- All amounts use precise decimal arithmetic (no floating-point rounding)

### 11.2 Voucher Types

| Type | Code | Usage |
|------|------|-------|
| Journal | JRNL | General adjustments, closing entries |
| Payment | PMNT | Payments to vendors/expenses |
| Receipt | RCPT | Receipts from customers |
| Receipt (Sale) | RCPT-SALE | Auto-generated from sales invoices |
| Contra | CONTRA | Cash ↔ Bank transfers |
| Sale | SALE | Auto-generated from sales vouchers |
| Purchase | PURC-SC/CO | Auto-generated from purchase vouchers |
| Sale Return | SALE-RET | Auto-generated from sales returns |
| Purchase Return | PURC-RET | Auto-generated from purchase returns |
| Credit Note | CN | Customer credit adjustments |
| Debit Note | DN | Vendor debit adjustments |
| Scheme | SCHM | Auto-generated from gold scheme payments |
| Salary | SLRY | Auto-generated from salary processing |
| Depreciation | DEPR | Auto-generated from fixed asset depreciation |

### 11.3 Creating Vouchers

#### New Voucher Entry

1. Navigate to **Financial Accounting > New Voucher Entry**
2. Select voucher type (Receipt / Payment / Journal / Contra)
3. You are taken to the voucher entry form with the type pre-selected

#### Payment Voucher (PMNT)

Records money paid to a vendor, supplier, or expense account.

**Step-by-step:**

1. Navigate to **Financial Accounting > New Voucher Entry > Payment**, or go to **Voucher Lists > Payment Vouchers** and click **Add New**
2. **Date**: Defaults to today; change if backdating within the active fiscal year
3. **Voucher No**: Auto-generated (read-only)
4. **Vendor Bill No**: Optionally enter the vendor's invoice/bill reference
5. **Add the vendor/expense line** (the party being paid):
   - In the **Account** field, type the vendor or expense ledger name (e.g., "Priya Gold Suppliers")
   - Enter the amount in the **Debit** column
   - Press **Tab** from the Credit field to add the row
6. **Allocate against outstanding purchase bills** (optional):
   - When you select a vendor ledger, the **Outstanding Purchase Bills** panel appears below the table
   - It lists all unpaid purchase invoices for that vendor with bill number, date, total, and outstanding amount
   - **Auto-fill (FIFO)**: Click to automatically allocate oldest bills first until the entered amount is exhausted
   - **Manual allocation**: Type specific amounts in the Allocate column for each bill
   - The footer shows: Party amount | Allocated | Unallocated (on account)
   - When you press Tab, the single vendor row is expanded into one row per allocated bill (with Ref Bill No filled), plus an "on account" row for any unallocated remainder
7. **Add the cash/bank line** (source of payment):
   - Select the Cash or Bank ledger in the **Account** field
   - Enter the same amount in the **Credit** column
   - Press **Tab** to add the row
8. Verify: **Total Debit = Total Credit** (difference must be 0)
9. Enter a **Narration** (e.g., "Payment to Priya Gold against PV-001")
10. Optionally attach supporting documents (up to 3 files)
11. Click **Save** (or press **F4**)

**Cash payment limit**: Payments over Rs 10,000 in cash to a single vendor per day are blocked under Section 40A(3). Use a bank account for larger payments.

#### Receipt Voucher (RCPT)

Records money received from a customer.

**Step-by-step:**

1. Navigate to **Financial Accounting > New Voucher Entry > Receipt**, or go to **Voucher Lists > Receipt Vouchers** and click **Add New**
2. **Date**: Defaults to today
3. **Add the cash/bank line** (where the money goes):
   - Select the Cash or Bank ledger in **Account**
   - Enter the amount in the **Debit** column
   - Press **Tab** to add the row
4. **Add the customer line** (the party paying):
   - Select the customer ledger in **Account** (e.g., "Rahul Mehta")
   - Enter the amount in the **Credit** column
5. **Allocate against outstanding sales bills** (optional):
   - The **Outstanding Sales Bills** panel appears for the selected customer
   - Use **Auto-fill (FIFO)** or manually allocate across bills
   - Press **Tab** from Credit to expand allocations into individual rows
6. Verify: **Total Debit = Total Credit**
7. Add narration, optional attachments, then **Save**

**Cash receipt limit**: Cash receipts over Rs 1,99,999 from a single customer per financial year are blocked under Section 269ST.

#### Journal Voucher (JRNL)

Used for adjustments, provisions, depreciation entries, and other non-cash transfers.

1. Navigate to **Financial Accounting > New Voucher Entry > Journal**
2. Add debit and credit lines with ledger accounts and amounts
3. The **Status** column is available for journal entries — set to "Against_Ref" to link to a specific invoice, or "onAccount" for general entries
4. In the **Ref Bill No** field, enter a sales or purchase invoice number to adjust its outstanding balance
5. Verify totals balance, add narration, and **Save**

#### Contra Voucher (CONTRA)

Transfers funds between Cash and Bank accounts (e.g., cash deposit or withdrawal).

1. Navigate to **Financial Accounting > New Voucher Entry > Contra**
2. Debit the receiving account (e.g., Bank for a deposit)
3. Credit the sending account (e.g., Cash)
4. Amounts must balance. Add narration and **Save**

#### Bill-wise Allocation (Details)

The bill allocation system ensures payments and receipts are properly matched to invoices:

- **Automatic matching**: Select a party ledger and the system fetches all unpaid invoices for that party
- **FIFO auto-fill**: One click allocates against the oldest outstanding bills first
- **Manual allocation**: Enter specific amounts per bill — useful for partial payments
- **On-account remainder**: Any unallocated amount is posted as an "on account" balance
- **Validation**:
  - Allocation cannot exceed the party amount in the voucher
  - Each bill allocation cannot exceed that bill's outstanding balance
  - Ledger must match — you cannot pay Vendor A's bill from Vendor B's ledger
- **Due amount tracking**: When a voucher is saved, the allocated amounts are deducted from each invoice's `due_amt`, keeping the outstanding report accurate

### 11.4 Opening Balances

Set up beginning balances for a new fiscal year:

1. Navigate to **Financial Accounting > Opening Balances**
2. Select ledger
3. Enter debit or credit opening balance
4. Save

> For subsequent years, use the **Sync Opening Balances** feature in Fiscal Year management.

### 11.5 Cash Gold Conversion

Track conversion between cash and gold accounts:

1. Navigate to **Financial Accounting > Cash Gold Conversion**
2. Select type: **CG** (Cash to Gold) or **GC** (Gold to Cash)
3. Enter ledger, weight, rate, amount
4. System auto-creates a journal voucher

### 11.6 Ledger Statement

View detailed transaction history for any ledger:

1. Navigate to **Financial Accounting > Ledger Statement**
2. Select ledger and date range
3. View all debits, credits, and running balance

### 11.7 Outstanding Report

View amounts due from customers / to vendors:

1. Navigate to **Financial Accounting > Outstanding Report**
2. Filter by ledger type (Receivable / Payable)
3. See invoice-wise outstanding amounts

### 11.8 Bank Reconciliation

Match bank statement entries to book entries:

1. Navigate to **Financial Accounting > Finance Reports > Bank Reconciliation**
2. Select bank ledger
3. Import bank statement (CSV) or enter manually
4. Match statement lines to voucher entries
5. View reconciliation summary (book vs bank balance)

### 11.9 Audit Queue

Auditors can review and approve vouchers:

1. Navigate to **Financial Accounting > Audit Queue**
2. View un-audited vouchers
3. Review details and mark as audited
4. Add audit notes

---

## 12. GST & Tax Compliance

### 12.1 Automatic GST Computation

The system automatically determines GST treatment:
- **Intra-state** (same state): CGST + SGST
- **Inter-state** (different state): IGST
- **Unregistered vendor**: Reverse Charge Mechanism (RCM)

GST rates are derived from the HSN code linked to items.

### 12.2 GST Reports

| Report | Path | Description |
|--------|------|-------------|
| GST Input Register | Financial Accounting > GST & Tax Reports | All input tax credits |
| GST Output Register | Financial Accounting > GST & Tax Reports | All output tax collected |
| GSTR-1 | Financial Accounting > GST & Tax Reports | B2B, B2CL, B2CS breakdowns |
| GSTR-3B Summary | Financial Accounting > GST & Tax Reports | Monthly return summary |
| GSTR-2B Reconciliation | Financial Accounting > GST & Tax Reports | Match with vendor filings |

### 12.3 Credit/Debit Notes

For post-billing adjustments:

1. Navigate to **Financial Accounting > Credit/Debit Notes**
2. Select type: **Credit Note** (customer) or **Debit Note** (vendor)
3. Link to original invoice (optional)
4. Enter adjustment amount, GST breakup
5. System auto-creates the accounting voucher with correct GST ledger postings

### 12.4 TDS Register

View all TDS deductions made on purchases:

1. Navigate to **Financial Accounting > GST & Tax Reports > TDS Register**
2. Filter by period, section, vendor
3. Export for TDS return filing

### 12.5 TCS Register

View all TCS collected on sales:

1. Navigate to **Financial Accounting > GST & Tax Reports > TCS Register**
2. Filter by period and section

---

## 13. Fixed Assets & Depreciation

### 13.1 Asset Master

Register fixed assets (computers, furniture, vehicles, etc.):

1. Navigate to **Financial Accounting > Fixed Assets > Asset Master**
2. Click **Add Asset**
3. Fill in details:
   - Asset code, name, description
   - Purchase date and cost
   - Residual/salvage value
   - Depreciation method: **WDV** (Income Tax Act) or **SLM** (Companies Act)
   - IT Block Category (Computer 40%, Furniture 10%, Vehicle 15%, etc.)
   - Rate or useful life

### 13.2 Depreciation Worksheet

Generate and approve depreciation:

1. Navigate to **Financial Accounting > Fixed Assets > Depreciation Worksheet**
2. Select period (from date, to date)
3. Click **Generate Suggestions**
4. Review calculated amounts for each asset
5. Override amounts if needed (e.g., half-year rule for IT Act)
6. **Approve** to create the depreciation voucher

### 13.3 FA Settings

Configure default ledgers per retail:

1. Navigate to **Financial Accounting > Fixed Assets > FA Settings**
2. Set default Depreciation Expense ledger
3. Set default Accumulated Depreciation ledger

---

## 14. Gold Scheme Management

### 14.1 Scheme Types

| Type | Description |
|------|-------------|
| **INSTALLMENT** | Monthly fixed-amount payments for a tenure |
| **ACCUMULATION** | Monthly payments converted to gold at payment-day rate |
| **LUMPSUM** | One-time payment with locked gold rate |

### 14.2 Scheme Setup

1. Navigate to **Gold Scheme** (via admin or API)
2. Create a scheme master:
   - Name, code, type
   - Tenure (months), min/max amount
   - Gold price mode (Current / Accumulated / Locked)
3. Define benefit tiers:
   - 6-8 months → 40% making charge discount
   - 9-10 months → 60% making charge discount
   - 11 months → 75% making charge discount

### 14.3 Customer Enrollment

1. Create an enrollment for a customer:
   - Select scheme and customer
   - Set installment amount
   - Start date and maturity date
2. Enrollment status: ACTIVE → MATURED → REDEEMED

### 14.4 Recording Payments

1. Record each monthly payment:
   - Amount, payment mode (Cash/Bank/UPI)
   - Payment ledger (Cash or Bank account)
2. System auto-creates a **SCHM** accounting voucher:
   - Dr Cash/Bank
   - Cr Scheme Liability

### 14.5 Redemption

When the scheme matures and the customer purchases jewellery:

1. The accumulated amount/gold is adjusted against the sales bill
2. Making charge discount is applied as per benefit tier
3. Enrollment status changes to REDEEMED

### 14.6 Customer Portal

Customers can access their scheme information online:
- View enrollment details
- Check payment history
- See accumulated gold weight
- View applicable benefits

---

## 15. HR & Payroll

### 15.1 Employee Setup

1. Navigate to **HR > Employees**
2. Click **Add Employee**
3. Fill in:
   - Employee code, full name
   - Designation, department
   - Date of joining
   - Bank details (for salary transfer)
   - PAN, PF number, ESI number
4. System creates a linked Django user account

### 15.2 Salary Structure

1. Navigate to **HR > Salary Structure**
2. Define earnings for each employee:
   - Basic salary
   - HRA (House Rent Allowance)
   - DA (Dearness Allowance)
   - Conveyance, Medical, Special Allowance

### 15.3 Deduction Configuration

Configure deductions per employee:
- **PF**: 12% of basic (capped at Rs 15,000 basic if not opted for full)
- **ESI**: 0.75% employee + 3.25% employer (for gross < Rs 21,000)
- **Professional Tax**: State-specific slab
- **TDS**: Monthly income tax deduction
- **Advance Recovery**: EMI for advance salary

### 15.4 Salary Processing

1. Navigate to **HR > Salary Processing**
2. Select month and year
3. Click **Generate Slips**
4. System auto-calculates:
   - Proportional earnings (based on days worked)
   - All applicable deductions
   - Net salary
5. Review and **Approve** slips
6. On approval, system creates a **SLRY** accounting voucher

### 15.5 HR Settings

Configure accounting ledgers for salary posting:
- Salary Expense Ledger
- Employee Payable Ledger
- PF/ESI/PT/TDS Payable Ledgers

---

## 16. Reports

### 16.1 Financial Reports

| Report | Path | Description |
|--------|------|-------------|
| Trial Balance | Finance Reports | All ledger balances (Debit/Credit) |
| Balance Sheet | Finance Reports | Assets = Liabilities + Capital |
| Profit & Loss | Finance Reports | Income - Expenses = Profit/Loss |
| P&L Calculation | Finance Reports | Detailed P&L with opening/closing stock |
| Financial Ratios | Finance Reports | Current ratio, quick ratio, etc. |
| Cash Book | Finance Reports | All cash transactions |
| Bank Book | Finance Reports | All bank transactions |
| Day Book | Finance Reports | All vouchers for a date |
| Gold Ledger Balances | Finance Reports | Gold weight balances per ledger |

### 16.2 Sales Reports

| Report | Path | Description |
|--------|------|-------------|
| Salesperson Commission | Sales > Reports | Commission earned per salesperson |

### 16.3 Inventory Reports

| Report | Path | Description |
|--------|------|-------------|
| Stock Report | Inventory > Reports | Current stock by barcode |
| Closing Stock Valuation | Inventory > Reports | Stock value for accounting |
| Metal Report | Inventory > Reports | Gold/silver weight summaries |
| Packetwise Stone | Inventory > Reports | Stone inventory by packet |
| Raw Material Balance | Inventory > Reports | Raw material on hand |
| Raw Material Ledger | Inventory > Reports | Transaction history per material |
| Semi-Finished Stock | Inventory > Reports | Items with karigars |
| ItemWise Barcode | Inventory > Reports | Barcodes grouped by item |
| Barcode Split/Merge | Inventory > Reports | History of splits and merges |

### 16.4 Manufacturing Reports

| Report | Path | Description |
|--------|------|-------------|
| Karigar Job Work | Manufacturing > Reports | Outstanding with each karigar |
| Karigar Stone Transactions | Manufacturing > Reports | Stone issue/return per karigar |
| Hallmark Issue/Receive | Manufacturing > Reports | Hallmarking status |
| Finished Item Receive | Manufacturing > Reports | Items received from manufacturing |
| Refinery Report | Manufacturing > Reports | Refinery transactions |

---

## 17. Settings & Administration

### 17.1 User Management

1. Navigate to **Settings > User Management**
2. Create, edit, or deactivate user accounts
3. Assign retail location access

### 17.2 Roles & Permissions

1. Navigate to **Settings > Roles & Permissions**
2. Create roles (Admin, Manager, Sales, Billing, Accounts, etc.)
3. Configure permissions per module:
   - Can View (GET)
   - Can List (LIST)
   - Can Create (POST)
   - Can Edit (PUT/PATCH)
   - Can Delete (DELETE)

### 17.3 Fiscal Year Management

Navigate to **Setup > Organisation > Fiscal Years**:

- **Create FY**: New fiscal year for a retail
- **Close FY**: Prevents new transactions (soft close)
- **Hard Close FY**: Prevents all changes including audit adjustments
- **Reopen FY**: Reverses a soft close
- **Sync Opening Balances**: Copies closing balances to the next FY as opening balances

### 17.4 Exhibition Mode

For temporary exhibitions/fairs at different venues:

1. Navigate to **Setup > Organisation > Exhibitions**
2. Create an exhibition profile:
   - Venue name, address, GSTIN (if different)
   - Activation dates
3. When active, the exhibition's GSTIN/address overrides the retail's defaults on all invoices

### 17.5 CRM Automation (WhatsApp)

Configure automated WhatsApp messages:

1. Navigate to **Settings > CRM Automation**
2. Select provider: Meta Cloud API, WATI, or AiSensy
3. Configure API keys and template names
4. Enable automated messages for:
   - Sales confirmation
   - Payment receipts
   - Birthday/anniversary greetings

### 17.6 Advanced Settings

Configure system-wide settings:
- Attachment storage path
- Barcode image storage path
- Bill total auto-calculation mode

### 17.7 Audit Log

Navigate to **Settings > Audit Log** to view:
- All data changes (create, update, delete)
- HTTP request history
- Login/logout events

---

## 18. Customer Portal

A separate web portal for customers to access their scheme information.

### Portal Access

- URL: `http://your-domain/portal/`
- Login via mobile number + OTP
- Or username/password (if configured)

### Portal Features

- View gold scheme enrollments
- Check payment history
- See accumulated gold weight
- View applicable discount benefits
- Download enrollment statements

---

## 19. Best Practices

### Data Entry Guidelines

1. **Always verify gold rates** before creating sales/purchase vouchers
2. **Scan barcodes** instead of manual entry wherever possible
3. **Allocate payments to specific bills** (don't leave as "on account" unless intentional)
4. **Record cash transactions immediately** — the system tracks daily/annual cash limits
5. **Close fiscal year promptly** after auditing — prevents back-dated entries

### Common Mistakes to Avoid

| Mistake | Impact | Prevention |
|---------|--------|------------|
| Creating vouchers outside the fiscal year | Reports will be inaccurate | System now validates FY boundaries |
| Not configuring GST ledgers before billing | GST won't be posted correctly | Setup wizard ensures this |
| Deleting barcodes instead of processing returns | Audit trail lost permanently | Use Sales/Purchase Return flows |
| Duplicate salary slip generation | Double payment | System enforces unique (employee, month, year) |
| Transferring stock without receiving at destination | Items stuck "in transit" forever | Follow up on all pending transfers |
| Ignoring TDS on large purchase payments | Compliance penalty | System auto-calculates when configured |

### Daily Checklist

- [ ] Update gold rates for the day
- [ ] Check and process pending stock transfers
- [ ] Verify cash book balance matches physical cash
- [ ] Review outstanding payments due today
- [ ] Back up the database (for SQLite setups)

### Monthly Checklist

- [ ] Process salaries for all employees
- [ ] Run bank reconciliation for all bank accounts
- [ ] Review and file GSTR-3B
- [ ] Check outstanding receivables aged > 90 days
- [ ] Review gold scheme payments and maturity calendar

### Year-End Checklist

- [ ] Run closing stock valuation
- [ ] Generate P&L and Balance Sheet
- [ ] Generate depreciation for all fixed assets
- [ ] File GSTR-1 annual reconciliation
- [ ] Sync opening balances to new fiscal year
- [ ] Close the old fiscal year (after auditor approval)

---

## 20. Troubleshooting

### Common Issues & Solutions

#### "Retail location not found" error
**Cause:** Invalid `X-RETAIL-ID` header or retail not configured.
**Fix:**
1. Check that the retail code in your browser/session matches an existing retail
2. Go to **Setup > Organisation > Retail** and verify the code
3. Log out and log in again to refresh the session

#### "Fiscal year is hard-closed" error
**Cause:** Attempting to post entries in a closed fiscal year.
**Fix:**
1. Go to **Setup > Organisation > Fiscal Years**
2. Click **Reopen** on the hard-closed FY (requires admin permission)
3. Post the entry, then re-close

#### "Cash receipt limit exceeded" warning
**Cause:** Section 269ST limits cash receipts to Rs 1,99,999 per customer per FY.
**Fix:**
1. Accept remaining amount via bank transfer / UPI
2. Or split across fiscal years if applicable

#### "Cash payment limit exceeded" warning
**Cause:** Section 40A(3) limits cash payments to Rs 10,000 per vendor per day.
**Fix:** Make the payment via bank transfer instead.

#### "Total debit and credit amounts must be equal" error
**Cause:** Voucher lines don't balance.
**Fix:** Check all debit and credit amounts. Ensure they sum to the same total.

#### "Overpayment on purchase/sale" error
**Cause:** Trying to allocate more than the outstanding amount on an invoice.
**Fix:** Check the outstanding amount on the invoice and adjust the payment accordingly.

#### Sales or P&L report shows incorrect values
**Cause:** Opening stock not configured, or fiscal year not synced.
**Fix:**
1. Verify opening balances are set for all ledgers
2. Ensure closing stock valuation has been run
3. Check that the correct fiscal year is active

#### Barcode not found during sales
**Cause:** Barcode is not in stock (already sold, in transit, or with karigar).
**Fix:**
1. Check barcode history to see its current status
2. If in transit, receive the stock transfer first
3. If with karigar, process the job work receive first

#### Gold scheme voucher not created
**Cause:** Signal failed during payment recording (accounting error).
**Fix:**
1. Check the error logs for details
2. Create a manual SCHM journal voucher:
   - Dr Cash/Bank (payment ledger)
   - Cr Gold Scheme Liability

### Getting Help

- **Admin Panel:** Access Django admin at `http://your-domain/admin/` for low-level data management
- **Audit Log:** Check **Settings > Audit Log** for recent system activity
- **Error Logs:** Server logs are available in the terminal where `runserver` is running

---

## 21. Glossary

| Term | Description |
|------|-------------|
| **Barcode** | 13-digit unique identifier for each jewellery piece |
| **Karigar** | Artisan / goldsmith who manufactures jewellery |
| **Ledger** | An account representing a customer, vendor, bank, or expense head |
| **Purity** | Gold purity (22K = 91.6%, 24K = 99.9%, etc.) |
| **HSN** | Harmonized System Nomenclature — product classification code for GST |
| **HUID** | Hallmark Unique Identification — BIS hallmark number |
| **Tunch** | Purity factor used in gold valuation |
| **Making Charges** | Labour cost for manufacturing jewellery (per gram or per piece) |
| **Old Gold** | Gold brought by customer for exchange against new purchase |
| **FY** | Fiscal Year (April 1 to March 31 in India) |
| **CGST** | Central Goods & Services Tax |
| **SGST** | State Goods & Services Tax |
| **IGST** | Integrated Goods & Services Tax (inter-state) |
| **RCM** | Reverse Charge Mechanism — buyer pays GST for unregistered seller |
| **TDS** | Tax Deducted at Source |
| **TCS** | Tax Collected at Source |
| **WDV** | Written Down Value — depreciation method (Income Tax Act) |
| **SLM** | Straight Line Method — depreciation method (Companies Act) |
| **PF** | Provident Fund — employee retirement savings |
| **ESI** | Employee State Insurance — medical coverage |
| **PT** | Professional Tax — state-level employment tax |
| **Contra** | Cash to Bank or Bank to Cash transfer entry |
| **E-Way Bill** | Electronic permit for movement of goods (GST compliance) |
| **Solitaire** | Large, individually priced diamond (vs melee/small diamonds) |
| **Packet** | Standardized stone specification (shape + color + clarity + sieve) |
| **Retail** | A physical store/showroom location in the ERP |
| **Branch** | State-level organizational grouping of retail locations |

---

## 22. Migrating from an Existing ERP

If you are transitioning from another ERP (Tally, Marg, Busy, Wonder, or any custom system), you do **not** start fresh. Instead, you bring your existing balances and master data into Jewel India ERP on a **cut-over date** — typically the first day of a new financial year or the first day of the current month.

### 22.1 Overview of the Migration Flow

The data must be entered in the following order. Each step depends on the previous one being complete.

```
1. Company, Branch, GSTIN, Retail, Fiscal Year  (Setup Wizard)
       ↓
2. Account Groups + System Ledgers              (Setup Wizard: auto-seeded)
       ↓
3. States, TDS/TCS Sections, HSN Codes, Purities (Setup Wizard: auto-seeded)
       ↓
4. Item Masters & Packets                        (Masters section)
       ↓
5. Ledger Masters (Customers, Vendors, Banks,    (CRM → Ledgers)
   Karigars, etc.) with opening balances
       ↓
6. Opening Stock (Barcoded & Raw)               (Inventory section)
       ↓
7. Fixed Assets with opening WDV                (Fixed Assets section)
       ↓
8. Ledger Opening Balances (Trial Balance)       (Financial Accounting)
       ↓
9. Pending Orders & Job Cards (optional)         (Sales / Manufacturing)
```

### 22.2 Step-by-Step Instructions

#### Step 1 — Complete the Setup Wizard

Run the setup wizard at **Settings > Setup Wizard** if you have not already done so. This creates your company, branch, GSTIN, at least one retail location, and the active fiscal year. The wizard also auto-seeds:

- All Indian states/UTs
- Chart of accounts (account groups)
- TDS and TCS sections
- Default HSN codes for jewellery
- Default purity masters

Do not skip any wizard step before proceeding.

#### Step 2 — Create Item Masters

Before entering any stock, set up your item hierarchy:

1. Navigate to **Masters > Item Group** — create main categories (Gold Jewellery, Diamond Jewellery, Silver, etc.)
2. Navigate to **Masters > Item Master** — create individual items within each group
3. Navigate to **Masters > Packet Master** — define stone specification packets if you carry stones

Pull this data from your old ERP's item list or stock registers.

#### Step 3 — Create Ledger Masters

Create ledger accounts for every party you transact with. Navigate to **CRM > Ledgers > New Ledger** for each.

| Ledger Type | Role to Assign | Account Group |
|---|---|---|
| Customer | Customer (CO) | Sundry Debtors |
| Wholesale Dealer | Dealer (DL) | Sundry Debtors |
| Supplier / Vendor | Vendor (VD) | Sundry Creditors |
| Karigar | Karigar (KR) | Sundry Creditors |
| Bank Account | Bank Account (BA) | Bank Accounts |
| Cash Account | Cash (CA) | Cash-in-Hand |
| Expense accounts | — | Relevant expense group |

**Tips:**
- If a party is both a customer and a supplier, assign both roles (CO + VD) on the same ledger
- GST number, PAN, and state are required for B2B parties for correct tax treatment
- For banks, enter the account number and IFSC in the contact section

#### Step 4 — Enter Opening Stock

##### Barcoded Stock

For each barcoded item in hand on your cut-over date:

1. Navigate to **Inventory > Barcode Management > Barcodes**
2. Click **Add New Barcode**
3. Enter all fields: barcode number, item, purity, gross weight, pcs, making type, making value, and packet details (for stone items)
4. Set **Status** to `In Stock`

If you have many barcodes, use the **Import** feature: navigate to **Masters > Import Data**, download the barcode import template, fill it from your old system's stock report, and upload.

##### Raw / Unbarcoded Stock

For raw material (gold bars, silver, loose stones) that is not barcoded:

1. Navigate to **Inventory > Raw Material Ledger**
2. Enter an opening balance entry for each material type and purity
3. Enter quantity (in grams), purity, and value

#### Step 5 — Enter Fixed Asset Opening Balances

For each fixed asset on your balance sheet on the cut-over date:

1. Navigate to **Financial Accounting > Fixed Assets > Asset Master**
2. Click **Add Asset**
3. Fill in the following fields:

| Field | What to Enter |
|---|---|
| Asset Code | Unique code (e.g., `COMP-001`, `VEH-001`) |
| Asset Name | Descriptive name (e.g., "Dell Laptop — Accounts") |
| Purchase Date | Original date of purchase (not the cut-over date) |
| Purchase Cost | Original cost at the time of purchase |
| Residual Value | Expected scrap value at end of life |
| Depreciation Method | WDV (Income Tax Act) or SLM (Companies Act) |
| IT Block Category | Select the applicable IT Act block |
| Rate or Useful Life | Depreciation % (WDV) or years (SLM) |

> **For migration specifically:** After saving the asset, the system will calculate accumulated depreciation from the purchase date to the cut-over date automatically when you run the Depreciation Worksheet. Review and approve this opening depreciation to establish the correct **Written Down Value (WDV)** as of the cut-over date. Do this before recording any new depreciation for the current year.

If you already know the WDV as of the cut-over date from your old ERP's fixed asset register:
- Cross-check it against the system's calculated WDV
- If there is a difference (rounding, block-pooling in old system), enter a one-time adjusting journal entry to the accumulated depreciation ledger

#### Step 6 — Enter Ledger Opening Balances

Enter the opening trial balance — the balances of all ledgers as of the cut-over date from your old ERP's trial balance report.

1. Navigate to **Financial Accounting > Vouchers > Journal**
2. Select voucher type **OPENING** (or the fiscal year's first date)
3. Enter each ledger with its Dr/Cr balance:
   - All customer balances as **Debit** (they owe you)
   - All supplier/karigar balances as **Credit** (you owe them)
   - Bank account balances as **Debit**
   - Cash balance as **Debit**
   - Loan/liability balances as **Credit**
   - Capital account as **Credit**
   - Fixed asset account totals as **Debit** (gross cost)
   - Accumulated depreciation as **Credit**
   - Retained earnings / P&L carried forward as **Credit**
4. The journal must balance (Total Debit = Total Credit) before saving

> **Important:** The fixed asset account in the journal represents the gross cost of all assets. The accumulated depreciation account represents all depreciation up to the cut-over date. The difference between the two equals the total WDV, which should match the sum of individual asset WDVs from Step 5.

#### Step 7 — Enter Pending Customer Orders (Optional)

If you have open customer orders that were taken in your old system and have not yet been delivered, enter them in **Sales > Customer Orders** so they flow correctly into manufacturing job cards and pending reports. Only enter orders that are still open (not yet fully delivered).

#### Step 8 — Enter Pending Karigar Job Cards (Optional)

If you have gold or stones currently issued to karigars and not yet received back, enter opening issue records in **Manufacturing > Issue > Job Work**. This ensures your karigar-wise outstanding reports are accurate from day one.

### 22.3 Verification Checklist

After completing migration, verify the following before going live:

- [ ] Trial balance Total Debit = Total Credit
- [ ] Bank ledger balances match bank statements on cut-over date
- [ ] Cash ledger balance matches physical cash count
- [ ] Total barcoded stock WGT matches your old system's stock report
- [ ] Total raw material balance matches your old system
- [ ] Fixed asset WDV total in ERP matches fixed asset register from old ERP
- [ ] Customer outstanding total matches old system's debtors report
- [ ] Vendor outstanding total matches old system's creditors report
- [ ] All GST input/output credit carry-forwards are entered if applicable

### 22.4 What NOT to Enter

Avoid entering the following historical data unless specifically required:

- Completed past vouchers (old invoices, old receipts) — only opening balances are needed
- Closed job cards and completed orders — only open/pending ones matter
- Historical depreciation voucher-by-voucher — enter opening accumulated depreciation as a single lump sum

---

## 23. AI Assistant & MCP Server Setup

Jewel India ERP includes a built-in AI assistant powered by Claude (Anthropic). The AI can answer business questions in plain English, such as:

- "What were total sales last month?"
- "Show me outstanding dues from customers over ₹50,000"
- "Which karigar has the most gold pending return?"
- "What is the current gold stock valuation?"

There are two ways to use the AI:

1. **In-app AI Chat** — available directly in the ERP interface (no additional setup required)
2. **MCP Server** — connects the ERP's data to Claude Desktop or other AI clients on your computer for a richer, conversational experience

### 23.1 In-App AI Chat

No setup required. Navigate to the **AI Assistant** section in the sidebar. Type your question in plain English and press Enter. The assistant has read access to all your ERP data but cannot modify records.

### 23.2 MCP Server Setup (Claude Desktop)

The MCP (Model Context Protocol) server exposes your ERP data as tools that Claude Desktop can call. This gives you a full conversational AI experience with your business data.

#### Prerequisites

- Claude Desktop installed on your computer ([download from claude.ai](https://claude.ai/download))
- The ERP backend must be running (`python manage.py runserver`)
- Python virtual environment must be active

#### Configuration

1. **Locate your Claude Desktop config file:**

   - **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

2. **Open the config file** in any text editor. If it does not exist, create it.

3. **Add the MCP server entry:**

```json
{
  "mcpServers": {
    "jewel-india-erp": {
      "command": "python",
      "args": ["C:\\path\\to\\your\\Jewel India ERP\\backend\\mcp_server.py"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "jewel_test.settings"
      }
    }
  }
}
```

Replace `C:\\path\\to\\your\\Jewel India ERP` with the actual path where you installed the ERP. Use double backslashes (`\\`) on Windows.

4. **Save the config file** and **restart Claude Desktop** completely (quit and reopen — not just close the window).

5. **Verify the connection:** Open Claude Desktop and look for the hammer icon (🔨) in the chat input area. Click it — you should see tools listed like `get_sales_summary`, `get_outstanding_debtors`, `get_stock_summary`, etc. If you see these, the connection is working.

#### Testing the Connection

In Claude Desktop, type:

> "Connect to Jewel India ERP and show me the available retail locations."

Claude will call the ERP and respond with your retail location list. If it works, you can ask any business question.

#### Available AI Tools

| Tool | What It Does |
|---|---|
| `get_sales_summary` | Total sales, invoice count, top customers for a date range |
| `get_outstanding_debtors` | All customers with unpaid balances |
| `get_outstanding_creditors` | All vendors/karigars with payable balances |
| `get_stock_summary` | Current barcoded stock count and weight by category |
| `get_stock_valuation` | Stock value breakdown by item and purity |
| `get_karigar_jobs_status` | Gold and stones currently with karigars |
| `get_ledger_balance` | Balance of any specific ledger account |
| `get_trial_balance_summary` | Summarised trial balance for a period |
| `get_cash_position` | Current cash and bank balances |
| `get_day_book` | All vouchers for a given date range |
| `get_profit_and_loss` | P&L statement for a period |
| `get_balance_sheet` | Balance sheet as of a date |
| `get_gst_summary` | GST output, input, and net payable |
| `get_scheme_summary` | Gold scheme enrollment and payment stats |
| `get_dashboard_summary` | Combined business health snapshot |

#### Multi-Location Usage

If you have multiple retail locations, you can specify a retail code in your question:

> "Show me outstanding debtors for the Borivali branch."

Claude will pass the appropriate `retail_code` to filter results for that location.

#### Troubleshooting the MCP Connection

| Problem | Solution |
|---|---|
| Tools not appearing in Claude Desktop | Restart Claude Desktop completely; verify the path in config is correct |
| "Django settings not found" error | Ensure `DJANGO_SETTINGS_MODULE` is set in the env block of the config |
| "Database locked" errors | Make sure only one Django process is running; close the dev server and restart |
| No data returned | Confirm the ERP backend is running on `http://127.0.0.1:8000` |
| Python not found | Use the full path to the venv Python: `C:\\...\\backend\\env\\Scripts\\python.exe` |

#### Using the Full Python Path (Recommended)

To avoid "Python not found" errors, use the full path to the virtual environment's Python executable instead of just `python`:

```json
{
  "mcpServers": {
    "jewel-india-erp": {
      "command": "C:\\path\\to\\Jewel India ERP\\backend\\env\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\Jewel India ERP\\backend\\mcp_server.py"]
    }
  }
}
```

---

## Document Information

| Field | Value |
|-------|-------|
| **Document Title** | Jewel India ERP - User Manual |
| **Version** | 1.1 |
| **Date** | April 2026 |
| **Prepared For** | First-time ERP clients |
| **Confidentiality** | Client-use only |

---

*This manual covers the core features of Jewel India ERP. For API documentation, developer guides, or custom integrations, please contact the vendor's technical team.*
