import React, { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Table, TableRow, TableCell, TableHead, TableHeader, TableBody } from "@/components/ui/table";
import { fetchStockMatchingReport } from "@/services/apiService";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, RefreshCw, FileText, Tag, PackageX } from "lucide-react";

// Format a number to 3 decimals � blank stays blank.
const fmt = (v) => {
  const n = parseFloat(v);
  return isNaN(n) ? "�" : n.toFixed(3);
};

const today = () => new Date().toISOString().split("T")[0];
const firstOfMonth = () => {
  const d = new Date();
  d.setDate(1);
  return d.toISOString().split("T")[0];
};

const StockMatchingReport = () => {
  const [fromDate, setFromDate] = useState(firstOfMonth());
  const [toDate, setToDate] = useState(today());
  const [tolerance, setTolerance] = useState("0.05");
  const [mismatchesOnly, setMismatchesOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [bills, setBills] = useState([]);
  const [summary, setSummary] = useState({ total_bills: 0, bills_with_issues: 0 });
  const [lastRunAt, setLastRunAt] = useState(null);

  const load = async () => {
    setLoading(true);
    const res = await fetchStockMatchingReport({
      from: fromDate,
      to: toDate,
      tolerance: parseFloat(tolerance) || 0,
      mismatchesOnly,
    });
    setLoading(false);
    if (res.success) {
      setBills(res.data.bills || []);
      setSummary(res.data.summary || { total_bills: 0, bills_with_issues: 0 });
      setLastRunAt(new Date());
    } else {
      setBills([]);
      setSummary({ total_bills: 0, bills_with_issues: 0 });
    }
  };

  // Auto-run on mount.
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const cleanBillsCount = Math.max(summary.total_bills - summary.bills_with_issues, 0);

  return (
    <div className="mt-4 space-y-4 pb-8">
      {/* ─── Filters ─── */}
      <div className="rounded-lg border bg-card shadow-sm">
        <div className="px-4 py-2 border-b bg-muted/30">
          <span className="text-xs font-semibold text-primary uppercase tracking-wide">
            Filters
          </span>
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); load(); }}
          className="grid grid-cols-2 md:grid-cols-5 gap-x-4 gap-y-3 p-4 items-end"
        >
          <div className="space-y-1">
            <Label className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">From</Label>
            <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="h-9 text-sm" />
          </div>
          <div className="space-y-1">
            <Label className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">To</Label>
            <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="h-9 text-sm" />
          </div>
          <div className="space-y-1">
            <Label className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Tolerance (�)</Label>
            <Input
              type="number" step="0.001" min="0"
              value={tolerance}
              onChange={(e) => setTolerance(e.target.value)}
              className="h-9 text-sm text-right tabular-nums"
              placeholder="0.05"
            />
          </div>
          <label className="flex items-center gap-2 h-9 cursor-pointer select-none">
            <Checkbox
              checked={mismatchesOnly}
              onCheckedChange={(v) => setMismatchesOnly(Boolean(v))}
              className="cursor-pointer"
            />
            <span className="text-xs font-medium">Mismatches only</span>
          </label>
          <Button type="submit" disabled={loading} className="h-9 cursor-pointer">
            {loading ? (
              <><RefreshCw className="size-4 mr-1.5 animate-spin" /> Loading�</>
            ) : (
              <><RefreshCw className="size-4 mr-1.5" /> Refresh</>
            )}
          </Button>
        </form>
      </div>

      {/* ─── Summary header ─── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border bg-card shadow-sm p-4 flex items-center gap-3">
          <div className="rounded-md bg-muted/50 p-2">
            <FileText className="size-5 text-muted-foreground" />
          </div>
          <div className="flex-1">
            <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Bills in range</div>
            <div className="text-2xl font-bold tabular-nums">{summary.total_bills}</div>
          </div>
        </div>
        <div className="rounded-lg border bg-card shadow-sm p-4 flex items-center gap-3">
          <div className="rounded-md bg-emerald-50 p-2">
            <CheckCircle2 className="size-5 text-emerald-600" />
          </div>
          <div className="flex-1">
            <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Reconciled</div>
            <div className="text-2xl font-bold tabular-nums text-emerald-700">{cleanBillsCount}</div>
          </div>
        </div>
        <div className="rounded-lg border bg-card shadow-sm p-4 flex items-center gap-3">
          <div className="rounded-md bg-rose-50 p-2">
            <AlertTriangle className="size-5 text-rose-600" />
          </div>
          <div className="flex-1">
            <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">With mismatches</div>
            <div className="text-2xl font-bold tabular-nums text-rose-700">{summary.bills_with_issues}</div>
          </div>
        </div>
      </div>

      {/* ─── Bills list ─── */}
      {loading ? (
        <div className="rounded-lg border bg-card p-12 text-center text-sm text-muted-foreground">
          Loading reconciliation�
        </div>
      ) : bills.length === 0 ? (
        <div className="rounded-lg border bg-card p-12 text-center text-sm text-muted-foreground">
          {mismatchesOnly
            ? "No mismatched bills in this range. Everything reconciles."
            : "No purchase vouchers in this date range."}
        </div>
      ) : (
        <div className="space-y-3">
          {bills.map((b) => (
            <div key={b.billno} className="rounded-lg border bg-card shadow-sm overflow-hidden">
              <div className={`px-4 py-2.5 border-b flex items-center justify-between ${b.has_issue ? "bg-rose-50/60" : "bg-emerald-50/60"}`}>
                <div className="flex items-center gap-3 min-w-0">
                  <FileText className={`size-4 shrink-0 ${b.has_issue ? "text-rose-600" : "text-emerald-600"}`} />
                  <div className="flex flex-col min-w-0">
                    <span className="text-sm font-semibold font-mono truncate">{b.billno}</span>
                    <span className="text-[11px] text-muted-foreground truncate">
                      {b.date || "�"}
                      {b.vendor ? <> � {b.vendor}</> : null}
                    </span>
                  </div>
                </div>
                <span
                  className={`inline-flex items-center gap-1 rounded-full text-[11px] font-semibold px-2 py-0.5 border ${
                    b.has_issue
                      ? "bg-rose-100 text-rose-700 border-rose-200"
                      : "bg-emerald-100 text-emerald-700 border-emerald-200"
                  }`}
                >
                  {b.has_issue ? (
                    <><AlertTriangle className="size-3" /> Mismatch</>
                  ) : (
                    <><CheckCircle2 className="size-3" /> Reconciled</>
                  )}
                </span>
              </div>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40 text-xs">
                      <TableHead className="min-w-[160px]">Item</TableHead>
                      <TableHead className="text-right">Purchase Ct</TableHead>
                      <TableHead className="text-right">Barcode Ct</TableHead>
                      <TableHead className="text-right">Δ Ct</TableHead>
                      <TableHead className="text-right">Purchase Gw</TableHead>
                      <TableHead className="text-right">Barcode Gw</TableHead>
                      <TableHead className="text-right">Δ Gw</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {b.items.map((it) => (
                      <TableRow key={it.item_id} className={it.row_issue ? "bg-rose-50/40" : "hover:bg-muted/20"}>
                        <TableCell className="font-medium">{it.item_name || "�"}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(it.stock_ct)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(it.barcode_ct)}</TableCell>
                        <TableCell className={`text-right tabular-nums font-semibold ${it.diff_ct ? "text-rose-700" : "text-emerald-700"}`}>
                          {it.diff_ct ? (it.diff_ct > 0 ? "+" : "") + fmt(it.diff_ct) : "0.000"}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(it.stock_gw)}</TableCell>
                        <TableCell className="text-right tabular-nums">{fmt(it.barcode_gw)}</TableCell>
                        <TableCell className={`text-right tabular-nums font-semibold ${it.diff_gw ? "text-rose-700" : "text-emerald-700"}`}>
                          {it.diff_gw ? (it.diff_gw > 0 ? "+" : "") + fmt(it.diff_gw) : "0.000"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
              {/* ─── Barcodes created against this bill ─── */}
              <div className="px-4 py-3 bg-muted/20 border-t">
                <div className="flex items-center gap-2 mb-2">
                  <Tag className="size-3.5 text-muted-foreground" />
                  <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">
                    Barcodes
                  </span>
                  <span className="inline-flex items-center justify-center rounded-full bg-muted/70 text-[10px] font-semibold px-1.5 min-w-4 h-4 text-muted-foreground">
                    {(b.barcodes || []).length}
                  </span>
                </div>
                {(b.barcodes || []).length === 0 ? (
                  <span className="text-xs text-muted-foreground italic">
                    No barcodes created for this bill yet.
                  </span>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {b.barcodes.map((bc) => {
                      const chipBase =
                        "inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-[11px] font-mono transition-colors duration-150";
                      const tooltip = `${bc.item_name || bc.item || "Item"}\n${bc.pcs ?? 0} pcs � ${(bc.gw ?? 0).toFixed(3)} g${bc.created_date ? "\nCreated " + bc.created_date : ""}${bc.stk_status ? "" : "\nNot in stock"}`;
                      return bc.stk_status ? (
                        <Link
                          key={bc.id}
                          to={`/inventory/barcodemanagement/list/${bc.id}`}
                          title={tooltip}
                          className={`${chipBase} bg-primary/5 border-primary/20 text-primary hover:bg-primary/10 hover:border-primary/40 cursor-pointer`}
                        >
                          <Tag className="size-3" />
                          {bc.barcode}
                        </Link>
                      ) : (
                        <span
                          key={bc.id}
                          title={tooltip}
                          className={`${chipBase} bg-muted/50 border-border text-muted-foreground line-through cursor-not-allowed`}
                        >
                          <PackageX className="size-3" />
                          {bc.barcode}
                        </span>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="px-4 py-1.5 text-[11px] text-muted-foreground bg-muted/20 border-t">
                Differences within �{tolerance} are ignored.
              </div>
            </div>
          ))}
        </div>
      )}

      {lastRunAt && (
        <div className="text-[11px] text-muted-foreground text-right px-1">
          Last run {lastRunAt.toLocaleTimeString()}
        </div>
      )}
    </div>
  );
};

export default StockMatchingReport;
