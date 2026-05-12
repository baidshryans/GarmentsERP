import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Link2, IndianRupee, RefreshCw, ArrowRight } from "lucide-react";
import { fetchUnallocatedVouchers, allocateVoucherBills, linkReceiptToOrder } from "@/services/api/accounting";
import { fetchCustomerOrders } from "@/services/api/sales";
import { useToast } from "@/hooks/use-toast";
import BillAllocationTable from "./vouchers/BillAllocationTable";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";

const fmt = (n) => Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function UnallocatedVouchers() {
  const { toast } = useToast();
  const [receipts, setReceipts]       = useState([]);
  const [payments, setPayments]       = useState([]);
  const [loading, setLoading]         = useState({ receipt: false, payment: false });
  const [selected, setSelected]       = useState(null); // voucher row being allocated
  const [sheetOpen, setSheetOpen]     = useState(false);
  const [allocations, setAllocations] = useState([]);
  const [orderSearch, setOrderSearch] = useState("");
  const [orders, setOrders]           = useState([]);
  const [pickedOrder, setPickedOrder] = useState(null);
  const [saving, setSaving]           = useState(false);
  const [activeTab, setActiveTab]     = useState("receipts");

  const load = useCallback(async (type) => {
    setLoading(l => ({ ...l, [type]: true }));
    const res = await fetchUnallocatedVouchers(type);
    if (res.success) {
      if (type === "receipt") setReceipts(res.data);
      else setPayments(res.data);
    }
    setLoading(l => ({ ...l, [type]: false }));
  }, []);

  useEffect(() => { load("receipt"); load("payment"); }, [load]);

  function openSheet(row) {
    setSelected(row);
    setAllocations([]);
    setPickedOrder(null);
    setOrderSearch("");
    setOrders([]);
    setSheetOpen(true);
  }

  useEffect(() => {
    if (!selected || selected._kind !== "receipt") return;
    fetchCustomerOrders({ search: orderSearch, page: 1 }).then(res => {
      if (res.success) {
        const list = Array.isArray(res.data) ? res.data : (res.data.results || []);
        setOrders(list.filter(o => !selected.party_id || o.ldgr === selected.party_id || o.ldgr_detail?.id === selected.party_id));
      }
    });
  }, [orderSearch, selected]);

  async function handleLinkOrder() {
    if (!pickedOrder) return;
    setSaving(true);
    const res = await linkReceiptToOrder(selected.id, pickedOrder.id);
    setSaving(false);
    if (res.success) {
      toast({ title: "Receipt linked to order." });
      setSheetOpen(false);
      load("receipt");
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
  }

  async function handleAllocateBills() {
    if (!allocations.length) return;
    setSaving(true);
    const kind = selected._kind === "receipt" ? "sales" : "purchase";
    const payload = allocations.map(a => ({ bill_id: a.bill_id, amount: String(a.amount) }));
    const res = await allocateVoucherBills(selected.id, kind, payload);
    setSaving(false);
    if (res.success) {
      toast({ title: "Allocations saved." });
      setSheetOpen(false);
      load(selected._kind);
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Unallocated Vouchers</h2>
        <p className="text-sm text-muted-foreground">
          Receipts and payments not yet matched to any invoice or order
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="receipts">
            Receipts
            {receipts.length > 0 && (
              <Badge variant="destructive" className="ml-2 h-5 px-1.5 text-[11px]">{receipts.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="payments">
            Payments
            {payments.length > 0 && (
              <Badge variant="destructive" className="ml-2 h-5 px-1.5 text-[11px]">{payments.length}</Badge>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="receipts" className="mt-3">
          <VoucherTable
            rows={receipts}
            loading={loading.receipt}
            onRefresh={() => load("receipt")}
            onAllocate={(row) => openSheet({ ...row, _kind: "receipt" })}
            kind="receipt"
          />
        </TabsContent>

        <TabsContent value="payments" className="mt-3">
          <VoucherTable
            rows={payments}
            loading={loading.payment}
            onRefresh={() => load("payment")}
            onAllocate={(row) => openSheet({ ...row, _kind: "payment" })}
            kind="payment"
          />
        </TabsContent>
      </Tabs>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
          {selected && (
            <>
              <SheetHeader>
                <SheetTitle>
                  Allocate {selected._kind === "receipt" ? "Receipt" : "Payment"} — {selected.voucher_no}
                </SheetTitle>
                <div className="text-sm text-muted-foreground space-y-0.5 mt-1">
                  <div><span className="font-medium">Party:</span> {selected.party}</div>
                  <div><span className="font-medium">Date:</span> {selected.date}</div>
                  <div>
                    <span className="font-medium">Unallocated:</span>{" "}
                    <span className="text-amber-700 font-semibold">₹{fmt(selected.unallocated_amount)}</span>
                  </div>
                  {selected.narration && <div className="text-xs text-muted-foreground">{selected.narration}</div>}
                </div>
              </SheetHeader>

              <div className="mt-6 space-y-6 pb-6">
                {selected._kind === "receipt" && (
                  <section className="space-y-3">
                    <h3 className="text-sm font-semibold flex items-center gap-2">
                      <Link2 className="size-4" /> Link to Customer Order
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      If this receipt is an advance for a pending order, link it here.
                    </p>
                    <div className="flex items-center gap-2">
                      <div className="flex-1">
                        <SearchableComboBox
                          options={orders}
                          labelKey="order_no"
                          value={pickedOrder?.order_no || orderSearch}
                          onSelect={(o) => setPickedOrder(o)}
                          onInputChange={(v) => { setOrderSearch(v); if (!v) setPickedOrder(null); }}
                        />
                      </div>
                      <Button
                        size="sm"
                        onClick={handleLinkOrder}
                        disabled={!pickedOrder || saving}
                      >
                        <ArrowRight className="size-4 mr-1" />
                        Link Order
                      </Button>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <hr className="flex-1" />
                      <span>or allocate directly to invoices below</span>
                      <hr className="flex-1" />
                    </div>
                  </section>
                )}

                <section className="space-y-3">
                  <h3 className="text-sm font-semibold flex items-center gap-2">
                    <IndianRupee className="size-4" />
                    Allocate to {selected._kind === "receipt" ? "Sales Invoices" : "Purchase Invoices"}
                  </h3>
                  <BillAllocationTable
                    ledgerId={selected.party_id}
                    kind={selected._kind === "receipt" ? "sales" : "purchase"}
                    partyAmount={selected.unallocated_amount}
                    allocations={allocations}
                    onChange={setAllocations}
                  />
                  <Button
                    className="w-full"
                    onClick={handleAllocateBills}
                    disabled={!allocations.length || saving}
                  >
                    {saving ? "Saving…" : "Save Allocations"}
                  </Button>
                </section>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function VoucherTable({ rows, loading, onRefresh, onAllocate, kind }) {
  return (
    <div className="rounded-md border">
      <div className="flex items-center justify-between px-4 py-2 border-b bg-muted/30">
        <span className="text-xs text-muted-foreground">
          {rows.length} unallocated {kind === "receipt" ? "receipt" : "payment"}{rows.length !== 1 ? "s" : ""}
        </span>
        <Button variant="ghost" size="sm" onClick={onRefresh} disabled={loading}>
          <RefreshCw className={`size-3.5 mr-1 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Voucher No</TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Party</TableHead>
            <TableHead className="text-right">Amount</TableHead>
            <TableHead className="text-right">Unallocated</TableHead>
            <TableHead>Narration</TableHead>
            <TableHead className="w-24" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading && (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-muted-foreground py-8">Loading…</TableCell>
            </TableRow>
          )}
          {!loading && rows.length === 0 && (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                No unallocated {kind === "receipt" ? "receipts" : "payments"} found.
              </TableCell>
            </TableRow>
          )}
          {rows.map(row => (
            <TableRow key={row.id}>
              <TableCell className="font-mono text-xs">{row.voucher_no}</TableCell>
              <TableCell className="text-xs">{row.date}</TableCell>
              <TableCell className="text-sm">{row.party}</TableCell>
              <TableCell className="text-right text-sm">₹{fmt(row.amount)}</TableCell>
              <TableCell className="text-right">
                <span className="text-amber-700 font-semibold text-sm">₹{fmt(row.unallocated_amount)}</span>
              </TableCell>
              <TableCell className="text-xs text-muted-foreground max-w-[160px] truncate">{row.narration}</TableCell>
              <TableCell>
                <Button size="sm" variant="outline" onClick={() => onAllocate(row)}>
                  Allocate
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
