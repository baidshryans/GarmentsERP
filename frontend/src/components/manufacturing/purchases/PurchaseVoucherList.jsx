import React, { useState, useEffect } from 'react'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { fetchPurchaseVoucher, fetchCompanies } from "@/services/apiService";
import { useQuery ,useQueryClient,useMutation} from '@tanstack/react-query';
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link, useNavigate } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Printer, Trash2, X } from "lucide-react";
import { openAndPrint } from '@/services/print/utils';
import PurchaseVoucher from '@/services/print/PurchaseVoucherVendor';
import { useToast } from "@/hooks/use-toast";
import { deletePurchaseVoucher } from '../../../services/apiService';
import PurchaseAttachments from './PurchaseAttachments';
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import { useSearchParams } from 'react-router-dom';
import { Table, TableBody, TableHead, TableHeader, TableRow, TableCell } from "@/components/ui/table";
import { useF2Navigate } from "@/hooks/useF2Navigate";

function PurchaseVoucherList({ voucherType = "" }) {
  useF2Navigate(voucherType ? `/purchase/customerpurchase/list/add/?vou_type=${voucherType}` : "/purchase/add/");
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const deleteVoucherMutation = useMutation({
  mutationFn: ({ id }) => deletePurchaseVoucher(id),
  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: ["purchaseVouchers"],
    });
    setShowPanel(false);
    toast({ title: "Purchase voucher deleted successfully" });
  },
  onError: (err) => {
    toast({ title: "Delete failed", description: err.message || "Something went wrong", variant: "destructive" });
  },
});
  const [params,setParams] = useSearchParams()
  const navigate = useNavigate()
  const [page, setPage] = useState(1);
  const [details, setDetails] = useState({ purchasevoucheritems_set: [] }); // Default ordering by 'Name'
  const [showPanel, setShowPanel] = useState(false); // New state for panel visibility
  const [companyInfo, setCompanyInfo] = useState({});

  useEffect(() => {
    fetchCompanies().then((res) => {
      if (res.success) {
        const companies = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
        if (companies.length > 0) {
          const c = companies[0];
          setCompanyInfo({
            company_name: c.company_name,
            company_address: [c.address, c.city, c.pincode].filter(Boolean).join(', '),
            company_phone: c.phone,
            company_email: c.email,
            company_pan: c.pan,
            company_gstin: c.gstin,
            company_tan: c.tan,
            company_cin: c.cin,
          });
        }
      }
    });
  }, []);

  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"";

  const {
    data,            // this will be the normalized result.data (see queryFn below)
    loading,
    isError,
    error,
    isFetching,
  } = useQuery({
    queryKey: ['purchaseVouchers', { search, page, sortby, voucherType }],
    queryFn: async ({ signal }) => {
      const result = await fetchPurchaseVoucher({
        search,
        page,
        ordering: sortby,
        voucher_type: voucherType,
        signal, // optional
      });

      if (!result.success) {
        throw new Error(result.error ?? 'Failed to load purchase vouchers');
      }
      return result;
    },
    keepPreviousData: true,
    staleTime: 1000 * 60 * 2,
    // retry, refetchOnWindowFocus, etc. are also allowed here
  });


  console.log(data);

