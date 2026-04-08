import React,{useState, useEffect} from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { fetchKarigarIssues, fetchStoneIssues, getLedgers, fetchSalesReturn } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { Edit, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { deleteSalesReturn } from '../../services/apiService';
import { useSearchParams } from 'react-router-dom';

function SalesReturnList() {
  const {toast} = useToast();
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
          const result = await  fetchSalesReturn({
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
                 <Link to={`/sales/salesreturn/${row.original.id}`} className="text-primary flex items-center">
                   <Edit className="mr-1" /> 
                 </Link>
                 <button 
                           onClick={() => deleteSalesReturn(row.original.id,toast)} 
                           className="text-red-500 flex items-center"
                         >
                           <Trash2 className="mr-1" />
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
             <Select value={sortby} onValueChange={(value)=>setParams({search,sortby:value})}>
              <SelectTrigger className="max-w-sm">
                <span>Sort By</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date1">(Old)Date</SelectItem>
                <SelectItem value="-date1">(New)Date</SelectItem>
                <SelectItem value="billno">(Asc)Billno</SelectItem>
                <SelectItem value="-billno">(Des)Billno</SelectItem>
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
                <Link to="/sales/salesreturn/add/">
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

export default SalesReturnList