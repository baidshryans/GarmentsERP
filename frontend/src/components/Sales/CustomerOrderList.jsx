import React, { useState, useEffect, useCallback } from 'react';
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { fetchCustomerOrders, fetchDeliveryOverview, updateOrderDeliveryStatus, fetchCustomerOrderForEdit, cancelCustomerOrder } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { SquarePen, Printer, Trash2, AlertTriangle, Clock, CheckCircle2, Truck, Bell, X, LayoutDashboard, Ban, Lock } from "lucide-react";
import { openAndPrint } from '@/services/print/utils';
import CustomerOrder from '@/services/print/CustomerOrder';
import { useToast } from "@/hooks/use-toast";
import { deleteCustomerOrder } from '../../services/apiService';
import { useSearchParams } from 'react-router-dom';
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter,
} from "@/components/ui/sheet";

// ── Helpers ────────────────────────────────────────────────────────────────────

const DELIVERY_STATUS_OPTIONS = [
  { value: 'pending',   label: 'Pending',              color: 'bg-violet-100 text-primary' },
  { value: 'ready',     label: 'Ready for Delivery',   color: 'bg-sky-100 text-sky-800' },
  { value: 'delivered', label: 'Delivered',             color: 'bg-emerald-100 text-emerald-800' },
  { value: 'cancelled', label: 'Cancelled',             color: 'bg-gray-100 text-gray-600' },
];

function deliveryStatusMeta(v) {
  return DELIVERY_STATUS_OPTIONS.find(o => o.value === v) ?? DELIVERY_STATUS_OPTIONS[0];
}

function fmtDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-GB').replaceAll('/', '-');
}

function DeliveryDateCell({ row }) {
  const { delivery_date, delivery_status, is_overdue, days_overdue } = row.original;
  if (!delivery_date) return <span className="text-xs text-muted-foreground">—</span>;

  const today    = new Date(new Date().toDateString());
  const due      = new Date(delivery_date);
  const diffDays = Math.round((due - today) / 86400000);

  if (delivery_status === 'delivered' || delivery_status === 'cancelled') {
    return <span className="text-xs text-muted-foreground">{fmtDate(delivery_date)}</span>;
  }

  if (is_overdue) {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="text-xs font-semibold text-red-600">{fmtDate(delivery_date)}</span>
        <span className="text-[10px] text-red-500 flex items-center gap-0.5">
          <AlertTriangle className="w-2.5 h-2.5" />{days_overdue}d overdue
        </span>
      </div>
    );
  }
  if (diffDays === 0) {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="text-xs font-semibold text-amber-600">{fmtDate(delivery_date)}</span>
        <span className="text-[10px] text-amber-500 font-medium">Due today</span>
      </div>
    );
  }
  if (diffDays <= 3) {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="text-xs font-semibold text-amber-600">{fmtDate(delivery_date)}</span>
        <span className="text-[10px] text-amber-400">{diffDays}d left</span>
      </div>
    );
  }
  return <span className="text-xs">{fmtDate(delivery_date)}</span>;
}

// ── Overdue Alert Banner ───────────────────────────────────────────────────────

function OverdueBanner({ overview, onDismiss }) {
  if (!overview || overview.overdue_count === 0) return null;

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex gap-3">
      <Bell className="size-5 text-red-600 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-red-800">
          {overview.overdue_count} order{overview.overdue_count !== 1 ? 's' : ''} overdue
        </p>
        <div className="mt-2 space-y-1">
          {overview.overdue_orders.map(o => (
            <div key={o.id} className="flex items-center gap-2 text-xs text-red-700">
              <span className="font-mono font-medium">{o.order_no}</span>
              <span className="text-red-400">·</span>
              <span className="truncate">{o.customer}</span>
              <span className="text-red-400">·</span>
              <span className="shrink-0">due {fmtDate(o.delivery_date)}</span>
              <span className="inline-flex items-center gap-0.5 bg-red-100 text-red-700 rounded px-1 font-semibold shrink-0">
                <AlertTriangle className="w-2.5 h-2.5" />{o.days_overdue}d
              </span>
              <Link to={`${o.id}`} className="text-red-600 underline shrink-0">Open</Link>
            </div>
          ))}
          {overview.overdue_count > overview.overdue_orders.length && (
            <p className="text-xs text-red-500 italic">
              …and {overview.overdue_count - overview.overdue_orders.length} more
            </p>
          )}
        </div>
      </div>
      <button onClick={onDismiss} className="shrink-0 text-red-400 hover:text-red-600">
        <X className="size-4" />
      </button>
    </div>
  );
}

