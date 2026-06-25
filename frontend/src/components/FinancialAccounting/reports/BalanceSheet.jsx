import { useState, useEffect, useCallback, useMemo } from "react";
import { formatNumber, formatDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { fetchCompanies } from "@/services/apiService";
import {
  Printer, ChevronRight, ChevronDown, X, Loader2, Scale,
  Wallet, Landmark, ChevronsDownUp, ChevronsUpDown,
  Droplets, TrendingUp, IndianRupee, Coins,
} from "lucide-react";
import { printReport } from "@/lib/printReport";
import { RetailScopePicker, applyRetailScopeParams } from "@/components/common/RetailScopePicker";

const today = new Date().toISOString().split("T")[0];

const fmt = (v) => {
  const n = Number(v);
  if (!n) return "—";
  return formatNumber(n, { decimals: 2, abs: true });
};

// Fine-gold gram formatter — 3 decimals, no Indian-lakh grouping (gold weights
// are typically shown 0.001g precision). "—" when null/zero/no rate available.
const fmtGrams = (v) => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (!n) return "—";
  return formatNumber(n, { decimals: 3, abs: true });
};

// Positive = debit balance, negative = credit balance (our Dr-Cr convention)
// side: "assets" (normal=debit) | "liabilities" (normal=credit)
// Returns { text, anomalous } — anomalous balances shown in parentheses
function bsBalDisplay(balance, side) {
  const n = Number(balance);
  if (n === 0) return { text: "—", anomalous: false };
  const anomalous = side === "assets" ? n < 0 : n > 0;
  return { text: anomalous ? `(${fmt(n)})` : fmt(n), anomalous };
}

function bsGoldDisplay(grams, side) {
  if (grams === null || grams === undefined) return { text: "—", anomalous: false };
  const n = Number(grams);
  if (!n) return { text: "—", anomalous: false };
  const anomalous = side === "assets" ? n < 0 : n > 0;
  return { text: anomalous ? `(${fmtGrams(n)} g)` : `${fmtGrams(n)} g`, anomalous };
}

const balLabel = (v) => {
  const n = Number(v);
  if (n === 0) return "—";
  return `${fmt(n)} ${n >= 0 ? "Dr" : "Cr"}`;
};

const gramsLabel = (v) => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (!n) return "—";
  return `${fmtGrams(n)} g ${n >= 0 ? "Dr" : "Cr"}`;
};

