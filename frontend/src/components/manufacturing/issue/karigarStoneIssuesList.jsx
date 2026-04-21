import React, { useState, useEffect } from "react";
import { SquarePen, Printer, Trash2, Plus } from "lucide-react";
import { fetchKarigarIssues, fetchStoneIssues, getLedgers } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { openAndPrint } from "@/services/print/utils";
import StoneIssue from "@/services/print/StoneissueToKarigar";
import { useToast } from "@/hooks/use-toast";
import { deleteStoneIssue } from "../../../services/apiService";
import { useSearchParams } from 'react-router-dom';

const KarigarStoneIssueList = () => {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [ordering, setOrdering] = useState("ac_name"); // Default ordering by 'Name'
  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"";

  useEffect(() => {
    const fetchLedgers = async () => {
      setLoading(true);
      const result = await fetchStoneIssues({
        search,
        page,
        ordering:sortby,
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
  }, [search, page, sortby]);


  // Column definition
  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-4">
          <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
            <SquarePen className="mr-1" /> 
          </Link>
          <button
            onClick={() => deleteStoneIssue(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="mr-1" />
          </button>
          <button onClick={() => openAndPrint(<StoneIssue data={row.original} />)}>
            <Printer className="size-4" />
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
      header: "Bill No",
      accessorKey: "billno",
    },
    // {
    //   header: "Design ",
    //   accessorKey: "design_code",
    //   cell: ({ row }) => (
    //     <div>
    //    { row.original.items.map(item =>( <div>
    //     {item.design_code}
    //    </div>))}

    //     </div>
    //   ),
    // },
    {
      header: "Job No",
      accessorKey: "job_no",
      cell: ({ row }) => (
        <div>
          {row.original.slip_type === "Purchase Order" ? row.original.ref_job_no?.po_no : row.original.ref_job_no?.issue_slip_no}

        </div>
      ),

    },
    {
      header: "Design code",
      accessorKey: "design_code",
      cell: ({ row }) => (
        <div>
          {row.original.slip_type !== "Purchase Order" ? row.original?.ref_job_no?.items.map(item => (<div>
            {String(item.design_code)}
          </div>)) : ""}


        </div>
      ),

    },
    {
      header: "Main Item",
      accessorKey: "main_item",
      cell: ({ row }) => (
        <div>
          {row.original.slip_type !== "Purchase Order" ? row.original?.ref_job_no?.items.map(item => (<div>
            {String(item.customer_order_item)}
          </div>)) : ""}


        </div>
      ),

    },
    {
      header: "Karigar Name",
      accessorKey: "karigar_name",
      cell: ({ row }) => (
        <div>
          {row.original?.ref_job_no?.karigar_ldgr?.display_name}

        </div>
      ),

    },
    {
      header: "Job Sl no",
      accessorKey: "job_sl_no",
      cell: ({ row }) => (
        <div>
          {row.original?.sl_no}

        </div>
      ),

    },
    // {
    //   header: "Customer",
    //   accessorKey: "customer",
    //   cell: ({ row }) => (
    //     <div>
    //    { row.original.items.map(item =>( <div>
    //     {item?.customer_order_item?.order_no?.ldgr_code?.display_name ?? ""}
    //    </div>))}

    //     </div>
    //   ),
    // },
    // {
    //   header: "Order No",
    //   accessorKey: "order_no",
    //   cell: ({ row }) => (
    //     <div>
    //    { row.original.items.map(item =>( <div>
    //     {item?.customer_order_item?.order_no?.order_no ?? ""}
    //    </div>))}

    //     </div>
    //   ),
    // },
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
              placeholder="Search stone issues..."
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
          </div>
          <Link to="add/">
            <Button size="sm" className="gap-1.5">
              <Plus className="size-4" />
              Add Stone Issue
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
  );
};

export default KarigarStoneIssueList;
