import { useState, useRef, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { getClosingStockValuation } from "../../services/apiService";
import { Package, Printer, TrendingUp, Weight, Gem, BarChart3 } from "lucide-react";
import { printReport } from "@/lib/printReport";

const today = new Date().toISOString().split("T")[0];

const CATEGORY_TABS = [
  { key: "all", label: "All" },
  { key: "R",   label: "Raw" },
  { key: "S",   label: "Stone" },
  { key: "F",   label: "Finished" },
  { key: "C",   label: "Coin" },
];

const fmt   = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtWt = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const fmtK  = (v) => { const n = Number(v); if (n >= 1e7) return (n/1e7).toFixed(2)+"Cr"; if (n >= 1e5) return (n/1e5).toFixed(2)+"L"; return fmt(n); };
const isNonZero = (v) => Math.abs(Number(v)) > 0.001;

/* ─── KPI Card ──────────────────────────────────────────────────────────── */
function KpiCard({ icon: Icon, label, value, sub }) {
  return (
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4 shadow-sm min-w-[130px] flex-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <Icon className="w-4 h-4 text-muted-foreground/50" />
      </div>
      <p className="text-xl font-bold tabular-nums text-foreground leading-none">{value}</p>
      {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

/* ─── column group header ───────────────────────────────────────────────── */
const ColGroup = ({ label, span, className = "" }) => (
  <th colSpan={span} className={`px-2 py-2 text-center text-[10px] uppercase tracking-widest font-bold border border-border bg-muted/60 text-muted-foreground ${className}`}>
    {label}
  </th>
);

/* ─── closing column group header (uses primary tint) ──────────────────── */
const ColGroupPrimary = ({ label, span }) => (
  <th colSpan={span} className="px-2 py-2 text-center text-[10px] uppercase tracking-widest font-bold border border-border bg-primary/8 text-primary">
    {label}
  </th>
);

/* ─── sub-header cell ───────────────────────────────────────────────────── */
const SubHead = ({ label, className = "" }) => (
  <th className={`px-2 py-1.5 text-right text-[10px] uppercase tracking-wider font-semibold border border-border bg-muted/30 text-muted-foreground ${className}`}>
    {label}
  </th>
);

/* ─── data cell ─────────────────────────────────────────────────────────── */
const Td = ({ children, className = "" }) => (
  <td className={`px-2 py-1.5 text-right text-xs border border-border/50 tabular-nums ${className}`}>
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
            <div className="flex justify-between"><Skeleton className="h-3 w-20" /><Skeleton className="h-4 w-4 rounded" /></div>
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

export default function ClosingStockTable() {
  const [asOnDate, setAsOnDate] = useState(today);
  const tableRef = useRef(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [category, setCategory] = useState("all");

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    setData(null);
    const res = await getClosingStockValuation({ to_date: asOnDate });
    if (res.success) setData(res.data);
    else setError(typeof res.error === "string" ? res.error : res.error?.error || "Failed to load report.");
    setLoading(false);
  };

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
    ? new Date(asOnDate + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })
    : "";

  const handlePrint = () => {
    if (!tableRef.current || !data) return;
    printReport({ title: "Closing Stock Valuation", subtitle: `As on ${asOnDate}`, html: tableRef.current.outerHTML, landscape: true });
  };

  return (
    <div className="flex flex-col gap-5">

      {/* ── Filter bar ─────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-4 rounded-xl border border-border bg-muted/20">
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs font-medium text-muted-foreground">As on Date</Label>
          <Input type="date" value={asOnDate} onChange={(e) => setAsOnDate(e.target.value)} className="h-9 w-44" />
        </div>

        <Button size="sm" onClick={fetchReport} disabled={loading} className="h-9 px-5">
          {loading ? (
            <span className="flex items-center gap-2">
              <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Loading…
            </span>
          ) : (
            <span className="flex items-center gap-1.5"><BarChart3 className="w-3.5 h-3.5" /> Show Report</span>
          )}
        </Button>

        {data && (
          <Button size="sm" variant="outline" onClick={handlePrint} className="h-9 ml-auto gap-1.5">
            <Printer className="w-4 h-4" /> Print
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

      {/* ── Data table ─────────────────────────────────────────────────── */}
      {data && !loading && (
        <div className="rounded-xl border border-border overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table ref={tableRef} className="w-full text-xs border-collapse">
              <thead className="sticky top-0 z-10">
                {/* Level 1 — group headers */}
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
                {/* Level 2 — sub-headers */}
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

                {filteredDetails.map((d, i) => (
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

                    {/* Opening */}
                    <Td>{isNonZero(d.opening_gw)  ? fmtWt(d.opening_gw)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.opening_ct)  ? fmtWt(d.opening_ct)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.opening_amt) ? fmt(d.opening_amt)   : <Dash/>}</Td>

                    {/* Purchases */}
                    <Td>{isNonZero(d.purchase_gw)  ? fmtWt(d.purchase_gw)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.purchase_ct)  ? fmtWt(d.purchase_ct)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.purchase_amt) ? fmt(d.purchase_amt)   : <Dash/>}</Td>

                    {/* Purchase Return */}
                    <Td>{isNonZero(d.purc_ret_gw)  ? fmtWt(d.purc_ret_gw)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.purc_ret_ct)  ? fmtWt(d.purc_ret_ct)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.purc_ret_amt) ? fmt(d.purc_ret_amt)   : <Dash/>}</Td>

                    {/* Sales */}
                    <Td>{isNonZero(d.sales_gw)  ? fmtWt(d.sales_gw)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.sales_ct)  ? fmtWt(d.sales_ct)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.sales_amt) ? fmt(d.sales_amt)   : <Dash/>}</Td>

                    {/* Sale Return */}
                    <Td>{isNonZero(d.sale_ret_gw)  ? fmtWt(d.sale_ret_gw)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.sale_ret_ct)  ? fmtWt(d.sale_ret_ct)  : <Dash/>}</Td>
                    <Td>{isNonZero(d.sale_ret_amt) ? fmt(d.sale_ret_amt)   : <Dash/>}</Td>

                    {/* Refinery */}
                    <Td>{isNonZero(d.ref_iss_gw) ? fmtWt(d.ref_iss_gw) : <Dash/>}</Td>
                    <Td>{isNonZero(d.ref_iss_ct) ? fmtWt(d.ref_iss_ct) : <Dash/>}</Td>
                    <Td>{isNonZero(d.ref_rec_gw) ? fmtWt(d.ref_rec_gw) : <Dash/>}</Td>
                    <Td>{isNonZero(d.ref_rec_ct) ? fmtWt(d.ref_rec_ct) : <Dash/>}</Td>

                    {/* Wtd Avg Rate */}
                    <Td className="font-mono text-muted-foreground">{fmtWt(d.weighted_avg_rate)}</Td>

                    {/* Closing */}
                    <Td className="bg-primary/5 font-medium">{isNonZero(d.closing_gw) ? fmtWt(d.closing_gw) : <Dash/>}</Td>
                    <Td className="bg-primary/5 font-medium">{isNonZero(d.closing_ct) ? fmtWt(d.closing_ct) : <Dash/>}</Td>
                    <Td className="bg-primary/5 font-bold text-primary">{fmt(d.closing_amt)}</Td>
                  </tr>
                ))}
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
            <Package className="h-9 w-9 text-muted-foreground/50" />
          </div>
          <h3 className="text-sm font-semibold text-foreground mb-1.5">Closing Stock Valuation</h3>
          <p className="text-sm text-muted-foreground max-w-xs leading-relaxed">
            Select a date and click <span className="font-medium text-foreground">Show Report</span> to view closing stock with category breakdowns.
          </p>
        </div>
      )}
    </div>
  );
}
