import React, { useState, useEffect } from "react";
import { Edit, Trash2, Plus } from "lucide-react";
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const search = params.get('search') || "";
  const sortby = params.get('sortby') || "";

  useEffect(() => {
    const fetchLedgers = async () => {
      setLoading(true);
      const result = await getLedgers({ search, page, ordering: sortby, type: "" });
      if (result.success) {
        setLedgers(result.data.results);
        setTotalPages(result.data.total_pages);
      } else {
        setError(result.error);
      }
      setLoading(false);
    };
    fetchLedgers();
  }, [search, page, sortby]);

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <Link to={`${row.original.id}`} className="text-primary hover:text-primary/80">
            <Edit className="w-4 h-4" />
          </Link>
          <button
            onClick={() => deleteLedger(row.original.id, toast)}
            className="text-destructive hover:text-destructive/80"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <LedgerDocuments
            ledgerId={row.original.id}
            ledgerName={row.original.ac_name}
          />
        </div>
      ),
    },
    { header: "Name", accessorKey: "ac_name" },
    { header: "Address", accessorKey: "add1" },
    { header: "Mobile", accessorKey: "mobile1" },
    { header: "PAN", accessorKey: "pan" },
    { header: "Group", accessorKey: "ac_group_name" },
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
            <Plus className="w-4 h-4" />
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
          <DataTable columns={columns} data={ledgers} />

          {/* Pagination */}
          <div className="flex items-center justify-between pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
              disabled={page === 1}
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
              disabled={page === totalPages}
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
