import React, { useState, useEffect } from 'react';
import { formatNumber, getFormatConfig } from '@/lib/format';
import { useSearchParams } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer,
} from 'recharts';
import {
  useReactTable, getCoreRowModel, getSortedRowModel, getPaginationRowModel, flexRender,
} from '@tanstack/react-table';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import VendorFilterBar from '../components/VendorFilterBar';
import SplitLayout from '../components/SplitLayout';
import { fetchVendorDesignPerformance } from '@/services/apiService';

// ─── Chart ────────────────────────────────────────────────────────────────────

function barColor(status) {
  if (status === 'fast') return '#22c55e';
  if (status === 'slow') return '#eab308';
  return '#ef4444';
}

function DesignPerfChart({ data, onFilter }) {
  const chartData = [...data.designs]
    .sort((a, b) => b.avg_days_to_sell - a.avg_days_to_sell)
    .slice(0, 20)
    .map((d) => ({
      name: d.design_code || '(none)',
      avg_days: d.avg_days_to_sell,
      status: d.velocity_status,
    }));

  return (
    <div>
      <p className="text-sm font-medium mb-2">Avg Days to Sell by Design Code (Top 20)</p>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            layout="vertical"
            data={chartData}
            onClick={(e) =>
              e?.activePayload &&
              onFilter(e.activeLabel === '(none)' ? '' : e.activeLabel)
            }
          >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              type="number"
              tick={{ fontSize: 11 }}
              label={{ value: 'Days', position: 'insideRight', offset: -5 }}
            />
            <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 10 }} />
            <Tooltip formatter={(v) => [`${v.toFixed(1)} days`, 'Avg Days to Sell']} />
            <Bar dataKey="avg_days">
              {chartData.map((entry, i) => (
                <Cell key={i} fill={barColor(entry.status)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Table ────────────────────────────────────────────────────────────────────

const columns = [
  {
    accessorKey: 'design_code',
    header: 'Design Code',
    cell: ({ getValue }) => getValue() || '(none)',
  },
  { accessorKey: 'item_name', header: 'Item' },
  { accessorKey: 'pcs_purchased', header: 'Purchased' },
  { accessorKey: 'pcs_sold', header: 'Sold' },
  { accessorKey: 'pcs_unsold', header: 'Unsold' },
  {
    accessorKey: 'avg_days_to_sell',
    header: 'Avg Days',
    cell: ({ getValue }) => Number(getValue()).toFixed(1),
  },
  {
    accessorKey: 'total_value',
    header: `Value (${getFormatConfig().symbol})`,
    cell: ({ getValue }) =>
      `₹${formatNumber(getValue(), { maxDecimals: 0 })}`,
  },
  {
    accessorKey: 'velocity_status',
    header: 'Velocity',
    cell: ({ getValue }) => {
      const v = getValue();
      const cls =
        v === 'fast' ? 'text-green-600' : v === 'slow' ? 'text-amber-600' : 'text-red-600';
      return <span className={cls}>{v}</span>;
    },
  },
];

function DesignPerfTable({ data, activeFilter, onClearFilter }) {
  const rows =
    activeFilter !== null
      ? data.designs.filter((d) => (d.design_code || '') === activeFilter)
      : data.designs;

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
      {activeFilter !== null && (
        <div className="flex items-center gap-2 px-4 py-2 bg-muted/50 text-sm">
          Filtered by design: <strong>{activeFilter || '(none)'}</strong>
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

export default function DesignPerformanceReport() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeFilter, setActiveFilter] = useState(null);

  const initialVendorId = searchParams.get('vendor_id') || '';

  const handleApply = async (filters) => {
    setActiveFilter(null);
    setLoading(true);
    const res = await fetchVendorDesignPerformance(filters);
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
      title="Design Performance Report"
      filterBar={<VendorFilterBar onApply={handleApply} loading={loading} />}
      loading={loading}
      empty={!data && !loading}
      chartHeight="h-auto"
      chart={data && <DesignPerfChart data={data} onFilter={setActiveFilter} />}
      table={
        data && (
          <DesignPerfTable
            data={data}
            activeFilter={activeFilter}
            onClearFilter={() => setActiveFilter(null)}
          />
        )
      }
    />
  );
}
