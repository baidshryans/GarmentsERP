import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { Printer, ChevronDown, ChevronRight } from "lucide-react";
import { printReport } from "@/lib/printReport";

const today = new Date().toISOString().split("T")[0];
const fy = new Date().getMonth() < 3 ? new Date().getFullYear() - 1 : new Date().getFullYear();
const firstOfYear = `${fy}-04-01`;

const fmt = (v) => {
  const n = Number(v);
  if (!n) return "";
  return Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const balLabel = (v) => {
  const n = Number(v);
  if (n === 0) return "—";
  return `${fmt(n)} ${n >= 0 ? "Dr" : "Cr"}`;
};

export default function TrialBalance() {
  const [fromDate, setFromDate] = useState(firstOfYear);
  const [toDate, setToDate] = useState(today);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState({});
  const [combined, setCombined] = useState(false);

  const user = JSON.parse(localStorage.getItem("user") || "{}");
  const canViewCombined = user.is_superuser || ["admin", "super admin"].includes((user.role || "").toLowerCase());

  const toggle = (name) => setCollapsed((p) => ({ ...p, [name]: !p[name] }));

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    try {
      const params = new URLSearchParams({ from_date: fromDate, to_date: toDate });
      if (combined) params.set("combined", "true");
      const res = await apiClient.get(`/accounting/api/trial?${params}`);
      setReport(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load Trial Balance.");
    }
    setLoading(false);
  };

  // Compute grand totals
  let grandOpenDr = 0, grandOpenCr = 0, grandTxnDr = 0, grandTxnCr = 0, grandCloseDr = 0, grandCloseCr = 0;
  if (report) {
    for (const group of report.trial_balance) {
      for (const l of group.ledgers) {
        const ob = Number(l.opening_balance);
        if (ob > 0) grandOpenDr += ob; else grandOpenCr += Math.abs(ob);
        grandTxnDr += Number(l.total_debit);
        grandTxnCr += Number(l.total_credit);
        const cb = Number(l.closing_balance);
        if (cb > 0) grandCloseDr += cb; else grandCloseCr += Math.abs(cb);
      }
    }
  }

  const handlePrint = () => {
    if (!report) return;
    const groupRows = report.trial_balance
      .filter((g) => g.ledgers.length > 0)
      .map((group) => {
        let gOD = 0, gOC = 0, gTD = 0, gTC = 0, gCD = 0, gCC = 0;
        const ledgerRows = group.ledgers.map((l, i) => {
          const ob = Number(l.opening_balance), cb = Number(l.closing_balance);
          if (ob > 0) gOD += ob; else gOC += Math.abs(ob);
          gTD += Number(l.total_debit); gTC += Number(l.total_credit);
          if (cb > 0) gCD += cb; else gCC += Math.abs(cb);
          return `<tr${i % 2 === 1 ? ' style="background:#fafafa"' : ""}>
            <td class="pl-10">${l.ledger_name}</td>
            <td style="text-align:right" class="tabular-nums">${ob > 0 ? fmt(ob) : ""}</td>
            <td style="text-align:right" class="tabular-nums">${ob < 0 ? fmt(ob) : ""}</td>
            <td style="text-align:right" class="tabular-nums">${fmt(l.total_debit)}</td>
            <td style="text-align:right" class="tabular-nums">${fmt(l.total_credit)}</td>
            <td style="text-align:right" class="tabular-nums">${cb > 0 ? fmt(cb) : ""}</td>
            <td style="text-align:right" class="tabular-nums">${cb < 0 ? fmt(cb) : ""}</td>
          </tr>`;
        });
        return `<tr class="group-header">
          <td class="font-semibold">${group.group_name} (${group.ledgers.length})</td>
          <td style="text-align:right" class="tabular-nums font-semibold">${fmt(gOD)}</td>
          <td style="text-align:right" class="tabular-nums font-semibold">${fmt(gOC)}</td>
          <td style="text-align:right" class="tabular-nums font-semibold">${fmt(gTD)}</td>
          <td style="text-align:right" class="tabular-nums font-semibold">${fmt(gTC)}</td>
          <td style="text-align:right" class="tabular-nums font-semibold">${fmt(gCD)}</td>
          <td style="text-align:right" class="tabular-nums font-semibold">${fmt(gCC)}</td>
        </tr>${ledgerRows.join("")}`;
      });

    const html = `<table>
      <thead>
        <tr><th rowspan="2" style="width:30%">Particulars</th>
          <th colspan="2" style="text-align:center">Opening Balance</th>
          <th colspan="2" style="text-align:center">Transactions</th>
          <th colspan="2" style="text-align:center">Closing Balance</th></tr>
        <tr><th style="text-align:right">Debit</th><th style="text-align:right">Credit</th>
          <th style="text-align:right">Debit</th><th style="text-align:right">Credit</th>
          <th style="text-align:right">Debit</th><th style="text-align:right">Credit</th></tr>
      </thead>
      <tbody>${groupRows.join("")}</tbody>
      <tfoot><tr class="totals-row">
        <td>Total</td>
        <td style="text-align:right" class="tabular-nums">${fmt(grandOpenDr)}</td>
        <td style="text-align:right" class="tabular-nums">${fmt(grandOpenCr)}</td>
        <td style="text-align:right" class="tabular-nums">${fmt(grandTxnDr)}</td>
        <td style="text-align:right" class="tabular-nums">${fmt(grandTxnCr)}</td>
        <td style="text-align:right" class="tabular-nums">${fmt(grandCloseDr)}</td>
        <td style="text-align:right" class="tabular-nums">${fmt(grandCloseCr)}</td>
      </tr></tfoot>
    </table>`;

    printReport({
      title: "Trial Balance",
      subtitle: `${fromDate} to ${toDate}`,
      html,
    });
  };

  return (
    <div className="flex flex-col gap-4">
      {/* ── Filters ───────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border print:hidden">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="h-9 w-36" />
        </div>
        {canViewCombined && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="tb-combined"
              checked={combined}
              onChange={(e) => setCombined(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300"
            />
            <Label htmlFor="tb-combined" className="text-xs cursor-pointer">Combined (All Retails)</Label>
          </div>
        )}
        <Button size="sm" onClick={fetchReport} className="h-9">Show</Button>
        {report && (
          <Button size="sm" variant="outline" onClick={handlePrint} className="h-9 ml-auto">
            <Printer className="w-4 h-4 mr-1.5" /> Print
          </Button>
        )}
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      )}

      {report && !loading && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                {/* Two-level header */}
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th rowSpan={2} className="px-4 py-2.5 text-left font-semibold border-r border-border w-[30%]">
                    Particulars
                  </th>
                  <th colSpan={2} className="px-2 py-1.5 text-center font-semibold border-r border-border">
                    Opening Balance
                  </th>
                  <th colSpan={2} className="px-2 py-1.5 text-center font-semibold border-r border-border">
                    Transactions
                  </th>
                  <th colSpan={2} className="px-2 py-1.5 text-center font-semibold">
                    Closing Balance
                  </th>
                </tr>
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-3 py-1.5 text-right font-semibold border-r border-border/50 w-[10%]">Debit</th>
                  <th className="px-3 py-1.5 text-right font-semibold border-r border-border w-[10%]">Credit</th>
                  <th className="px-3 py-1.5 text-right font-semibold border-r border-border/50 w-[10%]">Debit</th>
                  <th className="px-3 py-1.5 text-right font-semibold border-r border-border w-[10%]">Credit</th>
                  <th className="px-3 py-1.5 text-right font-semibold border-r border-border/50 w-[10%]">Debit</th>
                  <th className="px-3 py-1.5 text-right font-semibold w-[10%]">Credit</th>
                </tr>
              </thead>

              <tbody>
                {report.trial_balance
                  .filter((g) => g.ledgers.length > 0)
                  .map((group) => {
                    const isOpen = !collapsed[group.group_name];
                    // Group subtotals
                    let gOpenDr = 0, gOpenCr = 0, gTxnDr = 0, gTxnCr = 0, gCloseDr = 0, gCloseCr = 0;
                    for (const l of group.ledgers) {
                      const ob = Number(l.opening_balance);
                      if (ob > 0) gOpenDr += ob; else gOpenCr += Math.abs(ob);
                      gTxnDr += Number(l.total_debit);
                      gTxnCr += Number(l.total_credit);
                      const cb = Number(l.closing_balance);
                      if (cb > 0) gCloseDr += cb; else gCloseCr += Math.abs(cb);
                    }

                    return (
                      <tbody key={group.group_name}>
                        {/* Group header */}
                        <tr
                          className="bg-muted/30 border-t border-border cursor-pointer hover:bg-muted/50 transition-colors"
                          onClick={() => toggle(group.group_name)}
                        >
                          <td className="px-4 py-2 font-semibold border-r border-border">
                            <span className="flex items-center gap-1.5">
                              {isOpen
                                ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />
                                : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />}
                              {group.group_name}
                              <span className="text-xs font-normal text-muted-foreground ml-1">
                                ({group.ledgers.length})
                              </span>
                            </span>
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border/50">{fmt(gOpenDr)}</td>
                          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border">{fmt(gOpenCr)}</td>
                          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border/50">{fmt(gTxnDr)}</td>
                          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border">{fmt(gTxnCr)}</td>
                          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border/50">{fmt(gCloseDr)}</td>
                          <td className="px-3 py-2 text-right tabular-nums font-medium">{fmt(gCloseCr)}</td>
                        </tr>

                        {/* Ledger rows */}
                        {isOpen &&
                          group.ledgers.map((ledger, i) => {
                            const ob = Number(ledger.opening_balance);
                            const cb = Number(ledger.closing_balance);
                            return (
                              <tr
                                key={`${group.group_name}-${i}`}
                                className={`border-t border-border/40 hover:bg-accent/30 transition-colors ${
                                  i % 2 === 1 ? "bg-muted/20" : ""
                                }`}
                              >
                                <td className="px-4 py-1.5 pl-10 border-r border-border">{ledger.ledger_name}</td>
                                <td className="px-3 py-1.5 text-right tabular-nums border-r border-border/50">
                                  {ob > 0 ? fmt(ob) : ""}
                                </td>
                                <td className="px-3 py-1.5 text-right tabular-nums border-r border-border">
                                  {ob < 0 ? fmt(ob) : ""}
                                </td>
                                <td className="px-3 py-1.5 text-right tabular-nums border-r border-border/50">
                                  {fmt(ledger.total_debit)}
                                </td>
                                <td className="px-3 py-1.5 text-right tabular-nums border-r border-border">
                                  {fmt(ledger.total_credit)}
                                </td>
                                <td className="px-3 py-1.5 text-right tabular-nums border-r border-border/50">
                                  {cb > 0 ? fmt(cb) : ""}
                                </td>
                                <td className="px-3 py-1.5 text-right tabular-nums">
                                  {cb < 0 ? fmt(cb) : ""}
                                </td>
                              </tr>
                            );
                          })}
                      </tbody>
                    );
                  })}
              </tbody>

              <tfoot>
                <tr className="border-t-2 border-border bg-muted/50 font-semibold">
                  <td className="px-4 py-2.5 border-r border-border">Total</td>
                  <td className="px-3 py-2.5 text-right tabular-nums border-r border-border/50">{fmt(grandOpenDr)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums border-r border-border">{fmt(grandOpenCr)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums border-r border-border/50">{fmt(grandTxnDr)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums border-r border-border">{fmt(grandTxnCr)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums border-r border-border/50">{fmt(grandCloseDr)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{fmt(grandCloseCr)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
