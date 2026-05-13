import React, { useState, useEffect } from 'react';
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { SquarePen, Trash2, Plus } from "lucide-react";
import { deleteAssayReceive, fetchAssayReceive } from '../../../services/apiService';
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from 'react-router-dom';


function AssayReceiveList() {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const search = params.get('search') || "";
  const sortby = params.get('sortby') || "-date1";

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const result = await fetchAssayReceive({ search, page, ordering: sortby });
      if (result.success) {
        setRecords(result.data.results);
        setTotalPages(result.data.total_pages);
      } else {
        setError(result.error);
      }
      setLoading(false);
    };
    load();
  }, [search, page, sortby]);

  const handleDelete = async (id) => {
    await deleteAssayReceive(id, toast);
    setRecords((prev) => prev.filter((r) => r.id !== id));
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => handleDelete(row.original.id)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) => {
        const v = getValue();
        if (!v) return "-";
        return new Date(v).toLocaleDateString('en-GB').replaceAll('/', '-');
      },
    },
    {
      header: "Bill No",
      accessorKey: "billno",
      cell: ({ getValue }) => (
        <span className="font-mono text-sm">{getValue()}</span>
      ),
    },
    {
      header: "Melting House",
      accessorKey: "ldgr_name",
      cell: ({ getValue }) => getValue() || "-",
    },
    {
      header: "Items",
      accessorKey: "assayreceivedetail_set",
      cell: ({ row }) => {
        const details = row.original.assayreceivedetail_set || [];
        if (details.length === 0) return <span className="text-gray-400">�</span>;
        return (
          <div className="space-y-0.5">
            {details.map((d, i) => (
              <div key={i} className={`text-xs ${d.is_cornet ? "text-amber-600 font-semibold" : "text-gray-700"}`}>
                {d.is_cornet && "★ "}{d.item} &mdash; {d.conv_purity} &mdash; {d.conv_nw}g
              </div>
            ))}
          </div>
        );
      },
    },
    {
      header: "Cornet Wt (g)",
      accessorKey: "total_cornet",
      cell: ({ row }) => {
        const details = row.original.assayreceivedetail_set || [];
        const total = details
          .filter((d) => d.is_cornet)
          .reduce((sum, d) => sum + parseFloat(d.conv_nw || 0), 0);
        return total > 0 ? <span className="text-amber-600 font-semibold">{total.toFixed(3)}</span> : "�";
      },
    },
    {
      header: "Total Conv. Wt (g)",
      accessorKey: "total_conv_nw",
      cell: ({ row }) => {
        const details = row.original.assayreceivedetail_set || [];
        const total = details.reduce((sum, d) => sum + parseFloat(d.conv_nw || 0), 0);
        return total > 0 ? total.toFixed(3) : "�";
      },
    },
  ];

  return (
    <div className="p-4">
      <div className="flex flex-col gap-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2 flex-1">
            <Input
              type="text"
              value={search}
              onChange={(e) => setParams({ search: e.target.value, sortby })}
              placeholder="Search by bill no..."
              className="max-w-xs"
            />
            <Select value={sortby} onValueChange={(v) => setParams({ search, sortby: v })}>
              <SelectTrigger className="w-44">
                <span>{sortby ? sortby.replace('-', '↓ ') : 'Sort by'}</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date1">Date (Old first)</SelectItem>
                <SelectItem value="-date1">Date (New first)</SelectItem>
                <SelectItem value="billno">Bill No (Asc)</SelectItem>
                <SelectItem value="-billno">Bill No (Desc)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Link to="add/">
            <Button size="sm" className="gap-1.5">
              <Plus className="size-4" />
              Add Assay Receive
            </Button>
          </Link>
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex flex-col gap-2">
            {[...Array(6)].map((_, i) => (
              <Skeleton key={i} className="w-full h-10" />
            ))}
          </div>
        ) : error ? (
          <div className="text-destructive text-sm">Error: {String(error)}</div>
        ) : (
          <>
            <DataTable columns={columns} data={records} />
            <div className="flex items-center justify-between pt-1">
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(p - 1, 1))} disabled={page === 1}>
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(p + 1, totalPages))} disabled={page === totalPages}>
                Next
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default AssayReceiveList;
