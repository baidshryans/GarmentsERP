import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { fetchPurchaseRetun, fetchCompanies, fetchRetails, fetchPurchaseReturnForEdit } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Trash2, FileText, Plus } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { deletePurchaseReturn } from '../../../services/apiService';
import { openAndPrint } from "@/services/print/utils";
import PurchaseReturnDebitNote from "@/services/print/PurchaseReturnDebitNote";
import { useSearchParams } from 'react-router-dom';
import { useF2Navigate } from "@/hooks/useF2Navigate";



function PurchaseReturnList() {
  useF2Navigate("/purchase/purchasereturn/list/add/");
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const[params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [allFy, setAllFy] = useState(false);
  const [companyInfo, setCompanyInfo] = useState({});
  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"";

  useEffect(() => {
    Promise.all([fetchCompanies(), fetchRetails()]).then(([companyRes, retailRes]) => {
      if (companyRes.success) {
        const companies = Array.isArray(companyRes.data) ? companyRes.data : companyRes.data?.results ?? [];
        if (companies.length > 0) {
          const c = companies[0];
          const retails = retailRes.success ? (Array.isArray(retailRes.data) ? retailRes.data : retailRes.data?.results ?? []) : [];
          const retailCode = sessionStorage.getItem("retail_code");
          const retail = retails.find(r => r.retail_code === retailCode) || retails[0];
          setCompanyInfo({
            company_name: c.company_name,
            company_legal_name: c.legal_name || '',
            company_address: [c.address, c.city, c.pincode].filter(Boolean).join(', '),
            company_phone: c.phone,
            company_email: c.email,
            company_pan: c.pan,
            company_gstin: retail?.gstin_master_str || "",
            company_tan: c.tan,
            company_cin: c.cin,
          });
        }
      }
    });
  }, []);

  // React Query handles the "show old data while refetching" behaviour that
  // was previously implemented with a manual `transitioning` flag — `isFetching`
  // tells us when a background refresh is in flight while `data` stays.
  const {
    data,
    isLoading,
    isFetching,
    error: queryError,
  } = useQuery({
    queryKey: ['purchaseReturns', { search, page, sortby, allFy }],
    queryFn: async () => {
      const result = await fetchPurchaseRetun({ search, page, ordering: sortby, allFy });
      if (!result.success) {
        throw new Error(typeof result.error === 'string' ? result.error : JSON.stringify(result.error));
      }
      return result.data;
    },
    placeholderData: (prev) => prev,
  });
  const ledgers = data?.results ?? [];
  const totalPages = data?.total_pages ?? 1;
  const loading = isLoading;                       // first-load skeleton
  const transitioning = isFetching && !isLoading;  // background refetch overlay
  const error = queryError ? queryError.message : "";

  // Refresh the list after delete so the row disappears without a manual reload.
  const handleDeletePurchaseReturn = async (id) => {
    await deletePurchaseReturn(id, toast);
    queryClient.invalidateQueries({ queryKey: ['purchaseReturns'] });
  };



  const handlePrintDN = async (row) => {
    // The list payload already includes nested items via PurchaseReturnSerializer,
    // but we re-fetch the full PR by id to guarantee we have a fresh copy with
    // all related sub-items (and to stay aligned with how the edit form loads).
    let data = row;
    try {
      const res = await fetchPurchaseReturnForEdit(row.id);
      if (res?.success && res?.data) data = res.data;
      else if (res?.data) data = res.data;
    } catch {
      // fall back to row payload — pre-existing nested data is still usable
    }
    openAndPrint(<PurchaseReturnDebitNote data={{ ...data, ...companyInfo }} />);
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-4">
          <Link to={`/purchase/purchasereturn/list/${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => handlePrintDN(row.original)}
            className="p-1.5 rounded text-amber-600 hover:bg-amber-50 transition-colors flex items-center"
            title="Print Debit Note"
          >
            <FileText className="size-4" />
          </button>
          <button
            onClick={() => handleDeletePurchaseReturn(row.original.id)}
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
      cell: ({ getValue }) => new Date(getValue()).toLocaleDateString('en-GB').replaceAll('/', '-'),
    },
     {
      header: "Party Name",
      accessorKey: "ldgr_name",
    },
    {
      header: "Bill No",
      accessorKey: "billno",
    },
    {
      header: "Narration",
      accessorKey: "narration",
    },


  ]
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
              placeholder="Search purchase returns..."
              className="max-w-xs"
            />
            <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
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
            <Label className="flex items-center gap-2 text-sm whitespace-nowrap cursor-pointer">
              <Checkbox checked={allFy} onCheckedChange={(v) => { setAllFy(!!v); setPage(1); }} />
              All years
            </Label>
          </div>
          <Link to="add/">
            <Button size="sm" className="gap-1.5">
              <Plus className="size-4" />
              Add Purchase Return
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
            <div className={transitioning ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}>
              <DataTable columns={columns} data={ledgers} />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Button variant="outline" size="sm" onClick={() => setPage((prev) => Math.max(prev - 1, 1))} disabled={page === 1 || transitioning}>
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))} disabled={page === totalPages || transitioning}>
                Next
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default PurchaseReturnList