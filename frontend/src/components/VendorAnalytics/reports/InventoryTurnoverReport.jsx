import React, { useState, useEffect } from 'react';
import { formatNumber } from '@/lib/format';
import { useSearchParams } from 'react-router-dom';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import VendorFilterBar from '../components/VendorFilterBar';
import { fetchVendorInventoryTurnover } from '@/services/apiService';
import { Activity, Package, X } from 'lucide-react';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const fmtRatio = (v) => Number(v).toFixed(2);
const fmtDays  = (v) => `${Number(v).toFixed(1)}d`;
const fmtCcy   = (v) =>
  `₹${formatNumber(v, { maxDecimals: 0 })}`;

// ─── Metric Card ──────────────────────────────────────────────────────────────

const ACCENTS = {
  indigo: {
    border : 'border-indigo-200',
    blob   : 'bg-indigo-100',
    label  : 'text-indigo-400',
    value  : 'text-indigo-700',
  },
  teal: {
    border : 'border-teal-200',
    blob   : 'bg-teal-100',
    label  : 'text-teal-400',
    value  : 'text-teal-700',
  },
};

function MetricCard({ title, value, sub, icon: Icon, accent = 'indigo' }) {
  const c = ACCENTS[accent] ?? ACCENTS.indigo;
  return (
    <div className={`relative rounded-xl border ${c.border} bg-white shadow-sm p-5 overflow-hidden`}>
      {/* decorative blob */}
      <div
        className={`absolute -top-6 -right-6 w-20 h-20 ${c.blob} rounded-full opacity-50 pointer-events-none`}
      />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">{title}</p>
          {Icon && <Icon className={`w-4 h-4 ${c.label}`} />}
        </div>
        <p className={`text-3xl font-bold tracking-tight ${c.value}`}>{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
      </div>
    </div>
  );
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label, fmt }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white/95 backdrop-blur-sm shadow-xl p-3 text-xs min-w-[160px]">
      <p className="font-semibold text-slate-700 mb-2 pb-1 border-b border-slate-100">{label}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-6 mt-1">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: p.color }} />
            <span className="text-slate-500">{p.name}</span>
          </div>
          <span className="font-semibold text-slate-800">
            {fmt ? fmt(p.value, p.dataKey) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── Empty State ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-slate-400">
      <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
        <Package className="w-8 h-8 opacity-50" />
      </div>
      <p className="font-medium text-slate-600">No turnover data</p>
      <p className="text-sm mt-1">Select a vendor and date range, then click Apply</p>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function InventoryTurnoverReport() {
  const [searchParams] = useSearchParams();
  const [data, setData]               = useState(null);
  const [loading, setLoading]         = useState(false);
  const [activeMonth, setActiveMonth] = useState(null);

  const initialVendorId = searchParams.get('vendor_id') || '';

  const handleApply = async (filters) => {
    setLoading(true);
    const res = await fetchVendorInventoryTurnover(filters);
    setLoading(false);
    if (res.success) { setData(res.data); setActiveMonth(null); }
  };

  useEffect(() => {
    if (initialVendorId) handleApply({ vendor_id: initialVendorId });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const tooltipFmt = (v, key) =>
    key === 'days_inventory' ? fmtDays(v) : fmtRatio(v);

  return (
    <div className="flex flex-col gap-5 p-4">
      <h1 className="text-xl font-semibold text-slate-800">Inventory Turnover</h1>

      <VendorFilterBar onApply={handleApply} loading={loading} />

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-56 rounded-xl" />
          ))}
        </div>
      )}

      {!data && !loading && <EmptyState />}

      {data && (
        <>
          {/* ── Top row ── */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-start">

            {/* KPI column */}
            <div className="flex flex-col gap-3">
              <MetricCard
                title="Turnover Ratio"
                value={fmtRatio(data.current_period.turnover_ratio)}
                sub={`Avg Inventory ${fmtCcy(data.current_period.avg_inventory)}`}
                icon={Activity}
                accent="indigo"
              />
              <MetricCard
                title="Days Inventory Outstanding"
                value={fmtDays(data.current_period.days_inventory)}
                sub={`COGS ${fmtCcy(data.current_period.cogs)}`}
                icon={Package}
                accent="teal"
              />
            </div>

            {/* Monthly AreaChart */}
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-4">
              <p className="text-sm font-semibold text-slate-700 mb-3">Monthly Turnover Trend</p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={data.monthly_trend}
                    margin={{ top: 6, right: 6, left: -8, bottom: 0 }}
                    onClick={(e) => e?.activeLabel && setActiveMonth(
                      activeMonth === e.activeLabel ? null : e.activeLabel
                    )}
                  >
                    <defs>
                      <linearGradient id="turnoverGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.18} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 4" stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tick={{ fontSize: 10, fill: '#94a3b8' }}
                      axisLine={false} tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: '#94a3b8' }}
                      axisLine={false} tickLine={false}
                    />
                    <Tooltip
                      content={<ChartTooltip fmt={tooltipFmt} />}
                      cursor={{ stroke: '#6366f1', strokeWidth: 1, strokeDasharray: '3 3' }}
                    />
                    <Area
                      type="monotone"
                      dataKey="turnover_ratio"
                      name="Turnover Ratio"
                      stroke="#6366f1"
                      strokeWidth={2.5}
                      fill="url(#turnoverGrad)"
                      dot={{ r: 3.5, fill: '#6366f1', stroke: '#fff', strokeWidth: 1.5 }}
                      activeDot={{ r: 6, fill: '#6366f1', stroke: '#e0e7ff', strokeWidth: 3 }}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              {data.monthly_trend.length > 0 && (
                <p className="text-[10px] text-slate-400 mt-2 text-center">
                  Click a point to highlight that month in the table
                </p>
              )}
            </div>

            {/* YoY BarChart */}
            <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-4">
              <p className="text-sm font-semibold text-slate-700 mb-3">Year-over-Year Comparison</p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={data.yoy_comparison}
                    margin={{ top: 6, right: 6, left: -8, bottom: 0 }}
                    barSize={48}
                  >
                    <defs>
                      <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%"   stopColor="#6366f1" stopOpacity={0.9} />
                        <stop offset="100%" stopColor="#a5b4fc" stopOpacity={0.55} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="4 4" stroke="#f1f5f9" vertical={false} />
                    <XAxis
                      dataKey="fy"
                      tick={{ fontSize: 11, fill: '#94a3b8' }}
                      axisLine={false} tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: '#94a3b8' }}
                      axisLine={false} tickLine={false}
                    />
                    <Tooltip
                      content={<ChartTooltip fmt={(v) => fmtRatio(v)} />}
                      cursor={{ fill: '#f8fafc', radius: 4 }}
                    />
                    <Bar
                      dataKey="turnover_ratio"
                      name="Turnover Ratio"
                      fill="url(#barGrad)"
                      radius={[6, 6, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* ── Monthly breakdown table ── */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between bg-slate-50/60">
              <p className="text-sm font-semibold text-slate-700">Monthly Breakdown</p>
              {activeMonth && (
                <button
                  className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 transition-colors"
                  onClick={() => setActiveMonth(null)}
                >
                  <X className="w-3 h-3" /> Clear filter
                </button>
              )}
            </div>
            <Table>
              <TableHeader>
                <TableRow className="bg-slate-50/60 hover:bg-slate-50/60">
                  <TableHead className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">Month</TableHead>
                  <TableHead className="text-right text-[11px] font-semibold uppercase tracking-wide text-slate-400">Turnover Ratio</TableHead>
                  <TableHead className="text-right text-[11px] font-semibold uppercase tracking-wide text-slate-400">Days Inventory</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(activeMonth
                  ? data.monthly_trend.filter((r) => r.month === activeMonth)
                  : data.monthly_trend
                ).map((row) => {
                  const isGood = row.turnover_ratio >= 4;
                  const isActive = activeMonth === row.month;
                  return (
                    <TableRow
                      key={row.month}
                      className={`cursor-pointer transition-colors ${
                        isActive
                          ? 'bg-indigo-50 hover:bg-indigo-50'
                          : 'hover:bg-slate-50'
                      }`}
                      onClick={() => setActiveMonth(isActive ? null : row.month)}
                    >
                      <TableCell className="font-medium text-slate-700">{row.month}</TableCell>
                      <TableCell className="text-right">
                        <span
                          className={`inline-flex items-center gap-1 font-semibold text-sm ${
                            isGood ? 'text-emerald-600' : 'text-amber-600'
                          }`}
                        >
                          {fmtRatio(row.turnover_ratio)}
                        </span>
                      </TableCell>
                      <TableCell className="text-right text-slate-500 text-sm">
                        {fmtDays(row.days_inventory)}
                      </TableCell>
                    </TableRow>
                  );
                })}
                {data.monthly_trend.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center py-8 text-slate-400">
                      No monthly data available
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  );
}
