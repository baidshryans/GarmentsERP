import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Package,
  Factory,
  Truck,
  CheckCircle2,
  Tag,
  ClipboardList,
  Search,
  Loader2,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  fetchCustomerOrders,
  fetchCustomerOrderTimeline,
} from "@/services/apiService";

/* ─── helpers ─────────────────────────────────────────────── */

// Per-event visual config — icon + dot colour. Keeps timeline code tidy.
const EVENT_STYLES = {
  placed:            { Icon: ClipboardList, dot: "bg-slate-400",   ring: "ring-slate-100"   },
  released_po:       { Icon: Package,       dot: "bg-amber-500",   ring: "ring-amber-100"   },
  released_mo:       { Icon: Factory,       dot: "bg-amber-500",   ring: "ring-amber-100"   },
  received_karigar:  { Icon: Truck,         dot: "bg-blue-500",    ring: "ring-blue-100"    },
  received_pv:       { Icon: Truck,         dot: "bg-indigo-500",  ring: "ring-indigo-100"  },
  barcoded:          { Icon: Tag,           dot: "bg-sky-500",     ring: "ring-sky-100"     },
  delivered:         { Icon: CheckCircle2,  dot: "bg-emerald-600", ring: "ring-emerald-100" },
};

// Pipeline stages — every CO item passes through these 5 milestones.
// `kinds` lists the event types that satisfy each stage.
const PIPELINE_STAGES = [
  { id: "placed",    label: "Order Placed",        Icon: ClipboardList, kinds: ["placed"] },
  { id: "released",  label: "Released to Production", Icon: Package,    kinds: ["released_po", "released_mo"] },
  { id: "received",  label: "Received in Stock",   Icon: Truck,         kinds: ["received_pv", "received_karigar"] },
  { id: "barcoded",  label: "Barcoded",            Icon: Tag,           kinds: ["barcoded"] },
  { id: "delivered", label: "Delivered",           Icon: CheckCircle2,  kinds: ["delivered"] },
];

// Build a 5-stage timeline view from the raw event list.
// Each stage carries the matching event (if any) plus a `status` flag.
function buildStageTimeline(events) {
  const matchedEvents = PIPELINE_STAGES.map((stage) => {
    const ev = events.find((e) => stage.kinds.includes(e.kind)) || null;
    return { stage, ev };
  });
  const lastDoneIdx = matchedEvents.reduce(
    (acc, m, i) => (m.ev ? i : acc),
    -1,
  );
  return matchedEvents.map((m, i) => ({
    ...m,
    status: m.ev ? "done" : i === lastDoneIdx + 1 ? "next" : "future",
  }));
}

