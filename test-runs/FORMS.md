# Form requirements per `/add` route

## `/accounting/account-create`
**Selects (need pre-existing data):**
- Camac Street
**Submit:** Save Group, Save Group

## `/accounting/credit-debit-notes/add`
**Selects (need pre-existing data):**
- Camac Street
**Submit:** Save Credit Note

## `/crm/ledger/add`
**Required:**
- ac_name (input)
- display_name (input)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
-  (select)
-  (select)
-  (select)
-  (select)
- Camac Street
- — None —
- Not Applicable
- None
- — Select —
- 🇮🇳 +91
- 🇮🇳 +91
- 🇮🇳 +91
**Submit:** Save Ledger, Save Ledger

## `/inventory/barcodemanagement/list/add/`
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
- Camac Street
- Select
- Select
- Type
**Submit:** Save

## `/inventory/stockjournal/add`
**Required:**
- Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
- Camac Street
- Purity
- Type
**Submit:** Save

## `/inventory/stocktransfer/add`
**Required:**
- form.date1 (date)
**Selects (need pre-existing data):**
-  (select)
- Camac Street
- Select destination retail
**Submit:** Save Transfer

## `/manufacturing/issue/assay/add`
**Required:**
- form.date1 (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
- Camac Street
- No available melting receives
- Purity
**Submit:** Save

## `/manufacturing/issue/goldissue/add`
**Required:**
- Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
- Camac Street
- Select Slip Type
- Select Purity
- Select Purity
**Submit:** Save

## `/manufacturing/issue/hallmarkissue/add`
**Required:**
- Date (date)
- Hallmarking center (input)
**Selects (need pre-existing data):**
- Camac Street
**Submit:** Save

## `/manufacturing/issue/jobwork/add`
**Required:**
- Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
- Camac Street
- Stock
- Select Purity
- 
**Submit:** Save

## `/manufacturing/issue/melting/add`
**Required:**
- form.date1 (date)
**Selects (need pre-existing data):**
-  (select)
- Camac Street
- Purity
**Submit:** Save

## `/manufacturing/issue/refinary/add`
**Required:**
- form.date1 (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
- Camac Street
- — None —
- Pick a source type first
- Purity
**Submit:** Save

## `/manufacturing/issue/stoneissue/add`
**Required:**
- Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
- Camac Street
- Select Slip Type
- West Bengal
**Submit:** Save

## `/manufacturing/receive/assay/add`
**Required:**
- form.date1 (date)
- form.ldgr_name (input)
**Selects (need pre-existing data):**
- Camac Street
**Submit:** Save

## `/manufacturing/receive/hallmarkreceive/add`
**Required:**
- Date (date)
- Hallmarking center (input)
**Selects (need pre-existing data):**
- Camac Street
**Submit:** Save

## `/manufacturing/receive/jobworkreceive/add`
**Required:**
- Date (date)
**Selects (need pre-existing data):**
-  (select)
- Camac Street
- West Bengal
**Submit:** Save

## `/manufacturing/receive/melting/add`
**Required:**
- form.date1 (date)
- form.ldgr_name (input)
**Selects (need pre-existing data):**
- Camac Street
**Submit:** Save

## `/manufacturing/receive/refinary/add`
**Required:**
- form.date1 (date)
- form.ldgr_name (input)
**Selects (need pre-existing data):**
- Camac Street
**Submit:** Save

## `/manufacturing/receive/stonereturn/add`
**Required:**
- Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
- Camac Street
- Select Slip Type
- West Bengal
**Submit:** Save

## `/manufacturing/repair/new`
**Selects (need pre-existing data):**
- Camac Street
- — None —
- — None —
**Submit:** Create Job Card

## `/purchase/add-purchase-voucher/add`
**Required:**
- Date (date)
- Ref.Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
-  (select)
-  (select)
- Camac Street
- Vendor
- Jewellery Plain or Studded
- 
- Making type
- 
**Submit:** Save

## `/purchase/add-rawpurchase-voucher/add`
**Required:**
- Date (date)
- Ref.Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
-  (select)
-  (select)
- Camac Street
- Vendor
- Jewellery Plain or Studded
- 
- Making type
- 
**Submit:** Save

## `/purchase/add/`
**Required:**
- Date (date)
- Ref.Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
-  (select)
-  (select)
- Camac Street
- Vendor
- Jewellery Plain or Studded
- 
- Making type
- 
**Submit:** Save

## `/purchase/customerpurchase/list/add/`
**Required:**
- Date (date)
- Ref.Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
-  (select)
-  (select)
- Camac Street
- Vendor
- Jewellery Plain or Studded
- 
- Making type
- 
**Submit:** Save

## `/purchase/purchaseorder/list/add`
**Required:**
- Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
- Camac Street
- Select Slip Type
- West Bengal
- Select Purity
**Submit:** Save

## `/purchase/purchasereturn/list/add/`
**Required:**
- Vendor / Ledger (input)
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
- Camac Street
- Purity
- Type
- Purity
**Submit:** Save

## `/purchase/purchasevoucher/list/add/`
**Required:**
- Date (date)
- Ref.Date (date)
**Selects (need pre-existing data):**
-  (select)
-  (select)
- Camac Street
- Vendor
- Select HSN
**Submit:** Save

## `/sales/add/`
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
-  (select)
- bank.payment_mode (select)
- bank.ledger (select)
- Camac Street
- Select
- Select
- West Bengal
- Jewellery Plain or Studded
**Submit:** Save

## `/sales/customerorder/list/add/`
**Selects (need pre-existing data):**
- 
- 
- 
- New Booking
- Pending
- Select Purity
- Making type
**Submit:** Save

## `/sales/quotation/add/`
**Selects (need pre-existing data):**
- 
- Select…
- Customer
- Select customer…
**Submit:** Save Draft, Save & Print, Add

## `/sales/rawsalesvoucher/add/`

## `/sales/salesapproval/add/`
**Selects (need pre-existing data):**
-  (select)
-  (select)
-  (select)
-  (select)
- Camac Street
- Select Sales Person
- Select Sales Person 2
- Select State
- 
**Submit:** Save

## `/sales/salesreturn/add/`
**Required:**
- form.ldgr_name (input)
**Selects (need pre-existing data):**
-  (select)
- Camac Street
- Type
**Submit:** Save

## `/scheme/enrollments/add`
**Required:**
- installment_amount (number)
**Selects (need pre-existing data):**
-  (select)
- Camac Street
- Select scheme
**Submit:** Enroll Customer
