import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import {
  Users,
  IndianRupee,
  Clock,
  AlertCircle,
  CalendarClock,
  ShieldAlert,
  Wallet,
  CheckCircle2,
  TrendingUp,
} from "lucide-react";
import {
  fetchSchemeSummary,
  fetchOverduePayments,
  fetchSchemeDashboardExt,
} from "@/services/apiService";

// ────────────────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────────────────
const inr = (v) => `₹${Number(v || 0).toLocaleString("en-IN")}`;
const inrCompact = (v) => {
  const n = Number(v || 0);
  if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)}Cr`;
  if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)}L`;
  return `₹${n.toLocaleString("en-IN")}`;
};

// Single KPI card primitive — consistent layout, sizing, focus, contrast.
function KpiCard({ icon: Icon, label, value, sub, tone = "slate" }) {
  const tones = {
    slate:  "text-slate-600 bg-slate-50",
    green:  "text-emerald-700 bg-emerald-50",
    blue:   "text-blue-700 bg-blue-50",
    amber:  "text-amber-700 bg-amber-50",
    rose:   "text-rose-700 bg-rose-50",
    red:    "text-red-700 bg-red-100",
  };
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className={`shrink-0 rounded-lg p-2 ${tones[tone]}`}>
            <Icon className="h-5 w-5" aria-hidden="true" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {label}
            </p>
            <p className="mt-1 text-xl font-semibold tabular-nums leading-tight truncate">
              {value}
            </p>
            {sub && (
              <p className="mt-0.5 text-xs text-muted-foreground tabular-nums">{sub}</p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Simple tab strip — pill style, accessible, ≥44px touch target.
function TabStrip({ tabs, active, onChange }) {
  return (
    <div role="tablist" className="inline-flex rounded-md border bg-muted/40 p-0.5">
      {tabs.map((t) => {
        const selected = active === t.key;
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.key)}
            className={
              "px-3 h-8 text-xs font-medium rounded-[5px] transition-colors " +
              (selected
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900")
            }
          >
            {t.label}
            {typeof t.count === "number" && (
              <span
                className={
                  "ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-semibold tabular-nums " +
                  (selected ? "bg-slate-100 text-slate-700" : "bg-white text-slate-500")
                }
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// Empty state — meaningful copy + optional positive icon.
function EmptyState({ icon: Icon = CheckCircle2, text, tone = "muted" }) {
  return (
    <div
      className={
        "flex items-center gap-2 py-6 text-sm " +
        (tone === "positive" ? "text-emerald-700" : "text-muted-foreground")
      }
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      <span>{text}</span>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Page
// ────────────────────────────────────────────────────────────────────────────
export default function SchemeDashboard() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [overdueInstallments, setOverdueInstallments] = useState([]);
  const [ext, setExt] = useState(null);
  const [loading, setLoading] = useState(true);

  const [duesTab, setDuesTab] = useState("7d");
  const [maturityTab, setMaturityTab] = useState("7d");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const [sRes, oRes, eRes] = await Promise.all([
        fetchSchemeSummary(),
        fetchOverduePayments(),
        fetchSchemeDashboardExt(),
      ]);
      if (sRes.success) setSummary(sRes.data);
      if (oRes.success) setOverdueInstallments(Array.isArray(oRes.data) ? oRes.data : []);
      if (eRes.success) setExt(eRes.data);
      setLoading(false);
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </div>
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  // Derived data
  const dues7d = ext?.dues_7d || [];
  const duesMonth = ext?.dues_month || [];
  const maturing7d = ext?.maturing_7d || [];
  const maturingMonth = ext?.maturing_month || [];
  const overdueMatured = ext?.overdue_matured || [];
  const agedAdvances = ext?.aged_advances || [];
  const modeMix = ext?.collections_by_mode_month || {};

  const duesMonthTotal = duesMonth.reduce(
    (s, r) => s + Number(r.installment_amount || 0),
    0,
  );
  const modeTotal = Object.values(modeMix).reduce((s, v) => s + Number(v || 0), 0);

  const dueTabs = [
    { key: "overdue", label: "Overdue", count: overdueInstallments.length },
    { key: "7d", label: "Next 7 Days", count: dues7d.length },
    { key: "month", label: "This Month", count: duesMonth.length },
  ];
  const maturityTabs = [
    { key: "7d", label: "Next 7 Days", count: maturing7d.length },
    { key: "month", label: "This Month", count: maturingMonth.length },
  ];

  // Column defs
  const duesColumns = [
    { accessorKey: "enrollment_no", header: "Enrollment" },
    { accessorKey: "customer", header: "Customer" },
    { accessorKey: "phone", header: "Phone" },
    {
      accessorKey: "installment_amount",
      header: () => <span className="block text-right">Installment</span>,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums">
          {inr(row.original.installment_amount)}
        </span>
      ),
    },
    { accessorKey: "next_due_date", header: "Next Due" },
    {
      id: "progress",
      header: "Paid / Total",
      cell: ({ row }) => (
        <span className="tabular-nums">
          {row.original.payments_made} / {row.original.tenure_months}
        </span>
      ),
    },
  ];

  const overdueInstallColumns = [
    { accessorKey: "customer", header: "Customer" },
    { accessorKey: "scheme", header: "Scheme" },
    {
      accessorKey: "missed_payments",
      header: () => <span className="block text-right">Missed</span>,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums">{row.original.missed_payments}</span>
      ),
    },
    {
      accessorKey: "total_overdue",
      header: () => <span className="block text-right">Overdue Amount</span>,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums font-medium text-rose-700">
          {inr(row.original.total_overdue)}
        </span>
      ),
    },
  ];

  const maturityColumns = [
    { accessorKey: "enrollment_no", header: "Enrollment" },
    { accessorKey: "customer", header: "Customer" },
    { accessorKey: "scheme", header: "Scheme" },
    { accessorKey: "maturity_date", header: "Maturity Date" },
    {
      accessorKey: "total_paid",
      header: () => <span className="block text-right">Accumulated</span>,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums">{inr(row.original.total_paid)}</span>
      ),
    },
  ];

  const overdueMaturedColumns = [
    { accessorKey: "enrollment_no", header: "Enrollment" },
    { accessorKey: "customer", header: "Customer" },
    { accessorKey: "maturity_date", header: "Matured On" },
    {
      accessorKey: "days_overdue",
      header: () => <span className="block text-right">Days Past</span>,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums font-medium text-rose-700">
          {row.original.days_overdue}
        </span>
      ),
    },
    {
      accessorKey: "total_paid",
      header: () => <span className="block text-right">Accumulated</span>,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums">{inr(row.original.total_paid)}</span>
      ),
    },
    {
      id: "action",
      header: "",
      cell: ({ row }) => (
        <Button
          size="sm"
          variant="outline"
          onClick={() => navigate(`/scheme/enrollments/${row.original.enrollment_uuid}/pay`)}
        >
          Open
        </Button>
      ),
    },
  ];

  const agedColumns = [
    { accessorKey: "enrollment_no", header: "Enrollment" },
    { accessorKey: "customer", header: "Customer" },
    { accessorKey: "phone", header: "Phone" },
    { accessorKey: "first_payment_date", header: "First Payment" },
    {
      accessorKey: "days_held",
      header: () => <span className="block text-right">Days Held</span>,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums font-semibold text-red-700">
          {row.original.days_held}
        </span>
      ),
    },
    {
      accessorKey: "total_collected",
      header: () => <span className="block text-right">Total Collected</span>,
      cell: ({ row }) => (
        <span className="block text-right tabular-nums">
          {inr(row.original.total_collected)}
        </span>
      ),
    },
    {
      id: "action",
      header: "",
      cell: ({ row }) => (
        <Button
          size="sm"
          variant="outline"
          onClick={() => navigate(`/scheme/enrollments/${row.original.enrollment_uuid}/pay`)}
        >
          Open
        </Button>
      ),
    },
  ];

  const duesActive =
    duesTab === "overdue" ? overdueInstallments : duesTab === "7d" ? dues7d : duesMonth;
  const duesActiveCols =
    duesTab === "overdue" ? overdueInstallColumns : duesColumns;
  const maturityActive = maturityTab === "7d" ? maturing7d : maturingMonth;

  return (
    <div className="space-y-6">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Gold Scheme Dashboard</h2>
          <p className="text-sm text-muted-foreground">
            As of {ext?.as_of || new Date().toISOString().split("T")[0]}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => navigate("/scheme/master")}>
            Schemes
          </Button>
          <Button size="sm" onClick={() => navigate("/scheme/enrollments")}>
            All Enrollments
          </Button>
        </div>
      </div>

      {/* ── KPI Strip (6 unified cards, no duplicates) ─────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard
          icon={Users}
          label="Active"
          value={summary?.active_enrollments || 0}
          tone="green"
        />
        <KpiCard
          icon={IndianRupee}
          label="Total Collection"
          value={inrCompact(summary?.total_collection)}
          tone="blue"
        />
        <KpiCard
          icon={Wallet}
          label="Due This Month"
          value={inrCompact(duesMonthTotal)}
          sub={`${duesMonth.length} installments`}
          tone="amber"
        />
        <KpiCard
          icon={CalendarClock}
          label="Maturing This Month"
          value={maturingMonth.length}
          sub={maturing7d.length > 0 ? `${maturing7d.length} in 7 days` : "0 in 7 days"}
          tone="amber"
        />
        <KpiCard
          icon={Clock}
          label="Overdue Matured"
          value={overdueMatured.length}
          sub="Awaiting redemption"
          tone="rose"
        />
        <KpiCard
          icon={ShieldAlert}
          label="Aged >365 Days"
          value={agedAdvances.length}
          sub="Regulatory"
          tone="red"
        />
      </div>

      {/* ── Action Required Banner (Aged Advances — regulatory, top priority) */}
      <Card className="border-red-300 shadow-sm">
        <CardHeader className="bg-red-50 border-b border-red-200 py-3">
          <div className="flex items-start gap-3">
            <ShieldAlert className="h-5 w-5 text-red-700 mt-0.5" aria-hidden="true" />
            <div className="flex-1">
              <CardTitle className="text-sm font-semibold text-red-900">
                Aged Advances — Older Than 365 Days
              </CardTitle>
              <p className="text-xs text-red-800 mt-0.5">
                Customer advances older than 365 days must be settled (matured, redeemed, or refunded).
              </p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {agedAdvances.length > 0 ? (
            <DataTable columns={agedColumns} data={agedAdvances} />
          ) : (
            <div className="px-4">
              <EmptyState
                icon={CheckCircle2}
                tone="positive"
                text="No aged advances. All customer balances within policy."
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Operational Row: Dues + Maturities side-by-side ────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Upcoming Dues — with Overdue / 7d / Month tabs */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-amber-600" aria-hidden="true" />
                Installment Dues
              </CardTitle>
              <TabStrip tabs={dueTabs} active={duesTab} onChange={setDuesTab} />
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {duesActive.length > 0 ? (
              <DataTable columns={duesActiveCols} data={duesActive} />
            ) : (
              <div className="px-4">
                <EmptyState
                  tone="positive"
                  text={
                    duesTab === "overdue"
                      ? "No overdue installments."
                      : "No dues in this window."
                  }
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Maturing Schemes — 7d / Month tabs */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base flex items-center gap-2">
                <CalendarClock className="h-4 w-4 text-amber-600" aria-hidden="true" />
                Maturing Schemes
              </CardTitle>
              <TabStrip
                tabs={maturityTabs}
                active={maturityTab}
                onChange={setMaturityTab}
              />
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {maturityActive.length > 0 ? (
              <DataTable columns={maturityColumns} data={maturityActive} />
            ) : (
              <div className="px-4">
                <EmptyState text="No maturities in this window." />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Overdue Matured (action needed, less urgent than aged) ─────────── */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2 text-rose-700">
            <Clock className="h-4 w-4" aria-hidden="true" />
            Matured &amp; Awaiting Redemption
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {overdueMatured.length > 0 ? (
            <DataTable columns={overdueMaturedColumns} data={overdueMatured} />
          ) : (
            <div className="px-4">
              <EmptyState
                tone="positive"
                text="All matured schemes have been redeemed."
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Collections by Payment Mode ─────────────────────────────────────── */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-blue-600" aria-hidden="true" />
              Collections by Payment Mode
            </CardTitle>
            <span className="text-xs text-muted-foreground tabular-nums">
              Total: {inr(modeTotal)} · This Month
            </span>
          </div>
        </CardHeader>
        <CardContent>
          {modeTotal > 0 ? (
            <div className="space-y-3">
              {/* Stacked bar */}
              <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100">
                {Object.entries(modeMix).map(([mode, amt], i) => {
                  const pct = modeTotal > 0 ? (Number(amt) / modeTotal) * 100 : 0;
                  if (pct === 0) return null;
                  const colors = [
                    "bg-blue-500",
                    "bg-emerald-500",
                    "bg-amber-500",
                    "bg-rose-500",
                    "bg-accent-500",
                  ];
                  return (
                    <div
                      key={mode}
                      className={colors[i % colors.length]}
                      style={{ width: `${pct}%` }}
                      title={`${mode}: ${inr(amt)}`}
                    />
                  );
                })}
              </div>
              {/* Legend */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {Object.entries(modeMix).map(([mode, amt], i) => {
                  const colors = [
                    "bg-blue-500",
                    "bg-emerald-500",
                    "bg-amber-500",
                    "bg-rose-500",
                    "bg-accent-500",
                  ];
                  const pct = modeTotal > 0 ? (Number(amt) / modeTotal) * 100 : 0;
                  return (
                    <div key={mode} className="flex items-start gap-2">
                      <span
                        className={`mt-1 h-2.5 w-2.5 rounded-sm shrink-0 ${colors[i % colors.length]}`}
                        aria-hidden="true"
                      />
                      <div className="min-w-0">
                        <p className="text-xs text-muted-foreground">{mode}</p>
                        <p className="text-sm font-semibold tabular-nums">{inr(amt)}</p>
                        <p className="text-[10px] text-muted-foreground tabular-nums">
                          {pct.toFixed(1)}%
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <EmptyState text="No collections recorded this month." />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
