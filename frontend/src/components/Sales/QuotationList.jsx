import { useState } from "react";
import { formatNumber, formatDate } from "@/lib/format";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import { DataTable } from "@/table";
import { SquarePen, Plus, Printer, Trash2, Copy, CheckCircle2, Loader2, CalendarDays } from "lucide-react";
import { openAndPrint } from "@/services/print/utils";
import QuotationPrint from "./QuotationPrint";
import { useToast } from "@/hooks/use-toast";
import {
  fetchQuotations,
  fetchQuotationPrintData,
  deleteQuotation,
  duplicateQuotation,
  finalizeQuotation,
  patchQuotation,
} from "@/services/apiService";

const statusColors = {
  draft: "bg-yellow-100 text-yellow-800",
  finalized: "bg-green-100 text-green-800",
  expired: "bg-gray-100 text-gray-500",
  converted: "bg-blue-100 text-blue-800",
};

export default function QuotationList() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [allFy, setAllFy] = useState(false);
  const [actionLoading, setActionLoading] = useState(null);
  const [extendTarget, setExtendTarget] = useState(null); // { id, valid_until }
  const [extendDate, setExtendDate] = useState("");
  const search = params.get("search") || "";
  const statusFilter = params.get("status") || "";

  // React Query manages fetching/caching; `load()` becomes a one-liner that
  // invalidates the cache so the hook refetches.
  const {
    data: queryData,
    isLoading: loading,
  } = useQuery({
    queryKey: ['quotations', { search, status: statusFilter, page, allFy }],
    queryFn: async () => {
      const qs = new URLSearchParams();
      if (search) qs.set("search", search);
      if (statusFilter) qs.set("status", statusFilter);
      qs.set("page", page);
      if (allFy) qs.set("all_fy", "1");
      const res = await fetchQuotations(qs.toString());
      if (!res.success) {
        throw new Error(typeof res.error === 'string' ? res.error : JSON.stringify(res.error));
      }
      return res.data;
    },
    placeholderData: (prev) => prev,
  });
  const quotations = Array.isArray(queryData) ? queryData : (queryData?.results ?? []);
  const totalPages = queryData?.total_pages || 1;
  const load = () => queryClient.invalidateQueries({ queryKey: ['quotations'] });

  const handleSearch = (val) => {
    setParams((prev) => { val ? prev.set("search", val) : prev.delete("search"); return prev; });
    setPage(1);
  };

  const handlePrint = async (id) => {
    setActionLoading(id);
    const res = await fetchQuotationPrintData(id);
    if (res.success) {
      openAndPrint(<QuotationPrint data={res.data} />);
    } else {
      toast({ title: "Failed to load print data", variant: "destructive" });
    }
    setActionLoading(null);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this quotation?")) return;
    const res = await deleteQuotation(id);
    if (res.success) { toast({ title: "Quotation deleted" }); load(); }
    else toast({ title: "Delete failed", variant: "destructive" });
  };

  const handleDuplicate = async (id) => {
    setActionLoading(id);
    const res = await duplicateQuotation(id);
    if (res.success) {
      toast({ title: `Duplicated as ${res.data.quotation_no}` });
      navigate(`/sales/quotation/${res.data.id}`);
    } else {
      toast({ title: "Duplicate failed", variant: "destructive" });
    }
    setActionLoading(null);
  };

  const handleFinalize = async (id) => {
    setActionLoading(id);
    const res = await finalizeQuotation(id);
    if (res.success) { toast({ title: "Quotation finalized" }); load(); }
    else toast({ title: res.error?.error || "Finalize failed", variant: "destructive" });
    setActionLoading(null);
  };

  const openExtendDialog = (q) => {
    setExtendTarget(q);
    setExtendDate(q.valid_until || "");
  };

  const handleExtendExpiry = async () => {
    if (!extendTarget || !extendDate) return;
    const res = await patchQuotation(extendTarget.id, { valid_until: extendDate });
    if (res.success) {
      toast({ title: "Expiry extended" });
      setExtendTarget(null);
      load();
    } else {
      toast({ title: "Failed to extend expiry", variant: "destructive" });
    }
  };

  const columns = [
    {
      header: "Qt No",
      accessorKey: "quotation_no",
      cell: ({ row }) => (
        <Link to={`/sales/quotation/${row.original.id}`} className="font-mono text-primary hover:underline">
          {row.original.quotation_no}
        </Link>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ row }) => formatDate(row.original.date1, "numeric"),
    },
    {
      header: "Party",
      accessorKey: "ldgr_name",
      cell: ({ row }) => row.original.ldgr_name || row.original.party_name || "Walk-in",
    },
    {
      header: "Items",
      accessorKey: "total_items",
    },
    {
      header: "Total",
      accessorKey: "net_total",
      cell: ({ row }) => (
        <span className="tabular-nums font-medium">
          ₹ {formatNumber(row.original.net_total || 0)}
        </span>
      ),
    },
    {
      header: "Status",
      accessorKey: "status",
      cell: ({ row }) => {
        const s = row.original.status;
        return (
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase ${statusColors[s] || "bg-gray-100"}`}>
            {s}
          </span>
        );
      },
    },
    {
      header: "Valid Until",
      accessorKey: "valid_until",
      cell: ({ row }) => {
        if (!row.original.valid_until) return "—";
        const d = new Date(row.original.valid_until);
        const isExpired = d < new Date();
        return (
          <span className={isExpired ? "text-red-500" : ""}>
            {formatDate(d, "numeric")}
          </span>
        );
      },
    },
    {
      header: "Actions",
      id: "actions",
      cell: ({ row }) => {
        const q = row.original;
        const isLoading = actionLoading === q.id;
        return (
          <div className="flex space-x-4">
            {isLoading && <Loader2 className="size-4 animate-spin" />}
            <Link to={`/sales/quotation/${q.id}`} title="Edit" className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
              <SquarePen className="size-4" />
            </Link>
            <button type="button" title="Print" onClick={() => handlePrint(q.id)} className="p-1.5 rounded text-emerald-600 hover:bg-emerald-50 transition-colors flex items-center">
              <Printer className="size-4" />
            </button>
            <button type="button" title="Duplicate" onClick={() => handleDuplicate(q.id)} className="p-1.5 rounded text-slate-600 hover:bg-slate-100 transition-colors flex items-center">
              <Copy className="size-4" />
            </button>
            <button type="button" title="Extend Expiry" onClick={() => openExtendDialog(q)} className="p-1.5 rounded text-blue-600 hover:bg-blue-50 transition-colors flex items-center">
              <CalendarDays className="size-4" />
            </button>
            {q.status === "draft" && (
              <>
                <button type="button" title="Finalize" onClick={() => handleFinalize(q.id)} className="p-1.5 rounded text-green-600 hover:bg-green-50 transition-colors flex items-center">
                  <CheckCircle2 className="size-4" />
                </button>
                <button type="button" title="Delete" onClick={() => handleDelete(q.id)} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center">
                  <Trash2 className="size-4" />
                </button>
              </>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4 w-full max-w-[90%] mx-auto">
      {/* Header */}
      <h1 className="text-xl font-bold">Quotations</h1>

      {/* Filters + Actions row */}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          placeholder="Search quotation no, party…"
          value={search}
          onChange={(e) => handleSearch(e.target.value)}
          className="h-9 max-w-xs"
        />
        <div className="flex items-center gap-1.5">
          <Label className="text-xs text-muted-foreground whitespace-nowrap">Status</Label>
          <Select
            value={statusFilter || "all"}
            onValueChange={(v) => {
              setParams((prev) => { v && v !== "all" ? prev.set("status", v) : prev.delete("status"); return prev; });
              setPage(1);
            }}
          >
            <SelectTrigger className="h-9 w-36">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All</SelectItem>
              <SelectItem value="draft">Draft</SelectItem>
              <SelectItem value="finalized">Finalized</SelectItem>
              <SelectItem value="expired">Expired</SelectItem>
              <SelectItem value="converted">Converted</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Label className="flex items-center gap-2 text-sm whitespace-nowrap cursor-pointer">
          <Checkbox checked={allFy} onCheckedChange={(v) => { setAllFy(!!v); setPage(1); }} />
          All years
        </Label>
        <div className="ml-auto">
          <Link to="/sales/quotation/add/">
            <Button className="gap-1.5 h-9">
              <Plus className="size-4" /> New Quotation
            </Button>
          </Link>
        </div>
      </div>

      {/* Table */}
      <DataTable columns={columns} data={quotations} loading={loading} />

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Prev
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      )}

      {/* Extend Expiry Dialog */}
      <Dialog open={!!extendTarget} onOpenChange={(open) => { if (!open) setExtendTarget(null); }}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Extend Expiry Date</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-2 py-2">
            <Label className="text-xs">Quotation: <span className="font-mono font-semibold">{extendTarget?.quotation_no}</span></Label>
            <Label className="text-xs">New Valid Until</Label>
            <Input
              type="date"
              value={extendDate}
              onChange={(e) => setExtendDate(e.target.value)}
              className="h-9"
              min={new Date().toISOString().split("T")[0]}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExtendTarget(null)}>Cancel</Button>
            <Button onClick={handleExtendExpiry} disabled={!extendDate}>Extend</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
