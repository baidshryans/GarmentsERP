import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { Download, Search } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchTCSRegister, fetchTCSSections, getFiscalYears } from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

const today = new Date().toISOString().split("T")[0];

export default function TCSRegister() {
  const [rows, setRows] = useState([]);
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    from_date: "",
    to_date: today,
    section: "",
  });

  useEffect(() => {
    fetchTCSSections().then((res) => {
      if (res.success) {
        const d = res.data;
        setSections(Array.isArray(d) ? d : d?.results ?? []);
      }
    });
    getFiscalYears().then((res) => {
      if (res.success) {
        const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
        const activeFy = data.find((fy) => fy.is_active);
        if (activeFy?.fy_start) {
          setFilters((f) => ({ ...f, from_date: activeFy.fy_start }));
        } else {
          const now = new Date();
          const fyYear = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
          setFilters((f) => ({ ...f, from_date: `${fyYear}-04-01` }));
        }
      }
    });
  }, []);

  const handleSearch = async () => {
    if (!isValidDateRange(filters.from_date, filters.to_date)) {
      alert("From date cannot be after To date.");
      return;
    }
    setLoading(true);
    const res = await fetchTCSRegister(filters);
    if (res.success) {
      const d = res.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  const handleExportCSV = () => {
    if (!rows.length) return;
    const headers = [
      "Bill No", "GST Bill No", "Date", "Customer", "GSTIN", "PAN",
      "Section", "Description", "Taxable Value", "TCS Rate %", "TCS Amount", "Bill Value",
    ];
    const csvRows = rows.map((r) => [
      r.bill_no, r.gst_bill_no, r.date, r.customer, r.gstin, r.pan,
      r.section, r.description,
      r.taxable_value, r.tcs_rate, r.tcs_amt, r.bill_value,
    ]);
    const csv = [headers, ...csvRows].map((row) => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `TCS_Register_${filters.from_date || "all"}_to_${filters.to_date || "all"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const fmt = (v) =>
    Number(v || 0).toLocaleString("en-IN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  const totalTCS = rows.reduce((sum, r) => sum + (parseFloat(r.tcs_amt) || 0), 0);
  const totalTaxable = rows.reduce((sum, r) => sum + (parseFloat(r.taxable_value) || 0), 0);

  const columns = [
    { header: "#", cell: ({ row }) => row.index + 1, size: 40 },
    { header: "Bill No", accessorKey: "bill_no" },
    { header: "GST Bill No", accessorKey: "gst_bill_no" },
    { header: "Date", accessorKey: "date" },
    { header: "Customer", accessorKey: "customer" },
    { header: "GSTIN", accessorKey: "gstin" },
    { header: "PAN", accessorKey: "pan" },
    { header: "Section", accessorKey: "section" },
    {
      header: "Taxable Value",
      cell: ({ row }) => fmt(row.original.taxable_value),
      meta: { align: "right" },
    },
    {
      header: "TCS Rate %",
      cell: ({ row }) => `${parseFloat(row.original.tcs_rate || 0).toFixed(3)}%`,
    },
    {
      header: "TCS Amount",
      cell: ({ row }) => fmt(row.original.tcs_amt),
      meta: { align: "right" },
    },
    {
      header: "Bill Value",
      cell: ({ row }) => fmt(row.original.bill_value),
      meta: { align: "right" },
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-5">
      {/* Info strip */}
      <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2">
        <strong>Section 206C(1H)</strong> — TCS is collected by the seller on receipt of sale
        consideration exceeding ₹50 lakh from a buyer in a financial year. Rate: 0.1% (1% without PAN).
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 p-4 rounded-lg border border-border bg-muted/30">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input
            type="date"
            className="h-9 w-40 text-sm"
            value={filters.from_date}
            onChange={(e) => setFilters((f) => ({ ...f, from_date: e.target.value }))}
            max={filters.to_date || undefined}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input
            type="date"
            className="h-9 w-40 text-sm"
            value={filters.to_date}
            onChange={(e) => setFilters((f) => ({ ...f, to_date: e.target.value }))}
            min={filters.from_date || undefined}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">TCS Section</Label>
          <Select
            value={filters.section}
            onValueChange={(v) => setFilters((f) => ({ ...f, section: v === "all" ? "" : v }))}
          >
            <SelectTrigger className="h-9 w-52 text-sm">
              <SelectValue placeholder="All sections" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Sections</SelectItem>
              {sections.map((s) => (
                <SelectItem key={s.id} value={s.section_code}>
                  {s.section_code} — {s.description}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          size="sm"
          onClick={handleSearch}
          className="bg-primary hover:bg-primary text-white h-9"
        >
          <Search className="size-4 mr-1" />
          Search
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={handleExportCSV}
          disabled={!rows.length}
          className="h-9"
        >
          <Download className="size-4 mr-1" />
          Export CSV
        </Button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : rows.length > 0 ? (
        <>
          <DataTable columns={columns} data={rows} />
          {/* Totals footer */}
          <div className="flex justify-end">
            <div className="rounded-lg border border-border bg-muted/30 px-6 py-3 flex items-center gap-8">
              <div className="flex flex-col items-end">
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">
                  Total Taxable Value
                </span>
                <span className="text-sm font-semibold">₹{fmt(totalTaxable)}</span>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">
                  Total TCS Collected
                </span>
                <span className="text-base font-bold text-primary">₹{fmt(totalTCS)}</span>
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center text-sm text-muted-foreground py-12">
          Select a date range and click Search to load TCS register.
        </div>
      )}
    </div>
  );
}