const totalPages = data?.data?.total_pages ?? 1;
  const handleRowClick = (row) => {
    setDetails(row);
    setShowPanel(true);
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-4">
          <Link to={voucherType ? `/purchase/customerpurchase/list/${row.original.id}` : `/purchase/${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
            <SquarePen className="mr-1" />
          </Link>

          <button
            onClick={() => deleteVoucherMutation.mutate({id:row.original.id})}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-4" />
          </button>
          <button onClick={() => openAndPrint(<PurchaseVoucher data={{ ...row.original, ...companyInfo }} />)}>
            <Printer className="size-4" />
          </button>
          {row.original.voucher_type === "Vendor" && (
            <PurchaseAttachments
              purchaseId={row.original.id}
              billNo={row.original.billno}
            />
          )}
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
      header: "Party Name",
      accessorKey: "ldgr_name",
    },
    {
      header: "Amount",
      accessorKey: "bill_value",
      cell: ({ getValue }) => {
        const v = parseFloat(getValue() || 0);
        return v > 0 ? v.toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—";
      },
    },
    {
      header: "Tax",
      accessorKey: "id",
      id: "tax",
      cell: ({ row }) => {
        const tax = parseFloat(row.original.cgst || 0) + parseFloat(row.original.sgst || 0) + parseFloat(row.original.igst || 0);
        return tax > 0 ? tax.toLocaleString("en-IN", { minimumFractionDigits: 2 }) : "—";
      },
    },
    {
      header: "GW",
      accessorKey: "total_gw",
      cell: ({ getValue }) => getValue() != null ? parseFloat(getValue()).toFixed(3) : "—",
    },
    {
      header: "NW",
      accessorKey: "total_nw",
      cell: ({ getValue }) => getValue() != null ? parseFloat(getValue()).toFixed(3) : "—",
    },
    {
      header: "Stone Wt",
      accessorKey: "total_stone_wt",
      cell: ({ getValue }) => getValue() != null ? parseFloat(getValue()).toFixed(3) : "—",
    },
  ];

  return (
    <ResizablePanelGroup className="min-h-screen h-full" direction="vertical">
      <ResizablePanel defaultSize={showPanel ? 60 : 100}>
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
                  <SelectItem value="billno">(Asc)Billno</SelectItem>
                  <SelectItem value="-billno">(Des)Billno</SelectItem>
                </SelectContent>
              </Select>
              {/* {!showPanel && (
                <Button
                  variant="outline"
                  onClick={() => setShowPanel(true)}
                  className="text-sm"
                >
                  Show Details
                </Button>
              )} */}
           
          </div>

          {loading ? (
            <div>
        
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="w-full h-8 mb-2" />
              ))}
            </div>
          ) : error ? (
            <div>Error: {error}</div>
          ) : (
            <>
              {/* Data Table */}
              <div className={isFetching ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}>
              <DataTable columns={columns} data={data?.data?.results ?? []} rowClick={handleRowClick} />
              </div>

              {/* Pagination Controls */}
              <div className="flex justify-between items-center mt-4">
                <Button
                  variant="outline"
                  onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                  disabled={page === 1 || isFetching}
                >
                  Previous
                </Button>

                <span>
                  Page {page} of {totalPages}
                </span>

                <Button
                  variant="outline"
                  onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                  disabled={page === totalPages || isFetching}
                >
                  Next
                </Button>
              </div>

              <div className="flex justify-end mt-4">
                <Link to={voucherType ? `/purchase/customerpurchase/list/add/?vou_type=${voucherType}` : "/purchase/add/"}>
                  <Button>Add New</Button>
                </Link>
              </div>
            </>
          )}
        </div>
      </ResizablePanel>

      {showPanel && (
        <>
          <ResizableHandle withHandle />
          <ResizablePanel defaultSize={30}>
            {/* Panel header — matches ERP border-b style, no gradient */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b bg-background">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Purchase Details</p>
                <p className="text-sm font-medium text-foreground">{details.billno}</p>
              </div>
              <button
                onClick={() => setShowPanel(false)}
                className="p-1 rounded-md hover:bg-muted transition-colors"
              >
                <X className="size-4 text-muted-foreground" />
              </button>
            </div>

            {/* Detail table */}
            <div className="overflow-auto h-[calc(100%-45px)]">
              <div className="rounded-none border-0 overflow-hidden">
                <Table className="w-full table-fixed text-sm">
                  <TableHeader>
                    <TableRow className="bg-muted/50 hover:bg-muted/50">
                      {["Sl","Date","Packet","Item","Pcs","Ct","Gw","Purity","Fine Wt","Rate","Making","Value","Action"].map((col) => (
                        <TableHead
                          key={col}
                          className="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground whitespace-nowrap border-b"
                        >
                          {col}
                        </TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {details.purchasevoucheritems_set.map((item, idx) => (
                      <React.Fragment key={idx}>
                        {/* Main item row */}
                        <TableRow className={`hover:bg-accent/40 transition-colors ${idx % 2 === 1 ? "bg-muted/20" : ""}`}>
                          <TableCell className="px-3 py-2 text-xs font-medium text-center">{idx + 1}</TableCell>
                          <TableCell className="px-3 py-2 text-xs whitespace-nowrap">{item.date}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-muted-foreground">—</TableCell>
                          <TableCell className="px-3 py-2 text-xs font-semibold text-foreground">{item.item}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center">{item.pcs}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center text-muted-foreground">—</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center font-medium">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center">{item.purity || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center text-muted-foreground">—</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center">{item.making_amt || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center text-muted-foreground">—</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center font-medium text-foreground">
                            {item.item_value != null ? Number(item.item_value).toLocaleString("en-IN") : "—"}
                          </TableCell>
                          <TableCell className="px-2 py-2 text-center">
                            <Button
                              onClick={() => navigate(`/inventory/barcodemanagement/list/add/?bill_no=${encodeURIComponent(details.billno)}&sl_no=${item.sl_no}`)}
                              disabled={!(item.pending_gw > 0)}
                              size="sm"
                              className="whitespace-nowrap text-xs h-7 px-2"
                            >
                              Create Barcode
                            </Button>
                          </TableCell>
                        </TableRow>

                        {/* Sub-detail rows — indented, subtler */}
                        {item.purchasevoucherdetails_set?.map((detail, sub_id) => (
                          <TableRow key={sub_id} className="bg-muted/10 hover:bg-muted/30 transition-colors border-l-2 border-l-border">
                            <TableCell className="px-3 py-1.5 text-xs text-muted-foreground text-center">{detail.sl_no}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-muted-foreground">—</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs">{detail.packet || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-muted-foreground pl-5">{detail.sub_item}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{detail.sub_pcs}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center font-medium">{detail.sub_gw || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{detail.metal_purity || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{detail.fine_wt || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{detail.rate || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center text-muted-foreground">—</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center font-medium">
                              {detail.value != null ? Number(detail.value).toLocaleString("en-IN") : "—"}
                            </TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-muted-foreground">—</TableCell>
                          </TableRow>
                        ))}
                      </React.Fragment>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          </ResizablePanel>
        </>
      )}
    </ResizablePanelGroup>
  );
}

export default PurchaseVoucherList;