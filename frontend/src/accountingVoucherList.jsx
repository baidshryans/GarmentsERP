import React, { useState, useEffect } from "react";
import { SquarePen, Printer, Trash2, Ban } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Link } from "react-router-dom";
import { DataTable } from "@/table"
import { useToast } from "@/hooks/use-toast";
import { deleteJournalentry, fetchAccountingVoucher, cancelJournalEntry } from "./services/apiService";
import { fetchCompanies, fetchRetails } from "@/services/apiService";
import { useSearchParams, useParams, useNavigate } from 'react-router-dom';

const VALID_JOURNAL_TYPES = ["JRNL", "RCPT", "PMNT", "CONTRA"];
import { useF2Navigate } from "@/hooks/useF2Navigate";
import { openAndPrint } from "@/services/print/utils";
import AccountingVoucher from "@/services/print/AccountingVoucher";
import PaymentVoucherSlip  from "@/services/print/PaymentVoucherSlip";
import { isPmnt } from "@/services/print/printHelpers";
import VoucherAttachments from "@/components/FinancialAccounting/vouchers/VoucherAttachments";

const AccountingVoucherList = () => {
  const { toast } = useToast();
  const {journal_type}=useParams();
  const navigate = useNavigate();
  const isValidType = VALID_JOURNAL_TYPES.includes(journal_type);

  useF2Navigate(`/accounting/${journal_type}/add`);

  // Guard against legacy / malformed URLs (e.g. /accounting/AddJournal/JRNL).
  // Use an effect so all subsequent hooks still run in stable order.
  useEffect(() => {
    if (!isValidType) navigate("/accounting", { replace: true });
  }, [isValidType, navigate]);
  const [params , setParams]=useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [ordering, setOrdering] = useState("ac_name"); // Default ordering by 'Name'
  const [companyInfo, setCompanyInfo] = useState({});
  const [refreshCount, setRefreshCount] = useState(0);
  const [allFy, setAllFy] = useState(false);

  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"";


 useEffect(() => {
    Promise.all([fetchCompanies(), fetchRetails()]).then(([companyRes, retailRes]) => {
      if (companyRes.success) {
        const companies = Array.isArray(companyRes.data) ? companyRes.data : companyRes.data?.results ?? [];
        if (companies.length > 0) {
          const c = companies[0];
          const retails = retailRes.success ? (Array.isArray(retailRes.data) ? retailRes.data : retailRes.data?.results ?? []) : [];
          const activeRetailCode = sessionStorage.getItem("retail_code") || "";
          const retail = retails.find((r) => r.retail_code === activeRetailCode);
          setCompanyInfo({
            company_name: c.company_name,
            company_address: [c.address, c.city, c.pincode].filter(Boolean).join(', '),
            company_phone: c.phone,
            company_email: c.email,
            company_pan: c.pan,
            company_gstin:      retail?.gstin_master_str || c.gstin || "",
            company_legal_name: c.legal_name || "",
            company_tan: c.tan,
            company_cin: c.cin,
          });
        }
      }
    })
    .catch((err) => console.error("Failed to load company/retail info:", err));
  }, []);

 useEffect(() => {
  const fetchLedgers = async () => {
    if (ledgers.length === 0) setLoading(true);
    else setTransitioning(true);

    const result = await fetchAccountingVoucher({
      search,
      page,
      ordering: sortby,
      voucher_type: journal_type || "",
      allFy,
    });

    if (result.success) {
      setLedgers(result.data.results);
      setTotalPages(result.data.total_pages);
      setError("");
    } else {
      setError(result.error);
    }
    setLoading(false);
    setTransitioning(false);
  };

  fetchLedgers();
}, [search, page, sortby, journal_type, refreshCount, allFy]);


  // Column definition
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
            onClick={() => deleteJournalentry(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-4" />
          </button>
          {row.original.status === 'posted' && (
            <button
              title="Cancel voucher"
              onClick={async () => {
                if (!window.confirm(`Cancel voucher ${row.original.voucher_no}? This will reverse its accounting effects.`)) return;
                const res = await cancelJournalEntry(row.original.id);
                if (res.success) {
                  toast({ title: "Voucher cancelled", description: `${row.original.voucher_no} has been cancelled.` });
                  setRefreshCount(c => c + 1);
                } else {
                  const msg = typeof res.error === 'object' ? JSON.stringify(res.error) : res.error;
                  toast({ title: "Cancel failed", description: msg, variant: "destructive" });
                }
              }}
              className="p-1.5 rounded text-orange-500 hover:bg-orange-50 transition-colors flex items-center"
            >
              <Ban className="size-4" />
            </button>
          )}
          <button
            onClick={() => {
              const printData = { ...row.original, ...companyInfo };
              openAndPrint(
                isPmnt(row.original.voucher_type)
                  ? <PaymentVoucherSlip data={printData} />
                  : <AccountingVoucher  data={printData} />
              );
            }}
          >
            <Printer className="size-4" />
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
      header: "Voucher No",
      accessorKey: "voucher_no",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span>{row.original.voucher_no}</span>
          {row.original.status === 'cancelled' && (
            <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-gray-100 text-gray-500 border border-gray-300">
              Cancelled
            </span>
          )}
        </div>
      ),
    },
    {
      header: "Party Name",
      id: "party_name",
      cell: ({ row }) => {
        const details = row.original.voucher_details || [];
        const names = [...new Set(details.map(d => d.account_name).filter(Boolean))];
        return names.join(", ");
      },
    },
    {
      header: "Narration",
      accessorKey: "narration",
    },
    {
      header: "Amount",
      id: "amount",
      cell: ({ row }) => {
        const details = row.original.voucher_details || [];
        const total = details.reduce(
          (sum, d) => sum + (Number(d.debit) || 0),
          0
        );
        return total.toFixed(2);
      },
    },
  ];

  if (!isValidType) return null;

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
        <Label className="flex items-center gap-2 text-sm whitespace-nowrap cursor-pointer">
          <Checkbox checked={allFy} onCheckedChange={(v) => { setAllFy(!!v); setPage(1); }} />
          All years
        </Label>
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

export default AccountingVoucherList;
