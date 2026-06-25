import { useState, useEffect } from "react";
import { formatDate } from "@/lib/format";
import { Loader2, Search, Download, GitBranch, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchSplitBarcodeReport } from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

function fmt(v, dec = 3) {
  const n = parseFloat(v);
  return isNaN(n) ? "—" : n.toFixed(dec);
}
function fmtDate(d) {
  if (!d) return "—";
  return formatDate(d, "numeric");
}

const TH = ({ children, className = "" }) => (
  <th className={`px-3 py-2 text-left text-xs font-semibold text-muted-foreground whitespace-nowrap ${className}`}>
    {children}
  </th>
);
const TD = ({ children, className = "" }) => (
  <td className={`px-3 py-2 text-sm border-b border-border ${className}`}>{children}</td>
);

export default function BarcodeSplitReport() {
  const today = new Date().toISOString().split("T")[0];
  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);

  const fetchData = async () => {
    if (!fromDate || !toDate) return;
    if (!isValidDateRange(fromDate, toDate)) {
      setError("From date cannot be after To date.");
      return;
    }
    setLoading(true);
    setError("");
    const res = await fetchSplitBarcodeReport(fromDate, toDate);
    if (res.success) {
      const data = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setRows(data);
      setSearched(true);
    } else {
      setError(typeof res.error === "string" ? res.error : JSON.stringify(res.error));
    }
    setLoading(false);
  };

  const handlePrint = () => {
    const tableEl = document.querySelector("#split-report-table");
    if (!tableEl) return;
    const win = window.open("", "_blank", "width=900,height=600");
    win.document.write(`<!DOCTYPE html><html><head><title>Barcode Split Report ${fromDate} – ${toDate}</title>
<style>
  body { font-family: sans-serif; font-size: 11px; padding: 16px; }
  h2 { font-size: 14px; margin-bottom: 4px; }
  p { margin: 0 0 12px; color: #666; font-size: 11px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; font-size: 11px; }
  th { background: #f3f4f6; font-weight: 600; }
  .text-right { text-align: right; }
  tfoot td { font-weight: 600; background: #f3f4f6; }
  @media print { @page { margin: 10mm; size: landscape; } }
</style></head><body>
<h2>Barcode Split Report</h2>
<p>${fromDate} — ${toDate} &nbsp;·&nbsp; ${rows.length} record${rows.length !== 1 ? "s" : ""}</p>
${tableEl.outerHTML}
</body></html>`);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); win.close(); }, 300);
  };

  const exportCSV = () => {
    const headers = ["Date","Old Barcode","Old Item","Old Pcs","Old GW","Old NW","New Barcode","New Item","New Pcs","New GW","New NW"];
    const csvRows = rows.map((r) => [
      fmtDate(r.date1),
      r.old_barcode?.barcode ?? "—",
      r.old_barcode?.item?.item_name ?? "—",
      r.old_barcode?.pcs ?? "",
      fmt(r.old_barcode?.gw),
      fmt(r.old_barcode?.nw),
      r.new_barcode?.barcode ?? "—",
      r.new_barcode?.item?.item_name ?? "—",
      r.new_barcode?.pcs ?? "",
      fmt(r.new_barcode?.gw),
      fmt(r.new_barcode?.nw),
    ]);
    const csv = [headers, ...csvRows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `barcode_split_${fromDate}_${toDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filter bar */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">From Date</Label>
            <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} className="h-9 text-sm w-40" />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">To Date</Label>
            <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} className="h-9 text-sm w-40" />
          </div>
          <Button onClick={fetchData} disabled={loading} className="bg-primary hover:bg-primary text-white h-9">
            {loading ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : <Search className="size-4 mr-1.5" />}
            {loading ? "Loading..." : "Search"}
          </Button>
          {rows.length > 0 && (
            <>
              <Button variant="outline" size="sm" onClick={exportCSV} className="h-9">
                <Download className="size-4 mr-1.5" /> Export CSV
              </Button>
              <Button variant="outline" size="sm" onClick={handlePrint} className="h-9">
                <Printer className="size-4 mr-1.5" /> Print
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Results */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/30">
          <div className="flex items-center gap-2">
            <GitBranch className="size-4 text-primary" />
            <span className="font-semibold text-sm">Barcode Split Report</span>
            {searched && (
              <span className="ml-2 text-xs text-muted-foreground">
                {fromDate} — {toDate} · {rows.length} record{rows.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table id="split-report-table" className="w-full border-collapse">
            <thead>
              {/* ── Group header row ── */}
              <tr className="border-b border-border">
                <th rowSpan={2} className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground bg-muted/50 border-r border-border w-10">#</th>
                <th rowSpan={2} className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground bg-muted/50 border-r border-border whitespace-nowrap">Date</th>
                <th colSpan={5} className="px-3 py-2 text-center text-xs font-bold text-amber-700 bg-amber-50 border-r border-border tracking-wide uppercase">
                  Old Barcode
                </th>
                <th colSpan={5} className="px-3 py-2 text-center text-xs font-bold text-primary bg-accent-50 tracking-wide uppercase">
                  New Barcode
                </th>
              </tr>
              {/* ── Sub-column header row ── */}
              <tr className="border-b-2 border-border">
                <th className="px-3 py-2 text-left text-xs font-semibold text-amber-700 bg-amber-50/60 whitespace-nowrap">Barcode</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-amber-700 bg-amber-50/60">Item</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-amber-700 bg-amber-50/60">Pcs</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-amber-700 bg-amber-50/60">GW</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-amber-700 bg-amber-50/60 border-r border-border">NW</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-primary bg-accent-50/60 whitespace-nowrap">Barcode</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-primary bg-accent-50/60">Item</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-primary bg-accent-50/60">Pcs</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-primary bg-accent-50/60">GW</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-primary bg-accent-50/60">NW</th>
              </tr>
            </thead>
            <tbody>
              {!searched && !loading && (
                <tr>
                  <TD colSpan={12} className="text-center py-12 text-muted-foreground text-sm border-b-0">
                    Select a date range and click Search to view split records.
                  </TD>
                </tr>
              )}
              {loading && (
                <tr>
                  <TD colSpan={12} className="text-center py-12 border-b-0">
                    <Loader2 className="size-5 animate-spin text-primary mx-auto" />
                  </TD>
                </tr>
              )}
              {searched && !loading && rows.length === 0 && (
                <tr>
                  <TD colSpan={12} className="text-center py-12 text-muted-foreground text-sm border-b-0">
                    No split transactions found for the selected date range.
                  </TD>
                </tr>
              )}
              {!loading && rows.map((row, i) => (
                <tr key={row.id} className={`hover:bg-muted/30 transition-colors ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
                  <TD className="text-muted-foreground border-r border-border">{i + 1}</TD>
                  <TD className="whitespace-nowrap border-r border-border">{fmtDate(row.date1)}</TD>
                  {/* Old barcode columns */}
                  <TD className="bg-amber-50/20">
                    <span className="font-mono text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">
                      {row.old_barcode?.barcode ?? "—"}
                    </span>
                  </TD>
                  <TD className="bg-amber-50/20">{row.old_barcode?.item?.item_name ?? "—"}</TD>
                  <TD className="text-right bg-amber-50/20">{row.old_barcode?.pcs ?? "—"}</TD>
                  <TD className="text-right font-mono text-xs bg-amber-50/20">{fmt(row.old_barcode?.gw)}</TD>
                  <TD className="text-right font-mono text-xs bg-amber-50/20 border-r border-border">{fmt(row.old_barcode?.nw)}</TD>
                  {/* New barcode columns */}
                  <TD className="bg-accent-50/20">
                    <span className="font-mono text-xs bg-accent-100 text-primary px-1.5 py-0.5 rounded">
                      {row.new_barcode?.barcode ?? "—"}
                    </span>
                  </TD>
                  <TD className="bg-accent-50/20">{row.new_barcode?.item?.item_name ?? "—"}</TD>
                  <TD className="text-right bg-accent-50/20">{row.new_barcode?.pcs ?? "—"}</TD>
                  <TD className="text-right font-mono text-xs bg-accent-50/20">{fmt(row.new_barcode?.gw)}</TD>
                  <TD className="text-right font-mono text-xs bg-accent-50/20">{fmt(row.new_barcode?.nw)}</TD>
                </tr>
              ))}
            </tbody>
            {rows.length > 0 && (
              <tfoot className="border-t-2 border-border font-semibold text-sm">
                <tr>
                  <td colSpan={2} className="px-3 py-2.5 text-right text-xs text-muted-foreground border-r border-border">Totals →</td>
                  <td className="px-3 py-2.5 bg-amber-50/40" />
                  <td className="px-3 py-2.5 bg-amber-50/40" />
                  <td className="px-3 py-2.5 text-right bg-amber-50/40">
                    {rows.reduce((s, r) => s + (r.old_barcode?.pcs || 0), 0)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs bg-amber-50/40">
                    {fmt(rows.reduce((s, r) => s + parseFloat(r.old_barcode?.gw || 0), 0))}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs bg-amber-50/40 border-r border-border">
                    {fmt(rows.reduce((s, r) => s + parseFloat(r.old_barcode?.nw || 0), 0))}
                  </td>
                  <td className="px-3 py-2.5 bg-accent-50/40" />
                  <td className="px-3 py-2.5 bg-accent-50/40" />
                  <td className="px-3 py-2.5 text-right bg-accent-50/40">
                    {rows.reduce((s, r) => s + (r.new_barcode?.pcs || 0), 0)}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs bg-accent-50/40">
                    {fmt(rows.reduce((s, r) => s + parseFloat(r.new_barcode?.gw || 0), 0))}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs bg-accent-50/40">
                    {fmt(rows.reduce((s, r) => s + parseFloat(r.new_barcode?.nw || 0), 0))}
                  </td>
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </div>
    </div>
  );
}
