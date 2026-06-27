import React, { useState, useEffect } from 'react'
import { formatNumber } from '@/lib/format'
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { fetchPurchaseVoucher, fetchCompanies, fetchRetails } from "@/services/apiService";
import { useQuery ,useQueryClient,useMutation} from '@tanstack/react-query';
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Link, useNavigate } from "react-router-dom";
import { DataTable } from "@/table"
import { SquarePen, Printer, Trash2, X, Plus } from "lucide-react";
import { openAndPrint } from '@/services/print/utils';
import PurchaseVoucherVendorPrint from '@/services/print/PurchaseVoucherVendor';
import PurchaseVoucherCustomerPrint from '@/services/print/PurchaseVoucherCustomer';
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
  const [allFy, setAllFy] = useState(false);
  const [details, setDetails] = useState({ purchasevoucheritems_set: [] }); // Default ordering by 'Name'
  const [showPanel, setShowPanel] = useState(false); // New state for panel visibility
  const [companyInfo, setCompanyInfo] = useState({});

  useEffect(() => {
    Promise.all([fetchCompanies(), fetchRetails()]).then(([companyRes, retailRes]) => {
      if (companyRes.success) {
        const companies = Array.isArray(companyRes.data) ? companyRes.data : companyRes.data?.results ?? [];
        if (companies.length > 0) {
          const c = companies[0];
          const retails = retailRes.success ? (Array.isArray(retailRes.data) ? retailRes.data : retailRes.data?.results ?? []) : [];
          const retailCode = sessionStorage.getItem("retail_code");
          const retail = retails.find(r => r.retail_code === retailCode) || retails[0];
          setCompanyInfo({
            company_name: c.company_name,
            company_legal_name: c.legal_name || '',
            company_address: [c.address, c.city, c.pincode].filter(Boolean).join(', '),
            company_phone: c.phone,
            company_email: c.email,
            company_pan: c.pan,
            company_gstin: retail?.gstin_master_str || "",
            company_tan: c.tan,
            company_cin: c.cin,
          });
        }
      }
    });
  }, []);

  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"-date1";

  const {
    data,            // this will be the normalized result.data (see queryFn below)
    loading,
    isError,
    error,
    isFetching,
  } = useQuery({
    queryKey: ['purchaseVouchers', { search, page, sortby, voucherType: voucherType || "Vendor", allFy }],
    queryFn: async ({ signal }) => {
      const result = await fetchPurchaseVoucher({
        search,
        page,
        ordering: sortby,
        voucher_type: voucherType || "Vendor",
        allFy,
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
            <SquarePen className="size-4" />
          </Link>

          <button
            onClick={() => deleteVoucherMutation.mutate({id:row.original.id})}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-4" />
          </button>
          <button onClick={() => {
            const PrintComp = row.original.voucher_type === "Customer" ? PurchaseVoucherCustomerPrint : PurchaseVoucherVendorPrint;
            openAndPrint(<PrintComp data={{ ...row.original, ...companyInfo }} />);
          }}>
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
        return v > 0 ? formatNumber(v, { minDecimals: 2 }) : "—";
      },
    },
    {
      header: "Tax",
      accessorKey: "id",
      id: "tax",
      cell: ({ row }) => {
        const tax = parseFloat(row.original.cgst || 0) + parseFloat(row.original.sgst || 0) + parseFloat(row.original.igst || 0);
        return tax > 0 ? formatNumber(tax, { minDecimals: 2 }) : "—";
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
        <div className="flex flex-col gap-4 p-4">
          {/* Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2 flex-1">
              <Input
                type="text"
                value={search}
                onChange={(e) => setParams({ search: e.target.value, sortby })}
                placeholder="Search purchase vouchers..."
                className="max-w-xs"
              />
              <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
                <SelectTrigger className="w-44">
                  <span>{sortby ? sortby.replace('-', '↓ ') : 'Sort by'}</span>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="date1">Date (Old first)</SelectItem>
                  <SelectItem value="-date1">Date (New first)</SelectItem>
                  <SelectItem value="billno">Bill No (Asc)</SelectItem>
                  <SelectItem value="-billno">Bill No (Desc)</SelectItem>
                </SelectContent>
              </Select>
              <Label className="flex items-center gap-2 text-sm whitespace-nowrap cursor-pointer">
                <Checkbox checked={allFy} onCheckedChange={(v) => { setAllFy(!!v); setPage(1); }} />
                All years
              </Label>
            </div>
            <Link to={voucherType ? `/purchase/customerpurchase/list/add/?vou_type=${voucherType}` : "/purchase/add/"}>
              <Button size="sm" className="gap-1.5">
                <Plus className="size-4" />
                Add Purchase
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
            <div className="text-destructive text-sm">Error: {String(error)}</div>
          ) : (
            <>
              <div className={isFetching ? "opacity-50 pointer-events-none transition-opacity duration-150" : "transition-opacity duration-150"}>
                <DataTable columns={columns} data={data?.data?.results ?? []} rowClick={handleRowClick} />
              </div>

              <div className="flex items-center justify-between pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
                  disabled={page === 1 || isFetching}
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
                  disabled={page === totalPages || isFetching}
                >
                  Next
                </Button>
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
                    {(details.purchasevoucherdetails_set || []).filter(d => !d.main_item).map((detail, dIdx) => (
                      <TableRow key={`direct-${dIdx}`} className={`hover:bg-accent/40 transition-colors ${dIdx % 2 === 1 ? "bg-muted/20" : ""}`}>
                        <TableCell className="px-3 py-2 text-xs font-medium text-center">{(details.purchasevoucheritems_set?.length || 0) + dIdx + 1}</TableCell>
                        <TableCell className="px-3 py-2 text-xs whitespace-nowrap">{detail.date || details.date1 || "—"}</TableCell>
                        <TableCell className="px-3 py-2 text-xs">{detail.packet || "—"}</TableCell>
                        <TableCell className="px-3 py-2 text-xs font-semibold text-foreground">{detail.sub_item_name || detail.sub_item || "—"}</TableCell>
                        <TableCell className="px-3 py-2 text-xs text-center">{detail.sub_pcs ?? "—"}</TableCell>
                        <TableCell className="px-3 py-2 text-xs text-center">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                        <TableCell className="px-3 py-2 text-xs text-center font-medium">{detail.sub_gw || "—"}</TableCell>
                        <TableCell className="px-3 py-2 text-xs text-center">{detail.metal_purity || "—"}</TableCell>
                        <TableCell className="px-3 py-2 text-xs text-center">{detail.fine_wt || "—"}</TableCell>
                        <TableCell className="px-3 py-2 text-xs text-center">{detail.rate || "—"}</TableCell>
                        <TableCell className="px-3 py-2 text-xs text-center text-muted-foreground">—</TableCell>
                        <TableCell className="px-3 py-2 text-xs text-center font-medium text-foreground">
                          {detail.value != null ? formatNumber(detail.value) : "—"}
                        </TableCell>
                        <TableCell className="px-2 py-2 text-muted-foreground text-center">—</TableCell>
                      </TableRow>
                    ))}
                    {details.purchasevoucheritems_set.map((item, idx) => (
                      <React.Fragment key={idx}>
                        {/* Main item row */}
                        <TableRow className={`hover:bg-accent/40 transition-colors ${idx % 2 === 1 ? "bg-muted/20" : ""}`}>
                          <TableCell className="px-3 py-2 text-xs font-medium text-center">{idx + 1}</TableCell>
                          <TableCell className="px-3 py-2 text-xs whitespace-nowrap">{item.date}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-muted-foreground">—</TableCell>
                          <TableCell className="px-3 py-2 text-xs font-semibold text-foreground">{item.item_name || item.item}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center">{item.pcs}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center text-muted-foreground">—</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center font-medium">{item.gw != null ? parseFloat(item.gw).toFixed(3) : "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center">{item.purity || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center text-muted-foreground">—</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center">{item.making_amt || "—"}</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center text-muted-foreground">—</TableCell>
                          <TableCell className="px-3 py-2 text-xs text-center font-medium text-foreground">
                            {item.item_value != null ? formatNumber(item.item_value) : "—"}
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
                            <TableCell className="px-3 py-1.5 text-xs text-muted-foreground pl-5">{detail.sub_item_name || detail.sub_item}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{detail.sub_pcs}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center font-medium">{detail.sub_gw || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{detail.metal_purity || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{detail.fine_wt || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center">{detail.rate || "—"}</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center text-muted-foreground">—</TableCell>
                            <TableCell className="px-3 py-1.5 text-xs text-center font-medium">
                              {detail.value != null ? formatNumber(detail.value) : "—"}
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