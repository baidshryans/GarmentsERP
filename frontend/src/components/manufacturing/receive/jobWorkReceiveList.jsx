import React, { useState, useEffect } from "react";
import { SquarePen, Printer, Trash2, X } from "lucide-react";
import { fetchKarigarIssues, fetchKarigarReceive, getLedgers } from "@/services/apiService";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select";
import { Table, TableBody, TableRow, TableCell } from "@/components/ui/table";
import { Link, useNavigate } from "react-router-dom";
import { DataTable } from "@/table"
import { useToast } from "@/hooks/use-toast";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable"
import { openAndPrint } from "@/services/print/utils";
import ReceiveFromKarigar from "@/services/print/ReceiveFromKariger";
import { deleteJobWorkReceive } from "../../../services/apiService";
import { useSearchParams } from 'react-router-dom';

const KarigarReceive = () => {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate()
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [ordering, setOrdering] = useState("ac_name");
  const [details, setDetails] = useState({ items: [] });
  const [showPanel, setShowPanel] = useState(false); // Changed to false by default
  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"";

  useEffect(() => {
    const fetchLedgers = async () => {
      setLoading(true);
      const result = await fetchKarigarReceive({
        search,
        page,
        ordering:sortby,
      });

      if (result.success) {
        setLedgers(result.data.results);
        setTotalPages(result.data.total_pages);
      } else {
        setError(result.error);
      }
      setLoading(false);
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
          {/* <Button onClick={(e)=>setDetails(row.original)}>Details </Button> */}
          <button
            onClick={() => deleteJobWorkReceive(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="mr-1" />
          </button>
          <button onClick={() => openAndPrint(<ReceiveFromKarigar data={row.original} />)}>
            <Printer className="w-4 h-4" />
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
      header: "Receive Slip Number",
      accessorKey: "receive_slip_no",
    },
     {
      header: "Name",
      accessorKey: "karigar_ldgr_name",
    },


    // {
    //   header: "Issue Slip No",
    //   accessorKey: "issue_slip_no",
    // },

    // {
    //   header: "Customer",
    //   accessorKey: "customer",
    //   cell: ({ row }) => (
    //     <div>
    //    { row.original.items.map(item =>( <div>
    //     {item?.customer_order_item?.order_no?.ldgr_code?.display_name ?? ""}
    //    </div>))}

    //     </div>
    //   ),
    // },
    // {
    //   header: "Order No",
    //   accessorKey: "order_no",
    //   cell: ({ row }) => (
    //     <div>
    //    { row.original.items.map(item =>( <div>
    //     {item?.customer_order_item?.order_no?.order_no ?? ""}
    //    </div>))}

    //     </div>
    //   ),
    // },
  ];

  const itemFields = [
  "packet",
  "issue_pcs",
  "issue_ct",
  "issue_gw",
  "broken_pcs",
  "broken_ct",
  "broken_gw",
  "return_pcs",
  "return_ct",
  "return_gw",
  "balance_pcs",
  "balance_ct",
  "balance_gw",
  "rate",
  "amt"
];

  return (
    <ResizablePanelGroup className="min-h-screen h-full" direction="vertical">
      <ResizablePanel defaultSize={showPanel ? 60 : 100}>
        <div className="max-h-fit p-4">
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
                  <SelectItem value="receive_slip_no">(Asc)SlipNo</SelectItem>
                  <SelectItem value="-receive_slip_no">(Des)SlipNo</SelectItem>
                </SelectContent>
              </Select> 
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
              <DataTable 
                columns={columns} 
                data={ledgers} 
                rowClick={(row) => { 
                  setDetails(row);
                  setShowPanel(true);
                }}
              />

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
          )}
        </div>
      </ResizablePanel>

      {showPanel && (
        <>
          <ResizableHandle />
          <ResizablePanel defaultSize={30}>
            <div className="flex items-center justify-between p-2 bg-gray-50 border-b">
            <br></br>
              <button onClick={() => setShowPanel(false)}>
                <X className="w-5 h-5 text-gray-600 hover:text-red-500" />
              </button>
            </div>
            <div className="overflow-auto h-full">
              <Table className="w-full table-fixed border-collapse text-sm text-center">
                <TableBody>
                  <TableRow className="bg-violet-100 font-semibold">
                    <TableCell className="w-24 px-2 py-2 border">Main SL No</TableCell>
                    <TableCell className="w-28 px-2 py-2 border">pcs</TableCell>
                    <TableCell className="w-16 px-2 py-2 border">gw</TableCell>
                    <TableCell className="w-16 px-2 py-2 border">SL No</TableCell>
                    <TableCell className="w-28 px-2 py-2 border">Item</TableCell>
                    <TableCell className="w-28 px-2 py-2 border">Metal Purity</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Packet</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Issue Pcs</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Issue Ct</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Issue GW</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Broken Pcs</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Broken Ct</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Broken GW</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Return Pcs</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Return Ct</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Return GW</TableCell>
                    <TableCell className="w-28 px-2 py-2 border">Balance Pcs</TableCell>
                    <TableCell className="w-28 px-2 py-2 border">Balance Ct</TableCell>
                    <TableCell className="w-28 px-2 py-2 border">Balance GW</TableCell>
                    <TableCell className="w-24 px-2 py-2 border">Rate</TableCell>
                    <TableCell className="w-28 px-2 py-2 border">Amount</TableCell>
                    <TableCell className="w-32 px-2 py-2 border">Create Barcode</TableCell>
                  </TableRow>

                  {details.items.map((detail, idx) =>
                    detail.details.map((item, subIdx) => (
                      <TableRow key={`${idx}-${subIdx}`} className="bg-gray-100">
                        <TableCell className="w-24 px-2 py-2 border">{idx + 1}</TableCell>
                        <TableCell className="w-28 px-2 py-2 border">{detail.pcs || ''}</TableCell>
                        <TableCell className="w-16 px-2 py-2 border">{detail.gw || ''}</TableCell>
                        <TableCell className="w-16 px-2 py-2 border">{item.sl_no || ''}</TableCell>
                        <TableCell className="w-28 px-2 py-2 border">{item.item || ''}</TableCell>
                        <TableCell className="w-28 px-2 py-2 border">{item.purity || ''}</TableCell>

                        {itemFields.map((key, i) => (
                          <TableCell key={i} className="w-24 px-2 py-2 border text-center">
                            {item[key] ?? ""}
                          </TableCell>
                        ))}
                       
                        {subIdx === 0 && (
                          <TableCell
                            className="w-32 px-2 py-2 border"
                            rowSpan={detail.details.length}
                          >
                            <Button 
                              onClick={() => navigate(`/inventory/barcodemanagement/list/add/?rec_sl_no=${encodeURIComponent(details.receive_slip_no)}&sl_no=${item.sl_no}`)} 
                              disabled={!(item.pending_pcs && item.pending_gw)} 
                            >
                              Create Barcode
                            </Button>
                          </TableCell>
                        )}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
          </ResizablePanel>
        </>
      )}
    </ResizablePanelGroup>
  );
};

export default KarigarReceive;