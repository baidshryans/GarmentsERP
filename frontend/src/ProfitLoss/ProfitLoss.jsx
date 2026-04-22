import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { ChevronDown, ChevronRight, X, Printer } from "lucide-react";
import { printReport } from "@/lib/printReport";
import { fetchCompanies } from "@/services/apiService";

const today = new Date().toISOString().split("T")[0];
const fy = new Date().getMonth() < 3 ? new Date().getFullYear() - 1 : new Date().getFullYear();
const firstOfYear = `${fy}-04-01`;

const fmt = (v) => {
  const n = Number(v);
  if (!n && n !== 0) return "—";
  return Math.abs(n).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};

/* ═══════════════════════════════════════════════════════════════
   Drill-down Modal — shows the voucher list behind a P&L figure
   ═══════════════════════════════════════════════════════════════ */
function DrilldownModal({ title, metric, startDate, endDate, onClose, accountGroupId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let url = `/accounting/api/pnl-drilldown/?metric=${metric}&start_date=${startDate}&end_date=${endDate}`;
    if (accountGroupId) url += `&account_group_id=${accountGroupId}`;
    apiClient
      .get(url)
      .then((r) => setRows(r.data.vouchers || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [metric, startDate, endDate, accountGroupId]);

  // Determine columns based on metric
  const isExpenses = metric === "expenses";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="bg-background rounded-lg border border-border shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border">
          <h3 className="font-semibold text-foreground">{title}</h3>
          <button onClick={onClose} className="p-1 rounded hover:bg-muted transition-colors">
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="p-5 flex flex-col gap-2">
              {[...Array(6)].map((_, i) => (
                <Skeleton key={i} className="h-8 w-full" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">No transactions found.</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10">
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2.5 text-left font-semibold">Date</th>
                  <th className="px-4 py-2.5 text-left font-semibold">Voucher No</th>
                  {isExpenses ? (
                    <>
                      <th className="px-4 py-2.5 text-left font-semibold">Account</th>
                      <th className="px-4 py-2.5 text-right font-semibold">Debit</th>
                      <th className="px-4 py-2.5 text-right font-semibold">Credit</th>
                    </>
                  ) : (
                    <>
                      <th className="px-4 py-2.5 text-left font-semibold">Party</th>
                      <th className="px-4 py-2.5 text-right font-semibold">Amount</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr
                    key={i}
                    className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/20" : ""} hover:bg-accent/30 transition-colors`}
                  >
                    <td className="px-4 py-1.5 tabular-nums">
                      {r.date || r.voucher_main__date}
                    </td>
                    <td className="px-4 py-1.5 font-mono text-xs">
                      {r.voucher_no || r.voucher_main__voucher_no}
                    </td>
                    {isExpenses ? (
                      <>
                        <td className="px-4 py-1.5">{r.account__ac_name}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          {Number(r.debit) > 0 ? fmt(r.debit) : ""}
                        </td>
                        <td className="px-4 py-1.5 text-right tabular-nums">
                          {Number(r.credit) > 0 ? fmt(r.credit) : ""}
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="px-4 py-1.5">{r.party || r.narration}</td>
                        <td className="px-4 py-1.5 text-right tabular-nums">{fmt(r.total)}</td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-border bg-muted/50 font-semibold text-sm">
                  <td colSpan={isExpenses ? 3 : 3} className="px-4 py-2">
                    {rows.length} transaction(s)
                  </td>
                  {isExpenses ? (
                    <>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {fmt(rows.reduce((s, r) => s + Number(r.debit || 0), 0))}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {fmt(rows.reduce((s, r) => s + Number(r.credit || 0), 0))}
                      </td>
                    </>
                  ) : (
                    <td className="px-4 py-2 text-right tabular-nums">
                      {fmt(rows.reduce((s, r) => s + Number(r.total || 0), 0))}
                    </td>
                  )}
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Clickable P&L row — opens drill-down on click
   ═══════════════════════════════════════════════════════════════ */
function PnlRow({ label, value, indent = false, bold = false, metric, onDrill, negative = false, border = false }) {
  const clickable = !!metric;
  const n = Number(value || 0);

  return (
    <tr
      className={[
        "border-t border-border/40",
        clickable ? "cursor-pointer hover:bg-accent/40 transition-colors" : "",
        bold ? "font-semibold" : "",
        border ? "border-t-2 border-border" : "",
      ].join(" ")}
      onClick={clickable ? () => onDrill(metric, label) : undefined}
    >
      <td className={`py-2 pr-3 ${indent ? "pl-8" : "pl-4"}`}>
        <span className="flex items-center gap-2">
          {label}
          {clickable && (
            <ChevronRight className="size-3 text-muted-foreground opacity-0 group-hover:opacity-100" />
          )}
        </span>
      </td>
      <td className="py-2 px-4 text-right tabular-nums">
        {negative && n > 0 ? `(${fmt(n)})` : fmt(n)}
      </td>
    </tr>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Expense tree — collapsible, each leaf opens drill-down
   ═══════════════════════════════════════════════════════════════ */
function ExpenseTree({ items, level = 0, onDrill }) {
  const [collapsed, setCollapsed] = useState({});
  if (!items?.length) return null;

  return items.map((acc) => {
    const hasChildren = acc.children?.length > 0;
    const isOpen = !collapsed[acc.id];
    const bal = Math.abs(Number(acc.balance || 0));
    const indent = 16 + level * 20;

    return (
      <tbody key={acc.id}>
        <tr
          className="border-t border-border/40 hover:bg-accent/40 transition-colors cursor-pointer"
          onClick={() => {
            if (hasChildren) {
              setCollapsed((p) => ({ ...p, [acc.id]: !p[acc.id] }));
            } else {
              onDrill("expenses", acc.name, acc.id);
            }
          }}
        >
          <td className="py-2 pr-3" style={{ paddingLeft: indent }}>
            <span className="flex items-center gap-1.5">
              {hasChildren ? (
                isOpen ? (
                  <ChevronDown className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                ) : (
                  <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                )
              ) : (
                <span className="w-[14px] shrink-0" />
              )}
              {acc.name}
            </span>
          </td>
          <td className="py-2 px-4 text-right tabular-nums">{bal ? fmt(bal) : ""}</td>
        </tr>
        {hasChildren && isOpen && (
          <ExpenseTree items={acc.children} level={level + 1} onDrill={onDrill} />
        )}
      </tbody>
    );
  });
}

/* ═══════════════════════════════════════════════════════════════
   Main P&L Component
   ═══════════════════════════════════════════════════════════════ */
export default function ProfitLoss() {
  const [startDate, setStartDate] = useState(firstOfYear);
  const [endDate, setEndDate] = useState(today);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [drill, setDrill] = useState(null); // { metric, title, accountGroupId? }
  const [combined, setCombined] = useState(false);
  const [companyName, setCompanyName] = useState("");

  useEffect(() => {
    fetchCompanies().then((res) => {
      if (res.success) {
        const results = res.data?.results || res.data || [];
        if (results.length > 0) setCompanyName(results[0].company_name || "");
      }
    });
  }, []);

  const user = JSON.parse(sessionStorage.getItem("user") || "{}");
  const canViewCombined = user.is_superuser || ["admin", "super admin"].includes((user.role || "").toLowerCase());

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    try {
      const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
      if (combined) params.set("combined", "true");
      const res = await apiClient.get(`/accounting/api/pnl?${params}`);
      setData(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load Profit & Loss data.");
    }
    setLoading(false);
  };

  const openDrill = useCallback(
    (metric, title, accountGroupId) => {
      setDrill({ metric, title, accountGroupId });
    },
    []
  );

  const handlePrint = () => {
    if (!data) return;
    const row = (label, value, opts = {}) => {
      const { indent, bold, negative, border } = opts;
      const n = Number(value || 0);
      const display = negative && n > 0 ? `(${fmt(n)})` : fmt(n);
      return `<tr${border ? ' style="border-top:2px solid #94a3b8"' : ""}${bold ? ' class="font-semibold"' : ""}>
        <td${indent ? ` style="padding-left:${indent}px"` : ""}>${label}</td>
        <td style="text-align:right" class="tabular-nums">${display}</td>
      </tr>`;
    };
    const sectionHead = (label) =>
      `<tr class="section-header"><td colspan="2">${label}</td></tr>`;

    // Flatten expense tree
    const flattenExpenses = (items, level = 0) => {
      if (!items?.length) return "";
      return items
        .map((acc) => {
          const bal = Math.abs(Number(acc.balance || 0));
          const indent = 24 + level * 20;
          let html = `<tr><td style="padding-left:${indent}px">${acc.name}</td>
            <td style="text-align:right" class="tabular-nums">${bal ? fmt(bal) : ""}</td></tr>`;
          if (acc.children?.length) html += flattenExpenses(acc.children, level + 1);
          return html;
        })
        .join("");
    };

    const np = Number(data.net_profit || 0);
    const html = `<table>
      <thead><tr><th>Particulars</th><th style="text-align:right;width:150px">Amount (\u20B9)</th></tr></thead>
      <tbody>
        ${sectionHead("Revenue")}
        ${row("Gross Sales", data.gross_sales, { indent: 24 })}
        ${Number(data.sales_return) > 0 ? row("(\u2212) Sales Returns", data.sales_return, { indent: 24, negative: true }) : ''}
        ${row("Net Sales Revenue", data.sales_revenue, { bold: true, border: true })}
        ${sectionHead("Cost of Goods Sold")}
        ${row("Opening Stock", data.opening_stock, { indent: 24 })}
        ${row("(+) Gross Purchases", data.purchases, { indent: 24 })}
        ${row("(\u2212) Purchase Returns", data.purchase_returns, { indent: 24, negative: true })}
        ${row("(\u2212) Closing Stock", data.closing_stock, { indent: 24, negative: true })}
        ${row("Total COGS", data.cogs, { bold: true, border: true })}
        ${sectionHead("Direct Expenses")}
        ${flattenExpenses(data.direct_expenses)}
        ${row("Total Direct Expenses", data.direct_expenses_total, { bold: true, border: true })}
        ${row("Gross Profit", data.gross_profit, { bold: true, border: true })}
        ${sectionHead("Indirect Expenses")}
        ${flattenExpenses(data.indirect_expenses)}
        ${row("Total Indirect Expenses", data.indirect_expenses_total, { bold: true, border: true })}
      </tbody>
      <tfoot><tr class="totals-row">
        <td style="font-size:12px">${np >= 0 ? "Net Profit" : "Net Loss"}</td>
        <td style="text-align:right;font-size:12px;color:${np >= 0 ? "#059669" : "#e11d48"}" class="tabular-nums font-bold">${fmt(data.net_profit)}</td>
      </tr></tfoot>
    </table>`;

    const toDdMm = (s) => {
      const [y, m, d] = (s || "").split("-");
      return y && m && d ? `${d}-${m}-${y}` : s;
    };
    printReport({
      title: "Profit & Loss Statement",
      subtitle: `${toDdMm(startDate)} to ${toDdMm(endDate)}`,
      html,
      company: companyName,
    });
  };

  const netProfit = Number(data?.net_profit || 0);

  return (
    <div className="flex flex-col gap-4">
      {/* ── Filters ───────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border print:hidden">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="h-9 w-36" />
        </div>
        {canViewCombined && (
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="pnl-combined"
              checked={combined}
              onChange={(e) => setCombined(e.target.checked)}
              className="size-4 rounded border-gray-300"
            />
            <Label htmlFor="pnl-combined" className="text-xs cursor-pointer">Combined (All Retails)</Label>
          </div>
        )}
        <Button size="sm" onClick={fetchReport} className="h-9">Show</Button>
        {data && (
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

      {data && !loading && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            {/* ── Header ───────────────────────────────────── */}
            <thead>
              <tr className="bg-muted/50">
                <th className="px-4 py-3 text-left font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Particulars
                </th>
                <th className="px-4 py-3 text-right font-semibold text-xs uppercase tracking-wider text-muted-foreground w-40">
                  Amount (₹)
                </th>
              </tr>
            </thead>

            {/* ── Revenue ──────────────────────────────────── */}
            <tbody>
              <tr className="bg-muted/30">
                <td colSpan={2} className="px-4 py-2 font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Revenue
                </td>
              </tr>
              <PnlRow label="Gross Sales" value={data.gross_sales} indent metric="sales" onDrill={openDrill} />
              {Number(data.sales_return) > 0 && (
                <PnlRow label="(-) Sales Returns" value={data.sales_return} indent negative />
              )}
              <PnlRow label="Net Sales Revenue" value={data.sales_revenue} bold border />
            </tbody>

            {/* ── COGS ─────────────────────────────────────── */}
            <tbody>
              <tr className="bg-muted/30">
                <td colSpan={2} className="px-4 py-2 font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Cost of Goods Sold
                </td>
              </tr>
              <PnlRow label="Opening Stock" value={data.opening_stock} indent />
              <PnlRow label="(+) Gross Purchases" value={data.purchases} indent metric="purchases" onDrill={openDrill} />
              <PnlRow label="(−) Purchase Returns" value={data.purchase_returns} indent negative metric="purchase_returns" onDrill={openDrill} />
              <PnlRow label="(−) Closing Stock" value={data.closing_stock} indent negative />
              <PnlRow label="Total COGS" value={data.cogs} bold border />
            </tbody>

            {/* ── Direct Expenses ──────────────────────────── */}
            <tbody>
              <tr className="bg-muted/30 border-t border-border">
                <td colSpan={2} className="px-4 py-2 font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Direct Expenses
                </td>
              </tr>
            </tbody>
            <ExpenseTree items={data.direct_expenses} onDrill={openDrill} />
            <tbody>
              <PnlRow label="Total Direct Expenses" value={data.direct_expenses_total} bold border />
            </tbody>

            {/* ── Gross Profit = Net Sales - COGS - Direct Expenses ── */}
            <tbody>
              <PnlRow label="Gross Profit" value={data.gross_profit} bold border />
            </tbody>

            {/* ── Indirect Expenses ────────────────────────── */}
            <tbody>
              <tr className="bg-muted/30 border-t border-border">
                <td colSpan={2} className="px-4 py-2 font-semibold text-xs uppercase tracking-wider text-muted-foreground">
                  Indirect Expenses
                </td>
              </tr>
            </tbody>
            <ExpenseTree items={data.indirect_expenses} onDrill={openDrill} />
            <tbody>
              <PnlRow label="Total Indirect Expenses" value={data.indirect_expenses_total} bold border />
            </tbody>

            {/* ── Net Profit / Loss = Gross Profit - Indirect Expenses ── */}
            <tfoot>
              <tr className="border-t-2 border-border bg-muted/50">
                <td className="px-4 py-3 font-semibold text-base">
                  {netProfit >= 0 ? "Net Profit" : "Net Loss"}
                </td>
                <td
                  className={`px-4 py-3 text-right font-bold text-base tabular-nums ${
                    netProfit >= 0 ? "text-emerald-600" : "text-rose-600"
                  }`}
                >
                  {fmt(data.net_profit)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {/* ── Drill-down modal ──────────────────────────────── */}
      {drill && (
        <DrilldownModal
          title={drill.title}
          metric={drill.metric}
          startDate={startDate}
          endDate={endDate}
          accountGroupId={drill.accountGroupId}
          onClose={() => setDrill(null)}
        />
      )}
    </div>
  );
}
