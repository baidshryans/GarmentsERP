import {useState} from 'react'
import { formatNumber } from '@/lib/format'
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { fetchSalesReturn } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Trash2, Printer } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { deleteSalesReturn, fetchSaleReturnPrintData } from '../../services/apiService';
import { openAndPrint } from "@/services/print/utils";
import SaleReturnCreditNote from "@/services/print/SaleReturnCreditNote";
import { useSearchParams } from 'react-router-dom';
import { useF2Navigate } from "@/hooks/useF2Navigate";

function SalesReturnList() {
  useF2Navigate("/sales/salesreturn/add/");
  const {toast} = useToast();
  const queryClient = useQueryClient();
      const [params, setParams] = useSearchParams();
      const [page, setPage] = useState(1);
      const [allFy, setAllFy] = useState(false);
      const search=params.get('search')||"";
      const sortby=params.get('sortby')||"";

      // React Query replaces the old useEffect+useState+setLoading triplet.
      const {
        data,
        isLoading: loading,
        error: queryError,
      } = useQuery({
        queryKey: ['salesReturns', { search, page, sortby, allFy }],
        queryFn: async () => {
          const result = await fetchSalesReturn({ search, page, ordering: sortby, allFy });
          if (!result.success) {
            throw new Error(typeof result.error === 'string' ? result.error : JSON.stringify(result.error));
          }
          return result.data;
        },
        placeholderData: (prev) => prev,
      });
      const ledgers = data?.results ?? [];
      const totalPages = data?.total_pages ?? 1;
      const error = queryError ? queryError.message : "";

      // Refresh after delete so the row disappears without a manual reload.
      const handleDeleteSalesReturn = async (id) => {
        await deleteSalesReturn(id, toast);
        queryClient.invalidateQueries({ queryKey: ['salesReturns'] });
      };
    
      

    const handlePrintCN = async (row) => {
      // Direct print from sale return data (items + discount + GST)
      const res = await fetchSaleReturnPrintData(row.id);
      if (res.success) {
        openAndPrint(<SaleReturnCreditNote data={res.data} />);
        return;
      }
      const errMsg = res.error?.detail || res.error?.message || res.error || "Could not load credit note data.";
      toast({ title: "Print failed", description: String(errMsg), variant: "destructive" });
    };

    const columns = [
           {
             header: "Action",
             accessorKey: "id",
             cell: ({ row }) => (
               <div className="flex space-x-4">
                 <Link to={`/sales/salesreturn/${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center" title="Edit">
                   <SquarePen className="size-4" />
                 </Link>
                 <button
                   onClick={() => handlePrintCN(row.original)}
                   className="p-1.5 rounded text-emerald-600 hover:bg-emerald-50 transition-colors flex items-center"
                   title="Print Credit Note"
                 >
                   <Printer className="size-4" />
                 </button>
                 <button
                           onClick={() => handleDeleteSalesReturn(row.original.id)}
                           className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
                           title="Delete"
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
               cell: ({ getValue }) => {
                 const v = parseFloat(getValue());
                 return isNaN(v) ? "-" : formatNumber(v, { decimals: 2 });
               },
             },
             {
               header: "Total Bill",
               accessorKey: "total_bill_value",
               cell: ({ getValue }) => {
                 const v = parseFloat(getValue());
                 return isNaN(v) ? "-" : formatNumber(v, { decimals: 2 });
               },
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
            <Label className="flex items-center gap-2 text-sm whitespace-nowrap cursor-pointer">
              <Checkbox checked={allFy} onCheckedChange={(v) => { setAllFy(!!v); setPage(1); }} />
              All years
            </Label>
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