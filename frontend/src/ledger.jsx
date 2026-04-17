import React, { useState, useEffect } from "react";
import { SquarePen, Trash2, Plus, Paperclip } from "lucide-react";
import { getLedgers } from "@/services/apiService";
import LedgerDocuments from "@/components/shared/LedgerDocuments";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { deleteLedger } from "./services/apiService";
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from 'react-router-dom';

const Ledger = () => {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);       // true only on first load
  const [transitioning, setTransitioning] = useState(false); // true during page changes
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const search = params.get('search') || "";
  const sortby = params.get('sortby') || "";

  useEffect(() => {
    const fetchLedgers = async () => {
      // Only show full skeleton on first load (no data yet)
      if (ledgers.length === 0) setLoading(true);
      else setTransitioning(true);

      const result = await getLedgers({ search, page, ordering: sortby, type: "" });
      if (result.success) {
        setLedgers(result.data.results);
        setTotalPages(result.data.total_pages);
      } else {
        setError(result.error);
      }
      setLoading(false);
      setTransitioning(false);
    };
    fetchLedgers();
  }, [search, page, sortby, refreshKey]);

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete ledger "${name}"?\n\nThis cannot be undone.`)) return;
    await deleteLedger(id, toast);
    setRefreshKey((k) => k + 1);
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="size-4" />
          </Link>
          {row.original.is_system ? (
            <span
              className="p-1.5 rounded text-muted-foreground/30 cursor-not-allowed"
              title="System ledger — cannot be deleted"
            >
              <Trash2 className="size-4" />
            </span>
          ) : (
            <button
              onClick={() => handleDelete(row.original.id, row.original.ac_name)}
              className="p-1.5 rounded text-destructive hover:bg-red-50 transition-colors"
              title="Delete ledger"
            >
              <Trash2 className="size-4" />
            </button>
          )}
          {['CO', 'KR', 'DL', 'VD'].some(r => row.original.roles?.some(lr => lr.role === r)) ? (
            <LedgerDocuments
              ledgerId={row.original.id}
              ledgerName={row.original.ac_name}
            />
          ) : (
            <span
              className="p-1.5 rounded text-muted-foreground/30 cursor-not-allowed"
              title="Documents not applicable for this ledger type"
            >
              <Paperclip className="size-4" />
            </span>
          )}
        </div>
      ),
    },
    { header: "Name", accessorKey: "ac_name" },
    { header: "Address", accessorKey: "add1" },
    { header: "Mobile", accessorKey: "mobile1" },
    { header: "PAN", accessorKey: "pan" },
    {
      header: "Roles",
      id: "roles",
      cell: ({ row }) => {
        const roles = row.original.roles || [];
        if (!roles.length) return <span className="text-muted-foreground">—</span>;
        return (
          <div className="flex flex-wrap gap-1">
            {roles.map((r, i) => (
              <span key={i} className="inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-xs font-medium">
                {r.role}
              </span>
            ))}
          </div>
        );
      },
    },
    {
      header: "Group",
      accessorKey: "ac_group_name",
      cell: ({ row }) => {
        const parent = row.original.parent_group_name;
        const group = row.original.ac_group_name;
        return (
          <div className="flex flex-col leading-tight">
            {parent && <span className="text-xs text-muted-foreground">{parent}</span>}
            <span className="italic">{group || "—"}</span>
          </div>
        );
      },
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-1">
          <Input
            type="text"
            value={search}
            onChange={(e) => setParams({ search: e.target.value, sortby })}
            placeholder="Search ledgers..."
            className="max-w-xs"
          />
          <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
            <SelectTrigger className="w-40">
              <span>{sortby ? sortby.replace('-', '↓ ') : "Sort by"}</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ac_name">Name</SelectItem>
              <SelectItem value="add1">Address</SelectItem>
              <SelectItem value="ac_group">Group (Asc)</SelectItem>
              <SelectItem value="-ac_group">Group (Desc)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Link to="add/">
          <Button size="sm" className="gap-1.5">
            <Plus className="size-4" />
            Add Ledger
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
        <div className="text-destructive text-sm">Error: {error}</div>
      ) : (
        <>
          <div className={transitioning ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}>
            <DataTable columns={columns} data={ledgers} />
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
              disabled={page === 1 || transitioning}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
              disabled={page === totalPages || transitioning}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
};

export default Ledger;
