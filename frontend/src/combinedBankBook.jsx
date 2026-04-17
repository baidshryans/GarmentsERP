import { useState, useEffect } from "react";
import { getLedgers, fetchBankBookReport } from "./services/apiService";
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
import { Landmark } from "lucide-react";

const today = new Date().toISOString().split("T")[0];
const fyStart = (() => {
  const now = new Date();
  const year = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
  return `${year}-04-01`;
})();

const fmt = (v) =>
  Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2 });

export default function CombinedBankBook() {
  const [ledgers, setLedgers] = useState([]);
  const [selectedLedger, setSelectedLedger] = useState("");
  const [fromDate, setFromDate] = useState(fyStart);
  const [toDate, setToDate] = useState(today);
  const [withNarration, setWithNarration] = useState(false);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    getLedgers({ type: "BA" }).then((r) => {
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
    setError("");
    setLoading(true);
    try {
      const data = await fetchBankBookReport(fromDate, toDate, selectedLedger);
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
      bal += (t.debit_val || 0) - (t.credit_val || 0);
      return { ...t, running_balance: bal };
    });
  };

  const rows = buildRows();

  const balLabel = (v) => {
    if (v === 0) return "0.00";
    return `${fmt(Math.abs(v))} ${v >= 0 ? "Dr" : "Cr"}`;
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1 min-w-52">
          <Label className="text-xs">Bank Ledger</Label>
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
            className="h-9 w-36"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
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
                  <th className="px-4 py-2.5 text-left font-semibold">Chq. No</th>
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
                    <td colSpan={7} className="text-center py-8 text-muted-foreground">
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
                      {new Date(t.txn_date).toLocaleDateString("en-GB")}
                    </td>
                    <td className="px-4 py-2">
                      <span className="font-medium">{t.narration || "Transaction"}</span>
                      <span className="text-xs text-muted-foreground ml-2">{t.txn_voucher_no}</span>
                      {withNarration && t.narration && (
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {t.narration}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span className="text-xs bg-muted px-1.5 py-0.5 rounded font-medium">
                        {t.txn_voucher_type}
                      </span>
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">
                      {t.chq_no || "--"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {t.debit_val > 0 ? fmt(t.debit_val) : ""}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {t.credit_val > 0 ? fmt(t.credit_val) : ""}
                    </td>
                    <td className="px-4 py-2 text-right font-medium">
                      {balLabel(t.running_balance)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-border bg-muted/50 font-semibold">
                  <td colSpan={4} className="px-4 py-2.5 text-sm">
                    Closing Balance
                  </td>
                  <td className="px-4 py-2.5 text-right text-sm">
                    {fmt(rows.reduce((s, t) => s + (t.debit_val || 0), 0))}
                  </td>
                  <td className="px-4 py-2.5 text-right text-sm">
                    {fmt(rows.reduce((s, t) => s + (t.credit_val || 0), 0))}
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
            <Landmark className="size-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">Bank Book</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Select a bank ledger and date range, then click Show to view transactions.
          </p>
        </div>
      )}
    </div>
  );
}
