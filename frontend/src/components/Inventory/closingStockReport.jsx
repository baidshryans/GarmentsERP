import { useState, useRef, useMemo, useCallback, useEffect } from "react";
import { formatNumber, formatDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { getClosingStockValuation, getClosingStockTxns, fetchCompanies, fetchRetails } from "../../services/apiService";
import { Package, Printer, TrendingUp, Weight, Gem, BarChart3, X, Loader2, Store, ChevronDown, Check } from "lucide-react";
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuCheckboxItem, DropdownMenuSeparator, DropdownMenuLabel,
} from "@/components/ui/dropdown-menu";
import { printReport } from "@/lib/printReport";

const today = new Date().toISOString().split("T")[0];

const CATEGORY_TABS = [
  { key: "all", label: "All" },
  { key: "R",   label: "Raw" },
  { key: "S",   label: "Stone" },
  { key: "F",   label: "Finished" },
  { key: "C",   label: "Coin" },
];

const TXN_LABELS = {
  purchases:        "Purchases",
  purchase_returns: "Purchase Returns",
  sales:            "Sales",
  sale_returns:     "Sale Returns",
  refinery_issues:  "Refinery Issues",
  refinery_receives:"Refinery Receives",
};

const fmt   = (v) => formatNumber(v, { decimals: 2 });
const fmtWt = (v) => formatNumber(v, { decimals: 3 });
const fmtK  = (v) => { const n = Number(v); if (n >= 1e7) return (n/1e7).toFixed(2)+"Cr"; if (n >= 1e5) return (n/1e5).toFixed(2)+"L"; return fmt(n); };
const isNonZero = (v) => Math.abs(Number(v)) > 0.001;
const fmtDate = (d) => d ? formatDate(d + "T00:00:00", "short") : "—";

/* ─── KPI Card ──────────────────────────────────────────────────────────── */
function KpiCard({ icon: Icon, label, value, sub }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4 shadow-sm min-w-[130px] flex-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <Icon className="size-4 text-muted-foreground/50" />
      </div>
      <p className="text-xl font-bold tabular-nums text-foreground leading-none">{value}</p>
      {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

/* ─── Column group headers ──────────────────────────────────────────────── */
const ColGroup = ({ label, span, className = "" }) => (
  <th colSpan={span} className={`px-2 py-2 text-center text-[10px] uppercase tracking-widest font-bold border border-border bg-muted/60 text-muted-foreground ${className}`}>
    {label}
  </th>
);
const ColGroupPrimary = ({ label, span }) => (
  <th colSpan={span} className="px-2 py-2 text-center text-[10px] uppercase tracking-widest font-bold border border-border bg-primary/8 text-primary">
    {label}
  </th>
);
const SubHead = ({ label, className = "" }) => (
  <th className={`px-2 py-1.5 text-right text-[10px] uppercase tracking-wider font-semibold border border-border bg-muted/30 text-muted-foreground ${className}`}>
    {label}
  </th>
);

/* ─── Plain data cell ───────────────────────────────────────────────────── */
const Td = ({ children, className = "" }) => (
  <td className={`px-2 py-1.5 text-right text-xs border border-border/50 tabular-nums ${className}`}>
    {children}
  </td>
);

/* ─── Clickable data cell ───────────────────────────────────────────────── */
const ClickTd = ({ children, className = "", onClick, active = false }) => (
  <td
    onClick={onClick}
    className={`px-2 py-1.5 text-right text-xs border border-border/50 tabular-nums
      cursor-pointer select-none transition-colors duration-100
      ${active ? "bg-primary/15 text-primary font-semibold" : "hover:bg-primary/8 hover:text-primary"}
      ${className}`}
  >
    {children}
  </td>
);

const Dash = () => <span className="text-muted-foreground/25">—</span>;

/* ─── Loading skeleton ──────────────────────────────────────────────────── */
function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-xl border p-4 flex flex-col gap-2">
            <div className="flex justify-between"><Skeleton className="h-3 w-20" /><Skeleton className="size-4 rounded" /></div>
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-8 w-20 rounded-full" />)}
      </div>
      <div className="rounded-xl border overflow-hidden">
        {[...Array(7)].map((_, i) => <Skeleton key={i} className="h-9 w-full rounded-none border-t" />)}
      </div>
    </div>
  );
}

