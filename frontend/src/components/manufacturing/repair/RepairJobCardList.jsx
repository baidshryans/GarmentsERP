import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { SquarePen, PlusCircle, Printer, Trash2, Wrench, Plus } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchRepairJobCards, deleteRepairJobCard, fetchRepairJobCardById } from "@/services/apiService";
import { openAndPrint } from "@/services/print/utils";
import RepairJobCardPrint from "@/services/print/RepairJobCard";
import { DataTable } from "@/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";

const STATUS_LABELS = {
  RCV:  { label: "Received",        cls: "bg-blue-100 text-blue-700"   },
  ISS:  { label: "Issued",          cls: "bg-amber-100 text-amber-700" },
  RECV: { label: "Rcvd from Karigar",cls: "bg-purple-100 text-primary"},
  RDY:  { label: "Ready",           cls: "bg-green-100 text-green-700" },
  DLV:  { label: "Delivered",       cls: "bg-gray-100 text-gray-600"   },
};

export default function RepairJobCardList() {
  const { toast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage]       = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const search = searchParams.get("search") || "";
  const status = searchParams.get("status") || "";

  const load = async () => {
    setLoading(true);
    const res = await fetchRepairJobCards({ search, page, status });
    if (res.success) {
      const results = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
      setData(results);
      setTotalPages(res.data?.total_pages ?? 1);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [search, page, status]);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this repair job card?")) return;
    const res = await deleteRepairJobCard(id);
    if (res.success) {
      toast({ title: "Deleted." });
      load();
    } else {
      toast({ title: "Failed to delete.", variant: "destructive" });
    }
  };

  const handlePrint = async (id) => {
    const res = await fetchRepairJobCardById(id);
    if (res.success) openAndPrint(<RepairJobCardPrint data={res.data} />);
    else toast({ title: "Failed to load job card for printing." });
  };

  const columns = [
    {
      header: "Actions",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex gap-2">
          <Link to={`/manufacturing/repair/${row.original.id}`}>
            <SquarePen className="size-4 text-primary" />
          </Link>
          <button onClick={() => handlePrint(row.original.id)} title="Print receipt">
            <Printer className="size-4 text-muted-foreground hover:text-foreground" />
          </button>
          <button onClick={() => handleDelete(row.original.id)} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    {
      header: "RJC No",
      accessorKey: "rjc_no",
      cell: ({ getValue }) => (
        <span className="font-mono text-xs font-semibold">{getValue()}</span>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) =>
        new Date(getValue()).toLocaleDateString("en-GB").replaceAll("/", "-"),
    },
    { header: "Customer", accessorKey: "customer_name" },
    { header: "Item",     accessorKey: "item_name"     },
    { header: "Purity",   accessorKey: "purity_name"   },
    {
      header: "Recv GW",
      accessorKey: "received_gw",
      cell: ({ getValue }) => (
        <span className="tabular-nums">{parseFloat(getValue()).toFixed(3)}</span>
      ),
    },
    {
      header: "Exp. Delivery",
      accessorKey: "expected_delivery_date",
      cell: ({ getValue }) =>
        getValue()
          ? new Date(getValue()).toLocaleDateString("en-GB").replaceAll("/", "-")
          : "�",
    },
    {
      header: "Status",
      accessorKey: "status",
      cell: ({ getValue }) => {
        const s = STATUS_LABELS[getValue()] ?? { label: getValue(), cls: "" };
        return (
          <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${s.cls}`}>
            {s.label}
          </span>
        );
      },
    },
  ];

  return (
    <div className="p-4 space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 flex-1">
          <Input
            className="max-w-xs"
            placeholder="Search RJC no / customer�"
            value={search}
            onChange={(e) => {
              setPage(1);
              setSearchParams((p) => { p.set("search", e.target.value); return p; });
            }}
          />
          <Select
            value={status || "__all__"}
            onValueChange={(v) => {
              setPage(1);
              setSearchParams((p) => {
                if (v === "__all__") p.delete("status");
                else p.set("status", v);
                return p;
              });
            }}
          >
            <SelectTrigger className="w-44">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All statuses</SelectItem>
              {Object.entries(STATUS_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Link to="/manufacturing/repair/new">
          <Button size="sm" className="gap-1.5">
            <Plus className="size-4" />
            Add Repair Job Card
          </Button>
        </Link>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="w-full h-10" />
          ))}
        </div>
      ) : (
        <DataTable
          columns={columns}
          data={data}
          pageCount={totalPages}
          currentPage={page}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
