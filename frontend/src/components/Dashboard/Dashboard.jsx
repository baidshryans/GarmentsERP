import React, { useEffect, useState } from "react";
import { usePermissions } from "@/contexts/PermissionContext";
import { formatNumber, formatDate, getFormatConfig } from "@/lib/format";
import { Link } from "react-router-dom";
import {
  Gem,
  TrendingUp,
  TrendingDown,
  PenSquare,
  ShoppingCart,
  PackageCheck,
  ReceiptText,
  ArrowRight,
  Package,
  Hammer,
  Calculator,
  BookOpen,
  FileText,
  Wallet,
  IndianRupee,
  ClipboardList,
  AlertCircle,
} from "lucide-react";
import { useGoldRates } from "@/contexts/GoldRateContext";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { fetchDashboardSummary } from "@/services/apiService";

/* ── Gold rate card ───────────────────────────────────────── */
function GoldRateCard() {
  const { goldRates, loading, error } = useGoldRates();
  const sortedRates = [...goldRates].sort((a, b) => a.purity - b.purity);

  return (
    <div className="col-span-full rounded-2xl border border-accent-100 bg-gradient-to-br from-accent-50/80 to-white p-6 shadow-sm">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center size-10 rounded-xl bg-primary shadow-md shadow-accent-200">
            <Gem className="size-5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-gray-900 tracking-tight">
              Today's Gold Rates
            </h2>
            <p className="text-xs text-gray-500">
              {formatDate(new Date(), {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            </p>
          </div>
        </div>
        <Link
          to="/goldrate/form"
          className="flex items-center gap-1.5 text-xs font-semibold text-primary hover:text-primary transition-colors bg-accent-100/60 hover:bg-accent-100 rounded-lg px-3 py-1.5"
        >
          <PenSquare className="w-3.5 h-3.5" />
          Update
        </Link>
      </div>

      {loading ? (
        <div className="flex items-center gap-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="flex-1 h-20 rounded-xl bg-accent-100/50 animate-pulse"
            />
          ))}
        </div>
      ) : error ? (
        <div className="text-sm text-red-500 bg-red-50 rounded-xl px-4 py-3">
          Could not load gold rates. Please check your connection.
        </div>
      ) : sortedRates.length === 0 ? (
        <div className="text-sm text-gray-500 bg-gray-50 rounded-xl px-4 py-3">
          No gold rates set for today.{" "}
          <Link to="/goldrate/form" className="text-primary font-medium hover:underline">
            Set rates now
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {sortedRates.map((rate) => (
            <div
              key={rate.purity}
              className="relative rounded-xl border border-gray-100 bg-white px-4 py-3.5 shadow-sm hover:shadow-md hover:border-accent-200 transition-all group"
            >
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400 group-hover:text-primary transition-colors">
                  {rate.purity_name || `${rate.purity}K`}
                </span>
                <span className="text-[10px] text-gray-400">per gram</span>
              </div>
              <div className="text-xl font-bold text-gray-900 tabular-nums">
                {getFormatConfig().symbol}
                {formatNumber(rate.rate)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── KPI Summary Cards ────────────────────────────────────── */
function KPICards() {
  const [kpi, setKpi]         = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDashboardSummary().then((res) => {
      if (res.success) setKpi(res.data);
      setLoading(false);
    });
  }, []);

  const fmt = (n) =>
    formatNumber(n, { maxDecimals: 0 });

  const cards = kpi ? [
    {
      label: "Today's Sales",
      value: `₹${fmt(kpi.sales_today_value)}`,
      sub: `${kpi.sales_today_count} bill${kpi.sales_today_count !== 1 ? "s" : ""}`,
      icon: ReceiptText,
      color: "violet",
    },
    {
      label: "This Month Sales",
      value: `₹${fmt(kpi.sales_month_value)}`,
      sub: `${kpi.sales_month_count} bills`,
      icon: TrendingUp,
      color: "emerald",
    },
    {
      label: "Today's Purchases",
      value: `₹${fmt(kpi.purchases_today_value)}`,
      sub: "item total",
      icon: ShoppingCart,
      color: "sky",
    },
    {
      label: "Outstanding",
      value: `₹${fmt(kpi.outstanding_receivable)}`,
      sub: "total due from customers",
      icon: AlertCircle,
      color: kpi.outstanding_receivable > 0 ? "rose" : "emerald",
    },
    {
      label: "Purchase Orders",
      value: kpi.pending_po,
      sub: "total orders",
      icon: ClipboardList,
      color: "amber",
    },
  ] : [];

  const colorMap = {
    violet:  { bg: "bg-accent-50",  icon: "bg-accent-100 text-primary",  val: "text-primary"  },
    emerald: { bg: "bg-emerald-50", icon: "bg-emerald-100 text-emerald-600", val: "text-emerald-700" },
    sky:     { bg: "bg-sky-50",     icon: "bg-sky-100 text-sky-600",         val: "text-sky-700"     },
    rose:    { bg: "bg-rose-50",    icon: "bg-rose-100 text-rose-600",       val: "text-rose-700"    },
    amber:   { bg: "bg-amber-50",   icon: "bg-amber-100 text-amber-600",     val: "text-amber-700"   },
  };

  if (loading) return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="h-24 rounded-xl border border-gray-100 bg-white animate-pulse" />
      ))}
    </div>
  );

  if (!kpi) return null;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
      {cards.map(({ label, value, sub, icon: Icon, color }) => {
        const c = colorMap[color] || colorMap.violet;
        return (
          <div key={label} className={`rounded-xl border border-gray-100 ${c.bg} px-4 py-3.5 shadow-sm`}>
            <div className={`inline-flex items-center justify-center w-7 h-7 rounded-lg ${c.icon} mb-2`}>
              <Icon className="w-3.5 h-3.5" />
            </div>
            <div className={`text-lg font-bold tabular-nums ${c.val}`}>{value}</div>
            <div className="text-[11px] font-medium text-gray-600 mt-0.5">{label}</div>
            <div className="text-[10px] text-gray-400 mt-0.5">{sub}</div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Quick-action shortcut tile ───────────────────────────── */
function QuickAction({ to, icon: Icon, label, description, color }) {
  const colorMap = {
    violet: "bg-accent-50 text-primary group-hover:bg-accent-100",
    emerald: "bg-emerald-50 text-emerald-600 group-hover:bg-emerald-100",
    sky: "bg-sky-50 text-sky-600 group-hover:bg-sky-100",
    rose: "bg-rose-50 text-rose-600 group-hover:bg-rose-100",
    amber: "bg-amber-50 text-amber-600 group-hover:bg-amber-100",
    gray: "bg-gray-50 text-gray-600 group-hover:bg-gray-100",
  };

  return (
    <Link
      to={to}
      className="group flex items-start gap-3.5 rounded-xl border border-gray-100 bg-white p-4 shadow-sm hover:shadow-md hover:border-accent-200 transition-all"
    >
      <div
        className={`flex items-center justify-center w-9 h-9 rounded-lg shrink-0 transition-colors ${colorMap[color] || colorMap.violet}`}
      >
        <Icon className="w-4.5 h-4.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-gray-800 group-hover:text-primary transition-colors">
          {label}
        </div>
        <div className="text-xs text-gray-400 mt-0.5 truncate">
          {description}
        </div>
      </div>
      <ArrowRight className="size-4 text-gray-300 group-hover:text-accent-400 mt-0.5 shrink-0 transition-colors" />
    </Link>
  );
}

/* ── Main Dashboard ───────────────────────────────────────── */
export default function Dashboard() {
  const user = (() => {
    try {
      return JSON.parse(sessionStorage.getItem("user"));
    } catch {
      return null;
    }
  })();

  const greeting = (() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  })();

  const { canAccess } = usePermissions();

  const quickActions = [
    { to: "/sales/list/", icon: ReceiptText, label: "Sales Voucher", description: "Create or view sales bills", color: "violet", module: "sales.salesvou", perm: "post" },
    { to: "/purchase/list/", icon: ShoppingCart, label: "Purchase Voucher", description: "Record purchases", color: "emerald", module: "purchase.purchasevoucher", perm: "post" },
    { to: "/sales/estimate", icon: Calculator, label: "Estimate", description: "Create a new estimate", color: "sky", module: "sales.salesvou", perm: "post" },
    { to: "/manufacturing/issue/jobwork/", icon: Hammer, label: "Job Work Issue", description: "Issue to karigar", color: "amber", module: "manufacturing.karigarissue", perm: "post" },
    { to: "/inventory/barcodemanagement/list/", icon: Package, label: "Barcode Management", description: "Manage inventory barcodes", color: "gray", module: "inventory.barcodemain", perm: "list" },
    { to: "/accounting/vouchers/select", icon: Wallet, label: "Accounting Voucher", description: "Receipt, payment, journal", color: "rose", module: "accounting.vouchermain", perm: "post" },
  ].filter((a) => canAccess(a.module, a.perm));

  const reports = [
    { to: "/accounting/ledger-statement", icon: FileText, label: "Ledger Statement", module: "accounting.vouchermain" },
    { to: "/accounting/day-book", icon: BookOpen, label: "Day Book", module: "accounting.vouchermain" },
    { to: "/accounting/outstanding", icon: Wallet, label: "Outstanding", module: "accounting.vouchermain" },
    { to: "/accounting/trialbalance", icon: BookOpen, label: "Trial Balance", module: "accounting.vouchermain" },
    { to: "/accounting/balancesheet", icon: BookOpen, label: "Balance Sheet", module: "accounting.vouchermain" },
    { to: "/accounting/profitloss", icon: BookOpen, label: "Profit & Loss", module: "accounting.vouchermain" },
    { to: "/inventory/reports/closing-stock", icon: Package, label: "Closing Stock", module: "inventory.barcodemain" },
    { to: "/inventory/reports/barcodestockreport", icon: Package, label: "Stock Report", module: "inventory.barcodemain" },
    { to: "/inventory/reports/itemwisebarcode", icon: Package, label: "Value Report", module: "inventory.barcodemain" },
  ].filter((r) => canAccess(r.module, "list"));

  return (
    <div className="min-h-[calc(100svh-4rem)]">
      {/* ── Top bar ────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-6 h-14 border-b border-gray-100 bg-white">
        <div className="flex items-center gap-3">
          <SidebarTrigger className="text-gray-500 hover:text-primary transition-colors" />
          <div className="h-5 w-px bg-gray-200" />
          <div className="flex items-center gap-2">
            <span className="block w-[3px] h-4 rounded-full bg-primary" />
            <h1 className="text-sm font-bold text-gray-800 tracking-tight">
              Dashboard
            </h1>
          </div>
        </div>
      </header>

      {/* ── Content ────────────────────────────────────────── */}
      <div className="p-6 space-y-6 max-w-6xl mx-auto">
        {/* Greeting */}
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight">
            {greeting}
            {user?.username ? `, ${user.username}` : ""}
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Here's an overview of your Jewel India ERP workspace.
          </p>
        </div>

        {/* KPI Summary */}
        <KPICards />

        {/* Gold Rates */}
        <GoldRateCard />

        {/* Quick Actions */}
        {quickActions.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">
            Quick Actions
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {quickActions.map((a) => (
              <QuickAction
                key={a.to}
                to={a.to}
                icon={a.icon}
                label={a.label}
                description={a.description}
                color={a.color}
              />
            ))}
          </div>
        </div>
        )}

        {/* Reports shortcuts */}
        {reports.length > 0 && (
        <div>
          <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400 mb-3">
            Reports
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {reports.map(({ to, icon: Icon, label }) => (
              <Link
                key={to}
                to={to}
                className="group flex items-center gap-2.5 rounded-xl border border-gray-100 bg-white px-4 py-3 shadow-sm hover:shadow-md hover:border-accent-200 transition-all"
              >
                <Icon className="size-4 text-gray-400 group-hover:text-primary transition-colors shrink-0" />
                <span className="text-sm text-gray-700 group-hover:text-primary font-medium transition-colors truncate">
                  {label}
                </span>
              </Link>
            ))}
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
