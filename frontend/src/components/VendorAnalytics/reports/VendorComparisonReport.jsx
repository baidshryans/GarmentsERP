import React, { useState, useEffect, useCallback } from 'react';
import { formatNumber } from '@/lib/format';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { getLedgers, fetchVendorComparison } from '@/services/apiService';
import {
  ChevronDown, ChevronUp, Users, TrendingUp,
  Package, BarChart2, ArrowUpDown,
} from 'lucide-react';

// ─── helpers ──────────────────────────────────────────────────────────────────

const fmtCcy = (v) =>
  `₹${formatNumber(v, { maxDecimals: 0 })}`;
const fmtPct = (v) => `${Number(v).toFixed(1)}%`;
const fmtDays = (v) => `${Number(v).toFixed(1)}d`;

function fyStartDate() {
  const today = new Date();
  const year = today.getMonth() >= 3 ? today.getFullYear() : today.getFullYear() - 1;
  return `${year}-04-01`;
}
function todayDate() {
  return new Date().toISOString().slice(0, 10);
}

// Indigo palette shades per bar (cycles if >5 vendors)
const BAR_COLORS = ['#6366f1', '#818cf8', '#a5b4fc', '#4f46e5', '#c7d2fe', '#3730a3'];

// ─── KPI summary card ────────────────────────────────────────────────────────

function SummaryCard({ title, value, icon: Icon, sub }) {
  return (
    <div className="relative rounded-xl border border-indigo-100 bg-white shadow-sm p-5 overflow-hidden">
      <div className="absolute -top-5 -right-5 w-16 h-16 bg-indigo-50 rounded-full opacity-60 pointer-events-none" />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-slate-400">{title}</p>
          {Icon && <Icon className="w-4 h-4 text-indigo-400" />}
        </div>
        <p className="text-2xl font-bold text-indigo-700 tracking-tight">{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
      </div>
    </div>
  );
}

// ─── custom chart tooltip ─────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label, fmt }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white/95 backdrop-blur-sm shadow-xl p-3 text-xs min-w-[180px]">
      <p className="font-semibold text-slate-700 mb-2 pb-1 border-b border-slate-100 truncate">{label}</p>
      {payload.map((p) => (
        <div key={p.dataKey} className="flex items-center justify-between gap-4 mt-1">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: p.fill || p.color }} />
            <span className="text-slate-500">{p.name}</span>
          </div>
          <span className="font-semibold text-slate-800">
            {fmt ? fmt(p.value) : p.value}
          </span>
        </div>
      ))}
    </div>
  );
}

// ─── multi-vendor selector ────────────────────────────────────────────────────

function VendorMultiSelect({ vendors, selected, onChange }) {
  const [search, setSearch] = useState('');

  const filtered = vendors.filter((v) =>
    v.ac_name.toLowerCase().includes(search.toLowerCase())
  );

  const toggleAll = () => {
    if (selected.length === vendors.length) onChange([]);
    else onChange(vendors.map((v) => v.id));
  };

  const toggle = (id) => {
    onChange(
      selected.includes(id)
        ? selected.filter((x) => x !== id)
        : [...selected, id]
    );
  };

  const label =
    selected.length === 0
      ? 'All Vendors'
      : selected.length === 1
      ? vendors.find((v) => v.id === selected[0])?.ac_name ?? '1 vendor'
      : `${selected.length} vendors selected`;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="flex items-center gap-2 h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-left shadow-sm hover:bg-accent transition-colors"
          type="button"
        >
          <span className="flex-1 truncate text-slate-700">{label}</span>
          <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-72" align="start">
        {/* Search box — stop dropdown from closing on click */}
        <div className="px-2 py-1.5" onPointerDown={(e) => e.stopPropagation()}>
          <Input
            placeholder="Search vendors…"
            className="h-8 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onClick={(e) => e.stopPropagation()}
          />
        </div>
        <DropdownMenuSeparator />
        <div className="max-h-56 overflow-y-auto">
          {/* All vendors toggle */}
          <DropdownMenuCheckboxItem
            checked={selected.length === vendors.length && vendors.length > 0}
            onCheckedChange={toggleAll}
            className="font-medium"
          >
            All Vendors
          </DropdownMenuCheckboxItem>
          <DropdownMenuSeparator />
          {filtered.map((v) => (
            <DropdownMenuCheckboxItem
              key={v.id}
              checked={selected.includes(v.id)}
              onCheckedChange={() => toggle(v.id)}
            >
              <span className="truncate">{v.ac_name}</span>
            </DropdownMenuCheckboxItem>
          ))}
          {filtered.length === 0 && (
            <p className="text-xs text-slate-400 px-2 py-2">No vendors found</p>
          )}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

// ─── sortable table header cell ───────────────────────────────────────────────

function SortableTH({ label, colKey, sortKey, sortDir, onSort, className = '' }) {
  const active = sortKey === colKey;
  return (
    <TableHead
      className={`cursor-pointer select-none text-[11px] font-semibold uppercase tracking-wide ${
        active ? 'text-indigo-600' : 'text-slate-400'
      } ${className}`}
      onClick={() => onSort(colKey)}
    >
      <div className="flex items-center gap-1">
        {label}
        {active
          ? sortDir === 'asc'
            ? <ChevronUp className="w-3 h-3" />
            : <ChevronDown className="w-3 h-3" />
          : <ArrowUpDown className="w-3 h-3 opacity-30" />}
      </div>
    </TableHead>
  );
}

// ─── empty state ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-slate-400">
      <div className="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
        <Users className="w-8 h-8 opacity-40" />
      </div>
      <p className="font-medium text-slate-600">No comparison data</p>
      <p className="text-sm mt-1">Select a date range and click Apply</p>
    </div>
  );
}

