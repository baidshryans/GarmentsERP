import { Link, useLocation } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Building2,
  Calculator,
  DollarSign,
  FileBarChartIcon,
  FileText,
  Gem,
  Hammer,
  History,
  Layers,
  Package,
  PackageCheckIcon,
  PackageXIcon,
  ReceiptTextIcon,
  Settings,
  ShoppingCart,
  SquareTerminal,
  Tag,
  Upload,
  Users,
  Wallet,
} from "lucide-react";

/* ── Section map ──────────────────────────────────────────────────────────────
   Key  = pathname (no trailing slash, lowercase)
   Each entry has a title, optional description, and a list of child links.
   ─────────────────────────────────────────────────────────────────────────── */
const SECTIONS = {
  "/setup": {
    title: "Setup & Masters",
    description: "Configure master data used across the ERP — items, groups, fiscal years, retails and more.",
    items: [
      { title: "Item Group",          url: "/setup/item-group",        icon: Layers,           desc: "Organise inventory items into groups" },
      { title: "Packet Group",        url: "/setup/packet-group",      icon: Package,          desc: "Group stone / loose packets" },
      { title: "HSN",                 url: "/setup/hsn",               icon: Tag,              desc: "HSN codes and GST tax rates" },
      { title: "Item",                url: "/setup/item",              icon: Gem,              desc: "Item master records" },
      { title: "Packet",              url: "/setup/packet",            icon: Package,          desc: "Packet / stone master records" },
      { title: "Fiscal Years",        url: "/setup/fiscal-years",      icon: BookOpen,         desc: "Create and manage financial years" },
      { title: "Retail",              url: "/setup/retail",            icon: ShoppingCart,     desc: "Retail outlet / branch locations" },
      { title: "Branch",              url: "/setup/branch",            icon: Layers,           desc: "Branch grouping for analytics" },
      { title: "TDS Sections",        url: "/setup/tds-section",       icon: ReceiptTextIcon,  desc: "TDS section codes" },
      { title: "TCS Sections",        url: "/setup/tcs-section",       icon: ReceiptTextIcon,  desc: "TCS section codes" },
      { title: "Chart of Accounts",   url: "/accounting/account-tree", icon: BookOpen,         desc: "Account hierarchy and groups" },
      { title: "Exhibitions",         url: "/setup/exhibitions",       icon: Tag,              desc: "Exhibition profiles for events" },
      { title: "Company",             url: "/setup/company",           icon: Building2,        desc: "Legal entity — PAN, TAN, contact, address" },
      { title: "Karigar Making",      url: "/setup/karigar-making",    icon: Hammer,           desc: "Making rate master per karigar" },
      { title: "Import Master Data",  url: "/setup/import-data",       icon: Upload,           desc: "Bulk CSV import for master tables" },
    ],
  },

  "/crm": {
    title: "CRM",
    description: "Customer relationship management — ledgers, occasions and more.",
    items: [
      { title: "Ledger",                url: "/crm/ledger",    icon: BookOpen, desc: "Manage customer, dealer, karigar and other party ledgers" },
      { title: "Birthday & Anniversary", url: "/crm/occasions", icon: BookOpen, desc: "Track customer birthdays and anniversaries" },
    ],
  },

  "/sales": {
    title: "Sales",
    description: "Manage estimates, customer orders, sales invoices, returns and approvals.",
    items: [
      { title: "Estimate",          url: "/sales/estimate",                icon: Calculator,       desc: "Prepare sales estimates for customers" },
      { title: "Customer Order",    url: "/sales/customerorder/list/",     icon: BookOpen,         desc: "Customer order book with advance tracking" },
      { title: "Sales Voucher",     url: "/sales/salesvoucher/list/",      icon: BookOpen,         desc: "Create and manage sales invoices" },
      { title: "Sales Return",      url: "/sales/salesreturn/list/",       icon: PackageXIcon,     desc: "Process sales return notes" },
      { title: "Sales Approval",    url: "/sales/salesapproval/list/",     icon: PackageCheckIcon, desc: "Approval-based vouchers" },
    ],
  },

  "/purchase": {
    title: "Purchases",
    description: "Record goods receipts, purchase orders, returns and approval vouchers.",
    items: [
      { title: "Purchase Voucher",       url: "/purchase/purchasevoucher/list/",   icon: ShoppingCart,     desc: "Purchase vouchers from suppliers" },
      { title: "Purchase Return",        url: "/purchase/purchasereturn/list/",    icon: PackageXIcon,     desc: "Return goods to supplier" },
      { title: "Purchase Approval",      url: "/purchase/purchaseapproval/list/",  icon: PackageCheckIcon, desc: "Approval-based purchase vouchers" },
      { title: "Purchase Order",         url: "/purchase/purchaseorder/list/",     icon: BookOpen,         desc: "Raise and track purchase orders" },
      { title: "Customer Purchase",      url: "/purchase/customerpurchase/list/",  icon: ShoppingCart,     desc: "Customer-side purchase records" },
    ],
  },

  "/manufacturing": {
    title: "Manufacturing",
    description: "Track job work, metal and stone issues and receives across the manufacturing workflow.",
    items: [
      { title: "Issue",   url: "/manufacturing/issue",   icon: PackageXIcon,    desc: "Job work, gold, stone, hallmark & refinery issues to karigar" },
      { title: "Receive", url: "/manufacturing/receive", icon: PackageCheckIcon, desc: "Receive finished items, stone returns, hallmark & refinery" },
      { title: "Reports", url: "/manufacturing/reports", icon: FileBarChartIcon, desc: "Manufacturing reports" },
    ],
  },

  "/manufacturing/issue": {
    title: "Manufacturing — Issue",
    description: "Issue raw materials and jobs to karigars and external processors.",
    items: [
      { title: "Job Work",        url: "/manufacturing/issue/jobwork",        icon: Hammer,   desc: "Issue job work to karigar" },
      { title: "Gold Issue",      url: "/manufacturing/issue/goldissue",      icon: Gem,      desc: "Gold issue to karigar" },
      { title: "Stone Issue",     url: "/manufacturing/issue/stoneissue/",    icon: Package,  desc: "Loose stone issue to karigar" },
      { title: "Hallmark Issue",  url: "/manufacturing/issue/hallmarkissue/", icon: Tag,      desc: "Items sent for BIS hallmarking" },
      { title: "Refinery Issue",  url: "/manufacturing/issue/refinary/",      icon: Package,  desc: "Metal sent to refinery" },
    ],
  },

  "/manufacturing/receive": {
    title: "Manufacturing — Receive",
    description: "Record returns and finished goods received from karigars and processors.",
    items: [
      { title: "Job Work Receive",  url: "/manufacturing/receive/jobworkreceive/",  icon: PackageCheckIcon, desc: "Receive finished items from karigar" },
      { title: "Stone Return",      url: "/manufacturing/receive/stonereturn/",      icon: PackageXIcon,     desc: "Stone returned from karigar" },
      { title: "Hallmark Receive",  url: "/manufacturing/receive/hallmarkreceive/",  icon: PackageCheckIcon, desc: "Items received after hallmarking" },
      { title: "Refinery Receive",  url: "/manufacturing/receive/refinary/",         icon: PackageCheckIcon, desc: "Metal received from refinery" },
    ],
  },

  "/manufacturing/reports": {
    title: "Manufacturing — Reports",
    description: "Manufacturing reports and analytics.",
    items: [
      { title: "Kr Stone Issue / Receive",  url: "/manufacturing/reports/krstoneissandrec",  icon: Package, desc: "" },
      { title: "Hallmark Issue / Receive",  url: "/manufacturing/reports/hallmarkissandrec", icon: Tag,     desc: "" },
      { title: "Hallmark Receive",          url: "/manufacturing/reports/hallmarkreceive",   icon: Tag,     desc: "" },
      { title: "Hallmark Issue",            url: "/manufacturing/reports/hmissue",           icon: Tag,     desc: "" },
      { title: "Finished Item Receive",     url: "/manufacturing/reports/finisheditemrec",   icon: Package, desc: "" },
      { title: "Job Order",                 url: "/manufacturing/reports/joborder",          icon: BookOpen, desc: "" },
      { title: "Karigar – Job Work",        url: "/manufacturing/reports/karigar-jobwork",   icon: Hammer,  desc: "" },
      { title: "Refinery Report",           url: "/manufacturing/reports/refinery",          icon: Package, desc: "" },
    ],
  },

  "/accounting": {
    title: "Financial Accounting",
    description: "Vouchers, ledger statements, reconciliation, financial reports and books of accounts.",
    items: [
      { title: "New Voucher Entry",    url: "/accounting/vouchers/select",     icon: ReceiptTextIcon, desc: "Create receipt, payment, contra or journal entry" },
      { title: "Opening Balances",     url: "/accounting/opening-balance",     icon: Wallet,          desc: "Set ledger opening balances" },
      { title: "Receipt Vouchers",     url: "/accounting/AddJournal/RCPT",     icon: BookOpen,        desc: "" },
      { title: "Payment Vouchers",     url: "/accounting/AddJournal/PMNT",     icon: BookOpen,        desc: "" },
      { title: "Contra Vouchers",      url: "/accounting/AddJournal/CONTRA",   icon: BookOpen,        desc: "" },
      { title: "Journal Vouchers",     url: "/accounting/AddJournal/JRNL",     icon: BookOpen,        desc: "" },
      { title: "Cash Gold Conversion", url: "/accounting/cashgoldconversion",  icon: DollarSign,      desc: "Convert cash to gold rate equivalents" },
      { title: "Ledger Statement",     url: "/accounting/ledger-statement",    icon: FileText,        desc: "Account-level transaction history" },
      { title: "Day Book",             url: "/accounting/day-book",            icon: BookOpen,        desc: "All vouchers in a date range" },
      { title: "Outstanding Report",   url: "/accounting/outstanding",         icon: Wallet,          desc: "Receivables and payables outstanding" },
      { title: "Bank Reconciliation",  url: "/accounting/bank-reconciliation", icon: Wallet,          desc: "Match bank statement to books" },
      { title: "Cash Book",            url: "/accounting/cashbook",            icon: Wallet,          desc: "" },
      { title: "Bank Book",            url: "/accounting/bankbook",            icon: Wallet,          desc: "Combined bank book" },
      { title: "Trial Balance",        url: "/accounting/trialbalance",        icon: BookOpen,        desc: "" },
      { title: "Balance Sheet",        url: "/accounting/balancesheet",        icon: BookOpen,        desc: "" },
      { title: "P & L Account",        url: "/accounting/profitloss",          icon: BookOpen,        desc: "" },
    ],
  },

  "/accounting/reports": {
    title: "Accounting — Reports",
    description: "Financial, GST and tax reports.",
    items: [
      { title: "Financial Ratios",          url: "/accounting/reports/financial-ratios",      icon: DollarSign,      desc: "" },
      { title: "Gold Ledger Balances",      url: "/accounting/reports/gold-ledger-balances",  icon: DollarSign,      desc: "" },
      { title: "GSTR-1",                    url: "/accounting/reports/gstr1",                 icon: ReceiptTextIcon, desc: "" },
      { title: "GSTR-3B Summary",           url: "/accounting/reports/gstr3b",                icon: ReceiptTextIcon, desc: "" },
      { title: "TDS Register",              url: "/accounting/reports/tds-register",           icon: ReceiptTextIcon, desc: "" },
      { title: "TCS Register",              url: "/accounting/reports/tcs-register",           icon: ReceiptTextIcon, desc: "" },
    ],
  },

  "/inventory": {
    title: "Inventory",
    description: "Barcode management, stock transfers, journals and design records.",
    items: [
      { title: "Barcode Management",  url: "/inventory/barcodemanagement/list/",            icon: SquareTerminal,   desc: "Create, split, merge and print barcodes" },
      { title: "Stock Transfer",      url: "/inventory/stocktransfer",                       icon: Package,          desc: "Transfer stock between retail locations" },
      { title: "Stock Journal",       url: "/inventory/stockjournal/",                       icon: FileText,         desc: "Manual stock adjustments" },
      { title: "Barcode History",     url: "/inventory/barcodemanagement/barcodehistory/",  icon: History,          desc: "Full audit trail of barcode changes" },
      { title: "Design",              url: "/inventory/design/list/",                        icon: BookOpen,         desc: "Design master records" },
      { title: "Reports",             url: "/inventory/reports",                              icon: FileBarChartIcon, desc: "Inventory reports" },
    ],
  },

  "/inventory/barcodemanagement": {
    title: "Barcode Management",
    description: "List, split, merge, export and print barcode labels.",
    items: [
      { title: "List",                url: "/inventory/barcodemanagement/list/",              icon: SquareTerminal,   desc: "All active barcodes" },
      { title: "Split",               url: "/inventory/barcodemanagement/split/",             icon: Package,          desc: "Split one barcode into multiple" },
      { title: "Merge",               url: "/inventory/barcodemanagement/merge",              icon: Package,          desc: "Merge multiple barcodes into one" },
      { title: "Stock Report",        url: "/inventory/reports/barcodestockreport",           icon: FileBarChartIcon, desc: "Barcode-wise stock report" },
      { title: "Bulk Print / Export", url: "/inventory/barcode-bulk",                         icon: Upload,           desc: "Print or export labels in bulk" },
    ],
  },

  "/inventory/reports": {
    title: "Inventory — Reports",
    description: "Inventory, stock and barcode reports.",
    items: [
      { title: "Id Generation",           url: "/inventory/reports/idgen",              icon: FileBarChartIcon, desc: "" },
      { title: "Metal Report",            url: "/inventory/reports/metalreport",        icon: Gem,              desc: "" },
      { title: "Packetwise Stone",        url: "/inventory/reports/packetwisestone",    icon: Package,          desc: "" },
      { title: "Stone Issue & Receive",   url: "/inventory/reports/stoneissuereceive",  icon: Package,          desc: "" },
      { title: "Closing Stock Valuation", url: "/inventory/reports/closing-stock",      icon: Package,          desc: "" },
      { title: "Barcode Split",           url: "/inventory/reports/barcodesplit",       icon: SquareTerminal,   desc: "" },
      { title: "Barcode Merge",           url: "/inventory/reports/barcodemerge",       icon: SquareTerminal,   desc: "" },
      { title: "ItemWise Barcode",        url: "/inventory/reports/itemwisebarcode",    icon: SquareTerminal,   desc: "" },
      { title: "Stock Report",            url: "/inventory/reports/barcodestockreport", icon: FileBarChartIcon, desc: "" },
    ],
  },
};

