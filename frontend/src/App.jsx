import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";

// ── Always-loaded (layout skeleton + auth routing logic) ─────────────────────
import { Page } from "./dashboard";
import Header from "./breadCrumbDecor";
import BaseUrlConfig from "./components/BaseUrlConfig";
import { LoginPage } from "./login";

// ── Lazy-loaded route components ──────────────────────────────────────────────
const Ledger                     = lazy(() => import("./ledger"));
const LedgerForm                 = lazy(() => import("./addLedger.jsx"));
const AccountTree                = lazy(() => import("./chartOfAccouts"));
const AccountCreationForm        = lazy(() => import("./AccountCreate"));
const AddJournal                 = lazy(() => import("./components/FinancialAccounting/vouchers/addJournal"));
const CashGoldConversion         = lazy(() => import("./CashGoldConversion"));
const KarigarIssue               = lazy(() => import("./components/manufacturing/issue/karigarissue"));
const PurchaseVoucher            = lazy(() => import("./components/manufacturing/purchases/PurchaseVoucher"));
const PurchaseOrder              = lazy(() => import("./components/manufacturing/purchases/purchaseOrder"));
const PurchaseOrderList          = lazy(() => import("./components/manufacturing/purchases/purchaseOrderList"));
const KarigarJobs                = lazy(() => import("./components/manufacturing/issue/jobWorkList.jsx"));
const KarigarReceiveList         = lazy(() => import("./components/manufacturing/receive/jobWorkReceiveList"));
const JobWorkReceive             = lazy(() => import("./components/manufacturing/receive/jobWorkReceive"));
const StoneReturn                = lazy(() => import("./components/manufacturing/receive/StoneReturn"));
const KarigarStoneIssue          = lazy(() => import("./components/manufacturing/issue/stoneIssue"));
const GoldIssue                  = lazy(() => import("./components/manufacturing/issue/goldIssue"));
const SampleIssue                = lazy(() => import("./components/manufacturing/issue/SampleIssue"));
const SampleIssueList            = lazy(() => import("./components/manufacturing/issue/SampleIssueList"));
const HallmarkIssue              = lazy(() => import("./components/manufacturing/issue/hallmarkIssue"));
const HallmarkReceive            = lazy(() => import("./components/manufacturing/receive/HallmarkReceive"));
const BarcodeManagementList      = lazy(() => import("./components/Inventory/BarcodeManagement/barcodemanagementlist"));
const BarcodePrint               = lazy(() => import("./components/Inventory/BarcodeManagement/BarcodePrint"));
const MergeBarcode               = lazy(() => import("./components/Inventory/BarcodeManagement/barcodeMerge"));
const DesignList                 = lazy(() => import("./components/Inventory/DesignList"));
const BarcodeListView            = lazy(() => import("./components/Inventory/BarcodeManagement/barcodeList"));
const BarcodeSplit               = lazy(() => import("./components/Inventory/BarcodeManagement/barcodeSplit"));
const SalesVoucherAdd            = lazy(() => import("./components/Sales/SalesVoucherAdd"));
const SalesReturnAdd             = lazy(() => import("./components/Sales/SalesReturnAdd"));
const SalesApprovalAdd           = lazy(() => import("./components/Sales/SalesApprovalAdd"));
const CustomerOrderList          = lazy(() => import("./components/Sales/CustomerOrderList"));
const CustomerOrderKanban        = lazy(() => import("./components/Sales/CustomerOrderKanban"));
const CustomerOrderTracker       = lazy(() => import("./components/Sales/CustomerOrderTracker"));
const CustomerOrderForm          = lazy(() => import("./CustomerOrderForm"));
const SalesVoucherList           = lazy(() => import("./components/Sales/SalesVoucherList"));
const SalesApprovalList          = lazy(() => import("./components/Sales/SalesApprovalList"));
const SalesReturnList            = lazy(() => import("./components/Sales/SalesReturnList"));
const EWayBillList               = lazy(() => import("./components/Sales/EWayBillList"));
const ChequePendingPage          = lazy(() => import("./components/Sales/ChequePendingPage"));
const PurchaseReturnList         = lazy(() => import("./components/manufacturing/purchases/PurchaseReturnList"));
const PurchaseApprovalList       = lazy(() => import("./components/manufacturing/purchases/PurchaseApprovalList.jsx"));
const NotFoundPage               = lazy(() => import("./pageNotFound"));
const HallmarkIssueAdd           = lazy(() => import("./components/manufacturing/issue/hallmarkIssueAdd"));
const SchemeMasterPage           = lazy(() => import("./components/GoldScheme/SchemeMasterPage"));
const SchemeEnrollmentList       = lazy(() => import("./components/GoldScheme/SchemeEnrollmentList"));
const SchemeEnrollmentForm       = lazy(() => import("./components/GoldScheme/SchemeEnrollmentForm"));
const SchemePaymentForm          = lazy(() => import("./components/GoldScheme/SchemePaymentForm"));
const SchemeStatement            = lazy(() => import("./components/GoldScheme/SchemeStatement"));
const SchemeDashboard            = lazy(() => import("./components/GoldScheme/SchemeDashboard"));
const PortalApp                  = lazy(() => import("./portal/PortalApp"));
const EmployeeMasterPage         = lazy(() => import("./components/HR/EmployeeMasterPage"));
const SalaryStructurePage        = lazy(() => import("./components/HR/SalaryStructurePage"));
const SalaryProcessingPage       = lazy(() => import("./components/HR/SalaryProcessingPage"));
const HRSettingsPage             = lazy(() => import("./components/HR/HRSettingsPage"));
const HRPortalApp                = lazy(() => import("./hr-portal/HRPortalApp"));
const FixedAssetMasterPage       = lazy(() => import("./components/FixedAssets/FixedAssetMasterPage"));
const DepreciationWorksheetPage  = lazy(() => import("./components/FixedAssets/DepreciationWorksheetPage"));
const FixedAssetSettingsPage     = lazy(() => import("./components/FixedAssets/FixedAssetSettingsPage"));
const HallmarkReceiveAdd         = lazy(() => import("./components/manufacturing/receive/hallmarkReceiveAdd"));
const PurchaseReturnadd          = lazy(() => import("./components/manufacturing/purchases/PurchaseReturnAdd"));
const PurchaseVoucherList        = lazy(() => import("./components/manufacturing/purchases/PurchaseVoucherList"));
const StockMatchingReport        = lazy(() => import("./components/manufacturing/purchases/StockMatchingReport"));
const IdGenerationReport         = lazy(() => import("./components/Inventory/BarcodeManagement/IdGenerationReport"));
const KarigarStoneTransactions   = lazy(() => import("./components/manufacturing/reports/KarigarStoneTransactions.jsx"));
const UnbarcodedStockReport      = lazy(() => import("./components/manufacturing/reports/UnbarcodedStockReport.jsx"));
const FinishedItemRecReport      = lazy(() => import("./finishItemreceiveReport.jsx"));
const GstInputRegister           = lazy(() => import("./GstInputRegister.jsx"));
const GstOutputRegister          = lazy(() => import("./GstOutputRegister.jsx"));
const BarcodeSplitRepot          = lazy(() => import("./BarcodeSplitReport.jsx"));
const BarcodeMergeReport         = lazy(() => import("./BarcodeMergeReport.jsx"));
const ItemWiseBarcodeReport      = lazy(() => import("./ItemWiseBarcodeReport.jsx"));
const IssueToRefinary            = lazy(() => import("./components/manufacturing/issue/IssueToRefinary.jsx"));
const ReceiveFromRefinary        = lazy(() => import("./components/manufacturing/receive/ReceiveFromRefinary.jsx"));
const RetToRetstockTransfer      = lazy(() => import("./StockTrans.jsx"));
const StockJournal               = lazy(() => import("./StockJournal.jsx"));
const StockJournalList           = lazy(() => import("./StockJournalList.jsx"));
const JoborderReport             = lazy(() => import("./jobOrderReport.jsx"));
const StoneReturnAdd             = lazy(() => import("./components/manufacturing/receive/stoneReturnList.jsx"));
const Account                    = lazy(() => import("./components/FinancialAccounting/vouchers/account.jsx"));
const KarigarGoldIssuesList      = lazy(() => import("./components/manufacturing/issue/KarigarGoldIssuesList.jsx"));
const KarigarStoneIssueList      = lazy(() => import("./components/manufacturing/issue/karigarStoneIssuesList.jsx"));
const RefinaryIssueList          = lazy(() => import("./components/manufacturing/issue/RefinaryIssueList.jsx"));
const RefinaryReceiveList        = lazy(() => import("./components/manufacturing/receive/refinaryReceiveList.jsx"));
const MeltingIssueList           = lazy(() => import("./components/manufacturing/issue/MeltingIssueList.jsx"));
const MeltingReceiveList         = lazy(() => import("./components/manufacturing/receive/meltingReceiveList.jsx"));
const AssayIssueList             = lazy(() => import("./components/manufacturing/issue/AssayIssueList.jsx"));
const AssayReceiveList           = lazy(() => import("./components/manufacturing/receive/assayReceiveList.jsx"));
const IssueToMelting             = lazy(() => import("./components/manufacturing/issue/IssueToMelting.jsx"));
const ReceiveFromMelting         = lazy(() => import("./components/manufacturing/receive/ReceiveFromMelting.jsx"));
const IssueToAssay               = lazy(() => import("./components/manufacturing/issue/IssueToAssay.jsx"));
const ReceiveFromAssay           = lazy(() => import("./components/manufacturing/receive/ReceiveFromAssay.jsx"));
const StockTransferList          = lazy(() => import("./StockTransferList.jsx"));
const AccountingVoucherList      = lazy(() => import("./accountingVoucherList.jsx"));
const VoucherTypeSelector        = lazy(() => import("./components/FinancialAccounting/vouchers/VoucherTypeSelector"));
const LedgerStatement            = lazy(() => import("./components/FinancialAccounting/reports/LedgerStatement"));
const DayBook                    = lazy(() => import("./components/FinancialAccounting/reports/DayBook"));
const OutstandingReport          = lazy(() => import("./components/FinancialAccounting/reports/OutstandingReport"));
const AgedReceivables            = lazy(() => import("./components/FinancialAccounting/reports/AgedReceivables"));
const AdvanceRegister            = lazy(() => import("./components/FinancialAccounting/reports/AdvanceRegister"));
const UnallocatedVouchers        = lazy(() => import("./components/FinancialAccounting/UnallocatedVouchers"));
const CreditDebitNoteList        = lazy(() => import("./components/FinancialAccounting/CreditDebitNoteList"));
const CreditDebitNoteAdd         = lazy(() => import("./components/FinancialAccounting/CreditDebitNoteAdd"));
const BankReconciliation         = lazy(() => import("./components/FinancialAccounting/BankReconciliation"));
const BarcodeHistoryList         = lazy(() => import("./components/Inventory/BarcodeManagement/BarcodeHistoryList.jsx"));
const GoldRateForm               = lazy(() => import("./components/GoldRates/goldrate.jsx"));
const SalesEstimate              = lazy(() => import("./components/Sales/SalesEstimate.jsx"));
const QuotationAdd               = lazy(() => import("./components/Sales/QuotationAdd"));
const QuotationList              = lazy(() => import("./components/Sales/QuotationList"));
const ForbiddenPage              = lazy(() => import("./Forbidden.jsx"));
const ProfitLoss                 = lazy(() => import("./ProfitLoss/ProfitLoss.jsx"));
const ProfitLossCal              = lazy(() => import("./ProfitLoss/ProfitLossCal.jsx"));
const BalanceSheet               = lazy(() => import("./components/FinancialAccounting/reports/BalanceSheet.jsx"));
const FinancialRatios            = lazy(() => import("./components/FinancialAccounting/reports/FinancialRatios.jsx"));
const AuditQueue                 = lazy(() => import("./components/FinancialAccounting/reports/AuditQueue.jsx"));
const TrialBalance               = lazy(() => import("./trialBalance.jsx"));
const ClosingStockTable          = lazy(() => import("./components/Inventory/closingStockReport.jsx"));
const InterRetailTransferList    = lazy(() => import("./components/inventory/transfers/InterRetailTransferList.jsx"));
const InterRetailTransferAdd     = lazy(() => import("./components/inventory/transfers/InterRetailTransferAdd.jsx"));
const InterRetailTransferDetail  = lazy(() => import("./components/inventory/transfers/InterRetailTransferDetail.jsx"));
const OpeningStockList           = lazy(() => import("./components/Inventory/OpeningStock/OpeningStockList.jsx"));
const OpeningStockForm           = lazy(() => import("./components/Inventory/OpeningStock/OpeningStockForm.jsx"));
const HallmarkIssueReport        = lazy(() => import("./hallmarkissuereport.jsx"));
const HallmarkReceiveReport      = lazy(() => import("./hallmarkreceivereport.jsx"));
const Metalreport                = lazy(() => import("./Metalreport.jsx"));
const StockValueReport           = lazy(() => import("./stockValueReport.jsx"));
const CashBookRetail             = lazy(() => import("./cashBookRetail.jsx"));
const CombinedBankBook           = lazy(() => import("./combinedBankBook.jsx"));
const BarcodeStockReport         = lazy(() => import("./components/Inventory/BarcodeManagement/barcodeStockReport.jsx"));
const StoneWorkOrderReport       = lazy(() => import("./components/manufacturing/stoneissuereceivereport.jsx"));
const PacketWiseStoneReport      = lazy(() => import("./components/manufacturing/PacketWiseStoneReport.jsx"));
const ImportDataPage             = lazy(() => import("./components/MasterImport/ImportDataPage.jsx"));
const OpeningBalance             = lazy(() => import("./OpeningBalance.jsx"));
const SalesPersonList            = lazy(() => import("./components/Sales/SalesPersonList.jsx"));
const ItemGroupMaster            = lazy(() => import("./components/Masters/ItemGroupMaster.jsx"));
const PacketGroupMaster          = lazy(() => import("./components/Masters/PacketGroupMaster.jsx"));
const HsnMaster                  = lazy(() => import("./components/Masters/HsnMaster.jsx"));
const ItemMaster                 = lazy(() => import("./components/Masters/ItemMaster.jsx"));
const PacketMaster               = lazy(() => import("./components/Masters/PacketMaster.jsx"));
const FiscalYearManager          = lazy(() => import("./components/Masters/FiscalYearManager.jsx"));
const RetailMasterPage           = lazy(() => import("./components/Masters/RetailMasterPage.jsx"));
const BranchMasterPage           = lazy(() => import("./components/Masters/BranchMasterPage.jsx"));
const CompanyMasterPage          = lazy(() => import("./components/Masters/CompanyMasterPage.jsx"));
const BranchAnalytics            = lazy(() => import("./components/Masters/BranchAnalytics.jsx"));
const RetailAnalytics            = lazy(() => import("./components/Masters/RetailAnalytics.jsx"));
const KarigarMakingPage          = lazy(() => import("./components/Masters/KarigarMakingPage.jsx"));
const ExhibitionMaster           = lazy(() => import("./components/Masters/ExhibitionMaster.jsx"));
const TDSSectionMasterPage       = lazy(() => import("./components/Masters/TDSSectionMaster.jsx"));
const TCSSectionMasterPage       = lazy(() => import("./components/Masters/TCSSectionMaster.jsx"));
const PurityMasterPage           = lazy(() => import("./components/Masters/PurityMasterPage.jsx"));
const ShapeMasterPage            = lazy(() => import("./components/Masters/ShapeMasterPage.jsx"));
const ColorMasterPage            = lazy(() => import("./components/Masters/ColorMasterPage.jsx"));
const TDSRegister                = lazy(() => import("./components/reports/TDSRegister.jsx"));
const TCSRegister                = lazy(() => import("./components/reports/TCSRegister.jsx"));
const CommissionReport           = lazy(() => import("./components/reports/CommissionReport.jsx"));
const SalesRegister              = lazy(() => import("./components/reports/SalesRegister.jsx"));
const SaleApprovalRegister       = lazy(() => import("./components/reports/SaleApprovalRegister.jsx"));
const B2BPricelistPage           = lazy(() => import("./components/Masters/B2BPricelistPage.jsx"));
const RetailDiscountPricelistPage = lazy(() => import("./components/Masters/RetailDiscountPricelistPage.jsx"));
const SalesOfferPage             = lazy(() => import("./components/Masters/SalesOfferPage.jsx"));
const KarigarJobWorkReport       = lazy(() => import("./components/reports/KarigarJobWorkReport.jsx"));
const RefineryReport             = lazy(() => import("./components/reports/RefineryReport.jsx"));
const CRMDashboard               = lazy(() => import("./components/CRM/CRMDashboard.jsx"));
const GSTR1Report                = lazy(() => import("./components/reports/GSTR1Report.jsx"));
const GSTR3BReport               = lazy(() => import("./components/reports/GSTR3BReport.jsx"));
const GoldLedgerBalances         = lazy(() => import("./components/Reports/GoldLedgerBalances.jsx"));
const UserManagement             = lazy(() => import("./components/Settings/UserManagement.jsx"));
const RoleManagement             = lazy(() => import("./components/Settings/RoleManagement.jsx"));
const AuditLog                   = lazy(() => import("./components/Settings/AuditLog.jsx"));
const CRMAutomation              = lazy(() => import("./components/Settings/CRMAutomation.jsx"));
const Dashboard                  = lazy(() => import("./components/Dashboard/Dashboard.jsx"));
const BarcodeBulkOps             = lazy(() => import("./components/Inventory/BarcodeManagement/BarcodeBulkOps.jsx"));
const RawMaterialBalanceReport   = lazy(() => import("./components/Inventory/RawMaterialBalanceReport.jsx"));
const RawMaterialLedger          = lazy(() => import("./components/Inventory/RawMaterialLedger.jsx"));
const RawMaterialTransactionsList = lazy(() => import("./components/Inventory/RawMaterialTransactionsList.jsx"));
const SemiFinishedStockReport    = lazy(() => import("./components/Inventory/SemiFinishedStockReport.jsx"));
const SetupWizard                = lazy(() => import("./components/Settings/SetupWizard.jsx"));
const SettingsPage               = lazy(() => import("./components/Settings/SettingsPage.jsx"));
const SectionIndexPage           = lazy(() => import("./components/SectionIndexPage.jsx"));
const RepairJobCardList          = lazy(() => import("./components/manufacturing/repair/RepairJobCardList.jsx"));
const RepairJobCardForm          = lazy(() => import("./components/manufacturing/repair/RepairJobCardForm.jsx"));
const AppsPage                   = lazy(() => import("./components/Apps/AppsPage.jsx"));
const CustomerPurchaseHistory    = lazy(() => import("./components/CRM/CustomerPurchaseHistory.jsx"));
const GSTR2BReconcile            = lazy(() => import("./components/purchase/GSTR2BReconcile.jsx"));
const RfidTagAssign              = lazy(() => import("./components/Inventory/RFID/RfidTagAssign.jsx"));
const RfidInventoryCount         = lazy(() => import("./components/Inventory/RFID/RfidInventoryCount.jsx"));
const CarryForwardPage           = lazy(() => import("./components/Settings/CarryForwardPage.jsx"));
const VendorDashboard            = lazy(() => import("./components/VendorAnalytics/VendorDashboard.jsx"));
const StockAgeingReport          = lazy(() => import("./components/VendorAnalytics/reports/StockAgeingReport.jsx"));
const DesignPerformanceReport    = lazy(() => import("./components/VendorAnalytics/reports/DesignPerformanceReport.jsx"));
const InventoryTurnoverReport    = lazy(() => import("./components/VendorAnalytics/reports/InventoryTurnoverReport.jsx"));
const ItemPerformanceReport      = lazy(() => import("./components/VendorAnalytics/reports/ItemPerformanceReport.jsx"));
const VendorComparisonReport     = lazy(() => import("./components/VendorAnalytics/reports/VendorComparisonReport.jsx"));


