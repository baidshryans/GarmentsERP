import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/hooks/use-toast";
import { fetchCustomerOrdersKanban, updateOrderDeliveryStatus } from "@/services/apiService";
import { List, AlertTriangle, Clock, PackageCheck, XCircle } from "lucide-react";

/* ─── Column definitions ─────────────────────────────────────── */
const COLUMNS = [
  {
    key: "pending",
    label: "Pending",
    icon: Clock,
    accent: "border-t-amber-400",
    dot: "bg-amber-400",
    labelColor: "text-gray-700",
    countBg: "bg-amber-50 text-amber-600",
    badgeBg: "bg-amber-50 text-amber-600",
    nextStatus: { key: "ready", label: "Mark Ready →" },
    prevStatus: null,
  },
  {
    key: "ready",
    label: "Ready for Delivery",
    icon: PackageCheck,
    accent: "border-t-blue-400",
    dot: "bg-blue-400",
    labelColor: "text-gray-700",
    countBg: "bg-blue-50 text-blue-600",
    badgeBg: "bg-blue-50 text-blue-600",
    nextStatus: { key: "delivered", label: "Mark Delivered →" },
    prevStatus: { key: "pending", label: "← Back to Pending" },
  },
  {
    key: "delivered",
    label: "Delivered",
    icon: PackageCheck,
    accent: "border-t-emerald-400",
    dot: "bg-emerald-400",
    labelColor: "text-gray-700",
    countBg: "bg-emerald-50 text-emerald-600",
    badgeBg: "bg-emerald-50 text-emerald-600",
    nextStatus: null,
    prevStatus: { key: "ready", label: "← Back to Ready" },
  },
  {
    key: "cancelled",
    label: "Cancelled",
    icon: XCircle,
    accent: "border-t-rose-300",
    dot: "bg-rose-300",
    labelColor: "text-gray-500",
    countBg: "bg-gray-100 text-gray-500",
    badgeBg: "bg-gray-50 text-gray-500",
    nextStatus: null,
    prevStatus: { key: "pending", label: "← Restore" },
  },
];

/* ─── Helpers ────────────────────────────────────────────────── */
function daysFromToday(dateStr) {
  if (!dateStr) return null;
  const diff = Math.round(
    (new Date(dateStr) - new Date(new Date().toDateString())) / 86400000
  );
  return diff;
}

function calculateOrderDeliveryStatus(order) {
  if (!order.items || order.items.length === 0) return order.delivery_status;

  const itemStates = order.items.map(item => item.lock_state || 'unlocked');
  const hasAll = (state) => itemStates.every(s => s === state);
  const hasAny = (state) => itemStates.some(s => s === state);

  // All items billed → delivered
  if (hasAll('billed')) return 'delivered';

  // Any item in production or billed → ready
  if (hasAny('in_production') || hasAny('billed')) return 'ready';

  // All unlocked → pending
  return 'pending';
}

function DeliveryDateBadge({ dateStr, isOverdue, daysOverdue }) {
  if (!dateStr) return null;
  const days = daysFromToday(dateStr);
  const formatted = new Date(dateStr).toLocaleDateString("en-GB").replaceAll("/", "-");

  if (isOverdue) {
    return (
      <span className="flex items-center gap-1 text-xs font-medium text-red-600">
        <AlertTriangle size={11} />
        {formatted} · {daysOverdue}d overdue
      </span>
    );
  }
  if (days !== null && days <= 3) {
    return (
      <span className="text-xs font-medium text-orange-500">
        {formatted} · due in {days}d
      </span>
    );
  }
  return <span className="text-xs text-gray-500">{formatted}</span>;
}

