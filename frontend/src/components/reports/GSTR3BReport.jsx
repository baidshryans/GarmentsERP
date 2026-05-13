import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, FileText, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { fetchGSTR3BReport } from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function SummaryCard({ label, value, color = "violet", sub }) {
  const colors = {
    violet: "border-violet-200 bg-violet-50",
    green:  "border-green-200 bg-green-50",
    amber:  "border-amber-200 bg-amber-50",
    red:    "border-red-200 bg-red-50",
  };
  const textColors = {
    violet: "text-primary",
    green:  "text-green-800",
    amber:  "text-amber-800",
    red:    "text-red-800",
  };
  return (
    <div className={`rounded-lg border px-5 py-4 flex flex-col gap-1 ${colors[color]}`}>
      <span className="text-[11px] text-muted-foreground uppercase tracking-widest font-semibold">{label}</span>
      <span className={`text-xl font-bold ${textColors[color]}`}>₹{fmt(value)}</span>
      {sub && <span className="text-[10px] text-muted-foreground">{sub}</span>}
    </div>
  );
}

function GSTRow({ label, igst, cgst, sgst, bold }) {
  return (
    <tr className={bold ? "bg-violet-50 font-semibold" : "border-b border-border/50"}>
      <td className="px-4 py-2.5 text-sm">{label}</td>
      <td className="px-4 py-2.5 text-sm text-right font-mono">₹{fmt(igst)}</td>
      <td className="px-4 py-2.5 text-sm text-right font-mono">₹{fmt(cgst)}</td>
      <td className="px-4 py-2.5 text-sm text-right font-mono">₹{fmt(sgst)}</td>
      <td className="px-4 py-2.5 text-sm text-right font-mono font-semibold">
        ₹{fmt((parseFloat(igst) || 0) + (parseFloat(cgst) || 0) + (parseFloat(sgst) || 0))}
      </td>
    </tr>
  );
}

