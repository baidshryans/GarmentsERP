import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { getClosingStockValuation } from "../../services/apiService";
import { Package, Printer } from "lucide-react";
import { printReport } from "@/lib/printReport";

const today = new Date().toISOString().split("T")[0];

const fmt = (v) =>
  Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtWt = (v) =>
  Number(v).toLocaleString("en-IN", { minimumFractionDigits: 3, maximumFractionDigits: 3 });

const fmtRate = (v) =>
  Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const isNonZero = (v) => Math.abs(Number(v)) > 0.001;

/* ─── column group header ───────────────────────────────────────────── */
const ColGroup = ({ label, span, className = "" }) => (
  <th
    colSpan={span}
    className={`px-2 py-1.5 text-center text-[10px] uppercase tracking-wider font-semibold border border-border ${className}`}
  >
    {label}
  </th>
);

/* ─── sub-header cell ───────────────────────────────────────────────── */
const SubHead = ({ label, className = "" }) => (
  <th className={`px-2 py-1.5 text-right text-[10px] uppercase tracking-wider font-medium border border-border ${className}`}>
    {label}
  </th>
);

/* ─── data cell ─────────────────────────────────────────────────────── */
const Td = ({ children, className = "" }) => (
  <td className={`px-2 py-1.5 text-right text-xs border border-border tabular-nums ${className}`}>
    {children}
  </td>
);

