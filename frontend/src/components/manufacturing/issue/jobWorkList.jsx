import React, { useState, useEffect } from "react";
import { SquarePen, Printer, Trash2, Plus } from "lucide-react";
import { fetchKarigarIssues, getLedgers } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
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
  const [allFy, setAllFy] = useState(false);

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
        allFy,
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
  }, [search, page, sortby, allFy]);


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
      cell: ({ row }) => {
        const nos = Array.from(new Set(
          (row.original.items ?? [])
            .map(it => it?.customer_order_no || it?.customer_order_item?.order_no?.order_no || "")
            .filter(Boolean)
        ));
        return (
          <div>
            {nos.length === 0 ? "" : nos.map((n, i) => <div key={i}>{n}</div>)}
          </div>
        );
      },
    },
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
              placeholder="Search job work..."
              className="max-w-xs"
            />
            <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
              <SelectTrigger className="w-44">
                <span>{sortby ? sortby.replace('-', '↓ ') : 'Sort by'}</span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date1">Date (Old first)</SelectItem>
                <SelectItem value="-date1">Date (New first)</SelectItem>
                <SelectItem value="issue_slip_no">Slip No (Asc)</SelectItem>
                <SelectItem value="-issue_slip_no">Slip No (Desc)</SelectItem>
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
              Add Job Work
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
            <div className={transitioning ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}>
              <DataTable columns={columns} data={ledgers} />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Button variant="outline" size="sm" onClick={() => setPage((prev) => Math.max(prev - 1, 1))} disabled={page === 1 || transitioning}>
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))} disabled={page === totalPages || transitioning}>
                Next
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default KarigarJobs;
