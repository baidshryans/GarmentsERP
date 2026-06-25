import React, { useState } from 'react';
import { formatMoney, formatNumber } from '@/lib/format';
import { useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import VendorFilterBar from './components/VendorFilterBar';
import KPICard from './components/KPICard';
import { fetchVendorDashboard } from '@/services/apiService';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

function fmt(v, type = 'number') {
  if (v === undefined || v === null) return '—';
  if (type === 'currency') return formatMoney(v, { decimals: 0, space: false });
  if (type === 'pct') return `${Number(v).toFixed(1)}%`;
  if (type === 'days') return `${Number(v).toFixed(1)}d`;
  if (type === 'ratio') return Number(v).toFixed(2);
  return String(v);
}

export default function VendorDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [currentFilters, setCurrentFilters] = useState({});

  const handleApply = async (filters) => {
    setCurrentFilters(filters);
    setLoading(true);
    setError(null);
    const res = await fetchVendorDashboard(filters);
    setLoading(false);
    if (res.success) setData(res.data);
    else setError(res.error?.detail || 'Failed to load dashboard');
  };

  const vendorId = currentFilters.vendor_id;

  const fin = data?.financial ?? {};
  const inv = data?.inventory ?? {};
  const perf = data?.performance ?? {};

  // last 6 months of trend for mini chart
  const trendData = (data?.monthly_purchase_trend ?? []).slice(-6);

  return (
    <div className="flex flex-col gap-6 p-4">
      <h1 className="text-xl font-semibold">Vendor Dashboard</h1>

      <VendorFilterBar onApply={handleApply} loading={loading} />

      {loading && (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-3 gap-4">
            {Array(9).fill(0).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
          <Skeleton className="h-48 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      )}

      {!loading && !data && (
        <div className="flex items-center justify-center py-20 text-muted-foreground">
          Select a vendor and click Apply to load the dashboard
        </div>
      )}

      {!loading && error && (
        <div className="text-red-500 text-sm p-4 border border-red-200 rounded">{error}</div>
      )}

      {!loading && data && (
        <>
          {/* Row 1: Financial KPIs */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Financial</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <KPICard title="Total Purchases" value={fmt(fin.total_purchases, 'currency')} color="border-blue-500" />
              <KPICard title="Outstanding Payable" value={fmt(fin.outstanding_payable, 'currency')} color="border-orange-400" />
              <KPICard title="Avg Payment Days" value={fmt(fin.avg_payment_days, 'days')} color="border-purple-400" />
            </div>
          </div>

          {/* Row 2: Inventory KPIs */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Inventory</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <KPICard
                title="Total Stock Value"
                value={fmt(inv.total_stock_value, 'currency')}
                color="border-teal-500"
                navigateTo="/vendor-analytics/stock-ageing"
                navParams={{ vendor_id: vendorId }}
              />
              <KPICard
                title="Ageing Score"
                value={fmt(inv.ageing_score, 'pct')}
                color="border-amber-500"
                variant={inv.ageing_score > 50 ? 'danger' : inv.ageing_score > 25 ? 'warning' : 'success'}
                navigateTo="/vendor-analytics/stock-ageing"
                navParams={{ vendor_id: vendorId }}
              />
              <KPICard
                title="Turnover Ratio"
                value={fmt(inv.turnover_ratio, 'ratio')}
                color="border-cyan-500"
                navigateTo="/vendor-analytics/inventory-turnover"
                navParams={{ vendor_id: vendorId }}
              />
            </div>
          </div>

          {/* Row 3: Performance KPIs */}
          <div>
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Performance</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <KPICard
                title="Best Design"
                value={perf.best_design || '—'}
                color="border-green-500"
                navigateTo="/vendor-analytics/design-performance"
                navParams={{ vendor_id: vendorId }}
              />
              <KPICard
                title="Sell-Through %"
                value={fmt(perf.sell_through_pct, 'pct')}
                variant={perf.sell_through_pct > 70 ? 'success' : perf.sell_through_pct > 40 ? 'default' : 'warning'}
                color="border-lime-500"
                navigateTo="/vendor-analytics/design-performance"
                navParams={{ vendor_id: vendorId }}
              />
              <KPICard
                title="Avg Days to Sell"
                value={fmt(perf.avg_days_to_sell, 'days')}
                color="border-pink-400"
                navigateTo="/vendor-analytics/design-performance"
                navParams={{ vendor_id: vendorId }}
              />
            </div>
          </div>

          {/* Mini purchase trend chart */}
          {trendData.length > 0 && (
            <div className="rounded-lg border bg-white p-4 shadow-sm">
              <p className="text-sm font-medium mb-3">Monthly Purchase Trend (Last 6 Months)</p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={trendData} margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                    <Tooltip formatter={(v) => [`₹${formatNumber(v)}`, 'Purchases']} />
                    <Bar dataKey="value" fill="#6366f1" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Top designs table */}
          {data.top_designs?.length > 0 && (
            <div className="rounded-lg border bg-white shadow-sm">
              <div className="p-4 border-b">
                <p className="text-sm font-medium">Top 5 Designs by Sold Pieces</p>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Design Code</TableHead>
                    <TableHead className="text-right">Sold Pcs</TableHead>
                    <TableHead className="text-right">Avg Days to Sell</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_designs.map((d) => (
                    <TableRow
                      key={d.design_code}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/vendor-analytics/design-performance?vendor_id=${vendorId}`)}
                    >
                      <TableCell className="font-mono">{d.design_code || '(no design)'}</TableCell>
                      <TableCell className="text-right">{d.sold_pcs}</TableCell>
                      <TableCell className="text-right">{fmt(d.avg_days, 'days')}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
