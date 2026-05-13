import React, { useState, useEffect, useCallback } from "react";
import { SquarePen, Trash2, SendHorizontal, PackageCheck, ArrowUpRight, ArrowDownLeft, ScanBarcode, ArrowRight } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from "react-router-dom";
import {
  fetchStockTransferForList,
  deleteStockTransfer,
  markStockTransferSent,
  markStockTransferReceived,
  fetchInTransitBarcodes,
} from "./services/apiService";

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatusBadge({ sentStatus, recStatus }) {
  if (recStatus) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-green-100 text-green-800">
        <PackageCheck className="size-3" /> Received
      </span>
    );
  }
  if (sentStatus) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">
        <SendHorizontal className="size-3" /> In Transit
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-gray-100 text-gray-600">
      Draft
    </span>
  );
}

// ── Tab button ────────────────────────────────────────────────────────────────
function TabBtn({ active, onClick, children, count }) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
        active
          ? "border-primary text-primary"
          : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
      }`}
    >
      {children}
      {count != null && (
        <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${
          active ? "bg-violet-100 text-primary" : "bg-muted text-muted-foreground"
        }`}>
          {count}
        </span>
      )}
    </button>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
const StockTransferList = () => {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState(() => params.get("tab") === "intransit" ? "intransit" : "transfers"); // "transfers" | "intransit"

  // Transfers tab state
  const [transfers, setTransfers] = useState([]);
  const [loadingTransfers, setLoadingTransfers] = useState(true);
  const [transitioningTransfers, setTransitioningTransfers] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [actionLoading, setActionLoading] = useState(null);

  // In Transit tab state
  const [inTransitBarcodes, setInTransitBarcodes] = useState([]);
  const [loadingIntransit, setLoadingIntransit] = useState(false);
  const [intransitLoaded, setIntransitLoaded] = useState(false);

  const search = params.get("search") || "";

  // ── Load transfers ──
  const loadTransfers = useCallback(async () => {
    if (transfers.length === 0) setLoadingTransfers(true);
    else setTransitioningTransfers(true);
    const result = await fetchStockTransferForList({ search, page });
    if (result.success) {
      setTransfers(result.data.results ?? result.data ?? []);
      setTotalPages(result.data.total_pages ?? 1);
    } else {
      toast({ title: "Failed to load transfers", variant: "destructive" });
    }
    setLoadingTransfers(false);
    setTransitioningTransfers(false);
  }, [search, page]);

  useEffect(() => { loadTransfers(); }, [loadTransfers]);

  useEffect(() => {
    if (tab === "intransit") loadInTransit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Load in-transit barcodes (lazy — on first tab switch) ──
  const loadInTransit = useCallback(async () => {
    setLoadingIntransit(true);
    const result = await fetchInTransitBarcodes();
    if (result.success) {
      setInTransitBarcodes(Array.isArray(result.data) ? result.data : []);
    } else {
      toast({ title: "Failed to load in-transit barcodes", variant: "destructive" });
    }
    setLoadingIntransit(false);
    setIntransitLoaded(true);
  }, []);

  const handleTabChange = (next) => {
    setTab(next);
    if (next === "intransit" && !intransitLoaded) {
      loadInTransit();
    }
  };

  // ── Actions ──
  const handleMarkSent = async (id) => {
    setActionLoading(id);
    const res = await markStockTransferSent(id);
    if (res.success) {
      toast({ title: "Transfer marked as sent", description: "Barcodes are now in transit." });
      loadTransfers();
      // Refresh in-transit if that tab was already loaded
      if (intransitLoaded) loadInTransit();
    } else {
      toast({ title: "Could not mark as sent", description: res.error?.detail || JSON.stringify(res.error), variant: "destructive" });
    }
    setActionLoading(null);
  };

  const handleMarkReceived = async (id) => {
    setActionLoading(id);
    const res = await markStockTransferReceived(id);
    if (res.success) {
      toast({ title: "Transfer received", description: "Barcodes added to your inventory." });
      loadTransfers();
      if (intransitLoaded) loadInTransit();
    } else {
      toast({ title: "Could not receive transfer", description: res.error?.detail || JSON.stringify(res.error), variant: "destructive" });
    }
    setActionLoading(null);
  };

  // ── Transfers table columns ──
  const transferColumns = [
    {
      header: "Actions",
      cell: ({ row }) => {
        const t = row.original;
        const busy = actionLoading === t.id;
        return (
          <div className="flex items-center gap-1.5">
            {!t.sent_status && !t.rec_status && (
              <>
                <Link to={`${t.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
                  <SquarePen className="size-4" />
                </Link>
                <button onClick={() => deleteStockTransfer(t.id, toast).then(loadTransfers)}
                  className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors">
                  <Trash2 className="size-4" />
                </button>
                <Button size="sm" variant="outline" disabled={busy}
                  className="h-6 px-2 text-[11px] text-amber-700 border-amber-300 hover:bg-amber-50"
                  onClick={() => handleMarkSent(t.id)}>
                  <SendHorizontal className="size-3 mr-1" /> Send
                </Button>
              </>
            )}
            {t.sent_status && !t.rec_status && (
              <Button size="sm" variant="outline" disabled={busy}
                className="h-6 px-2 text-[11px] text-green-700 border-green-300 hover:bg-green-50"
                onClick={() => handleMarkReceived(t.id)}>
                <PackageCheck className="size-3 mr-1" /> Receive
              </Button>
            )}
          </div>
        );
      },
    },
    {
      header: "Status",
      cell: ({ row }) => <StatusBadge sentStatus={row.original.sent_status} recStatus={row.original.rec_status} />,
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) => new Date(getValue()).toLocaleDateString("en-GB").replaceAll("/", "-"),
    },
    { header: "Bill No", accessorKey: "billno" },
    {
      header: "From → To",
      cell: ({ row }) => (
        <span className="flex items-center gap-1 text-xs">
          <span className="text-muted-foreground">{row.original.from_retail_name || "—"}</span>
          <ArrowRight className="size-3 text-muted-foreground/50 shrink-0" />
          <span className="font-medium">{row.original.to_retail_name || "—"}</span>
        </span>
      ),
    },
    {
      header: "Barcodes",
      cell: ({ row }) => {
        const items = row.original.stocktransfermain_set ?? [];
        return (
          <div className="flex flex-wrap gap-1 max-w-[220px]">
            {items.slice(0, 3).map((item, i) => (
              <span key={i} className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono">{item.barcode}</span>
            ))}
            {items.length > 3 && (
              <span className="text-[10px] text-muted-foreground">+{items.length - 3} more</span>
            )}
            {items.length === 0 && <span className="text-[10px] text-muted-foreground">—</span>}
          </div>
        );
      },
    },
    {
      header: "GW (g)",
      cell: ({ row }) => {
        const total = (row.original.stocktransfermain_set ?? []).reduce((s, i) => s + (parseFloat(i.gw) || 0), 0);
        return total > 0 ? total.toFixed(3) : "—";
      },
    },
  ];

  // ── In-transit barcodes table columns ──
  const intransitColumns = [
    {
      header: "Barcode",
      accessorKey: "barcode",
      cell: ({ getValue }) => (
        <span className="font-mono text-xs text-primary">{getValue()}</span>
      ),
    },
    { header: "Item", accessorKey: "item_name",
      cell: ({ row }) => (
        <span className="text-xs">{row.original.item_name || row.original.item_code || "—"}</span>
      ),
    },
    { header: "Purity", accessorKey: "purity",
      cell: ({ getValue }) => <span className="text-xs text-muted-foreground">{getValue() || "—"}</span>,
    },
    { header: "Pcs", accessorKey: "pcs",
      cell: ({ getValue }) => <span className="text-xs text-right block">{getValue() || "—"}</span>,
    },
    { header: "GW (g)", accessorKey: "gw",
      cell: ({ getValue }) => (
        <span className="text-xs font-medium text-right block">
          {getValue() ? parseFloat(getValue()).toFixed(3) : "—"}
        </span>
      ),
    },
    { header: "NW (g)", accessorKey: "nw",
      cell: ({ getValue }) => (
        <span className="text-xs text-right block">
          {getValue() ? parseFloat(getValue()).toFixed(3) : "—"}
        </span>
      ),
    },
    {
      header: "From → To",
      cell: ({ row }) => (
        <span className="flex items-center gap-1 text-xs whitespace-nowrap">
          <span className="text-muted-foreground">{row.original.from_retail_name || "—"}</span>
          <ArrowRight className="size-3 text-muted-foreground/50 shrink-0" />
          <span className="font-medium">{row.original.to_retail_name || "—"}</span>
        </span>
      ),
    },
    {
      header: "Transfer",
      cell: ({ row }) => (
        <div className="text-xs">
          <div className="font-mono text-primary">{row.original.transfer_billno}</div>
          <div className="text-muted-foreground">
            {row.original.transfer_date
              ? new Date(row.original.transfer_date).toLocaleDateString("en-GB").replaceAll("/", "-")
              : "—"}
          </div>
        </div>
      ),
    },
    {
      header: "Status",
      cell: () => (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800">
          <SendHorizontal className="size-3" /> In Transit
        </span>
      ),
    },
  ];

  const intransitGW = inTransitBarcodes.reduce((s, b) => s + (parseFloat(b.gw) || 0), 0);

  return (
    <div className="p-4 flex flex-col gap-4">

      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold">Stock Transfers</h1>
        <Link to="add/">
          <Button size="sm" className="bg-primary hover:bg-primary text-white">
            New Transfer
          </Button>
        </Link>
      </div>

      {/* ── Tabs ── */}
      <div className="border-b border-border flex gap-0">
        <TabBtn active={tab === "transfers"} onClick={() => handleTabChange("transfers")}
          count={transfers.length > 0 ? transfers.length : null}>
          Transfers
        </TabBtn>
        <TabBtn active={tab === "intransit"} onClick={() => handleTabChange("intransit")}
          count={intransitLoaded ? inTransitBarcodes.length : null}>
          <SendHorizontal className="size-3.5" />
          In Transit Barcodes
        </TabBtn>
      </div>

      {/* ── Transfers tab ── */}
      {tab === "transfers" && (
        <>
          <div className="flex items-center gap-3">
            <Input
              type="text"
              value={search}
              onChange={e => setParams({ search: e.target.value })}
              placeholder="Search bill no..."
              className="max-w-xs h-9"
            />
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 text-xs text-muted-foreground bg-muted/40 rounded-lg px-4 py-2">
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-gray-400 inline-block" /> Draft
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-amber-400 inline-block" /> In Transit
            </span>
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-full bg-green-500 inline-block" /> Received
            </span>
          </div>

          {loadingTransfers ? (
            <div className="flex flex-col gap-2">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="w-full h-9" />)}
            </div>
          ) : (
            <>
              <div className={transitioningTransfers ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}>
              <DataTable columns={transferColumns} data={transfers} />
              </div>
              {totalPages > 1 && (
                <div className="flex justify-between items-center">
                  <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(p - 1, 1))} disabled={page === 1 || transitioningTransfers}>
                    Previous
                  </Button>
                  <span className="text-xs text-muted-foreground">Page {page} of {totalPages}</span>
                  <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(p + 1, totalPages))} disabled={page === totalPages || transitioningTransfers}>
                    Next
                  </Button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {/* ── In Transit Barcodes tab ── */}
      {tab === "intransit" && (
        <>
          {loadingIntransit ? (
            <div className="flex flex-col gap-2">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="w-full h-9" />)}
            </div>
          ) : inTransitBarcodes.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-20 gap-3 text-muted-foreground">
              <PackageCheck className="size-12 opacity-20" />
              <p className="text-sm font-medium">No barcodes in transit</p>
              <p className="text-xs">All transfers have been received or no transfers have been sent yet.</p>
            </div>
          ) : (
            <>
              {/* Summary strip */}
              <div className="flex items-center gap-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
                <span className="flex items-center gap-1.5">
                  <SendHorizontal className="size-4" />
                  <strong>{inTransitBarcodes.length}</strong> barcode{inTransitBarcodes.length !== 1 ? "s" : ""} in transit
                </span>
                <span className="text-amber-600">
                  Total GW: <strong>{intransitGW.toFixed(3)} g</strong>
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="ml-auto h-7 text-xs border-amber-300 text-amber-700 hover:bg-amber-100"
                  onClick={loadInTransit}
                >
                  Refresh
                </Button>
              </div>

              <DataTable columns={intransitColumns} data={inTransitBarcodes} />
            </>
          )}
        </>
      )}
    </div>
  );
};

export default StockTransferList;
