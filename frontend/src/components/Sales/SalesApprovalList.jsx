import { useState, useEffect, useCallback } from 'react';
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { DataTable } from "@/table";
import { SquarePen, Trash2, RotateCcw, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from 'react-router-dom';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

import {
  fetchSalesApproval,
  deleteSalesApproval,
  fetchSalesApprovalById,
  returnSalesApprovalItems,
} from '../../services/apiService';
import SalesApprovalReturnForm from './SalesApprovalReturnForm';

function SalesApprovalList() {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [allFy, setAllFy] = useState(false);

  // Sheet state
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetApproval, setSheetApproval] = useState(null);
  const [sheetLoading, setSheetLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const search = params.get('search') || "";
  const sortby = params.get('sortby') || "";

  const fetchList = useCallback(async () => {
    setLoading(true);
    const result = await fetchSalesApproval({ search, page, ordering: sortby, allFy });
    if (result.success) {
      setLedgers(result.data.results);
      setTotalPages(result.data.total_pages);
    } else {
      setError(result.error);
    }
    setLoading(false);
  }, [search, page, sortby, allFy]);

  useEffect(() => { fetchList(); }, [fetchList]);

  const openReturnSheet = async (approvalId) => {
    setSheetApproval(null);
    setSheetOpen(true);
    setSheetLoading(true);
    const res = await fetchSalesApprovalById(approvalId);
    if (res.success) setSheetApproval(res.data);
    else toast({ title: "Failed to load approval", variant: "destructive" });
    setSheetLoading(false);
  };

  const handleSheetSave = async (returnedItemIds) => {
    if (!sheetApproval) return;
    setSaving(true);
    const res = await returnSalesApprovalItems(sheetApproval.id, returnedItemIds);
    setSaving(false);
    if (res.success) {
      toast({ title: "Return recorded successfully" });
      setSheetOpen(false);
      fetchList();
    } else {
      toast({
        title: "Failed to record return",
        description: JSON.stringify(res.error),
        variant: "destructive",
      });
    }
  };

  const allReturned = (row) =>
    row.items?.length > 0 && row.items.every((it) => it.ret_status);

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-2">
          <Link
            to={`/sales/salesapproval/${row.original.id}`}
            className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center"
          >
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => openReturnSheet(row.original.id)}
            disabled={allReturned(row.original)}
            title="Record return"
            className="p-1.5 rounded text-amber-600 hover:bg-amber-50 transition-colors flex items-center disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <RotateCcw className="size-4" />
          </button>
          <button
            onClick={() => deleteSalesApproval(row.original.id, toast)}
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
    { header: "Name", accessorKey: "ldgr_name" },
    {
      header: "Discount",
      accessorKey: "discount",
      cell: ({ getValue }) =>
        Number(getValue() || 0).toLocaleString("en-IN", {
          minimumFractionDigits: 2, maximumFractionDigits: 2,
        }),
    },
    {
      header: "Total Bill",
      accessorKey: "total_bill_value",
      cell: ({ getValue }) =>
        Number(getValue() || 0).toLocaleString("en-IN", {
          minimumFractionDigits: 2, maximumFractionDigits: 2,
        }),
    },
  ];

  return (
    <>
      <div className="p-4">
        <div className="flex justify-between mb-4">
          <Input
            type="text"
            value={search}
            onChange={(e) => setParams({ search: e.target.value, sortby })}
            placeholder="Search..."
            className="max-w-sm"
          />
          <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
            <SelectTrigger className="max-w-sm">
              <span>Sort By</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date1">(Old) Date</SelectItem>
              <SelectItem value="-date1">(New) Date</SelectItem>
              <SelectItem value="billno">(Asc) Bill No</SelectItem>
              <SelectItem value="-billno">(Desc) Bill No</SelectItem>
            </SelectContent>
          </Select>
          <Label className="flex items-center gap-2 text-sm whitespace-nowrap cursor-pointer">
            <Checkbox checked={allFy} onCheckedChange={(v) => { setAllFy(!!v); setPage(1); }} />
            All years
          </Label>
        </div>

        {loading ? (
          <div>
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="w-full h-8 mb-2" />
            ))}
          </div>
        ) : error ? (
          <div>Error: {error}</div>
        ) : (
          <>
            <DataTable columns={columns} data={ledgers} />

            <div className="flex justify-between items-center mt-4">
              <Button
                variant="outline"
                onClick={() => setPage((p) => Math.max(p - 1, 1))}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span>Page {page} of {totalPages}</span>
              <Button
                variant="outline"
                onClick={() => setPage((p) => Math.min(p + 1, totalPages))}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>

            <div className="flex justify-end mt-4">
              <Link to="/sales/salesapproval/add/">
                <Button>Add New</Button>
              </Link>
            </div>
          </>
        )}
      </div>

      {/* Return Sheet */}
      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
          <SheetHeader className="mb-4">
            <SheetTitle>Record Approval Return</SheetTitle>
          </SheetHeader>
          {sheetLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground mt-8">
              <Loader2 className="size-4 animate-spin" />
              Loading…
            </div>
          ) : (
            <SalesApprovalReturnForm
              key={sheetApproval?.id}
              approval={sheetApproval}
              onSave={handleSheetSave}
              saving={saving}
            />
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}

export default SalesApprovalList;
