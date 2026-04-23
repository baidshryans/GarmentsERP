import { useState, useEffect, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { fetchCompanies } from "@/services/apiService";
import {
  Printer, ChevronRight, ChevronDown, X, Loader2, Scale,
  TrendingUp, Wallet, Landmark,
} from "lucide-react";
import { printReport } from "@/lib/printReport";
import { RetailScopePicker, applyRetailScopeParams } from "@/components/common/RetailScopePicker";

const today = new Date().toISOString().split("T")[0];

const fmt = (v) => {
  const n = Number(v);
  if (!n) return "—";
  return Math.abs(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

// Positive = debit balance, negative = credit balance (our Dr-Cr convention)
const balLabel = (v) => {
  const n = Number(v);
  if (n === 0) return "—";
  return `${fmt(n)} ${n >= 0 ? "Dr" : "Cr"}`;
};

// Indian-lakh compact formatter for the summary tiles (e.g. ₹ 16.99 L)
const fmtCompact = (v) => {
  const n = Math.abs(Number(v) || 0);
  if (n >= 1e7) return `${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(2)} L`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)} K`;
  return n.toFixed(0);
};

/* ── Ledger drill-down modal ──────────────────────────────────────────────── */
function LedgerModal({ groupId, groupName, endDate, onClose }) {
  const [ledgers, setLedgers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");

  useEffect(() => {
    setLoading(true);
    apiClient
      .get(`/accounting/api/bs-group-ledgers/?group_id=${groupId}&end_date=${endDate}`)
      .then((res) => setLedgers(res.data.ledgers || []))
      .catch(() => setError("Failed to load ledgers."))
      .finally(() => setLoading(false));
  }, [groupId, endDate]);

  const total = ledgers?.reduce((s, l) => s + Number(l.balance || 0), 0) ?? 0;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-card rounded-xl shadow-2xl w-[92vw] max-w-xl max-h-[80vh] flex flex-col border border-border"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div>
            <p className="font-semibold text-foreground text-sm">{groupName}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Ledger balances as on {new Date(endDate + "T00:00:00").toLocaleDateString("en-IN")}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 hover:bg-accent rounded-lg transition-colors cursor-pointer"
          >
            <X className="size-4 text-muted-foreground" />
          </button>
        </div>

        <div className="overflow-auto flex-1">
          {loading && (
            <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground text-sm">
              <Loader2 className="size-4 animate-spin" /> Loading…
            </div>
          )}
          {error && <p className="text-center py-16 text-destructive text-sm">{error}</p>}
          {!loading && ledgers?.length === 0 && (
            <p className="text-center py-16 text-muted-foreground text-sm">No ledger balances for this group.</p>
          )}
          {!loading && ledgers && ledgers.length > 0 && (
            <table className="w-full text-sm border-collapse">
              <thead className="bg-muted/50 sticky top-0">
                <tr>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold text-muted-foreground uppercase tracking-wide border-b border-border">
                    Ledger
                  </th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-semibold text-muted-foreground uppercase tracking-wide border-b border-border w-36">
                    Balance
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {ledgers.map((l, i) => (
                  <tr key={l.id} className={`hover:bg-accent/30 transition-colors ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
                    <td className="px-4 py-2 text-foreground">{l.ac_name}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-sm">
                      {balLabel(l.balance)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-border bg-muted/50">
                <tr>
                  <td className="px-4 py-2.5 font-semibold text-[11px] uppercase tracking-wide text-muted-foreground">
                    Total
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-bold text-foreground">
                    {balLabel(total)}
                  </td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Subgroup block (header + child rows + subtotal) ──────────────────────── */
function SubgroupBlock({ group, onOpen, activeId }) {
  const [expanded, setExpanded] = useState(true);
  const visibleAccounts = (group.accounts || []).filter(
    (a) => Number(a.balance || 0) !== 0
  );
  if (visibleAccounts.length === 0 && Number(group.total || 0) === 0) return null;

  return (
    <>
      <tr
        className="bg-muted/40 border-t border-border cursor-pointer hover:bg-muted/60 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="px-4 py-2 text-sm font-semibold flex items-center gap-1.5">
          {expanded
            ? <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden="true" />
            : <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden="true" />}
          {group.name}
        </td>
        <td className="px-4 py-2 text-right tabular-nums text-sm font-semibold">
          {fmt(group.total)}
        </td>
      </tr>
      {expanded && visibleAccounts.map((acc) => {
        const isSpecial = acc.id === "net_profit" || acc.id === "closing_stock";
        const isActive = activeId === acc.id;
        return (
          <tr
            key={acc.id}
            onClick={() => !isSpecial && onOpen(acc.id, acc.name)}
            className={`border-t border-border/30 transition-colors
              ${isSpecial ? "opacity-80" : "cursor-pointer hover:bg-primary/5"}
              ${isActive ? "bg-primary/10" : ""}`}
          >
            <td className="px-4 py-1.5 pl-12 text-sm flex items-center gap-1.5">
              {!isSpecial && (
                isActive
                  ? <ChevronDown className="size-3 text-primary flex-shrink-0" aria-hidden="true" />
                  : <ChevronRight className="size-3 text-muted-foreground/40 flex-shrink-0" aria-hidden="true" />
              )}
              {acc.id === "net_profit"
                ? <span className="italic text-muted-foreground">{acc.name}</span>
                : <span className="text-muted-foreground">{acc.name}</span>}
            </td>
            <td className="px-4 py-1.5 text-right tabular-nums text-sm text-muted-foreground">
              {balLabel(acc.balance)}
            </td>
          </tr>
        );
      })}
    </>
  );
}

/* ── Side panel (Assets or Liabilities) ───────────────────────────────────── */
function SidePanel({ title, icon: Icon, side, totalLabel, onOpen, activeId }) {
  const groups = (side?.groups || []).filter(
    (g) => Number(g.total || 0) !== 0 || (g.accounts || []).some((a) => Number(a.balance || 0) !== 0)
  );
  return (
    <div className="rounded-lg border border-border overflow-hidden bg-card">
      <div className="flex items-center gap-2 px-4 py-2.5 bg-muted/50 border-b border-border">
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
      </div>
      <table className="w-full text-sm">
        <tbody>
          {groups.length === 0 && (
            <tr>
              <td colSpan={2} className="px-4 py-8 text-center text-sm text-muted-foreground">
                No {title.toLowerCase()} with balance.
              </td>
            </tr>
          )}
          {groups.map((g) => (
            <SubgroupBlock key={g.id} group={g} onOpen={onOpen} activeId={activeId} />
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-border bg-muted/60">
            <td className="px-4 py-2.5 font-semibold text-sm">{totalLabel}</td>
            <td className="px-4 py-2.5 text-right tabular-nums font-bold text-sm">
              {fmt(side?.total)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

/* ── Main component ───────────────────────────────────────────────────────── */
export default function BalanceSheet() {
  const [endDate, setEndDate]   = useState(today);
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [scope, setScope]             = useState("all");
  const [selectedRetailIds, setSelectedRetailIds] = useState([]);
  const [modal, setModal]       = useState(null);
  const [activeId, setActiveId] = useState(null);
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
    if (scope === "selected" && selectedRetailIds.length === 0) {
      setError("Select at least one retail, or choose 'All retails (combined)'.");
      return;
    }
    setLoading(true);
    setModal(null);
    setActiveId(null);
    try {
      const params = new URLSearchParams({ end_date: endDate });
      applyRetailScopeParams(params, scope, selectedRetailIds);
      const res = await apiClient.get(`/accounting/api/bal-sheet?${params}`);
      setData(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load Balance Sheet data.");
    }
    setLoading(false);
  };

  useEffect(() => { fetchReport(); /* eslint-disable-next-line */ }, []);

  const openGroup = useCallback((id, name) => {
    if (activeId === id) {
      setModal(null);
      setActiveId(null);
    } else {
      setModal({ id, name });
      setActiveId(id);
    }
  }, [activeId]);

  const netWorth = Number(data?.net_worth ?? 0);
  const isBalanced = netWorth === 0;

  const assetsTotal = Number(data?.assets?.total || 0);
  const liabilitiesTotal = Math.abs(Number(data?.liabilities?.total || 0));

  const handlePrint = () => {
    if (!data) return;

    const renderSection = (title, groups, total) => {
      const rows = (groups || [])
        .filter((g) => Number(g.total || 0) !== 0 || (g.accounts || []).some((a) => Number(a.balance || 0) !== 0))
        .map((g) => {
          const accRows = (g.accounts || [])
            .filter((a) => Number(a.balance || 0) !== 0)
            .map((acc) => `<tr>
              <td style="padding-left:32px">${acc.id === "net_profit" ? `<em>${acc.name}</em>` : acc.name}</td>
              <td style="text-align:right" class="tabular-nums">${balLabel(acc.balance)}</td>
            </tr>`).join("");
          return `<tr style="background:#f5f5f5"><td style="font-weight:600;padding-left:12px">${g.name}</td>
                    <td style="text-align:right;font-weight:600" class="tabular-nums">${fmt(g.total)}</td></tr>
                  ${accRows}`;
        }).join("");
      return `<tr class="section-header"><td colspan="2">${title}</td></tr>
        ${rows}
        <tr class="totals-row"><td>Total ${title}</td>
          <td style="text-align:right" class="tabular-nums">${fmt(total)}</td></tr>`;
    };

    const html = `<table>
      <thead><tr><th>Particulars</th><th style="text-align:right;width:150px">Amount (₹)</th></tr></thead>
      <tbody>
        ${renderSection("Assets", data.assets?.groups, data.assets?.total)}
        ${renderSection("Liabilities & Equity", data.liabilities?.groups, data.liabilities?.total)}
      </tbody>
      <tfoot><tr class="totals-row">
        <td>Difference (Assets − Liabilities)</td>
        <td style="text-align:right" class="tabular-nums font-bold">${fmt(data.net_worth)}</td>
      </tr></tfoot>
    </table>`;

    const [y, m, d] = (endDate || "").split("-");
    const ddmmyyyy  = y && m && d ? `${d}-${m}-${y}` : endDate;
    const scopeLabel = scope === "all"
      ? " (Combined — All Retails)"
      : selectedRetailIds.length === 1
        ? ""
        : ` (${selectedRetailIds.length} retails)`;
    printReport({
      title: "Balance Sheet",
      subtitle: `As on ${ddmmyyyy}${scopeLabel}`,
      html,
      company: companyName,
    });
  };

  const asOnLabel = useMemo(() => {
    if (!endDate) return "";
    const [y, m, d] = endDate.split("-");
    return `${d}-${m}-${y}`;
  }, [endDate]);

  return (
    <div className="flex flex-col gap-4">
      {/* ── Filter bar ───────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-3 bg-muted/30 rounded-lg border border-border print:hidden">
        <div className="flex flex-col gap-1">
          <Label htmlFor="bs-end-date" className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            As on
          </Label>
          <Input
            id="bs-end-date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="h-9 w-40"
          />
        </div>
        {canViewCombined && (
          <RetailScopePicker
            scope={scope}
            selectedIds={selectedRetailIds}
            onChange={({ scope: s, selectedIds }) => {
              setScope(s);
              setSelectedRetailIds(selectedIds);
            }}
          />
        )}
        <Button size="sm" onClick={fetchReport} disabled={loading} className="h-9 cursor-pointer">
          {loading ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : "Show Report"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={handlePrint}
          disabled={!data}
          aria-label="Print balance sheet"
          className="h-9 cursor-pointer ml-auto"
        >
          <Printer className="size-4 mr-1.5" aria-hidden="true" /> Print
        </Button>
      </div>

      {error && (
        <p className="text-sm text-destructive border border-destructive/40 bg-destructive/5 rounded-md px-3 py-2">
          {error}
        </p>
      )}

      {/* ── Summary tiles ────────────────────────────────────────────────── */}
      {data && !loading && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Wallet className="size-3.5" aria-hidden="true" /> Total Assets
            </div>
            <p className="mt-1.5 text-xl font-semibold tabular-nums">
              ₹ {fmt(assetsTotal)}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">₹ {fmtCompact(assetsTotal)}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Landmark className="size-3.5" aria-hidden="true" /> Total Liabilities & Equity
            </div>
            <p className="mt-1.5 text-xl font-semibold tabular-nums">
              ₹ {fmt(liabilitiesTotal)}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">₹ {fmtCompact(liabilitiesTotal)}</p>
          </div>
          <div className={`rounded-lg border p-4 ${isBalanced
            ? "border-emerald-200 bg-emerald-50 dark:border-emerald-900/40 dark:bg-emerald-900/10"
            : "border-amber-200 bg-amber-50 dark:border-amber-900/40 dark:bg-amber-900/10"}`}>
            <div className={`flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide ${isBalanced
              ? "text-emerald-800 dark:text-emerald-300"
              : "text-amber-800 dark:text-amber-300"}`}>
              <Scale className="size-3.5" aria-hidden="true" /> Status
            </div>
            <p className={`mt-1.5 text-xl font-semibold tabular-nums ${isBalanced
              ? "text-emerald-700 dark:text-emerald-300"
              : "text-amber-700 dark:text-amber-300"}`}>
              {isBalanced ? "Balanced" : balLabel(netWorth)}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {isBalanced ? "Assets = Liabilities + Equity" : "Difference (Assets − Liabilities)"}
            </p>
          </div>
        </div>
      )}

      {data && !loading && (
        <p className="text-[11px] text-muted-foreground -mt-1 print:hidden">
          Balance Sheet as on {asOnLabel}{scope === "all" ? " · Combined (all retails)" : selectedRetailIds.length > 1 ? ` · ${selectedRetailIds.length} retails` : ""}. Click any account to see its ledgers.
        </p>
      )}

      {loading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="flex flex-col gap-2">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </div>
          <div className="flex flex-col gap-2">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
          </div>
        </div>
      )}

      {/* ── Side-by-side two-column layout ───────────────────────────────── */}
      {data && !loading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <SidePanel
            title="Assets"
            icon={Wallet}
            side={data.assets}
            totalLabel="Total Assets"
            onOpen={openGroup}
            activeId={activeId}
          />
          <SidePanel
            title="Liabilities & Equity"
            icon={Landmark}
            side={data.liabilities}
            totalLabel="Total Liabilities & Equity"
            onOpen={openGroup}
            activeId={activeId}
          />
        </div>
      )}

      {modal && (
        <LedgerModal
          groupId={modal.id}
          groupName={modal.name}
          endDate={endDate}
          onClose={() => { setModal(null); setActiveId(null); }}
        />
      )}
    </div>
  );
}