/* ── Normalise pathname: strip trailing slash, lowercase ─────────────────── */
const normalisePath = (p) => p.replace(/\/+$/, "").toLowerCase() || "/";

/* ── Component ────────────────────────────────────────────────────────────── */
export default function SectionIndexPage() {
  const { pathname } = useLocation();
  const section = SECTIONS[normalisePath(pathname)] ?? SECTIONS[pathname] ?? null;

  if (!section) {
    return (
      <div className="container mt-8 max-w-4xl text-center text-gray-400 text-sm">
        No sub-pages found for this section.
      </div>
    );
  }

  return (
    <div className="container mt-6 max-w-5xl">
      {section.description && (
        <p className="text-sm text-gray-500 mb-6">{section.description}</p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {section.items.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.url}
              to={item.url}
              className="flex items-start gap-3 p-4 rounded-lg border border-gray-200 bg-white hover:border-violet-300 hover:shadow-md transition-all group"
            >
              {/* Icon badge */}
              <div className="flex-shrink-0 w-8 h-8 rounded-md bg-violet-50 flex items-center justify-center group-hover:bg-violet-100 transition-colors">
                <Icon className="w-4 h-4 text-violet-600" />
              </div>

              {/* Text */}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-800 group-hover:text-violet-700 transition-colors leading-tight">
                  {item.title}
                </p>
                {item.desc && (
                  <p className="text-xs text-gray-400 mt-0.5 leading-snug">{item.desc}</p>
                )}
              </div>

              {/* Arrow */}
              <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-violet-400 transition-colors mt-0.5 flex-shrink-0" />
            </Link>
          );
        })}
      </div>
    </div>
  );
}
