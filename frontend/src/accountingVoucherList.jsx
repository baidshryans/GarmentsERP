import React, { useState, useEffect } from "react";
import { SquarePen, Printer, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { useToast } from "@/hooks/use-toast";
import { deleteJournalentry,fetchAccountingVoucher} from "./services/apiService";
import { useSearchParams,useParams } from 'react-router-dom';
import { useF2Navigate } from "@/hooks/useF2Navigate";
import { openAndPrint } from "@/services/print/utils";
import AccountingVoucher from "@/services/print/AccouuntingVoucher";
import VoucherAttachments from "@/components/FinancialAccounting/vouchers/VoucherAttachments";

const AccountingVoucherList = () => {
  const { toast } = useToast();
  const {journal_type}=useParams();
  useF2Navigate(`/accounting/AddJournal/${journal_type}/add`);
  const [params , setParams]=useSearchParams();
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
    const result = await fetchAccountingVoucher({
      search,
      page,
      ordering: sortby,
      voucher_type: journal_type || "",
    });

    if (result.success) {
      setLedgers(result.data.results);
      setTotalPages(result.data.total_pages);
      setError("");
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  fetchLedgers();
}, [search, page, sortby, journal_type]);


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
            onClick={() => deleteJournalentry(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="mr-1" />
          </button>
          <button onClick={() => openAndPrint(<AccountingVoucher data={row.original} />)}>
            <Printer className="w-4 h-4" />
          </button>
          <VoucherAttachments
            voucherId={row.original.id}
            voucherNo={row.original.voucher_no}
          />
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
      accessorKey: "voucher_no",
    },

     {
      header: "Voucher Type",
      accessorKey: "voucher_type",
    },


  ];

  return (
    <div className="p-4">
      <div className="flex justify-between mb-4">
        {/* Search Input */}
        <Input
          type="text"
          value={search}
          onChange={(e) => setParams({search:e.target.value,sortby,journal_type})}
          placeholder="Search..."
          className="max-w-sm"
        />

        <Select value={sortby} onValueChange={(value)=>setParams({search,sortby:value,journal_type})}>
          <SelectTrigger className="max-w-sm">
            <span>Sort By</span>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="-date">(New)Date</SelectItem>
            <SelectItem value="date">(old)Date</SelectItem>
            <SelectItem value="voucher_no">(Asc)BillNo</SelectItem>
            <SelectItem value="-voucher_no">(Des)BillNo</SelectItem>
           
          </SelectContent>
        </Select>
      </div>

      {(loading) ?

        <div>
          <h1 className="text-2xl mb-4"></h1>
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
  );
};

export default AccountingVoucherList;