import { useState, useEffect, useCallback } from 'react';
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { SquarePen, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from 'react-router-dom';
import { useF2Navigate } from "@/hooks/useF2Navigate";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import {
  fetchSalesApprovalReturns,
  deleteSalesApprovalReturn,
} from '../../services/apiService';

function SalesApprovalReturnList() {
  useF2Navigate("/sales/salesapprovalreturn/add/");
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [totalPages, setTotalPages] = useState(1);
  const [deleteId, setDeleteId] = useState(null);
  const [allFy, setAllFy] = useState(false);

  const search = params.get('search') || "";
  const sortby = params.get('sortby') || "";
  const page = parseInt(params.get('page') || '1', 10);

  const fetchList = useCallback(async () => {
    setLoading(true);
    const result = await fetchSalesApprovalReturns({ search, page, ordering: sortby, allFy });
    if (result.success) {
      setRecords(result.data.results);
      setTotalPages(result.data.total_pages);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [search, page, sortby, allFy]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const handleDelete = async () => {
    const id = deleteId;
    setDeleteId(null);
    await deleteSalesApprovalReturn(id, toast);
    fetchList();
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-2">
          <Link
            to={`/sales/salesapprovalreturn/${row.original.id}`}
            className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center"
          >
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => setDeleteId(row.original.id)}
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
      cell: ({ getValue }) =>
        new Date(getValue()).toLocaleDateString('en-GB').replaceAll('/', '-'),
    },
    { header: "Bill No", accessorKey: "billno" },
    {
      header: "Ref Approval",
      accessorKey: "ref_approval_billno",
      cell: ({ getValue }) => getValue() ?? "—",
    },
    {
      header: "Items",
      accessorKey: "items",
      cell: ({ getValue }) => (getValue() || []).length,
    },
    { header: "Narration", accessorKey: "narration" },
  ];

  return (
    <>
    <div className="p-4">
      <div className="flex justify-between mb-4 gap-2">
        <Input
          type="text"
          value={search}
          onChange={(e) => setParams({ search: e.target.value, sortby, page: '1' })}
          placeholder="Search bill no or ref approval…"
          className="max-w-sm"
        />
        <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value, page: '1' })}>
          <SelectTrigger className="max-w-xs">
            <SelectValue placeholder="Sort By" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="-date1">Date (Newest)</SelectItem>
            <SelectItem value="date1">Date (Oldest)</SelectItem>
            <SelectItem value="billno">Bill No (Asc)</SelectItem>
            <SelectItem value="-billno">Bill No (Desc)</SelectItem>
          </SelectContent>
        </Select>
        <Label className="flex items-center gap-2 text-sm whitespace-nowrap cursor-pointer">
          <Checkbox checked={allFy} onCheckedChange={(v) => { setAllFy(!!v); setParams({ search, sortby, page: '1' }); }} />
          All years
        </Label>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="w-full h-8" />)}
        </div>
      ) : error ? (
        <div className="text-red-500">Error: {String(error)}</div>
      ) : (
        <>
          <DataTable columns={columns} data={records} />

          <div className="flex justify-between items-center mt-4">
            <Button
              variant="outline"
              onClick={() => setParams({ search, sortby, page: String(page - 1) })}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
            <Button
              variant="outline"
              onClick={() => setParams({ search, sortby, page: String(page + 1) })}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>

          <div className="flex justify-end mt-4">
            <Link to="/sales/salesapprovalreturn/add/">
              <Button>Add New</Button>
            </Link>
          </div>
        </>
      )}
    </div>

    <ConfirmDialog
      open={!!deleteId}
      title="Confirm Delete"
      description="This sales approval return will be permanently deleted."
      onConfirm={handleDelete}
      onCancel={() => setDeleteId(null)}
    />
    </>
  );
}

export default SalesApprovalReturnList;
