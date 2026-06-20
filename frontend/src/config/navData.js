import {
  ArrowUpFromLine,
  BarChart2,
  Landmark,
  BookOpen,
  Building2,
  Calculator,
  ClipboardList,
  Clock,
  DollarSign,
  FileBarChartIcon,
  FileText,
  Gem,
  Hammer,
  Heart,
  History,
  LayoutDashboard,
  Monitor,
  Package,
  PackageCheckIcon,
  PackageXIcon,
  Palette,
  Percent,
  ReceiptTextIcon,
  Scale,
  ScanLine,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  Tag,
  TrendingDown,
  Users,
  UserCog,
  Wallet,
  Wrench,
  Layers,
} from "lucide-react"

export const navData = {
  // ── Setup ──────────────────────────────────────────────────────────────────
  navMain0: [
    {
      title: "Organisation",
      url: "#",
      icon: Building2,
      items: [
        { title: "Import Master Data", url: "/setup/import-data"          },
        { title: "Company",            url: "/setup/company"              },
        { title: "Branch",             url: "/setup/branch"               },
        { title: "Retail",             url: "/setup/retail"               },
        { title: "Exhibitions",        url: "/setup/exhibitions"          },
        { title: "Fiscal Years",       url: "/setup/fiscal-years"         },
        { title: "GST Master",          url: "/setup/gstin"               },
      ],
    },
    {
      title: "Item Management",
      url: "#",
      icon: Tag,
      items: [
        { title: "HSN",           url: "/setup/hsn"          },
        { title: "Item Groups",   url: "/setup/item-group"   },
        { title: "Item Master",   url: "/setup/item"         },
        { title: "Packet Groups", url: "/setup/packet-group" },
        { title: "Packets",       url: "/setup/packet"       },
        { title: "Purity Master", url: "/setup/purity"       },
        { title: "Shape Master",  url: "/setup/shape"        },
        { title: "Color Master",  url: "/setup/color"        },
      ],
    },
    { title: "Sales Person",      url: "/setup/salesperson",       icon: Users        },
    { title: "Karigar Making",    url: "/setup/karigar-making",    icon: Hammer       },
    { title: "B2B Sale Pricelist",     url: "/setup/b2b-pricelist",     icon: Tag          },
    { title: "Retail Discount Pricelist", url: "/setup/retail-discount-pricelist", icon: Tag },
    { title: "Sales Offers",             url: "/setup/sales-offer",               icon: Tag },
    { title: "Chart of Accounts", url: "/accounting/account-tree", icon: BookOpen     },
    { title: "TDS Sections",      url: "/setup/tds-section",       icon: Percent      },
    { title: "TCS Sections",      url: "/setup/tcs-section",       icon: Percent      },
  ],

  // ── CRM (core) ─────────────────────────────────────────────────────────────
  navCRM: [
    { title: "Ledger",                   url: "/crm/ledger",            icon: BookOpen },
    { title: "Customer History",         url: "/crm/customer-history",  icon: History  },
  ],

  // ── CRM Occasions (addon) ─────────────────────────────────────────────────
  navCRMOccasions: [
    { title: "Birthday & Anniversary", url: "/crm/occasions", icon: Heart    },
  ],

  // ── Manufacturing ──────────────────────────────────────────────────────────
  navMain: [
    {
      title: "Issue",
      url: "#",
      icon: ArrowUpFromLine,
      items: [
        { title: "Job Work",        url: "/manufacturing/issue/jobwork/"       },
        { title: "Sample Issue",    url: "/manufacturing/issue/sample-issue"   },
        { title: "Gold Issue",      url: "/manufacturing/issue/goldissue/"     },
        { title: "Stone Issue",     url: "/manufacturing/issue/stoneissue/"    },
        { title: "Hallmark Issue",  url: "/manufacturing/issue/hallmarkissue/" },
        { title: "Refinery Issue",  url: "/manufacturing/issue/refinary/"      },
        { title: "Melting Issue",   url: "/manufacturing/issue/melting/"       },
        { title: "Assay Issue",     url: "/manufacturing/issue/assay/"         },
      ],
    },
    {
      title: "Receive",
      url: "#",
      icon: PackageCheckIcon,
      items: [
        { title: "Job Work Receive", url: "/manufacturing/receive/jobworkreceive/"  },
        { title: "Stone Return",     url: "/manufacturing/receive/stonereturn/"     },
        { title: "Hallmark Receive", url: "/manufacturing/receive/hallmarkreceive/" },
        { title: "Refinery Receive", url: "/manufacturing/receive/refinary/"        },
        { title: "Melting Receive",  url: "/manufacturing/receive/melting/"         },
        { title: "Assay Receive",    url: "/manufacturing/receive/assay/"           },
      ],
    },
    {
      title: "Repair",
      url: "#",
      icon: Wrench,
      items: [
        { title: "Repair Job Cards", url: "/manufacturing/repair/list/" },
      ],
    },
    {
      title: "Reports",
      url: "#",
      icon: FileBarChartIcon,
      items: [
        { title: "Karigar Stone Transactions", url: "/manufacturing/reports/karigarstonetxns"      },
        { title: "Hallmark Receive",          url: "/manufacturing/reports/hallmarkreceive"         },
        { title: "Hallmark Issue",            url: "/manufacturing/reports/hmissue"                 },
        { title: "Finished Item Receive",     url: "/manufacturing/reports/finisheditemrec"         },
        { title: "Job Work Status",           url: "/manufacturing/reports/karigar-jobwork"         },
        { title: "Refinery Report",           url: "/manufacturing/reports/refinery"                },
        { title: "Raw Material Balance",       url: "/inventory/reports/raw-material"                },
        { title: "Raw Material Ledger",        url: "/inventory/reports/raw-material-ledger"         },
        { title: "Raw Material Transactions",  url: "/inventory/reports/raw-material-transactions"   },
        { title: "Gold Ledger Balances",       url: "/accounting/reports/gold-ledger-balances"       },
        { title: "Unbarcoded Stock",           url: "/manufacturing/reports/unbarcoded-stock"        },
      ],
    },
  ],

  // ── Purchases ──────────────────────────────────────────────────────────────
  navPurchases: [
    { title: "Purchase Voucher",       url: "/purchase/list/",                  icon: ShoppingCart     },
    { title: "Purchase Return",        url: "/purchase/purchasereturn/list/",    icon: PackageXIcon     },
    { title: "Purchase Approval",      url: "/purchase/purchaseapproval/list/",  icon: PackageCheckIcon },
    { title: "Purchase Order",         url: "/purchase/purchaseorder/list/",     icon: ClipboardList    },
    { title: "Customer Purchase",      url: "/purchase/customerpurchase/list/",  icon: ShoppingCart     },
  ],

  // ── Sales ──────────────────────────────────────────────────────────────────
  navMain2: [
    { title: "POS Counter",    url: "/sales/pos",                 icon: Monitor          },
    { title: "Estimate",       url: "/sales/estimate",            icon: Calculator       },
    { title: "Quotation",     url: "/sales/quotation/list/",     icon: FileText         },
    { title: "Customer Order", url: "/sales/customerorder/list/", icon: ClipboardList    },
    { title: "Sales Voucher",  url: "/sales/list/",               icon: ReceiptTextIcon  },
    { title: "Sales Return",   url: "/sales/salesreturn/list/",   icon: PackageXIcon     },
    { title: "Sales Approval",  url: "/sales/salesapproval/list/",        icon: PackageCheckIcon },
    { title: "Approval Return", url: "/sales/salesapprovalreturn/list/", icon: PackageXIcon     },
    { title: "E-Way Bills",    url: "/sales/eway-bills",                  icon: FileText         },
    { title: "Pending Cheques", url: "/sales/pending-cheques",     icon: Landmark         },
    {
      title: "Reports",
      url: "#",
      icon: FileBarChartIcon,
      items: [
        { title: "Order Tracker",          url: "/sales/customerorder/tracker/" },
        { title: "Sales Register",         url: "/sales/reports/sales-register" },
        { title: "Sale Approval Register", url: "/sales/reports/sale-approval-register" },
        { title: "Salesperson Commission", url: "/sales/reports/commission" },
      ],
    },
  ],

  // ── Inventory ──────────────────────────────────────────────────────────────
  navMain3: [
    {
      title: "Barcode Management",
      url: "#",
      icon: ScanLine,
      items: [
        { title: "List",                url: "/inventory/barcodemanagement/list/"      },
        { title: "Split",               url: "/inventory/barcodemanagement/split/"     },
        { title: "Merge",               url: "/inventory/barcodemanagement/merge"      },
        { title: "Stock Report",        url: "/inventory/reports/barcodestockreport"   },
        { title: "Bulk Print / Export", url: "/inventory/barcode-bulk"                },
      ],
    },
    { title: "Stock Transfer",  url: "/inventory/stocktransfer",                         icon: Package    },
    { title: "Inter-Retail Transfer", url: "/inventory/inter-retail-transfer",           icon: Package    },
    { title: "Stock Journal",   url: "/inventory/stockjournal/",                         icon: FileText   },
    { title: "Barcode History", url: "/inventory/barcodemanagement/barcodehistory/",     icon: History    },
    { title: "Design",          url: "/inventory/design/list/",                          icon: Palette    },
    { title: "Catalog",         url: "/inventory/catalog/",                              icon: Package    },
    { title: "Opening Stock",   url: "/inventory/opening-stock",                         icon: Package    },
    {
      title: "Reports",
      url: "#",
      icon: FileBarChartIcon,
      items: [
        { title: "Id Generation",           url: "/inventory/reports/idgen"                },
        { title: "Metal Report",            url: "/inventory/reports/metalreport"          },
        { title: "Packetwise Stone",        url: "/inventory/reports/packetwisestone"      },
        { title: "Closing Stock Valuation", url: "/inventory/reports/closing-stock"        },
        { title: "Barcode Split",           url: "/inventory/reports/barcodesplit"         },
        { title: "Barcode Merge",           url: "/inventory/reports/barcodemerge"         },
        { title: "ItemWise Barcode",        url: "/inventory/reports/itemwisebarcode"      },
        { title: "Stock Matching",          url: "/inventory/reports/stock-matching"        },
        { title: "Stock Value",             url: "#"                                       },
        { title: "Semi-Finished Stock",     url: "/inventory/reports/semi-finished"         },
      ],
    },
  ],

  // ── Financial Accounting ───────────────────────────────────────────────────
  navMain4: [
    { title: "New Voucher Entry",    url: "/accounting/vouchers/select",      icon: ReceiptTextIcon  },
    { title: "Opening Balances",     url: "/accounting/opening-balance",      icon: Scale            },
    {
      title: "Voucher Lists",
      url: "#",
      icon: BookOpen,
      items: [
        { title: "Receipt Vouchers", url: "/accounting/RCPT"   },
        { title: "Payment Vouchers", url: "/accounting/PMNT"   },
        { title: "Contra Vouchers",  url: "/accounting/CONTRA" },
        { title: "Journal Vouchers", url: "/accounting/JRNL"   },
      ],
    },
    { title: "Credit / Debit Notes", url: "/accounting/credit-debit-notes",  icon: FileText         },
    { title: "Cash Gold Conversion", url: "/accounting/cashgoldconversion",  icon: DollarSign       },
    { title: "Ledger Statement",     url: "/accounting/ledger-statement",    icon: FileText         },
    { title: "Outstanding Report",   url: "/accounting/outstanding",         icon: Clock            },
    { title: "Aged Receivables",     url: "/accounting/aged-receivables",    icon: Clock            },
    { title: "Advance Register",     url: "/accounting/advance-register",    icon: Clock            },
    { title: "Unallocated Vouchers", url: "/accounting/unallocated-vouchers", icon: Clock            },
    {
      title: "Finance Reports",
      url: "#",
      icon: FileBarChartIcon,
      items: [
        { title: "Trial Balance",           url: "/accounting/trialbalance"                  },
        { title: "Bank Reconciliation",     url: "/accounting/bank-reconciliation"           },
        { title: "Day Book",                url: "/accounting/day-book"                      },
        { title: "Cash Book",               url: "/accounting/cashbook"                      },
        { title: "Bank Book",               url: "/accounting/bankbook"                      },
        { title: "Balance Sheet",           url: "/accounting/balancesheet"                  },
        { title: "P & L Account",           url: "/accounting/profitloss"                    },
        { title: "Profit Loss Calculation", url: "/accounting/profitlosscal"                 },
        { title: "Financial Ratios",        url: "/accounting/reports/financial-ratios"       },
      ],
    },
    { title: "Audit Queue", url: "/accounting/audit-queue", icon: ShieldCheck },
    {
      title: "GST & Tax Reports",
      url: "#",
      icon: ReceiptTextIcon,
      items: [
        { title: "GST Input Register",          url: "/accounting/gstinputregister"          },
        { title: "GST Output Register",         url: "/accounting/gstoutputregister"         },
        { title: "GSTR-1 (B2B / B2CL / B2CS)", url: "/accounting/reports/gstr1"             },
        { title: "GSTR-3B Summary",             url: "/accounting/reports/gstr3b"            },
        { title: "GSTR-2B Reconciliation",      url: "/purchase/gstr2b-reconcile"            },
        { title: "TDS Register",                url: "/accounting/reports/tds-register"      },
        { title: "TCS Register",                url: "/accounting/reports/tcs-register"      },
      ],
    },
    {
      title: "Fixed Assets",
      url: "#",
      icon: Layers,
      items: [
        { title: "Asset Master",           url: "/fixed-assets/master"       },
        { title: "Depreciation Worksheet", url: "/fixed-assets/depreciation" },
        { title: "FA Settings",            url: "/fixed-assets/settings"     },
      ],
    },
  ],

  // ── HR ─────────────────────────────────────────────────────────────────────
  navHR: [
    { title: "Employees",          url: "/hr/employees",          icon: UserCog      },
    { title: "Salary Structure",   url: "/hr/salary-structure",   icon: Wallet       },
    { title: "Salary Processing",  url: "/hr/salary-processing",  icon: FileText     },
    { title: "HR Settings",        url: "/hr/settings",           icon: Settings     },
  ],

  // ── Gold Schemes ───────────────────────────────────────────────────────────
  navGoldScheme: [
    { title: "Dashboard",    url: "/scheme/dashboard",    icon: LayoutDashboard },
    { title: "Scheme Master", url: "/scheme/master",      icon: Gem             },
    { title: "Enrollments",  url: "/scheme/enrollments",  icon: ClipboardList   },
  ],

  // ── AI ─────────────────────────────────────────────────────────────────────
  navMainAI: [
    {
      title: "AI Assistant",
      url: "#",
      icon: Sparkles,
      items: [
        { title: "Query History", url: "/ai/history", icon: History },
      ],
    },
  ],

  // ── Vendor Analytics ───────────────────────────────────────────────────────
  navVendorAnalytics: [
    { title: "Dashboard",          url: "/vendor-analytics/dashboard",          icon: BarChart2 },
    { title: "Stock Ageing",       url: "/vendor-analytics/stock-ageing",       icon: BarChart2 },
    { title: "Design Performance", url: "/vendor-analytics/design-performance", icon: BarChart2 },
    { title: "Inventory Turnover", url: "/vendor-analytics/inventory-turnover", icon: BarChart2 },
    { title: "Item Performance",   url: "/vendor-analytics/item-performance",   icon: BarChart2 },
    { title: "Vendor Comparison",  url: "/vendor-analytics/vendor-comparison",  icon: BarChart2 },
  ],

  // ── System ─────────────────────────────────────────────────────────────────
  navSettings: [
    {
      title: "Settings",
      url: "#",
      icon: Settings,
      items: [
        { title: "ERP Setup Wizard",  url: "/settings/setup"           },
        { title: "User Management",   url: "/settings/user-management" },
        { title: "Roles & Permissions", url: "/settings/roles"          },
        { title: "Audit Log",         url: "/settings/audit-log"       },
        { title: "Advanced Settings", url: "/settings"                 },
        { title: "CRM Automation",    url: "/settings/crm-automation"  },
        { title: "Carry Forward DB",  url: "/settings/carry-forward"   },
      ],
    },
  ],
}

