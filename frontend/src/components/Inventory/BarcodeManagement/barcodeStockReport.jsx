import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Printer } from "lucide-react";
import {
  fetchBarcodeStockReport,
  fetchBarcodeStockReportBarcodes,
} from "../../../services/apiService";

const COLUMN_LABELS = {
  opening: "Opening",
  create_pur: "Purchase",
  create_rec: "Karigar Receipt",
  sale_ret: "Sale Return",
  sale_app_ret: "Approval Return",
  trf_rr_in: "Transfer In",
  bar_mer_crt: "Merge Created",
  bar_split_crt: "Split Created",
  sale: "Sale",
  sale_app: "Sale Approval",
  trf_rr_out: "Transfer Out",
  bar_mer: "Merge Consumed",
  bar_split: "Split Consumed",
  bar_trf_unb: "Barcode Unbar",
  pur_ret: "Purchase Return",
  stock: "In Stock",
};

const today = new Date().toISOString().split("T")[0];

const ColGroup = ({ label, span, className = "" }) => (
  <th
    colSpan={span}
    className={`px-2 py-1.5 text-center text-[10px] uppercase tracking-wider font-semibold border border-border ${className}`}
  >
    {label}
  </th>
);

const SubHead = ({ label, className = "" }) => (
  <th
    className={`px-2 py-1.5 text-right text-[10px] uppercase tracking-wider font-medium border border-border whitespace-nowrap ${className}`}
  >
    {label}
  </th>
);

const Td = ({ children, className = "" }) => (
  <td
    className={`px-2 py-1.5 text-right text-xs border border-border tabular-nums ${className}`}
  >
    {children}
  </td>
);

const CTd = ({ value, onClick, className = "" }) => {
  const clickable = !!value;
  return (
    <td
      className={`px-2 py-1.5 text-right text-xs border border-border tabular-nums ${className} ${
        clickable
          ? "cursor-pointer hover:underline hover:bg-accent/30 text-primary"
          : "text-muted-foreground"
      }`}
      onClick={clickable ? onClick : undefined}
    >
      {value ? value : "-"}
    </td>
  );
};

const INFLOW_KEYS = [
  "create_pur", "create_rec", "sale_ret", "sale_app_ret",
  "trf_rr_in", "bar_mer_crt", "bar_split_crt",
];
const OUTFLOW_KEYS = [
  "sale", "sale_app", "trf_rr_out",
  "bar_mer", "bar_split", "bar_trf_unb", "pur_ret",
];
const ALL_KEYS = ["opening", ...INFLOW_KEYS, "inflow", ...OUTFLOW_KEYS, "outflow", "stock"];
const ALL_KEYS_WITH_COUNT = ALL_KEYS.flatMap((k) => [k, `${k}_count`]);

