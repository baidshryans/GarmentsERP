import React, { useState, useEffect } from "react";
import { SquarePen, Printer, Trash2, X, Plus } from "lucide-react";
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
import BarcodeDetailsModal from "./BarcodeDetailsModal";

const KarigarReceive = () => {
  const { toast } = useToast();
  const [params, setParams] = useSearchParams();
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [transitioning, setTransitioning] = useState(false);
  const navigate = useNavigate()
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [ordering, setOrdering] = useState("ac_name");
  const [details, setDetails] = useState({ items: [] });
  const [showPanel, setShowPanel] = useState(false); // Changed to false by default
  const search=params.get('search')||"";
  const sortby=params.get('sortby')||"";
  const [barcodeModalOpen, setBarcodeModalOpen] = useState(false);
  const [selectedBarcodeItem, setSelectedBarcodeItem] = useState(null);

  useEffect(() => {
    const fetchLedgers = async () => {
      if (ledgers.length === 0) setLoading(true);
      else setTransitioning(true);
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
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => deleteJobWorkReceive(row.original.id, toast)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-4" />
          </button>
          <button onClick={() => openAndPrint(<ReceiveFromKarigar data={row.original} />)}>
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

  return (
    <ResizablePanelGroup className="min-h-screen h-full" direction="vertical">
      <ResizablePanel defaultSize={showPanel ? 60 : 100}>
        <div className="max-h-fit p-4">
          <div className="flex flex-col gap-4">
            {/* Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2 flex-1">
                <Input
                  type="text"
                  value={search}
                  onChange={(e) => setParams({ search: e.target.value, sortby })}
                  placeholder="Search job work receive..."
                  className="max-w-xs"
                />
                <Select value={sortby} onValueChange={(value) => setParams({ search, sortby: value })}>
                  <SelectTrigger className="w-44">
                    <span>{sortby ? sortby.replace('-', '↓ ') : 'Sort by'}</span>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="date1">Date (Old first)</SelectItem>
                    <SelectItem value="-date1">Date (New first)</SelectItem>
                    <SelectItem value="receive_slip_no">Slip No (Asc)</SelectItem>
                    <SelectItem value="-receive_slip_no">Slip No (Desc)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Link to="add/">
                <Button size="sm" className="gap-1.5">
                  <Plus className="size-4" />
                  Add Job Work Receive
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
                  <DataTable
                    columns={columns}
                    data={ledgers}
                    rowClick={(row) => {
                      setDetails(row);
                      setShowPanel(true);
                    }}
                  />
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
      </ResizablePanel>

      {showPanel && (
        <>
          <ResizableHandle />
          <ResizablePanel defaultSize={30}>
            <div className="flex items-center justify-between p-2 bg-gray-50 border-b">
            <br></br>
              <button onClick={() => setShowPanel(false)}>
                <X className="size-5 text-gray-600 hover:text-red-500" />
              </button>
            </div>
            <div className="overflow-auto h-full">
              <Table className="w-full border-collapse text-[12.5px]">
                <TableBody>
                  {/* Group header row */}
                  <TableRow className="hover:bg-transparent">
                    <TableCell colSpan={5} className="px-3 py-2.5 border bg-slate-100 text-slate-600 text-[11px] font-semibold uppercase tracking-wider text-center">Received piece</TableCell>
                    <TableCell colSpan={3} className="px-3 py-2.5 border bg-slate-100 text-slate-600 text-[11px] font-semibold uppercase tracking-wider text-center">Stone / Sub-item</TableCell>
                    <TableCell colSpan={3} className="px-3 py-2.5 border bg-[hsl(242_64%_95%)] text-[hsl(242_64%_38%)] text-[11px] font-semibold uppercase tracking-wider text-center">Issued</TableCell>
                    <TableCell colSpan={3} className="px-3 py-2.5 border bg-[hsl(242_64%_97.5%)] text-[hsl(242_64%_38%)] text-[11px] font-semibold uppercase tracking-wider text-center">Broken</TableCell>
                    <TableCell colSpan={3} className="px-3 py-2.5 border bg-[hsl(242_64%_95%)] text-[hsl(242_64%_38%)] text-[11px] font-semibold uppercase tracking-wider text-center">Returned</TableCell>
                    <TableCell colSpan={3} className="px-3 py-2.5 border bg-[hsl(242_64%_97.5%)] text-[hsl(242_64%_38%)] text-[11px] font-semibold uppercase tracking-wider text-center">Balance</TableCell>
                    <TableCell colSpan={2} className="px-3 py-2.5 border bg-slate-100 text-slate-600 text-[11px] font-semibold uppercase tracking-wider text-center">Value</TableCell>
                    <TableCell className="px-3 py-2.5 border bg-slate-100 text-slate-600 text-[11px] font-semibold uppercase tracking-wider text-center w-32">Action</TableCell>
                  </TableRow>

                  {/* Sub-header row */}
                  <TableRow className="hover:bg-transparent bg-slate-50">
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-center">Sl</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Item</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Purity</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right">Pcs</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right">GW</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-center">#</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Item</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">Packet</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Pcs</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Ct</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">GW</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Pcs</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Ct</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">GW</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Pcs</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">Ct</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(220_30%_97.5%)]">GW</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Pcs</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">Ct</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right bg-[hsl(242_30%_97.5%)]">GW</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right">Rate</TableCell>
                    <TableCell className="px-3 py-2 border text-[11px] font-semibold uppercase tracking-wider text-muted-foreground text-right">Amount</TableCell>
                    <TableCell className="px-3 py-2 border" />
                  </TableRow>

                  {(() => {
                    const stageA = "bg-[hsl(220_30%_97.5%)]";
                    const stageB = "bg-[hsl(242_30%_97.5%)]";
                    const lossText = "text-[hsl(0_65%_47%)] font-semibold";
                    const muted = "text-slate-400";
                    const fmt = (n, dp) => {
                      const num = parseFloat(n);
                      if (!Number.isFinite(num)) return "�";
                      return dp === 0 ? String(Math.round(num)) : num.toFixed(dp);
                    };
                    const totals = {
                      issue_pcs: 0, issue_ct: 0, issue_gw: 0,
                      broken_pcs: 0, broken_ct: 0, broken_gw: 0,
                      return_pcs: 0, return_ct: 0, return_gw: 0,
                      balance_pcs: 0, balance_ct: 0, balance_gw: 0,
                      amt: 0,
                    };
                    let subItemCount = 0;
                    const rendered = [];

                    (details.items || []).forEach((detail, idx) => {
                      const subRows = detail.details || [];
                      subRows.forEach((item, subIdx) => {
                        const num = (k) => {
                          const v = parseFloat(item[k]);
                          return Number.isFinite(v) ? v : 0;
                        };
                        Object.keys(totals).forEach((k) => { totals[k] += num(k); });
                        subItemCount += 1;
                        const brokenPcs = num('broken_pcs'), brokenCt = num('broken_ct'), brokenGw = num('broken_gw');
                        const lossCls = (val, base) => `px-3 py-2.5 border text-right tabular-nums ${base} ${val > 0 ? lossText : muted}`;
                        const cls = (val, base) => `px-3 py-2.5 border text-right tabular-nums ${base} ${val > 0 ? "" : muted}`;

                        rendered.push(
                          <TableRow key={`${idx}-${subIdx}`} className="hover:bg-slate-50/60">
                            {subIdx === 0 && (
                              <>
                                <TableCell rowSpan={subRows.length} className="px-3 py-2.5 border text-center font-semibold align-middle">{idx + 1}</TableCell>
                                <TableCell rowSpan={subRows.length} className="px-3 py-2.5 border align-middle font-medium">{detail.item || '�'}</TableCell>
                                <TableCell rowSpan={subRows.length} className="px-3 py-2.5 border align-middle">
                                  {detail.purity ? <span className="inline-block px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[11px] font-medium">{detail.purity}</span> : '�'}
                                </TableCell>
                                <TableCell rowSpan={subRows.length} className="px-3 py-2.5 border text-right tabular-nums align-middle">{fmt(detail.pcs, 0)}</TableCell>
                                <TableCell rowSpan={subRows.length} className="px-3 py-2.5 border text-right tabular-nums align-middle">{fmt(detail.gw, 3)}</TableCell>
                              </>
                            )}
                            <TableCell className="px-3 py-2.5 border text-center">{item.sl_no ?? ''}</TableCell>
                            <TableCell className="px-3 py-2.5 border">{item.item || '�'}</TableCell>
                            <TableCell className="px-3 py-2.5 border">{item.packet || '�'}</TableCell>
                            <TableCell className={cls(num('issue_pcs'), stageA)}>{fmt(item.issue_pcs, 0)}</TableCell>
                            <TableCell className={cls(num('issue_ct'), stageA)}>{fmt(item.issue_ct, 3)}</TableCell>
                            <TableCell className={cls(num('issue_gw'), stageA)}>{fmt(item.issue_gw, 3)}</TableCell>
                            <TableCell className={lossCls(brokenPcs, stageB)}>{fmt(item.broken_pcs, 0)}</TableCell>
                            <TableCell className={lossCls(brokenCt, stageB)}>{fmt(item.broken_ct, 3)}</TableCell>
                            <TableCell className={lossCls(brokenGw, stageB)}>{fmt(item.broken_gw, 3)}</TableCell>
                            <TableCell className={cls(num('return_pcs'), stageA)}>{fmt(item.return_pcs, 0)}</TableCell>
                            <TableCell className={cls(num('return_ct'), stageA)}>{fmt(item.return_ct, 3)}</TableCell>
                            <TableCell className={cls(num('return_gw'), stageA)}>{fmt(item.return_gw, 3)}</TableCell>
                            <TableCell className={cls(num('balance_pcs'), stageB)}>{fmt(item.balance_pcs, 0)}</TableCell>
                            <TableCell className={cls(num('balance_ct'), stageB)}>{fmt(item.balance_ct, 3)}</TableCell>
                            <TableCell className={cls(num('balance_gw'), stageB)}>{fmt(item.balance_gw, 3)}</TableCell>
                            <TableCell className="px-3 py-2.5 border text-right tabular-nums">{fmt(item.rate, 2)}</TableCell>
                            <TableCell className="px-3 py-2.5 border text-right tabular-nums font-semibold">{fmt(item.amt, 2)}</TableCell>
                            {subIdx === 0 && (
                              <TableCell rowSpan={subRows.length} className="px-3 py-2.5 border text-center align-middle">
                                {detail.has_barcode && detail.pending_pcs === 0 && detail.pending_gw === 0 ? (
                                  <Button
                                    size="sm"
                                    className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                                    onClick={() => {
                                      setSelectedBarcodeItem({ slNo: detail.sl_no, detail });
                                      setBarcodeModalOpen(true);
                                    }}
                                  >
                                    View Barcode
                                  </Button>
                                ) : (
                                  <Button
                                    size="sm"
                                    className="bg-[hsl(242_64%_63%)] hover:bg-[hsl(242_64%_56%)] text-white text-xs"
                                    onClick={() => navigate(`/inventory/barcodemanagement/list/add/?rec_sl_no=${encodeURIComponent(details.receive_slip_no)}&sl_no=${item.sl_no}`)}
                                    disabled={detail.item_id === 31 ? !detail.pending_gw : !(detail.pending_pcs && (detail.pending_gw || detail.pending_ct))}
                                  >
                                    Create Barcode
                                  </Button>
                                )}
                              </TableCell>
                            )}
                          </TableRow>
                        );
                      });
                    });

                    if (subItemCount > 0) {
                      const tCell = "px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-right tabular-nums font-semibold";
                      const lossT = (val, base) => `${tCell} ${base} ${val > 0 ? lossText : ""}`;
                      rendered.push(
                        <TableRow key="totals" className="hover:bg-transparent">
                          <TableCell colSpan={8} className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)] text-center font-semibold">Total � {subItemCount} sub-item{subItemCount === 1 ? '' : 's'}</TableCell>
                          <TableCell className={`${tCell} ${stageA}`}>{fmt(totals.issue_pcs, 0)}</TableCell>
                          <TableCell className={`${tCell} ${stageA}`}>{fmt(totals.issue_ct, 3)}</TableCell>
                          <TableCell className={`${tCell} ${stageA}`}>{fmt(totals.issue_gw, 3)}</TableCell>
                          <TableCell className={lossT(totals.broken_pcs, stageB)}>{fmt(totals.broken_pcs, 0)}</TableCell>
                          <TableCell className={lossT(totals.broken_ct, stageB)}>{fmt(totals.broken_ct, 3)}</TableCell>
                          <TableCell className={lossT(totals.broken_gw, stageB)}>{fmt(totals.broken_gw, 3)}</TableCell>
                          <TableCell className={`${tCell} ${stageA}`}>{fmt(totals.return_pcs, 0)}</TableCell>
                          <TableCell className={`${tCell} ${stageA}`}>{fmt(totals.return_ct, 3)}</TableCell>
                          <TableCell className={`${tCell} ${stageA}`}>{fmt(totals.return_gw, 3)}</TableCell>
                          <TableCell className={`${tCell} ${stageB}`}>{fmt(totals.balance_pcs, 0)}</TableCell>
                          <TableCell className={`${tCell} ${stageB}`}>{fmt(totals.balance_ct, 3)}</TableCell>
                          <TableCell className={`${tCell} ${stageB}`}>{fmt(totals.balance_gw, 3)}</TableCell>
                          <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)]"></TableCell>
                          <TableCell className={tCell}>{fmt(totals.amt, 2)}</TableCell>
                          <TableCell className="px-3 py-2.5 border-t-2 border-t-[hsl(242_30%_86%)] bg-[hsl(242_35%_94%)]"></TableCell>
                        </TableRow>
                      );
                    }
                    return rendered;
                  })()}
                </TableBody>
              </Table>
            </div>
          </ResizablePanel>
        </>
      )}

      <BarcodeDetailsModal
        isOpen={barcodeModalOpen}
        onClose={() => {
          setBarcodeModalOpen(false);
          setSelectedBarcodeItem(null);
        }}
        receiveSlipNo={details.receive_slip_no}
        slNo={selectedBarcodeItem?.slNo}
        detail={selectedBarcodeItem?.detail}
      />
    </ResizablePanelGroup>
  );
};

export default KarigarReceive;