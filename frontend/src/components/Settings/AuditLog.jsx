import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/hooks/use-toast";
import { Search, ChevronLeft, ChevronRight, RefreshCw } from "lucide-react";
import { fetchAuditLog } from "@/services/apiService";

const EVENT_STYLE = {
  CREATE: "bg-green-50 text-green-700",
  UPDATE: "bg-blue-50  text-blue-700",
  DELETE: "bg-red-50   text-red-700",
};

export default function AuditLog() {
  const { toast }    = useToast();
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

  useEffect(() => { load(); }, []);

  const applyFilters = () => {
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

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-base font-semibold">Audit Log</h1>
        <Button size="sm" variant="outline" onClick={() => load(filters)} disabled={loading}>
          <RefreshCw className={`size-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* ── Filters ── */}
      <div className="flex flex-wrap items-end gap-3 p-3 rounded-xl border border-border bg-muted/30">
        <div>
          <Label className="text-xs">From Date</Label>
          <Input type="date" className="h-8 text-sm mt-1 w-36"
            value={filters.from_date} onChange={(e) => sf("from_date", e.target.value)} />
        </div>
        <div>
          <Label className="text-xs">To Date</Label>
          <Input type="date" className="h-8 text-sm mt-1 w-36"
            value={filters.to_date} onChange={(e) => sf("to_date", e.target.value)} />
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
                  {["Date & Time", "User", "Action", "Model", "Record", "Changed Fields"].map((h) => (
                    <th key={h} className="text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground px-4 py-2.5">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.results.length === 0 ? (
                  <tr><td colSpan={6} className="text-center py-8 text-muted-foreground text-sm">No events found.</td></tr>
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
                          <summary className="text-primary hover:underline text-[11px]">
                            View changes
                          </summary>
                          <pre className="mt-1 text-[10px] bg-muted rounded p-1 overflow-x-auto max-h-32 whitespace-pre-wrap">
                            {typeof e.changed_fields === "string"
                              ? e.changed_fields
                              : JSON.stringify(e.changed_fields, null, 2)}
                          </pre>
                        </details>
                      ) : "—"}
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
          <span className="text-xs text-muted-foreground">
            Page {data.page} / {data.num_pages}
          </span>
          <Button size="sm" variant="outline" disabled={data.page >= data.num_pages} onClick={() => goPage(data.page + 1)}>
            <ChevronRight className="size-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
