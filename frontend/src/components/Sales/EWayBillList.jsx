import { useState, useEffect, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from "react-router-dom";
import { Truck, Ban, Pencil, Trash2, Check, X, Download } from "lucide-react";
import {
  fetchEWayBills,
  cancelEWayBill,
  updateEWayBillEBN,
  deleteEWayBill,
} from "@/services/apiService";

function StatusBadge({ status }) {
  if (status === "CANCELLED") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-100 text-red-700">
        <Ban className="size-3" /> Cancelled
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-green-100 text-green-700">
      <Truck className="size-3" /> Generated
    </span>
  );
}

export default function EWayBillList() {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [bills, setBills] = useState([]);
  const [loading, setLoading] = useState(true);

  // Inline EBN edit state
  const [editingId, setEditingId] = useState(null);
  const [ebnInput, setEbnInput] = useState("");

  const search = params.get("search") || "";
  const statusFilter = params.get("status") || "";

  const load = useCallback(async () => {
    setLoading(true);
    const res = await fetchEWayBills({ search, status: statusFilter });
    if (res.success) setBills(Array.isArray(res.data) ? res.data : []);
    else toast({ title: "Failed to load E-Way Bills", variant: "destructive" });
    setLoading(false);
  }, [search, statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleCancel = async (id) => {
    const reason = prompt("Reason for cancellation:");
    if (reason === null) return;
    const res = await cancelEWayBill(id, reason);
    if (res.success) {
      toast({ title: "E-Way Bill cancelled" });
      load();
    } else {
      toast({ title: "Failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this E-Way Bill record?")) return;
    const res = await deleteEWayBill(id);
    if (res.success) {
      toast({ title: "E-Way Bill deleted" });
      load();
    } else {
      toast({
        title: "Cannot delete",
        description: res.error?.detail || JSON.stringify(res.error),
        variant: "destructive",
      });
    }
  };

  const handleDownloadJson = (bill) => {
    const payload = bill.json_payload;
    if (!payload) {
      toast({ title: "No JSON available", description: "This record has no stored JSON payload.", variant: "destructive" });
      return;
    }
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `EWAY_${bill.source_billno || bill.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSaveEBN = async (id) => {
    const res = await updateEWayBillEBN(id, { eway_bill_no: ebnInput });
    if (res.success) {
      toast({ title: "EBN saved" });
      setEditingId(null);
      load();
    } else {
      toast({ title: "Failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  const columns = [
    {
      header: "Actions",
      cell: ({ row }) => {
        const b = row.original;
        return (
          <div className="flex items-center gap-1">
            {b.json_payload && (
              <button
                onClick={() => handleDownloadJson(b)}
                className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors"
                title="Download E-Way Bill JSON"
              >
                <Download className="size-4" />
              </button>
            )}
            {b.status !== "CANCELLED" && (
              <button
                onClick={() => handleCancel(b.id)}
                className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors"
                title="Cancel E-Way Bill"
              >
                <Ban className="size-4" />
              </button>
            )}
            {!b.eway_bill_no && (
              <button
                onClick={() => handleDelete(b.id)}
                className="p-1.5 rounded text-red-400 hover:bg-red-50 transition-colors"
                title="Delete"
              >
                <Trash2 className="size-4" />
              </button>
            )}
          </div>
        );
      },
    },
    {
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      header: "EBN",
      cell: ({ row }) => {
        const b = row.original;
        if (editingId === b.id) {
          return (
            <div className="flex items-center gap-1">
              <Input
                value={ebnInput}
                onChange={(e) => setEbnInput(e.target.value)}
                className="h-7 w-32 text-xs"
                placeholder="Enter EBN"
                autoFocus
              />
              <button onClick={() => handleSaveEBN(b.id)} className="p-1 text-green-600 hover:bg-green-50 rounded">
                <Check className="size-3.5" />
              </button>
              <button onClick={() => setEditingId(null)} className="p-1 text-gray-400 hover:bg-gray-100 rounded">
                <X className="size-3.5" />
              </button>
            </div>
          );
        }
        return (
          <div className="flex items-center gap-1">
            <span className="font-mono text-xs">{b.eway_bill_no || "—"}</span>
            {b.status !== "CANCELLED" && (
              <button
                onClick={() => { setEditingId(b.id); setEbnInput(b.eway_bill_no || ""); }}
                className="p-0.5 text-muted-foreground hover:text-foreground"
                title="Enter/Edit EBN"
              >
                <Pencil className="size-3" />
              </button>
            )}
          </div>
        );
      },
    },
    {
      header: "Source",
      cell: ({ row }) => (
        <div className="text-xs">
          <div className="font-mono text-primary">{row.original.source_billno || "—"}</div>
          <div className="text-muted-foreground">{row.original.source_type || ""}</div>
        </div>
      ),
    },
    {
      header: "Party",
      accessorKey: "party_name",
      cell: ({ getValue }) => <span className="text-xs">{getValue() || "—"}</span>,
    },
    {
      header: "Vehicle",
      accessorKey: "vehicle_no",
      cell: ({ getValue }) => <span className="text-xs font-mono">{getValue() || "—"}</span>,
    },
    {
      header: "Transporter",
      accessorKey: "transporter_name",
      cell: ({ getValue }) => <span className="text-xs">{getValue() || "—"}</span>,
    },
    {
      header: "Distance (km)",
      accessorKey: "trans_distance",
      cell: ({ getValue }) => {
        const v = getValue();
        return <span className="text-xs text-right block">{v != null && v !== '' ? v : "—"}</span>;
      },
    },
    {
      header: "Generated",
      accessorKey: "generated_date",
      cell: ({ getValue }) => {
        const d = getValue();
        if (!d) return "—";
        return <span className="text-xs text-muted-foreground">{new Date(d).toLocaleDateString("en-GB").replaceAll("/", "-")}</span>;
      },
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-base font-semibold flex items-center gap-2">
          <Truck className="size-5" /> E-Way Bills
        </h1>
      </div>

      <div className="flex items-center gap-3">
        <Input
          type="text"
          value={search}
          onChange={(e) => setParams({ search: e.target.value, status: statusFilter })}
          placeholder="Search bill no, party, vehicle..."
          className="max-w-xs h-9"
        />
        <div className="flex rounded-md overflow-hidden border border-border h-9">
          {[
            { k: "", lbl: "All" },
            { k: "GENERATED", lbl: "Active" },
            { k: "CANCELLED", lbl: "Cancelled" },
          ].map((t) => (
            <button
              key={t.k}
              onClick={() => setParams({ search, status: t.k })}
              className={`px-3 text-xs font-medium transition-colors ${
                statusFilter === t.k
                  ? "bg-primary text-primary-foreground"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
            >
              {t.lbl}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="w-full h-9" />)}
        </div>
      ) : bills.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-3 text-muted-foreground">
          <Truck className="size-12 opacity-20" />
          <p className="text-sm font-medium">No E-Way Bills found</p>
          <p className="text-xs">Generate E-Way Bills from the Sales Voucher list using the truck icon.</p>
        </div>
      ) : (
        <DataTable columns={columns} data={bills} />
      )}
    </div>
  );
}
