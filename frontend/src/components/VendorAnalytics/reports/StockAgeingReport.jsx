import React, { useState, useEffect } from 'react';
import { formatNumber, getFormatConfig } from '@/lib/format';
import { useSearchParams } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  useReactTable, getCoreRowModel, getSortedRowModel, getPaginationRowModel, flexRender,
} from '@tanstack/react-table';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import VendorFilterBar from '../components/VendorFilterBar';
import SplitLayout from '../components/SplitLayout';
import { fetchVendorStockAgeing } from '@/services/apiService';

// ─── Chart ────────────────────────────────────────────────────────────────────

const BUCKET_COLORS = {
  '0_30': '#22c55e',
  '31_60': '#eab308',
  '61_90': '#f97316',
  '90_plus': '#ef4444',
};

function StockAgeingChart({ data, onFilter }) {
  const chartData = data.by_item.map((item) => ({
    name: item.item_name,
    '0-30d': item['0_30'],
    '31-60d': item['31_60'],
    '61-90d': item['61_90'],
    '90+d': item['90_plus'],
  }));

  return (
    <div>
      <p className="text-sm font-medium mb-2">Stock by Item &amp; Age (Pieces)</p>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            onClick={(e) => e?.activePayload && onFilter(e.activeLabel)}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Bar dataKey="0-30d" stackId="a" fill={BUCKET_COLORS['0_30']} />
            <Bar dataKey="31-60d" stackId="a" fill={BUCKET_COLORS['31_60']} />
            <Bar dataKey="61-90d" stackId="a" fill={BUCKET_COLORS['61_90']} />
            <Bar dataKey="90+d" stackId="a" fill={BUCKET_COLORS['90_plus']} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* Summary badges */}
      <div className="flex gap-4 mt-3 text-sm flex-wrap">
        <span className="text-green-600">0-30d: {data.summary['0_30']} pcs</span>
        <span className="text-yellow-600">31-60d: {data.summary['31_60']} pcs</span>
        <span className="text-orange-600">61-90d: {data.summary['61_90']} pcs</span>
        <span className="text-red-600">90+d: {data.summary['90_plus']} pcs</span>
        <span className="font-medium ml-auto">Ageing Score: {data.summary.ageing_score}%</span>
      </div>
    </div>
  );
}

// ─── Table ────────────────────────────────────────────────────────────────────

const columns = [
  { accessorKey: 'barcode', header: 'Barcode' },
  { accessorKey: 'item', header: 'Item' },
  { accessorKey: 'design_code', header: 'Design Code' },
  { accessorKey: 'purchase_date', header: 'Purchase Date' },
  {
    accessorKey: 'age_days',
    header: 'Age (Days)',
    cell: ({ getValue }) => {
      const v = getValue();
      const cls = v > 60 ? 'text-red-600 font-medium' : v > 30 ? 'text-amber-600' : 'text-green-600';
      return <span className={cls}>{v}</span>;
    },
  },
  {
    accessorKey: 'gw',
    header: 'GW (g)',
    cell: ({ getValue }) => Number(getValue()).toFixed(3),
  },
  {
    accessorKey: 'value',
    header: `Value (${getFormatConfig().symbol})`,
    cell: ({ getValue }) =>
      `₹${formatNumber(getValue(), { maxDecimals: 0 })}`,
  },
];

function StockAgeingTable({ data, activeFilter, onClearFilter }) {
  const rows = activeFilter
    ? data.by_barcode.filter((r) => r.item === activeFilter)
    : data.by_barcode;

  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 50 } },
  });

  return (
    <div>
      {activeFilter && (
        <div className="flex items-center gap-2 px-4 py-2 bg-muted/50 text-sm">
          Filtered by item: <strong>{activeFilter}</strong>
          <Button variant="ghost" size="sm" onClick={onClearFilter}>
            ✕ Clear
          </Button>
        </div>
      )}
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((hg) => (
            <TableRow key={hg.id}>
              {hg.headers.map((h) => (
                <TableHead
                  key={h.id}
                  className="cursor-pointer select-none"
                  onClick={h.column.getToggleSortingHandler()}
                >
                  {flexRender(h.column.columnDef.header, h.getContext())}
                  {h.column.getIsSorted() === 'asc'
                    ? ' ↑'
                    : h.column.getIsSorted() === 'desc'
                    ? ' ↓'
                    : ''}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map((row) => (
            <TableRow key={row.id}>
              {row.getVisibleCells().map((cell) => (
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <div className="flex items-center justify-between px-4 py-2 border-t text-sm text-muted-foreground">
        <span>
          Page {table.getState().pagination.pageIndex + 1} of {table.getPageCount()} ({rows.length}{' '}
          rows)
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
          >
            Prev
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function StockAgeingReport() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState(null);

  const initialVendorId = searchParams.get('vendor_id') || '';

  const handleApply = async (filters) => {
    setActiveFilter(null);
    setLoading(true);
    const res = await fetchVendorStockAgeing(filters);
    setLoading(false);
    if (res.success) setData(res.data);
  };

  useEffect(() => {
    if (initialVendorId) {
      handleApply({ vendor_id: initialVendorId });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <SplitLayout
      title="Stock Ageing Report"
      filterBar={<VendorFilterBar onApply={handleApply} loading={loading} />}
      loading={loading}
      empty={!data && !loading}
      chartHeight="h-auto"
      chart={data && <StockAgeingChart data={data} onFilter={setActiveFilter} />}
      table={
        data && (
          <StockAgeingTable
            data={data}
            activeFilter={activeFilter}
            onClearFilter={() => setActiveFilter(null)}
          />
        )
      }
    />
  );
}
