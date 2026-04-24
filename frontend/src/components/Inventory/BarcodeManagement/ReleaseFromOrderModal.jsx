import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { releaseBarcodeFromOrder } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

export default function ReleaseFromOrderModal({ open, barcode, onClose, onReleased }) {
  const { toast } = useToast();
  const [mode, setMode] = useState("cancel_order");
  const [remarks, setRemarks] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setMode("cancel_order");
      setRemarks("");
      setSubmitting(false);
    }
  }, [open, barcode?.id]);

  if (!open || !barcode) return null;

  const handleConfirm = async () => {
    setSubmitting(true);
    const result = await releaseBarcodeFromOrder(barcode.id, { mode, remarks });
    setSubmitting(false);
    if (result.success) {
      toast({
        title:
          mode === "cancel_order"
            ? "Order cancelled, barcode released"
            : "Barcode released",
        description: `Barcode ${barcode.barcode} is no longer reserved.`,
      });
      onReleased?.();
      onClose?.();
    } else {
      const msg =
        typeof result.error === "string"
          ? result.error
          : result.error?.detail ||
            JSON.stringify(result.error);
      toast({ title: "Release failed", description: msg, variant: "destructive" });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-md shadow-lg w-full max-w-md p-6">
        <h2 className="text-lg font-semibold mb-3">Release barcode from customer order</h2>

        <div className="text-sm space-y-1 mb-4 bg-gray-50 rounded p-3 border">
          <div>
            <span className="text-gray-500">Barcode:</span>{" "}
            <span className="font-medium">{barcode.barcode}</span>
          </div>
          <div>
            <span className="text-gray-500">Item:</span>{" "}
            {barcode.item_name || "-"}
          </div>
          <div>
            <span className="text-gray-500">Reserved for:</span>{" "}
            {barcode.customer_order_party_name || "-"}
          </div>
          <div>
            <span className="text-gray-500">Order no:</span>{" "}
            {barcode.customer_order_no || "-"}
          </div>
        </div>

        <p className="text-sm font-medium mb-2">
          What should happen to the original customer order?
        </p>

        <div className="space-y-2 mb-4">
          <label className="flex items-start gap-2 cursor-pointer p-2 rounded border hover:bg-gray-50">
            <input
              type="radio"
              name="release-mode"
              value="cancel_order"
              checked={mode === "cancel_order"}
              onChange={() => setMode("cancel_order")}
              className="mt-1"
            />
            <div>
              <div className="text-sm font-medium">Cancel the original customer order</div>
              <div className="text-xs text-gray-500">
                Marks order {barcode.customer_order_no} as cancelled and frees this barcode.
              </div>
            </div>
          </label>

          <label className="flex items-start gap-2 cursor-pointer p-2 rounded border hover:bg-gray-50">
            <input
              type="radio"
              name="release-mode"
              value="reassign"
              checked={mode === "reassign"}
              onChange={() => setMode("reassign")}
              className="mt-1"
            />
            <div>
              <div className="text-sm font-medium">Release — I'll place a new order</div>
              <div className="text-xs text-gray-500">
                Keeps the original order open; item lifecycle flags are reset so staff can reassign.
              </div>
            </div>
          </label>
        </div>

        <label className="block text-sm font-medium mb-1">Remarks (optional)</label>
        <textarea
          rows={2}
          className="w-full border rounded p-2 text-sm mb-4"
          value={remarks}
          onChange={(e) => setRemarks(e.target.value)}
          placeholder="Reason for release..."
        />

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={submitting}>
            {submitting ? "Releasing..." : "Confirm release"}
          </Button>
        </div>
      </div>
    </div>
  );
}