// ─── compact vendor name for chart axis ──────────────────────────────────────

function shortName(name, maxLen = 18) {
  return name.length > maxLen ? name.slice(0, maxLen - 1) + '…' : name;
}

// ─── main component ───────────────────────────────────────────────────────────

const ITEM_TYPES = [
  { value: '__all__', label: 'All' },
  { value: 'M', label: 'Making' },
  { value: 'R', label: 'Raw' },
  { value: 'S', label: 'Studded' },
  { value: 'O', label: 'Other' },
  { value: 'C', label: 'Casting' },
];

export default function VendorComparisonReport() {
  const [vendors, setVendors]       = useState([]);
  const [selectedIds, setSelectedIds] = useState([]); // empty = all
  const [fromDate, setFromDate]     = useState(fyStartDate());
  const [toDate, setToDate]         = useState(todayDate());
  const [itemType, setItemType]     = useState('');
  const [loading, setLoading]       = useState(false);
  const [data, setData]             = useState(null);
  const [sortKey, setSortKey]       = useState('total_purchases');
  const [sortDir, setSortDir]       = useState('desc');
  const [activeVendor, setActiveVendor] = useState(null); // highlight in table

  // Load vendor list once
  useEffect(() => {
    getLedgers({ type: 'VD', page_size: 500 }).then((res) => {
      if (res?.success && res?.data?.results) setVendors(res.data.results);
    });
  }, []);

  const handleApply = useCallback(async () => {
    setLoading(true);
    setActiveVendor(null);
    const filters = {
      vendor_ids: selectedIds.length ? selectedIds : undefined,
      from_date: fromDate || undefined,
      to_date: toDate || undefined,
      item_type: itemType && itemType !== '__all__' ? itemType : undefined,
    };
    const res = await fetchVendorComparison(filters);
    setLoading(false);
    if (res.success) setData(res.data);
  }, [selectedIds, fromDate, toDate, itemType]);

  // Sort handler
  const handleSort = (key) => {
    if (sortKey === key) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('desc'); }
  };

  // Sorted rows
  const sortedRows = data
    ? [...data.vendors].sort((a, b) => {
        const av = a[sortKey] ?? 0;
        const bv = b[sortKey] ?? 0;
        return sortDir === 'asc' ? av - bv : bv - av;
      })
    : [];

  // Summary aggregates
  const totPurchases   = sortedRows.reduce((s, v) => s + v.total_purchases, 0);
  const totStock       = sortedRows.reduce((s, v) => s + v.total_stock_value, 0);
  const avgSellThrough = sortedRows.length
    ? sortedRows.reduce((s, v) => s + v.sell_through_pct, 0) / sortedRows.length
    : 0;
  const avgDays = sortedRows.filter((v) => v.avg_days_to_sell > 0).length
    ? sortedRows.filter((v) => v.avg_days_to_sell > 0)
        .reduce((s, v) => s + v.avg_days_to_sell, 0) /
      sortedRows.filter((v) => v.avg_days_to_sell > 0).length
    : 0;

  // Chart data — top 10 vendors by total_purchases (descending)
  const chartData = [...(data?.vendors ?? [])]
    .sort((a, b) => b.total_purchases - a.total_purchases)
    .slice(0, 10)
    .map((v, i) => ({
      ...v,
      name: shortName(v.vendor_name),
      color: BAR_COLORS[i % BAR_COLORS.length],
    }));

  return (
    <div className="flex flex-col gap-5 p-4">
      <h1 className="text-xl font-semibold text-slate-800">Vendor Comparison</h1>

      {/* ── Filters ── */}
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-end">
          {/* Vendor multi-select */}
          <div className="lg:col-span-1">
            <Label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5 block">
              Vendors
            </Label>
            <VendorMultiSelect
              vendors={vendors}
              selected={selectedIds}
              onChange={setSelectedIds}
            />
          </div>

          {/* Date range */}
          <div>
            <Label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5 block">
              From
            </Label>
            <Input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="h-9 text-sm"
            />
          </div>
          <div>
            <Label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5 block">
              To
            </Label>
            <Input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="h-9 text-sm"
            />
          </div>

          {/* Item type + apply */}
          <div className="flex gap-2 items-end">
            <div className="flex-1">
              <Label className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1.5 block">
                Item Type
              </Label>
              <Select value={itemType || '__all__'} onValueChange={(v) => setItemType(v === '__all__' ? '' : v)}>
                <SelectTrigger className="h-9 text-sm">
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  {ITEM_TYPES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={handleApply}
              disabled={loading}
              className="h-9 bg-indigo-600 hover:bg-indigo-700 text-white px-5 flex-shrink-0"
            >
              {loading ? 'Loading…' : 'Apply'}
            </Button>
          </div>
        </div>
      </div>

      {/* ── Loading skeletons ── */}
      {loading && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      )}

      {/* ── Empty state ── */}
      {!data && !loading && <EmptyState />}

      {/* ── Results ── */}
      {data && !loading && (
        <>
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <SummaryCard
              title="Total Purchases"
              value={fmtCcy(totPurchases)}
              icon={TrendingUp}
              sub={`${sortedRows.length} vendor${sortedRows.length !== 1 ? 's' : ''}`}
            />
            <SummaryCard
              title="Total Stock Value"
              value={fmtCcy(totStock)}
              icon={Package}
              sub="current inventory"
            />
            <SummaryCard
              title="Avg Sell-Through"
              value={fmtPct(avgSellThrough)}
              icon={BarChart2}
              sub="across all vendors"
            />
            <SummaryCard
              title="Avg Days to Sell"
              value={avgDays > 0 ? fmtDays(avgDays) : '—'}
              icon={Users}
              sub="sold items only"
            />
          </div>

          {/* Charts row */}
          {chartData.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

              {/* Total Purchases chart */}
              <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-4">
                <p className="text-sm font-semibold text-slate-700 mb-3">
                  Total Purchases by Vendor
                </p>
                <div style={{ height: Math.max(200, chartData.length * 36) }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
                      onClick={(e) =>
                        e?.activePayload &&
                        setActiveVendor(
                          activeVendor === e.activePayload[0]?.payload?.vendor_id
                            ? null
                            : e.activePayload[0]?.payload?.vendor_id
                        )
                      }
                    >
                      <CartesianGrid strokeDasharray="4 4" stroke="#f1f5f9" horizontal={false} />
                      <XAxis
                        type="number"
                        tick={{ fontSize: 10, fill: '#94a3b8' }}
                        axisLine={false} tickLine={false}
                        tickFormatter={(v) => `₹${(v / 100000).toFixed(0)}L`}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 10, fill: '#64748b' }}
                        axisLine={false} tickLine={false}
                        width={110}
                      />
                      <Tooltip
                        content={<ChartTooltip fmt={fmtCcy} />}
                        cursor={{ fill: '#f8fafc' }}
                      />
                      <Bar dataKey="total_purchases" name="Total Purchases" radius={[0, 4, 4, 0]}>
                        {chartData.map((entry) => (
                          <Cell
                            key={entry.vendor_id}
                            fill={entry.color}
                            opacity={activeVendor && activeVendor !== entry.vendor_id ? 0.35 : 1}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Sell-through chart */}
              <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-4">
                <p className="text-sm font-semibold text-slate-700 mb-3">
                  Sell-Through % by Vendor
                </p>
                <div style={{ height: Math.max(200, chartData.length * 36) }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartData}
                      layout="vertical"
                      margin={{ top: 4, right: 16, left: 4, bottom: 4 }}
                      onClick={(e) =>
                        e?.activePayload &&
                        setActiveVendor(
                          activeVendor === e.activePayload[0]?.payload?.vendor_id
                            ? null
                            : e.activePayload[0]?.payload?.vendor_id
                        )
                      }
                    >
                      <CartesianGrid strokeDasharray="4 4" stroke="#f1f5f9" horizontal={false} />
                      <XAxis
                        type="number"
                        domain={[0, 100]}
                        tick={{ fontSize: 10, fill: '#94a3b8' }}
                        axisLine={false} tickLine={false}
                        tickFormatter={(v) => `${v}%`}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fontSize: 10, fill: '#64748b' }}
                        axisLine={false} tickLine={false}
                        width={110}
                      />
                      <Tooltip
                        content={<ChartTooltip fmt={fmtPct} />}
                        cursor={{ fill: '#f8fafc' }}
                      />
                      <Bar dataKey="sell_through_pct" name="Sell-Through %" radius={[0, 4, 4, 0]}>
                        {chartData.map((entry) => (
                          <Cell
                            key={entry.vendor_id}
                            fill={
                              entry.sell_through_pct >= 70
                                ? '#10b981'  // emerald
                                : entry.sell_through_pct >= 40
                                ? '#f59e0b'  // amber
                                : '#ef4444'  // red
                            }
                            opacity={activeVendor && activeVendor !== entry.vendor_id ? 0.35 : 1}
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[10px] text-slate-400 mt-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1" />≥70% good
                  <span className="inline-block w-2 h-2 rounded-full bg-amber-500 mx-1 ml-3" />40–70% moderate
                  <span className="inline-block w-2 h-2 rounded-full bg-red-500 mx-1 ml-3" />&lt;40% low
                </p>
              </div>
            </div>
          )}

          {/* Comparison table */}
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 bg-slate-50/60 flex items-center justify-between">
              <p className="text-sm font-semibold text-slate-700">
                Vendor Comparison — {sortedRows.length} vendor{sortedRows.length !== 1 ? 's' : ''}
              </p>
              {activeVendor && (
                <button
                  className="text-xs text-indigo-500 hover:text-indigo-700 transition-colors"
                  onClick={() => setActiveVendor(null)}
                >
                  Clear highlight
                </button>
              )}
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-slate-50/60 hover:bg-slate-50/60">
                    <SortableTH
                      label="Vendor"
                      colKey="vendor_name"
                      sortKey={sortKey}
                      sortDir={sortDir}
                      onSort={handleSort}
                      className="min-w-[160px]"
                    />
                    <SortableTH
                      label="Total Purchases"
                      colKey="total_purchases"
                      sortKey={sortKey}
                      sortDir={sortDir}
                      onSort={handleSort}
                      className="text-right"
                    />
                    <SortableTH
                      label="Stock Value"
                      colKey="total_stock_value"
                      sortKey={sortKey}
                      sortDir={sortDir}
                      onSort={handleSort}
                      className="text-right"
                    />
                    <SortableTH
                      label="Total Pcs"
                      colKey="total_pcs"
                      sortKey={sortKey}
                      sortDir={sortDir}
                      onSort={handleSort}
                      className="text-right"
                    />
                    <SortableTH
                      label="Sold Pcs"
                      colKey="sold_pcs"
                      sortKey={sortKey}
                      sortDir={sortDir}
                      onSort={handleSort}
                      className="text-right"
                    />
                    <SortableTH
                      label="Sell Through %"
                      colKey="sell_through_pct"
                      sortKey={sortKey}
                      sortDir={sortDir}
                      onSort={handleSort}
                      className="text-right"
                    />
                    <SortableTH
                      label="Avg Days to Sell"
                      colKey="avg_days_to_sell"
                      sortKey={sortKey}
                      sortDir={sortDir}
                      onSort={handleSort}
                      className="text-right"
                    />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedRows.map((row) => {
                    const isActive = activeVendor === row.vendor_id;
                    const stColor =
                      row.sell_through_pct >= 70
                        ? 'text-emerald-600'
                        : row.sell_through_pct >= 40
                        ? 'text-amber-600'
                        : 'text-red-500';

                    return (
                      <TableRow
                        key={row.vendor_id}
                        className={`cursor-pointer transition-colors ${
                          isActive
                            ? 'bg-indigo-50 hover:bg-indigo-50'
                            : 'hover:bg-slate-50'
                        }`}
                        onClick={() =>
                          setActiveVendor(isActive ? null : row.vendor_id)
                        }
                      >
                        <TableCell className="font-medium text-slate-800">
                          {row.vendor_name}
                        </TableCell>
                        <TableCell className="text-right font-semibold text-slate-700">
                          {fmtCcy(row.total_purchases)}
                        </TableCell>
                        <TableCell className="text-right text-slate-600">
                          {fmtCcy(row.total_stock_value)}
                        </TableCell>
                        <TableCell className="text-right text-slate-600">
                          {row.total_pcs}
                        </TableCell>
                        <TableCell className="text-right text-slate-600">
                          {row.sold_pcs}
                        </TableCell>
                        <TableCell className="text-right">
                          <span className={`font-semibold text-sm ${stColor}`}>
                            {fmtPct(row.sell_through_pct)}
                          </span>
                        </TableCell>
                        <TableCell className="text-right text-slate-500 text-sm">
                          {row.avg_days_to_sell > 0 ? fmtDays(row.avg_days_to_sell) : '—'}
                        </TableCell>
                      </TableRow>
                    );
                  })}

                  {sortedRows.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-10 text-slate-400">
                        No vendors found for the selected filters
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
