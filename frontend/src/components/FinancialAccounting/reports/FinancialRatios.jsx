import { useState } from "react";
import { formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { TrendingUp, BarChart2, Scale, Activity } from "lucide-react";
import { isValidDateRange } from "@/lib/dateRange";

const today = new Date().toISOString().split("T")[0];
const fy = new Date().getMonth() < 3 ? new Date().getFullYear() - 1 : new Date().getFullYear();
const firstOfYear = `${fy}-04-01`;

const fmtCur = (v) => {
  const n = Number(v);
  if (!n && n !== 0) return "—";
  return formatNumber(n, { decimals: 2, abs: true });
};

const fmtRatio = (v, unit) => {
  if (v === null || v === undefined) return "N/A";
  if (unit === "%") return `${v.toFixed(2)}%`;
  if (unit === "days") return `${v.toFixed(1)} days`;
  return `${v.toFixed(2)}×`;
};

const statusColor = (label, value) => {
  if (value === null || value === undefined) return "text-muted-foreground";
  const l = label.toLowerCase();
  if (l.includes("margin") || l.includes("return") || l.includes("ebit")) {
    return value >= 15 ? "text-green-600 dark:text-green-400"
      : value >= 5   ? "text-yellow-600 dark:text-yellow-400"
      : "text-red-600 dark:text-red-400";
  }
  if (l.includes("turnover") && !l.includes("days")) {
    return value >= 3 ? "text-green-600 dark:text-green-400"
      : value >= 1   ? "text-yellow-600 dark:text-yellow-400"
      : "text-red-600 dark:text-red-400";
  }
  if (l.includes("debt ratio") || l.includes("debt-to-equity")) {
    return value <= 0.5 ? "text-green-600 dark:text-green-400"
      : value <= 1      ? "text-yellow-600 dark:text-yellow-400"
      : "text-red-600 dark:text-red-400";
  }
  return "text-foreground";
};

function RatioCard({ label, value, unit, desc }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 flex flex-col gap-1 hover:bg-muted/30 transition-colors">
      <p className="text-xs text-muted-foreground leading-tight">{label}</p>
      <p className={`text-2xl font-bold tracking-tight ${statusColor(label, value)}`}>
        {fmtRatio(value, unit)}
      </p>
      <p className="text-xs text-muted-foreground/70 mt-auto pt-1">{desc}</p>
    </div>
  );
}

function SectionHeader({ icon: Icon, title, color }) {
  return (
    <div className={`flex items-center gap-2 mb-3 pb-2 border-b border-border`}>
      <Icon className={`w-4 h-4 ${color}`} />
      <h3 className="font-semibold text-sm text-foreground">{title}</h3>
    </div>
  );
}

function BaseDataRow({ label, value }) {
  return (
    <div className="flex justify-between items-center py-1 border-b border-border/50 last:border-0 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-medium">{fmtCur(value)}</span>
    </div>
  );
}