export default function GSTR3BReport() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ from_date: "", to_date: "" });

  const handleSearch = async () => {
    if (!isValidDateRange(filters.from_date, filters.to_date)) {
      alert("From date cannot be after To date.");
      return;
    }
    if (!filters.from_date || !filters.to_date) return;
    setLoading(true);
    const res = await fetchGSTR3BReport(filters);
    if (res.success) setData(res.data);
    setLoading(false);
  };

  return (
    <div className="p-4 flex flex-col gap-5">
      {/* Info */}
      <div className="text-xs text-blue-800 bg-blue-50 border border-blue-200 rounded-lg px-4 py-2">
        <strong>GSTR-3B</strong> � Monthly self-declaration summary return. Due by the 20th of the following month.
        Shows outward supplies, ITC claimed, and net tax payable.
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 p-4 rounded-lg border border-border bg-muted/30">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input
            type="date" className="h-9 w-40 text-sm"
            value={filters.from_date}
            onChange={(e) => setFilters((f) => ({ ...f, from_date: e.target.value }))}
            max={filters.to_date || undefined}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input
            type="date" className="h-9 w-40 text-sm"
            value={filters.to_date}
            onChange={(e) => setFilters((f) => ({ ...f, to_date: e.target.value }))}
            min={filters.from_date || undefined}
          />
        </div>
        <Button size="sm" onClick={handleSearch} className="bg-primary hover:bg-primary text-white h-9">
          <Search className="size-4 mr-1" /> Generate
        </Button>
      </div>

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}
        </div>
      )}

      {!loading && data && (
        <div className="flex flex-col gap-5">
          {/* KPI cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            <SummaryCard
              label="Outward Tax Liability"
              value={data.summary?.tax_payable}
              color="violet"
              sub={`Taxable value: ₹${fmt(data['3_1']?.txval)}`}
            />
            <SummaryCard
              label="Input Tax Credit (ITC)"
              value={data.summary?.itc}
              color="green"
              sub="Eligible ITC from purchases"
            />
            <SummaryCard
              label="Net Tax Payable"
              value={data.summary?.net_payable}
              color={parseFloat(data.summary?.net_payable) > 0 ? "red" : "green"}
              sub={parseFloat(data.summary?.net_payable) > 0 ? "Amount to deposit with GST portal" : "No tax payable (ITC covers liability)"}
            />
          </div>

          {/* Table 3.1 */}
          <div className="rounded-lg border border-border overflow-hidden">
            <div className="px-4 py-2.5 bg-muted/40 text-sm font-semibold border-b border-border">
              Table 3.1 � Outward Taxable Supplies (Net of Returns)
            </div>
            <table className="w-full">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2 text-left">Description</th>
                  <th className="px-4 py-2 text-right">IGST</th>
                  <th className="px-4 py-2 text-right">CGST</th>
                  <th className="px-4 py-2 text-right">SGST/UTGST</th>
                  <th className="px-4 py-2 text-right">Total GST</th>
                </tr>
              </thead>
              <tbody>
                <GSTRow
                  label="(a) Taxable outward supplies"
                  igst={data['3_1']?.iamt}
                  cgst={data['3_1']?.camt}
                  sgst={data['3_1']?.samt}
                />
                <tr className="border-b border-border/50 text-xs text-muted-foreground">
                  <td className="px-4 py-1.5 pl-8" colSpan={5}>
                    Taxable value: ₹{fmt(data['3_1']?.txval)}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Table 4 � ITC */}
          <div className="rounded-lg border border-border overflow-hidden">
            <div className="px-4 py-2.5 bg-muted/40 text-sm font-semibold border-b border-border">
              Table 4 � Eligible Input Tax Credit (ITC)
            </div>
            <table className="w-full">
              <thead>
                <tr className="text-[11px] uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2 text-left">Description</th>
                  <th className="px-4 py-2 text-right">IGST</th>
                  <th className="px-4 py-2 text-right">CGST</th>
                  <th className="px-4 py-2 text-right">SGST/UTGST</th>
                  <th className="px-4 py-2 text-right">Total ITC</th>
                </tr>
              </thead>
              <tbody>
                <GSTRow
                  label="(A) ITC Available � Inputs from purchases with GST suppliers"
                  igst={data['4']?.itc_igst}
                  cgst={data['4']?.itc_cgst}
                  sgst={data['4']?.itc_sgst}
                />
              </tbody>
            </table>
          </div>

          {/* Net Tax Summary */}
          <div className="rounded-lg border border-border overflow-hidden">
            <div className="px-4 py-2.5 bg-muted/40 text-sm font-semibold border-b border-border">
              Table 6.1 � Payment of Tax
            </div>
            <div className="p-4">
              <table className="w-full text-sm">
                <tbody>
                  <tr className="border-b border-border/30">
                    <td className="py-2 text-muted-foreground">Total outward tax liability</td>
                    <td className="py-2 text-right font-mono">₹{fmt(data.summary?.tax_payable)}</td>
                  </tr>
                  <tr className="border-b border-border/30">
                    <td className="py-2 text-muted-foreground">Less: ITC utilised</td>
                    <td className="py-2 text-right font-mono text-green-700">− ₹{fmt(data.summary?.itc)}</td>
                  </tr>
                  <tr className="bg-violet-50">
                    <td className="py-2.5 px-0 font-bold">Net tax payable (cash)</td>
                    <td className="py-2.5 text-right font-mono font-bold text-primary text-base">
                      ₹{fmt(data.summary?.net_payable)}
                    </td>
                  </tr>
                </tbody>
              </table>
              {parseFloat(data.summary?.net_payable) > 0 && (
                <p className="mt-3 text-xs text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">
                  ₹{fmt(data.summary?.net_payable)} must be deposited with the GST portal before filing.
                  Late payment attracts interest @ 18% p.a. under Section 50 of the CGST Act.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {!loading && !data && (
        <div className="text-center text-sm text-muted-foreground py-12">
          <FileText className="size-10 mx-auto opacity-20 mb-2" />
          Select a date range and click Generate to load GSTR-3B summary.
        </div>
      )}
    </div>
  );
}
