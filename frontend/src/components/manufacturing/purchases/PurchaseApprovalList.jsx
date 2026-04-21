import React,{useState, useEffect} from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { fetchKarigarIssues, fetchStoneIssues, getLedgers } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Trash2, Plus } from "lucide-react";



function PurchaseApprovalList() {

      const [ledgers, setLedgers] = useState([]);
      const [loading, setLoading] = useState(true);
      const [error, setError] = useState("");
      const [search, setSearch] = useState("");
      const [page, setPage] = useState(1);
      const [totalPages, setTotalPages] = useState(1);
      const [ordering, setOrdering] = useState("ac_name"); // Default ordering by 'Name'
    
    useEffect(() => {
        const fetchLedgers = async () => {
          setLoading(true);
          const result = await fetchStoneIssues({
            search,
            page,
            ordering,
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
      }, [search, page, ordering]);
    
      

    const columns = [
        {
          header: "Action",
          accessorKey: "id",
          cell: ({ row }) => (
            <div className="flex space-x-4">
              <a href={`delete/${row.original.id}`} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center">
                <Trash2 className="mr-1" />
              </a>
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
          {
            header: "Job No",
            accessorKey: "job_no",
            cell: ({ row }) => (
              <div>
             { row.original.slip_type === "Purchase Order" ? row.original.ref_job_no?.po_no :  row.original.ref_job_no?.issue_slip_no }
      
              </div>
            ),
           
          },
          {
              header: "Design code",
              accessorKey: "design_code",
              cell: ({ row }) => (
                  <div>
                     { row.original.slip_type !== "Purchase Order" ? row.original?.ref_job_no?.items.map(item =>( <div>
                              {String(item.design_code)}
                      </div>)) : "" }
      
      
                      </div>
              ),
             
            },
            {
              header: "Main Item",
              accessorKey: "main_item",
              cell: ({ row }) => (
                  <div>
                     { row.original.slip_type !== "Purchase Order" ? row.original?.ref_job_no?.items.map(item =>( <div>
                              {String(item.customer_order_item)}
                      </div>)) : "" }
      
      
                      </div>
              ),
             
            },
            {
              header: "Karigar Name",
              accessorKey: "karigar_name",
              cell: ({ row }) => (
                <div>
               { row.original?.ref_job_no?.karigar_ldgr?.display_name }
        
                </div>
              ),
             
            },
            {
              header: "Job Sl no",
              accessorKey: "job_sl_no",
              cell: ({ row }) => (
                <div>
               { row.original?.sl_no }
        
                </div>
              ),
             
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
              placeholder="Search approvals..."
              className="max-w-xs"
            />
            <Select>
              <SelectTrigger className="w-44">
                <span>Sort by</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ac_name">Name</SelectItem>
                <SelectItem value="mobile1">Phone</SelectItem>
                <SelectItem value="add1">Address</SelectItem>
                <SelectItem value="ac_group">Group</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Link to="add/">
            <Button size="sm" className="gap-1.5">
              <Plus className="size-4" />
              Add Approval
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

export default PurchaseApprovalList