export default function FinancialRatios() {
  const [startDate, setStartDate] = useState(firstOfYear);
  const [endDate, setEndDate]     = useState(today);
  const [data, setData]           = useState(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);
  const [combined, setCombined]   = useState(false);

  const user = JSON.parse(sessionStorage.getItem("user") || "{}");
  const canViewCombined = user.is_superuser || ["admin", "super admin"].includes((user.role || "").toLowerCase());

  const fetchRatios = () => {
    if (!isValidDateRange(startDate, endDate)) {
      setError("From date cannot be after To date.");
      return;
    }
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
    if (combined) params.set("combined", "true");
    apiClient
      .get(`/accounting/api/financial-ratios/?${params}`)
      .then((r) => setData(r.data))
      .catch((e) => setError(e?.response?.data?.error || "Failed to load ratios."))
      .finally(() => setLoading(false));
  };

  const profitability = data?.profitability ? Object.values(data.profitability) : [];
  const efficiency    = data?.efficiency    ? Object.values(data.efficiency)    : [];
  const leverage      = data?.leverage      ? Object.values(data.leverage)      : [];
  const base          = data?.base_data;

  return (
    <div className="max-w-6xl mx-auto p-4 space-y-6">
      {/* ── Filters ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} max={endDate || undefined} className="w-40 h-8 text-sm" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} min={startDate || undefined} className="w-40 h-8 text-sm" />
        </div>
        {canViewCombined && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="fr-combined"
              checked={combined}
              onChange={(e) => setCombined(e.target.checked)}
              className="size-4 rounded border-gray-300"
            />
            <Label htmlFor="fr-combined" className="text-xs cursor-pointer">Combined (All Retails)</Label>
          </div>
        )}
        <Button onClick={fetchRatios} disabled={loading} size="sm">
          {loading ? "Loading…" : "Generate Ratios"}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {Array.from({ length: 16 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-lg" />
          ))}
        </div>
      )}

      {data && !loading && (
        <>
          {/* ── Period banner ─────────────────────────────────────── */}
          <div className="text-xs text-muted-foreground">
            Period: <span className="font-medium text-foreground">{data.period.start_date}</span>
            {" "}to{" "}
            <span className="font-medium text-foreground">{data.period.end_date}</span>
          </div>

          {/* ── Profitability ─────────────────────────────────────── */}
          <div>
            <SectionHeader icon={TrendingUp} title="Profitability Ratios" color="text-green-500" />
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {profitability.map((r) => (
                <RatioCard key={r.label} label={r.label} value={r.value} unit={r.unit} desc={r.desc} />
              ))}
            </div>
          </div>

          {/* ── Efficiency ────────────────────────────────────────── */}
          <div>
            <SectionHeader icon={Activity} title="Efficiency / Activity Ratios" color="text-blue-500" />
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {efficiency.map((r) => (
                <RatioCard key={r.label} label={r.label} value={r.value} unit={r.unit} desc={r.desc} />
              ))}
            </div>
          </div>

          {/* ── Leverage ──────────────────────────────────────────── */}
          <div>
            <SectionHeader icon={Scale} title="Leverage / Solvency Ratios" color="text-orange-500" />
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {leverage.map((r) => (
                <RatioCard key={r.label} label={r.label} value={r.value} unit={r.unit} desc={r.desc} />
              ))}
            </div>
          </div>

          {/* ── Base Data ─────────────────────────────────────────── */}
          {base && (
            <div>
              <SectionHeader icon={BarChart2} title="Base Data Summary" color="text-primary" />
              <div className="rounded-lg border border-border bg-card p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8">
                <div>
                  <BaseDataRow label="Sales Revenue"    value={base.sales_revenue} />
                  <BaseDataRow label="COGS"             value={base.cogs} />
                  <BaseDataRow label="Gross Profit"     value={base.gross_profit} />
                  <BaseDataRow label="Total Expenses"   value={base.total_expenses} />
                  <BaseDataRow label="Net Profit"       value={base.net_profit} />
                </div>
                <div>
                  <BaseDataRow label="Opening Stock"    value={base.opening_stock} />
                  <BaseDataRow label="Closing Stock"    value={base.closing_stock} />
                  <BaseDataRow label="Avg Inventory"    value={base.avg_inventory} />
                  <BaseDataRow label="Purchases"        value={base.purchases} />
                </div>
                <div>
                  <BaseDataRow label="Total Assets"     value={base.total_assets} />
                  <BaseDataRow label="Total Liabilities" value={base.total_liabilities} />
                  <BaseDataRow label="Equity"           value={base.equity} />
                  <BaseDataRow label="Total Debtors"    value={base.total_debtors} />
                  <BaseDataRow label="Total Creditors"  value={base.total_creditors} />
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-16 text-muted-foreground text-sm">
          Select a date range and click <strong>Generate Ratios</strong> to view financial ratios.
        </div>
      )}
    </div>
  );
}