function StateChip({ state }) {
  const map = {
    unlocked:      "bg-slate-100 text-slate-700 border-slate-200",
    in_production: "bg-amber-50 text-amber-800 border-amber-200",
    billed:        "bg-emerald-50 text-emerald-800 border-emerald-200",
  };
  const label = {
    unlocked: "Not yet released",
    in_production: "In production",
    billed: "Delivered",
  }[state] || state;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${map[state] || "bg-slate-100 text-slate-700 border-slate-200"}`}>
      {label}
    </span>
  );
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  } catch {
    return iso;
  }
}

/* ─── timeline for one CO item ────────────────────────────── */

function ItemTimeline({ item }) {
  const events = item.events || [];
  return (
    <div className="rounded-xl border border-border bg-white shadow-sm overflow-hidden">
      {/* Item header */}
      <div className="px-4 py-3 border-b border-border bg-muted/20 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center justify-center size-6 rounded-md bg-primary/10 text-primary text-xs font-semibold tabular-nums">
              {item.sl_no}
            </span>
            <h4 className="text-sm font-semibold text-foreground truncate">
              {item.item_name || item.item || "Unnamed item"}
            </h4>
            <StateChip state={item.state} />
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[11px] text-muted-foreground">
            {item.item_name && item.item && <span className="font-mono">{item.item}</span>}
            {item.purity && <span>{item.purity}</span>}
            {item.pcs != null && <span>{item.pcs} pcs</span>}
            {item.approx_wt != null && <span>{item.approx_wt} g</span>}
            {item.size && <span>Size {item.size}</span>}
          </div>
          {item.remarks && (
            <p className="mt-1 text-xs text-muted-foreground italic truncate">{item.remarks}</p>
          )}
        </div>
      </div>

      {/* Timeline — fixed 5-stage pipeline, future stages greyed out */}
      <div className="px-5 py-4">
        <ol className="relative">
          {buildStageTimeline(events).map((row, i, arr) => {
            const { stage, ev, status } = row;
            const isLast = i === arr.length - 1;
            const isDone = status === "done";
            const isNext = status === "next";

            const cfg = ev ? (EVENT_STYLES[ev.kind] || EVENT_STYLES.placed) : null;
            const Icon = cfg?.Icon || stage.Icon;

            // Visual treatment per status.
            const dotClass = isDone
              ? `${cfg.dot} text-white shadow-sm`
              : isNext
              ? "bg-white text-slate-400 border-2 border-dashed border-slate-300"
              : "bg-slate-50 text-slate-300 border border-slate-200";

            const ringClass = isDone ? `ring-4 ${cfg.ring}` : "";
            const lineClass = isDone ? "bg-border" : "bg-slate-200/70 border-l border-dashed border-slate-200";
            const labelClass = isDone
              ? "text-foreground font-medium"
              : isNext
              ? "text-slate-500 font-medium"
              : "text-slate-400";

            return (
              <li key={stage.id} className="relative pl-10 pb-5 last:pb-0">
                {!isLast && (
                  <span
                    aria-hidden
                    className={`absolute left-[15px] top-7 bottom-0 w-px ${lineClass}`}
                  />
                )}
                <span
                  className={`absolute left-0 top-0.5 inline-flex items-center justify-center size-8 rounded-full ${dotClass} ${ringClass}`}
                >
                  <Icon className="size-4" />
                </span>

                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
                  <span className={`text-sm ${labelClass}`}>
                    {ev?.label || stage.label}
                  </span>
                  {isDone && (
                    <span className="text-xs text-muted-foreground">{formatDate(ev.date)}</span>
                  )}
                  {!isDone && (
                    <span className={`text-[10px] uppercase tracking-wider ${isNext ? "text-amber-600" : "text-slate-300"}`}>
                      {isNext ? "Pending" : "Upcoming"}
                    </span>
                  )}
                </div>

                {isDone && (
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px]">
                    {ev.ref && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-muted text-foreground font-mono">
                        {ev.ref}
                      </span>
                    )}
                    {ev.vendor && (
                      <span className="text-muted-foreground">Vendor: <span className="text-foreground">{ev.vendor}</span></span>
                    )}
                    {ev.karigar && (
                      <span className="text-muted-foreground">Karigar: <span className="text-foreground">{ev.karigar}</span></span>
                    )}
                    {ev.barcode && (
                      <span className="text-muted-foreground">Barcode: <span className="text-foreground font-mono">{ev.barcode}</span></span>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

/* ─── main page ───────────────────────────────────────────── */

const CustomerOrderTracker = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const presetOrderId = searchParams.get("order");

  const [orders, setOrders] = useState([]);
  const [ordersLoading, setOrdersLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(
    presetOrderId ? Number(presetOrderId) : null
  );
  const [timeline, setTimeline] = useState(null);
  const [timelineLoading, setTimelineLoading] = useState(false);

  // Initial + search fetch for left-pane list.
  useEffect(() => {
    let cancelled = false;
    setOrdersLoading(true);
    fetchCustomerOrders({ search, page: 1, ordering: "-date1" }).then((r) => {
      if (cancelled) return;
      if (r.success) setOrders(r.data.results || []);
      setOrdersLoading(false);
    });
    return () => { cancelled = true; };
  }, [search]);

  // When an order is selected, load its timeline.
  useEffect(() => {
    if (!selectedId) { setTimeline(null); return; }
    let cancelled = false;
    setTimelineLoading(true);
    fetchCustomerOrderTimeline(selectedId).then((r) => {
      if (cancelled) return;
      setTimeline(r.success ? r.data : null);
      setTimelineLoading(false);
    });
    return () => { cancelled = true; };
  }, [selectedId]);

  // One-shot — honour deep link then strip the query param so a refresh
  // doesn't silently force-select after the user clicks another order.
  useEffect(() => {
    if (presetOrderId) setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const headline = useMemo(() => {
    if (!timeline) return null;
    const { order, items } = timeline;
    const total = items.length;
    const delivered = items.filter(i => i.state === "billed").length;
    const inProd    = items.filter(i => i.state === "in_production").length;
    const open      = total - delivered - inProd;
    return { order, total, delivered, inProd, open };
  }, [timeline]);

  return (
    <div className="w-full max-w-[1500px] mx-auto px-4 py-5 space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-foreground tracking-tight">Customer Order Tracker</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          Follow every order from placement through delivery — no more hunting across modules.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr] gap-4 min-h-[70vh]">
        {/* ── Left pane: order list ── */}
        <aside className="bg-white border border-border rounded-xl shadow-sm flex flex-col overflow-hidden">
          <div className="px-3 py-2.5 border-b border-border bg-muted/20">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search CO #, customer, phone…"
                className="h-8 pl-8 text-sm"
              />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {ordersLoading ? (
              <div className="p-6 flex items-center justify-center text-muted-foreground text-xs">
                <Loader2 className="size-4 animate-spin mr-2" /> Loading orders…
              </div>
            ) : orders.length === 0 ? (
              <p className="p-6 text-xs text-muted-foreground text-center">No customer orders match.</p>
            ) : (
              <ul className="divide-y divide-border">
                {orders.map((o) => (
                  <li
                    key={o.id}
                    onClick={() => setSelectedId(o.id)}
                    className={`px-3 py-2.5 cursor-pointer transition-colors ${selectedId === o.id ? "bg-primary/5" : "hover:bg-muted/30"}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-mono font-semibold text-foreground truncate">{o.order_no}</span>
                      <span className="text-[10px] text-muted-foreground whitespace-nowrap">{formatDate(o.date1)}</span>
                    </div>
                    <div className="mt-0.5 text-xs text-foreground truncate">{o.ldgr_code_name || o.ldgr_name || "—"}</div>
                    <div className="mt-0.5 flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
                      <span>Due {formatDate(o.delivery_date)}</span>
                      {o.is_overdue && <span className="text-rose-600 font-semibold">Overdue</span>}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>

        {/* ── Right pane: timeline ── */}
        <section className="space-y-4">
          {!selectedId && (
            <div className="bg-white border border-dashed border-border rounded-xl p-10 text-center text-sm text-muted-foreground">
              Select a customer order on the left to see its event timeline.
            </div>
          )}

          {selectedId && timelineLoading && (
            <div className="bg-white border border-border rounded-xl p-10 flex items-center justify-center text-muted-foreground text-sm">
              <Loader2 className="size-4 animate-spin mr-2" /> Loading timeline…
            </div>
          )}

          {selectedId && !timelineLoading && !timeline && (
            <div className="bg-white border border-border rounded-xl p-10 text-center text-sm text-destructive">
              Could not load timeline for this order.
            </div>
          )}

          {selectedId && timeline && (
            <>
              {/* Order header card */}
              <div className="bg-white border border-border rounded-xl shadow-sm p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 text-sm">
                      <span className="font-mono font-semibold text-foreground">{timeline.order.order_no}</span>
                      {timeline.order.nature && (
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{String(timeline.order.nature).replace(/_/g, " ")}</span>
                      )}
                    </div>
                    <h2 className="text-base font-semibold text-foreground mt-0.5 truncate">
                      {timeline.order.customer_name || "—"}
                    </h2>
                    <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-[11px] text-muted-foreground">
                      <span>Placed {formatDate(timeline.order.date1)}</span>
                      <span>Delivery by {formatDate(timeline.order.delivery_date)}</span>
                      {timeline.order.delivery_status && (
                        <span>Status: <span className="text-foreground">{timeline.order.delivery_status}</span></span>
                      )}
                    </div>
                  </div>
                  {headline && (
                    <div className="flex items-center gap-2 shrink-0">
                      {headline.delivered > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                          {headline.delivered}/{headline.total} delivered
                        </span>
                      )}
                      {headline.inProd > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                          {headline.inProd} in production
                        </span>
                      )}
                      {headline.open > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                          {headline.open} open
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Per-item timelines */}
              {timeline.items.length === 0 ? (
                <div className="bg-white border border-border rounded-xl p-8 text-center text-sm text-muted-foreground">
                  This order has no items.
                </div>
              ) : (
                <div className="space-y-4">
                  {timeline.items.map((it) => (
                    <ItemTimeline key={it.co_item_id} item={it} />
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
};

export default CustomerOrderTracker;
