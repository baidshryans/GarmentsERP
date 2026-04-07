import { Routes, Route, Navigate } from "react-router-dom";
import { Page } from "./dashboard";
import BaseUrlConfig from "./components/BaseUrlConfig";
import Ledger from "./ledger";
import LedgerForm from "./addLedger.jsx";
import AccountTree from "./chartOfAccouts";
import AccountCreationForm from "./AccountCreate";
import AddJournal from "./components/FinancialAccounting/vouchers/addJournal";
import CashGoldConversion from "./CashGoldConversion";
import KarigarIssue from "./components/manufacturing/issue/karigarissue";
import PurchaseVoucher from "./components/manufacturing/purchases/PurchaseVoucher";
import PurchaseOrder from "./components/manufacturing/purchases/purchaseOrder";
import PurchaseOrderList from "./components/manufacturing/purchases/purchaseOrderList";
import KarigarJobs from "./components/manufacturing/issue/jobWorkList.jsx";
import KarigarReceiveList from "./components/manufacturing/receive/jobWorkReceiveList";
import JobWorkReceive from "./components/manufacturing/receive/jobWorkReceive";
import StoneReturn, { } from "./components/manufacturing/receive/StoneReturn";
import KarigarStoneIssue from "./components/manufacturing/issue/stoneIssue";
import StoneIssue from "./components/manufacturing/issue/stoneIssue";
import GoldIssue from "./components/manufacturing/issue/goldIssue";
import HallmarkIssue from "./components/manufacturing/issue/hallmarkIssue";
import HallmarkReceive from "./components/manufacturing/receive/HallmarkReceive";
import BarcodeManagementList from "./components/Inventory/BarcodeManagement/barcodemanagementlist";
import BarcodePrint from "./components/Inventory/BarcodeManagement/BarcodePrint";
import MergeBarcode from "./components/Inventory/BarcodeManagement/barcodeMerge";
import BarcodeMergeView from "./components/Inventory/BarcodeManagement/barcodemergeList";
import DesignList from "./components/Inventory/DesignList";
import BarcodeListView from "./components/Inventory/BarcodeManagement/barcodeList";
import BarcodeSplit from "./components/Inventory/BarcodeManagement/barcodeSplit";
import BarcodeSplitView from "./components/Inventory/BarcodeManagement/barcodeSplitList";
import SalesVoucherAdd from "./components/Sales/SalesVoucherAdd";
import SalesReturnAdd from "./components/Sales/SalesReturnAdd";
import SalesApprovalAdd from "./components/Sales/SalesApprovalAdd";
import CustomerOrderList from "./components/Sales/CustomerOrderList";
import CustomerOrderKanban from "./components/Sales/CustomerOrderKanban";
import CustomerOrderForm from "./CustomerOrderForm";
import SalesVoucherList from "./components/Sales/SalesVoucherList";
import SalesApprovalList from "./components/Sales/SalesApprovalList";
import SalesReturnList from "./components/Sales/SalesReturnList";
import PurchaseReturnList from "./components/manufacturing/purchases/PurchaseReturnList";
import PurchaseApprovalList from "./components/manufacturing/purchases/PurchaseApprovalList.jsx";
import Header from "./breadCrumbDecor";
import NotFoundPage from "./pageNotFound";
import { LoginPage } from "./login"
import HallmarkIssueAdd from "./components/manufacturing/issue/hallmarkIssueAdd";
import HallmarkReceiveAdd from "./components/manufacturing/receive/hallmarkReceiveAdd";
import PurchaseReturnadd from "./components/manufacturing/purchases/PurchaseReturnAdd";
import PurchaseVoucherList from "./components/manufacturing/purchases/PurchaseVoucherList";

