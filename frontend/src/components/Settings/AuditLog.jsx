import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import {
  Search, ChevronLeft, ChevronRight, RefreshCw, Undo2,
  History, AlertTriangle, LogIn, Loader2,
} from "lucide-react";
import {
  fetchAuditLog, reverseTransaction, restoreToPoint,
  fetchLoginLog, fetchAuditDetail,
} from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

const EVENT_STYLE = {
  CREATE: "bg-green-50 text-green-700",
  UPDATE: "bg-blue-50  text-blue-700",
  DELETE: "bg-red-50   text-red-700",
};

// ── Diff cell: fetches old/new on first click, then shows inline table ────────
function DiffCell({ row }) {
  const [state, setState] = useState("idle"); // idle | loading | done | error
  const [changes, setChanges] = useState([]);

  // Only UPDATE rows can have a meaningful diff
  if (row.event_type !== "UPDATE") return <span className="text-muted-foreground">—</span>;

  async function load() {
    if (state !== "idle") return;
    setState("loading");
    const res = await fetchAuditDetail(row.id);
    if (res.success) {
      setChanges(res.data.changes || []);
      setState("done");
    } else {
      setState("error");
    }
  }

  if (state === "idle") {
    return (
      <button
        onClick={load}
        className="text-[11px] text-primary hover:underline"
      >
        View diff
      </button>
    );
  }
  if (state === "loading") {
    return <Loader2 className="size-3 animate-spin text-muted-foreground" />;
  }
  if (state === "error") {
    return <span className="text-[10px] text-red-500">Failed to load</span>;
  }
  if (changes.length === 0) {
    return <span className="text-[10px] text-muted-foreground">No field changes recorded</span>;
  }
  return (
    <details open className="text-[10px]">
      <summary className="cursor-pointer text-primary hover:underline text-[11px] mb-1">
        {changes.length} field{changes.length !== 1 ? "s" : ""} changed
      </summary>
      <table className="w-full border-collapse mt-1 text-[10px]">
        <thead>
          <tr className="bg-muted/60">
            <th className="text-left px-1.5 py-0.5 font-semibold">Field</th>
            <th className="text-left px-1.5 py-0.5 font-semibold text-red-600">Old</th>
            <th className="text-left px-1.5 py-0.5 font-semibold text-green-700">New</th>
          </tr>
        </thead>
        <tbody>
          {changes.map((c, i) => (
            <tr key={i} className={i % 2 === 1 ? "bg-muted/20" : ""}>
              <td className="px-1.5 py-0.5 font-mono">{c.field}</td>
              <td className="px-1.5 py-0.5 text-red-600 max-w-[120px] truncate" title={c.old ?? "—"}>{c.old ?? <span className="italic text-muted-foreground">null</span>}</td>
              <td className="px-1.5 py-0.5 text-green-700 max-w-[120px] truncate" title={c.new ?? "—"}>{c.new ?? <span className="italic text-muted-foreground">null</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

export default function AuditLog() {
  const { toast } = useToast();
  const [tab, setTab] = useState("log"); // "log" | "logins" | "restore"
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

  // ── Reverse a single transaction ──────────────────────────────────────────
  async function handleReverse(row) {
    if (!row.history_transaction_id) {
      toast({ title: "This event has no transaction id — cannot reverse.", variant: "destructive" });
      return;
    }
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
          <Button size="sm" variant={tab === "logins" ? "default" : "ghost"} className="h-7 text-xs" onClick={() => setTab("logins")}>
            <LogIn className="size-3.5 mr-1" /> Login Activity
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
                        <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[280px]">
                          <DiffCell row={e} />
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

      {tab === "logins" && <LoginActivityTab toast={toast} />}

      {tab === "restore" && <RestorePointsTab toast={toast} />}
    </div>
  );
}

// ── Login Activity Tab ────────────────────────────────────────────────────────

function LoginActivityTab({ toast }) {
  const [data, setData]       = useState({ results: [], count: 0, num_pages: 1, page: 1 });
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ from_date: "", to_date: "", action: "", username: "", page: 1 });

  const load = useCallback(async (f = filters) => {
    setLoading(true);
    const params = {};
    if (f.from_date) params.from_date = f.from_date;
    if (f.to_date)   params.to_date   = f.to_date;
    if (f.action)    params.action    = f.action;
    if (f.username)  params.username  = f.username;
    params.page = f.page;
    const res = await fetchLoginLog(params);
    if (res.success) setData(res.data);
    else toast({ title: "Failed to load login log", variant: "destructive" });
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, []);

  const sf = (k, v) => setFilters((prev) => ({ ...prev, [k]: v }));
  const apply = () => { const f = { ...filters, page: 1 }; setFilters(f); load(f); };
  const goPage = (p) => { const f = { ...filters, page: p }; setFilters(f); load(f); };

  return (
    <>
      {/* Filters */}
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
          <Label className="text-xs">Username</Label>
          <Input className="h-8 text-sm mt-1 w-36" placeholder="Search user…"
            value={filters.username} onChange={(e) => sf("username", e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && apply()} />
        </div>
        <div>
          <Label className="text-xs">Action</Label>
          <select className="h-8 text-sm mt-1 border rounded-md px-2 bg-background"
            value={filters.action} onChange={(e) => sf("action", e.target.value)}>
            <option value="">All</option>
            <option value="login">Login</option>
            <option value="logout">Logout</option>
          </select>
        </div>
        <Button size="sm" className="h-8" onClick={apply}>
          <Search className="size-3.5 mr-1.5" /> Search
        </Button>
        <Button size="sm" variant="outline" className="h-8" onClick={() => {
          const f = { from_date: "", to_date: "", action: "", username: "", page: 1 };
          setFilters(f); load(f);
        }}>Clear</Button>
      </div>

      <p className="text-xs text-muted-foreground">
        {data.count.toLocaleString()} event{data.count !== 1 ? "s" : ""} found
        {data.num_pages > 1 && ` — Page ${data.page} of ${data.num_pages}`}
      </p>

      {loading ? (
        <div className="flex flex-col gap-2">{[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}</div>
      ) : (
        <div className="rounded-xl border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 border-b border-border">
                  {["Date & Time", "Username", "Action", "Result", "IP Address", "Retail", "User Agent"].map((h) => (
                    <th key={h} className="text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-4 py-2.5">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.results.length === 0 ? (
                  <tr><td colSpan={7} className="text-center py-8 text-muted-foreground text-sm">No login events found.</td></tr>
                ) : data.results.map((e, i) => (
                  <tr key={e.id} className={`border-b border-border last:border-0 hover:bg-accent/30 transition-colors ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
                    <td className="px-4 py-2.5 font-mono text-xs whitespace-nowrap">{e.timestamp}</td>
                    <td className="px-4 py-2.5 text-xs font-medium">{e.username_attempted || e.user || "—"}</td>
                    <td className="px-4 py-2.5">
                      <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold ${e.action === "login" ? "bg-blue-50 text-blue-700" : "bg-gray-100 text-gray-600"}`}>
                        {e.action}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold ${e.success ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                        {e.success ? "Success" : "Failed"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs">{e.ip_address || "—"}</td>
                    <td className="px-4 py-2.5 text-xs">{e.retail || "—"}</td>
                    <td className="px-4 py-2.5 text-xs text-muted-foreground max-w-[200px] truncate" title={e.user_agent}>{e.user_agent || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
  );
}

// ── Restore Points Tab ────────────────────────────────────────────────────────

function RestorePointsTab({ toast }) {
  const [timestamp, setTimestamp] = useState(() => {
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
