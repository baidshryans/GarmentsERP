import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { DataTable } from "@/table";
import { useToast } from "@/hooks/use-toast";
import { Download, FileText, Printer } from "lucide-react";
import { fetchSalesRegister, fetchSalesperson } from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

const fmtINR = (n) =>
  Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtDate = (d) => {
  if (!d) return "";
  const dt = new Date(d);
  if (Number.isNaN(dt.getTime())) return String(d);
  return dt.toLocaleDateString("en-GB").replaceAll("/", "-");
};

function downloadCsv(filename, rows, totals) {
  const headers = [
    "Date", "Bill No", "GST Bill No", "Customer", "GSTIN", "Place of Supply", "Salesperson",
    "MRP", "Discount", "Taxable", "CGST%", "CGST", "SGST%", "SGST", "IGST%", "IGST",
    "Total", "Round Off", "Return",
  ];
  const escape = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
  };
  const lines = [headers.join(",")];
  rows.forEach((r) => {
    lines.push([
      fmtDate(r.date), r.billno, r.gst_billno, r.party_name, r.gstin, r.place_of_supply,
      r.salesperson, r.mrp, r.discount, r.taxable_value, r.cgst_per, r.cgst_amt,
      r.sgst_per, r.sgst_amt, r.igst_per, r.igst_amt, r.total_bill_value, r.round_off,
      r.is_return ? "Yes" : "",
    ].map(escape).join(","));
  });
  lines.push([
    "", "", "", "TOTALS", "", "", "", "", "",
    totals.taxable_value, "", totals.cgst_amt, "", totals.sgst_amt, "", totals.igst_amt,
    totals.total_bill_value, totals.round_off, "",
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

export default function SalesRegister() {
  const { toast } = useToast();

  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";
  const [fromDate, setFromDate] = useState(firstOfMonth);
  const [toDate, setToDate]     = useState(today);
  const [spFilter, setSpFilter] = useState("");
  const [minAmt, setMinAmt]     = useState("");
  const [maxAmt, setMaxAmt]     = useState("");

  const [rows, setRows] = useState([]);
  const [serverTotals, setServerTotals] = useState({
    taxable_value: 0, sgst_amt: 0, cgst_amt: 0, igst_amt: 0, round_off: 0, total_bill_value: 0,
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
    const params = { from_date: fromDate, to_date: toDate };
    if (spFilter) params.sales_person = spFilter;
    const res = await fetchSalesRegister(params);
    if (res.success && res.data?.success) {
      setRows(res.data.data.rows || []);
      setServerTotals(res.data.data.totals || {});
    } else {
      const msg = res.data?.error || res.error || "Unknown error";
      toast({ title: "Failed to load Sales Register", description: String(msg), variant: "destructive" });
      setRows([]);
    }
    setLoading(false);
  }, [fromDate, toDate, spFilter, toast]);

  useEffect(() => { load(); }, [load]);

  const minNum = minAmt === "" ? null : Number(minAmt);
  const maxNum = maxAmt === "" ? null : Number(maxAmt);
  const valueFilterActive = minNum !== null || maxNum !== null;

  const filteredRows = useMemo(() => {
    if (!valueFilterActive) return rows;
    return rows.filter((r) => {
      const v = Number(r.total_bill_value || 0);
      if (minNum !== null && !Number.isNaN(minNum) && v < minNum) return false;
      if (maxNum !== null && !Number.isNaN(maxNum) && v > maxNum) return false;
      return true;
    });
  }, [rows, minNum, maxNum, valueFilterActive]);

  const totals = useMemo(() => {
    if (!valueFilterActive) return serverTotals;
    const t = { taxable_value: 0, sgst_amt: 0, cgst_amt: 0, igst_amt: 0, round_off: 0, total_bill_value: 0 };
    filteredRows.forEach((r) => {
      t.taxable_value    += Number(r.taxable_value    || 0);
      t.sgst_amt         += Number(r.sgst_amt         || 0);
      t.cgst_amt         += Number(r.cgst_amt         || 0);
      t.igst_amt         += Number(r.igst_amt         || 0);
      t.round_off        += Number(r.round_off        || 0);
      t.total_bill_value += Number(r.total_bill_value || 0);
    });
    Object.keys(t).forEach((k) => { t[k] = Math.round(t[k] * 100) / 100; });
    return t;
  }, [filteredRows, serverTotals, valueFilterActive]);

  const columns = [
    { header: "Date",      accessorKey: "date",        cell: ({ row }) => fmtDate(row.original.date) },
    { header: "Bill No",   accessorKey: "billno",
      cell: ({ row }) => (
        <span className={row.original.is_return ? "text-red-600 font-medium" : "font-medium"}>
          {row.original.billno}
        </span>
      ) },
    { header: "GST Bill",  accessorKey: "gst_billno" },
    { header: "Customer",  accessorKey: "party_name" },
    { header: "GSTIN",     accessorKey: "gstin" },
    { header: "POS",       accessorKey: "place_of_supply" },
    { header: "Salesperson", accessorKey: "salesperson" },
    { header: "Discount",  accessorKey: "discount",      cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.discount)}</span> },
    { header: "Taxable",   accessorKey: "taxable_value", cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.taxable_value)}</span> },
    { header: "CGST",      accessorKey: "cgst_amt",      cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.cgst_amt)}</span> },
    { header: "SGST",      accessorKey: "sgst_amt",      cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.sgst_amt)}</span> },
    { header: "IGST",      accessorKey: "igst_amt",      cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.igst_amt)}</span> },
    { header: "Total",     accessorKey: "total_bill_value",
      cell: ({ row }) => (
        <span className={`text-right block tabular-nums font-semibold ${row.original.is_return ? "text-red-600" : ""}`}>
          {fmtINR(row.original.total_bill_value)}
        </span>
      ) },
    { header: "Round Off", accessorKey: "round_off",     cell: ({ row }) => <span className="text-right block tabular-nums">{fmtINR(row.original.round_off)}</span> },
  ];

  return (
    <div className="flex flex-col gap-4 p-4 print:p-2">
      {/* Print-only header */}
      <div className="hidden print:block mb-2">
        <h1 className="text-lg font-bold">Sales Register</h1>
        <p className="text-xs">From {fromDate} to {toDate}{spFilter ? ` � Salesperson: ${(salespersons.find((s) => String(s.id) === String(spFilter)) || {}).salesperson_name || ""}` : ""}</p>
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
          <Label className="text-xs">Min Bill Value</Label>
          <Input
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={minAmt}
            onChange={(e) => setMinAmt(e.target.value)}
            placeholder="0"
            className="w-28"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Max Bill Value</Label>
          <Input
            type="number"
            inputMode="decimal"
            min="0"
            step="any"
            value={maxAmt}
            onChange={(e) => setMaxAmt(e.target.value)}
            placeholder="∞"
            className="w-28"
          />
        </div>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          {loading ? "Loading�" : "Refresh"}
        </Button>
        {valueFilterActive && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => { setMinAmt(""); setMaxAmt(""); }}
            disabled={loading}
          >
            Clear value filter
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          onClick={() => downloadCsv(`sales-register_${fromDate}_${toDate}.csv`, filteredRows, totals)}
          disabled={loading || filteredRows.length === 0}
          className="gap-1.5"
        >
          <Download className="size-4" /> CSV
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => window.print()}
          disabled={loading || filteredRows.length === 0}
          className="gap-1.5"
        >
          <Printer className="size-4" /> Print
        </Button>
      </div>

      {/* Totals strip */}
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground items-center">
        <span>
          {filteredRows.length} bill{filteredRows.length !== 1 ? "s" : ""}
          {valueFilterActive && rows.length !== filteredRows.length && (
            <span className="text-xs text-muted-foreground/70"> (of {rows.length})</span>
          )}
        </span>
        <span>Taxable: <span className="font-semibold text-foreground">₹{fmtINR(totals.taxable_value)}</span></span>
        <span>CGST: <span className="font-semibold text-foreground">₹{fmtINR(totals.cgst_amt)}</span></span>
        <span>SGST: <span className="font-semibold text-foreground">₹{fmtINR(totals.sgst_amt)}</span></span>
        <span>IGST: <span className="font-semibold text-foreground">₹{fmtINR(totals.igst_amt)}</span></span>
        <span>Total: <span className="font-semibold text-primary">₹{fmtINR(totals.total_bill_value)}</span></span>
        <span>Round Off: <span className="font-semibold text-foreground">₹{fmtINR(totals.round_off)}</span></span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="w-full h-10" />)}
        </div>
      ) : filteredRows.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-16 text-muted-foreground">
          <FileText className="size-10" />
          <p className="text-sm">
            {rows.length === 0
              ? "No sales vouchers found for the selected period."
              : "No bills match the value filter."}
          </p>
        </div>
      ) : (
        <DataTable columns={columns} data={filteredRows} />
      )}
    </div>
  );
}