import IdGenerationReport from "./components/Inventory/BarcodeManagement/IdGenerationReport";
import HallmarkIssueReceiveReport from "./hallmarkIssAndRecReport.jsx";
import KrStoneIssueAndReceive from "./krStoneIssueAndReceive.jsx";
import FinishedItemRecReport from "./finishItemreceiveReport.jsx";
import GstInputRegister from "./GstInputRegister.jsx";
import GstOutputRegister from "./GstOutputRegister.jsx";
import BarcodeSplitRepot from "./BarcodeSplitReport.jsx";
import BarcodeMergeReport from "./BarcodeMergeReport.jsx";
import ItemWiseBarcodeReport from "./ItemWiseBarcodeReport.jsx";
import IssueToRefinary from "./components/manufacturing/issue/IssueToRefinary.jsx";
import ReceiveFromRefinary from "./components/manufacturing/receive/ReceiveFromRefinary.jsx";
import RetToRetstockTransfer from "./StockTrans.jsx";
import StockJournal from "./StockJournal.jsx";
import StockJournalList from "./StockJournalList.jsx";
import JoborderReport from "./jobOrderReport.jsx";
import StoneReturnAdd from "./components/manufacturing/receive/stoneReturnList.jsx";
import Account from "./components/FinancialAccounting/vouchers/account.jsx";
import KarigarGoldIssuesList from "./components/manufacturing/issue/KarigarGoldIssuesList.jsx";
import KarigarStoneIssueList from "./components/manufacturing/issue/karigarStoneIssuesList.jsx";
import RefinaryIssueList from "./components/manufacturing/issue/RefinaryIssueList.jsx";
import RefinaryReceiveList from "./components/manufacturing/receive/refinaryReceiveList.jsx";
import StockTransferList from "./StockTransferList.jsx";
import AccountingVoucherList from "./accountingVoucherList.jsx";
import VoucherTypeSelector from "./components/FinancialAccounting/vouchers/VoucherTypeSelector";
import LedgerStatement from "./components/FinancialAccounting/reports/LedgerStatement";
import DayBook from "./components/FinancialAccounting/reports/DayBook";
import OutstandingReport from "./components/FinancialAccounting/reports/OutstandingReport";
import BankReconciliation from "./components/FinancialAccounting/BankReconciliation";
import BarcodeHistoryList from "./components/Inventory/BarcodeManagement/BarcodeHistoryList.jsx";
import GoldRateForm from "./components/GoldRates/goldrate.jsx";
import SalesEstimate from "./components/Sales/SalesEstimate.jsx";
import ForbiddenPage from "./Forbidden.jsx";
import ProfitLoss from "./ProfitLoss/ProfitLoss.jsx";
import ProfitDemo from "./ProfitLoss/ProfitDemo.jsx";
import ProfitLossCal from "./ProfitLoss/ProfitLossCal.jsx";
import BalanceSheet from "./components/FinancialAccounting/reports/BalanceSheet.jsx";
import FinancialRatios from "./components/FinancialAccounting/reports/FinancialRatios.jsx";
import AuditQueue from "./components/FinancialAccounting/reports/AuditQueue.jsx";
import TrialBalance from "./trialBalance.jsx";
import ClosingStockTable from "./components/Inventory/closingStockReport.jsx";
import HallmarkIssueReport from "./hallmarkissuereport.jsx";
import HallmarkReceiveReport from "./hallmarkreceivereport.jsx";
import Metalreport from "./Metalreport.jsx"
import StockValueReport from "./stockValueReport.jsx";
import CashBookRetail from "./cashBookRetail.jsx";
import CombinedBankBook from "./combinedBankBook.jsx";
import BarcodeStockReport from "./components/Inventory/BarcodeManagement/barcodeStockReport.jsx";
import StoneWorkOrderReport from "./components/manufacturing/stoneissuereceivereport.jsx";
import PacketWiseStoneReport from "./components/manufacturing/PacketWiseStoneReport.jsx";
import ImportDataPage from "./components/MasterImport/ImportDataPage.jsx";
import OpeningBalance from "./OpeningBalance.jsx";
import SalesPersonList from "./components/Sales/SalesPersonList.jsx";
import ItemGroupMaster from "./components/Masters/ItemGroupMaster.jsx";
import PacketGroupMaster from "./components/Masters/PacketGroupMaster.jsx";
import HsnMaster from "./components/Masters/HsnMaster.jsx";
import ItemMaster from "./components/Masters/ItemMaster.jsx";
import PacketMaster from "./components/Masters/PacketMaster.jsx";
import FiscalYearManager from "./components/Masters/FiscalYearManager.jsx";
import RetailMasterPage from "./components/Masters/RetailMasterPage.jsx";
import BranchMasterPage from "./components/Masters/BranchMasterPage.jsx";
import CompanyMasterPage from "./components/Masters/CompanyMasterPage.jsx";
import BranchAnalytics from "./components/Masters/BranchAnalytics.jsx";
import KarigarMakingPage from "./components/Masters/KarigarMakingPage.jsx";
import ExhibitionMaster from "./components/Masters/ExhibitionMaster.jsx";
import TDSSectionMasterPage from "./components/Masters/TDSSectionMaster.jsx";
import TCSSectionMasterPage from "./components/Masters/TCSSectionMaster.jsx";
import PurityMasterPage from "./components/Masters/PurityMasterPage.jsx";
import ShapeMasterPage from "./components/Masters/ShapeMasterPage.jsx";
import ColorMasterPage from "./components/Masters/ColorMasterPage.jsx";
import TDSRegister from "./components/reports/TDSRegister.jsx";
import TCSRegister from "./components/reports/TCSRegister.jsx";
import CommissionReport from "./components/reports/CommissionReport.jsx";
import KarigarJobWorkReport from "./components/reports/KarigarJobWorkReport.jsx";
import RefineryReport from "./components/reports/RefineryReport.jsx";
import CRMDashboard from "./components/CRM/CRMDashboard.jsx";
import GSTR1Report from "./components/reports/GSTR1Report.jsx";
import GSTR3BReport from "./components/reports/GSTR3BReport.jsx";
import GoldLedgerBalances from "./components/Reports/GoldLedgerBalances.jsx";
import UserManagement from "./components/Settings/UserManagement.jsx";
import RoleManagement from "./components/Settings/RoleManagement.jsx";
import AuditLog from "./components/Settings/AuditLog.jsx";
import CRMAutomation from "./components/Settings/CRMAutomation.jsx";
import Dashboard from "./components/Dashboard/Dashboard.jsx";
import BarcodeBulkOps from "./components/Inventory/BarcodeManagement/BarcodeBulkOps.jsx";
import RawMaterialBalanceReport from "./components/Inventory/RawMaterialBalanceReport.jsx";
import RawMaterialLedger from "./components/Inventory/RawMaterialLedger.jsx";
import SemiFinishedStockReport from "./components/Inventory/SemiFinishedStockReport.jsx";
import SetupWizard from "./components/Settings/SetupWizard.jsx";
import SettingsPage from "./components/Settings/SettingsPage.jsx";
import SectionIndexPage from "./components/SectionIndexPage.jsx";
import RepairJobCardList from "./components/manufacturing/repair/RepairJobCardList.jsx";
import RepairJobCardForm from "./components/manufacturing/repair/RepairJobCardForm.jsx";
import AppsPage from "./components/Apps/AppsPage.jsx";



