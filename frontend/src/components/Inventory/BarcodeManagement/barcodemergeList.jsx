import React,{useState, useEffect} from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { fetchKarigarIssues, fetchStoneIssues, getLedgers,fetchSalesApproval, fetchBarcodeList, fetchBarcodeMerges} from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Trash2 } from "lucide-react";



function BarcodeMergeView() {

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
          const result = await fetchBarcodeMerges({
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
                     <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
                       <SquarePen className="mr-1" /> 
                     </Link>
                     <a href={`delete/${row.original.id}`} className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center">
                       <Trash2 className="mr-1" /> 
                     </a>
                   </div>
                 ),
               },
               {
                 header: "Date",
                 accessorKey: "date1",
               },
               {
                   header: "Bill No",
                   accessorKey: "billno",
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
              placeholder="Search..."
              className="max-w-sm"
            />
             <Select >
              <SelectTrigger className="max-w-sm">
                <span>Sort By</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ac_name">Name</SelectItem>
                <SelectItem value="mobile1">Phone</SelectItem>
                <SelectItem value="add1">Address</SelectItem>
                <SelectItem value="ac_group">Group</SelectItem>
              </SelectContent>
            </Select>
          </div>

          { (loading) ? 
              
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

export default BarcodeMergeView;