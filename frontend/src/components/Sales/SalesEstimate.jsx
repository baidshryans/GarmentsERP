import React, { useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { Loader2, Printer, Search, Trash2, Plus } from "lucide-react";
import { fetchBarcodeDetailOnly } from "@/services/apiService";
import { openAndPrint } from "@/services/print/utils";
import { MultiEstimatePrint } from "./salesPrintEstimate";

const fmt = (v, d = 3) => {
  const n = parseFloat(v);
  return isNaN(n) ? "—" : n.toFixed(d);
};

export default function SalesEstimate() {
  const { toast } = useToast();
  const inputRef = useRef(null);

  const [barcodeInput, setBarcodeInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState([]); // array of barcode data objects

  const handleAdd = async (e) => {
    e?.preventDefault();
    const code = barcodeInput.trim();
    if (!code) return;

    // Prevent duplicates
    if (items.some((i) => i.barcode === code || i.voucher_no === code)) {
      toast({ title: "Already added", description: `Barcode "${code}" is already in the list.` });
      setBarcodeInput("");
      return;
    }

    setLoading(true);
    try {
      const res = await fetchBarcodeDetailOnly(code);
      if (res.success && res.data) {
        setItems((prev) => [...prev, { ...res.data, _key: Date.now() }]);
        setBarcodeInput("");
        setTimeout(() => inputRef.current?.focus(), 50);
      } else {
        toast({
          title: "Barcode not found",
          description: typeof res.error === "string" ? res.error : `No data for "${code}"`,
          variant: "destructive",
        });
      }
    } catch {
      toast({ title: "Error fetching barcode", variant: "destructive" });
    }
    setLoading(false);
  };

  const handleRemove = (key) => setItems((prev) => prev.filter((i) => i._key !== key));

  const handlePrint = () => {
    if (items.length === 0) {
      toast({ title: "Nothing to print", description: "Add at least one barcode first." });
      return;
    }
    openAndPrint(<MultiEstimatePrint items={items} />);
  };

  // ── per-item derived values ────────────────────────────────────────────────
  const getItemTotals = (data) => {
    const stoneItems = (data.main_item_set || []).filter((i) => i.item !== "GOLD");
    const metalItem = (data.main_item_set || []).find((i) => i.item === "GOLD");
    const totalStoneCt = stoneItems.reduce((s, i) => s + (parseFloat(i.ct) || 0), 0);
    const totalStoneValue = stoneItems.reduce((s, i) => s + (parseFloat(i.amt) || 0), 0);
    const totalMetalValue = metalItem ? parseFloat(metalItem.amt) || 0 : 0;
    const totalOtherValue = parseFloat(data.other_chg) || 0;
    const totalMakingValue = parseFloat(data.making) || 0;
    const productValue = totalStoneValue + totalMetalValue + totalOtherValue + totalMakingValue;
    const gstAmt = productValue * 0.03;
    const billValue = productValue + gstAmt;
    return { stoneItems, metalItem, totalStoneCt, totalStoneValue, totalMetalValue, totalOtherValue, totalMakingValue, productValue, gstAmt, billValue };
  };

  // Grand totals across all items
  const grand = items.reduce(
    (acc, item) => {
      const t = getItemTotals(item);
      return {
        pcs: acc.pcs + (parseInt(item.pcs) || 0),
        gw: acc.gw + (parseFloat(item.gw) || 0),
        nw: acc.nw + (parseFloat(item.nw) || 0),
        stoneCt: acc.stoneCt + t.totalStoneCt,
        stoneVal: acc.stoneVal + t.totalStoneValue,
        metalVal: acc.metalVal + t.totalMetalValue,
        otherVal: acc.otherVal + t.totalOtherValue,
        making: acc.making + t.totalMakingValue,
        productVal: acc.productVal + t.productValue,
        gstAmt: acc.gstAmt + t.gstAmt,
        billVal: acc.billVal + t.billValue,
      };
    },
    { pcs: 0, gw: 0, nw: 0, stoneCt: 0, stoneVal: 0, metalVal: 0, otherVal: 0, making: 0, productVal: 0, gstAmt: 0, billVal: 0 }
  );

  return (
    <div className="flex flex-col gap-5 max-w-6xl mx-auto">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">Sales Estimate</h1>
          <p className="text-sm text-muted-foreground mt-0.5">Scan or type barcodes to build a multi-item estimate</p>
        </div>
        {items.length > 0 && (
          <Button onClick={handlePrint} className="bg-violet-700 hover:bg-violet-800 text-white gap-1.5">
            <Printer className="size-4" /> Print Estimate ({items.length})
          </Button>
        )}
      </div>

      {/* ── Barcode input ──────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-border bg-card shadow-sm p-4">
        <form onSubmit={handleAdd} className="flex items-end gap-3">
          <div className="flex flex-col gap-1 flex-1 max-w-xs">
            <Label className="text-xs">Barcode / Voucher No</Label>
            <Input
              ref={inputRef}
              value={barcodeInput}
              onChange={(e) => setBarcodeInput(e.target.value)}
              placeholder="Scan or type barcode…"
              autoFocus
              className="h-9"
              disabled={loading}
            />
          </div>
          <Button type="submit" disabled={loading || !barcodeInput.trim()} className="h-9 bg-violet-700 hover:bg-violet-800 text-white">
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4 mr-1" />}
            {loading ? "Loading…" : "Add"}
          </Button>
        </form>
        <p className="text-xs text-muted-foreground mt-2">Press Enter or click Add after each barcode. Duplicate barcodes are ignored.</p>
      </div>

      {/* ── Items table ────────────────────────────────────────────────────── */}
      {items.length > 0 && (
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/30">
            <span className="text-sm font-semibold">Added Items · {items.length}</span>
            <Button
              variant="ghost"
              size="sm"
              className="text-xs text-muted-foreground hover:text-destructive"
              onClick={() => setItems([])}
            >
              Clear all
            </Button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-muted/50 border-b border-border">
                <tr>
                  <th className="px-3 py-2 text-left font-semibold text-muted-foreground">#</th>
                  <th className="px-3 py-2 text-left font-semibold text-muted-foreground">Barcode</th>
                  <th className="px-3 py-2 text-left font-semibold text-muted-foreground">Item / Purity</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">Pcs</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">GW</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">NW</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">Stone Ct</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">Stone Val</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">Metal Val</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">Making</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">Product Val</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">GST 3%</th>
                  <th className="px-3 py-2 text-right font-semibold text-muted-foreground">Bill Value</th>
                  <th className="px-3 py-2 text-center font-semibold text-muted-foreground"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const t = getItemTotals(item);
                  return (
                    <tr key={item._key} className="border-b border-border hover:bg-muted/20 transition-colors">
                      <td className="px-3 py-2 text-muted-foreground">{idx + 1}</td>
                      <td className="px-3 py-2 font-mono">
                        <span className="bg-muted px-1.5 py-0.5 rounded text-[11px]">{item.barcode || item.voucher_no || "—"}</span>
                      </td>
                      <td className="px-3 py-2">
                        <div className="font-medium">{item.item || "—"}</div>
                        {item.purity && <div className="text-muted-foreground">{item.purity}K</div>}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{item.pcs || 0}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-mono">{fmt(item.gw)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-mono">{fmt(item.nw)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-mono">{fmt(t.totalStoneCt)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmt(t.totalStoneValue, 2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmt(t.totalMetalValue, 2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmt(t.totalMakingValue, 2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-medium">{fmt(t.productValue, 2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmt(t.gstAmt, 2)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-semibold text-violet-700">{fmt(t.billValue, 2)}</td>
                      <td className="px-3 py-2 text-center">
                        <button onClick={() => handleRemove(item._key)} className="text-muted-foreground hover:text-destructive transition-colors">
                          <Trash2 className="size-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              {/* Grand totals footer */}
              <tfoot className="bg-muted/50 border-t-2 border-border font-semibold text-xs">
                <tr>
                  <td colSpan={3} className="px-3 py-2 text-right text-muted-foreground">Grand Total</td>
                  <td className="px-3 py-2 text-right tabular-nums">{grand.pcs}</td>
                  <td className="px-3 py-2 text-right tabular-nums font-mono">{fmt(grand.gw)}</td>
                  <td className="px-3 py-2 text-right tabular-nums font-mono">{fmt(grand.nw)}</td>
                  <td className="px-3 py-2 text-right tabular-nums font-mono">{fmt(grand.stoneCt)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(grand.stoneVal, 2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(grand.metalVal, 2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(grand.making, 2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(grand.productVal, 2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(grand.gstAmt, 2)}</td>
                  <td className="px-3 py-2 text-right tabular-nums text-violet-700">{fmt(grand.billVal, 2)}</td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Print footer */}
          <div className="flex justify-end px-5 py-3 border-t border-border bg-muted/10">
            <Button onClick={handlePrint} className="bg-violet-700 hover:bg-violet-800 text-white gap-1.5">
              <Printer className="size-4" /> Print / Save PDF
            </Button>
          </div>
        </div>
      )}

      {/* ── Empty state ────────────────────────────────────────────────────── */}
      {items.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-muted/10 flex flex-col items-center justify-center py-20 text-center gap-3">
          <Search className="size-8 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">No barcodes added yet.</p>
          <p className="text-xs text-muted-foreground">Type a barcode above and press Enter or click Add.</p>
        </div>
      )}
    </div>
  );
}
