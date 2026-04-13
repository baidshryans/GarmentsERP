import { useState } from "react";
import { Loader2, Search, Download, Merge, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchMergeBarcodeReport } from "@/services/apiService";

function fmt(v, dec = 3) {
  const n = parseFloat(v);
  return isNaN(n) ? "—" : n.toFixed(dec);
}
function fmtDate(d) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-IN");
}

const TH = ({ children, className = "", ...props }) => (
  <th className={`px-3 py-2 text-left text-xs font-semibold text-muted-foreground whitespace-nowrap ${className}`} {...props}>
    {children}
  </th>
);
const TD = ({ children, className = "" }) => (
  <td className={`px-3 py-2 text-sm border-b border-border ${className}`}>{children}</td>
);

export default function BarcodeMergeReport() {
  const today = new Date().toISOString().split("T")[0];
  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);

  const fetchData = async () => {
    if (!fromDate || !toDate) return;
    setLoading(true);
    setError("");
    const res = await fetchMergeBarcodeReport(fromDate, toDate);
    if (res.success) {
      const data = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setRows(data);
      setSearched(true);
    } else {
      setError(typeof res.error === "string" ? res.error : JSON.stringify(res.error));
    }
    setLoading(false);
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
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `barcode_merge_${fromDate}_${toDate}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handlePrint = () => {
    const tableEl = document.querySelector("#merge-report-table");
    if (!tableEl) return;
    const win = window.open("", "_blank", "width=900,height=600");
    win.document.write(`<!DOCTYPE html><html><head><title>Barcode Merge Report ${fromDate} – ${toDate}</title>
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
<h2>Barcode Merge Report</h2>
<p>${fromDate} — ${toDate} &nbsp;·&nbsp; ${rows.length} record${rows.length !== 1 ? "s" : ""}</p>
${tableEl.outerHTML}
</body></html>`);
    win.document.close();
    win.focus();
    setTimeout(() => { win.print(); win.close(); }, 300);
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filter bar */}
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex flex-col gap-1">
            <Label className="text-xs">From Date</Label>
            <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="h-9 text-sm w-40" />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs">To Date</Label>
            <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="h-9 text-sm w-40" />
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
        <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/30">
          <div className="flex items-center gap-2">
            <Merge className="size-4 text-primary" />
            <span className="font-semibold text-sm">Barcode Merge Report</span>
            {searched && (
              <span className="ml-2 text-xs text-muted-foreground">
                {fromDate} — {toDate} · {rows.length} record{rows.length !== 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table id="merge-report-table" className="w-full table-auto">
            <thead className="bg-muted/50">
              <tr className="border-b border-border">
                <TH rowSpan={2} className="border-r border-border align-middle w-24">Date</TH>
                <TH colSpan={5} className="text-center border-r border-border border-b border-border pb-1">Source Barcode (Old)</TH>
                <TH colSpan={5} className="text-center border-b border-border pb-1">Merged Into (New)</TH>
              </tr>
              <tr className="border-b border-border">
                <TH>Barcode</TH>
                <TH>Item</TH>
                <TH className="text-right">Pcs</TH>
                <TH className="text-right">GW</TH>
                <TH className="text-right border-r border-border">NW</TH>
                <TH>Barcode</TH>
                <TH>Item</TH>
                <TH className="text-right">Pcs</TH>
                <TH className="text-right">GW</TH>
                <TH className="text-right">NW</TH>
              </tr>
            </thead>
            <tbody>
              {!searched && !loading && (
                <tr>
                  <TD colSpan={11} className="text-center py-12 text-muted-foreground text-sm border-b-0">
                    Select a date range and click Search to view merge records.
                  </TD>
                </tr>
              )}
              {loading && (
                <tr>
                  <TD colSpan={11} className="text-center py-12 border-b-0">
                    <Loader2 className="size-5 animate-spin text-primary mx-auto" />
                  </TD>
                </tr>
              )}
              {searched && !loading && rows.length === 0 && (
                <tr>
                  <TD colSpan={11} className="text-center py-12 text-muted-foreground text-sm border-b-0">
                    No merge transactions found for the selected date range.
                  </TD>
                </tr>
              )}
              {!loading && rows.map((row) => (
                <tr key={row.id} className="hover:bg-muted/30 transition-colors">
                  <TD className="whitespace-nowrap border-r border-border">{fmtDate(row.date1)}</TD>
                  {/* Old (source) barcode */}
                  <TD>
                    <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                      {row.old_barcode?.barcode ?? "—"}
                    </span>
                  </TD>
                  <TD>{row.old_barcode?.item?.item_name ?? "—"}</TD>
                  <TD className="text-right">{row.old_barcode?.pcs ?? "—"}</TD>
                  <TD className="text-right font-mono text-xs">{fmt(row.old_barcode?.gw)}</TD>
                  <TD className="text-right font-mono text-xs border-r border-border">{fmt(row.old_barcode?.nw)}</TD>
                  {/* New (merged) barcode */}
                  <TD>
                    <span className="font-mono text-xs bg-green-50 text-green-800 px-1.5 py-0.5 rounded">
                      {row.new_barcode?.barcode ?? "—"}
                    </span>
                  </TD>
                  <TD>{row.new_barcode?.item?.item_name ?? "—"}</TD>
                  <TD className="text-right">{row.new_barcode?.pcs ?? "—"}</TD>
                  <TD className="text-right font-mono text-xs">{fmt(row.new_barcode?.gw)}</TD>
                  <TD className="text-right font-mono text-xs">{fmt(row.new_barcode?.nw)}</TD>
                </tr>
              ))}
            </tbody>
            {rows.length > 0 && (
              <tfoot className="bg-muted/50 border-t-2 border-border font-semibold text-sm">
                <tr>
                  <td className="px-3 py-2 text-xs text-muted-foreground border-r border-border">Totals</td>
                  <td colSpan={2} />
                  <td className="px-3 py-2 text-right">
                    {rows.reduce((s, r) => s + (r.old_barcode?.pcs || 0), 0)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs">
                    {fmt(rows.reduce((s, r) => s + parseFloat(r.old_barcode?.gw || 0), 0))}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs border-r border-border">
                    {fmt(rows.reduce((s, r) => s + parseFloat(r.old_barcode?.nw || 0), 0))}
                  </td>
                  <td colSpan={2} />
                  <td className="px-3 py-2 text-right">
                    {rows.reduce((s, r) => s + (r.new_barcode?.pcs || 0), 0)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs">
                    {fmt(rows.reduce((s, r) => s + parseFloat(r.new_barcode?.gw || 0), 0))}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-xs">
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
