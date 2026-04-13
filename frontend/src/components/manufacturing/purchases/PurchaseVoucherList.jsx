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
import { Table, TableBody, TableRow, TableCell } from "@/components/ui/table";
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
            <Trash2 className="mr-1" />
          </button>
          <button onClick={() => openAndPrint(<PurchaseVoucher data={{ ...row.original, ...companyInfo }} />)}>
            <Printer />
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
      header: "Place of supply",
      accessorKey: "pos_name",
    },
    // {
    //   header: "Bill amount ",
    //   accessorKey: "bill_value",
    // },
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
              <DataTable columns={columns} data={data?.data?.results ?? []} rowClick={handleRowClick} />

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
          <ResizableHandle />
          <ResizablePanel defaultSize={30}>
            <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-b">
              <h2 className="font-bold text-lg text-gray-800">Purchase Details</h2>
              <button
                onClick={() => setShowPanel(false)}
                className="p-1 hover:bg-gray-200 rounded-md transition-colors"
              >
                <X className="w-5 h-5 text-gray-600 hover:text-red-600" />
              </button>
            </div>
            <div className="overflow-auto h-full bg-white">
              <Table className="w-full table-fixed border-collapse">
                <TableBody>
                  <TableRow className="bg-gradient-to-r from-indigo-600 to-blue-600 sticky top-0 z-10">
                    <TableCell className="w-12 px-3 py-3 border text-white font-semibold text-center">Sl</TableCell>
                    <TableCell className="w-20 px-3 py-3 border text-white font-semibold">Date</TableCell>
                    <TableCell className="w-20 px-3 py-3 border text-white font-semibold">Packet</TableCell>
                    <TableCell className="w-24 px-3 py-3 border text-white font-semibold">Item</TableCell>
                    <TableCell className="w-14 px-3 py-3 border text-white font-semibold text-center">Pcs</TableCell>
                    <TableCell className="w-14 px-3 py-3 border text-white font-semibold text-center">Ct</TableCell>
                    <TableCell className="w-14 px-3 py-3 border text-white font-semibold text-center">Gw</TableCell>
                    <TableCell className="w-16 px-3 py-3 border text-white font-semibold">Size</TableCell>
                    <TableCell className="w-16 px-3 py-3 border text-white font-semibold text-center">Purity</TableCell>
                    <TableCell className="w-14 px-3 py-3 border text-white font-semibold text-center">Loss</TableCell>
                    <TableCell className="w-14 px-3 py-3 border text-white font-semibold text-center">Tunch</TableCell>
                    <TableCell className="w-16 px-3 py-3 border text-white font-semibold text-center">Fine wt</TableCell>
                    <TableCell className="w-16 px-3 py-3 border text-white font-semibold text-center">Rate</TableCell>
                    <TableCell className="w-16 px-3 py-3 border text-white font-semibold text-center">Making</TableCell>
                    <TableCell className="w-16 px-3 py-3 border text-white font-semibold text-center">Value</TableCell>
                    <TableCell className="w-20 px-3 py-3 border text-white font-semibold">Remarks</TableCell>
                    <TableCell className="w-32 px-3 py-3 border text-white font-semibold text-center">Action</TableCell>
                  </TableRow>

                  <React.Fragment>
                    {details.purchasevoucheritems_set.map((item, idx) => (
                      <React.Fragment key={idx}>
                        <TableRow className="bg-blue-50 hover:bg-blue-100 transition-colors border-b-2 border-blue-200">
                          <TableCell className="w-12 px-3 py-3 border font-semibold text-blue-700 text-center">{idx + 1}</TableCell>
                          <TableCell className="w-20 px-3 py-3 border text-sm">{item.date}</TableCell>
                          <TableCell className="w-20 px-3 py-3 border text-sm text-gray-600">—</TableCell>
                          <TableCell className="w-24 px-3 py-3 border font-semibold text-gray-800">{item.item}</TableCell>
                          <TableCell className="w-14 px-3 py-3 border text-center text-sm">{item.pcs}</TableCell>
                          <TableCell className="w-14 px-3 py-3 border text-center text-sm text-gray-600">—</TableCell>
                          <TableCell className="w-14 px-3 py-3 border text-center font-medium">{item.gw}</TableCell>
                          <TableCell className="w-16 px-3 py-3 border text-sm">{item.size || "—"}</TableCell>
                          <TableCell className="w-16 px-3 py-3 border text-center text-sm">{item.purity}</TableCell>
                          <TableCell className="w-14 px-3 py-3 border text-center text-sm text-gray-600">—</TableCell>
                          <TableCell className="w-14 px-3 py-3 border text-center text-sm text-gray-600">—</TableCell>
                          <TableCell className="w-16 px-3 py-3 border text-center text-sm text-gray-600">—</TableCell>
                          <TableCell className="w-16 px-3 py-3 border text-center text-sm">{item.making_amt || "—"}</TableCell>
                          <TableCell className="w-16 px-3 py-3 border text-center text-sm text-gray-600">—</TableCell>
                          <TableCell className="w-16 px-3 py-3 border text-center font-medium text-green-700">{item.item_value}</TableCell>
                          <TableCell className="w-20 px-3 py-3 border text-xs text-gray-600">{item.remarks || "—"}</TableCell>
                          <TableCell className="w-32 px-2 py-3 border text-center">
                            <Button
                              onClick={() => navigate(`/inventory/barcodemanagement/list/add/?bill_no=${encodeURIComponent(details.billno)}&sl_no=${item.sl_no}`)}
                              disabled={!(item.pending_gw > 0)}
                              className="whitespace-nowrap text-xs"
                              size="sm"
                            >
                              Create Barcode
                            </Button>
                          </TableCell>
                        </TableRow>
                        {item.purchasevoucherdetails_set?.map((detail, sub_id) => (
                          <TableRow key={sub_id} className="bg-gray-50 hover:bg-gray-100 transition-colors">
                            <TableCell className="w-12 px-3 py-2 border text-xs text-gray-600 text-center">  {detail.sl_no}</TableCell>
                            <TableCell className="w-20 px-3 py-2 border text-xs text-gray-600">—</TableCell>
                            <TableCell className="w-20 px-3 py-2 border text-xs">{detail.packet}</TableCell>
                            <TableCell className="w-24 px-3 py-2 border text-xs text-gray-700">{detail.sub_item}</TableCell>
                            <TableCell className="w-14 px-3 py-2 border text-center text-xs">{detail.sub_pcs}</TableCell>
                            <TableCell className="w-14 px-3 py-2 border text-center text-xs">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                            <TableCell className="w-14 px-3 py-2 border text-center text-xs font-medium">{detail.sub_gw}</TableCell>
                            <TableCell className="w-16 px-3 py-2 border text-xs text-gray-600">—</TableCell>
                            <TableCell className="w-16 px-3 py-2 border text-center text-xs">{detail.metal_purity}</TableCell>
                            <TableCell className="w-14 px-3 py-2 border text-center text-xs">{detail.loss || "—"}</TableCell>
                            <TableCell className="w-14 px-3 py-2 border text-center text-xs">{detail.tunch || "—"}</TableCell>
                            <TableCell className="w-16 px-3 py-2 border text-center text-xs">{detail.fine_wt || "—"}</TableCell>
                            <TableCell className="w-16 px-3 py-2 border text-center text-xs">{detail.rate || "—"}</TableCell>
                            <TableCell className="w-16 px-3 py-2 border text-center text-xs text-gray-600">—</TableCell>
                            <TableCell className="w-16 px-3 py-2 border text-center text-xs font-medium text-green-600">{detail.value}</TableCell>
                            <TableCell className="w-20 px-3 py-2 border text-xs text-gray-600">—</TableCell>
                            <TableCell className="w-32 px-3 py-2 border text-xs text-gray-600">—</TableCell>
                          </TableRow>
                        ))}
                      </React.Fragment>
                    ))}
                  </React.Fragment>
                </TableBody>
              </Table>
            </div>
          </ResizablePanel>
        </>
      )}
    </ResizablePanelGroup>
  );
}

export default PurchaseVoucherList;