import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { ChevronDown, ChevronRight, Printer } from "lucide-react";
import { printReport } from "@/lib/printReport";
import { isValidDateRange } from "@/lib/dateRange";

const today = new Date().toISOString().split("T")[0];

const VOUCHER_TYPE_LABELS = {
  JRNL: "Journal",
  PMNT: "Payment",
  RCPT_SALE: "Receipt",
  "RCPT-SALE": "Receipt",
  CONTRA: "Contra",
  SALE: "Sale",
  "SALE-RET": "Sale Return",
  "PURC-SC": "Purchase",
  "PURC-RET": "Purchase Return",
};

export default function DayBook() {
  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState({});

  const fetchReport = async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      setError("From date cannot be after To date.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await apiClient.get(
        `/accounting/api/day-book/?from_date=${fromDate}&to_date=${toDate}`
      );
      setReport(res.data);
      // expand all by default
      const exp = {};
      res.data.vouchers.forEach((v) => { exp[v.voucher_no] = true; });
      setExpanded(exp);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load day book.");
    }
    setLoading(false);
  };

  const toggle = (vno) => setExpanded((prev) => ({ ...prev, [vno]: !prev[vno] }));
  const fmt = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2 });

  const handlePrint = () => {
    if (!report) return;
    // Build a flat print-friendly table from the data (not from the interactive DOM)
    const rows = report.vouchers.flatMap((v) => {
      const lines = v.lines.map(
        (l, i) =>
          `<tr>
            ${i === 0 ? `<td rowspan="${v.lines.length}" style="vertical-align:top;border-bottom:1px solid #cbd5e1">${v.date}</td>
            <td rowspan="${v.lines.length}" style="vertical-align:top;border-bottom:1px solid #cbd5e1"><span class="badge">${VOUCHER_TYPE_LABELS[v.voucher_type] ?? v.voucher_type}</span></td>
            <td rowspan="${v.lines.length}" style="vertical-align:top;border-bottom:1px solid #cbd5e1;font-size:9px;font-family:monospace">${v.voucher_no}</td>` : ""}
            <td>${l.account}</td>
            <td style="text-align:right" class="tabular-nums">${Number(l.debit) > 0 ? fmt(l.debit) : ""}</td>
            <td style="text-align:right" class="tabular-nums">${Number(l.credit) > 0 ? fmt(l.credit) : ""}</td>
          </tr>`
      );
      // Add narration row
      if (v.narration) {
        lines.push(`<tr><td colspan="3"></td><td colspan="3" style="font-size:9px;color:#64748b;padding-bottom:6px"><em>${v.narration}</em></td></tr>`);
      }
      return lines;
    });

    const html = `
      <table>
        <thead>
          <tr>
            <th style="width:70px">Date</th>
            <th style="width:70px">Type</th>
            <th style="width:100px">Voucher No</th>
            <th>Account</th>
            <th style="text-align:right;width:100px">Debit</th>
            <th style="text-align:right;width:100px">Credit</th>
          </tr>
        </thead>
        <tbody>${rows.join("")}</tbody>
        <tfoot>
          <tr class="totals-row">
            <td colspan="4">Total (${report.vouchers.length} voucher(s))</td>
            <td style="text-align:right" class="tabular-nums">${fmt(report.total_debit)}</td>
            <td style="text-align:right" class="tabular-nums">${fmt(report.total_credit)}</td>
          </tr>
        </tfoot>
      </table>`;

    printReport({
      title: "Day Book",
      subtitle: `${report.from_date} to ${report.to_date}`,
      html,
    });
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} className="h-9 w-36" />
        </div>
        <Button size="sm" onClick={fetchReport} className="h-9">Show</Button>
        {report && (
          <Button size="sm" variant="outline" onClick={handlePrint} className="h-9 ml-auto">
            <Printer className="size-4 mr-1.5" /> Print
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {report && !loading && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-sm text-muted-foreground px-1">
            <span>{report.vouchers.length} voucher(s) — {report.from_date} to {report.to_date}</span>
            <span>
              Total Dr: <strong className="text-foreground">{fmt(report.total_debit)}</strong>
              {" / "}
              Total Cr: <strong className="text-foreground">{fmt(report.total_credit)}</strong>
            </span>
          </div>

          {report.vouchers.length === 0 && (
            <div className="text-center py-12 text-muted-foreground border rounded-lg">No transactions for this period.</div>
          )}

          {report.vouchers.map((v) => (
            <div key={v.voucher_no} className="rounded-lg border border-border overflow-hidden">
              {/* Voucher header */}
              <button
                className="w-full flex items-center gap-3 px-4 py-2.5 bg-muted/40 hover:bg-muted/70 transition-colors text-left"
                onClick={() => toggle(v.voucher_no)}
              >
                {expanded[v.voucher_no] ? <ChevronDown className="size-4 text-muted-foreground shrink-0" /> : <ChevronRight className="size-4 text-muted-foreground shrink-0" />}
                <span className="font-mono text-xs text-muted-foreground w-28 shrink-0">{v.voucher_no}</span>
                <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-medium shrink-0">
                  {VOUCHER_TYPE_LABELS[v.voucher_type] ?? v.voucher_type}
                </span>
                <span className="text-sm font-medium text-foreground">{v.narration}</span>
                <span className="ml-auto text-sm font-semibold text-foreground shrink-0">
                  {fmt(v.amount)}
                </span>
                <span className="text-xs text-muted-foreground shrink-0 w-24 text-right">{v.date}</span>
              </button>

              {/* Lines */}
              {expanded[v.voucher_no] && (
                <table className="w-full text-sm border-t border-border">
                  <thead>
                    <tr className="text-xs uppercase tracking-wider text-muted-foreground bg-muted/20">
                      <th className="px-4 py-2 text-left font-semibold">Account</th>
                      <th className="px-4 py-2 text-right font-semibold w-32">Debit</th>
                      <th className="px-4 py-2 text-right font-semibold w-32">Credit</th>
                      <th className="px-4 py-2 text-left font-semibold">Ref / Cheque</th>
                    </tr>
                  </thead>
                  <tbody>
                    {v.lines.map((line, i) => (
                      <tr key={i} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
                        <td className="px-4 py-1.5">{line.account}</td>
                        <td className="px-4 py-1.5 text-right">
                          {Number(line.debit) > 0 ? fmt(line.debit) : ""}
                        </td>
                        <td className="px-4 py-1.5 text-right">
                          {Number(line.credit) > 0 ? fmt(line.credit) : ""}
                        </td>
                        <td className="px-4 py-1.5 text-muted-foreground text-xs">
                          {line.ref_bill_no || line.chq_no || line.party_bank_name || ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
