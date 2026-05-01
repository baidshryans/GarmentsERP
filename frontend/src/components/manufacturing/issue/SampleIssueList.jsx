import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectTrigger, SelectContent, SelectItem,
} from "@/components/ui/select";
import { DataTable } from "@/table";
import { SquarePen, Trash2, Plus } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { fetchSampleIssues, deleteSampleIssue } from "@/services/apiService";

export default function SampleIssueList() {
  const { toast } = useToast();
  const navigate = useNavigate();

  const [search, setSearch] = useState("");
  const [sortby, setSortby] = useState("-date1");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ results: [], count: 0, total_pages: 1 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const PAGE_SIZE = 10;

  const load = async () => {
    setLoading(true);
    setError(null);
    const res = await fetchSampleIssues({ search, page, ordering: sortby });
    if (res.success) {
      const r = res.data || {};
      const results = Array.isArray(r) ? r : (r.results || []);
      const count = Array.isArray(r) ? results.length : (r.count ?? results.length);
      const total_pages = r.total_pages ?? Math.max(1, Math.ceil(count / PAGE_SIZE));
      setData({ results, count, total_pages });
    } else {
      setError(typeof res.error === "string" ? res.error : JSON.stringify(res.error));
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, [page, sortby]);

  const onSearch = () => {
    setPage(1);
    load();
  };

  const onDelete = async (id) => {
    if (!window.confirm("Delete this Sample Issue? This cannot be undone.")) return;
    const res = await deleteSampleIssue(id);
    if (res.success) {
      toast({ title: "Sample Issue deleted" });
      load();
    } else {
      const msg = res.error?.error || res.error?.detail || (typeof res.error === "string" ? res.error : "Delete failed");
      toast({ title: "Cannot delete", description: msg, variant: "destructive" });
    }
  };

  const fmtDate = (s) => {
    if (!s) return "—";
    try {
      return new Date(s).toLocaleDateString("en-GB").replaceAll("/", "-");
    } catch {
      return s;
    }
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-4">
          <Link
            to={`/manufacturing/issue/sample-issue/${row.original.id}`}
            className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center"
          >
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(row.original.id); }}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) => fmtDate(getValue()),
    },
    {
      header: "Bill No",
      accessorKey: "billno",
      cell: ({ getValue }) => <span className="font-medium">{getValue() || "—"}</span>,
    },
    {
      header: "Karigar",
      accessorKey: "karigar_ldgr_name",
      cell: ({ getValue }) => getValue() || "—",
    },
    {
      header: "Items",
      accessorKey: "items",
      cell: ({ getValue }) => (
        <span className="tabular-nums">{(getValue() || []).length}</span>
      ),
    },
    {
      header: "Remarks",
      accessorKey: "remarks",
      cell: ({ getValue }) => (
        <span className="text-muted-foreground text-sm">{getValue() || "—"}</span>
      ),
    },
  ];

  const handleRowClick = (row) => {
    navigate(`/manufacturing/issue/sample-issue/${row.id}`);
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 flex-1">
          <Input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") onSearch(); }}
            placeholder="Search bill no / karigar..."
            className="max-w-xs"
          />
          <Button size="sm" variant="secondary" onClick={onSearch}>Search</Button>
          <Select value={sortby} onValueChange={(v) => { setSortby(v); setPage(1); }}>
            <SelectTrigger className="w-44">
              <span>{sortby ? sortby.replace("-", "↓ ") : "Sort by"}</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="-date1">Date (New first)</SelectItem>
              <SelectItem value="date1">Date (Old first)</SelectItem>
              <SelectItem value="billno">Bill No (Asc)</SelectItem>
              <SelectItem value="-billno">Bill No (Desc)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Link to="/manufacturing/issue/sample-issue/new">
          <Button size="sm" className="gap-1.5">
            <Plus className="size-4" />
            Add Sample Issue
          </Button>
        </Link>
      </div>

      {/* Body */}
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
          <DataTable columns={columns} data={data.results} rowClick={handleRowClick} />

          <div className="flex items-center justify-between pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(p - 1, 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {data.total_pages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(p + 1, data.total_pages))}
              disabled={page >= data.total_pages}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