// ── KPI Strip ──────────────────────────────────────────────────────────────────

function KpiStrip({ overview }) {
  if (!overview) return null;
  const cards = [
    { label: 'Overdue',        value: overview.overdue_count,        icon: <AlertTriangle className="size-4" />, color: 'text-red-600 bg-red-50 border-red-100' },
    { label: 'Due Today',      value: overview.due_today_count,       icon: <Clock className="size-4" />,         color: 'text-amber-600 bg-amber-50 border-amber-100' },
    { label: 'Due This Week',  value: overview.due_this_week_count,   icon: <Bell className="size-4" />,          color: 'text-sky-600 bg-sky-50 border-sky-100' },
    { label: 'All Open',       value: overview.pending_count,         icon: <Truck className="size-4" />,         color: 'text-primary bg-violet-50 border-violet-100' },
    { label: 'Delivered (Mo)', value: overview.delivered_this_month,  icon: <CheckCircle2 className="size-4" />, color: 'text-emerald-600 bg-emerald-50 border-emerald-100' },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
      {cards.map(c => (
        <div key={c.label} className={`rounded-lg border p-3 flex items-center gap-2 ${c.color}`}>
          <div className="shrink-0">{c.icon}</div>
          <div>
            <p className="text-lg font-bold leading-none">{c.value}</p>
            <p className="text-[10px] text-muted-foreground mt-0.5">{c.label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Quick Status Update Sheet ─────────────────────────────────────────────────

function DeliveryUpdateSheet({ order, open, onClose, onUpdated }) {
  const { toast }   = useToast();
  const [status, setStatus]     = useState('');
  const [actDate, setActDate]   = useState('');
  const [saving, setSaving]     = useState(false);

  useEffect(() => {
    if (order) {
      setStatus(order.delivery_status || 'pending');
      setActDate(order.actual_delivery_date || '');
    }
  }, [order]);

  const handleSave = async () => {
    setSaving(true);
    const res = await updateOrderDeliveryStatus(order.id, status, actDate || undefined);
    setSaving(false);
    if (res.success) {
      toast({ title: 'Delivery status updated' });
      onUpdated(res.data);
      onClose();
    } else {
      toast({ title: 'Error', description: JSON.stringify(res.error), variant: 'destructive' });
    }
  };

  if (!order) return null;

  return (
    <Sheet open={open} onOpenChange={onClose}>
      <SheetContent side="right" className="sm:max-w-sm" aria-describedby={undefined}>
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Truck className="size-5 text-primary" />
            Update Delivery — {order.order_no}
          </SheetTitle>
        </SheetHeader>

        <div className="flex flex-col gap-4 py-4">
          <div className="text-sm text-muted-foreground">
            <p><span className="font-medium text-foreground">Customer:</span> {order.ldgr_code_name}</p>
            <p><span className="font-medium text-foreground">Promised date:</span> {fmtDate(order.delivery_date)}</p>
            {order.is_overdue && (
              <p className="text-red-600 font-medium flex items-center gap-1 mt-1">
                <AlertTriangle className="w-3.5 h-3.5" />{order.days_overdue} day{order.days_overdue !== 1 ? 's' : ''} overdue
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <Label className="text-xs">Delivery Status</Label>
            <Select value={status} onValueChange={setStatus}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DELIVERY_STATUS_OPTIONS.map(o => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {status === 'delivered' && (
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Actual Delivery Date</Label>
              <Input
                type="date"
                value={actDate}
                onChange={e => setActDate(e.target.value)}
                max={new Date().toISOString().slice(0, 10)}
              />
            </div>
          )}
        </div>

        <SheetFooter className="flex gap-2">
          <Button variant="outline" onClick={onClose} className="flex-1">
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving} className="flex-1">
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

function CustomerOrderList() {
  const { toast } = useToast();
  const [params, setParams]   = useSearchParams();
  const [orders, setOrders]   = useState([]);
  const [overview, setOverview] = useState(null);
  const [bannerDismissed, setBannerDismissed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [page, setPage]       = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Quick-update sheet state
  const [sheetOrder, setSheetOrder] = useState(null);
  const [sheetOpen, setSheetOpen]   = useState(false);

  // Filter by delivery status
  const [deliveryFilter, setDeliveryFilter] = useState('');

  const search = params.get('search') || '';
  const sortby = params.get('sortby') || '';

  // Load order list
  const loadOrders = useCallback(async () => {
    setLoading(true);
    const result = await fetchCustomerOrders({ search, page, ordering: sortby });
    if (result.success) {
      setOrders(result.data.results);
      setTotalPages(result.data.total_pages);
    }
    setLoading(false);
  }, [search, page, sortby]);

  useEffect(() => { loadOrders(); }, [loadOrders]);

  // Load delivery overview stats once on mount
  useEffect(() => {
    fetchDeliveryOverview().then(res => {
      if (res.success) setOverview(res.data);
    });
  }, []);

  const handleUpdated = (updatedOrder) => {
    setOrders(prev => prev.map(o => o.id === updatedOrder.id ? { ...o, ...updatedOrder } : o));
    // Refresh overview counts
    fetchDeliveryOverview().then(res => { if (res.success) setOverview(res.data); });
    setBannerDismissed(false);
  };

  const openSheet = (order) => { setSheetOrder(order); setSheetOpen(true); };

  // Client-side filter by delivery_status
  const visibleOrders = deliveryFilter
    ? orders.filter(o => (o.delivery_status || 'pending') === deliveryFilter)
    : orders;

  // ── Advance badge helper ──────────────────────────────────────────────────
  const advanceBadge = (row) => {
    const advance    = parseFloat(row.advance_amt    || 0);
    const available  = parseFloat(row.advance_available ?? advance);
    const reconciled = parseFloat(row.advance_reconciled || 0);
    if (advance === 0) return null;
    if (available <= 0)
      return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">✓ Reconciled</span>;
    if (reconciled > 0)
      return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">◑ Partial</span>;
    return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-violet-100 text-primary">● Pending</span>;
  };

  // ── Columns ───────────────────────────────────────────────────────────────
  const columns = [
    {
      header: "Action",
      cell: ({ row }) => {
        const o = row.original;
        const isDeletable   = o.is_deletable !== false;
        const isCancellable = o.is_cancellable !== false;
        const editHidden    = ['delivered', 'cancelled'].includes(o.delivery_status);
        return (
        <div className="flex gap-2 items-center">
          {!editHidden && (
            <Link to={`/sales/customerorder/list/${o.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors" title="Edit order">
              <SquarePen className="size-4" />
            </Link>
          )}
          {isCancellable && (
            <button
              onClick={async () => {
                const warnings = [];
                if (o.has_in_production_items) warnings.push("• Some items are still in production with a karigar or supplier.");
                if (o.has_advance)             warnings.push("• Advance receipts will remain on the customer's ledger as a credit.");
                const msg = `Cancel order ${o.order_no}?` + (warnings.length ? `\n\n${warnings.join("\n")}` : "");
                if (!window.confirm(msg)) return;
                const res = await cancelCustomerOrder(o.id);
                if (res.success) {
                  toast({ title: "Order cancelled." });
                  loadOrders();
                } else {
                  toast({ title: "Failed to cancel", description: String(res.error?.detail || res.error), variant: "destructive" });
                }
              }}
              className="p-1.5 rounded text-amber-600 hover:bg-amber-50 transition-colors"
              title="Cancel order"
            >
              <Ban className="size-4" />
            </button>
          )}
          <button
            onClick={() => {
              if (!isDeletable) return;
              if (!window.confirm(`Delete order ${o.order_no}? This cannot be undone.`)) return;
              deleteCustomerOrder(o.id, toast);
            }}
            disabled={!isDeletable}
            className={`p-1.5 rounded transition-colors ${isDeletable ? 'text-red-500 hover:bg-red-50' : 'text-gray-300 cursor-not-allowed'}`}
            title={isDeletable ? "Delete order" : "Cannot delete — a sales voucher has been raised against this order"}
          >
            <Trash2 className="size-4" />
          </button>
          <button
            onClick={() => openSheet(o)}
            className="text-sky-500 hover:text-sky-700"
            title="Update delivery status"
          >
            <Truck className="size-4" />
          </button>
          <button
            title="Print order"
            onClick={async () => {
              const res = await fetchCustomerOrderForEdit(row.original.id);
              if (res.success) {
                openAndPrint(<CustomerOrder data={res.data} />);
              } else {
                toast({ title: "Could not load order details for printing.", variant: "destructive" });
              }
            }}
          >
            <Printer className="size-4 text-muted-foreground" />
          </button>
        </div>
        );
      },
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) => fmtDate(getValue()),
    },
    {
      header: "Customer",
      accessorKey: "ldgr_code_name",
    },
    {
      header: "Order No",
      accessorKey: "order_no",
      cell: ({ row }) => {
        const o = row.original;
        const items = Array.isArray(o.items) ? o.items : [];
        let pill = null;
        if (o.delivery_status === 'cancelled') {
          pill = { label: 'Cancelled', cls: 'bg-gray-200 text-gray-700' };
        } else if (o.delivery_status === 'delivered') {
          pill = { label: 'Delivered', cls: 'bg-emerald-100 text-emerald-800' };
        } else if (items.some(i => i.lock_state === 'billed')) {
          pill = { label: 'Billed', cls: 'bg-sky-100 text-sky-800' };
        } else if (items.some(i => i.lock_state === 'in_production')) {
          pill = { label: 'In Production', cls: 'bg-amber-100 text-amber-800' };
        } else {
          pill = { label: 'Open', cls: 'bg-violet-100 text-primary' };
        }
        return (
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm">{o.order_no}</span>
            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${pill.cls}`}>
              {(pill.label === 'In Production' || pill.label === 'Billed') && <Lock className="w-2.5 h-2.5" />}
              {pill.label}
            </span>
          </div>
        );
      },
    },
    {
      header: "Billing",
      accessorKey: "status",
      cell: ({ row }) => {
        const s = row.original.status;
        const colors = {
          'Billed':  'bg-emerald-100 text-emerald-800',
          'Partial': 'bg-amber-100 text-amber-800',
          'Pending': 'bg-violet-100 text-primary',
        };
        return s
          ? <span className={`inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold ${colors[s] ?? 'bg-gray-100 text-gray-700'}`}>{s}</span>
          : <span className="text-xs text-muted-foreground">—</span>;
      },
    },
    {
      header: "Delivery Status",
      cell: ({ row }) => {
        const r   = row.original;
        const meta = deliveryStatusMeta(r.delivery_status || 'pending');
        return (
          <button
            onClick={() => openSheet(r)}
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold cursor-pointer hover:opacity-80 transition-opacity ${meta.color}`}
            title="Click to update"
          >
            {r.delivery_status === 'delivered'  && <CheckCircle2 className="w-2.5 h-2.5" />}
            {r.delivery_status === 'ready'       && <Truck className="w-2.5 h-2.5" />}
            {r.delivery_status === 'pending'     && <Clock className="w-2.5 h-2.5" />}
            {r.delivery_status === 'cancelled'   && <X className="w-2.5 h-2.5" />}
            {meta.label}
          </button>
        );
      },
    },
    {
      header: "Promised Date",
      cell: ({ row }) => <DeliveryDateCell row={row} />,
    },
    {
      header: "Actual Delivery",
      cell: ({ row }) => {
        const d = row.original.actual_delivery_date;
        return d
          ? <span className="text-xs text-emerald-700 font-medium">{fmtDate(d)}</span>
          : <span className="text-xs text-muted-foreground">—</span>;
      },
    },
    {
      header: "Advance",
      accessorKey: "advance_amt",
      cell: ({ row }) => {
        const adv = parseFloat(row.original.advance_amt || 0);
        if (adv === 0) return <span className="text-xs text-muted-foreground">—</span>;
        return (
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-semibold">₹{adv.toLocaleString('en-IN')}</span>
            {advanceBadge(row.original)}
          </div>
        );
      },
    },
    {
      header: "Bills",
      accessorKey: "linked_bill_count",
      cell: ({ getValue }) => {
        const v = getValue();
        return v > 0
          ? <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-semibold bg-sky-100 text-sky-800">{v} bill{v !== 1 ? 's' : ''}</span>
          : <span className="text-xs text-muted-foreground">—</span>;
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-4">

      {/* Overdue Alert Banner */}
      {!bannerDismissed && (
        <OverdueBanner overview={overview} onDismiss={() => setBannerDismissed(true)} />
      )}

      {/* KPI Strip */}
      <KpiStrip overview={overview} />

      {/* Toolbar */}
      <div className="flex flex-wrap gap-2 items-center justify-between">
        <div className="flex gap-2 flex-wrap">
          <Input
            type="text"
            value={search}
            onChange={e => setParams({ search: e.target.value, sortby })}
            placeholder="Search order / customer…"
            className="w-60"
          />
          <Select value={sortby} onValueChange={v => setParams({ search, sortby: v })}>
            <SelectTrigger className="w-44">
              <SelectValue placeholder="Sort by…" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date1">Date (oldest first)</SelectItem>
              <SelectItem value="-date1">Date (newest first)</SelectItem>
              <SelectItem value="order_no">Order No ↑</SelectItem>
              <SelectItem value="-order_no">Order No ↓</SelectItem>
              <SelectItem value="delivery_date">Delivery Date ↑</SelectItem>
              <SelectItem value="-delivery_date">Delivery Date ↓</SelectItem>
            </SelectContent>
          </Select>
          {/* Delivery status quick filter */}
          <Select value={deliveryFilter} onValueChange={v => setDeliveryFilter(v === '__all__' ? '' : v)}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="All delivery statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All statuses</SelectItem>
              {DELIVERY_STATUS_OPTIONS.map(o => (
                <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex gap-2">
          <Link to="/sales/customerorder/kanban/">
            <Button variant="outline" size="sm" className="flex items-center gap-1.5">
              <LayoutDashboard size={14} />
              Kanban View
            </Button>
          </Link>
          <Link to="add/">
            <Button>+ New Order</Button>
          </Link>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="w-full h-9" />)}
        </div>
      ) : (
        <>
          <DataTable columns={columns} data={visibleOrders} />

          {/* Pagination */}
          <div className="flex justify-between items-center mt-2">
            <Button variant="outline" onClick={() => setPage(p => Math.max(p - 1, 1))} disabled={page === 1}>
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
            <Button variant="outline" onClick={() => setPage(p => Math.min(p + 1, totalPages))} disabled={page === totalPages}>
              Next
            </Button>
          </div>
        </>
      )}

      {/* Delivery Quick-Update Sheet */}
      <DeliveryUpdateSheet
        order={sheetOrder}
        open={sheetOpen}
        onClose={() => setSheetOpen(false)}
        onUpdated={handleUpdated}
      />
    </div>
  );
}

export default CustomerOrderList;