export default function ClosingStockTable() {
  const [asOnDate, setAsOnDate] = useState(today);
  const tableRef = useRef(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchReport = async () => {
    setError("");
    setLoading(true);
    const res = await getClosingStockValuation({ to_date: asOnDate });
    if (res.success) {
      setData(res.data);
    } else {
      setError(
        typeof res.error === "string"
          ? res.error
          : res.error?.error || "Failed to load report."
      );
    }
    setLoading(false);
  };

  /* totals row computation */
  const totals = data?.details?.reduce(
    (acc, d) => {
      acc.opening_gw += d.opening_gw;  acc.opening_ct += d.opening_ct;  acc.opening_amt += d.opening_amt;
      acc.purchase_gw += d.purchase_gw; acc.purchase_ct += d.purchase_ct; acc.purchase_amt += d.purchase_amt;
      acc.purc_ret_gw += d.purc_ret_gw; acc.purc_ret_ct += d.purc_ret_ct; acc.purc_ret_amt += d.purc_ret_amt;
      acc.sales_gw += d.sales_gw;       acc.sales_ct += d.sales_ct;       acc.sales_amt += d.sales_amt;
      acc.sale_ret_gw += d.sale_ret_gw; acc.sale_ret_ct += d.sale_ret_ct; acc.sale_ret_amt += d.sale_ret_amt;
      acc.ref_iss_gw += d.ref_iss_gw;   acc.ref_iss_ct += d.ref_iss_ct;
      acc.ref_rec_gw += d.ref_rec_gw;   acc.ref_rec_ct += d.ref_rec_ct;
      acc.closing_gw += d.closing_gw;   acc.closing_ct += d.closing_ct;   acc.closing_amt += d.closing_amt;
      return acc;
    },
    {
      opening_gw: 0, opening_ct: 0, opening_amt: 0,
      purchase_gw: 0, purchase_ct: 0, purchase_amt: 0,
      purc_ret_gw: 0, purc_ret_ct: 0, purc_ret_amt: 0,
      sales_gw: 0, sales_ct: 0, sales_amt: 0,
      sale_ret_gw: 0, sale_ret_ct: 0, sale_ret_amt: 0,
      ref_iss_gw: 0, ref_iss_ct: 0,
      ref_rec_gw: 0, ref_rec_ct: 0,
      closing_gw: 0, closing_ct: 0, closing_amt: 0,
    }
  );

  const handlePrint = () => {
    if (!tableRef.current || !data) return;
    printReport({
      title: "Closing Stock Valuation",
      subtitle: `As on ${asOnDate}`,
      html: tableRef.current.outerHTML,
      landscape: true,
    });
  };

  return (
    <div className="flex flex-col gap-5">
      {/* ── Filters ────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">As on Date</Label>
          <Input
            type="date"
            value={asOnDate}
            onChange={(e) => setAsOnDate(e.target.value)}
            className="h-9 w-40"
          />
        </div>
        <Button size="sm" onClick={fetchReport} disabled={loading} className="h-9">
          {loading ? "Loading..." : "Show"}
        </Button>
        {data && (
          <Button size="sm" variant="outline" onClick={handlePrint} className="h-9 ml-auto">
            <Printer className="w-4 h-4 mr-1.5" /> Print
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

      {data && !loading && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table ref={tableRef} className="w-full text-xs border-collapse">
              {/* ── Level 1: group headers ───────────────── */}
              <thead>
                <tr className="bg-muted/50">
                  <ColGroup label="Item" span={1} className="text-left !text-[11px] w-36" />
                  <ColGroup label="Opening" span={3} className="bg-violet-50/60" />
                  <ColGroup label="Purchases" span={3} className="bg-green-50/60" />
                  <ColGroup label="Purc. Return" span={3} className="bg-orange-50/60" />
                  <ColGroup label="Sales" span={3} className="bg-red-50/60" />
                  <ColGroup label="Sale Return" span={3} className="bg-teal-50/60" />
                  <ColGroup label="Refinery" span={4} className="bg-purple-50/60" />
                  <ColGroup label="Wtd Avg" span={1} />
                  <ColGroup label="Closing" span={3} className="bg-primary/5" />
                </tr>

                {/* ── Level 2: sub-column headers ───────────── */}
                <tr className="bg-muted/30">
                  <SubHead label="Name" className="text-left !font-semibold w-36" />
                  {/* Opening */}
                  <SubHead label="Gw" className="bg-violet-50/40" />
                  <SubHead label="Ct" className="bg-violet-50/40" />
                  <SubHead label="Amt" className="bg-violet-50/40" />
                  {/* Purchases */}
                  <SubHead label="Gw" className="bg-green-50/40" />
                  <SubHead label="Ct" className="bg-green-50/40" />
                  <SubHead label="Amt" className="bg-green-50/40" />
                  {/* Purc Return */}
                  <SubHead label="Gw" className="bg-orange-50/40" />
                  <SubHead label="Ct" className="bg-orange-50/40" />
                  <SubHead label="Amt" className="bg-orange-50/40" />
                  {/* Sales */}
                  <SubHead label="Gw" className="bg-red-50/40" />
                  <SubHead label="Ct" className="bg-red-50/40" />
                  <SubHead label="Amt" className="bg-red-50/40" />
                  {/* Sale Return */}
                  <SubHead label="Gw" className="bg-teal-50/40" />
                  <SubHead label="Ct" className="bg-teal-50/40" />
                  <SubHead label="Amt" className="bg-teal-50/40" />
                  {/* Refinery */}
                  <SubHead label="Iss Gw" className="bg-purple-50/40" />
                  <SubHead label="Iss Ct" className="bg-purple-50/40" />
                  <SubHead label="Rec Gw" className="bg-purple-50/40" />
                  <SubHead label="Rec Ct" className="bg-purple-50/40" />
                  {/* Wtd Avg Rate */}
                  <SubHead label="Rate" />
                  {/* Closing */}
                  <SubHead label="Gw" className="bg-primary/5" />
                  <SubHead label="Ct" className="bg-primary/5" />
                  <SubHead label="Amt" className="bg-primary/5 !font-semibold" />
                </tr>
              </thead>

              <tbody>
                {data.details.length === 0 && (
                  <tr>
                    <td colSpan={24} className="text-center py-8 text-muted-foreground">
                      No stock data available for this date.
                    </td>
                  </tr>
                )}

                {data.details.map((d, i) => (
                  <tr
                    key={d.item_id}
                    className={`border-t border-border ${i % 2 === 1 ? "bg-muted/15" : ""} hover:bg-accent/20 transition-colors`}
                  >
                    {/* Item Name */}
                    <td className="px-2 py-1.5 text-left text-xs border border-border font-medium whitespace-nowrap">
                      <span className="mr-1.5 text-[9px] bg-muted px-1 py-0.5 rounded font-semibold text-muted-foreground">
                        {d.item_type}
                      </span>
                      {d.item_name}
                    </td>

                    {/* Opening */}
                    <Td>{isNonZero(d.opening_gw) ? fmtWt(d.opening_gw) : "-"}</Td>
                    <Td>{isNonZero(d.opening_ct) ? fmtWt(d.opening_ct) : "-"}</Td>
                    <Td>{isNonZero(d.opening_amt) ? fmt(d.opening_amt) : "-"}</Td>

                    {/* Purchases */}
                    <Td>{isNonZero(d.purchase_gw) ? fmtWt(d.purchase_gw) : "-"}</Td>
                    <Td>{isNonZero(d.purchase_ct) ? fmtWt(d.purchase_ct) : "-"}</Td>
                    <Td>{isNonZero(d.purchase_amt) ? fmt(d.purchase_amt) : "-"}</Td>

                    {/* Purchase Return */}
                    <Td>{isNonZero(d.purc_ret_gw) ? fmtWt(d.purc_ret_gw) : "-"}</Td>
                    <Td>{isNonZero(d.purc_ret_ct) ? fmtWt(d.purc_ret_ct) : "-"}</Td>
                    <Td>{isNonZero(d.purc_ret_amt) ? fmt(d.purc_ret_amt) : "-"}</Td>

                    {/* Sales */}
                    <Td>{isNonZero(d.sales_gw) ? fmtWt(d.sales_gw) : "-"}</Td>
                    <Td>{isNonZero(d.sales_ct) ? fmtWt(d.sales_ct) : "-"}</Td>
                    <Td>{isNonZero(d.sales_amt) ? fmt(d.sales_amt) : "-"}</Td>

                    {/* Sale Return */}
                    <Td>{isNonZero(d.sale_ret_gw) ? fmtWt(d.sale_ret_gw) : "-"}</Td>
                    <Td>{isNonZero(d.sale_ret_ct) ? fmtWt(d.sale_ret_ct) : "-"}</Td>
                    <Td>{isNonZero(d.sale_ret_amt) ? fmt(d.sale_ret_amt) : "-"}</Td>

                    {/* Refinery */}
                    <Td>{isNonZero(d.ref_iss_gw) ? fmtWt(d.ref_iss_gw) : "-"}</Td>
                    <Td>{isNonZero(d.ref_iss_ct) ? fmtWt(d.ref_iss_ct) : "-"}</Td>
                    <Td>{isNonZero(d.ref_rec_gw) ? fmtWt(d.ref_rec_gw) : "-"}</Td>
                    <Td>{isNonZero(d.ref_rec_ct) ? fmtWt(d.ref_rec_ct) : "-"}</Td>

                    {/* Wtd Avg Rate */}
                    <Td className="font-mono">{fmtRate(d.weighted_avg_rate)}</Td>

                    {/* Closing */}
                    <Td className="font-medium">{isNonZero(d.closing_gw) ? fmtWt(d.closing_gw) : "-"}</Td>
                    <Td className="font-medium">{isNonZero(d.closing_ct) ? fmtWt(d.closing_ct) : "-"}</Td>
                    <Td className="font-semibold">{fmt(d.closing_amt)}</Td>
                  </tr>
                ))}
              </tbody>

              {data.details.length > 0 && totals && (
                <tfoot>
                  <tr className="border-t-2 border-border bg-muted/50 font-semibold text-xs">
                    <td className="px-2 py-2 text-left border border-border">Total</td>

                    {/* Opening */}
                    <Td className="font-semibold">{fmtWt(totals.opening_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.opening_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.opening_amt)}</Td>

                    {/* Purchases */}
                    <Td className="font-semibold">{fmtWt(totals.purchase_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.purchase_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.purchase_amt)}</Td>

                    {/* Purchase Return */}
                    <Td className="font-semibold">{fmtWt(totals.purc_ret_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.purc_ret_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.purc_ret_amt)}</Td>

                    {/* Sales */}
                    <Td className="font-semibold">{fmtWt(totals.sales_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.sales_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.sales_amt)}</Td>

                    {/* Sale Return */}
                    <Td className="font-semibold">{fmtWt(totals.sale_ret_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.sale_ret_ct)}</Td>
                    <Td className="font-semibold">{fmt(totals.sale_ret_amt)}</Td>

                    {/* Refinery */}
                    <Td className="font-semibold">{fmtWt(totals.ref_iss_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.ref_iss_ct)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.ref_rec_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.ref_rec_ct)}</Td>

                    {/* Wtd Avg Rate */}
                    <Td></Td>

                    {/* Closing */}
                    <Td className="font-semibold">{fmtWt(totals.closing_gw)}</Td>
                    <Td className="font-semibold">{fmtWt(totals.closing_ct)}</Td>
                    <Td className="font-bold">{fmt(totals.closing_amt)}</Td>
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && !data && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-muted/50 p-4 mb-4">
            <Package className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">Closing Stock Valuation</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Select a date and click Show to view the closing stock valuation as on that date.
          </p>
        </div>
      )}
    </div>
  );
}
