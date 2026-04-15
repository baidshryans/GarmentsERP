import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Printer,
  Download,
  Search,
  Package,
  CheckSquare,
  Square,
  Filter,
  ImageIcon,
} from "lucide-react";
import BarcodeImages from "./BarcodeImages";
import { fetchBarcodeBulk, fetchMainItem, fetchPackets } from "@/services/apiService";

/* ═══════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════ */
const BASE_URL = sessionStorage.getItem("baseUrl") || "http://127.0.0.1:8000/";
const qrSrc = (path) => {
  if (!path) return null;
  if (path.startsWith("http")) return path;
  return `${BASE_URL.replace(/\/$/, "")}${path.startsWith("/") ? "" : "/"}${path}`;
};

const TAG_SIZES = {
  "99x12": { w: "99mm", h: "12mm", label: "99 \u00D7 12 mm", fontSize: "7px", qr: "10mm", gap: "3px", px: "2mm", py: "1mm" },
  "100x15": { w: "100mm", h: "15mm", label: "100 \u00D7 15 mm", fontSize: "8px", qr: "12mm", gap: "4px", px: "3mm", py: "1.5mm" },
};

/* ═══════════════════════════════════════════════════════════════
   Single barcode tag (inline style for print window)
   ═══════════════════════════════════════════════════════════════ */
function tagHTML(b, size) {
  const s = TAG_SIZES[size];
  const qrImg = b.qr_code
    ? `<img src="${qrSrc(b.qr_code)}" style="width:${s.qr};height:${s.qr};object-fit:contain;flex-shrink:0" />`
    : "";

  return `<div style="
    width:${s.w};height:${s.h};
    border:0.3px solid #ccc;
    border-radius:2px;
    padding:${s.py} ${s.px};
    display:flex;align-items:center;gap:${s.gap};
    box-sizing:border-box;overflow:hidden;
    page-break-inside:avoid;
    font-family:'Assistant',system-ui,sans-serif;
    font-size:${s.fontSize};line-height:1.2;
  ">
    ${qrImg}
    <div style="flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center;overflow:hidden">
      <div style="font-weight:700;font-family:monospace;letter-spacing:0.5px;white-space:nowrap">${b.barcode}</div>
      <div style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#444">
        ${b.item_name || b.item || ""} ${b.purity_name ? `| ${b.purity_name}` : ""}
      </div>
      <div style="color:#666;white-space:nowrap">
        Gw:${parseFloat(b.gw || 0).toFixed(3)}g Nw:${parseFloat(b.nw || 0).toFixed(3)}g${b.huid ? ` HUID:${b.huid}` : ""}
      </div>
    </div>
  </div>`;
}

/* ═══════════════════════════════════════════════════════════════
   Print labels in a new window
   ═══════════════════════════════════════════════════════════════ */
function printLabels(barcodes, size) {
  const s = TAG_SIZES[size];
  const labels = barcodes.map((b) => tagHTML(b, size)).join("");

  const win = window.open("", "_blank", "width=900,height=700");
  if (!win) { alert("Please allow popups to print labels."); return; }

  win.document.write(`<!DOCTYPE html>
<html><head>
  <meta charset="utf-8"/>
  <title>Barcode Labels</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@200..800&display=swap');
    @page { size: A4; margin: 5mm; }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Assistant', system-ui, sans-serif;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }
    .grid {
      display: flex; flex-wrap: wrap; gap: 2px;
      justify-content: flex-start;
    }
  </style>
</head>
<body>
  <div class="grid">${labels}</div>
</body></html>`);
  win.document.close();
  win.onload = () => setTimeout(() => { win.focus(); win.print(); }, 400);
}

/* ═══════════════════════════════════════════════════════════════
   Export selected barcodes as CSV
   ═══════════════════════════════════════════════════════════════ */
