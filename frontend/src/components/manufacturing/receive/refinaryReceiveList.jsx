import React, { useState, useEffect } from 'react';
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { SquarePen, Trash2 } from "lucide-react";
import { deleteRefineryReceive, fetchRefinaryReceive } from '../../../services/apiService';
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from 'react-router-dom';


function RefinaryReceiveList() {
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
      const result = await fetchRefinaryReceive({ search, page, ordering: sortby });
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
    await deleteRefineryReceive(id, toast);
    setRecords((prev) => prev.filter((r) => r.id !== id));
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex items-center gap-3">
          <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen size={16} />
          </Link>
          <button
            onClick={() => handleDelete(row.original.id)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors"
          >
            <Trash2 size={16} />
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
      header: "Refinery House",
      accessorKey: "ldgr_name",
      cell: ({ getValue }) => getValue() || "-",
    },
    {
      header: "Items",
      accessorKey: "refinaryreceivedetail_set",
      cell: ({ row }) => {
        const details = row.original.refinaryreceivedetail_set || [];
        if (details.length === 0) return <span className="text-gray-400">—</span>;
        return (
          <div className="space-y-0.5">
            {details.map((d, i) => (
              <div key={i} className="text-xs text-gray-700">
                {d.item} &mdash; {d.metal_purity} &mdash; {d.gw}g
              </div>
            ))}
          </div>
        );
      },
    },
    {
      header: "Total GW (g)",
      accessorKey: "total_gw",
      cell: ({ row }) => {
        const details = row.original.refinaryreceivedetail_set || [];
        const total = details.reduce((sum, d) => sum + parseFloat(d.gw || 0), 0);
        return total > 0 ? total.toFixed(3) : "—";
      },
    },
    {
      header: "Total Conv. Wt (g)",
      accessorKey: "total_conv_nw",
      cell: ({ row }) => {
        const details = row.original.refinaryreceivedetail_set || [];
        const total = details.reduce((sum, d) => sum + parseFloat(d.conv_nw || 0), 0);
        return total > 0 ? total.toFixed(3) : "—";
      },
    },
  ];

  return (
    <div className="p-4">
      {/* Toolbar */}
      <div className="flex flex-wrap gap-3 justify-between mb-4">
        <Input
          type="text"
          value={search}
          onChange={(e) => setParams({ search: e.target.value, sortby })}
          placeholder="Search by bill no..."
          className="max-w-xs"
        />
        <div className="flex gap-2 items-center">
          <Select value={sortby} onValueChange={(v) => setParams({ search, sortby: v })}>
            <SelectTrigger className="w-44">
              <span>Sort: {sortby.startsWith('-') ? "Newest first" : "Oldest first"}</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="-date1">Date (Newest first)</SelectItem>
              <SelectItem value="date1">Date (Oldest first)</SelectItem>
              <SelectItem value="billno">Bill No (A→Z)</SelectItem>
              <SelectItem value="-billno">Bill No (Z→A)</SelectItem>
            </SelectContent>
          </Select>
          <Link to="add/">
            <Button className="bg-primary hover:bg-primary text-white">+ Add New</Button>
          </Link>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="w-full h-10" />
          ))}
        </div>
      ) : error ? (
        <div className="text-red-500">Error: {error}</div>
      ) : (
        <>
          <DataTable columns={columns} data={records} />

          {/* Pagination */}
          <div className="flex justify-between items-center mt-4">
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span className="text-sm text-gray-600">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

export default RefinaryReceiveList;
