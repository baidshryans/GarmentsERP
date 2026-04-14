import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { fetchKarigarIssues, fetchStoneIssues, getLedgers, fetchSalesApproval, fetchBarcodeList } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Trash2, History, Printer } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useToast } from "@/hooks/use-toast";
import {deleteBarcodeManagement}from '../../../services/apiService';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import { fetchBarcodeHistoryList } from '../../../services/apiService';
import { useSearchParams } from 'react-router-dom';



function BarcodeListView() {
   const { toast } = useToast();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams() 
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
      const result = await fetchBarcodeList({
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
          {row.original.stk_status !== false ? (
            <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
              <SquarePen className="mr-1" />
            </Link>
          ) : (
            <span className="p-1.5 rounded text-muted-foreground cursor-not-allowed flex items-center" title="Not in stock — cannot edit">
              <SquarePen className="mr-1" />
            </span>
          )}
          
          <button
            onClick={() =>deleteBarcodeManagement(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
          {/* <a href={`delete/${row.original.id}`} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"> */}
            <Trash2 className="mr-1" /> 
            </button>
            <Link to={`/inventory/barcodemanagement/barcodehistory/?search=${row.original.barcode}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
            <History className="mr-1" />
          </Link>
          <button
            onClick={() => navigate(`/inventory/barcode-print?ids=${row.original.id}`)}
            className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center"
            title="Print label"
          >
            <Printer size={16} />
          </button>
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "created_date",
      cell: ({ getValue }) => new Date(getValue()).toLocaleDateString('en-GB').replaceAll('/', '-'),
    },
     {
      header: "Voucher No",
      accessorKey: "voucher_no",
    },
    {
      header: "Barcode",
      accessorKey: "barcode",
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
              <SelectItem value="created_date">(Old)Date</SelectItem>
              <SelectItem value="-created_date">(New)Date</SelectItem>
              <SelectItem value="voucher_no">(Asc)Billno</SelectItem>
              <SelectItem value="-voucher_no">(Des)Billno</SelectItem>
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
{/* Ordering Dropdown */ }
           
    
    </div >
    </>
  )
}

export default BarcodeListView;