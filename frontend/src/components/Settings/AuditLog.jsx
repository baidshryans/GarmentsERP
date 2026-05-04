import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { Search, ChevronLeft, ChevronRight, RefreshCw, Undo2, History, AlertTriangle } from "lucide-react";
import { fetchAuditLog, reverseTransaction, restoreToPoint } from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

const EVENT_STYLE = {
  CREATE: "bg-green-50 text-green-700",
  UPDATE: "bg-blue-50  text-blue-700",
  DELETE: "bg-red-50   text-red-700",
};

export default function AuditLog() {
  const { toast }    = useToast();
  const [tab, setTab] = useState("log");   // "log" | "restore"
  const [data, setData]       = useState({ results: [], count: 0, num_pages: 1, page: 1 });
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    from_date: "", to_date: "", model: "", page: 1,
  });

  const load = useCallback(async (f = filters) => {
    setLoading(true);
    const params = {};
    if (f.from_date) params.from_date = f.from_date;
    if (f.to_date)   params.to_date   = f.to_date;
    if (f.model)     params.model     = f.model;
    params.page = f.page;

    const res = await fetchAuditLog(params);
    if (res.success) setData(res.data);
    else toast({ title: "Failed to load audit log", variant: "destructive" });
    setLoading(false);
  }, []);

  useEffect(() => { if (tab === "log") load(); }, [tab]);

  const applyFilters = () => {
    if (!isValidDateRange(filters.from_date, filters.to_date)) {
      toast({ title: "From date cannot be after To date.", variant: "destructive" });
      return;
    }
    const f = { ...filters, page: 1 };
    setFilters(f);
    load(f);
  };

  const goPage = (p) => {
    const f = { ...filters, page: p };
    setFilters(f);
    load(f);
  };

  const sf = (k, v) => setFilters((prev) => ({ ...prev, [k]: v }));

  // ── Reverse a single transaction ────────────────────────────────────────
  async function handleReverse(row) {
    if (!row.history_transaction_id) {
      toast({ title: "This event has no transaction id — cannot reverse.", variant: "destructive" });
      return;
    }
    // 1. Dry run
    const dry = await reverseTransaction(row.history_transaction_id, true);
    if (!dry.success) {
      toast({ title: "Reversal preview failed", description: JSON.stringify(dry.error), variant: "destructive" });
      return;
    }
    const s = dry.data.summary;
    const blockedNote = s.blocked.length ? `\n\nBlocked: ${s.blocked.join("; ")}` : "";
    const ok = window.confirm(
      `This will revert ${s.total_changes} change(s) across ${s.affected_models.length} model(s):\n` +
      `  • ${s.creates} re-created\n  • ${s.updates} reverted\n  • ${s.deletes} removed${blockedNote}\n\nProceed?`
    );
    if (!ok) return;

    // 2. Real
    const real = await reverseTransaction(row.history_transaction_id, false);
    if (real.success) {
      toast({ title: `Reversed: ${real.data.summary.total_changes} change(s)` });
      load(filters);
    } else {
      toast({ title: "Reversal failed", description: JSON.stringify(real.error), variant: "destructive" });
    }
  }

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-base font-semibold">Audit Log</h1>
        <div className="flex items-center gap-1 rounded-md border p-0.5 bg-muted/30">
          <Button size="sm" variant={tab === "log" ? "default" : "ghost"} className="h-7 text-xs" onClick={() => setTab("log")}>
            <History className="size-3.5 mr-1" /> Activity
          </Button>
          <Button size="sm" variant={tab === "restore" ? "default" : "ghost"} className="h-7 text-xs" onClick={() => setTab("restore")}>
            <RefreshCw className="size-3.5 mr-1" /> Restore Points
          </Button>
        </div>
      </div>

      {tab === "log" && (
        <>
          {/* ── Filters ── */}
          <div className="flex flex-wrap items-end gap-3 p-3 rounded-xl border border-border bg-muted/30">
            <div>
              <Label className="text-xs">From Date</Label>
              <Input type="date" className="h-8 text-sm mt-1 w-36"
                value={filters.from_date} onChange={(e) => sf("from_date", e.target.value)} max={filters.to_date || undefined} />
            </div>
            <div>
              <Label className="text-xs">To Date</Label>
              <Input type="date" className="h-8 text-sm mt-1 w-36"
                value={filters.to_date} onChange={(e) => sf("to_date", e.target.value)} min={filters.from_date || undefined} />
            </div>
            <div>
              <Label className="text-xs">Model / Table</Label>
              <Input className="h-8 text-sm mt-1 w-40" placeholder="e.g. salesvou"
                value={filters.model} onChange={(e) => sf("model", e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && applyFilters()} />
            </div>
            <Button size="sm" className="bg-primary hover:bg-primary text-white h-8" onClick={applyFilters}>
              <Search className="size-3.5 mr-1.5" /> Search
            </Button>
            <Button size="sm" variant="outline" className="h-8" onClick={() => {
              const f = { from_date: "", to_date: "", model: "", page: 1 };
              setFilters(f); load(f);
            }}>Clear</Button>
          </div>

          {/* ── Count ── */}
          <p className="text-xs text-muted-foreground">
            {data.count.toLocaleString()} event{data.count !== 1 ? "s" : ""} found
            {data.num_pages > 1 && ` — Page ${data.page} of ${data.num_pages}`}
          </p>

          {/* ── Table ── */}
          {loading ? (
            <div className="flex flex-col gap-2">{[...Array(8)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
          ) : (
            <div className="rounded-xl border border-border overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-muted/50 border-b border-border">
                      {["Date & Time", "User", "Action", "Model", "Record", "Changed", ""].map((h) => (
                        <th key={h} className="text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-4 py-2.5">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {data.results.length === 0 ? (
                      <tr><td colSpan={7} className="text-center py-8 text-muted-foreground text-sm">No events found.</td></tr>
                    ) : data.results.map((e, i) => (
                      <tr key={e.id} className={`border-b border-border last:border-0 hover:bg-accent/30 transition-colors ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
                        <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap">{e.datetime}</td>
                        <td className="px-4 py-2.5 text-xs font-medium">{e.user}</td>
                        <td className="px-4 py-2.5">
                          <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold ${EVENT_STYLE[e.event_type] || ""}`}>
                            {e.event_type}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 font-mono text-xs">
                          <span className="text-muted-foreground">{e.app}.</span>{e.model}
                        </td>
                        <td className="px-4 py-2.5 text-xs max-w-[200px] truncate" title={e.object_repr}>
                          {e.object_repr}
                        </td>
                        <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[260px]">
                          {e.changed_fields ? (
                            <details className="cursor-pointer">
                              <summary className="text-primary hover:underline text-[11px]">View</summary>
                              <pre className="mt-1 text-[10px] bg-muted rounded p-1 overflow-x-auto max-h-32 whitespace-pre-wrap">
                                {typeof e.changed_fields === "string"
                                  ? e.changed_fields
                                  : JSON.stringify(e.changed_fields, null, 2)}
                              </pre>
                            </details>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {e.history_transaction_id && (
                            <Button size="sm" variant="ghost" className="h-7 text-xs"
                              onClick={() => handleReverse(e)} title="Reverse this operation">
                              <Undo2 className="size-3.5" />
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ── Pagination ── */}
          {data.num_pages > 1 && (
            <div className="flex items-center justify-center gap-2 pt-1">
              <Button size="sm" variant="outline" disabled={data.page <= 1} onClick={() => goPage(data.page - 1)}>
                <ChevronLeft className="size-4" />
              </Button>
              <span className="text-xs text-muted-foreground">Page {data.page} / {data.num_pages}</span>
              <Button size="sm" variant="outline" disabled={data.page >= data.num_pages} onClick={() => goPage(data.page + 1)}>
                <ChevronRight className="size-4" />
              </Button>
            </div>
          )}
        </>
      )}

      {tab === "restore" && <RestorePointsTab toast={toast} />}
    </div>
  );
}

// ── Restore Points Tab ─────────────────────────────────────────────────────

function RestorePointsTab({ toast }) {
  const [timestamp, setTimestamp] = useState(() => {
    // default: 1 hour ago, ISO local format suitable for datetime-local input
    const d = new Date(Date.now() - 60 * 60 * 1000);
    return d.toISOString().slice(0, 16);
  });
  const [busy, setBusy]       = useState(false);
  const [preview, setPreview] = useState(null);

  async function runDryRun() {
    setBusy(true);
    setPreview(null);
    const res = await restoreToPoint(new Date(timestamp).toISOString(), true);
    setBusy(false);
    if (!res.success) {
      toast({ title: "Preview failed", description: JSON.stringify(res.error), variant: "destructive" });
      return;
    }
    setPreview(res.data);
  }

  async function applyRestore() {
    if (!preview) return;
    const ok = window.confirm(
      `This will roll the system back to ${timestamp}.\n\n` +
      `  • ${preview.summary.creates} rows re-created\n` +
      `  • ${preview.summary.updates} rows reverted\n` +
      `  • ${preview.summary.deletes} rows deleted\n\n` +
      `This is destructive and affects ALL users in this retail. Proceed?`
    );
    if (!ok) return;
    setBusy(true);
    const res = await restoreToPoint(new Date(timestamp).toISOString(), false);
    setBusy(false);
    if (res.success) {
      toast({ title: `System restored to ${timestamp}`,
        description: `${res.data.summary.total_changes} change(s) applied.` });
      setPreview(null);
    } else {
      toast({ title: "Restore failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="rounded-xl border bg-amber-50 dark:bg-amber-950/30 border-amber-200 dark:border-amber-900 p-4 flex gap-3">
        <AlertTriangle className="size-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-800 dark:text-amber-200 space-y-1">
          <p className="font-semibold">System Restore — destructive operation</p>
          <p>Rolls every audited table back to its state at the chosen timestamp. Run a preview first, review the change counts, and only then apply.</p>
        </div>
      </div>

      <div className="rounded-xl border p-4 space-y-3">
        <div>
          <Label className="text-xs">Restore to this moment</Label>
          <Input type="datetime-local" className="h-9 text-sm mt-1 w-64"
            value={timestamp} onChange={(e) => setTimestamp(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={runDryRun} disabled={busy}>
            {busy ? "Calculating…" : "Preview changes"}
          </Button>
          {preview && (
            <Button size="sm" className="bg-red-600 hover:bg-red-700 text-white" onClick={applyRestore} disabled={busy}>
              {busy ? "Applying…" : `Apply (${preview.summary.total_changes} changes)`}
            </Button>
          )}
        </div>
      </div>

      {preview && (
        <div className="rounded-xl border p-4 space-y-2 text-sm">
          <p className="font-semibold">Preview at {preview.timestamp}{preview.retail ? ` (retail ${preview.retail})` : ""}</p>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="rounded bg-green-50 p-2"><span className="font-mono text-lg block">{preview.summary.creates}</span> re-created</div>
            <div className="rounded bg-blue-50 p-2"><span className="font-mono text-lg block">{preview.summary.updates}</span> reverted</div>
            <div className="rounded bg-red-50 p-2"><span className="font-mono text-lg block">{preview.summary.deletes}</span> deleted</div>
          </div>
          {preview.summary.affected_models.length > 0 && (
            <p className="text-xs text-muted-foreground pt-1">
              Touches: {preview.summary.affected_models.join(", ")}
            </p>
          )}
          {preview.summary.blocked.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-amber-700">Blocked ({preview.summary.blocked.length})</summary>
              <ul className="mt-1 pl-4 list-disc">
                {preview.summary.blocked.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
