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
import { fetchTDSRegister, fetchTDSSections } from "@/services/apiService";

export default function TDSRegister() {
  const [rows, setRows] = useState([]);
  const [sections, setSections] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    from_date: "",
    to_date: "",
    section: "",
  });

  useEffect(() => {
    fetchTDSSections().then((res) => {
      if (res.success) {
        const d = res.data;
        setSections(Array.isArray(d) ? d : d?.results ?? []);
      }
    });
  }, []);

  const handleSearch = async () => {
    setLoading(true);
    const res = await fetchTDSRegister(filters);
    if (res.success) {
      const d = res.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  const handleExportCSV = () => {
    if (!rows.length) return;
    const headers = ["Bill No", "Date", "Vendor", "PAN", "Section", "Description", "Taxable Value", "TDS Rate %", "TDS Amount"];
    const csvRows = rows.map(r => [
      r.bill_no, r.date, r.vendor, r.pan, r.section, r.description,
      r.taxable_value, r.tds_rate, r.tds_amt
    ]);
    const csv = [headers, ...csvRows].map(row => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `TDS_Register_${filters.from_date || "all"}_to_${filters.to_date || "all"}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const fmt = (v) => Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const totalTDS = rows.reduce((sum, r) => sum + (parseFloat(r.tds_amt) || 0), 0);

  const columns = [
    { header: "#", cell: ({ row }) => row.index + 1, size: 40 },
    { header: "Bill No", accessorKey: "bill_no" },
    { header: "Date", accessorKey: "date" },
    { header: "Vendor", accessorKey: "vendor" },
    { header: "PAN", accessorKey: "pan" },
    { header: "Section", accessorKey: "section" },
    { header: "Description", accessorKey: "description" },
    { header: "Taxable Value", cell: ({ row }) => fmt(row.original.taxable_value), meta: { align: "right" } },
    { header: "TDS Rate %", cell: ({ row }) => `${parseFloat(row.original.tds_rate || 0).toFixed(3)}%` },
    { header: "TDS Amount", cell: ({ row }) => fmt(row.original.tds_amt), meta: { align: "right" } },
  ];

  return (
    <div className="p-4 flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-4 p-4 rounded-lg border border-border bg-muted/30">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input
            type="date"
            className="h-9 w-40 text-sm"
            value={filters.from_date}
            onChange={(e) => setFilters((f) => ({ ...f, from_date: e.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input
            type="date"
            className="h-9 w-40 text-sm"
            value={filters.to_date}
            onChange={(e) => setFilters((f) => ({ ...f, to_date: e.target.value }))}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">TDS Section</Label>
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
        <Button size="sm" onClick={handleSearch} className="bg-primary hover:bg-primary text-white h-9">
          <Search className="size-4 mr-1" />
          Search
        </Button>
        <Button size="sm" variant="outline" onClick={handleExportCSV} disabled={!rows.length} className="h-9">
          <Download className="size-4 mr-1" />
          Export CSV
        </Button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : rows.length > 0 ? (
        <>
          <DataTable columns={columns} data={rows} />
          <div className="flex justify-end">
            <div className="rounded-lg border border-border bg-muted/30 px-6 py-3 flex items-center gap-6">
              <span className="text-xs text-muted-foreground uppercase tracking-widest font-semibold">Total TDS Deducted</span>
              <span className="text-base font-bold text-primary">₹{fmt(totalTDS)}</span>
            </div>
          </div>
        </>
      ) : (
        <div className="text-center text-sm text-muted-foreground py-12">
          Select a date range and click Search to load TDS register.
        </div>
      )}
    </div>
  );
}
