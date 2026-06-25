import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { fetchKarigarIssues, fetchStoneIssues, getLedgers, fetchSalesApproval, fetchBarcodeList, fetchHallmarkIssue, fetchHallmarkReceive, fetchPurchaseOrder, fetchCompanies, fetchRetails } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Trash2, Plus, Printer } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { deletePurchaseOrder, fetchPurchaseOrderForEdit } from '../../../services/apiService';
import { useSearchParams } from 'react-router-dom';
import { openAndPrint } from "@/services/print/utils";
import { PurchaseOrderPrint } from "./purchaseOrderPrint";



function PurchaseOrderList() {
  const { toast } = useToast();
  const [params, setParams]= useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [allFy, setAllFy] = useState(false);
  const [totalPages, setTotalPages] = useState(1);
  const [ordering, setOrdering] = useState("ac_name"); // Default ordering by 'Name'
  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"";
  const [company, setCompany] = useState({});
  const [retails, setRetails] = useState([]);
  const [printingId, setPrintingId] = useState(null);

  // Fetch company + retail details once on mount
  useEffect(() => {
    Promise.all([fetchCompanies(), fetchRetails()]).then(([companyRes, retailsRes]) => {
      if (companyRes.success) {
        const c = (companyRes.data?.results || companyRes.data || [])[0];
        if (c) setCompany({
          name:            c.company_name || '',
          address:         [c.address, c.city, c.pincode].filter(Boolean).join(', '),
          phone:           c.phone || '',
          email:           c.email || '',
          pan:             c.pan || '',
          cin:             c.cin || '',
          bis_logo_url:    c.bis_logo || '',
          company_logo_url: c.company_logo || '',
        });
      }
      if (retailsRes.success) {
        setRetails(retailsRes.data?.results || retailsRes.data || []);
      }
    });
  }, []);

  const handlePrint = async (id) => {
    setPrintingId(id);
    try {
      const res = await fetchPurchaseOrderForEdit(id);
      if (res.success && res.data) {
        const retail = retails.find(r => r.id === res.data.retail);
        const gstin = retail?.gstin_master_str || '';
        openAndPrint(
          <PurchaseOrderPrint
            po={res.data}
            rows={res.data.purchaseorderitems_set || []}
            company={{ ...company, gstin }}
          />
        );
      } else {
        toast({ title: "Could not load PO", variant: "destructive" });
      }
    } catch {
      toast({ title: "Error loading PO", variant: "destructive" });
    }
    setPrintingId(null);
  };

  useEffect(() => {
    const fetchLedgers = async () => {
      if (ledgers.length === 0) setLoading(true);
      else setTransitioning(true);
      const result = await fetchPurchaseOrder({
        search,
        page,
        ordering:sortby,
        allFy,
      });

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
  }, [search, page, sortby, allFy]);



  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex items-center gap-1">
          <Link to={`/purchase/purchaseorder/list/${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
            <SquarePen className="size-3.5" />
          </Link>
          <button
            onClick={() => handlePrint(row.original.id)}
            disabled={printingId === row.original.id}
            className="p-1.5 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors flex items-center disabled:opacity-40"
            title="Print"
          >
            <Printer className="size-3.5" />
          </button>
          <button
            onClick={() => deletePurchaseOrder(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-3.5" />
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
      header: "PO No",
      accessorKey: "po_no",
    },
     {
      header: "Name",
      accessorKey: "ldgr_name",
    },
    {
      header: "Discount",
      accessorKey: "discount",
    },
    {
      header: "Total bill",
      accessorKey: "total_bill_value",

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
              placeholder="Search purchase orders..."
              className="max-w-xs"
            />
            <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
              <SelectTrigger className="w-44">
                <span>{sortby ? sortby.replace('-', '↓ ') : 'Sort by'}</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date1">Date (Old first)</SelectItem>
                <SelectItem value="-date1">Date (New first)</SelectItem>
                <SelectItem value="po_no">PO No (Asc)</SelectItem>
                <SelectItem value="-po_no">PO No (Desc)</SelectItem>
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
              Add Purchase Order
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

export default PurchaseOrderList;