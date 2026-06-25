import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { fetchHallmarkReceive } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Printer, Trash2, Plus } from "lucide-react";
import { openAndPrint } from '@/services/print/utils';
import ReceiveFromHallmark from '@/services/print/ReceiveFromHallmark';
import { useToast } from "@/hooks/use-toast";
import { deleteHallmarkReceive } from '../../../services/apiService';
import { useSearchParams } from 'react-router-dom';

function HallmarkReceiveAdd() {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [allFy, setAllFy] = useState(false);

  const search = params.get('search') || "";
  const sortby = params.get('sortby') || "";

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      const result = await fetchHallmarkReceive({ search, page, ordering: sortby, allFy });
      if (result.success) {
        setLedgers(result.data.results);
        setTotalPages(result.data.total_pages);
      } else {
        setError(result.error);
      }
      setLoading(false);
    };
    fetchData();
  }, [search, page, sortby, allFy]);

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-4">
          <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => deleteHallmarkReceive(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-4" />
          </button>
          <button onClick={() => openAndPrint(<ReceiveFromHallmark data={row.original} />)}>
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
      accessorKey: "receive_slip_no",
    },
    {
      header: "Name",
      accessorKey: "hallmark_center_name",
    },
    {
      header: "Discount",
      accessorKey: "discount",
    },
    {
      header: "Total Bill",
      accessorKey: "total_bill_value",
    },
  ];

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2 flex-1">
          <Input
            type="text"
            value={search}
            onChange={(e) => setParams({ search: e.target.value, sortby })}
            placeholder="Search hallmark receives..."
            className="max-w-xs"
          />
          <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
            <SelectTrigger className="w-44">
              <span>{sortby ? sortby.replace('-', '↓ ') : 'Sort by'}</span>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="date1">Date (Old first)</SelectItem>
              <SelectItem value="-date1">Date (New first)</SelectItem>
              <SelectItem value="receive_slip_no">Bill No (Asc)</SelectItem>
              <SelectItem value="-receive_slip_no">Bill No (Desc)</SelectItem>
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
            Add Hallmark Receive
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="w-full h-10" />
          ))}
        </div>
      ) : error ? (
        <div className="text-destructive text-sm">Error: {error}</div>
      ) : (
        <>
          <DataTable columns={columns} data={ledgers} />

          <div className="flex items-center justify-between pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
              disabled={page === 1}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

export default HallmarkReceiveAdd;