export default function BarcodeStockReport() {
  const [asOnDate, setAsOnDate] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [drill, setDrill] = useState(null); // { item, column, rows, loading, error }
  const [metric, setMetric] = useState("pcs"); // "pcs" | "barcodes"

  const k = (base) => (metric === "pcs" ? base : `${base}_count`);
  const metricLabel = metric === "pcs" ? "Pcs" : "Barcodes";

  const openDrill = async (item, column) => {
    const count = item[column] || item[`${column}_count`] || 0;
    if (!count) return;
    setDrill({ item, column, rows: [], loading: true, error: "" });
    const res = await fetchBarcodeStockReportBarcodes({
      itemId: item.id ?? item.item_id,
      column,
      asOnDate,
    });
    if (res.success) {
      setDrill((d) => d && { ...d, rows: res.data, loading: false });
    } else {
      setDrill((d) => d && {
        ...d,
        loading: false,
        error: typeof res.error === "string" ? res.error : "Failed to load barcodes.",
      });
    }
  };

  const closeDrill = () => setDrill(null);

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    const res = await fetchBarcodeStockReport(asOnDate);
    if (res.success) {
      setData(res.data);
    } else {
      setError(typeof res.error === "string" ? res.error : "Failed to load report.");
    }
    setLoading(false);
  };

  const totals = data?.reduce(
    (acc, d) => {
      for (const key of ALL_KEYS_WITH_COUNT) acc[key] += d[key] || 0;
      return acc;
    },
    Object.fromEntries(ALL_KEYS_WITH_COUNT.map((key) => [key, 0]))
  );

  const v = (n) => (n ? n : "-");

  const printReport = () => {
    if (!data || data.length === 0) return;

    const fmtDate = (d) => {
      const [y, m, day] = d.split("-");
      return `${day}/${m}/${y}`;
    };

    const headerRow = `
      <tr>
        <th colspan="2" style="background:#f1f5f9;text-align:left">Item</th>
        <th colspan="1" style="background:#eff6ff">Opening</th>
        <th colspan="8" style="background:#f0fdf4">Inflows</th>
        <th colspan="8" style="background:#fef2f2">Outflows</th>
        <th colspan="1" style="background:#faf5ff">Stock</th>
      </tr>
      <tr>
        <th style="text-align:left">Code</th>
        <th style="text-align:left">Name</th>
        <th style="background:#eff6ff">${metricLabel}</th>
        <th style="background:#f0fdf4">Purchase</th>
        <th style="background:#f0fdf4">Kar Rec</th>
        <th style="background:#f0fdf4">Sale Ret</th>
        <th style="background:#f0fdf4">App Ret</th>
        <th style="background:#f0fdf4">Trf In</th>
        <th style="background:#f0fdf4">Merge Crt</th>
        <th style="background:#f0fdf4">Split Crt</th>
        <th style="background:#dcfce7;font-weight:700">Total</th>
        <th style="background:#fef2f2">Sale</th>
        <th style="background:#fef2f2">Sale App</th>
        <th style="background:#fef2f2">Trf Out</th>
        <th style="background:#fef2f2">Merge</th>
        <th style="background:#fef2f2">Split</th>
        <th style="background:#fef2f2">Trf Unbar</th>
        <th style="background:#fef2f2">Pur Ret</th>
        <th style="background:#fecaca;font-weight:700">Total</th>
        <th style="background:#f3e8ff;font-weight:700">${metricLabel}</th>
      </tr>`;

    const dataRows = data.map((d, i) => `
      <tr style="${i % 2 === 1 ? "background:#f8fafc" : ""}">
        <td style="text-align:left;font-weight:600">${d.short_code}</td>
        <td style="text-align:left">${d.item_name || d.short_code}</td>
        <td style="background:#eff6ff">${v(d[k("opening")])}</td>
        <td style="background:#f0fdf4">${v(d[k("create_pur")])}</td>
        <td style="background:#f0fdf4">${v(d[k("create_rec")])}</td>
        <td style="background:#f0fdf4">${v(d[k("sale_ret")])}</td>
        <td style="background:#f0fdf4">${v(d[k("sale_app_ret")])}</td>
        <td style="background:#f0fdf4">${v(d[k("trf_rr_in")])}</td>
        <td style="background:#f0fdf4">${v(d[k("bar_mer_crt")])}</td>
        <td style="background:#f0fdf4">${v(d[k("bar_split_crt")])}</td>
        <td style="background:#dcfce7;font-weight:600">${v(d[k("inflow")])}</td>
        <td style="background:#fef2f2">${v(d[k("sale")])}</td>
        <td style="background:#fef2f2">${v(d[k("sale_app")])}</td>
        <td style="background:#fef2f2">${v(d[k("trf_rr_out")])}</td>
        <td style="background:#fef2f2">${v(d[k("bar_mer")])}</td>
        <td style="background:#fef2f2">${v(d[k("bar_split")])}</td>
        <td style="background:#fef2f2">${v(d[k("bar_trf_unb")])}</td>
        <td style="background:#fef2f2">${v(d[k("pur_ret")])}</td>
        <td style="background:#fecaca;font-weight:600">${v(d[k("outflow")])}</td>
        <td style="background:#f3e8ff;font-weight:700;font-size:13px">${v(d[k("stock")])}</td>
      </tr>`).join("");

    const totalsRow = totals ? `
      <tr style="background:#e2e8f0;font-weight:700;border-top:2px solid #94a3b8">
        <td colspan="2" style="text-align:left">Total</td>
        <td style="background:#dbeafe">${v(totals[k("opening")])}</td>
        <td style="background:#bbf7d0">${v(totals[k("create_pur")])}</td>
        <td style="background:#bbf7d0">${v(totals[k("create_rec")])}</td>
        <td style="background:#bbf7d0">${v(totals[k("sale_ret")])}</td>
        <td style="background:#bbf7d0">${v(totals[k("sale_app_ret")])}</td>
        <td style="background:#bbf7d0">${v(totals[k("trf_rr_in")])}</td>
        <td style="background:#bbf7d0">${v(totals[k("bar_mer_crt")])}</td>
        <td style="background:#bbf7d0">${v(totals[k("bar_split_crt")])}</td>
        <td style="background:#86efac">${v(totals[k("inflow")])}</td>
        <td style="background:#fecaca">${v(totals[k("sale")])}</td>
        <td style="background:#fecaca">${v(totals[k("sale_app")])}</td>
        <td style="background:#fecaca">${v(totals[k("trf_rr_out")])}</td>
        <td style="background:#fecaca">${v(totals[k("bar_mer")])}</td>
        <td style="background:#fecaca">${v(totals[k("bar_split")])}</td>
        <td style="background:#fecaca">${v(totals[k("bar_trf_unb")])}</td>
        <td style="background:#fecaca">${v(totals[k("pur_ret")])}</td>
        <td style="background:#fca5a5">${v(totals[k("outflow")])}</td>
        <td style="background:#e9d5ff;font-size:13px">${v(totals[k("stock")])}</td>
      </tr>` : "";

    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Barcode Stock Report — As on ${fmtDate(asOnDate)}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; font-size: 11px; color: #1e293b; padding: 16px; }
    h2 { text-align: center; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
    p.sub { text-align: center; font-size: 11px; color: #64748b; margin-bottom: 14px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border: 1px solid #cbd5e1; padding: 4px 6px; text-align: right; white-space: nowrap; }
    thead tr:first-child th { font-size: 10px; text-transform: uppercase; letter-spacing: 0.05em; }
    thead tr:last-child th { font-size: 9px; text-transform: uppercase; }
    tfoot td { border-top: 2px solid #94a3b8; }
    @media print {
      @page { size: A4 landscape; margin: 8mm; }
      body { padding: 0; }
    }
  </style>
</head>
<body>
  <h2>Barcode Wise Stock Report (${metricLabel})</h2>
  <p class="sub">As on ${fmtDate(asOnDate)} &nbsp;|&nbsp; ${data.length} item${data.length !== 1 ? "s" : ""}</p>
  <table>
    <thead>${headerRow}</thead>
    <tbody>${dataRows}</tbody>
    <tfoot>${totalsRow}</tfoot>
  </table>
  <script>window.onload = () => { window.print(); }<\/script>
</body>
</html>`;

    const win = window.open("", "_blank");
    win.document.write(html);
    win.document.close();
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filter bar */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">As on Date</Label>
          <Input
            type="date"
            value={asOnDate}
            onChange={(e) => setAsOnDate(e.target.value)}
            className="h-9 w-40"
          />
        </div>
        <Button size="sm" onClick={fetchReport} disabled={loading} className="h-9">
          {loading ? "Loading..." : "Show"}
        </Button>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Show</Label>
          <div className="flex items-center gap-1 h-9 p-1 rounded-md border border-border bg-background">
            {[
              { key: "pcs", label: "Pcs" },
              { key: "barcodes", label: "Barcodes" },
            ].map((opt) => {
              const active = metric === opt.key;
              return (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => setMetric(opt.key)}
                  className={`px-3 h-7 rounded text-xs font-medium transition-colors ${
                    active
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent/40"
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={printReport}
          disabled={!data || data.length === 0}
          className="h-9"
        >
          <Printer className="size-4 mr-1" />
          Print PDF
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      )}

      {data && !loading && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                {/* Level 1: group headers */}
                <tr className="bg-muted/50">
                  <ColGroup label="Item" span={2} className="text-left !text-[11px]" />
                  <ColGroup label="Opening" span={1} className="bg-accent-50/60" />
                  <ColGroup label="Inflows" span={8} className="bg-green-50/60" />
                  <ColGroup label="Outflows" span={8} className="bg-red-50/60" />
                  <ColGroup label="Stock" span={1} className="bg-primary/5" />
                </tr>

                {/* Level 2: sub-column headers */}
                <tr className="bg-muted/30">
                  <SubHead label="Code" className="text-left !font-semibold w-20" />
                  <SubHead label="Name" className="text-left !font-semibold w-32" />
                  {/* Opening */}
                  <SubHead label={metricLabel} className="bg-accent-50/40" />
                  {/* Inflows */}
                  <SubHead label="Purchase" className="bg-green-50/40" />
                  <SubHead label="Kar Rec" className="bg-green-50/40" />
                  <SubHead label="Sale Ret" className="bg-green-50/40" />
                  <SubHead label="App Ret" className="bg-green-50/40" />
                  <SubHead label="Trf In" className="bg-green-50/40" />
                  <SubHead label="Merge Crt" className="bg-green-50/40" />
                  <SubHead label="Split Crt" className="bg-green-50/40" />
                  <SubHead label="Total" className="bg-green-50/40 !font-semibold" />
                  {/* Outflows */}
                  <SubHead label="Sale" className="bg-red-50/40" />
                  <SubHead label="Sale App" className="bg-red-50/40" />
                  <SubHead label="Trf Out" className="bg-red-50/40" />
                  <SubHead label="Merge" className="bg-red-50/40" />
                  <SubHead label="Split" className="bg-red-50/40" />
                  <SubHead label="Trf Unbar" className="bg-red-50/40" />
                  <SubHead label="Pur Ret" className="bg-red-50/40" />
                  <SubHead label="Total" className="bg-red-50/40 !font-semibold" />
                  {/* Stock */}
                  <SubHead label={metricLabel} className="bg-primary/5 !font-semibold" />
                </tr>
              </thead>

              <tbody>
                {data.length === 0 && (
                  <tr>
                    <td colSpan={20} className="text-center py-8 text-muted-foreground">
                      No stock data available for this date.
                    </td>
                  </tr>
                )}

                {data.map((d, i) => (
                  <tr
                    key={i}
                    className={`border-t border-border ${i % 2 === 1 ? "bg-muted/15" : ""} hover:bg-accent/20 transition-colors`}
                  >
                    <td className="px-2 py-1.5 text-left text-xs border border-border font-medium whitespace-nowrap">
                      <span className="text-[9px] bg-muted px-1 py-0.5 rounded font-semibold text-muted-foreground">
                        {d.short_code}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-left text-xs border border-border whitespace-nowrap">
                      {d.item_name || d.short_code}
                    </td>
                    {/* Opening */}
                    <CTd value={d[k("opening")]} onClick={() => openDrill(d, "opening")} className="bg-accent-50/20 font-medium" />
                    {/* Inflows */}
                    <CTd value={d[k("create_pur")]} onClick={() => openDrill(d, "create_pur")} className="bg-green-50/10" />
                    <CTd value={d[k("create_rec")]} onClick={() => openDrill(d, "create_rec")} className="bg-green-50/10" />
                    <CTd value={d[k("sale_ret")]} onClick={() => openDrill(d, "sale_ret")} className="bg-green-50/10" />
                    <CTd value={d[k("sale_app_ret")]} onClick={() => openDrill(d, "sale_app_ret")} className="bg-green-50/10" />
                    <CTd value={d[k("trf_rr_in")]} onClick={() => openDrill(d, "trf_rr_in")} className="bg-green-50/10" />
                    <CTd value={d[k("bar_mer_crt")]} onClick={() => openDrill(d, "bar_mer_crt")} className="bg-green-50/10" />
                    <CTd value={d[k("bar_split_crt")]} onClick={() => openDrill(d, "bar_split_crt")} className="bg-green-50/10" />
                    <Td className="bg-green-50/20 font-semibold">{v(d[k("inflow")])}</Td>
                    {/* Outflows */}
                    <CTd value={d[k("sale")]} onClick={() => openDrill(d, "sale")} className="bg-red-50/10" />
                    <CTd value={d[k("sale_app")]} onClick={() => openDrill(d, "sale_app")} className="bg-red-50/10" />
                    <CTd value={d[k("trf_rr_out")]} onClick={() => openDrill(d, "trf_rr_out")} className="bg-red-50/10" />
                    <CTd value={d[k("bar_mer")]} onClick={() => openDrill(d, "bar_mer")} className="bg-red-50/10" />
                    <CTd value={d[k("bar_split")]} onClick={() => openDrill(d, "bar_split")} className="bg-red-50/10" />
                    <CTd value={d[k("bar_trf_unb")]} onClick={() => openDrill(d, "bar_trf_unb")} className="bg-red-50/10" />
                    <CTd value={d[k("pur_ret")]} onClick={() => openDrill(d, "pur_ret")} className="bg-red-50/10" />
                    <Td className="bg-red-50/20 font-semibold">{v(d[k("outflow")])}</Td>
                    {/* Stock */}
                    <CTd value={d[k("stock")]} onClick={() => openDrill(d, "stock")} className="bg-primary/5 font-bold text-sm" />
                  </tr>
                ))}

                {/* Totals row */}
                {data.length > 0 && totals && (
                  <tr className="border-t-2 border-border bg-muted/40 font-semibold">
                    <td
                      colSpan={2}
                      className="px-2 py-2 text-left text-xs border border-border font-bold"
                    >
                      Total
                    </td>
                    <Td className="bg-accent-50/30 font-bold">{v(totals[k("opening")])}</Td>
                    <Td className="bg-green-50/20">{v(totals[k("create_pur")])}</Td>
                    <Td className="bg-green-50/20">{v(totals[k("create_rec")])}</Td>
                    <Td className="bg-green-50/20">{v(totals[k("sale_ret")])}</Td>
                    <Td className="bg-green-50/20">{v(totals[k("sale_app_ret")])}</Td>
                    <Td className="bg-green-50/20">{v(totals[k("trf_rr_in")])}</Td>
                    <Td className="bg-green-50/20">{v(totals[k("bar_mer_crt")])}</Td>
                    <Td className="bg-green-50/20">{v(totals[k("bar_split_crt")])}</Td>
                    <Td className="bg-green-50/30 font-bold">{v(totals[k("inflow")])}</Td>
                    <Td className="bg-red-50/20">{v(totals[k("sale")])}</Td>
                    <Td className="bg-red-50/20">{v(totals[k("sale_app")])}</Td>
                    <Td className="bg-red-50/20">{v(totals[k("trf_rr_out")])}</Td>
                    <Td className="bg-red-50/20">{v(totals[k("bar_mer")])}</Td>
                    <Td className="bg-red-50/20">{v(totals[k("bar_split")])}</Td>
                    <Td className="bg-red-50/20">{v(totals[k("bar_trf_unb")])}</Td>
                    <Td className="bg-red-50/20">{v(totals[k("pur_ret")])}</Td>
                    <Td className="bg-red-50/30 font-bold">{v(totals[k("outflow")])}</Td>
                    <Td className="bg-primary/5 font-bold text-sm">{v(totals[k("stock")])}</Td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {data.length > 0 && (
            <div className="px-4 py-2 bg-muted/20 border-t border-border text-xs text-muted-foreground">
              {data.length} item{data.length !== 1 ? "s" : ""} with stock activity
            </div>
          )}
        </div>
      )}

      <Dialog open={!!drill} onOpenChange={(open) => !open && closeDrill()}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>
              {drill
                ? `${COLUMN_LABELS[drill.column] || drill.column} — ${drill.item.short_code}${
                    drill.item.item_name ? ` · ${drill.item.item_name}` : ""
                  }`
                : ""}
            </DialogTitle>
            <DialogDescription>
              As on {asOnDate}
              {drill ? ` · ${drill.rows.length} barcode${drill.rows.length !== 1 ? "s" : ""}` : ""}
            </DialogDescription>
          </DialogHeader>

          {drill?.loading && (
            <div className="flex flex-col gap-2">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          )}

          {drill?.error && (
            <p className="text-sm text-destructive">{drill.error}</p>
          )}

          {drill && !drill.loading && !drill.error && (
            <div className="max-h-[60vh] overflow-auto rounded-lg border border-border">
              <table className="w-full text-xs">
                <thead className="bg-muted/40 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold border-b border-border">Barcode</th>
                    <th className="px-3 py-2 text-right font-semibold border-b border-border">Pcs</th>
                    <th className="px-3 py-2 text-left font-semibold border-b border-border">Date</th>
                    <th className="px-3 py-2 text-left font-semibold border-b border-border">Bill No</th>
                    <th className="px-3 py-2 text-left font-semibold border-b border-border">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {drill.rows.length === 0 && (
                    <tr>
                      <td colSpan={5} className="text-center py-6 text-muted-foreground">
                        No barcodes found for this selection.
                      </td>
                    </tr>
                  )}
                  {drill.rows.map((r, i) => (
                    <tr key={i} className={i % 2 === 1 ? "bg-muted/15" : ""}>
                      <td className="px-3 py-1.5 border-b border-border font-mono">{r.barcode}</td>
                      <td className="px-3 py-1.5 border-b border-border text-right tabular-nums">{r.pcs}</td>
                      <td className="px-3 py-1.5 border-b border-border">{r.date || "-"}</td>
                      <td className="px-3 py-1.5 border-b border-border">{r.billno || "-"}</td>
                      <td className="px-3 py-1.5 border-b border-border">
                        <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-semibold">
                          {r.trans_type}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