// ── Lightweight route-transition spinner ──────────────────────────────────────
function PageSpinner() {
  return (
    <div className="flex h-screen w-full items-center justify-center">
      <div className="size-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  );
}


const isAuthenticate = () => !!sessionStorage.getItem("Token");
const hasBaseUrl = () => !!sessionStorage.getItem("baseUrl");
const isSetupComplete = () => sessionStorage.getItem("erpSetupComplete") === "true";

// Wrapper for protected routes
const ProtectedRoute = ({ element }) => {
  if (!hasBaseUrl()) {
    return <Navigate to="/config" />;
  }
  if (!isAuthenticate()) {
    return <Navigate to="/login" />;
  }
  // Force users into the setup wizard until first-run setup is finished
  const path = window.location.pathname;
  const isSetupRoute = path === "/settings/setup" || path.startsWith("/settings/setup");
  if (!isSetupComplete() && !isSetupRoute) {
    return <Navigate to="/settings/setup" replace />;
  }
  return element;
};


const appRoutes = [
  // Apps
  { path: "apps", heading: "Apps", component: <AppsPage /> },

  // ── CRM ───────────────────────────────────────────────────────────────────
  { path: "crm/ledger",     heading: "Ledger",      component: <Ledger /> },
  { path: "crm/ledger/add", heading: "Add Ledger",   component: <LedgerForm /> },
  { path: "crm/ledger/:id", heading: "Edit Ledger",  component: <LedgerForm /> },
  { path: "crm/occasions",  heading: "Customer Occasions", component: <CRMDashboard /> },
  { path: "crm/customer-history", heading: "Customer Purchase History", component: <CustomerPurchaseHistory /> },

  // ── Setup / Masters ───────────────────────────────────────────────────────
  { path: "setup/salesperson",   heading: "Sales Person",          component: <SalesPersonList /> },
  { path: "setup/karigar-making", heading: "Karigar Making Master", component: <KarigarMakingPage /> },
  { path: "setup/import-data",   heading: "Import Master Data",    component: <ImportDataPage /> },
  { path: "setup/company",       heading: "Company Master",        component: <CompanyMasterPage /> },
  { path: "setup/branch",        heading: "Branch Master",         component: <BranchMasterPage /> },
  { path: "setup/branch/:id/analytics", heading: "Branch Analytics", component: <BranchAnalytics /> },
  { path: "setup/retail/:id/analytics", heading: "Retail Analytics", component: <RetailAnalytics /> },
  { path: "setup/retail",        heading: "Retail Master",         component: <RetailMasterPage /> },
  { path: "setup/exhibitions",   heading: "Exhibition Profiles",   component: <ExhibitionMaster /> },
  { path: "setup/fiscal-years",  heading: "Fiscal Year Management", component: <FiscalYearManager /> },
  { path: "setup/hsn",           heading: "HSN Master",            component: <HsnMaster /> },
  { path: "setup/item-group",    heading: "Item Group Master",     component: <ItemGroupMaster /> },
  { path: "setup/item",          heading: "Item Master",           component: <ItemMaster /> },
  { path: "setup/packet-group",  heading: "Packet Group Master",   component: <PacketGroupMaster /> },
  { path: "setup/packet",        heading: "Packet Master",         component: <PacketMaster /> },
  { path: "setup/purity",        heading: "Purity Master",         component: <PurityMasterPage /> },
  { path: "setup/shape",         heading: "Shape Master",          component: <ShapeMasterPage /> },
  { path: "setup/color",         heading: "Color Master",          component: <ColorMasterPage /> },
  { path: "setup/tds-section",   heading: "TDS Section Master",    component: <TDSSectionMasterPage /> },
  { path: "setup/tcs-section",   heading: "TCS Section Master",    component: <TCSSectionMasterPage /> },
  { path: "setup/b2b-pricelist",              heading: "B2B Sale Pricelist",                component: <B2BPricelistPage /> },
  { path: "setup/retail-discount-pricelist", heading: "Retail Discount Pricelist",     component: <RetailDiscountPricelistPage /> },
  { path: "setup/sales-offer",              heading: "Sales Offers",                   component: <SalesOfferPage /> },

  // ── Financial Accounting ──────────────────────────────────────────────────
  { path: "accounting/vouchers/select",           heading: "New Voucher Entry",        component: <VoucherTypeSelector /> },
  { path: "accounting/opening-balance",           heading: "Opening Balances",         component: <OpeningBalance /> },
  { path: "accounting/account-tree",              heading: "Account Tree",             component: <AccountTree /> },
  { path: "accounting/account-create",            heading: "Add Account Group",        component: <AccountCreationForm /> },
  { path: "accounting/account-edit/:id",          heading: "Edit Account Group",       component: <AccountCreationForm /> },
  { path: "accounting/:journal_type/add", heading: "Add Journal",             component: <AddJournal /> },
  { path: "accounting/:journal_type/:id", heading: "Edit Journal",            component: <AddJournal /> },
  { path: "accounting/:journal_type",     heading: "Accounting Voucher List", component: <AccountingVoucherList /> },
  { path: "accounting/cashgoldconversion",        heading: "Cash Gold Conversion",     component: <CashGoldConversion /> },
  { path: "accounting/ledger-statement",          heading: "Ledger Account Statement", component: <LedgerStatement /> },
  { path: "accounting/outstanding",               heading: "Outstanding Report",       component: <OutstandingReport /> },
  { path: "accounting/aged-receivables",          heading: "Aged Receivables / Payables", component: <AgedReceivables /> },
  { path: "accounting/advance-register",          heading: "Advance Register",         component: <AdvanceRegister /> },
  { path: "accounting/unallocated-vouchers",      heading: "Unallocated Vouchers",     component: <UnallocatedVouchers /> },
  { path: "accounting/credit-debit-notes",         heading: "Credit / Debit Notes",     component: <CreditDebitNoteList /> },
  { path: "accounting/credit-debit-notes/add",     heading: "New Credit / Debit Note",  component: <CreditDebitNoteAdd /> },
  { path: "accounting/credit-debit-notes/:id",     heading: "Credit / Debit Note",      component: <CreditDebitNoteAdd /> },
  { path: "accounting/day-book",                  heading: "Day Book",                 component: <DayBook /> },
  { path: "accounting/bank-reconciliation",       heading: "Bank Reconciliation",      component: <BankReconciliation /> },
  { path: "accounting/trialbalance",              heading: "Trial Balance",            component: <TrialBalance /> },
  { path: "accounting/cashbook",                  heading: "Cash Book",                component: <CashBookRetail /> },
  { path: "accounting/bankbook",                  heading: "Bank Book",                component: <CombinedBankBook /> },
  { path: "accounting/balancesheet",              heading: "Balance Sheet",            component: <BalanceSheet /> },
  { path: "accounting/profitloss",                heading: "Profit & Loss",            component: <ProfitLoss /> },
  { path: "accounting/profitlosscal",             heading: "Profit Loss Calculation",  component: <ProfitLossCal /> },
  { path: "accounting/gstinputregister",          heading: "GST Input Register",       component: <GstInputRegister /> },
  { path: "accounting/gstoutputregister",         heading: "GST Output Register",      component: <GstOutputRegister /> },
  { path: "accounting/audit-queue",               heading: "Audit Queue",              component: <AuditQueue /> },
  { path: "accounting/reports/financial-ratios",   heading: "Financial Ratios",         component: <FinancialRatios /> },
  { path: "accounting/reports/gold-ledger-balances", heading: "Gold Ledger Balances",  component: <GoldLedgerBalances /> },
  { path: "accounting/reports/gstr1",             heading: "GSTR-1",                   component: <GSTR1Report /> },
  { path: "accounting/reports/gstr3b",            heading: "GSTR-3B",                  component: <GSTR3BReport /> },
  { path: "accounting/reports/tds-register",      heading: "TDS Register",             component: <TDSRegister /> },
  { path: "accounting/reports/tcs-register",      heading: "TCS Register",             component: <TCSRegister /> },

  // ── Manufacturing ─────────────────────────────────────────────────────────
  { path: "manufacturing/issue/jobwork/add",  heading: "Add Karigar Issue",   component: <KarigarIssue /> },
  { path: "manufacturing/issue/jobwork/:id",  heading: "Edit Karigar Issue",  component: <KarigarIssue /> },
  { path: "manufacturing/issue/jobwork",      heading: "Karigar Issue List",  component: <KarigarJobs /> },
  { path: "manufacturing/issue/sample-issue/new", heading: "New Sample Issue",  component: <SampleIssue /> },
  { path: "manufacturing/issue/sample-issue/:id", heading: "Edit Sample Issue", component: <SampleIssue /> },
  { path: "manufacturing/issue/sample-issue",     heading: "Sample Issue List", component: <SampleIssueList /> },
  { path: "manufacturing/issue/stoneissue/add", heading: "Stone Issue to Karigar",  component: <KarigarStoneIssue /> },
  { path: "manufacturing/issue/stoneissue/:id", heading: "Edit Stone Issue",        component: <KarigarStoneIssue /> },
  { path: "manufacturing/issue/stoneissue/",  heading: "Stone Issue List",          component: <KarigarStoneIssueList /> },
  { path: "manufacturing/issue/goldissue/add", heading: "Gold Issue to Karigar",   component: <GoldIssue /> },
  { path: "manufacturing/issue/goldissue/:id", heading: "Edit Gold Issue",         component: <GoldIssue /> },
  { path: "manufacturing/issue/goldissue",    heading: "Gold Issue List",           component: <KarigarGoldIssuesList /> },
  { path: "manufacturing/issue/hallmarkissue/add", heading: "Add Hallmark Issue",  component: <HallmarkIssue /> },
  { path: "manufacturing/issue/hallmarkissue/:id", heading: "Edit Hallmark Issue", component: <HallmarkIssue /> },
  { path: "manufacturing/issue/hallmarkissue/",    heading: "Hallmark Issue",      component: <HallmarkIssueAdd /> },
  { path: "manufacturing/issue/refinary/add", heading: "Issue To Refinery",        component: <IssueToRefinary /> },
  { path: "manufacturing/issue/refinary/:id", heading: "Edit Issue To Refinery",   component: <IssueToRefinary /> },
  { path: "manufacturing/issue/refinary/",    heading: "Refinery Issue List",      component: <RefinaryIssueList /> },
  { path: "manufacturing/issue/melting/add",  heading: "Issue To Melting",         component: <IssueToMelting /> },
  { path: "manufacturing/issue/melting/:id",  heading: "Edit Issue To Melting",    component: <IssueToMelting /> },
  { path: "manufacturing/issue/melting/",     heading: "Melting Issue List",       component: <MeltingIssueList /> },
  { path: "manufacturing/issue/assay/add",    heading: "Issue To Assay",           component: <IssueToAssay /> },
  { path: "manufacturing/issue/assay/:id",    heading: "Edit Issue To Assay",      component: <IssueToAssay /> },
  { path: "manufacturing/issue/assay/",       heading: "Assay Issue List",         component: <AssayIssueList /> },
  { path: "manufacturing/receive/jobworkreceive/",    heading: "Receive From Karigar",     component: <KarigarReceiveList /> },
  { path: "manufacturing/receive/jobworkreceive/add", heading: "Add Receive From Karigar", component: <JobWorkReceive /> },
  { path: "manufacturing/receive/jobworkreceive/:id", heading: "Edit Receive From Karigar", component: <JobWorkReceive /> },
  { path: "manufacturing/receive/stonereturn/add", heading: "Stone Return Add",     component: <StoneReturn /> },
  { path: "manufacturing/receive/stonereturn/:id", heading: "Edit Stone Return",    component: <StoneReturn /> },
  { path: "manufacturing/receive/stonereturn/",    heading: "Stone Return List",    component: <StoneReturnAdd /> },
  { path: "manufacturing/receive/hallmarkreceive/",    heading: "Hallmark Receive",     component: <HallmarkReceiveAdd /> },
  { path: "manufacturing/receive/hallmarkreceive/add", heading: "Add Hallmark Receive", component: <HallmarkReceive /> },
  { path: "manufacturing/receive/hallmarkreceive/:id", heading: "Edit Hallmark Receive", component: <HallmarkReceive /> },
  { path: "manufacturing/receive/refinary/add", heading: "Add Refinery Receive",   component: <ReceiveFromRefinary /> },
  { path: "manufacturing/receive/refinary/:id", heading: "Edit Refinery Receive",  component: <ReceiveFromRefinary /> },
  { path: "manufacturing/receive/refinary/",    heading: "Refinery Receive List",  component: <RefinaryReceiveList /> },
  { path: "manufacturing/receive/melting/add",  heading: "Add Melting Receive",    component: <ReceiveFromMelting /> },
  { path: "manufacturing/receive/melting/:id",  heading: "Edit Melting Receive",   component: <ReceiveFromMelting /> },
  { path: "manufacturing/receive/melting/",     heading: "Melting Receive List",   component: <MeltingReceiveList /> },
  { path: "manufacturing/receive/assay/add",    heading: "Add Assay Receive",      component: <ReceiveFromAssay /> },
  { path: "manufacturing/receive/assay/:id",    heading: "Edit Assay Receive",     component: <ReceiveFromAssay /> },
  { path: "manufacturing/receive/assay/",       heading: "Assay Receive List",     component: <AssayReceiveList /> },
  { path: "manufacturing/repair/list/",  heading: "Repair Job Cards",      component: <RepairJobCardList /> },
  { path: "manufacturing/repair/new",    heading: "New Repair Job Card",   component: <RepairJobCardForm /> },
  { path: "manufacturing/repair/:id",    heading: "Edit Repair Job Card",  component: <RepairJobCardForm /> },
  { path: "manufacturing/reports/karigarstonetxns",  heading: "Karigar Stone Transactions",       component: <KarigarStoneTransactions /> },
  { path: "manufacturing/reports/hallmarkreceive",   heading: "Hallmark Receive Report",          component: <HallmarkReceiveReport /> },
  { path: "manufacturing/reports/hmissue",           heading: "Hallmark Issue Report",            component: <HallmarkIssueReport /> },
  { path: "manufacturing/reports/finisheditemrec",   heading: "Finished Item Receive Report",     component: <FinishedItemRecReport /> },
  { path: "manufacturing/reports/joborder",          heading: "Job Order Report",                 component: <JoborderReport /> },
  { path: "manufacturing/reports/karigar-jobwork",   heading: "Karigar Job Work Report",          component: <KarigarJobWorkReport /> },
  { path: "manufacturing/reports/refinery",          heading: "Refinery Report",                  component: <RefineryReport /> },
  { path: "manufacturing/reports/unbarcoded-stock",  heading: "Unbarcoded Stock Report",          component: <UnbarcodedStockReport /> },

  // ── Purchases ─────────────────────────────────────────────────────────────
  { path: "purchase/list/",                        heading: "Purchase Voucher List",  component: <PurchaseVoucherList /> },
  { path: "purchase/add/",                         heading: "Add Purchase Voucher",   component: <PurchaseVoucher /> },
  { path: "purchase/:id",                          heading: "Edit Purchase Voucher",  component: <PurchaseVoucher /> },
  // Legacy aliases — kept for backward compatibility
  { path: "purchase/purchasevoucher/list/",        heading: "Purchase Voucher List",  component: <PurchaseVoucherList /> },
  { path: "purchase/purchasevoucher/list/add/",    heading: "Add Purchase Voucher",   component: <PurchaseVoucher /> },
  { path: "purchase/purchasevoucher/list/:id",     heading: "Edit Purchase Voucher",  component: <PurchaseVoucher /> },
  { path: "purchase/add-purchase-voucher/add",    heading: "Add Purchase Voucher",   component: <PurchaseVoucher /> },
  { path: "purchase/add-purchase-voucher/:id",    heading: "Edit Purchase Voucher",  component: <PurchaseVoucher /> },
  { path: "purchase/add-rawpurchase-voucher/add", heading: "Add Purchase Voucher",   component: <PurchaseVoucher /> },
  { path: "purchase/purchasereturn/list/",        heading: "Purchase Return List",   component: <PurchaseReturnList /> },
  { path: "purchase/purchasereturn/list/add/",    heading: "Add Purchase Return",    component: <PurchaseReturnadd /> },
  { path: "purchase/purchasereturn/list/:id",     heading: "Edit Purchase Return",   component: <PurchaseReturnadd /> },
  { path: "purchase/purchaseapproval/list/",      heading: "Purchase Approval List", component: <PurchaseApprovalList /> },
  { path: "purchase/purchaseorder/list/",         heading: "Purchase Order List",    component: <PurchaseOrderList /> },
  { path: "purchase/purchaseorder/list/add",      heading: "Add Purchase Order",     component: <PurchaseOrder /> },
  { path: "purchase/purchaseorder/list/:id",      heading: "Edit Purchase Order",    component: <PurchaseOrder /> },
  { path: "purchase/gstr2b-reconcile",            heading: "GSTR-2B Reconciliation", component: <GSTR2BReconcile /> },
  { path: "purchase/customerpurchase/list/",      heading: "Customer Purchase List", component: <PurchaseVoucherList voucherType="Customer" /> },
  { path: "inventory/reports/stock-matching",      heading: "Stock Matching Report",  component: <StockMatchingReport /> },
  { path: "purchase/customerpurchase/list/add/",  heading: "Add Customer Purchase",  component: <PurchaseVoucher /> },
  { path: "purchase/customerpurchase/list/:id",   heading: "Edit Customer Purchase", component: <PurchaseVoucher /> },

  // ── Sales ─────────────────────────────────────────────────────────────────
  { path: "sales/estimate",                heading: "Sales Estimate",       component: <SalesEstimate /> },
  { path: "sales/quotation/list/",         heading: "Quotation List",       component: <QuotationList /> },
  { path: "sales/quotation/add/",          heading: "New Quotation",        component: <QuotationAdd /> },
  { path: "sales/quotation/:id",           heading: "Edit Quotation",       component: <QuotationAdd /> },
  { path: "sales/customerorder/list/",     heading: "Customer Order List",  component: <CustomerOrderList /> },
  { path: "sales/customerorder/kanban/",   heading: "Customer Order Kanban", component: <CustomerOrderKanban /> },
  { path: "sales/customerorder/tracker/",  heading: "Customer Order Tracker", component: <CustomerOrderTracker /> },
  { path: "sales/customerorder/list/add/", heading: "Add Customer Order",   component: <CustomerOrderForm /> },
  { path: "sales/customerorder/list/:id",  heading: "Edit Customer Order",  component: <CustomerOrderForm /> },
  { path: "sales/list/",                   heading: "Sales Voucher List",   component: <SalesVoucherList /> },
  { path: "sales/add/",                    heading: "Add Sales Voucher",    component: <SalesVoucherAdd /> },
  { path: "sales/:id",                     heading: "Edit Sales Voucher",   component: <SalesVoucherAdd /> },
  { path: "sales/rawsalesvoucher/add/",    heading: "Add Sales Voucher",    component: <SalesVoucherAdd /> },
  { path: "sales/salesreturn/list/",       heading: "Sales Return List",    component: <SalesReturnList /> },
  { path: "sales/salesreturn/add/",        heading: "Add Sales Return",     component: <SalesReturnAdd /> },
  { path: "sales/salesreturn/:id",         heading: "Edit Sales Return",    component: <SalesReturnAdd /> },
  { path: "sales/salesapproval",           heading: null,                   component: <Navigate to="/sales/salesapproval/list/" replace /> },
  { path: "sales/salesapproval/list/",     heading: "Sales Approval List",  component: <SalesApprovalList /> },
  { path: "sales/salesapproval/add/",      heading: "Add Sales Approval",   component: <SalesApprovalAdd /> },
  { path: "sales/salesapproval/:id",       heading: "Edit Sales Approval",  component: <SalesApprovalAdd /> },
  { path: "sales/reports/commission",      heading: "Salesperson Commission Report", component: <CommissionReport /> },
  { path: "sales/reports/sales-register",  heading: "Sales Register",                 component: <SalesRegister /> },
  { path: "sales/reports/sale-approval-register", heading: "Sale Approval Register",  component: <SaleApprovalRegister /> },
  { path: "sales/eway-bills",              heading: "E-Way Bills",          component: <EWayBillList /> },
  { path: "sales/pending-cheques",         heading: "Pending Cheques",      component: <ChequePendingPage /> },

  // ── Inventory ─────────────────────────────────────────────────────────────
  { path: "inventory/barcodemanagement/list/",      heading: "Barcode List",           component: <BarcodeListView /> },
  { path: "inventory/barcodemanagement/list/add/",  heading: "Create Barcode",         component: <BarcodeManagementList /> },
  { path: "inventory/barcodemanagement/list/:id",   heading: "Edit Barcode",           component: <BarcodeManagementList /> },
  { path: "inventory/barcodemanagement/split/",     heading: "Split Barcode",          component: <BarcodeSplit /> },
  { path: "inventory/barcodemanagement/merge/",     heading: "Merge Barcode",          component: <MergeBarcode /> },
  { path: "inventory/barcodemanagement/barcodehistory/", heading: "Barcode History",   component: <BarcodeHistoryList /> },
  { path: "inventory/barcode-print",                heading: "Print Barcode Labels",   component: <BarcodePrint /> },
  { path: "inventory/barcode-bulk",                 heading: "Barcode Bulk Operations", component: <BarcodeBulkOps /> },
  { path: "inventory/stocktransfer",                heading: "Stock Transfer List",    component: <StockTransferList /> },
  { path: "inventory/stocktransfer/add",            heading: "Add Stock Transfer",     component: <RetToRetstockTransfer /> },
  { path: "inventory/stocktransfer/:id",            heading: "Edit Stock Transfer",    component: <RetToRetstockTransfer /> },
  { path: "inventory/inter-retail-transfer",            heading: "Inter-Retail Transfers",    component: <InterRetailTransferList /> },
  { path: "inventory/inter-retail-transfer/new",        heading: "New Inter-Retail Transfer", component: <InterRetailTransferAdd /> },
  { path: "inventory/inter-retail-transfer/:id/edit",   heading: "Edit Inter-Retail Transfer", component: <InterRetailTransferAdd /> },
  { path: "inventory/inter-retail-transfer/:id",        heading: "Inter-Retail Transfer",     component: <InterRetailTransferDetail /> },
  { path: "inventory/opening-stock",                    heading: "Opening Stock",             component: <OpeningStockList /> },
  { path: "inventory/opening-stock/add",                heading: "Add Opening Stock",         component: <OpeningStockForm /> },
  { path: "inventory/opening-stock/:id/edit",           heading: "Edit Opening Stock",        component: <OpeningStockForm /> },
  { path: "inventory/stockjournal/",                heading: "Stock Journal List",     component: <StockJournalList /> },
  { path: "inventory/stockjournal/add",             heading: "Add Stock Journal",      component: <StockJournal /> },
  { path: "inventory/stockjournal/:id",             heading: "Edit Stock Journal",     component: <StockJournal /> },
  { path: "inventory/design/list/",                 heading: "Design List",            component: <DesignList /> },
  { path: "inventory/reports/idgen",                heading: "ID Generation Report",   component: <IdGenerationReport /> },
  { path: "inventory/reports/metalreport",          heading: "Metal Report",           component: <Metalreport /> },
  { path: "inventory/reports/packetwisestone",      heading: "Packet Wise Stone Report", component: <PacketWiseStoneReport /> },
  { path: "inventory/reports/stoneissuereceive",    heading: "Stone Work Order Report", component: <StoneWorkOrderReport /> },
  { path: "inventory/reports/closing-stock",        heading: "Closing Stock",          component: <ClosingStockTable /> },
  { path: "inventory/reports/barcodesplit",         heading: "Barcode Split Report",   component: <BarcodeSplitRepot /> },
  { path: "inventory/reports/barcodemerge",         heading: "Barcode Merge Report",   component: <BarcodeMergeReport /> },
  { path: "inventory/reports/itemwisebarcode",      heading: "Item Wise Barcode Report", component: <ItemWiseBarcodeReport /> },
  { path: "inventory/reports/barcodestockreport",   heading: "Barcode Stock Report",   component: <BarcodeStockReport /> },
  { path: "inventory/reports/stockvalue",           heading: "Stock Value Report",     component: <StockValueReport /> },
  { path: "inventory/reports/raw-material",              heading: "Raw Material Balance",       component: <RawMaterialBalanceReport /> },
  { path: "inventory/reports/raw-material-ledger",      heading: "Raw Material Ledger",        component: <RawMaterialLedger /> },
  { path: "inventory/reports/raw-material-transactions", heading: "Raw Material Transactions",  component: <RawMaterialTransactionsList /> },
  { path: "inventory/reports/semi-finished",        heading: "Semi-Finished Stock",    component: <SemiFinishedStockReport /> },
  { path: "inventory/rfid/tag-assign",              heading: "RFID Tag Assignment",    component: <RfidTagAssign /> },
  { path: "inventory/rfid/count",                   heading: "RFID Inventory Count",   component: <RfidInventoryCount /> },

  // ── Gold Schemes ──────────────────────────────────────────────────────────
  { path: "scheme/dashboard",                    heading: "Gold Scheme Dashboard",  component: <SchemeDashboard /> },
  { path: "scheme/master",                       heading: "Scheme Master",          component: <SchemeMasterPage /> },
  { path: "scheme/enrollments",                  heading: "Scheme Enrollments",     component: <SchemeEnrollmentList /> },
  { path: "scheme/enrollments/add",              heading: "New Enrollment",         component: <SchemeEnrollmentForm /> },
  { path: "scheme/enrollments/:id/pay",          heading: "Record Payment",         component: <SchemePaymentForm /> },
  { path: "scheme/enrollments/:id/statement",    heading: "Scheme Statement",       component: <SchemeStatement /> },

  // ── HR ────────────────────────────────────────────────────────────────────
  { path: "hr/employees",         heading: "Employee Master",      component: <EmployeeMasterPage /> },
  { path: "hr/salary-structure",  heading: "Salary Structure",     component: <SalaryStructurePage /> },
  { path: "hr/salary-processing", heading: "Salary Processing",    component: <SalaryProcessingPage /> },
  { path: "hr/settings",          heading: "HR Settings",          component: <HRSettingsPage /> },
  { path: "hr",                   heading: "Human Resources",      component: <SectionIndexPage /> },

  // ── Fixed Assets ─────────────────────────────────────────────────────────
  { path: "fixed-assets/master",       heading: "Fixed Asset Master",       component: <FixedAssetMasterPage /> },
  { path: "fixed-assets/depreciation", heading: "Depreciation Worksheet",   component: <DepreciationWorksheetPage /> },
  { path: "fixed-assets/settings",     heading: "Fixed Asset Settings",     component: <FixedAssetSettingsPage /> },
  { path: "fixed-assets",              heading: "Fixed Assets",             component: <SectionIndexPage /> },

  // ── Gold Rates ────────────────────────────────────────────────────────────
  { path: "goldrate/form", heading: "Update Gold Rate", component: <GoldRateForm /> },

  // ── AI ────────────────────────────────────────────────────────────────────
  // (routes defined elsewhere if needed)

  // ── Settings ──────────────────────────────────────────────────────────────
  { path: "settings",                heading: "Settings",            component: <SettingsPage /> },
  { path: "settings/setup",         heading: "ERP Setup Wizard",    component: <SetupWizard /> },
  { path: "settings/user-management", heading: "User Management",   component: <UserManagement /> },
  { path: "settings/roles",         heading: "Roles & Permissions", component: <RoleManagement /> },
  { path: "settings/audit-log",     heading: "Audit Log",           component: <AuditLog /> },
  { path: "settings/crm-automation", heading: "CRM Automation",     component: <CRMAutomation /> },
  { path: "settings/carry-forward", heading: "Database Carry-Forward", component: <CarryForwardPage /> },

  // ── Section index pages (breadcrumb intermediates) ────────────────────────
  { path: "setup",                      heading: "Setup",                   component: <SectionIndexPage /> },
  { path: "crm",                        heading: "CRM",                     component: <SectionIndexPage /> },
  { path: "sales",                      heading: "Sales",                   component: <SectionIndexPage /> },
  { path: "purchase",                   heading: "Purchases",               component: <SectionIndexPage /> },
  { path: "manufacturing",             heading: "Manufacturing",            component: <SectionIndexPage /> },
  { path: "manufacturing/issue",       heading: "Manufacturing — Issue",    component: <SectionIndexPage /> },
  { path: "manufacturing/receive",     heading: "Manufacturing — Receive",  component: <SectionIndexPage /> },
  { path: "manufacturing/reports",     heading: "Manufacturing — Reports",  component: <SectionIndexPage /> },
  { path: "accounting",               heading: "Financial Accounting",      component: <SectionIndexPage /> },
  { path: "accounting/reports",        heading: "Accounting — Reports",     component: <SectionIndexPage /> },
  { path: "inventory",                heading: "Inventory",                 component: <SectionIndexPage /> },
  { path: "inventory/barcodemanagement", heading: "Barcode Management",     component: <SectionIndexPage /> },
  { path: "inventory/reports",         heading: "Inventory — Reports",      component: <SectionIndexPage /> },
  { path: "scheme",                   heading: "Gold Schemes",             component: <SectionIndexPage /> },

  // ── Breadcrumb redirect shims (intermediate paths with no own UI) ─────────
  { path: "sales/quotation",           heading: null, component: <Navigate to="/sales/quotation/list/" replace /> },
  { path: "sales/customerorder",       heading: null, component: <Navigate to="/sales/customerorder/list/" replace /> },
  { path: "sales/salesreturn",         heading: null, component: <Navigate to="/sales/salesreturn/list/" replace /> },
  { path: "accounting/vouchers",       heading: null, component: <Navigate to="/accounting/vouchers/select" replace /> },
  { path: "manufacturing/repair",      heading: null, component: <Navigate to="/manufacturing/repair/list/" replace /> },
  { path: "purchase/purchasevoucher",  heading: null, component: <Navigate to="/purchase/list/" replace /> },
  { path: "inventory/rfid",            heading: null, component: <Navigate to="/inventory/rfid/tag-assign" replace /> },

  // ── Vendor Analytics ─────────────────────────────────────────────────────
  { path: "vendor-analytics",                  heading: "Vendor Analytics",          component: <SectionIndexPage /> },
  { path: "vendor-analytics/dashboard",        heading: "Vendor Dashboard",          component: <VendorDashboard /> },
  { path: "vendor-analytics/stock-ageing",     heading: "Stock Ageing Report",       component: <StockAgeingReport /> },
  { path: "vendor-analytics/design-performance", heading: "Design Performance",      component: <DesignPerformanceReport /> },
  { path: "vendor-analytics/inventory-turnover", heading: "Inventory Turnover",      component: <InventoryTurnoverReport /> },
  { path: "vendor-analytics/item-performance", heading: "Item Performance",          component: <ItemPerformanceReport /> },
  { path: "vendor-analytics/vendor-comparison", heading: "Vendor Comparison",        component: <VendorComparisonReport /> },
];


function App() {
  return (
    <Suspense fallback={<PageSpinner />}>
      <Routes>
        {/* Base URL Configuration */}
        <Route path="/config" element={<BaseUrlConfig />} />

        {/* Protected root */}
        <Route path="/" element={<ProtectedRoute element={<Page />} />}>
          {/* Dashboard — index route */}
          <Route index element={<ProtectedRoute element={<Dashboard />} />} />
          {appRoutes.map(({ path, heading, component }) => (
            <Route
              key={path}
              path={path}
              element={
                <ProtectedRoute
                  element={heading ? <Header heading={heading}>{component}</Header> : component}
                />
              }
            />
          ))}
          {/* Catch-all: unknown paths inside the layout redirect to home instead of blank */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>

        {/* Bill selection popup (opens in new window from receipt/payment vouchers) */}
        <Route path="accountadd/:type/:id" element={<Account />} />

        {/* Public route */}
        <Route path="login" element={<LoginPage />} />
        {/* Forbidden page — rendered on 403 redirect from apiClient */}
        <Route path="forbidden" element={<ForbiddenPage />} />

        {/* Customer Portal (standalone, separate from ERP auth) */}
        <Route path="portal/*" element={<PortalApp />} />

        {/* HR Employee Portal (uses ERP Token auth — employees are Django Users) */}
        <Route path="hr-portal/*" element={<HRPortalApp />} />
      </Routes>
    </Suspense>
  );
}


export default App;
