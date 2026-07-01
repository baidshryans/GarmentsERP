import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { fetchKarigarIssues, fetchStoneIssues, getLedgers } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Printer, Trash2, Plus } from "lucide-react";
import { deleteRefineryIssue, fetchGoldIssues, fetchRefinaryIssue } from '../../../services/apiService';
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from 'react-router-dom';
import { openAndPrint } from "@/services/print/utils";
import RefineryIssuePrint from "@/services/print/RefineryIssuePrint";
import { fetchCompanies } from "@/services/api/masters";
import { fetchRetails } from "@/services/apiService";



function RefinaryIssueList() {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [ordering, setOrdering] = useState("ac_name"); // Default ordering by 'Name'
  const [allFy, setAllFy] = useState(false);
  const [companyInfo, setCompanyInfo] = useState({});

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
            company_address: [c.address, c.city, c.pincode].filter(Boolean).join(', '),
            company_phone: c.phone,
            company_email: c.email,
            company_pan: c.pan,
            company_gstin: retail?.gstin_master_str || "",
          });
        }
      }
    });
  }, []);
  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"";

  useEffect(() => {
    const fetchLedgers = async () => {
      setLoading(true);
      const result = await fetchRefinaryIssue({
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
    };

    fetchLedgers();
  }, [search, page, sortby, allFy]);



  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex items-center space-x-2">
          <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors">
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => deleteRefineryIssue(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors"
          >
            <Trash2 className="size-4" />
          </button>
          <button
            onClick={() => openAndPrint(<RefineryIssuePrint data={{ ...row.original, ...companyInfo }} />)}
            className="p-1.5 rounded text-muted-foreground hover:bg-muted transition-colors"
          >
            <Printer className="size-4" />
          </button>
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) => {
        const v = getValue();
        const d = v ? new Date(v) : null;
        return d && !isNaN(d) ? d.toLocaleDateString('en-GB').replaceAll('/', '-') : "";
      },
    },
    {
      header: "Bill No",
      accessorKey: "billno",
    },
    {
      header: "Refinery Name",
      accessorKey: "ldgr_name",
    },
    {
      header: "Item",
      accessorKey: "item",
      cell: ({ row }) => {
        const items = [...new Set((row.original.refinaryissuedetail_set || []).map((d) => d.item_name || d.item).filter(Boolean))];
        return <div>{items.join(", ")}</div>;
      },
    },
    {
      header: "Gross Weight",
      accessorKey: "gw",
      cell: ({ row }) => {
        const total = (row.original.refinaryissuedetail_set || [])
          .reduce((sum, d) => sum + (parseFloat(d.gw) || 0), 0);
        return <div>{total.toFixed(3)}</div>;
      },
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
              placeholder="Search refinery issues..."
              className="max-w-xs"
            />
            <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
              <SelectTrigger className="w-44">
                <span>{sortby ? sortby.replace('-', '↓ ') : 'Sort by'}</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date">Date (Old first)</SelectItem>
                <SelectItem value="-date">Date (New first)</SelectItem>
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
              Add Refinery Issue
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
            <DataTable columns={columns} data={ledgers} />
            <div className="flex items-center justify-between pt-1">
              <Button variant="outline" size="sm" onClick={() => setPage((prev) => Math.max(prev - 1, 1))} disabled={page === 1}>
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))} disabled={page === totalPages}>
                Next
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default RefinaryIssueList;