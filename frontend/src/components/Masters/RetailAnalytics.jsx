import { useState, useEffect } from "react";
import { formatNumber, getFormatConfig } from "@/lib/format";
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
  Users,
  Truck,
  Zap,
} from "lucide-react";
import { fetchRetailAnalytics } from "@/services/apiService";

// ── helpers ──────────────────────────────────────────────────────────────────

function fmt(v) {
  if (v === null || v === undefined) return "—";
  return formatNumber(v, { maxDecimals: 0 });
}

function KpiTile({ label, value, icon: Icon, color, prefix = getFormatConfig().symbol }) {
  const colors = {
    violet:  "bg-accent-50  text-primary       border-accent-200",
    emerald: "bg-emerald-50 text-emerald-700   border-emerald-200",
    sky:     "bg-sky-50     text-sky-700       border-sky-200",
    amber:   "bg-amber-50   text-amber-700     border-amber-200",
    rose:    "bg-rose-50    text-rose-700      border-rose-200",
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

function LeaderboardRow({ rank, name, total, max, accent }) {
  const pct = max > 0 ? Math.round((total / max) * 100) : 0;
  return (
    <tr className="border-b border-border hover:bg-muted/40 transition-colors">
      <td className="px-4 py-3 w-10 text-xs font-semibold text-muted-foreground">#{rank}</td>
      <td className="px-4 py-3">
        <p className="text-sm font-medium">{name || "—"}</p>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-1">
          <p className="text-sm font-semibold text-right">₹{fmt(total)}</p>
          <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${accent}`} style={{ width: `${pct}%` }} />
          </div>
        </div>
      </td>
    </tr>
  );
}

function Leaderboard({ title, icon: Icon, rows, accent, emptyText }) {
  const max = rows.length ? Math.max(...rows.map((r) => r.total), 1) : 1;
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="px-4 py-3 bg-muted/40 border-b border-border flex items-center gap-2">
        <Icon className="size-4 text-muted-foreground" />
        <span className="text-sm font-semibold">{title}</span>
        <span className="ml-auto text-[11px] text-muted-foreground">Current month · ₹</span>
      </div>
      {rows.length === 0 ? (
        <div className="py-10 text-center text-sm text-muted-foreground">{emptyText}</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/20">
                <th className="px-4 py-2 text-left text-xs font-semibold text-muted-foreground">Rank</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-muted-foreground">Ledger</th>
                <th className="px-4 py-2 text-right text-xs font-semibold text-muted-foreground">Total</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <LeaderboardRow
                  key={r.ledger_id ?? i}
                  rank={i + 1}
                  name={r.ledger_name}
                  total={r.total}
                  max={max}
                  accent={accent}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function RetailAnalytics() {
  const { id }       = useParams();
  const navigate     = useNavigate();
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    const res = await fetchRetailAnalytics(id);
    if (res.success) {
      setData(res.data);
    } else {
      setError("Failed to load retail analytics.");
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

  const { retail, totals, top_customers, top_vendors } = data;

  return (
    <div className="p-4 flex flex-col gap-5">

      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate("/setup/retail")}
          className="p-1.5 rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-4" />
        </button>
        <div className="flex items-center gap-2">
          <div className="size-8 rounded-lg bg-accent-100 flex items-center justify-center">
            <Store className="size-4 text-primary" />
          </div>
          <div>
            <h1 className="text-base font-bold leading-tight">{retail.retail_name}</h1>
            <p className="text-[11px] text-muted-foreground">
              {retail.retail_code}
              {retail.branch_name ? ` · ${retail.branch_name}` : ""}
              {retail.active_fy_code ? ` · FY ${retail.active_fy_code}` : ""}
              {retail.is_exhibition ? (
                <span className="inline-flex items-center gap-1 ml-2 px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">
                  <Zap className="size-2.5" />Exhibition
                </span>
              ) : null}
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

      {/* KPI tiles */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <KpiTile label="Today's Sales (Net)"   value={totals.today_sales}     icon={TrendingUp}    color="emerald" />
        <KpiTile label="Month Sales (Net)"     value={totals.month_sales}     icon={TrendingUp}    color="violet"  />
        <KpiTile label="Today's Purchases"     value={totals.today_purchases} icon={TrendingDown}  color="rose"    />
        <KpiTile label="Outstanding"           value={totals.outstanding}     icon={Wallet}        color="amber"   />
        <KpiTile label="Open Purchase Orders"  value={totals.purchase_orders} icon={ClipboardList} color="sky"     prefix="" />
      </div>

      {/* Month-purchases secondary row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <KpiTile label="Month Purchases" value={totals.month_purchases} icon={ShoppingCart} color="rose" />
      </div>

      {/* Leaderboards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Leaderboard
          title="Top Customers (Month)"
          icon={Users}
          rows={top_customers}
          accent="bg-emerald-500"
          emptyText="No sales recorded this month."
        />
        <Leaderboard
          title="Top Vendors (Month)"
          icon={Truck}
          rows={top_vendors}
          accent="bg-rose-500"
          emptyText="No purchases recorded this month."
        />
      </div>
    </div>
  );
}
