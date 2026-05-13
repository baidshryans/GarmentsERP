import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { Printer } from "lucide-react";
import { printReport } from "@/lib/printReport";
import { isValidDateRange } from "@/lib/dateRange";

const today = new Date().toISOString().split("T")[0];
const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function BillsPanel({ title, data, showDis = true }) {
  const rows = data?.rows || [];
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="bg-muted/60 px-3 py-2 text-sm font-semibold border-b">{title}</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wider text-muted-foreground bg-muted/20">
            <th className="px-3 py-1.5 text-left w-full">Party</th>
            <th className="px-3 py-1.5 text-left whitespace-nowrap">Bill No</th>
            {showDis && <th className="px-3 py-1.5 text-right whitespace-nowrap">Dis</th>}
            <th className="px-3 py-1.5 text-right whitespace-nowrap">Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={showDis ? 4 : 3} className="px-3 py-3 text-center text-muted-foreground text-xs">
                No entries
              </td>
            </tr>
          )}
          {rows.map((r, i) => (
            <tr key={i} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
              <td className="px-3 py-1.5 w-full">{r.party}</td>
              <td className="px-3 py-1.5 font-mono text-xs whitespace-nowrap">{r.billno}</td>
              {showDis && <td className="px-3 py-1.5 text-right tabular-nums whitespace-nowrap">{Number(r.dis) > 0 ? fmt(r.dis) : ""}</td>}
              <td className="px-3 py-1.5 text-right tabular-nums whitespace-nowrap">{fmt(r.amount)}</td>
            </tr>
          ))}
        </tbody>
        {rows.length > 0 && (
          <tfoot>
            <tr className="border-t bg-muted/30 font-semibold">
              <td colSpan={showDis ? 3 : 2} className="px-3 py-1.5 text-right">Total</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{fmt(data.grand_total)}</td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

function VouchersPanel({ title, data }) {
  const rows = data?.rows || [];
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="bg-muted/60 px-3 py-2 text-sm font-semibold border-b">{title}</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wider text-muted-foreground bg-muted/20">
            <th className="px-3 py-1.5 text-left w-full">Party</th>
            <th className="px-3 py-1.5 text-left whitespace-nowrap">Voucher No</th>
            <th className="px-3 py-1.5 text-right whitespace-nowrap">Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={3} className="px-3 py-3 text-center text-muted-foreground text-xs">No entries</td>
            </tr>
          )}
          {rows.map((r, i) => (
            <tr key={i} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
              <td className="px-3 py-1.5 w-full">
                {r.party}
                {r.narration && (
                  <div className="text-xs text-muted-foreground italic">{r.narration}</div>
                )}
              </td>
              <td className="px-3 py-1.5 font-mono text-xs whitespace-nowrap">{r.voucher_no}</td>
              <td className="px-3 py-1.5 text-right tabular-nums whitespace-nowrap">{fmt(r.amount)}</td>
            </tr>
          ))}
        </tbody>
        {rows.length > 0 && (
          <tfoot>
            <tr className="border-t bg-muted/30 font-semibold">
              <td colSpan={2} className="px-3 py-1.5 text-right">Total</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{fmt(data.grand_total)}</td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

function ApprovalsPanel({ data }) {
  const rows = data?.rows || [];
  return (
    <div className="rounded-lg border border-border overflow-hidden">
      <div className="bg-muted/60 px-3 py-2 text-sm font-semibold border-b">Sale Approvals</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs uppercase tracking-wider text-muted-foreground bg-muted/20">
            <th className="px-3 py-1.5 text-left w-full">Customer</th>
            <th className="px-3 py-1.5 text-left whitespace-nowrap">Approval No</th>
            <th className="px-3 py-1.5 text-right whitespace-nowrap">Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={3} className="px-3 py-3 text-center text-muted-foreground text-xs">No entries</td>
            </tr>
          )}
          {rows.map((r, i) => (
            <tr key={i} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
              <td className="px-3 py-1.5 w-full">{r.party}</td>
              <td className="px-3 py-1.5 font-mono text-xs whitespace-nowrap">{r.billno}</td>
              <td className="px-3 py-1.5 text-right tabular-nums whitespace-nowrap">{fmt(r.amount)}</td>
            </tr>
          ))}
        </tbody>
        {rows.length > 0 && (
          <tfoot>
            <tr className="border-t bg-muted/30 font-semibold">
              <td colSpan={2} className="px-3 py-1.5 text-right">Total</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{fmt(data.grand_total)}</td>
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

export default function DayBook() {
  const [fromDate, setFromDate] = useState(today);
  const [toDate, setToDate] = useState(today);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load day book.");
    }
    setLoading(false);
  };

  const handlePrint = () => {
    if (!report) return;

    const billsTable = (title, data, showDis = true) => {
      const rows = data?.rows || [];
      const body = rows.length
        ? rows.map(r => `
            <tr>
              <td>${r.party || ""}</td>
              <td style="white-space:nowrap">${r.billno || ""}</td>
              ${showDis ? `<td style="text-align:right">${Number(r.dis) > 0 ? fmt(r.dis) : ""}</td>` : ""}
              <td style="text-align:right">${fmt(r.amount)}</td>
            </tr>`).join("")
        : `<tr><td colspan="${showDis ? 4 : 3}" style="text-align:center;color:#94a3b8">No entries</td></tr>`;
      const totalCols = showDis ? 3 : 2;
      return `
        <h3 style="margin:6px 0 4px;font-size:11px">${title}</h3>
        <table style="width:100%">
          <thead>
            <tr>
              <th>Party</th>
              <th style="white-space:nowrap">Bill No</th>
              ${showDis ? `<th style="width:60px;text-align:right">Dis</th>` : ""}
              <th style="width:90px;text-align:right">Amount</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
          ${rows.length ? `<tfoot>
            <tr class="totals-row">
              <td colspan="${totalCols}" style="text-align:right">Total</td>
              <td style="text-align:right">${fmt(data.grand_total)}</td>
            </tr>
          </tfoot>` : ""}
        </table>`;
    };

    const vouchersTable = (title, data) => {
      const rows = data?.rows || [];
      const body = rows.length
        ? rows.map(r => `
            <tr>
              <td>${r.party || ""}${r.narration ? `<br><em style="font-size:9px;color:#64748b">${r.narration}</em>` : ""}</td>
              <td style="white-space:nowrap">${r.voucher_no || ""}</td>
              <td style="text-align:right">${fmt(r.amount)}</td>
            </tr>`).join("")
        : `<tr><td colspan="3" style="text-align:center;color:#94a3b8">No entries</td></tr>`;
      return `
        <h3 style="margin:6px 0 4px;font-size:11px">${title}</h3>
        <table style="width:100%">
          <thead>
            <tr>
              <th>Party</th>
              <th style="white-space:nowrap">Voucher No</th>
              <th style="width:90px;text-align:right">Amount</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
          ${rows.length ? `<tfoot>
            <tr class="totals-row">
              <td colspan="2" style="text-align:right">Total</td>
              <td style="text-align:right">${fmt(data.grand_total)}</td>
            </tr>
          </tfoot>` : ""}
        </table>`;
    };

    const approvalsTable = (data) => {
      const rows = data?.rows || [];
      const body = rows.length
        ? rows.map(r => `
            <tr>
              <td>${r.party || ""}</td>
              <td style="white-space:nowrap">${r.billno || ""}</td>
              <td style="text-align:right">${fmt(r.amount)}</td>
            </tr>`).join("")
        : `<tr><td colspan="3" style="text-align:center;color:#94a3b8">No entries</td></tr>`;
      return `
        <h3 style="margin:6px 0 4px;font-size:11px">Sale Approvals</h3>
        <table style="width:100%">
          <thead>
            <tr>
              <th>Customer</th>
              <th style="white-space:nowrap">Approval No</th>
              <th style="width:90px;text-align:right">Amount</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
          ${rows.length ? `<tfoot>
            <tr class="totals-row">
              <td colspan="2" style="text-align:right">Total</td>
              <td style="text-align:right">${fmt(data.grand_total)}</td>
            </tr>
          </tfoot>` : ""}
        </table>`;
    };

    const pair = (left, right) => `
      <table style="width:100%;border-collapse:collapse;margin-bottom:10px">
        <tr>
          <td style="width:50%;vertical-align:top;padding-right:6px">${left}</td>
          <td style="width:50%;vertical-align:top;padding-left:6px">${right}</td>
        </tr>
      </table>`;

    const html = [
      pair(billsTable("Sale", report.sale), billsTable("Purchase", report.purchase)),
      pair(billsTable("Purchase Return", report.purchase_return), billsTable("Sale Return", report.sale_return)),
      pair(vouchersTable("Payment", report.payment), vouchersTable("Receipt", report.receipt)),
      pair(vouchersTable("Contra", report.contra), vouchersTable("Journal", report.journal)),
      pair(approvalsTable(report.sale_approvals), ""),
    ].join("");

    printReport({
      title: "Day Book",
      subtitle: `${report.from_date} to ${report.to_date}`,
      html: html || "<p>No entries for this period.</p>",
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
        <div className="flex flex-col gap-3">
          <div className="text-sm text-muted-foreground px-1">
            Day Book — {report.from_date} to {report.to_date}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 [&>*]:min-w-0">
            <BillsPanel title="Sale" data={report.sale} />
            <BillsPanel title="Purchase" data={report.purchase} />
            <BillsPanel title="Purchase Return" data={report.purchase_return} />
            <BillsPanel title="Sale Return" data={report.sale_return} />
            <VouchersPanel title="Payment" data={report.payment} />
            <VouchersPanel title="Receipt" data={report.receipt} />
            <VouchersPanel title="Contra" data={report.contra} />
            <VouchersPanel title="Journal" data={report.journal} />
            <ApprovalsPanel data={report.sale_approvals} />
            <div aria-hidden="true" />
          </div>
        </div>
      )}
    </div>
  );
}