/* ─── Drill-down Transaction Modal ─────────────────────────────────────── */
function TxnModal({ drill, asOnDate, onClose }) {
  const [vouchers, setVouchers]   = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState("");

  useEffect(() => {
    if (!drill) return;
    setLoading(true);
    setError("");
    setVouchers(null);
    getClosingStockTxns({
      item_id: drill.item_id, txn_type: drill.txn_type, to_date: asOnDate,
      retail_ids: scope === "selected" ? selectedRetailIds : undefined,
    })
      .then((res) => {
        if (res.success) setVouchers(res.data.vouchers);
        else setError("Failed to load transactions.");
      })
      .finally(() => setLoading(false));
  }, [drill, asOnDate]);

  const totals = useMemo(() => {
    if (!vouchers) return null;
    return vouchers.reduce(
      (acc, v) => ({ gw: acc.gw + v.gw, ct: acc.ct + v.ct, amount: acc.amount + v.amount }),
      { gw: 0, ct: 0, amount: 0 }
    );
  }, [vouchers]);

  const showAmt   = drill?.txn_type !== "refinery_issues" && drill?.txn_type !== "refinery_receives";
  const showCt    = true;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-card rounded-xl shadow-2xl w-[96vw] max-w-3xl max-h-[85vh] flex flex-col border border-border"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-5 py-4 border-b border-border">
          <div>
            <p className="font-semibold text-foreground text-sm">{drill?.item_name}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              {TXN_LABELS[drill?.txn_type]} · up to {fmtDate(asOnDate)}
            </p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-accent rounded-lg transition-colors">
            <X className="size-4 text-muted-foreground" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-auto flex-1">
          {loading && (
            <div className="flex items-center justify-center py-16 gap-2 text-muted-foreground text-sm">
              <Loader2 className="size-4 animate-spin" /> Loading…
            </div>
          )}
          {error && (
            <p className="text-center py-16 text-destructive text-sm">{error}</p>
          )}
          {!loading && vouchers && vouchers.length === 0 && (
            <p className="text-center py-16 text-muted-foreground text-sm">No transactions found.</p>
          )}
          {!loading && vouchers && vouchers.length > 0 && (
            <table className="w-full text-xs border-collapse">
              <thead className="bg-muted/50 sticky top-0">
                <tr>
                  <th className="px-3 py-2.5 text-left text-[10px] uppercase tracking-wide font-semibold text-muted-foreground border-b border-border">Date</th>
                  <th className="px-3 py-2.5 text-left text-[10px] uppercase tracking-wide font-semibold text-muted-foreground border-b border-border">Voucher No</th>
                  <th className="px-3 py-2.5 text-left text-[10px] uppercase tracking-wide font-semibold text-muted-foreground border-b border-border">Party</th>
                  <th className="px-3 py-2.5 text-right text-[10px] uppercase tracking-wide font-semibold text-muted-foreground border-b border-border">GW (g)</th>
                  {showCt && <th className="px-3 py-2.5 text-right text-[10px] uppercase tracking-wide font-semibold text-muted-foreground border-b border-border">Ct</th>}
                  {showAmt && <th className="px-3 py-2.5 text-right text-[10px] uppercase tracking-wide font-semibold text-muted-foreground border-b border-border">Amount (₹)</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {vouchers.map((v, i) => (
                  <tr key={i} className="hover:bg-accent/30 transition-colors">
                    <td className="px-3 py-2 text-muted-foreground whitespace-nowrap">{fmtDate(v.date)}</td>
                    <td className="px-3 py-2 font-medium text-foreground">{v.voucher_no}</td>
                    <td className="px-3 py-2 text-muted-foreground max-w-[180px] truncate">{v.party || "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{isNonZero(v.gw) ? fmtWt(v.gw) : <Dash />}</td>
                    {showCt  && <td className="px-3 py-2 text-right tabular-nums">{isNonZero(v.ct) ? fmtWt(v.ct) : <Dash />}</td>}
                    {showAmt && <td className="px-3 py-2 text-right tabular-nums font-medium">{isNonZero(v.amount) ? fmt(v.amount) : <Dash />}</td>}
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-border bg-muted/50">
                <tr>
                  <td colSpan={3} className="px-3 py-2.5 text-right text-[10px] font-bold uppercase tracking-wide text-muted-foreground">
                    Total ({vouchers.length} rows)
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums font-bold text-foreground">{fmtWt(totals.gw)}</td>
                  {showCt  && <td className="px-3 py-2.5 text-right tabular-nums font-bold text-foreground">{fmtWt(totals.ct)}</td>}
                  {showAmt && <td className="px-3 py-2.5 text-right tabular-nums font-bold text-primary">₹{fmt(totals.amount)}</td>}
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Main component ────────────────────────────────────────────────────── */
export default function ClosingStockTable() {
  const [asOnDate, setAsOnDate] = useState(today);
  const tableRef = useRef(null);
  const [data, setData]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");
  const [category, setCategory] = useState("all");
  const [drill, setDrill]       = useState(null); // { item_id, item_name, txn_type }
  const [companyName, setCompanyName] = useState("");
  const [retails, setRetails] = useState([]);
  const [scope, setScope] = useState("all"); // 'all' | 'selected'
  const [selectedRetailIds, setSelectedRetailIds] = useState([]);

  const user = JSON.parse(sessionStorage.getItem("user") || "{}");
  const canViewCombined = user.is_superuser || ["admin", "super admin"].includes((user.role || "").toLowerCase());

  useEffect(() => {
    fetchCompanies().then((res) => {
      if (res.success) {
        const results = res.data?.results || res.data || [];
        if (results.length > 0) setCompanyName(results[0].company_name || "");
      }
    });
    fetchRetails().then((res) => {
      if (res.success) {
        const results = res.data?.results || res.data || [];
        setRetails(results);
      }
    });
  }, []);

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    setData(null);
    const retail_ids = scope === "selected" ? selectedRetailIds : undefined;
    if (scope === "selected" && (!retail_ids || retail_ids.length === 0)) {
      setError("Select at least one retail, or choose 'All retails combined'.");
      setLoading(false);
      return;
    }
    const res = await getClosingStockValuation({ to_date: asOnDate, retail_ids });
    if (res.success) setData(res.data);
    else setError(typeof res.error === "string" ? res.error : res.error?.error || "Failed to load report.");
    setLoading(false);
  };

  const openDrill = useCallback((item_id, item_name, txn_type) => {
    setDrill({ item_id, item_name, txn_type });
  }, []);

  const filteredDetails = useMemo(() => {
    if (!data?.details) return [];
    if (category === "all") return data.details;
    if (category === "F") return data.details.filter((d) => !["R", "S", "M", "C"].includes(d.item_type));
    return data.details.filter((d) => d.item_type === category);
  }, [data, category]);

  const categoryCounts = useMemo(() => {
    if (!data?.details) return {};
    const counts = {};
    for (const d of data.details) {
      const cat = ["R", "S", "C"].includes(d.item_type) ? d.item_type : "F";
      if (!counts[cat]) counts[cat] = { count: 0, closing_amt: 0 };
      counts[cat].count++;
      counts[cat].closing_amt += d.closing_amt;
    }
    return counts;
  }, [data]);

  const totals = filteredDetails?.reduce(
    (acc, d) => {
      acc.opening_gw  += d.opening_gw;   acc.opening_ct  += d.opening_ct;   acc.opening_amt  += d.opening_amt;
      acc.purchase_gw += d.purchase_gw;  acc.purchase_ct += d.purchase_ct;  acc.purchase_amt += d.purchase_amt;
      acc.purc_ret_gw += d.purc_ret_gw;  acc.purc_ret_ct += d.purc_ret_ct;  acc.purc_ret_amt += d.purc_ret_amt;
      acc.sales_gw    += d.sales_gw;     acc.sales_ct    += d.sales_ct;     acc.sales_amt    += d.sales_amt;
      acc.sale_ret_gw += d.sale_ret_gw;  acc.sale_ret_ct += d.sale_ret_ct;  acc.sale_ret_amt += d.sale_ret_amt;
      acc.ref_iss_gw  += d.ref_iss_gw;   acc.ref_iss_ct  += d.ref_iss_ct;
      acc.ref_rec_gw  += d.ref_rec_gw;   acc.ref_rec_ct  += d.ref_rec_ct;
      acc.closing_gw  += d.closing_gw;   acc.closing_ct  += d.closing_ct;   acc.closing_amt  += d.closing_amt;
      return acc;
    },
    { opening_gw:0,opening_ct:0,opening_amt:0,purchase_gw:0,purchase_ct:0,purchase_amt:0,purc_ret_gw:0,purc_ret_ct:0,purc_ret_amt:0,sales_gw:0,sales_ct:0,sales_amt:0,sale_ret_gw:0,sale_ret_ct:0,sale_ret_amt:0,ref_iss_gw:0,ref_iss_ct:0,ref_rec_gw:0,ref_rec_ct:0,closing_gw:0,closing_ct:0,closing_amt:0 }
  );

  const formattedDate = asOnDate
    ? formatDate(asOnDate + "T00:00:00", "short")
    : "";

  const handlePrint = () => {
    if (!tableRef.current || !data) return;
    // Light vertical dividers between column groups (Opening | Purchases | Purc Ret | Sales |
    // Sale Ret | Refinery | Wtd Avg | Closing). nth-child indices reference the 24-col data layout.
    const groupBorderCss = `
      thead tr:nth-child(2) th:nth-child(2),
      thead tr:nth-child(2) th:nth-child(5),
      thead tr:nth-child(2) th:nth-child(8),
      thead tr:nth-child(2) th:nth-child(11),
      thead tr:nth-child(2) th:nth-child(14),
      thead tr:nth-child(2) th:nth-child(17),
      thead tr:nth-child(2) th:nth-child(21),
      thead tr:nth-child(2) th:nth-child(22),
      tbody tr td:nth-child(2),
      tbody tr td:nth-child(5),
      tbody tr td:nth-child(8),
      tbody tr td:nth-child(11),
      tbody tr td:nth-child(14),
      tbody tr td:nth-child(17),
      tbody tr td:nth-child(21),
      tbody tr td:nth-child(22),
      tfoot tr td:nth-child(2),
      tfoot tr td:nth-child(5),
      tfoot tr td:nth-child(8),
      tfoot tr td:nth-child(11),
      tfoot tr td:nth-child(14),
      tfoot tr td:nth-child(17),
      tfoot tr td:nth-child(21),
      tfoot tr td:nth-child(22) {
        border-left: 0.75px solid #cbd5e1 !important;
      }
      tbody tr td:last-child,
      tfoot tr td:last-child,
      thead tr:nth-child(2) th:last-child {
        border-right: 0.75px solid #cbd5e1 !important;
      }
      tbody tr td:first-child,
      tfoot tr td:first-child,
      thead tr:nth-child(2) th:first-child {
        border-left: 0.75px solid #cbd5e1 !important;
      }
    `;
    const [y, m, d] = (asOnDate || "").split("-");
    const ddmmyyyy  = y && m && d ? `${d}-${m}-${y}` : asOnDate;
    printReport({
      title: "Closing Stock Valuation",
      subtitle: `As on ${ddmmyyyy}`,
      html: tableRef.current.outerHTML,
      landscape: true,
      extraCss: groupBorderCss,
      company: companyName,
    });
  };

  return (
    <div className="flex flex-col gap-5">

      {/* ── Filter bar ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-3 rounded-xl border border-border bg-muted/20">
        <div className="flex flex-col gap-1.5">
          <Label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">As on</Label>
          <Input
            type="date"
            value={asOnDate}
            onChange={(e) => setAsOnDate(e.target.value)}
            className="h-9 w-40"
          />
        </div>

        {canViewCombined && (
        <div className="flex flex-col gap-1.5 min-w-[16rem]">
          <Label className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Retails</Label>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-9 w-full justify-between gap-2 font-normal px-3 cursor-pointer"
              >
                <span className="flex items-center gap-2 truncate">
                  <Store className="size-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
                  <span className="truncate">
                    {scope === "all"
                      ? "All retails (combined)"
                      : selectedRetailIds.length === 0
                        ? <span className="text-muted-foreground">Select retails…</span>
                        : selectedRetailIds.length === 1
                          ? (retails.find((r) => r.id === selectedRetailIds[0])?.retail_name || `#${selectedRetailIds[0]}`)
                          : `${selectedRetailIds.length} retails selected`}
                  </span>
                </span>
                <ChevronDown className="size-3.5 text-muted-foreground shrink-0" aria-hidden="true" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-64">
              <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Scope
              </DropdownMenuLabel>
              <DropdownMenuCheckboxItem
                checked={scope === "all"}
                onCheckedChange={() => { setScope("all"); setSelectedRetailIds([]); }}
                onSelect={(e) => e.preventDefault()}
              >
                All retails (combined)
              </DropdownMenuCheckboxItem>
              {retails.length > 0 && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuLabel className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                    Individual retails
                  </DropdownMenuLabel>
                  {retails.map((r) => (
                    <DropdownMenuCheckboxItem
                      key={r.id}
                      checked={scope === "selected" && selectedRetailIds.includes(r.id)}
                      onCheckedChange={(checked) => {
                        setScope("selected");
                        setSelectedRetailIds((prev) =>
                          checked ? [...new Set([...prev, r.id])] : prev.filter((x) => x !== r.id),
                        );
                      }}
                      onSelect={(e) => e.preventDefault()}
                    >
                      {r.retail_name || r.retail_code || `#${r.id}`}
                    </DropdownMenuCheckboxItem>
                  ))}
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        )}

        <div className="flex items-end gap-2">
          <Button
            size="sm"
            onClick={fetchReport}
            disabled={loading}
            className="h-9 px-4 gap-1.5 cursor-pointer"
            aria-label="Show closing stock report"
          >
            {loading ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <BarChart3 className="size-3.5" aria-hidden="true" />}
            {loading ? "Loading…" : "Show Report"}
          </Button>
        </div>
        {data && (
          <Button
            size="sm"
            variant="outline"
            onClick={handlePrint}
            className="h-9 gap-1.5 cursor-pointer ml-auto"
            aria-label="Print report"
          >
            <Printer className="size-3.5" aria-hidden="true" /> Print
          </Button>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          <span className="font-semibold">Error:</span> {error}
        </div>
      )}

      {loading && <LoadingSkeleton />}

      {/* ── KPI summary cards ──────────────────────────────────────────── */}
      {data && !loading && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiCard icon={TrendingUp} label="Closing Value"  value={`₹${fmtK(totals.closing_amt)}`}  sub={`as on ${formattedDate}`} />
          <KpiCard icon={Weight}     label="Closing GW"     value={`${fmtWt(totals.closing_gw)} g`} sub={`Ct: ${fmtWt(totals.closing_ct)}`} />
          <KpiCard icon={Gem}        label="Total Items"    value={filteredDetails.length}            sub="unique SKUs in stock" />
          <KpiCard icon={Package}    label="Purchases"      value={`₹${fmtK(totals.purchase_amt)}`} sub={`GW: ${fmtWt(totals.purchase_gw)} g`} />
        </div>
      )}

      {/* ── Category tabs ──────────────────────────────────────────────── */}
      {data && !loading && (
        <div className="flex flex-wrap items-center gap-2">
          {CATEGORY_TABS.map((t) => {
            const isActive = category === t.key;
            const cnt = t.key !== "all" ? categoryCounts[t.key] : null;
            return (
              <button
                key={t.key}
                onClick={() => setCategory(t.key)}
                className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border text-xs font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30
                  ${isActive
                    ? "bg-primary text-primary-foreground border-primary shadow-sm"
                    : "bg-background text-muted-foreground border-border hover:border-primary/40 hover:text-foreground"
                  }`}
              >
                {t.label}
                {cnt && (
                  <span className={`inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold
                    ${isActive ? "bg-white/20 text-white" : "bg-muted text-muted-foreground"}`}>
                    {cnt.count}
                  </span>
                )}
              </button>
            );
          })}
          {category !== "all" && categoryCounts[category] && (
            <span className="ml-1 text-xs text-muted-foreground border-l border-border pl-3">
              ₹{fmt(categoryCounts[category].closing_amt)} closing
            </span>
          )}
        </div>
      )}

      {data && !loading && (
        <p className="text-[11px] text-muted-foreground -mt-3 print:hidden">
          Click any amount cell to drill into its vouchers.
        </p>
      )}

      {/* ── Data table ─────────────────────────────────────────────────── */}
      {data && !loading && (
        <div className="rounded-xl border border-border overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table ref={tableRef} className="w-full text-xs border-collapse">
              <thead className="sticky top-0 z-10">
                <tr>
                  <ColGroup label="Item"         span={1} className="text-left w-36" />
                  <ColGroup label="Opening"      span={3} />
                  <ColGroup label="Purchases"    span={3} />
                  <ColGroup label="Purc. Return" span={3} />
                  <ColGroup label="Sales"        span={3} />
                  <ColGroup label="Sale Return"  span={3} />
                  <ColGroup label="Refinery"     span={4} />
                  <ColGroup label="Wtd Avg"      span={1} />
                  <ColGroupPrimary label="Closing" span={3} />
                </tr>
                <tr>
                  <SubHead label="Name" className="text-left !font-bold w-36" />
                  <SubHead label="GW" /><SubHead label="Ct" /><SubHead label="Amt" />
                  <SubHead label="GW" /><SubHead label="Ct" /><SubHead label="Amt" />
                  <SubHead label="GW" /><SubHead label="Ct" /><SubHead label="Amt" />
                  <SubHead label="GW" /><SubHead label="Ct" /><SubHead label="Amt" />
                  <SubHead label="GW" /><SubHead label="Ct" /><SubHead label="Amt" />
                  <SubHead label="Iss GW" /><SubHead label="Iss Ct" /><SubHead label="Rec GW" /><SubHead label="Rec Ct" />
                  <SubHead label="Rate" />
                  <SubHead label="GW"  className="bg-primary/5 text-primary" />
                  <SubHead label="Ct"  className="bg-primary/5 text-primary" />
                  <SubHead label="Amt" className="bg-primary/5 text-primary !font-bold" />
                </tr>
              </thead>

              <tbody>
                {filteredDetails.length === 0 && (
                  <tr>
                    <td colSpan={24} className="text-center py-12 text-muted-foreground">
                      No stock data available for this date.
                    </td>
                  </tr>
                )}

                {filteredDetails.map((d, i) => {
                  const isActive = (txn) => drill?.item_id === d.item_id && drill?.txn_type === txn;
                  const click    = (txn) => () => openDrill(d.item_id, d.item_name, txn);
                  return (
                    <tr
                      key={d.item_id}
                      className={`border-t border-border/40 transition-colors hover:bg-muted/30 ${i % 2 === 1 ? "bg-muted/10" : ""}`}
                    >
                      {/* Item name */}
                      <td className="px-2 py-2 text-left border border-border/40 font-medium whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-muted text-muted-foreground">
                            {d.item_type}
                          </span>
                          <span>{d.item_name}</span>
                        </div>
                      </td>

                      {/* Opening — not drillable (opening stock from op_stk records, not vouchers) */}
                      <Td>{isNonZero(d.opening_gw)  ? fmtWt(d.opening_gw)  : <Dash/>}</Td>
                      <Td>{isNonZero(d.opening_ct)  ? fmtWt(d.opening_ct)  : <Dash/>}</Td>
                      <Td>{isNonZero(d.opening_amt) ? fmt(d.opening_amt)   : <Dash/>}</Td>

                      {/* Purchases */}
                      <ClickTd active={isActive("purchases")} onClick={click("purchases")}>{isNonZero(d.purchase_gw)  ? fmtWt(d.purchase_gw)  : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("purchases")} onClick={click("purchases")}>{isNonZero(d.purchase_ct)  ? fmtWt(d.purchase_ct)  : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("purchases")} onClick={click("purchases")}>{isNonZero(d.purchase_amt) ? fmt(d.purchase_amt)   : <Dash/>}</ClickTd>

                      {/* Purchase Returns */}
                      <ClickTd active={isActive("purchase_returns")} onClick={click("purchase_returns")}>{isNonZero(d.purc_ret_gw)  ? fmtWt(d.purc_ret_gw)  : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("purchase_returns")} onClick={click("purchase_returns")}>{isNonZero(d.purc_ret_ct)  ? fmtWt(d.purc_ret_ct)  : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("purchase_returns")} onClick={click("purchase_returns")}>{isNonZero(d.purc_ret_amt) ? fmt(d.purc_ret_amt)   : <Dash/>}</ClickTd>

                      {/* Sales */}
                      <ClickTd active={isActive("sales")} onClick={click("sales")}>{isNonZero(d.sales_gw)  ? fmtWt(d.sales_gw)  : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("sales")} onClick={click("sales")}>{isNonZero(d.sales_ct)  ? fmtWt(d.sales_ct)  : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("sales")} onClick={click("sales")}>{isNonZero(d.sales_amt) ? fmt(d.sales_amt)   : <Dash/>}</ClickTd>

                      {/* Sale Returns */}
                      <ClickTd active={isActive("sale_returns")} onClick={click("sale_returns")}>{isNonZero(d.sale_ret_gw)  ? fmtWt(d.sale_ret_gw)  : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("sale_returns")} onClick={click("sale_returns")}>{isNonZero(d.sale_ret_ct)  ? fmtWt(d.sale_ret_ct)  : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("sale_returns")} onClick={click("sale_returns")}>{isNonZero(d.sale_ret_amt) ? fmt(d.sale_ret_amt)   : <Dash/>}</ClickTd>

                      {/* Refinery */}
                      <ClickTd active={isActive("refinery_issues")}   onClick={click("refinery_issues")}>{isNonZero(d.ref_iss_gw) ? fmtWt(d.ref_iss_gw) : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("refinery_issues")}   onClick={click("refinery_issues")}>{isNonZero(d.ref_iss_ct) ? fmtWt(d.ref_iss_ct) : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("refinery_receives")} onClick={click("refinery_receives")}>{isNonZero(d.ref_rec_gw) ? fmtWt(d.ref_rec_gw) : <Dash/>}</ClickTd>
                      <ClickTd active={isActive("refinery_receives")} onClick={click("refinery_receives")}>{isNonZero(d.ref_rec_ct) ? fmtWt(d.ref_rec_ct) : <Dash/>}</ClickTd>

                      {/* Wtd Avg Rate */}
                      <Td className="font-mono text-muted-foreground">{fmtWt(d.weighted_avg_rate)}</Td>

                      {/* Closing — derived, not drillable */}
                      <Td className="bg-primary/5 font-medium">{isNonZero(d.closing_gw) ? fmtWt(d.closing_gw) : <Dash/>}</Td>
                      <Td className="bg-primary/5 font-medium">{isNonZero(d.closing_ct) ? fmtWt(d.closing_ct) : <Dash/>}</Td>
                      <Td className="bg-primary/5 font-bold text-primary">{fmt(d.closing_amt)}</Td>
                    </tr>
                  );
                })}
              </tbody>

              {filteredDetails.length > 0 && totals && (
                <tfoot>
                  <tr className="border-t-2 border-border bg-muted/50 font-semibold text-xs">
                    <td className="px-2 py-2.5 text-left border border-border font-bold uppercase text-xs tracking-wide">Total</td>

                    <Td className="font-semibold">{fmtWt(totals.opening_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.opening_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.opening_amt)}</Td>

                    <Td className="font-semibold">{fmtWt(totals.purchase_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.purchase_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.purchase_amt)}</Td>

                    <Td className="font-semibold">{fmtWt(totals.purc_ret_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.purc_ret_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.purc_ret_amt)}</Td>

                    <Td className="font-semibold">{fmtWt(totals.sales_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.sales_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.sales_amt)}</Td>

                    <Td className="font-semibold">{fmtWt(totals.sale_ret_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.sale_ret_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.sale_ret_amt)}</Td>

                    <Td className="font-semibold">{fmtWt(totals.ref_iss_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.ref_iss_ct)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.ref_rec_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.ref_rec_ct)}</Td>

                    <Td></Td>

                    <Td className="bg-primary/8 font-bold">{fmtWt(totals.closing_gw)}</Td>
                    <Td className="bg-primary/8 font-bold">{fmtWt(totals.closing_ct)}</Td>
                    <Td className="bg-primary/8 font-extrabold text-primary text-sm">₹{fmt(totals.closing_amt)}</Td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      )}

      {/* ── Empty state ─────────────────────────────────────────────────── */}
      {!loading && !error && !data && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="rounded-2xl bg-muted/40 border border-border p-6 mb-5">
            <Package className="size-9 text-muted-foreground/50" />
          </div>
          <h3 className="text-sm font-semibold text-foreground mb-1.5">Closing Stock Valuation</h3>
          <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
            Select a date and click <span className="font-medium text-foreground">Show Report</span> to view closing stock with category breakdowns.
          </p>
        </div>
      )}

      {/* ── Drill-down modal ─────────────────────────────────────────────── */}
      {drill && (
        <TxnModal drill={drill} asOnDate={asOnDate} onClose={() => setDrill(null)} />
      )}
    </div>
  );
}
