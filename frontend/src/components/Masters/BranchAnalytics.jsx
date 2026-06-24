import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  Wallet,
  ShoppingCart,
  ClipboardList,
  Store,
  BarChart2,
  RefreshCw,
} from "lucide-react";
import { fetchBranchAnalytics } from "@/services/apiService";

// ── helpers ──────────────────────────────────────────────────────────────────

function fmt(v) {
  if (v === null || v === undefined) return "—";
  return Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function KpiTile({ label, value, icon: Icon, color, prefix = "₹" }) {
  const colors = {
    violet: "bg-accent-50 text-primary border-accent-200",
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
    sky:    "bg-sky-50    text-sky-700    border-sky-200",
    amber:  "bg-amber-50  text-amber-700  border-amber-200",
    rose:   "bg-rose-50   text-rose-700   border-rose-200",
  };
  return (
    <div className={`rounded-lg border px-4 py-3 flex items-center gap-3 ${colors[color] ?? colors.violet}`}>
      <div className="p-2 rounded-md bg-white/60">
        <Icon className="size-4" />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-medium opacity-70 truncate">{label}</p>
        <p className="text-base font-bold leading-tight">{prefix}{fmt(value)}</p>
      </div>
    </div>
  );
}

// ── retail row ───────────────────────────────────────────────────────────────

function RetailRow({ stat, maxMonth }) {
  const pct = maxMonth > 0 ? Math.round((stat.month_sales / maxMonth) * 100) : 0;
  return (
    <tr className="border-b border-border hover:bg-muted/40 transition-colors">
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="size-7 rounded-md bg-accent-100 flex items-center justify-center">
            <Store className="size-3.5 text-primary" />
          </div>
          <div>
            <p className="text-sm font-medium">{stat.retail_name}</p>
            <p className="text-[11px] text-muted-foreground">{stat.retail_code}{stat.active_fy_code ? ` · FY ${stat.active_fy_code}` : ""}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-right text-sm font-semibold text-emerald-700">
        ₹{fmt(stat.today_sales)}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-1">
          <p className="text-sm font-semibold text-right">₹{fmt(stat.month_sales)}</p>
          <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-right text-sm text-rose-600">
        ₹{fmt(stat.today_purchases)}
      </td>
      <td className="px-4 py-3 text-right text-sm">
        ₹{fmt(stat.month_purchases)}
      </td>
      <td className="px-4 py-3 text-right text-sm font-medium text-amber-700">
        ₹{fmt(stat.outstanding)}
      </td>
      <td className="px-4 py-3 text-right text-sm text-sky-700">
        {fmt(stat.purchase_orders)}
      </td>
    </tr>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function BranchAnalytics() {
  const { id }       = useParams();
  const navigate     = useNavigate();
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    const res = await fetchBranchAnalytics(id);
    if (res.success) {
      setData(res.data);
    } else {
      setError("Failed to load branch analytics.");
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [id]);

  if (loading) {
    return (
      <div className="p-6 flex flex-col gap-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-20" />)}
        </div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 flex flex-col gap-4 items-center text-center">
        <BarChart2 className="size-10 text-muted-foreground" />
        <p className="text-muted-foreground">{error ?? "No data"}</p>
        <Button variant="outline" size="sm" onClick={load}>Retry</Button>
      </div>
    );
  }

  const { branch, retails, totals } = data;
  const maxMonth = Math.max(...retails.map((r) => r.month_sales), 1);

  return (
    <div className="p-4 flex flex-col gap-5">

      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate("/setup/branch")}
          className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-4" />
        </button>
        <div className="flex items-center gap-2">
          <div className="size-8 rounded-lg bg-accent-100 flex items-center justify-center">
            <BarChart2 className="size-4 text-primary" />
          </div>
          <div>
            <h1 className="text-base font-bold leading-tight">{branch.branch_name}</h1>
            <p className="text-[11px] text-muted-foreground">
              {branch.branch_code} · {branch.retail_count} retail location{branch.retail_count !== 1 ? "s" : ""}
              {branch.description ? ` · ${branch.description}` : ""}
            </p>
          </div>
        </div>
        <div className="ml-auto">
          <Button
            variant="outline"
            size="sm"
            onClick={load}
            className="gap-1.5"
          >
            <RefreshCw className="size-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Grand-total KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiTile label="Today's Sales (Net)"   value={totals.today_sales}     icon={TrendingUp}    color="emerald" />
        <KpiTile label="Month Sales (Net)"     value={totals.month_sales}     icon={TrendingUp}    color="violet"  />
        <KpiTile label="Today's Purchases"     value={totals.today_purchases} icon={TrendingDown}  color="rose"    />
        <KpiTile label="Outstanding"           value={totals.outstanding}     icon={Wallet}        color="amber"   />
        <KpiTile label="Open Purchase Orders"  value={totals.purchase_orders} icon={ClipboardList} color="sky" prefix="" />
      </div>

      {/* Per-retail breakdown */}
      {retails.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border py-14 flex flex-col items-center gap-3 text-center">
          <Store className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No retail locations are linked to this branch yet.
          </p>
          <p className="text-xs text-muted-foreground">
            Go to <strong>Masters → Retail</strong> and assign a branch to each location.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="px-4 py-3 bg-muted/40 border-b border-border flex items-center gap-2">
            <ShoppingCart className="size-4 text-muted-foreground" />
            <span className="text-sm font-semibold">Retail Performance Breakdown</span>
            <span className="ml-auto text-[11px] text-muted-foreground">All figures in ₹</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/20">
                  <th className="px-4 py-2 text-left text-xs font-semibold text-muted-foreground">Retail</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-muted-foreground">Today Sales</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-muted-foreground">Month Sales</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-muted-foreground">Today Purchases</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-muted-foreground">Month Purchases</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-muted-foreground">Outstanding</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-muted-foreground">Open POs</th>
                </tr>
              </thead>
              <tbody>
                {retails.map((stat) => (
                  <RetailRow key={stat.retail_id} stat={stat} maxMonth={maxMonth} />
                ))}
              </tbody>
              {/* Totals row */}
              <tfoot>
                <tr className="bg-accent-50 border-t-2 border-accent-200 font-semibold">
                  <td className="px-4 py-2.5 text-sm text-primary">Branch Total</td>
                  <td className="px-4 py-2.5 text-right text-sm text-emerald-700">₹{fmt(totals.today_sales)}</td>
                  <td className="px-4 py-2.5 text-right text-sm text-primary">₹{fmt(totals.month_sales)}</td>
                  <td className="px-4 py-2.5 text-right text-sm text-rose-600">₹{fmt(totals.today_purchases)}</td>
                  <td className="px-4 py-2.5 text-right text-sm">₹{fmt(totals.month_purchases)}</td>
                  <td className="px-4 py-2.5 text-right text-sm text-amber-700">₹{fmt(totals.outstanding)}</td>
                  <td className="px-4 py-2.5 text-right text-sm text-sky-700">{fmt(totals.purchase_orders)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
