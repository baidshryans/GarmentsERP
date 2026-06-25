import React, { useState, useEffect } from 'react';
import { formatNumber } from '@/lib/format';
import { useSearchParams } from 'react-router-dom';
import {
  ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import {
  useReactTable, getCoreRowModel, getSortedRowModel, getPaginationRowModel, flexRender,
} from '@tanstack/react-table';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import VendorFilterBar from '../components/VendorFilterBar';
import SplitLayout from '../components/SplitLayout';
import { fetchVendorItemPerformance } from '@/services/apiService';

// ─── Chart ────────────────────────────────────────────────────────────────────

function ItemPerfChart({ data, onFilter }) {
  const chartData = data.items.map((item) => ({
    name: item.item_name,
    purchase_cost: item.purchase_cost,
    sale_value: item.sale_value,
    margin_pct: item.margin_pct,
  }));

  return (
    <div>
      <p className="text-sm font-medium mb-2">Purchase Cost vs Sale Value with Margin %</p>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            onClick={(e) => e?.activeLabel && onFilter(e.activeLabel)}
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 10 }}
              tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 10 }}
              tickFormatter={(v) => `${v}%`}
            />
            <Tooltip />
            <Legend />
            <Bar yAxisId="left" dataKey="purchase_cost" name="Purchase Cost" fill="#94a3b8" />
            <Bar yAxisId="left" dataKey="sale_value" name="Sale Value" fill="#6366f1" />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="margin_pct"
              name="Margin %"
              stroke="#22c55e"
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Table ────────────────────────────────────────────────────────────────────

const columns = [
  { accessorKey: 'item_name', header: 'Item' },
  {
    accessorKey: 'gw_purchased',
    header: 'GW Purchased (g)',
    cell: ({ getValue }) => Number(getValue()).toFixed(3),
  },
  {
    accessorKey: 'gw_sold',
    header: 'GW Sold (g)',
    cell: ({ getValue }) => Number(getValue()).toFixed(3),
  },
  {
    accessorKey: 'weight_loss_gm',
    header: 'Loss (g)',
    cell: ({ getValue }) => Number(getValue()).toFixed(3),
  },
  {
    accessorKey: 'weight_loss_pct',
    header: 'Loss %',
    cell: ({ getValue }) => `${Number(getValue()).toFixed(1)}%`,
  },
  {
    accessorKey: 'purchase_cost',
    header: 'Purchase Cost',
    cell: ({ getValue }) =>
      `₹${formatNumber(getValue(), { maxDecimals: 0 })}`,
  },
  {
    accessorKey: 'sale_value',
    header: 'Sale Value',
    cell: ({ getValue }) =>
      `₹${formatNumber(getValue(), { maxDecimals: 0 })}`,
  },
  {
    accessorKey: 'gross_margin',
    header: 'Gross Margin',
    cell: ({ getValue }) =>
      `₹${formatNumber(getValue(), { maxDecimals: 0 })}`,
  },
  {
    accessorKey: 'margin_pct',
    header: 'Margin %',
    cell: ({ getValue }) => {
      const v = Number(getValue());
      return (
        <span className={v >= 0 ? 'text-green-600' : 'text-red-600'}>{v.toFixed(1)}%</span>
      );
    },
  },
  { accessorKey: 'pcs_purchased', header: 'Pcs' },
  { accessorKey: 'pcs_returned', header: 'Returned' },
  { accessorKey: 'pcs_sold', header: 'Sold' },
];

function ItemPerfTable({ data, activeFilter, onClearFilter }) {
  const rows = activeFilter
    ? data.items.filter((r) => r.item_name === activeFilter)
    : data.items;

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

export default function ItemPerformanceReport() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState(null);

  const initialVendorId = searchParams.get('vendor_id') || '';

  const handleApply = async (filters) => {
    setActiveFilter(null);
    setLoading(true);
    const res = await fetchVendorItemPerformance(filters);
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
      title="Item Performance Report"
      filterBar={<VendorFilterBar onApply={handleApply} loading={loading} />}
      loading={loading}
      empty={!data && !loading}
      chartHeight="h-auto"
      chart={data && <ItemPerfChart data={data} onFilter={setActiveFilter} />}
      table={
        data && (
          <ItemPerfTable
            data={data}
            activeFilter={activeFilter}
            onClearFilter={() => setActiveFilter(null)}
          />
        )
      }
    />
  );
}
