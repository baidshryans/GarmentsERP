import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { fetchKarigarIssues, fetchStoneIssues, getLedgers } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Printer, Trash2 } from "lucide-react";
import { deleteRefineryIssue, fetchGoldIssues, fetchRefinaryIssue } from '../../../services/apiService';
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from 'react-router-dom';



function RefinaryIssueList() {
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
      const result = await fetchRefinaryIssue({
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
            onClick={() => deleteRefineryIssue(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="mr-1" />
          </button>
          <button onClick={() => openAndPrint(<h1>Karigar Issue</h1>)}>
            <Printer />
          </button>
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "date",
      cell: ({ getValue }) => new Date(getValue()).toLocaleDateString('en-GB').replaceAll('/', '-'),
    },
    {
      header: "Bill No",
      accessorKey: "billno",
    },
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
  ]

  return (
    <>
      <div className="p-4">
        <div className="flex justify-between mb-4">
          {/* Search Input */}
          <Input
            type="text"
            value={search}
            onChange={(e)=>setParams({search:e.target.value,sortby})}
            placeholder="Search..."
            className="max-w-sm"
          />
          <Select value={sortby}onValueChange={(value)=>setParams({search,sortby:value})}>
            <SelectTrigger className="max-w-sm">
              <span>Sort By</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date">(Old)Date</SelectItem>
              <SelectItem value="-date">(New)Date</SelectItem>
              <SelectItem value="billno">(Asc)Bill No</SelectItem>
              <SelectItem value="-billno">(Des)Bill No</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {(loading) ?

          <div>
           
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="w-full h-8 mb-2" />
            ))}
          </div>

          :

          error ?
            <div>Error: {error}</div> :
            <>  {/* Data Table */}
              <DataTable columns={columns} data={ledgers} />

              {/* Pagination Controls */}
              <div className="flex justify-between items-center mt-4">
                <Button
                  variant="outline"
                  onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>

                <span>
                  Page {page} of {totalPages}
                </span>

                <Button
                  variant="outline"
                  onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                  disabled={page === totalPages}
                >
                  Next
                </Button>
              </div>

              <div className="flex justify-end mt-4">
                <Link to="add/">
                  <Button>Add New</Button>
                </Link>
              </div>
            </>
        }
        {/* Ordering Dropdown */}


      </div>
    </>
  )
}

export default RefinaryIssueList;