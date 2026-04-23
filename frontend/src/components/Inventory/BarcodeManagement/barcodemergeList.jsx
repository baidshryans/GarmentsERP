import React,{useState, useEffect} from 'react'
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchBarcodeMerges, getFiscalYears } from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Trash2 } from "lucide-react";

const today = new Date().toISOString().split("T")[0];

function BarcodeMergeView() {

      const [ledgers, setLedgers] = useState([]);
      const [loading, setLoading] = useState(true);
      const [error, setError] = useState("");
      const [search, setSearch] = useState("");
      const [page, setPage] = useState(1);
      const [totalPages, setTotalPages] = useState(1);
      const [fromDate, setFromDate] = useState("");
      const [toDate, setToDate] = useState(today);

      useEffect(() => {
        getFiscalYears().then((res) => {
          if (res.success) {
            const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
            const activeFy = data.find((fy) => fy.is_active);
            if (activeFy?.fy_start) {
              setFromDate(activeFy.fy_start);
            } else {
              const now = new Date();
              const fyYear = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
              setFromDate(`${fyYear}-04-01`);
            }
          }
        });
      }, []);

    useEffect(() => {
        if (!fromDate) return;
        const fetchLedgers = async () => {
          if (!isValidDateRange(fromDate, toDate)) {
            setError("From date cannot be after To date.");
            setLoading(false);
            return;
          }
          setLoading(true);
          const result = await fetchBarcodeMerges({ from_date: fromDate, to_date: toDate });
          if (result.success) {
            const d = result.data;
            setLedgers(Array.isArray(d) ? d : d?.results ?? []);
            setTotalPages(d?.total_pages ?? 1);
          } else {
            setError(result.error);
          }
          setLoading(false);
        };
        fetchLedgers();
      }, [fromDate, toDate, page, search]);
    
      

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
          <div className="flex flex-wrap items-end gap-3 mb-4">
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-muted-foreground">From Date</Label>
              <Input type="date" value={fromDate} onChange={(e) => { setFromDate(e.target.value); setPage(1); }} max={toDate || undefined} className="w-36" />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs text-muted-foreground">To Date</Label>
              <Input type="date" value={toDate} onChange={(e) => { setToDate(e.target.value); setPage(1); }} min={fromDate || undefined} className="w-36" />
            </div>
            <Input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="max-w-sm"
            />
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