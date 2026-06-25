import { useEffect, useState } from "react";
import { formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { RefreshCw, Search, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchAdvanceRegister } from "@/services/apiService";

const fmt = (v) =>
  formatNumber(v, { decimals: 2 });

const STATUS_STYLES = {
  Billed:  "bg-emerald-100 text-emerald-800",
  Partial: "bg-amber-100 text-amber-800",
  "":      "bg-slate-100 text-slate-700",
};

export default function AdvanceRegister() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");

  const load = async () => {
    setError("");
    setLoading(true);
    const res = await fetchAdvanceRegister();
    if (res.success) {
      setData(res.data);
    } else {
      setError(typeof res.error === "string" ? res.error : "Failed to load advance register.");
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  const rows = (data?.rows || []).filter((r) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      (r.order_no || "").toLowerCase().includes(q) ||
      (r.ldgr_name || "").toLowerCase().includes(q)
    );
  });

  const totals = data?.totals || { received: 0, reconciled: 0, remaining: 0 };

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex-1 min-w-[240px] max-w-sm relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            placeholder="Search order no or party…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
        <Button size="sm" onClick={load} className="h-9 gap-2" disabled={loading}>
          <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Totals */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="rounded-lg border border-border bg-background px-4 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Total Received
          </div>
          <div className="text-base font-bold mt-1">₹{fmt(totals.received)}</div>
        </div>
        <div className="rounded-lg border border-border bg-background px-4 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700">
            Already Reconciled
          </div>
          <div className="text-base font-bold mt-1 text-emerald-700">
            ₹{fmt(totals.reconciled)}
          </div>
        </div>
        <div className="rounded-lg border border-primary bg-primary/5 px-4 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-primary">
            Available to Apply
          </div>
          <div className="text-base font-bold mt-1 text-primary">
            ₹{fmt(totals.remaining)}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Order No</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Date</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Party</th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Status</th>
              <th className="text-right px-4 py-2 text-xs font-semibold uppercase tracking-wider">Received</th>
              <th className="text-right px-4 py-2 text-xs font-semibold uppercase tracking-wider">Reconciled</th>
              <th className="text-right px-4 py-2 text-xs font-semibold uppercase tracking-wider">Remaining</th>
              <th className="w-12"></th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [...Array(4)].map((_, i) => (
                <tr key={i}>
                  <td colSpan={8} className="px-4 py-2">
                    <Skeleton className="h-5 w-full" />
                  </td>
                </tr>
              ))}
            {!loading && rows.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-muted-foreground py-8 text-sm">
                  No advance receipts found.
                </td>
              </tr>
            )}
            {!loading &&
              rows.map((r) => (
                <tr key={r.order_id} className="border-t border-border hover:bg-muted/20">
                  <td className="px-4 py-2 font-mono font-medium">{r.order_no}</td>
                  <td className="px-4 py-2 text-muted-foreground">{r.date}</td>
                  <td className="px-4 py-2">{r.ldgr_name}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                        STATUS_STYLES[r.status] ?? STATUS_STYLES[""]
                      }`}
                    >
                      {r.status || "Open"}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-right font-medium">₹{fmt(r.received)}</td>
                  <td className="px-4 py-2 text-right text-emerald-700">
                    {r.reconciled > 0 ? `₹${fmt(r.reconciled)}` : "—"}
                  </td>
                  <td className="px-4 py-2 text-right font-bold text-primary">
                    ₹{fmt(r.remaining)}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <Link
                      to={`/sales/customerorder/${r.order_id}`}
                      className="inline-flex items-center text-muted-foreground hover:text-primary"
                      title="Open order"
                    >
                      <ExternalLink className="size-4" />
                    </Link>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
