import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { useToast } from "@/hooks/use-toast";
import apiClient from "@/services/apiClient";

const BarcodeDetailsModal = ({ isOpen, onClose, receiveSlipNo, slNo, detail }) => {
  const { toast } = useToast();
  const [barcodes, setBarcodes] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen && receiveSlipNo && slNo !== undefined) {
      loadBarcodes();
    }
  }, [isOpen, receiveSlipNo, slNo]);

  const loadBarcodes = async () => {
    setLoading(true);
    try {
      // Fetch barcodes created against this receive slip item
      // Using rec_item__receive_slip_no and rec_item__sl_no for filtering
      const response = await apiClient.get(
        `/inventory/barcode/?rec_item__receive_slip_no=${encodeURIComponent(receiveSlipNo)}&rec_item__sl_no=${slNo}`
      );

      const data = response.data;
      const barcodeList = Array.isArray(data) ? data : data.results || [];
      setBarcodes(barcodeList);

      if (barcodeList.length === 0) {
        toast({
          title: "No barcodes found",
          description: `No barcodes found for receive slip ${receiveSlipNo}`,
        });
      }
    } catch (error) {
      console.error("Barcode fetch error:", error);
      toast({
        title: "Error loading barcodes",
        description: error.response?.data?.detail || error.message || "Failed to fetch barcodes",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const formatValue = (value, decimals = 3) => {
    if (value === null || value === undefined) return "�";
    const num = parseFloat(value);
    if (!Number.isFinite(num)) return "�";
    return decimals === 0 ? Math.round(num).toString() : num.toFixed(decimals);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-lg">
            Barcode Details � {receiveSlipNo}
          </DialogTitle>
          <DialogDescription>
            Barcodes created against this receive slip item
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">Loading barcodes...</span>
          </div>
        ) : barcodes.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-muted-foreground">
              No barcodes found for this receive item.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {barcodes.map((barcode, idx) => (
              <div
                key={barcode.id || idx}
                className="border border-gray-200 rounded-lg p-4 bg-gray-50"
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <p className="font-semibold text-sm">
                      {barcode.barcode}
                    </p>
                    <p className="text-xs text-gray-500">
                      Created: {barcode.created_date ? new Date(barcode.created_date).toLocaleDateString('en-GB').replaceAll('/', '-') : "�"}
                    </p>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    barcode.stk_status === false
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-100 text-amber-700"
                  }`}>
                    {barcode.stk_status === false ? "Sold" : "In Stock"}
                  </span>
                </div>

                {/* Details Grid */}
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Item</p>
                    <p className="font-medium">{barcode.item_name || barcode.item || "�"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Purity</p>
                    <p className="font-medium">{barcode.purity_name || barcode.purity || "�"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Pieces</p>
                    <p className="font-medium text-right">{formatValue(barcode.pcs, 0)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Gross Weight (gm)</p>
                    <p className="font-medium text-right">{formatValue(barcode.gw, 3)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 uppercase">Net Weight (gm)</p>
                    <p className="font-medium text-right">{formatValue(barcode.nw, 3)}</p>
                  </div>
                  {barcode.making_val !== null && barcode.making_val !== undefined && (
                    <div>
                      <p className="text-xs text-gray-500 uppercase">Making Value</p>
                      <p className="font-medium text-right">₹{formatValue(barcode.making_val, 2)}</p>
                    </div>
                  )}
                </div>

                {/* Sub-items (BarcodeDetails) if available */}
                {barcode.barcodedetails_set && barcode.barcodedetails_set.length > 0 && (
                  <div className="mt-4 pt-4 border-t">
                    <p className="text-xs font-semibold text-gray-600 uppercase mb-2">
                      Sub-items ({barcode.barcodedetails_set.length})
                    </p>
                    <div className="space-y-2">
                      {barcode.barcodedetails_set.map((detail, sidx) => (
                        <div
                          key={sidx}
                          className="bg-white p-2 rounded border border-gray-200 text-xs"
                        >
                          <div className="flex justify-between items-center">
                            <span className="font-medium">{detail.item || detail.item_name || "�"}</span>
                            <span className="text-gray-500">{detail.packet || "�"}</span>
                          </div>
                          <div className="grid grid-cols-3 gap-2 text-gray-600 mt-1 text-[10px]">
                            <span>Pcs: {formatValue(detail.pcs, 0)}</span>
                            <span>Ct: {formatValue(detail.ct, 3)}</span>
                            <span>GW: {formatValue(detail.gw, 3)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-4 border-t">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default BarcodeDetailsModal;