function exportCSV(barcodes) {
  const headers = ["Barcode", "Item", "Item Desc", "Purity", "GW", "NW", "Pcs", "HUID", "Design Code", "Value", "Making", "Created Date", "Voucher No"];
  const rows = barcodes.map((b) => [
    b.barcode,
    b.item || "",
    `"${(b.item_name || "").replace(/"/g, '""')}"`,
    b.purity_name || b.purity || "",
    b.gw,
    b.nw,
    b.pcs,
    b.huid || "",
    b.design_code || "",
    b.value || 0,
    b.making_val || 0,
    b.created_date || "",
    b.voucher_no || "",
  ]);

  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `barcodes_export_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ═══════════════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════════════ */
export default function BarcodeBulkOps() {
  // Filter state
  const [itemFilter, setItemFilter] = useState("__all__");
  const [packetFilter, setPacketFilter] = useState("__all__");
  const [stkFilter, setStkFilter] = useState("true");
  const [searchTerm, setSearchTerm] = useState("");

  // Master data for dropdowns
  const [items, setItems] = useState([]);
  const [packets, setPackets] = useState([]);

  // Results
  const [barcodes, setBarcodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  // Selection
  const [selected, setSelected] = useState(new Set());

  // Tag size
  const [tagSize, setTagSize] = useState("99x12");

  // Image sheet
  const [imageSheet, setImageSheet] = useState({ open: false, barcodeId: null, barcodeText: "" });

  // Load master data
  useEffect(() => {
    fetchMainItem({ type: "M" }).then((r) => { if (r.success) setItems(Array.isArray(r.data) ? r.data : r.data?.results ?? []); });
    fetchPackets().then((r) => {
      if (r.success) {
        const data = Array.isArray(r.data) ? r.data : r.data?.results ?? [];
        setPackets(data);
      }
    });
  }, []);

  // Fetch barcodes with filters
  const handleSearch = async () => {
    setLoading(true);
    setFetched(true);
    setSelected(new Set());
    const res = await fetchBarcodeBulk({
      item: itemFilter !== "__all__" ? itemFilter : undefined,
      packet: packetFilter !== "__all__" ? packetFilter : undefined,
      stk_status: stkFilter !== "__all__" ? stkFilter : undefined,
      search: searchTerm || undefined,
    });
    if (res.success) {
      setBarcodes(res.data.results || []);
    } else {
      setBarcodes([]);
    }
    setLoading(false);
  };

  // Selection helpers
  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };
  const selectAll = () => setSelected(new Set(barcodes.map((b) => b.id)));
  const selectNone = () => setSelected(new Set());
  const selectedBarcodes = barcodes.filter((b) => selected.has(b.id));

  return (
    <div className="flex flex-col gap-5">
      {/* ── Filters ────────────────────────────────────────── */}
      <div className="p-4 bg-muted/30 rounded-lg border border-border space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <Filter className="w-4 h-4" /> Filter Barcodes
        </div>

        <div className="flex flex-wrap items-end gap-3">
          {/* Item */}
          <div className="flex flex-col gap-1 min-w-44">
            <Label className="text-xs">Item</Label>
            <Select value={itemFilter} onValueChange={setItemFilter}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="All items" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All items</SelectItem>
                {items.map((it) => (
                  <SelectItem key={it.short_code} value={it.short_code}>
                    {it.short_code} — {it.item_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Packet */}
          <div className="flex flex-col gap-1 min-w-44">
            <Label className="text-xs">Packet</Label>
            <Select value={packetFilter} onValueChange={setPacketFilter}>
              <SelectTrigger className="h-9">
                <SelectValue placeholder="All packets" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All packets</SelectItem>
                {packets.map((p) => (
                  <SelectItem key={p.pckt_no} value={p.pckt_no}>
                    {p.pckt_no}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Stock status */}
          <div className="flex flex-col gap-1 w-32">
            <Label className="text-xs">Stock Status</Label>
            <Select value={stkFilter} onValueChange={setStkFilter}>
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="true">In Stock</SelectItem>
                <SelectItem value="false">Sold</SelectItem>
                <SelectItem value="__all__">All</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Search */}
          <div className="flex flex-col gap-1 flex-1 min-w-48">
            <Label className="text-xs">Search</Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
              <Input
                placeholder="Barcode, item name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="h-9 pl-8"
              />
            </div>
          </div>

          <Button size="sm" onClick={handleSearch} disabled={loading} className="h-9">
            {loading ? "Searching..." : "Search"}
          </Button>
        </div>
      </div>

      {/* ── Action bar ─────────────────────────────────────── */}
      {barcodes.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 px-1">
          {/* Select all / none */}
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={selectAll} className="h-8 text-xs">
              <CheckSquare className="w-3.5 h-3.5 mr-1" /> Select All
            </Button>
            <Button size="sm" variant="outline" onClick={selectNone} className="h-8 text-xs">
              <Square className="w-3.5 h-3.5 mr-1" /> Deselect
            </Button>
            <span className="text-xs text-muted-foreground">
              {selected.size} of {barcodes.length} selected
            </span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            {/* Tag size */}
            <Select value={tagSize} onValueChange={setTagSize}>
              <SelectTrigger className="h-8 w-36 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(TAG_SIZES).map(([key, val]) => (
                  <SelectItem key={key} value={key}>
                    {val.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Print */}
            <Button
              size="sm"
              onClick={() => printLabels(selectedBarcodes, tagSize)}
              disabled={selected.size === 0}
              className="h-8 bg-primary hover:bg-primary text-white"
            >
              <Printer className="w-3.5 h-3.5 mr-1.5" />
              Print {selected.size > 0 ? `(${selected.size})` : ""}
            </Button>

            {/* CSV Export */}
            <Button
              size="sm"
              variant="outline"
              onClick={() => exportCSV(selectedBarcodes)}
              disabled={selected.size === 0}
              className="h-8"
            >
              <Download className="w-3.5 h-3.5 mr-1.5" />
              CSV
            </Button>
          </div>
        </div>
      )}

      {/* ── Loading ────────────────────────────────────────── */}
      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      )}

      {/* ── Results table ──────────────────────────────────── */}
      {!loading && barcodes.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-3 py-2.5 text-center font-semibold w-10">
                    <input
                      type="checkbox"
                      checked={selected.size === barcodes.length && barcodes.length > 0}
                      onChange={(e) => (e.target.checked ? selectAll() : selectNone())}
                      className="rounded border-border"
                    />
                  </th>
                  <th className="px-3 py-2.5 text-left font-semibold">Barcode</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Item</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Purity</th>
                  <th className="px-3 py-2.5 text-right font-semibold">GW</th>
                  <th className="px-3 py-2.5 text-right font-semibold">NW</th>
                  <th className="px-3 py-2.5 text-center font-semibold">Pcs</th>
                  <th className="px-3 py-2.5 text-left font-semibold">HUID</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Design</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Date</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Packets</th>
                  <th className="px-3 py-2.5 text-center font-semibold">Images</th>
                </tr>
              </thead>
              <tbody>
                {barcodes.map((b, i) => {
                  const isSelected = selected.has(b.id);
                  return (
                    <tr
                      key={b.id}
                      onClick={() => toggleSelect(b.id)}
                      className={`border-t border-border/50 cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-violet-50 hover:bg-violet-100/80"
                          : i % 2 === 1
                            ? "bg-muted/20 hover:bg-accent/30"
                            : "hover:bg-accent/30"
                      }`}
                    >
                      <td className="px-3 py-2 text-center" onClick={(e) => e.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelect(b.id)}
                          className="rounded border-border"
                        />
                      </td>
                      <td className="px-3 py-2 font-mono text-xs font-semibold">{b.barcode}</td>
                      <td className="px-3 py-2">
                        <span className="text-xs font-medium">{b.item}</span>
                        {b.item_name && (
                          <span className="text-xs text-muted-foreground ml-1.5">{b.item_name}</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs">{b.purity_name || b.purity}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs">
                        {parseFloat(b.gw || 0).toFixed(3)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs">
                        {parseFloat(b.nw || 0).toFixed(3)}
                      </td>
                      <td className="px-3 py-2 text-center text-xs">{b.pcs}</td>
                      <td className="px-3 py-2 text-xs font-mono">{b.huid || "-"}</td>
                      <td className="px-3 py-2 text-xs">{b.design_code || "-"}</td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {b.created_date ? new Date(b.created_date).toLocaleDateString("en-GB") : "-"}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {(b.barcodedetails_set || []).map((d) => d.packet || d.packet_text).filter(Boolean).join(", ") || "-"}
                      </td>
                      <td className="px-3 py-2 text-center" onClick={(e) => e.stopPropagation()}>
                        <button
                          title="View / Add Images"
                          className="text-muted-foreground hover:text-primary transition-colors"
                          onClick={() => setImageSheet({ open: true, barcodeId: b.id, barcodeText: b.barcode })}
                        >
                          <ImageIcon className="size-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Empty states ───────────────────────────────────── */}
      {!loading && fetched && barcodes.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-muted/50 p-4 mb-4">
            <Package className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">No barcodes found</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Try adjusting your filters or search term.
          </p>
        </div>
      )}

      {!loading && !fetched && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-muted/50 p-4 mb-4">
            <Package className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">Barcode Bulk Operations</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Filter by item, packet, or stock status, then select barcodes to print labels or export to CSV.
          </p>
        </div>
      )}

      {/* Barcode Images Sheet */}
      <BarcodeImages
        barcodeId={imageSheet.barcodeId}
        barcodeText={imageSheet.barcodeText}
        open={imageSheet.open}
        onOpenChange={(v) => setImageSheet((prev) => ({ ...prev, open: v }))}
      />
    </div>
  );
}
