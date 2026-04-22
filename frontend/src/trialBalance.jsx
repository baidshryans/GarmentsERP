import { useState, useEffect, Fragment } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { fetchCompanies } from "@/services/apiService";
import { Printer, ChevronDown, ChevronRight, X, Loader2 } from "lucide-react";
import { printReport } from "@/lib/printReport";

const today = new Date().toISOString().split("T")[0];
const fy = new Date().getMonth() < 3 ? new Date().getFullYear() - 1 : new Date().getFullYear();
const firstOfYear = `${fy}-04-01`;

const fmt = (v) => {
  const n = Number(v);
  if (!n) return "";
  return Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

/* Recursively sum all ledger balances within a node (including children) */
function sumNode(node) {
  let od = 0, oc = 0, td = 0, tc = 0, cd = 0, cc = 0;
  for (const l of node.ledgers || []) {
    const ob = Number(l.opening_balance), cb = Number(l.closing_balance);
    if (ob > 0) od += ob; else oc += Math.abs(ob);
    td += Number(l.total_debit); tc += Number(l.total_credit);
    if (cb > 0) cd += cb; else cc += Math.abs(cb);
  }
  for (const child of node.children || []) {
    const s = sumNode(child);
    od += s.od; oc += s.oc; td += s.td; tc += s.tc; cd += s.cd; cc += s.cc;
  }
  return { od, oc, td, tc, cd, cc };
}

/* ── Recursive group renderer ── */
function GroupRows({ nodes, depth = 0, collapsed, toggle, onLedgerClick }) {
  return nodes.map((group) => {
    const isOpen = !collapsed[`${depth}-${group.group_name}`];
    const key = `${depth}-${group.group_name}`;
    const { od, oc, td, tc, cd, cc } = sumNode(group);
    const hasContent = (group.ledgers?.length > 0) || (group.children?.length > 0);
    const paddingLeft = 16 + depth * 16;

    return (
      <Fragment key={key}>
        {/* Group header row */}
        <tr
          className="bg-muted/30 border-t border-border cursor-pointer hover:bg-muted/50 transition-colors"
          onClick={() => toggle(key)}
        >
          <td className="px-4 py-2 font-semibold border-r border-border" style={{ paddingLeft }}>
            <span className="flex items-center gap-1.5">
              {hasContent
                ? isOpen
                  ? <ChevronDown className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                  : <ChevronRight className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                : <span className="w-3.5 h-3.5 flex-shrink-0" />}
              {group.group_name}
              {(group.ledgers?.length > 0 || group.children?.length > 0) && (
                <span className="text-xs font-normal text-muted-foreground ml-1">
                  ({(group.ledgers?.length || 0) + (group.children?.length || 0)})
                </span>
              )}
            </span>
          </td>
          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border/50">{fmt(od)}</td>
          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border">{fmt(oc)}</td>
          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border/50">{fmt(td)}</td>
          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border">{fmt(tc)}</td>
          <td className="px-3 py-2 text-right tabular-nums font-medium border-r border-border/50">{fmt(cd)}</td>
          <td className="px-3 py-2 text-right tabular-nums font-medium">{fmt(cc)}</td>
        </tr>

        {isOpen && (
          <>
            {/* Child account groups */}
            {group.children?.length > 0 && (
              <GroupRows
                nodes={group.children}
                depth={depth + 1}
                collapsed={collapsed}
                toggle={toggle}
                onLedgerClick={onLedgerClick}
              />
            )}

            {/* Direct ledger rows */}
            {group.ledgers?.map((ledger, i) => {
              const ob = Number(ledger.opening_balance);
              const cb = Number(ledger.closing_balance);
              return (
                <tr
                  key={`${key}-l-${i}`}
                  className={`border-t border-border/40 hover:bg-accent/30 transition-colors ${i % 2 === 1 ? "bg-muted/20" : ""}`}
                >
                  <td
                    className="px-4 py-1.5 border-r border-border text-primary hover:underline cursor-pointer"
                    style={{ paddingLeft: paddingLeft + 24 }}
                    onClick={() => onLedgerClick && ledger.ledger_id != null && onLedgerClick(ledger.ledger_id, ledger.ledger_name)}
                  >
                    {ledger.ledger_name}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums border-r border-border/50">{ob > 0 ? fmt(ob) : ""}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums border-r border-border">{ob < 0 ? fmt(ob) : ""}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums border-r border-border/50">{fmt(ledger.total_debit)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums border-r border-border">{fmt(ledger.total_credit)}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums border-r border-border/50">{cb > 0 ? fmt(cb) : ""}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{cb < 0 ? fmt(cb) : ""}</td>
                </tr>
              );
            })}
          </>
        )}
      </Fragment>
    );
  });
}

/* Flatten nested tree for grand totals */
function collectAllLedgers(nodes) {
  const ledgers = [];
  for (const node of nodes) {
    ledgers.push(...(node.ledgers || []));
    if (node.children?.length) ledgers.push(...collectAllLedgers(node.children));
  }
  return ledgers;
}

/* Recursively build print HTML rows */
function buildPrintRows(nodes, depth = 0) {
  return nodes.map((group) => {
    const { od, oc, td, tc, cd, cc } = sumNode(group);
    const pad = depth * 16;
    const childRows = group.children?.length ? buildPrintRows(group.children, depth + 1) : "";
    const ledgerRows = (group.ledgers || []).map((l, i) => {
      const ob = Number(l.opening_balance), cb = Number(l.closing_balance);
      return `<tr${i % 2 === 1 ? ' style="background:#fafafa"' : ""}>
        <td style="padding-left:${pad + 40}px">${l.ledger_name}</td>
        <td style="text-align:right" class="tabular-nums">${ob > 0 ? fmt(ob) : ""}</td>
        <td style="text-align:right" class="tabular-nums">${ob < 0 ? fmt(ob) : ""}</td>
        <td style="text-align:right" class="tabular-nums">${fmt(l.total_debit)}</td>
        <td style="text-align:right" class="tabular-nums">${fmt(l.total_credit)}</td>
        <td style="text-align:right" class="tabular-nums">${cb > 0 ? fmt(cb) : ""}</td>
        <td style="text-align:right" class="tabular-nums">${cb < 0 ? fmt(cb) : ""}</td>
      </tr>`;
    }).join("");

    return `<tr class="group-header">
      <td style="padding-left:${pad + 16}px;font-weight:600">${group.group_name}</td>
      <td style="text-align:right;font-weight:600" class="tabular-nums">${fmt(od)}</td>
      <td style="text-align:right;font-weight:600" class="tabular-nums">${fmt(oc)}</td>
      <td style="text-align:right;font-weight:600" class="tabular-nums">${fmt(td)}</td>
      <td style="text-align:right;font-weight:600" class="tabular-nums">${fmt(tc)}</td>
      <td style="text-align:right;font-weight:600" class="tabular-nums">${fmt(cd)}</td>
      <td style="text-align:right;font-weight:600" class="tabular-nums">${fmt(cc)}</td>
    </tr>${childRows}${ledgerRows}`;
  }).join("");
}

export default function TrialBalance() {
  const [fromDate, setFromDate] = useState(firstOfYear);
  const [toDate, setToDate] = useState(today);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [collapsed, setCollapsed] = useState({});
  const [combined, setCombined] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [ledgerModal, setLedgerModal] = useState(null); // { id, name }

  const user = JSON.parse(sessionStorage.getItem("user") || "{}");
  const canViewCombined = user.is_superuser || ["admin", "super admin"].includes((user.role || "").toLowerCase());

  useEffect(() => {
    fetchCompanies().then((res) => {
      if (res.success) {
        const results = res.data?.results || res.data || [];
        if (results.length > 0) setCompanyName(results[0].company_name || "");
      }
    });
  }, []);

  const toggle = (key) => setCollapsed((p) => ({ ...p, [key]: !p[key] }));

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

  // Grand totals from the full nested tree
  const allLedgers = report ? collectAllLedgers(report.trial_balance) : [];
  let grandOpenDr = 0, grandOpenCr = 0, grandTxnDr = 0, grandTxnCr = 0, grandCloseDr = 0, grandCloseCr = 0;
  for (const l of allLedgers) {
    const ob = Number(l.opening_balance), cb = Number(l.closing_balance);
    if (ob > 0) grandOpenDr += ob; else grandOpenCr += Math.abs(ob);
    grandTxnDr += Number(l.total_debit); grandTxnCr += Number(l.total_credit);
    if (cb > 0) grandCloseDr += cb; else grandCloseCr += Math.abs(cb);
  }

  const handlePrint = () => {
    if (!report) return;
    const groupRows = buildPrintRows(report.trial_balance);
    const html = `<table>
      <thead>
        <tr>
          <th rowspan="2" style="width:30%;text-align:left">Particulars</th>
          <th colspan="2" style="text-align:center">Opening Balance</th>
          <th colspan="2" style="text-align:center">Transactions</th>
          <th colspan="2" style="text-align:center">Closing Balance</th>
        </tr>
        <tr>
          <th style="text-align:right">Debit</th><th style="text-align:right">Credit</th>
          <th style="text-align:right">Debit</th><th style="text-align:right">Credit</th>
          <th style="text-align:right">Debit</th><th style="text-align:right">Credit</th>
        </tr>
      </thead>
      <tbody>${groupRows}</tbody>
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

    const toDdMm = (s) => {
      const [y, m, d] = (s || "").split("-");
      return y && m && d ? `${d}-${m}-${y}` : s;
    };
    printReport({
      title: "Trial Balance",
      subtitle: `${toDdMm(fromDate)} to ${toDdMm(toDate)}`,
      html,
      landscape: true,
      company: companyName,
    });
  };

  return (
    <div className="flex flex-col gap-4">
      {/* ── Filters ── */}
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
              className="size-4 rounded border-gray-300"
            />
            <Label htmlFor="tb-combined" className="text-xs cursor-pointer">Combined (All Retails)</Label>
          </div>
        )}
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
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      )}

      {report && !loading && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
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
                <GroupRows
                  nodes={report.trial_balance}
                  depth={0}
                  collapsed={collapsed}
                  toggle={toggle}
                  onLedgerClick={(id, name) => setLedgerModal({ id, name })}
                />
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

      {ledgerModal && (
        <LedgerTxnModal
          ledger={ledgerModal}
          fromDate={fromDate}
          toDate={toDate}
          combined={combined}
          onClose={() => setLedgerModal(null)}
        />
      )}
    </div>
  );
}

/* ─── Ledger transactions modal ─────────────────────────────────────────── */
function LedgerTxnModal({ ledger, fromDate, toDate, combined, onClose }) {
  const [txns, setTxns] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    setTxns(null);
    const params = new URLSearchParams({ ledger_id: ledger.id, start_date: fromDate, end_date: toDate });
    if (combined) params.set("combined", "true");
    apiClient
      .get(`/accounting/api/pnl-ledger-txns/?${params}`)
      .then((res) => setTxns(res.data?.transactions || []))
      .catch((e) => setError(e.response?.data?.error || "Failed to load transactions."))
      .finally(() => setLoading(false));
  }, [ledger.id, fromDate, toDate, combined]);

  const totalDr = (txns || []).reduce((s, t) => s + Number(t.debit || 0), 0);
  const totalCr = (txns || []).reduce((s, t) => s + Number(t.credit || 0), 0);

  const fmtDate = (s) => {
    if (!s) return "";
    const d = new Date(s);
    if (isNaN(d)) return s;
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-background rounded-lg shadow-xl w-full max-w-4xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <div>
            <h3 className="font-semibold text-sm">{ledger.name}</h3>
            <p className="text-xs text-muted-foreground">Transactions from {fromDate} to {toDate}</p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-muted rounded">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 overflow-auto p-4">
          {loading && (
            <div className="flex items-center justify-center py-10 text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading…
            </div>
          )}
          {error && <div className="text-sm text-destructive py-4">{error}</div>}
          {!loading && !error && txns && txns.length === 0 && (
            <div className="text-center py-10 text-sm text-muted-foreground">No transactions in this period.</div>
          )}
          {!loading && !error && txns && txns.length > 0 && (
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Voucher</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Narration</th>
                  <th className="px-3 py-2 text-right">Debit</th>
                  <th className="px-3 py-2 text-right">Credit</th>
                </tr>
              </thead>
              <tbody>
                {txns.map((t, i) => (
                  <tr key={i} className={`border-t border-border/40 ${i % 2 === 1 ? "bg-muted/20" : ""}`}>
                    <td className="px-3 py-1.5 whitespace-nowrap">{fmtDate(t.voucher_main__date)}</td>
                    <td className="px-3 py-1.5 font-mono">{t.voucher_main__voucher_no}</td>
                    <td className="px-3 py-1.5">{t.voucher_main__voucher_type}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{t.voucher_main__narration || ""}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{Number(t.debit) ? fmt(t.debit) : ""}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{Number(t.credit) ? fmt(t.credit) : ""}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-border bg-muted/40 font-semibold">
                  <td colSpan={4} className="px-3 py-2 text-right">Total</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(totalDr)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(totalCr)}</td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
