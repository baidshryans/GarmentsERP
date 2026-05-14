import React, { useRef, useState } from "react";
import { Trash2 } from "lucide-react";

// ── formatters ────────────────────────────────────────────────────────────────
const fmtN  = (v, d = 3) => (parseFloat(v) || 0).toFixed(d);
const fmtINR = v => `₹${(parseFloat(v) || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export default function POSItemsTable({
  barcodeItems,
  onBarcodeSubmit,
  onDeleteBarcodeItem,
}) {
  const [barcode, setBarcode] = useState("");
  const inputRef = useRef(null);

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const val = barcode.trim();
      if (val) {
        onBarcodeSubmit(val);
        setBarcode("");
      }
    }
  };

  // Totals
  const totalPcs = barcodeItems.reduce((s, i) => s + (parseInt(i.pcs) || 0), 0);
  const totalGW  = barcodeItems.reduce((s, i) => s + (parseFloat(i.gw)  || 0), 0);
  const totalNW  = barcodeItems.reduce((s, i) => s + (parseFloat(i.nw)  || 0), 0);
  const totalMRP = barcodeItems.reduce((s, i) => s + (parseFloat(i.amount) || 0), 0);

  return (
    <div className="flex flex-col flex-1 overflow-hidden">

      {/* Scan bar */}
      <div className="flex items-center gap-3 px-3 py-2 bg-muted/40 border-b border-border shrink-0">
        <span className="text-[11px] font-bold uppercase tracking-wide text-muted-foreground whitespace-nowrap">
          Scan
        </span>
        <div className="relative max-w-[280px] flex-1">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground text-xs">⬡</span>
          <input
            ref={inputRef}
            autoFocus
            value={barcode}
            onChange={e => setBarcode(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Scan or type barcode, press Enter…"
            className="w-full border border-input rounded-md pl-7 pr-3 py-1.5 text-[13px] bg-background text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-colors"
          />
        </div>
        <span className="text-[11px] text-muted-foreground italic">Press Enter after each scan</span>
      </div>

      {/* Items table */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full border-collapse text-[13px]">
          <thead>
            <tr className="bg-muted/60 sticky top-0 z-10">
              <th className="px-2 py-1.5 text-left text-[10px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border w-7">#</th>
              <th className="px-2 py-1.5 text-left text-[10px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border">Barcode</th>
              <th className="px-2 py-1.5 text-left text-[10px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border">Item / Design</th>
              <th className="px-2 py-1.5 text-center text-[10px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border">Pcs</th>
              <th className="px-2 py-1.5 text-right text-[10px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border">GW (g)</th>
              <th className="px-2 py-1.5 text-right text-[10px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border">NW (g)</th>
              <th className="px-2 py-1.5 text-right text-[10px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border">Making</th>
              <th className="px-2 py-1.5 text-right text-[10px] font-bold uppercase tracking-wide text-muted-foreground border-b border-border">MRP (₹)</th>
              <th className="px-2 py-1.5 border-b border-border w-7"></th>
            </tr>
          </thead>
          <tbody>
            {barcodeItems.length === 0 ? (
              <tr>
                <td colSpan={9} className="text-center py-10 text-muted-foreground text-[13px] italic">
                  No items scanned yet. Use the scan bar above.
                </td>
              </tr>
            ) : (
              barcodeItems.map((item, idx) => (
                <tr
                  key={idx}
                  className="border-b border-muted/60 hover:bg-primary/5 transition-colors"
                >
                  <td className="px-2 py-2 text-muted-foreground text-[11px]">{idx + 1}</td>
                  <td className="px-2 py-2 font-mono text-[11px] text-primary font-semibold">
                    {item.barcode || item.barcode_txt || "—"}
                  </td>
                  <td className="px-2 py-2 max-w-[160px]">
                    <div className="font-medium text-foreground truncate">{item.item_name || item.item || "—"}</div>
                    <div className="text-[10px] text-muted-foreground mt-0.5">
                      {[item.design_code, item.metal_purity].filter(Boolean).join(" · ")}
                    </div>
                  </td>
                  <td className="px-2 py-2 text-center">{item.pcs || 1}</td>
                  <td className="px-2 py-2 text-right">{fmtN(item.gw)}</td>
                  <td className="px-2 py-2 text-right">{fmtN(item.nw)}</td>
                  <td className="px-2 py-2 text-right text-muted-foreground">
                    {item.making_type === "val"
                      ? fmtINR(item.making)
                      : item.making
                      ? `${item.making}${item.making_type === "per_nw" ? "%" : "/g"}`
                      : "—"}
                  </td>
                  <td className="px-2 py-2 text-right font-bold">{fmtINR(item.amount)}</td>
                  <td className="px-2 py-2">
                    <button
                      onClick={() => onDeleteBarcodeItem(idx)}
                      className="text-border hover:text-destructive hover:bg-red-50 rounded p-0.5 transition-colors"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
          {barcodeItems.length > 0 && (
            <tfoot>
              <tr className="bg-muted/60 border-t border-border font-bold text-[13px]">
                <td colSpan={3} className="px-2 py-2 text-muted-foreground text-[11px]">
                  {barcodeItems.length} piece{barcodeItems.length !== 1 ? "s" : ""}
                </td>
                <td className="px-2 py-2 text-center">{totalPcs}</td>
                <td className="px-2 py-2 text-right">{fmtN(totalGW)}</td>
                <td className="px-2 py-2 text-right">{fmtN(totalNW)}</td>
                <td className="px-2 py-2"></td>
                <td className="px-2 py-2 text-right">{fmtINR(totalMRP)}</td>
                <td></td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
