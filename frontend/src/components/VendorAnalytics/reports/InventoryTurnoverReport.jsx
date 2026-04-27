import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import VendorFilterBar from '../components/VendorFilterBar';
import KPICard from '../components/KPICard';
import { fetchVendorInventoryTurnover } from '@/services/apiService';

// ─── Empty State ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
      <p className="text-lg">No data found</p>
      <p className="text-sm">Try adjusting your filters</p>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function InventoryTurnoverReport() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const initialVendorId = searchParams.get('vendor_id') || '';

  const handleApply = async (filters) => {
    setLoading(true);
    const res = await fetchVendorInventoryTurnover(filters);
    setLoading(false);
    if (res.success) setData(res.data);
  };

  useEffect(() => {
    if (initialVendorId) {
      handleApply({ vendor_id: initialVendorId });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold">Inventory Turnover Report</h1>
      <VendorFilterBar onApply={handleApply} loading={loading} />

      {loading && <Skeleton className="h-96 w-full" />}
      {!data && !loading && <EmptyState />}

      {data && (
        <>
          {/* Top: 3-column panels */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Left: KPI cards */}
            <div className="flex flex-col gap-3">
              <KPICard
                title="Turnover Ratio"
                value={Number(data.current_period.turnover_ratio).toFixed(2)}
                color="border-blue-500"
              />
              <KPICard
                title="Days Inventory Outstanding"
                value={`${Number(data.current_period.days_inventory).toFixed(1)}d`}
                subtitle={`COGS ₹${Number(data.current_period.cogs).toLocaleString('en-IN', {
                  maximumFractionDigits: 0,
                })}`}
                color="border-teal-500"
              />
            </div>

            {/* Center: Monthly trend line chart */}
            <div className="rounded-lg border bg-white p-4 shadow-sm">
              <p className="text-sm font-medium mb-2">Monthly Turnover Trend</p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.monthly_trend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="turnover_ratio"
                      stroke="#6366f1"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Right: YoY bar chart */}
            <div className="rounded-lg border bg-white p-4 shadow-sm">
              <p className="text-sm font-medium mb-2">Year-over-Year Comparison</p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.yoy_comparison}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="fy" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="turnover_ratio" fill="#06b6d4" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>

          {/* Bottom: Monthly data table */}
          <div className="rounded-lg border bg-white shadow-sm">
            <div className="p-3 border-b text-sm font-medium">Monthly Breakdown</div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Month</TableHead>
                  <TableHead className="text-right">Turnover Ratio</TableHead>
                  <TableHead className="text-right">Days Inventory</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.monthly_trend.map((row) => (
                  <TableRow key={row.month}>
                    <TableCell>{row.month}</TableCell>
                    <TableCell className="text-right">
                      {Number(row.turnover_ratio).toFixed(2)}
                    </TableCell>
                    <TableCell className="text-right">
                      {Number(row.days_inventory).toFixed(1)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </>
      )}
    </div>
  );
}
