import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { fetchAgedReceivables } from "@/services/apiService";

const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const BUCKETS = [
  { key: "b0_30",    label: "0�30 days",  color: "text-emerald-700" },
  { key: "b31_60",   label: "31�60 days", color: "text-primary" },
  { key: "b61_90",   label: "61�90 days", color: "text-amber-600" },
  { key: "b90_plus", label: "90+ days",   color: "text-rose-600" },
];

export default function AgedReceivables() {
  const [kind, setKind] = useState("sales");
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState({});

  const load = async () => {
    setError("");
    setLoading(true);
    const res = await fetchAgedReceivables(kind);
    if (res.success) {
      setReport(res.data);
      setExpanded({});
    } else {
      setError(typeof res.error === "string" ? res.error : "Failed to load report.");
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  const toggle = (id) => setExpanded((p) => ({ ...p, [id]: !p[id] }));

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Report Type</Label>
          <div className="flex rounded-md overflow-hidden border border-border">
            {[
              { k: "sales",    lbl: "Receivables (Debtors)" },
              { k: "purchase", lbl: "Payables (Creditors)" },
            ].map((t) => (
              <button
                key={t.k}
                onClick={() => setKind(t.k)}
                className={`px-4 py-1.5 text-sm font-medium transition-colors ${
                  kind === t.k
                    ? "bg-primary text-primary-foreground"
                    : "bg-background text-muted-foreground hover:bg-muted"
                }`}
              >
                {t.lbl}
              </button>
            ))}
          </div>
        </div>
        <Button size="sm" onClick={load} className="h-9 gap-2" disabled={loading}>
          <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
        {report?.as_of && (
          <div className="ml-auto text-xs text-muted-foreground">
            As of <span className="font-semibold">{report.as_of}</span>
          </div>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Totals summary */}
      {report && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {BUCKETS.map((b) => (
            <div
              key={b.key}
              className="rounded-lg border border-border bg-background px-4 py-3 text-center"
            >
              <div className={`text-[11px] font-semibold uppercase tracking-wider ${b.color}`}>
                {b.label}
              </div>
              <div className={`text-base font-bold mt-1 ${b.color}`}>
                ₹{fmt(report.totals?.[b.key])}
              </div>
            </div>
          ))}
          <div className="rounded-lg border border-primary bg-primary/5 px-4 py-3 text-center">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-primary">Total</div>
            <div className="text-base font-bold mt-1 text-primary">
              ₹{fmt(report.totals?.total)}
            </div>
          </div>
        </div>
      )}

      {/* Party table */}
      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/40">
            <tr>
              <th className="w-10"></th>
              <th className="text-left px-4 py-2 text-xs font-semibold uppercase tracking-wider">Party</th>
              {BUCKETS.map((b) => (
                <th
                  key={b.key}
                  className={`text-right px-4 py-2 text-xs font-semibold uppercase tracking-wider ${b.color}`}
                >
                  {b.label}
                </th>
              ))}
              <th className="text-right px-4 py-2 text-xs font-semibold uppercase tracking-wider">Total</th>
            </tr>
          </thead>
          <tbody>
            {loading &&
              [...Array(4)].map((_, i) => (
                <tr key={i}>
                  <td colSpan={7} className="px-4 py-2">
                    <Skeleton className="h-5 w-full" />
                  </td>
                </tr>
              ))}
            {!loading && report?.rows?.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center text-muted-foreground py-8 text-sm">
                  No outstanding bills.
                </td>
              </tr>
            )}
            {!loading &&
              report?.rows?.map((r) => (
                <React.Fragment key={r.ldgr_id}>
                  <tr
                    className="border-t border-border hover:bg-muted/20 cursor-pointer"
                    onClick={() => toggle(r.ldgr_id)}
                  >
                    <td className="px-2">
                      {expanded[r.ldgr_id] ? (
                        <ChevronDown className="size-4 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="size-4 text-muted-foreground" />
                      )}
                    </td>
                    <td className="px-4 py-2 font-medium">{r.ldgr_name}</td>
                    {BUCKETS.map((b) => (
                      <td key={b.key} className={`px-4 py-2 text-right ${b.color}`}>
                        {r[b.key] > 0 ? `₹${fmt(r[b.key])}` : "�"}
                      </td>
                    ))}
                    <td className="px-4 py-2 text-right font-bold">₹{fmt(r.total)}</td>
                  </tr>
                  {expanded[r.ldgr_id] && (
                    <tr className="bg-muted/10">
                      <td></td>
                      <td colSpan={6} className="px-4 py-3">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-muted-foreground">
                              <th className="text-left py-1 font-semibold">Bill No</th>
                              <th className="text-left py-1 font-semibold">Date</th>
                              <th className="text-right py-1 font-semibold">Age (days)</th>
                              <th className="text-right py-1 font-semibold">Outstanding</th>
                            </tr>
                          </thead>
                          <tbody>
                            {r.bills.map((b) => (
                              <tr key={b.billno} className="border-t border-border/40">
                                <td className="py-1 font-mono">{b.billno}</td>
                                <td className="py-1">{b.date}</td>
                                <td className="py-1 text-right">{b.age}</td>
                                <td className="py-1 text-right font-medium">₹{fmt(b.due_amt)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
