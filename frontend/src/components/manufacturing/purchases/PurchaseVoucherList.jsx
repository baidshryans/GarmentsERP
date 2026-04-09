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

function PurchaseVoucherList({ voucherType = "" }) {
  const queryClient = useQueryClient();
  const deleteVoucherMutation = useMutation({
  mutationFn: ({ id }) => deletePurchaseVoucher(id),   // your API call
  onSuccess: () => {
    queryClient.invalidateQueries({
      queryKey: ["purchaseVouchers"],
    });
  },
  onError: (err) => {
    toast.error(err.message || "Delete failed");
  },
});
  const { toast } = useToast();
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
          <Link to={`${row.original.id}`} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center">
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
                <Link to={voucherType ? `add/?vou_type=${voucherType}` : "add/"}>
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
            <div className="flex items-center justify-between p-2 bg-gray-50">
              <h2 className="font-semibold"></h2>
              <button onClick={() => setShowPanel(false)}>
                <X className="w-5 h-5 text-gray-600 hover:text-red-500" />
              </button>
            </div>
            <div className="overflow-auto h-full">
              <Table className="w-full table-fixed border-collapse">
                <TableBody>
                  <TableRow className="bg-violet-100">
                    <TableCell className="w-20 px-4 py-2 border">Sl No</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Date</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Packet</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Item</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Pcs</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Ct</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Gw</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Size</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Purity</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Loss</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Tunch</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Fine wt</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Rate</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Making</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Value</TableCell>
                    <TableCell className="w-20 px-4 py-2 border">Remarks</TableCell>
                    <TableCell className="w-32 px-4 py-2 border">Create Barcode</TableCell>
                  </TableRow>

                  <React.Fragment>
                    {details.purchasevoucheritems_set.map((item, idx) => (
                      <React.Fragment key={idx}>
                        <TableRow className="bg-gray-100">
                          <TableCell className="w-20 px-4 py-2 border">{idx + 1}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.date}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border"></TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.item}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.pcs}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border"></TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.gw}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.size}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.purity}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border"></TableCell>
                          <TableCell className="w-20 px-4 py-2 border"></TableCell>
                          <TableCell className="w-20 px-4 py-2 border"></TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.making_amt}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border"></TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.item_value}</TableCell>
                          <TableCell className="w-20 px-4 py-2 border">{item.remarks}</TableCell>
                          <TableCell className="w-32 px-2 py-2 border">
                            <Button onClick={() => navigate(`/inventory/barcodemanagement/list/add/?bill_no=${encodeURIComponent(details.billno)}&sl_no=${item.sl_no}`)} disabled={!(item.pending_pcs && item.pending_gw)} >Create Barcode</Button>
                          </TableCell>
                        </TableRow>
                        {item.purchasevoucherdetails_set?.map((detail, sub_id) => (
                          <TableRow key={sub_id} className="bg-gray-100">
                            <TableCell className="w-20 px-4 py-2 border">{detail.sl_no}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border"></TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.packet}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.sub_item}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.sub_pcs}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{Number(detail.sub_ct || 0).toFixed(3)}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.sub_gw}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border"></TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.metal_purity}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.loss}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.tunch}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.fine_wt}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.rate}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border"></TableCell>
                            <TableCell className="w-20 px-4 py-2 border">{detail.value}</TableCell>
                            <TableCell className="w-20 px-4 py-2 border"></TableCell>
                            <TableCell className="w-20 px-4 py-2 border"></TableCell>
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