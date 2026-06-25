import { useState, useEffect } from "react";
import { formatNumber } from "@/lib/format";
import { getLedgers, fetchCashBookReport } from "./services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { BookOpen, Printer } from "lucide-react";
import { printReport } from "@/lib/printReport";
import { isValidDateRange } from "@/lib/dateRange";

const today = new Date().toISOString().split("T")[0];
const fyStart = (() => {
  const now = new Date();
  const year = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
  return `${year}-04-01`;
})();

const fmt = (v) =>
  formatNumber(v, { minDecimals: 2 });

export default function CashBookRetail() {
  const [ledgers, setLedgers] = useState([]);
  const [selectedLedger, setSelectedLedger] = useState("");
  const [fromDate, setFromDate] = useState(fyStart);
  const [toDate, setToDate] = useState(today);
  const [withNarration, setWithNarration] = useState(false);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getLedgers({ type: "CA" }).then((r) => {
      if (r.success && r.data.results?.length) {
        setLedgers(r.data.results);
        setSelectedLedger(String(r.data.results[0].id));
      }
    });
  }, []);

  const fetchData = async () => {
    if (!selectedLedger) {
      setError("Please select a ledger.");
      return;
    }
    if (!isValidDateRange(fromDate, toDate)) {
      setError("From date cannot be after To date.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const data = await fetchCashBookReport(selectedLedger, fromDate, toDate);
      setReport(data);
    } catch (e) {
      setError(e.message || "Failed to load report.");
    }
    setLoading(false);
  };

  const buildRows = () => {
    if (!report?.transactions) return [];
    let bal = report.opening_balance;
    return report.transactions.map((t) => {
      bal = bal + t.display_debit - t.display_credit;
      return { ...t, running_balance: bal };
    });
  };

  const rows = buildRows();

  const balLabel = (v) => {
    if (v === 0) return "0.00";
    return `${fmt(Math.abs(v))} ${v >= 0 ? "Dr" : "Cr"}`;
  };

  const handlePrint = () => {
    if (!report) return;
    const ledgerName = ledgers.find((l) => String(l.id) === selectedLedger)?.ac_name || "";
    const printRows = rows.map(
      (t, i) => `<tr${i % 2 === 1 ? ' style="background:#fafafa"' : ""}>
        <td>${new Date(t.voucher_main__date).toLocaleDateString("en-GB")}</td>
        <td>${t.account__ac_name}${withNarration && t.voucher_main__narration ? `<br/><span style="font-size:9px;color:#64748b">${t.voucher_main__narration}</span>` : ""}</td>
        <td><span class="badge">${t.voucher_main__voucher_type}</span></td>
        <td style="text-align:right" class="tabular-nums">${t.display_debit > 0 ? fmt(t.display_debit) : ""}</td>
        <td style="text-align:right" class="tabular-nums">${t.display_credit > 0 ? fmt(t.display_credit) : ""}</td>
        <td style="text-align:right" class="tabular-nums font-medium">${balLabel(t.running_balance)}</td>
      </tr>`
    );

    const html = `<table>
      <thead><tr>
        <th style="width:75px">Date</th>
        <th>Particulars</th>
        <th style="width:65px">Type</th>
        <th style="text-align:right;width:100px">Debit (Rs.)</th>
        <th style="text-align:right;width:100px">Credit (Rs.)</th>
        <th style="text-align:right;width:110px">Balance</th>
      </tr></thead>
      <tbody>
        <tr style="background:#f8f7ff"><td>--</td><td class="font-semibold">Opening Balance</td><td>--</td>
          <td style="text-align:right" class="tabular-nums">${report.opening_balance >= 0 ? fmt(report.opening_balance) : ""}</td>
          <td style="text-align:right" class="tabular-nums">${report.opening_balance < 0 ? fmt(Math.abs(report.opening_balance)) : ""}</td>
          <td style="text-align:right" class="tabular-nums font-semibold">${balLabel(report.opening_balance)}</td>
        </tr>
        ${printRows.join("")}
      </tbody>
      <tfoot><tr class="totals-row">
        <td colspan="3">Closing Balance</td>
        <td style="text-align:right" class="tabular-nums">${fmt(rows.reduce((s, t) => s + t.display_debit, 0))}</td>
        <td style="text-align:right" class="tabular-nums">${fmt(rows.reduce((s, t) => s + t.display_credit, 0))}</td>
        <td style="text-align:right" class="tabular-nums">${report.closing_balance !== undefined ? balLabel(report.closing_balance) : rows.length ? balLabel(rows[rows.length - 1].running_balance) : balLabel(report.opening_balance)}</td>
      </tr></tfoot>
    </table>`;

    printReport({
      title: `Cash Book — ${ledgerName}`,
      subtitle: `${fromDate} to ${toDate}`,
      html,
    });
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1 min-w-52">
          <Label className="text-xs">Cash Ledger</Label>
          <Select value={selectedLedger} onValueChange={setSelectedLedger}>
            <SelectTrigger className="h-9">
              <span className="truncate">
                {selectedLedger
                  ? ledgers.find((l) => String(l.id) === selectedLedger)
                      ?.ac_name ?? "Select ledger"
                  : "Select ledger"}
              </span>
            </SelectTrigger>
            <SelectContent>
              {ledgers.map((l) => (
                <SelectItem key={l.id} value={String(l.id)}>
                  {l.ac_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            max={toDate || undefined}
            className="h-9 w-36"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            min={fromDate || undefined}
            className="h-9 w-36"
          />
        </div>

        <label className="flex items-center gap-2 text-xs cursor-pointer select-none h-9">
          <input
            type="checkbox"
            checked={withNarration}
            onChange={(e) => setWithNarration(e.target.checked)}
            className="rounded border-border"
          />
          With Narration
        </label>

        <Button size="sm" onClick={fetchData} disabled={loading} className="h-9">
          {loading ? "Loading..." : "Show"}
        </Button>
        {report && (
          <Button size="sm" variant="outline" onClick={handlePrint} className="h-9 ml-auto">
            <Printer className="size-4 mr-1.5" /> Print
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      )}

      {report && !loading && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-foreground">
                {ledgers.find((l) => String(l.id) === selectedLedger)?.ac_name}
              </h3>
              <p className="text-xs text-muted-foreground">
                {fromDate} to {toDate}
              </p>
            </div>
            <div className="text-right text-sm">
              <p className="text-muted-foreground">Opening Balance</p>
              <p className="font-semibold">{balLabel(report.opening_balance)}</p>
            </div>
          </div>

          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2.5 text-left font-semibold">Date</th>
                  <th className="px-4 py-2.5 text-left font-semibold">Particulars</th>
                  <th className="px-4 py-2.5 text-left font-semibold">Type</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Debit (Rs.)</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Credit (Rs.)</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Balance</th>
                </tr>
              </thead>
              <tbody>
                {/* Opening Balance */}
                <tr className="border-t border-border bg-muted/20 font-medium">
                  <td className="px-4 py-2 text-muted-foreground">--</td>
                  <td className="px-4 py-2">Opening Balance</td>
                  <td className="px-4 py-2">--</td>
                  <td className="px-4 py-2 text-right">
                    {report.opening_balance >= 0 ? fmt(report.opening_balance) : ""}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {report.opening_balance < 0 ? fmt(Math.abs(report.opening_balance)) : ""}
                  </td>
                  <td className="px-4 py-2 text-right font-semibold">
                    {balLabel(report.opening_balance)}
                  </td>
                </tr>

                {rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-8 text-muted-foreground">
                      No transactions in this period.
                    </td>
                  </tr>
                )}

                {rows.map((t, i) => (
                  <tr
                    key={i}
                    className={`border-t border-border ${i % 2 === 1 ? "bg-muted/20" : ""} hover:bg-accent/30 transition-colors`}
                  >
                    <td className="px-4 py-2">
                      {new Date(t.voucher_main__date).toLocaleDateString("en-GB")}
                    </td>
                    <td className="px-4 py-2">
                      <span className="font-medium">{t.account__ac_name}</span>
                      {withNarration && t.voucher_main__narration && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {t.voucher_main__narration}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span className="text-xs bg-muted px-1.5 py-0.5 rounded font-medium">
                        {t.voucher_main__voucher_type}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right">
                      {t.display_debit > 0 ? fmt(t.display_debit) : ""}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {t.display_credit > 0 ? fmt(t.display_credit) : ""}
                    </td>
                    <td className="px-4 py-2 text-right font-medium">
                      {balLabel(t.running_balance)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-border bg-muted/50 font-semibold">
                  <td colSpan={3} className="px-4 py-2.5 text-sm">
                    Closing Balance
                  </td>
                  <td className="px-4 py-2.5 text-right text-sm">
                    {fmt(rows.reduce((s, t) => s + t.display_debit, 0))}
                  </td>
                  <td className="px-4 py-2.5 text-right text-sm">
                    {fmt(rows.reduce((s, t) => s + t.display_credit, 0))}
                  </td>
                  <td className="px-4 py-2.5 text-right text-sm">
                    {report.closing_balance !== undefined
                      ? balLabel(report.closing_balance)
                      : rows.length
                        ? balLabel(rows[rows.length - 1].running_balance)
                        : balLabel(report.opening_balance)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && !report && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-muted/50 p-4 mb-4">
            <BookOpen className="size-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">Cash Book</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Select a cash ledger and date range, then click Show to view transactions.
          </p>
        </div>
      )}
    </div>
  );
}