// Indian-lakh compact formatter for the summary tiles (e.g. ₹ 16.99 L)
const fmtCompact = (v) => {
  const n = Math.abs(Number(v) || 0);
  if (n >= 1e7) return `${(n / 1e7).toFixed(2)} Cr`;
  if (n >= 1e5) return `${(n / 1e5).toFixed(2)} L`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)} K`;
  return n.toFixed(0);
};

/* ── Fine-gold rate breakdown modal ───────────────────────────────────────── */
function FineGoldBreakdownModal({ endDate, scope, selectedRetailIds, onClose }) {
  const [data, setData]     = useState(null);
  const [loading, setLoad]  = useState(true);
  const [error, setError]   = useState("");
  const [openSrc, setOpenSrc] = useState({ purchases: true });

  useEffect(() => {
    setLoad(true);
    const params = new URLSearchParams({ end_date: endDate });
    applyRetailScopeParams(params, scope, selectedRetailIds);
    apiClient
      .get(`/accounting/api/fine-gold-rate-breakdown?${params}`)
      .then((res) => setData(res.data))
      .catch(() => setError("Failed to load breakdown."))
      .finally(() => setLoad(false));
  }, [endDate, scope, selectedRetailIds]);

  const num = (v, dp = 2) => formatNumber(v, { decimals: dp });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div className="bg-card rounded-xl shadow-2xl w-[96vw] max-w-4xl max-h-[88vh] flex flex-col border border-border" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div>
            <p className="font-semibold text-foreground text-sm">How the fine-gold rate was calculated</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Σ value (₹) ÷ Σ fine grams · Window: {data?.fy_start} → {data?.end_date}
            </p>
          </div>
          <button onClick={onClose} aria-label="Close" className="p-1.5 hover:bg-accent rounded-lg cursor-pointer">
            <X className="size-4 text-muted-foreground" />
          </button>
        </div>

        <div className="overflow-auto flex-1 p-4 space-y-4">
          {loading && (
            <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground text-sm">
              <Loader2 className="size-4 animate-spin" /> Loading breakdown…
            </div>
          )}
          {error && <p className="text-center py-16 text-destructive text-sm">{error}</p>}

          {!loading && data && (
            <>
              {/* Totals card */}
              <div className="rounded-lg border border-border bg-muted/30 p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Σ Value (₹)</p>
                  <p className="text-base font-semibold tabular-nums">₹ {num(data.total_value)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Σ Fine Grams (24K)</p>
                  <p className="text-base font-semibold tabular-nums">{num(data.total_fine_grams, 3)} g</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-muted-foreground">Fine-Gold Rate</p>
                  <p className="text-base font-semibold tabular-nums text-amber-700 dark:text-amber-300">
                    {data.fine_gold_rate ? `₹ ${num(data.fine_gold_rate)} / g` : "—"}
                  </p>
                </div>
              </div>

              {/* Per-source sections */}
              {data.sources.map((src) => {
                const expanded = openSrc[src.key];
                const Chev = expanded ? ChevronDown : ChevronRight;
                return (
                  <div key={src.key} className="rounded-lg border border-border overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setOpenSrc((p) => ({ ...p, [src.key]: !p[src.key] }))}
                      className="w-full flex items-center justify-between px-4 py-2.5 bg-muted/40 hover:bg-muted/60 cursor-pointer text-left"
                    >
                      <span className="flex items-center gap-1.5 font-semibold text-sm">
                        <Chev className="size-3.5 text-muted-foreground" /> {src.label}
                        <span className="text-xs text-muted-foreground font-normal ml-1">({src.rows.length} rows)</span>
                      </span>
                      <span className="flex gap-4 text-xs tabular-nums">
                        <span>₹ {num(src.total_value)}</span>
                        <span>{num(src.total_fine_grams, 3)} g</span>
                      </span>
                    </button>
                    {expanded && (
                      src.rows.length === 0 ? (
                        <p className="px-4 py-6 text-center text-xs text-muted-foreground">No rows.</p>
                      ) : (
                        <div className="overflow-auto max-h-72">
                          <table className="w-full text-xs">
                            <thead className="bg-muted/30 sticky top-0">
                              <tr className="text-[10px] uppercase tracking-wide text-muted-foreground">
                                <th className="px-3 py-1.5 text-left">Item</th>
                                <th className="px-3 py-1.5 text-left">Ref / Date</th>
                                <th className="px-3 py-1.5 text-left">Purity</th>
                                <th className="px-3 py-1.5 text-right">GW (g)</th>
                                <th className="px-3 py-1.5 text-right">Rate (₹/g)</th>
                                <th className="px-3 py-1.5 text-right">Value (₹)</th>
                                <th className="px-3 py-1.5 text-right">Fine (g)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-border/40">
                              {src.rows.map((r, i) => (
                                <tr key={i} className={i % 2 ? "bg-muted/10" : ""}>
                                  <td className="px-3 py-1.5">{r.label}</td>
                                  <td className="px-3 py-1.5 text-muted-foreground">
                                    {r.ref || "—"}{r.date ? ` · ${r.date}` : ""}
                                  </td>
                                  <td className="px-3 py-1.5">{r.purity} <span className="text-muted-foreground">({num(r.gw_per, 2)}%)</span></td>
                                  <td className="px-3 py-1.5 text-right tabular-nums">{num(r.gw, 3)}</td>
                                  <td className="px-3 py-1.5 text-right tabular-nums">{num(r.rate)}</td>
                                  <td className="px-3 py-1.5 text-right tabular-nums">{num(r.value)}</td>
                                  <td className="px-3 py-1.5 text-right tabular-nums">{num(r.fine_grams, 3)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )
                    )}
                  </div>
                );
              })}

              <p className="text-[11px] text-muted-foreground italic">
                Formula: fine-gold rate = Σ(value) / Σ(gw × purity% / 100). Each row contributes
                its value to the numerator and gw × purity% / 100 fine grams to the denominator.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Ledger drill-down modal ──────────────────────────────────────────────── */
function LedgerModal({ groupId, groupName, endDate, unit, sideType, onClose }) {
  const [ledgers, setLedgers] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState("");
  const isGold = unit === "gold";

  useEffect(() => {
    setLoading(true);
    const url = `/accounting/api/bs-group-ledgers/?group_id=${groupId}&end_date=${endDate}&unit=${unit || "inr"}`;
    apiClient
      .get(url)
      .then((res) => setLedgers(res.data.ledgers || []))
      .catch(() => setError("Failed to load ledgers."))
      .finally(() => setLoading(false));
  }, [groupId, endDate, unit]);

  const totalKey = isGold ? "gold_grams" : "balance";
  const total = ledgers?.reduce((s, l) => s + Number(l[totalKey] || 0), 0) ?? 0;
  const formatBal = isGold
    ? (v) => { const { text } = bsGoldDisplay(v, sideType); return text; }
    : (v) => { const { text } = bsBalDisplay(v, sideType); return text; };
  const isAnomalous = isGold
    ? (v) => bsGoldDisplay(v, sideType).anomalous
    : (v) => bsBalDisplay(v, sideType).anomalous;

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
              Ledger balances as on {formatDate(endDate + "T00:00:00", {})}
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
                {ledgers.map((l, i) => {
                  const rawVal = isGold ? l.gold_grams : l.balance;
                  const anomalous = isAnomalous(rawVal);
                  return (
                    <tr key={l.id} className={`hover:bg-accent/30 transition-colors ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
                      <td className="px-4 py-2 text-foreground">{l.ac_name}</td>
                      <td className={"px-4 py-2 text-right tabular-nums text-sm " + (anomalous ? "text-rose-600 font-medium" : "")}>
                        {formatBal(rawVal)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot className="border-t-2 border-border bg-muted/50">
                <tr>
                  <td className="px-4 py-2.5 font-semibold text-[11px] uppercase tracking-wide text-muted-foreground">
                    Total
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums font-bold text-foreground">
                    {formatBal(total)}
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
function SubgroupBlock({ group, onOpen, activeId, collapsed, toggleCollapsed, unit, sideType }) {
  const expanded = !collapsed[group.id];
  const isGold = unit === "gold";
  const visibleAccounts = (group.accounts || []).filter(
    (a) => Number(a.balance || 0) !== 0
  );
  if (visibleAccounts.length === 0 && Number(group.total || 0) === 0) return null;

  return (
    <>
      <tr
        className="bg-muted/40 border-t border-border cursor-pointer hover:bg-muted/60 transition-colors"
        onClick={() => toggleCollapsed(group.id)}
      >
        <td className="px-4 py-2 text-sm font-semibold flex items-center gap-1.5">
          {expanded
            ? <ChevronDown className="size-3.5 text-muted-foreground" aria-hidden="true" />
            : <ChevronRight className="size-3.5 text-muted-foreground" aria-hidden="true" />}
          {group.name}
        </td>
        <td className="px-4 py-2 text-right tabular-nums text-sm font-semibold">
          {isGold ? fmtGrams(group.gold_grams) : fmt(group.total)}
        </td>
      </tr>
      {expanded && visibleAccounts.map((acc) => {
        const isSpecial = acc.id === "net_profit" || acc.id === "closing_stock";
        const isActive = activeId === acc.id;
        const { text: balText, anomalous } = isGold
          ? bsGoldDisplay(acc.gold_grams, sideType)
          : bsBalDisplay(acc.balance, sideType);
        return (
          <tr
            key={acc.id}
            onClick={() => !isSpecial && onOpen(acc.id, acc.name, sideType)}
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
            <td className={"px-4 py-1.5 text-right tabular-nums text-sm " + (anomalous ? "text-rose-600 font-medium" : "text-muted-foreground")}>
              {balText}
            </td>
          </tr>
        );
      })}
    </>
  );
}

/* ── Side panel (Assets or Liabilities) ───────────────────────────────────── */
function SidePanel({ title, icon: Icon, side, totalLabel, onOpen, activeId, collapsed, toggleCollapsed, unit, sideType }) {
  const isGold = unit === "gold";
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
            <SubgroupBlock
              key={g.id}
              group={g}
              onOpen={onOpen}
              activeId={activeId}
              collapsed={collapsed}
              toggleCollapsed={toggleCollapsed}
              unit={unit}
              sideType={sideType}
            />
          ))}
        </tbody>
        <tfoot>
          <tr className="border-t-2 border-border bg-muted/60">
            <td className="px-4 py-2.5 font-semibold text-sm">{totalLabel}</td>
            <td className="px-4 py-2.5 text-right tabular-nums font-bold text-sm">
              {isGold ? fmtGrams(side?.gold_grams) : fmt(side?.total)}
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
  const [unit, setUnit]         = useState("inr");
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [scope, setScope]             = useState("all");
  const [selectedRetailIds, setSelectedRetailIds] = useState([]);
  const [modal, setModal]       = useState(null);
  const [breakdownOpen, setBreakdownOpen] = useState(false);
  const [activeId, setActiveId] = useState(null);
  const [companyName, setCompanyName] = useState("");
  const [collapsed, setCollapsed] = useState({});

  const toggleCollapsed = useCallback(
    (id) => setCollapsed((p) => ({ ...p, [id]: !p[id] })),
    []
  );

  const allGroupIds = useMemo(() => {
    const ids = [];
    for (const g of data?.assets?.groups || []) ids.push(g.id);
    for (const g of data?.liabilities?.groups || []) ids.push(g.id);
    return ids;
  }, [data]);

  const anyCollapsed = allGroupIds.some((id) => collapsed[id]);
  const toggleAll = () =>
    anyCollapsed
      ? setCollapsed({})
      : setCollapsed(Object.fromEntries(allGroupIds.map((id) => [id, true])));

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
      const params = new URLSearchParams({ end_date: endDate, unit });
      applyRetailScopeParams(params, scope, selectedRetailIds);
      const res = await apiClient.get(`/accounting/api/bal-sheet?${params}`);
      setData(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load Balance Sheet data.");
    }
    setLoading(false);
  };

  useEffect(() => { fetchReport(); /* eslint-disable-next-line */ }, []);

  const openGroup = useCallback((id, name, sideType) => {
    if (activeId === id) {
      setModal(null);
      setActiveId(null);
    } else {
      setModal({ id, name, sideType });
      setActiveId(id);
    }
  }, [activeId]);

  const netWorth = Number(data?.net_worth ?? 0);
  const isBalanced = netWorth === 0;

  const assetsTotal = Number(data?.assets?.total || 0);
  const liabilitiesTotal = Math.abs(Number(data?.liabilities?.total || 0));

  // Ratios derived from the balance sheet tree.
  // Equity subgroups come from the "Capital Account" root which the backend
  // merges into liabilities.groups (see BalanceSheetAPIView).
  const EQUITY_GROUP_NAMES = new Set([
    "Owner's Capital",
    "Reserves & Surplus",
    "Capital Account",
  ]);
  // Only formal borrowings count as debt. Trade payables, duties, etc.
  // sit in Current Liabilities and are not "debt" for D/E purposes.
  const DEBT_GROUP_NAMES = new Set(["Loans (Liability)"]);
  const ratios = useMemo(() => {
    const findGroupTotal = (groups, name) => {
      const g = (groups || []).find((x) => x.name === name);
      return g ? Math.abs(Number(g.total || 0)) : 0;
    };
    const findAccount = (groups, accId) => {
      for (const g of groups || []) {
        for (const a of g.accounts || []) if (a.id === accId) return a;
      }
      return null;
    };
    const currentAssets = findGroupTotal(data?.assets?.groups, "Current Assets");
    const currentLiab   = findGroupTotal(data?.liabilities?.groups, "Current Liabilities");

    const equity = (data?.liabilities?.groups || [])
      .filter((g) => EQUITY_GROUP_NAMES.has(g.name))
      .reduce((s, g) => s + Math.abs(Number(g.total || 0)), 0);
    const debt = (data?.liabilities?.groups || [])
      .filter((g) => DEBT_GROUP_NAMES.has(g.name))
      .reduce((s, g) => s + Math.abs(Number(g.total || 0)), 0);

    // Net profit is embedded as a synthetic "net_profit" account inside
    // Reserves & Surplus on the liabilities side. Liabilities are stored
    // Dr−Cr (credit-normal = negative), so negate for a signed profit.
    const npAcc = findAccount(data?.liabilities?.groups, "net_profit");
    const netProfit = npAcc ? -Number(npAcc.balance || 0) : 0;

    const safeDiv = (n, d) => (d > 0 ? n / d : null);
    return {
      currentRatio: safeDiv(currentAssets, currentLiab),
      workingCapital: currentAssets - currentLiab,
      debtToEquity: safeDiv(debt, equity),
      roa: assetsTotal > 0 ? (netProfit / assetsTotal) * 100 : null,
      netProfit,
      equity,
      debt,
      currentAssets,
      currentLiab,
    };
  }, [data, assetsTotal]);

  const fmtRatio = (v, suffix = "") =>
    v == null ? "—" : `${v.toFixed(2)}${suffix}`;

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
        <div className="flex flex-col gap-1">
          <Label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            Unit
          </Label>
          <div className="inline-flex h-9 rounded-md border border-border overflow-hidden bg-background">
            <button
              type="button"
              onClick={() => setUnit("inr")}
              className={`px-3 text-xs font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer ${
                unit === "inr" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
              }`}
              aria-pressed={unit === "inr"}
            >
              <IndianRupee className="size-3.5" aria-hidden="true" /> Rupees
            </button>
            <button
              type="button"
              onClick={() => setUnit("gold")}
              className={`px-3 text-xs font-semibold inline-flex items-center gap-1.5 transition-colors cursor-pointer ${
                unit === "gold" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent"
              }`}
              aria-pressed={unit === "gold"}
            >
              <Coins className="size-3.5" aria-hidden="true" /> Fine Gold (g)
            </button>
          </div>
        </div>
        <Button size="sm" onClick={fetchReport} disabled={loading} className="h-9 cursor-pointer">
          {loading ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : "Show Report"}
        </Button>
        <div className="flex items-center gap-2 ml-auto">
          <Button
            size="sm"
            variant="outline"
            onClick={toggleAll}
            disabled={!data}
            className="h-9 cursor-pointer"
          >
            {anyCollapsed ? (
              <ChevronsUpDown className="size-4 mr-1.5" aria-hidden="true" />
            ) : (
              <ChevronsDownUp className="size-4 mr-1.5" aria-hidden="true" />
            )}
            {anyCollapsed ? "Expand All" : "Collapse All"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handlePrint}
            disabled={!data}
            aria-label="Print balance sheet"
            className="h-9 cursor-pointer"
          >
            <Printer className="size-4 mr-1.5" aria-hidden="true" /> Print
          </Button>
        </div>
      </div>

      {error && (
        <p className="text-sm text-destructive border border-destructive/40 bg-destructive/5 rounded-md px-3 py-2">
          {error}
        </p>
      )}

      {/* ── Financial ratio tiles (derived from the balance sheet) ────────── */}
      {data && !loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Current Ratio — liquidity */}
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Droplets className="size-3.5" aria-hidden="true" /> Current Ratio
            </div>
            <p className={`mt-1.5 text-xl font-semibold tabular-nums ${
              ratios.currentRatio == null ? "" :
              ratios.currentRatio >= 1.5 ? "text-emerald-600 dark:text-emerald-400" :
              ratios.currentRatio >= 1   ? "text-amber-600 dark:text-amber-400"   :
              "text-rose-600 dark:text-rose-400"
            }`}>
              {fmtRatio(ratios.currentRatio, "×")}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">Current Assets ÷ Current Liabilities</p>
          </div>

          {/* Working Capital */}
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Wallet className="size-3.5" aria-hidden="true" /> Working Capital
            </div>
            <p className={`mt-1.5 text-xl font-semibold tabular-nums ${
              ratios.workingCapital >= 0 ? "text-emerald-600 dark:text-emerald-400"
                                         : "text-rose-600 dark:text-rose-400"
            }`}>
              ₹ {fmt(Math.abs(ratios.workingCapital))}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">₹ {fmtCompact(Math.abs(ratios.workingCapital))} · CA − CL</p>
          </div>

          {/* Debt-to-Equity — leverage */}
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <Scale className="size-3.5" aria-hidden="true" /> Debt-to-Equity
            </div>
            <p className={`mt-1.5 text-xl font-semibold tabular-nums ${
              ratios.debtToEquity == null ? "" :
              ratios.debtToEquity <= 1 ? "text-emerald-600 dark:text-emerald-400" :
              ratios.debtToEquity <= 2 ? "text-amber-600 dark:text-amber-400"   :
              "text-rose-600 dark:text-rose-400"
            }`}>
              {fmtRatio(ratios.debtToEquity, "×")}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">Debt ÷ Equity</p>
          </div>

          {/* Return on Assets — profitability */}
          <div className="rounded-lg border border-border bg-card p-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              <TrendingUp className="size-3.5" aria-hidden="true" /> Return on Assets
            </div>
            <p className={`mt-1.5 text-xl font-semibold tabular-nums ${
              ratios.roa == null ? "" :
              ratios.roa >= 0 ? "text-emerald-600 dark:text-emerald-400"
                              : "text-rose-600 dark:text-rose-400"
            }`}>
              {ratios.roa == null ? "—" : `${ratios.roa.toFixed(2)}%`}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">Net {ratios.netProfit >= 0 ? "Profit" : "Loss"} ÷ Total Assets</p>
          </div>
        </div>
      )}

      {/* Balanced status strip */}
      {data && !loading && !isBalanced && (
        <p className="text-xs px-3 py-2 rounded-md border border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/10 dark:text-amber-300 flex items-center gap-1.5">
          <Scale className="size-3.5" aria-hidden="true" />
          Balance sheet is out of balance by {balLabel(netWorth)}.
        </p>
      )}

      {data && !loading && (
        <p className="text-[11px] text-muted-foreground -mt-1 print:hidden">
          Balance Sheet as on {asOnLabel}{scope === "all" ? " · Combined (all retails)" : selectedRetailIds.length > 1 ? ` · ${selectedRetailIds.length} retails` : ""}. Click any account to see its ledgers.
        </p>
      )}

      {data?.unit === "gold" && !loading && (
        data.fine_gold_rate ? (
          <div className="text-xs px-3 py-2 rounded-md border border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/40 dark:bg-amber-900/10 dark:text-amber-300 flex items-center gap-2 print:hidden">
            <Coins className="size-3.5 flex-shrink-0" aria-hidden="true" />
            <span className="flex-1">
              Showing balances in fine gold (24K). Conversion rate: <strong>₹ {fmt(data.fine_gold_rate)} / g</strong> — derived from gold flows since FY start.
            </span>
            <button
              type="button"
              onClick={() => setBreakdownOpen(true)}
              className="px-2 py-1 text-[11px] font-semibold rounded border border-amber-400/60 bg-amber-100 hover:bg-amber-200 dark:bg-amber-900/30 dark:hover:bg-amber-900/50 text-amber-900 dark:text-amber-200 cursor-pointer transition-colors"
            >
              How was this calculated?
            </button>
          </div>
        ) : (
          <p className="text-xs px-3 py-2 rounded-md border border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-900/40 dark:bg-amber-900/10 dark:text-amber-300 flex items-center gap-1.5 print:hidden">
            <Coins className="size-3.5" aria-hidden="true" />
            No gold flows in this fiscal year — fine-gold rate cannot be derived.
          </p>
        )
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
            collapsed={collapsed}
            toggleCollapsed={toggleCollapsed}
            unit={data.unit}
            sideType="assets"
          />
          <SidePanel
            title="Liabilities & Equity"
            icon={Landmark}
            side={data.liabilities}
            totalLabel="Total Liabilities & Equity"
            onOpen={openGroup}
            activeId={activeId}
            collapsed={collapsed}
            toggleCollapsed={toggleCollapsed}
            unit={data.unit}
            sideType="liabilities"
          />
        </div>
      )}

      {breakdownOpen && (
        <FineGoldBreakdownModal
          endDate={endDate}
          scope={scope}
          selectedRetailIds={selectedRetailIds}
          onClose={() => setBreakdownOpen(false)}
        />
      )}

      {modal && (
        <LedgerModal
          groupId={modal.id}
          groupName={modal.name}
          endDate={endDate}
          unit={data?.unit || "inr"}
          sideType={modal.sideType}
          onClose={() => { setModal(null); setActiveId(null); }}
        />
      )}
    </div>
  );
}