const isAuthenticate = () => !!localStorage.getItem("Token");
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

  // ── Setup / Masters ───────────────────────────────────────────────────────
  { path: "setup/salesperson",   heading: "Sales Person",          component: <SalesPersonList /> },
  { path: "setup/karigar-making", heading: "Karigar Making Master", component: <KarigarMakingPage /> },
  { path: "setup/import-data",   heading: "Import Master Data",    component: <ImportDataPage /> },
  { path: "setup/company",       heading: "Company Master",        component: <CompanyMasterPage /> },
  { path: "setup/branch",        heading: "Branch Master",         component: <BranchMasterPage /> },
  { path: "setup/branch/:id/analytics", heading: "Branch Analytics", component: <BranchAnalytics /> },
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

  // ── Financial Accounting ──────────────────────────────────────────────────
  { path: "accounting/vouchers/select",           heading: "New Voucher Entry",        component: <VoucherTypeSelector /> },
  { path: "accounting/opening-balance",           heading: "Opening Balances",         component: <OpeningBalance /> },
  { path: "accounting/account-tree",              heading: "Account Tree",             component: <AccountTree /> },
  { path: "accounting/account-create",            heading: "Add Account Group",        component: <AccountCreationForm /> },
  { path: "accounting/account-edit/:id",          heading: "Edit Account Group",       component: <AccountCreationForm /> },
  { path: "accounting/AddJournal/:journal_type/add", heading: "Add Journal",           component: <AddJournal /> },
  { path: "accounting/AddJournal/:journal_type/:id", heading: "Edit Journal",          component: <AddJournal /> },
  { path: "accounting/AddJournal/:journal_type",  heading: "Accounting Voucher List",  component: <AccountingVoucherList /> },
  { path: "accounting/cashgoldconversion",        heading: "Cash Gold Conversion",     component: <CashGoldConversion /> },
  { path: "accounting/ledger-statement",          heading: "Ledger Account Statement", component: <LedgerStatement /> },
  { path: "accounting/outstanding",               heading: "Outstanding Report",       component: <OutstandingReport /> },
  { path: "accounting/day-book",                  heading: "Day Book",                 component: <DayBook /> },
  { path: "accounting/bank-reconciliation",       heading: "Bank Reconciliation",      component: <BankReconciliation /> },
  { path: "accounting/trialbalance",              heading: "Trial Balance",            component: <TrialBalance /> },
  { path: "accounting/cashbook",                  heading: "Cash Book",                component: <CashBookRetail /> },
  { path: "accounting/bankbook",                  heading: "Bank Book",                component: <CombinedBankBook /> },
  { path: "accounting/balancesheet",              heading: "Balance Sheet",            component: <BalanceSheet /> },
  { path: "accounting/profitloss",                heading: "Profit & Loss",            component: <ProfitLoss /> },
  { path: "accounting/profitlosscal",             heading: "Profit Loss Calculation",  component: <ProfitLossCal /> },
  { path: "accounting/profitdemo",                heading: "Profit Demo Report",       component: <ProfitDemo /> },
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
  { path: "manufacturing/repair/list/",  heading: "Repair Job Cards",      component: <RepairJobCardList /> },
  { path: "manufacturing/repair/new",    heading: "New Repair Job Card",   component: <RepairJobCardForm /> },
  { path: "manufacturing/repair/:id",    heading: "Edit Repair Job Card",  component: <RepairJobCardForm /> },
  { path: "manufacturing/reports/krstoneissandrec",  heading: "Kr Stone Issue & Receive Report",  component: <KrStoneIssueAndReceive /> },
  { path: "manufacturing/reports/hallmarkissandrec", heading: "Hallmark Issue & Receive Report",  component: <HallmarkIssueReceiveReport /> },
  { path: "manufacturing/reports/hallmarkreceive",   heading: "Hallmark Receive Report",          component: <HallmarkReceiveReport /> },
  { path: "manufacturing/reports/hmissue",           heading: "Hallmark Issue Report",            component: <HallmarkIssueReport /> },
  { path: "manufacturing/reports/finisheditemrec",   heading: "Finished Item Receive Report",     component: <FinishedItemRecReport /> },
  { path: "manufacturing/reports/joborder",          heading: "Job Order Report",                 component: <JoborderReport /> },
  { path: "manufacturing/reports/karigar-jobwork",   heading: "Karigar Job Work Report",          component: <KarigarJobWorkReport /> },
  { path: "manufacturing/reports/refinery",          heading: "Refinery Report",                  component: <RefineryReport /> },

  // ── Purchases ─────────────────────────────────────────────────────────────
  { path: "purchase/purchasevoucher/list/",       heading: "Purchase Voucher List",  component: <PurchaseVoucherList /> },
  { path: "purchase/purchasevoucher/list/add/",   heading: "Add Purchase Voucher",   component: <PurchaseVoucher /> },
  { path: "purchase/purchasevoucher/list/:id",    heading: "Edit Purchase Voucher",  component: <PurchaseVoucher /> },
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
  { path: "purchase/customerpurchase/list/",      heading: "Customer Purchase List", component: <PurchaseVoucherList voucherType="Customer" /> },
  { path: "purchase/customerpurchase/list/add/",  heading: "Add Customer Purchase",  component: <PurchaseVoucher /> },
  { path: "purchase/customerpurchase/list/:id",   heading: "Edit Customer Purchase", component: <PurchaseVoucher /> },

  // ── Sales ─────────────────────────────────────────────────────────────────
  { path: "sales/estimate",                heading: "Sales Estimate",       component: <SalesEstimate /> },
  { path: "sales/customerorder/list/",     heading: "Customer Order List",  component: <CustomerOrderList /> },
  { path: "sales/customerorder/kanban/",   heading: "Customer Order Kanban", component: <CustomerOrderKanban /> },
  { path: "sales/customerorder/list/add/", heading: "Add Customer Order",   component: <CustomerOrderForm /> },
  { path: "sales/customerorder/list/:id",  heading: "Edit Customer Order",  component: <CustomerOrderForm /> },
  { path: "sales/salesvoucher/list/",      heading: "Sales Voucher List",   component: <SalesVoucherList /> },
  { path: "sales/salesvoucher/list/add/",  heading: "Add Sales Voucher",    component: <SalesVoucherAdd /> },
  { path: "sales/salesvoucher/list/:id",   heading: "Edit Sales Voucher",   component: <SalesVoucherAdd /> },
  { path: "sales/salesvoucher/add/",       heading: "Add Sales Voucher",    component: <SalesVoucherAdd /> },
  { path: "sales/rawsalesvoucher/add/",    heading: "Add Sales Voucher",    component: <SalesVoucherAdd /> },
  { path: "sales/salesreturn/list/",       heading: "Sales Return List",    component: <SalesReturnList /> },
  { path: "sales/salesreturn/list/add/",   heading: "Add Sales Return",     component: <SalesReturnAdd /> },
  { path: "sales/salesreturn/list/:id",    heading: "Edit Sales Return",    component: <SalesReturnAdd /> },
  { path: "sales/salesreturn/add/",        heading: "Add Sales Return",     component: <SalesReturnAdd /> },
  { path: "sales/salesapproval/list/",     heading: "Sales Approval List",  component: <SalesApprovalList /> },
  { path: "sales/salesapproval/list/add/", heading: "Add Sales Approval",   component: <SalesApprovalAdd /> },
  { path: "sales/salesapproval/list/:id",  heading: "Edit Sales Approval",  component: <SalesApprovalAdd /> },
  { path: "sales/salesapproval/add/",      heading: "Add Sales Approval",   component: <SalesApprovalAdd /> },
  { path: "sales/reports/commission",      heading: "Salesperson Commission Report", component: <CommissionReport /> },

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
  { path: "inventory/reports/raw-material",         heading: "Raw Material Balance",   component: <RawMaterialBalanceReport /> },
  { path: "inventory/reports/raw-material-ledger",  heading: "Raw Material Ledger",    component: <RawMaterialLedger /> },
  { path: "inventory/reports/semi-finished",        heading: "Semi-Finished Stock",    component: <SemiFinishedStockReport /> },

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
];



function App() {
  return (
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
      </Route>

      {/* Bill selection popup (opens in new window from receipt/payment vouchers) */}
      <Route path="accountadd/:type/:id" element={<Account />} />

      {/* Public route */}
      <Route path="login" element={<LoginPage />} />
      {/* Forbidden page — rendered on 403 redirect from apiClient */}
      <Route path="forbidden" element={<ForbiddenPage />} />
    </Routes>
  );
}


export default App;
