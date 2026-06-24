import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  convertBarcode,
  fetchCustomerOrdersKanban,
  transferBarcodeToOrder,
} from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";
import { Repeat2, ArrowRightCircle, Unlink, ChevronLeft, X } from "lucide-react";

/**
 * BarcodeTransferDialog
 * One dialog with a 2-step flow:
 *   Step "menu"           → 3 cards (Transfer to Unbarcoded / Transfer to Order / Release from Order)
 *   Step "to-unbarcoded"  → confirmation
 *   Step "to-order"       → searchable list of open customer orders
 *   Step "release"        → defers to the existing ReleaseFromOrderModal flow via prop callback
 */
export default function BarcodeTransferDialog({ open, barcode, onClose, onDone, onRequestRelease }) {
  const { toast } = useToast();
  const [step, setStep] = useState("menu");
  const [submitting, setSubmitting] = useState(false);
  const [orders, setOrders] = useState([]);
  const [orderSearch, setOrderSearch] = useState("");
  const [loadingOrders, setLoadingOrders] = useState(false);

  useEffect(() => {
    if (open) {
      setStep("menu");
      setOrderSearch("");
      setSubmitting(false);
    }
  }, [open, barcode?.id]);

  useEffect(() => {
    if (step !== "to-order") return;
    let cancel = false;
    (async () => {
      setLoadingOrders(true);
      const res = await fetchCustomerOrdersKanban({ search: orderSearch });
      if (!cancel) {
        const open = (res.data || []).filter((o) => {
          const s = (o.delivery_status || "").toLowerCase();
          return s !== "delivered" && s !== "cancelled";
        });
        setOrders(open);
        setLoadingOrders(false);
      }
    })();
  
  // Close on Escape key
  useEffect(() => {
    const handleKey = (e) => { if (e.key === 'Escape' && !submitting) onClose?.() }
    if (open) window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [open, submitting, onClose])

  return () => { cancel = true; };
  }, [step, orderSearch]);

  if (!open || !barcode) return null;

  const hasOrder = !!barcode.customer_order;

  const handleTransferToUnbarcoded = async () => {
    setSubmitting(true);
    const res = await convertBarcode(barcode.barcode);
    setSubmitting(false);
    if (res.success) {
      toast({ title: "Transferred to Unbarcoded", description: `Barcode ${barcode.barcode} moved to unbarcoded inventory.` });
      onDone?.();
      onClose?.();
    } else {
      toast({ title: "Transfer failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  const handleTransferToOrder = async (order) => {
    setSubmitting(true);
    const res = await transferBarcodeToOrder(barcode.id, { order_id: order.id });
    setSubmitting(false);
    if (res.success) {
      toast({ title: "Assigned to order", description: `Barcode ${barcode.barcode} reserved for order ${order.order_no || order.id}.` });
      onDone?.();
      onClose?.();
    } else {
      const msg = typeof res.error === "string" ? res.error : (res.error?.detail || JSON.stringify(res.error));
      toast({ title: "Assignment failed", description: msg, variant: "destructive" });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-md shadow-lg w-full max-w-lg p-6">
        <div className="flex items-center gap-2 mb-3">
          {step !== "menu" && (
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setStep("menu")} disabled={submitting}>
              <ChevronLeft size={16} />
            </Button>
          )}
          <h2 className="text-lg font-semibold flex-1">
            {step === "menu" && "Transfer barcode"}
            {step === "to-unbarcoded" && "Transfer to Unbarcoded"}
            {step === "to-order" && "Transfer to Customer Order"}
          </h2>
          <Button variant="ghost" size="icon" className="h-7 w-7 ml-auto" onClick={onClose} disabled={submitting} title="Close">
            <X size={16} />
          </Button>
        </div>

        <div className="text-sm space-y-1 mb-4 bg-gray-50 rounded p-3 border">
          <div><span className="text-gray-500">Barcode:</span> <span className="font-medium">{barcode.barcode}</span></div>
          <div><span className="text-gray-500">Item:</span> {barcode.item_name || "-"}</div>
          {hasOrder && (
            <div><span className="text-gray-500">Reserved for order:</span> #{barcode.customer_order_no} ({barcode.customer_order_party_name || "-"})</div>
          )}
        </div>

        {step === "menu" && (
          <div className="grid grid-cols-1 gap-2">
            <button
              type="button"
              disabled={hasOrder}
              onClick={() => setStep("to-unbarcoded")}
              className="text-left p-3 rounded border hover:bg-accent-50/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-start gap-3"
              title={hasOrder ? "Release from order first" : ""}
            >
              <Repeat2 className="text-primary mt-0.5" size={20} />
              <div>
                <div className="text-sm font-medium">Transfer to Unbarcoded</div>
                <div className="text-xs text-muted-foreground">Move this barcoded piece into unbarcoded inventory (e.g. for rework).</div>
              </div>
            </button>

            <button
              type="button"
              disabled={hasOrder}
              onClick={() => setStep("to-order")}
              className="text-left p-3 rounded border hover:bg-accent-50/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-start gap-3"
              title={hasOrder ? "Already assigned to an order — release first" : ""}
            >
              <ArrowRightCircle className="text-primary mt-0.5" size={20} />
              <div>
                <div className="text-sm font-medium">Transfer to Order</div>
                <div className="text-xs text-muted-foreground">Reserve this barcode for an open customer order.</div>
              </div>
            </button>

            <button
              type="button"
              disabled={!hasOrder}
              onClick={() => { onClose?.(); onRequestRelease?.(barcode); }}
              className="text-left p-3 rounded border hover:bg-amber-50/50 disabled:opacity-50 disabled:cursor-not-allowed flex items-start gap-3"
              title={!hasOrder ? "Not assigned to any order" : ""}
            >
              <Unlink className="text-amber-600 mt-0.5" size={20} />
              <div>
                <div className="text-sm font-medium">Release from Order</div>
                <div className="text-xs text-muted-foreground">Free this barcode from its current customer order.</div>
              </div>
            </button>
          </div>
        )}

        {step === "to-unbarcoded" && (
          <>
            <p className="text-sm mb-4">
              This will move barcode <strong>{barcode.barcode}</strong> into unbarcoded inventory.
              The piece will no longer be available as a barcoded item.
            </p>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={onClose} disabled={submitting}>Cancel</Button>
              <Button onClick={handleTransferToUnbarcoded} disabled={submitting}>
                {submitting ? "Transferring…" : "Confirm Transfer"}
              </Button>
            </div>
          </>
        )}

        {step === "to-order" && (
          <>
            <Input
              placeholder="Search by order no / party / item…"
              value={orderSearch}
              onChange={(e) => setOrderSearch(e.target.value)}
              className="mb-2"
            />
            <div className="border rounded max-h-72 overflow-auto divide-y text-sm">
              {loadingOrders ? (
                <div className="p-4 text-center text-muted-foreground text-xs">Loading…</div>
              ) : orders.length === 0 ? (
                <div className="p-4 text-center text-muted-foreground text-xs">No open orders found.</div>
              ) : (
                orders.map((o) => (
                  <button
                    key={o.id}
                    type="button"
                    disabled={submitting}
                    onClick={() => handleTransferToOrder(o)}
                    className="w-full text-left p-3 hover:bg-accent-50/40 disabled:opacity-50 flex items-center justify-between"
                  >
                    <div>
                      <div className="font-medium">#{o.order_no || o.id}</div>
                      <div className="text-xs text-muted-foreground">
                        {o.party_name || o.ldgr_name || "—"}
                        {o.date1 ? ` · ${o.date1}` : ""}
                        {o.delivery_status ? ` · ${o.delivery_status}` : ""}
                      </div>
                    </div>
                    <ArrowRightCircle className="text-primary" size={18} />
                  </button>
                ))
              )}
            </div>
            <div className="flex justify-end gap-2 mt-3">
              <Button variant="outline" onClick={onClose} disabled={submitting}>Cancel</Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