/* ─── Single Kanban card ─────────────────────────────────────── */
function KanbanCard({ order, col, onMove }) {
  const itemCount = order.customerorderitems_set?.length ?? 0;
  const advanceAvail = parseFloat(order.advance_available ?? 0);
  const estAmt = parseFloat(order.est_amount ?? 0);

  return (
    <div
      className="rounded-lg border border-gray-200 bg-white shadow-sm hover:shadow-md transition-shadow p-3 flex flex-col gap-2"
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <Link
          to={`/sales/customerorder/list/${order.id}`}
          className="font-mono text-sm font-bold text-primary hover:underline leading-tight"
        >
          {order.order_no}
        </Link>
        <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${col.badgeBg}`}>
          {order.nature || "—"}
        </span>
      </div>

      {/* Customer */}
      <p className="text-sm font-medium text-gray-800 leading-tight truncate" title={order.ldgr_name}>
        {order.ldgr_name || "—"}
      </p>

      {/* Delivery date */}
      <DeliveryDateBadge
        dateStr={order.delivery_date}
        isOverdue={order.is_overdue}
        daysOverdue={order.days_overdue}
      />

      {/* Stats row */}
      <div className="flex gap-3 text-xs text-gray-500 border-t border-gray-100 pt-1.5 mt-0.5">
        <span>{itemCount} item{itemCount !== 1 ? "s" : ""}</span>
        {estAmt > 0 && (
          <span>Est ₹{estAmt.toLocaleString("en-IN")}</span>
        )}
        {advanceAvail > 0 && (
          <span className="text-emerald-600">Adv ₹{advanceAvail.toLocaleString("en-IN")}</span>
        )}
      </div>

      {/* Move buttons */}
      <div className="flex gap-1.5 flex-wrap pt-0.5">
        {col.prevStatus && (
          <button
            onClick={() => onMove(order.id, col.prevStatus.key)}
            className="text-[10px] px-2 py-0.5 rounded border border-gray-300 text-gray-500 hover:bg-gray-100 transition-colors"
          >
            {col.prevStatus.label}
          </button>
        )}
        {col.nextStatus && (
          <button
            onClick={() => onMove(order.id, col.nextStatus.key)}
            className="text-[10px] px-2 py-0.5 rounded border border-gray-300 text-gray-600 hover:bg-gray-100 transition-colors font-medium"
          >
            {col.nextStatus.label}
          </button>
        )}
      </div>
    </div>
  );
}

/* ─── Column ─────────────────────────────────────────────────── */
function KanbanColumn({ col, orders, onMove }) {
  return (
    <div className={`flex flex-col rounded-xl border border-gray-200 min-w-0 border-t-[3px] ${col.accent}`}>
      {/* Column header — clean, neutral */}
      <div className="bg-white px-4 py-3 flex items-center justify-between shrink-0 border-b border-gray-100">
        <div className="flex items-center gap-2.5">
          <span className={`w-2.5 h-2.5 rounded-full ${col.dot}`} />
          <span className={`font-semibold text-sm ${col.labelColor}`}>{col.label}</span>
        </div>
        <span className={`text-xs font-semibold rounded-full px-2 py-0.5 ${col.countBg}`}>
          {orders.length}
        </span>
      </div>

      {/* Cards area */}
      <div className="bg-gray-50/70 flex-1 overflow-y-auto p-3 flex flex-col gap-2.5"
           style={{ maxHeight: "calc(100vh - 13rem)" }}>
        {orders.length === 0 ? (
          <p className="text-center text-gray-400 text-xs py-8">No orders</p>
        ) : (
          orders.map((order) => (
            <KanbanCard key={order.id} order={order} col={col} onMove={onMove} />
          ))
        )}
      </div>
    </div>
  );
}

/* ─── Main Kanban board ──────────────────────────────────────── */
export default function CustomerOrderKanban() {
  const { toast } = useToast();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const autoMovedRef = React.useRef(new Set()); // Track which orders have been auto-moved

  useEffect(() => {
    setLoading(true);
    fetchCustomerOrdersKanban().then((res) => {
      if (res.success) {
        setOrders(res.data);
        autoMovedRef.current.clear(); // Reset tracking on new load
      }
      else toast({ title: "Failed to load orders", description: String(res.error) });
      setLoading(false);
    });
  }, []);

  /* Optimistic status move */
  const handleMove = React.useCallback(async (orderId, newStatus) => {
    // Optimistically update local state
    setOrders((prev) =>
      prev.map((o) => (o.id === orderId ? { ...o, delivery_status: newStatus } : o))
    );
    const res = await updateOrderDeliveryStatus(orderId, newStatus, null);
    if (!res.success) {
      toast({ title: "Update failed", description: "Reverting change." });
      // Revert
      setOrders((prev) =>
        prev.map((o) =>
          o.id === orderId ? { ...o, delivery_status: /* original */ o.delivery_status } : o
        )
      );
    }
  }, [toast]);

  /* Client-side filter across all columns */
  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return orders;
    return orders.filter(
      (o) =>
        o.order_no?.toLowerCase().includes(q) ||
        (o.ldgr_name || "").toLowerCase().includes(q)
    );
  }, [orders, search]);

  /* Auto-move orders to correct column based on item states — only once per order */
  useEffect(() => {
    if (loading) return;
    orders.forEach((order) => {
      const calculatedStatus = calculateOrderDeliveryStatus(order);
      if (calculatedStatus !== order.delivery_status && !autoMovedRef.current.has(order.id)) {
        autoMovedRef.current.add(order.id);
        handleMove(order.id, calculatedStatus);
      }
    });
  }, [orders, loading, handleMove]);

  const grouped = useMemo(
    () =>
      Object.fromEntries(
        COLUMNS.map((col) => [
          col.key,
          filtered.filter((o) => {
            const status = calculateOrderDeliveryStatus(o);
            return status === col.key;
          }),
        ])
      ),
    [filtered]
  );

  return (
    <div className="p-4 flex flex-col gap-4 h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 justify-between">
        <Input
          type="text"
          placeholder="Search order no or customer..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <Link to="/sales/customerorder/list/">
          <Button variant="outline" size="sm" className="flex items-center gap-1.5">
            <List size={14} />
            List View
          </Button>
        </Link>
      </div>

      {/* Board */}
      {loading ? (
        <div className="flex gap-4 flex-1">
          {COLUMNS.map((col) => (
            <div
              key={col.key}
              className="flex-1 rounded-xl bg-gray-100 animate-pulse"
              style={{ minHeight: "200px" }}
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-4 flex-1 min-h-0">
          {COLUMNS.map((col) => (
            <KanbanColumn
              key={col.key}
              col={col}
              orders={grouped[col.key] ?? []}
              onMove={handleMove}
            />
          ))}
        </div>
      )}
    </div>
  );
}
