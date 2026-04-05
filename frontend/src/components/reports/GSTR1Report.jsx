import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Download, Search, FileText, ChevronDown, ChevronRight } from "lucide-react";
import { fetchGSTR1Report } from "@/services/apiService";

const fmt = (v) =>
  Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ── Collapsible Section ────────────────────────────────────────────────────────
function Section({ title, badge, children }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-muted/40 hover:bg-muted/70 text-sm font-semibold transition-colors"
      >
        <span className="flex items-center gap-2">
          {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
          {title}
          {badge != null && (
            <span className="ml-1 px-2 py-0.5 rounded-full text-[10px] bg-violet-100 text-violet-700 font-semibold">
              {badge}
            </span>
          )}
        </span>
      </button>
      {open && <div className="p-4">{children}</div>}
    </div>
  );
}

// ── Shared table styles ────────────────────────────────────────────────────────
const TH = ({ children, right }) => (
  <th
    className={`px-3 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/40 border border-border ${right ? "text-right" : "text-left"}`}
  >
    {children}
  </th>
);
const TD = ({ children, right, bold }) => (
  <td
    className={`px-3 py-2 text-xs border border-border ${right ? "text-right" : ""} ${bold ? "font-semibold" : ""}`}
  >
    {children}
  </td>
);

// ── B2B Table ──────────────────────────────────────────────────────────────────
function B2BTable({ data }) {
  if (!data?.length)
    return <p className="text-xs text-muted-foreground">No B2B invoices for this period.</p>;
  const rows = data.flatMap((c) => c.inv.map((inv) => ({ ...inv, ctin: c.ctin, cname: c.cname })));
  const total = rows.reduce((s, r) => s + (parseFloat(r.txval) || 0), 0);
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <TH>Customer</TH><TH>GSTIN</TH><TH>Invoice No</TH><TH>Date</TH>
            <TH right>Taxable Value</TH><TH right>IGST</TH><TH right>CGST</TH><TH right>SGST</TH><TH right>Total</TH>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-muted/20"}>
              <TD>{r.cname}</TD><TD><span className="font-mono text-[10px]">{r.ctin}</span></TD>
              <TD>{r.inum}</TD><TD>{r.idt}</TD>
              <TD right>{fmt(r.txval)}</TD>
              <TD right>{fmt(r.iamt)}</TD><TD right>{fmt(r.camt)}</TD><TD right>{fmt(r.samt)}</TD>
              <TD right bold>{fmt(r.val)}</TD>
            </tr>
          ))}
          <tr className="bg-violet-50 font-semibold">
            <TD bold colSpan={4}>Total</TD>
            <TD right bold>{fmt(total)}</TD>
            <TD colSpan={4}></TD>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

