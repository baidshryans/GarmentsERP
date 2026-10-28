import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { SquarePen, Trash2, Plus, ShoppingCart, Undo2, Undo } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DataTable } from "@/table";
import { formatNumber } from "@/lib/format";
import { useToast } from "@/hooks/use-toast";
import { useF2Navigate } from "@/hooks/useF2Navigate";
import {
  fetchPurchaseApprovals,
  deletePurchaseApproval,
  returnApprovalItems,
  undoApprovalReturn,
} from "@/services/apiService";

const LINE_BADGE = { pending: "outline", purchased: "default", returned: "secondary" };
const todayISO = () => new Date().toISOString().split("T")[0];
const errText = (e) => (typeof e === "string" ? e : e?.detail || e?.[0] || JSON.stringify(e));

function PurchaseApprovalList() {
  useF2Navigate("/purchase/purchaseapproval/list/add/");
  const { toast } = useToast();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [allFy, setAllFy] = useState(false);
  const [openId, setOpenId] = useState(null); // approval shown in the detail dialog
  const [picked, setPicked] = useState(new Set());
  const [returnDate, setReturnDate] = useState(todayISO());
  const search = params.get("search") || "";

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["purchaseApprovals", { search, page, allFy }],
    queryFn: async () => {
      const res = await fetchPurchaseApprovals({ search, page, ordering: "-date1", allFy });
      if (!res.success) throw new Error(errText(res.error) || "Failed to load purchase approvals");
      return res.data;
    },
    keepPreviousData: true,
  });

  const rows = data?.results ?? [];
  const totalPages = data?.total_pages ?? 1;
  const open = rows.find((r) => r.id === openId) || null;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["purchaseApprovals"] });

  const closeDialog = () => { setOpenId(null); setPicked(new Set()); };
  const togglePick = (id) =>
    setPicked((prev) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete approval ${row.billno}?`)) return;
    try {
      await deletePurchaseApproval(row.id);
      toast({ title: "Purchase approval deleted" });
      refresh();
    } catch (e) {
      toast({ title: "Delete failed", description: e.message, variant: "destructive" });
    }
  };

  const buySelected = () => {
    if (!picked.size) return toast({ title: "Select the pending lines you are buying" });
    navigate(`/purchase/add/?approval=${open.id}&items=${[...picked].join(",")}`);
  };

  const returnSelected = async () => {
    if (!picked.size) return toast({ title: "Select the pending lines to send back" });
    const res = await returnApprovalItems(open.id, [...picked], returnDate);
    if (!res.success) return toast({ title: "Return failed", description: errText(res.error), variant: "destructive" });
    toast({ title: "Marked as returned to vendor" });
    setPicked(new Set());
    refresh();
  };

  const undoReturn = async (lineId) => {
    const res = await undoApprovalReturn(open.id, [lineId]);
    if (!res.success) return toast({ title: "Could not undo", description: errText(res.error), variant: "destructive" });
    refresh();
  };

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex space-x-3" onClick={(e) => e.stopPropagation()}>
          <Link
            to={`/purchase/purchaseapproval/list/${row.original.id}`}
            className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors flex items-center"
          >
            <SquarePen className="size-4" />
          </Link>
          <button
            onClick={() => handleDelete(row.original)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors flex items-center"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    {
      header: "Date",
      accessorKey: "date1",
      cell: ({ getValue }) => new Date(getValue()).toLocaleDateString("en-GB").replaceAll("/", "-"),
    },
    { header: "Bill No", accessorKey: "billno" },
    { header: "Vendor", accessorKey: "ldgr_name" },
    {
      header: "Lines",
      id: "lines",
      cell: ({ row }) => {
        const c = { pending: 0, purchased: 0, returned: 0 };
        row.original.items.forEach((i) => { c[i.status] += 1; });
        return `${c.pending} pending · ${c.purchased} bought · ${c.returned} returned`;
      },
    },
    {
      header: "Gross Wt",
      id: "gw",
      cell: ({ row }) => formatNumber(row.original.items.reduce((s, i) => s + parseFloat(i.gw || 0), 0), { decimals: 3 }),
    },
    {
      header: "Value",
      id: "value",
      cell: ({ row }) => formatNumber(row.original.items.reduce((s, i) => s + parseFloat(i.amount || 0), 0)),
    },
    {
      header: "Status",
      accessorKey: "status",
      cell: ({ getValue }) => (
        <Badge variant={getValue() === "Open" ? "default" : "secondary"} className="px-2 py-0.5 text-xs">
          {getValue()}
        </Badge>
      ),
    },
  ];

  const pendingInOpen = open ? open.items.filter((i) => i.status === "pending") : [];

  return (
    <div className="p-4">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-3 flex-1">
            <Input
              type="text"
              placeholder="Search bill no, vendor, narration…"
              className="max-w-xs"
              defaultValue={search}
              onChange={(e) => { setPage(1); setParams(e.target.value ? { search: e.target.value } : {}); }}
            />
            <div className="flex items-center gap-2">
              <Checkbox id="pa-allfy" checked={allFy} onCheckedChange={(v) => { setPage(1); setAllFy(!!v); }} />
              <Label htmlFor="pa-allfy" className="text-sm">All fiscal years</Label>
            </div>
          </div>
          <Link to="/purchase/purchaseapproval/list/add/">
            <Button size="sm" className="gap-1.5">
              <Plus className="size-4" />
              Add Approval
            </Button>
          </Link>
        </div>

        {isLoading ? (
          <div className="flex flex-col gap-2">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="w-full h-10" />)}
          </div>
        ) : isError ? (
          <div className="text-destructive text-sm">Error: {error.message}</div>
        ) : (
          <>
            <DataTable columns={columns} data={rows} rowClick={(row) => setOpenId(row.id)} />
            <div className="flex items-center justify-between pt-1">
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(p - 1, 1))} disabled={page === 1}>
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(p + 1, totalPages))} disabled={page >= totalPages}>
                Next
              </Button>
            </div>
          </>
        )}
      </div>

      <Dialog open={!!open} onOpenChange={(v) => !v && closeDialog()}>
        <DialogContent className="max-w-3xl">
          {open && (
            <>
              <DialogHeader>
                <DialogTitle>
                  {open.billno} · {open.ldgr_name}
                </DialogTitle>
              </DialogHeader>
              <div className="text-sm text-muted-foreground">{open.narration}</div>
              <div className="border rounded-md overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted/50 text-left">
                    <tr>
                      <th className="p-2 w-8" />
                      <th className="p-2">#</th>
                      <th className="p-2">Item</th>
                      <th className="p-2">Pcs</th>
                      <th className="p-2">Gross Wt</th>
                      <th className="p-2">Purity</th>
                      <th className="p-2 text-right">Amount</th>
                      <th className="p-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {open.items.map((i) => (
                      <tr key={i.id} className="border-t">
                        <td className="p-2">
                          {i.status === "pending" && (
                            <Checkbox checked={picked.has(i.id)} onCheckedChange={() => togglePick(i.id)} />
                          )}
                        </td>
                        <td className="p-2">{i.sl_no}</td>
                        <td className="p-2">{i.item_name || i.item}</td>
                        <td className="p-2">{i.pcs}</td>
                        <td className="p-2">{formatNumber(i.gw, { decimals: 3 })}</td>
                        <td className="p-2">{i.purity || "-"}</td>
                        <td className="p-2 text-right">{formatNumber(i.amount)}</td>
                        <td className="p-2">
                          <Badge variant={LINE_BADGE[i.status]} className="px-2 py-0.5 text-xs">{i.status}</Badge>
                          {i.status === "returned" && (
                            <button
                              title={`Returned ${i.returned_on}. Click to undo`}
                              onClick={() => undoReturn(i.id)}
                              className="ml-2 align-middle text-muted-foreground hover:text-foreground"
                            >
                              <Undo className="size-3.5 inline" />
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {pendingInOpen.length > 0 && (
                <DialogFooter className="items-center gap-2 sm:justify-between">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm">Return date</Label>
                    <Input type="date" className="w-40" value={returnDate} onChange={(e) => setReturnDate(e.target.value)} />
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="gap-1.5" onClick={returnSelected}>
                      <Undo2 className="size-4" /> Return to vendor
                    </Button>
                    <Button size="sm" className="gap-1.5" onClick={buySelected}>
                      <ShoppingCart className="size-4" /> Buy selected
                    </Button>
                  </div>
                </DialogFooter>
              )}
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export default PurchaseApprovalList;
