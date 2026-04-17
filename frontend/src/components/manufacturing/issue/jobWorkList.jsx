import React, { useState, useEffect } from "react";
import { SquarePen, Printer, Trash2 } from "lucide-react";
import { fetchKarigarIssues, getLedgers } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { openAndPrint } from "@/services/print/utils";
import JobOrder from "../../../services/print/JobOrder";
import { deleteJobWorkIssue } from "../../../services/apiService";
import { useToast } from "@/hooks/use-toast";
import { useSearchParams } from "react-router-dom";


const KarigarJobs = () => {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [error, setError] = useState("");
 
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [ordering, setOrdering] = useState(""); // Default ordering by 'Name'

  const search =params.get("search") || "";
  const sortby =params.get("sortby") || "";

  useEffect(() => {
    const fetchLedgers = async () => {
      if (ledgers.length === 0) setLoading(true);
      else setTransitioning(true);
      const result = await fetchKarigarIssues({
        search,
        page,
        ordering: sortby,
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
            onClick={() => deleteJobWorkIssue(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="mr-1" />
          </button>
         <button onClick={() => openAndPrint(<JobOrder data={row.original} />)}>
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
      header: "Issue Slip No",
      accessorKey: "issue_slip_no",
    },
    {
      header: "Design code",
      accessorKey: "design_code",
      cell: ({ row }) => (
        <div>
          {row.original.items.map(item => (<div>
            {item.design_code}
          </div>))}

        </div>
      ),
    },
    {
      header: "Karigar Name",
      accessorKey: "karigar_ldgr_name",
      cell: ({ row }) => (
        <div>
          {row.original.karigar_ldgr_name
          }

        </div>
      ),

    },

    {
      header: "Order No",
      accessorKey: "order_no",
      cell: ({ row }) => (
        <div>
          {row.original.items.map(item => (<div>
            {item?.customer_order_item?.order_no?.order_no ?? ""}
          </div>))}

        </div>
      ),
    },
  ];
  return (
    <div className="p-4">
      <div className="flex justify-between mb-4">
        {/* Search Input */}
        <Input
          type="text"
          value={search}
          onChange={(e) => setParams({search:e.target.value,sortby})}
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
            <SelectItem value="issue_slip_no">(Asc)SlipNo</SelectItem>
            <SelectItem value="-issue_slip_no">(Des)SlipNo</SelectItem>
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
            <div className={transitioning ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}>
            <DataTable columns={columns} data={ledgers} />
            </div>

            {/* Pagination Controls */}
            <div className="flex justify-between items-center mt-4">
              <Button
                variant="outline"
                onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                disabled={page === 1 || transitioning}
              >
                Previous
              </Button>

              <span>
                Page {page} of {totalPages}
              </span>

              <Button
                variant="outline"
                onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                disabled={page === totalPages || transitioning}
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
  );
};

export default KarigarJobs;