// ── B2CL Table ────────────────────────────────────────────────────────────────
function B2CLTable({ data }) {
  if (!data?.length)
    return <p className="text-xs text-muted-foreground">No B2CL invoices for this period. (Inter-state, ≥₹2.5L, unregistered customer)</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <TH>Invoice No</TH><TH>Date</TH><TH>State (POS)</TH>
            <TH right>Taxable Value</TH><TH right>Rate %</TH><TH right>IGST</TH><TH right>Total</TH>
          </tr>
        </thead>
        <tbody>
          {data.map((r, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-muted/20"}>
              <TD>{r.inum}</TD><TD>{r.idt}</TD><TD>{r.pos}</TD>
              <TD right>{fmt(r.txval)}</TD><TD right>{r.rt}%</TD>
              <TD right>{fmt(r.iamt)}</TD><TD right bold>{fmt(r.val)}</TD>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── B2CS Table ────────────────────────────────────────────────────────────────
function B2CSTable({ data }) {
  if (!data?.length)
    return <p className="text-xs text-muted-foreground">No B2CS data for this period.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <TH>Supply Type</TH><TH>State (POS)</TH><TH right>Rate %</TH>
            <TH right>Taxable Value</TH><TH right>IGST</TH><TH right>CGST</TH><TH right>SGST</TH>
          </tr>
        </thead>
        <tbody>
          {data.map((r, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-muted/20"}>
              <TD>{r.sply_tp}</TD><TD>{r.pos}</TD><TD right>{r.rt}%</TD>
              <TD right>{fmt(r.txval)}</TD>
              <TD right>{fmt(r.iamt)}</TD><TD right>{fmt(r.camt)}</TD><TD right>{fmt(r.samt)}</TD>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── CDNR Table (Credit Notes - Registered) ────────────────────────────────────
function CDNRTable({ data }) {
  if (!data?.length)
    return <p className="text-xs text-muted-foreground">No credit notes for registered customers.</p>;
  const rows = data.flatMap((c) => c.nt.map((n) => ({ ...n, ctin: c.ctin, cname: c.cname })));
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr>
            <TH>Customer</TH><TH>GSTIN</TH><TH>Note No</TH><TH>Date</TH>
            <TH right>Taxable Value</TH><TH right>IGST</TH><TH right>CGST</TH><TH right>SGST</TH>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-muted/20"}>
              <TD>{r.cname}</TD><TD><span className="font-mono text-[10px]">{r.ctin}</span></TD>
              <TD>{r.ntNum}</TD><TD>{r.ntDt}</TD>
              <TD right>{fmt(r.txval)}</TD>
              <TD right>{fmt(r.iamt)}</TD><TD right>{fmt(r.camt)}</TD><TD right>{fmt(r.samt)}</TD>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────
export default function GSTR1Report() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ from_date: "", to_date: "" });

  const handleSearch = async () => {
    if (!filters.from_date || !filters.to_date) return;
    setLoading(true);
    const res = await fetchGSTR1Report(filters);
    if (res.success) setData(res.data);
    setLoading(false);
  };

  const handleExportJSON = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `GSTR1_${filters.from_date}_to_${filters.to_date}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-4 flex flex-col gap-5">
      {/* Info */}
      <div className="text-xs text-blue-800 bg-blue-50 border border-blue-200 rounded-lg px-4 py-2">
        <strong>GSTR-1</strong> — Statement of outward supplies filed monthly or quarterly. Due by the 11th of the following month.
        This report classifies invoices into B2B, B2CL, and B2CS as required by the GST portal.
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 p-4 rounded-lg border border-border bg-muted/30">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input
            type="date" className="h-9 w-40 text-sm"
            value={filters.from_date}
            onChange={(e) => setFilters((f) => ({ ...f, from_date: e.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input
            type="date" className="h-9 w-40 text-sm"
            value={filters.to_date}
            onChange={(e) => setFilters((f) => ({ ...f, to_date: e.target.value }))}
          />
        </div>
        <Button size="sm" onClick={handleSearch} className="bg-violet-700 hover:bg-violet-800 text-white h-9">
          <Search className="size-4 mr-1" /> Generate
        </Button>
        {data && (
          <Button size="sm" variant="outline" onClick={handleExportJSON} className="h-9">
            <Download className="size-4 mr-1" /> Export JSON
          </Button>
        )}
      </div>

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      )}

      {!loading && data && (
        <div className="flex flex-col gap-4">
          {/* Summary strip */}
          <div className="flex flex-wrap gap-4 rounded-lg border border-border bg-muted/20 px-4 py-3">
            <div className="text-xs">
              <span className="text-muted-foreground">Period: </span>
              <strong>{data.period?.from} → {data.period?.to}</strong>
            </div>
            <div className="text-xs">
              <span className="text-muted-foreground">GSTIN: </span>
              <strong className="font-mono">{data.retail_gstin || "—"}</strong>
            </div>
            <div className="text-xs">
              <span className="text-muted-foreground">B2B Invoices: </span>
              <strong>{data.b2b?.reduce((s, c) => s + c.inv.length, 0)}</strong>
            </div>
            <div className="text-xs">
              <span className="text-muted-foreground">B2C Invoices: </span>
              <strong>{(data.b2cl?.length || 0) + (data.b2cs?.length || 0)}</strong>
            </div>
            <div className="text-xs">
              <span className="text-muted-foreground">Credit Notes: </span>
              <strong>{(data.cdnr?.reduce((s, c) => s + c.nt.length, 0) || 0) + (data.cdnur?.length || 0)}</strong>
            </div>
          </div>

          <Section title="4A — B2B: Supplies to Registered Dealers" badge={data.b2b?.length}>
            <B2BTable data={data.b2b} />
          </Section>

          <Section title="5 — B2CL: Large B2C Inter-State Invoices (≥₹2.5L)" badge={data.b2cl?.length}>
            <B2CLTable data={data.b2cl} />
          </Section>

          <Section title="7 — B2CS: Small B2C Invoices (Consolidated)" badge={data.b2cs?.length}>
            <B2CSTable data={data.b2cs} />
          </Section>

          <Section title="9B — CDNR: Credit Notes (Registered Customers)" badge={data.cdnr?.length}>
            <CDNRTable data={data.cdnr} />
          </Section>

          {data.cdnur?.length > 0 && (
            <Section title="9B — CDNUR: Credit Notes (Unregistered Customers)" badge={data.cdnur?.length}>
              <p className="text-xs text-muted-foreground">{data.cdnur.length} credit notes for unregistered customers.</p>
            </Section>
          )}
        </div>
      )}

      {!loading && !data && (
        <div className="text-center text-sm text-muted-foreground py-12">
          <FileText className="size-10 mx-auto opacity-20 mb-2" />
          Select a date range and click Generate to load GSTR-1 data.
        </div>
      )}
    </div>
  );
}
