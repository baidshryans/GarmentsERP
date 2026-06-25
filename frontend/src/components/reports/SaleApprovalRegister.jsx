import React, { useState, useEffect, useCallback } from "react";
import { formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { DataTable } from "@/table";
import { useToast } from "@/hooks/use-toast";
import { Download, FileText, Printer } from "lucide-react";
import { fetchSaleApprovalRegister, fetchSalesperson } from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

const fmtINR = (n) =>
  formatNumber(n, { decimals: 2 });

const fmtDate = (d) => {
  if (!d) return "";
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return String(d);
  return dt.toLocaleDateString("en-GB").replaceAll("/", "-");
};

function downloadCsv(filename, rows, totals) {
  const headers = [
    "Date", "Bill No", "Status", "Customer", "GSTIN", "Place of Supply", "Salesperson",
    "Taxable", "Discount", "Net Taxable", "CGST%", "CGST", "SGST%", "SGST",
    "IGST%", "IGST", "Total", "Narration",
  ];
  const escape = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  const lines = [headers.join(",")];
  rows.forEach((r) => {
    const statusText = r.is_pending
      ? `Pending${r.items_total ? ` ${r.items_pending}/${r.items_total}` : ""}`
      : "Cleared";
    lines.push([
      fmtDate(r.date), r.billno, statusText, r.party_name, r.gstin, r.place_of_supply, r.salesperson,
      r.taxable_value, r.discount, r.net_taxable, r.cgst_per, r.cgst_amt, r.sgst_per, r.sgst_amt,
      r.igst_per, r.igst_amt, r.total_bill_value, r.narration,
    ].map(escape).join(","));
  });
  lines.push([
    "", "", "", "TOTALS", "", "", "",
    totals.taxable_value, "", totals.net_taxable, "", totals.cgst_amt, "", totals.sgst_amt,
    "", totals.igst_amt, totals.total_bill_value, "",
  ].map(escape).join(","));

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function SaleApprovalRegister() {
  const { toast } = useToast();

  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";
  const [fromDate, setFromDate] = useState(firstOfMonth);
  const [toDate, setToDate]     = useState(today);
  const [spFilter, setSpFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("all"); // "all" | "pending"

  const [rows, setRows] = useState([]);
  const [totals, setTotals] = useState({
    taxable_value: 0, net_taxable: 0, sgst_amt: 0, cgst_amt: 0, igst_amt: 0, total_bill_value: 0,
  });
  const [salespersons, setSalespersons] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchSalesperson().then((r) => {
      if (r.success) setSalespersons(r.data || []);
    });
  }, []);

  const load = useCallback(async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      toast({ title: "From date cannot be after To date.", variant: "destructive" });
      return;
    }
    setLoading(true);
    const params = { from_date: fromDate, to_date: toDate, status: statusFilter };
    if (spFilter) params.sales_person = spFilter;
    const res = await fetchSaleApprovalRegister(params);
    if (res.success && res.data?.success) {
      setRows(res.data.data.rows || []);
      setTotals(res.data.data.totals || {});
    } else {
      const msg = res.data?.error || res.error || "Unknown error";
      toast({ title: "Failed to load Sale Approval Register", description: String(msg), variant: "destructive" });
      setRows([]);
    }
    setLoading(false);
  }, [fromDate, toDate, spFilter, statusFilter, toast]);

  useEffect(() => { load(); }, [load]);

  const columns = [
    { header: "Date",        accessorKey: "date",        cell: ({ row }) => fmtDate(row.original.date) },
    { header: "Bill No",     accessorKey: "billno",      cell: ({ row }) => <span className="font-medium">{row.original.billno}</span> },
    { header: "Status",      accessorKey: "is_pending",
      cell: ({ row }) => {
        const r = row.original;
        if (r.is_pending) {
          return (
            <span className="text-xs bg-amber-100 text-amber-700 rounded px-1.5 py-0.5">
              Pending{r.items_total ? ` ${r.items_pending}/${r.items_total}` : ""}
            </span>
          );
        }
        return <span className="text-xs bg-emerald-100 text-emerald-700 rounded px-1.5 py-0.5">Cleared</span>;
      } },
    { header: "Customer",    accessorKey: "party_name" },
    { header: "GSTIN",       accessorKey: "gstin" },
    { header: "POS",         accessorKey: "place_of_supply" },
    { header: "Salesperson", accessorKey: "salesperson" },
    { header: "Taxable",     accessorKey: "taxable_value", cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.taxable_value)}</span> },
    { header: "Discount",    accessorKey: "discount",      cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.discount)}</span> },
    { header: "Net Taxable", accessorKey: "net_taxable",   cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.net_taxable)}</span> },
    { header: "CGST",        accessorKey: "cgst_amt",      cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.cgst_amt)}</span> },
    { header: "SGST",        accessorKey: "sgst_amt",      cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.sgst_amt)}</span> },
    { header: "IGST",        accessorKey: "igst_amt",      cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.igst_amt)}</span> },
    { header: "Total",       accessorKey: "total_bill_value",
      cell: ({ row }) => <span className="text-right block tabular-nums font-semibold">{fmtINR(row.original.total_bill_value)}</span> },
  ];

  return (
    <div className="flex flex-col gap-4 p-4 print:p-2">
      {/* Print-only header */}
      <div className="hidden print:block mb-2">
        <h1 className="text-lg font-bold">Sale Approval Register</h1>
        <p className="text-xs">From {fromDate} to {toDate}{spFilter ? ` · Salesperson: ${(salespersons.find((s) => String(s.id) === String(spFilter)) || {}).salesperson_name || ""}` : ""} · Status: {statusFilter === "pending" ? "Pending only" : "All approvals"}</p>
      </div>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end print:hidden">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} className="w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} className="w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Salesperson</Label>
          <Select value={spFilter || "__all__"} onValueChange={(v) => setSpFilter(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-48"><SelectValue placeholder="All salespersons" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All salespersons</SelectItem>
              {salespersons.map((s) => (
                <SelectItem key={s.id} value={String(s.id)}>{s.salesperson_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Status</Label>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All approvals</SelectItem>
              <SelectItem value="pending">Pending only</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => downloadCsv(`sale-approval-register_${fromDate}_${toDate}.csv`, rows, totals)}
          disabled={loading || rows.length === 0}
          className="gap-1.5"
        >
          <Download className="size-4" /> CSV
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => window.print()}
          disabled={loading || rows.length === 0}
          className="gap-1.5"
        >
          <Printer className="size-4" /> Print
        </Button>
      </div>

      {/* Totals strip */}
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground items-center">
        <span>{rows.length} approval{rows.length !== 1 ? "s" : ""}</span>
        <span>Taxable: <span className="font-semibold text-foreground">₹{fmtINR(totals.taxable_value)}</span></span>
        <span>Net Taxable: <span className="font-semibold text-foreground">₹{fmtINR(totals.net_taxable)}</span></span>
        <span>CGST: <span className="font-semibold text-foreground">₹{fmtINR(totals.cgst_amt)}</span></span>
        <span>SGST: <span className="font-semibold text-foreground">₹{fmtINR(totals.sgst_amt)}</span></span>
        <span>IGST: <span className="font-semibold text-foreground">₹{fmtINR(totals.igst_amt)}</span></span>
        <span>Total: <span className="font-semibold text-primary">₹{fmtINR(totals.total_bill_value)}</span></span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="w-full h-10" />)}
        </div>
      ) : rows.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
          <FileText className="size-10" />
          <p className="text-sm">No sales approvals found for the selected period.</p>
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}