/** Flat array consumed by TopMenuBar — one entry per top-level nav group.
 *  `parts` lets multiple license keys merge under one visible section. */
export const navSections = [
  { label: "Setup",                parts: [{ key: "navMain0",          items: navData.navMain0 }] },
  { label: "CRM",                  parts: [{ key: "navCRM",            items: navData.navCRM },
                                           { key: "navCRMOccasions",   items: navData.navCRMOccasions }] },
  { label: "Manufacturing",        parts: [{ key: "navMain",           items: navData.navMain }] },
  { label: "Purchases",            parts: [{ key: "navPurchases",      items: navData.navPurchases }] },
  { label: "Sales",                parts: [{ key: "navMain2",          items: navData.navMain2 }] },
  { label: "Inventory",            parts: [{ key: "navMain3",          items: navData.navMain3 }] },
  { label: "Financial Accounting", parts: [{ key: "navMain4",          items: navData.navMain4 }] },
  { label: "HR",                   parts: [{ key: "navHR",             items: navData.navHR }] },
  { label: "Gold Schemes",         parts: [{ key: "navGoldScheme",     items: navData.navGoldScheme }] },
  { label: "AI",                   parts: [{ key: "navMainAI",         items: navData.navMainAI }] },
  { label: "Vendor Analytics",     parts: [{ key: "navVendorAnalytics", items: navData.navVendorAnalytics }] },
  { label: "System",               parts: [{ key: "navSettings",       items: navData.navSettings }] },
]
