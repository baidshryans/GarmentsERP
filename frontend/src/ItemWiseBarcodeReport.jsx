import { useState, useEffect } from "react";
import { FileText, Printer, Search, Gem } from "lucide-react";
import {
  fetchItemWiseBarcode,
  fetchMainItem,
  fetchPurity,
} from "@/services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";

const today = new Date().toISOString().split("T")[0];
const ALL = "__all__";
const COLS = 19; // total columns (group-header colspan)

const n3 = (x) => (Number(x) || 0).toFixed(3);
// Amounts render without decimals, with Indian-style grouping.
const money = (x) =>
  Math.round(Number(x) || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

const fmtDate = (d) => {
  if (!d) return "";
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y}`;
};

// Flatten an item's barcodes into detail rows. Each barcode yields
// max(stone, other, 1) rows; barcode-level cells render only on the first row.
const buildRows = (item) => {
  const rows = [];
  const subtotal = { pcs: 0, gw: 0, nw: 0, value: 0 };
  (item.barcodemain_set || []).forEach((bc) => {
    subtotal.pcs += Number(bc.pcs) || 0;
    subtotal.gw += Number(bc.gw) || 0;
    subtotal.nw += Number(bc.nw) || 0;
    subtotal.value += Number(bc.total_amount) || 0;
    const stone = bc.stone || [];
    const other = bc.other || [];
    const lines = Math.max(stone.length, other.length, 1);
    for (let i = 0; i < lines; i++) {
      rows.push({ bc, first: i === 0, stone: stone[i], other: other[i] });
    }
  });
  return { rows, subtotal };
};

export default function ItemwiseBarcodeReport() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [asOnDate, setAsOnDate] = useState(today);
  const [itemFilter, setItemFilter] = useState(ALL);
  const [purityFilter, setPurityFilter] = useState(ALL);
  const [searchTerm, setSearchTerm] = useState("");

  const [items, setItems] = useState([]);
  const [purities, setPurities] = useState([]);

  useEffect(() => {
    fetchMainItem({ type: "M" }).then((r) => {
      if (r.success) setItems(Array.isArray(r.data) ? r.data : r.data?.results ?? []);
    });
    fetchPurity().then((r) => {
      if (r.success) setPurities(Array.isArray(r.data) ? r.data : r.data?.results ?? []);
    });
  }, []);

  const fetchData = async (override = {}) => {
    const d = override.asOnDate ?? asOnDate;
    if (!d) {
      setError('Please choose an "as on" date.');
      return;
    }
    setLoading(true);
    setError("");
    try {
      const item = (override.itemFilter ?? itemFilter) !== ALL ? (override.itemFilter ?? itemFilter) : undefined;
      const purity = (override.purityFilter ?? purityFilter) !== ALL ? (override.purityFilter ?? purityFilter) : undefined;
      const result = await fetchItemWiseBarcode(d, { item, purity });
      setData(Array.isArray(result) ? result : []);
    } catch (err) {
      setError(err?.response?.data?.error || err.message || "Failed to load report");
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  const term = searchTerm.trim().toLowerCase();
  const filteredData = !term
    ? data
    : data.filter(
        (item) =>
          item.short_code?.toLowerCase().includes(term) ||
          item.item_name?.toLowerCase().includes(term) ||
          (item.barcodemain_set || []).some((b) => b.barcode?.toLowerCase().includes(term))
      );

  const grand = filteredData.reduce(
    (acc, item) => {
      (item.barcodemain_set || []).forEach((bc) => {
        acc.pcs += Number(bc.pcs) || 0;
        acc.gw += Number(bc.gw) || 0;
        acc.nw += Number(bc.nw) || 0;
        acc.value += Number(bc.total_amount) || 0;
        acc.barcodes += 1;
      });
      return acc;
    },
    { pcs: 0, gw: 0, nw: 0, value: 0, barcodes: 0 }
  );

  const handlePrint = () => {
    const groups = filteredData
      .map((item) => {
        const { rows, subtotal } = buildRows(item);
        if (rows.length === 0) return "";
        const body = rows
          .map((r) => {
            const { bc, first, stone, other } = r;
            return `<tr>
              <td class="l">${first ? bc.barcode || "" : ""}</td>
              <td class="l">${first ? bc.design_code || "" : ""}</td>
              <td class="l">${first ? bc.order_no || "" : ""}</td>
              <td class="l">${first ? bc.purity || "" : ""}</td>
              <td>${first ? (bc.pcs ?? "") : ""}</td>
              <td>${first ? n3(bc.gw) : ""}</td>
              <td>${first ? n3(bc.nw) : ""}</td>
              <td class="l">${stone?.sub || ""}</td>
              <td>${stone ? (stone.pcs ?? "") : ""}</td>
              <td>${stone ? n3(stone.ct) : ""}</td>
              <td>${stone ? money(stone.rate) : ""}</td>
              <td>${stone ? money(stone.value) : ""}</td>
              <td class="l">${other?.code || ""}</td>
              <td>${other ? (other.pcs ?? "") : ""}</td>
              <td>${other ? n3(other.gw) : ""}</td>
              <td>${other ? money(other.rate) : ""}</td>
              <td>${other ? money(other.value) : ""}</td>
              <td>${first ? money(bc.making_val) : ""}</td>
              <td class="b">${first ? money(bc.total_amount) : ""}</td>
            </tr>`;
          })
          .join("");
        return `<tr class="grp">
            <td colspan="${COLS}" class="l">${item.item_name || ""} (${item.short_code || ""})</td>
          </tr>${body}
          <tr class="sub">
            <td colspan="4" class="l">Subtotal</td>
            <td>${subtotal.pcs}</td>
            <td>${n3(subtotal.gw)}</td>
            <td>${n3(subtotal.nw)}</td>
            <td colspan="10"></td>
            <td></td>
            <td class="b">${money(subtotal.value)}</td>
          </tr>`;
      })
      .join("");

    const grandRow = `<tr class="gt">
        <td colspan="4" class="l">Grand Total (${grand.barcodes} barcode${grand.barcodes !== 1 ? "s" : ""})</td>
        <td>${grand.pcs}</td>
        <td>${n3(grand.gw)}</td>
        <td>${n3(grand.nw)}</td>
        <td colspan="10"></td>
        <td></td>
        <td class="b">${money(grand.value)}</td>
      </tr>`;

    const filterLine = [
      itemFilter !== ALL ? `Item: ${itemFilter}` : null,
      purityFilter !== ALL ? `Purity: ${purityFilter}` : null,
    ]
      .filter(Boolean)
      .join(" | ");

    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Barcode Value Report — As on ${fmtDate(asOnDate)}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; font-size: 10px; color: #1f2937; padding: 16px; }
    h2 { text-align: center; font-size: 14px; font-weight: 700; margin-bottom: 4px; }
    p.sub { text-align: center; font-size: 11px; color: #6b7280; margin-bottom: 14px; }
    table { width: 100%; border-collapse: collapse; }
    /* horizontal lines only — no vertical rules */
    th, td { padding: 3px 6px; text-align: right; white-space: nowrap; border-bottom: 1px solid #e5e7eb; }
    td.l, th.l { text-align: left; }
    td.b { font-weight: 600; }
    thead th { font-size: 9px; text-transform: uppercase; letter-spacing: 0.03em; color: #6b7280; background: #f9fafb; }
    tr.grp td { background: #f3f4f6; font-weight: 700; }
    tr.sub td { background: #fafafa; font-weight: 600; }
    tr.gt td { background: #f3f4f6; font-weight: 700; border-top: 2px solid #d1d5db; }
    @media print { @page { size: A4 portrait; margin: 14mm 12mm; } body { padding: 0; } }
  </style>
</head>
<body>
  <h2>Barcode Wise Value Report</h2>
  <p class="sub">As on ${fmtDate(asOnDate)} &nbsp;|&nbsp; ${filteredData.length} item${filteredData.length !== 1 ? "s" : ""}${filterLine ? ` &nbsp;|&nbsp; ${filterLine}` : ""}</p>
  <table>
    <thead>
      <tr>
        <th class="l" rowspan="2">Barcode</th><th class="l" rowspan="2">Design No</th><th class="l" rowspan="2">Order No</th>
        <th class="l" rowspan="2">Purity</th>
        <th rowspan="2">Pcs</th><th rowspan="2">Gw</th><th rowspan="2">Nw</th>
        <th colspan="5">Stone</th>
        <th colspan="5">Other</th>
        <th rowspan="2">Making</th><th rowspan="2">Value</th>
      </tr>
      <tr>
        <th class="l">Pckt</th><th>Pcs</th><th>Weight</th><th>Rate</th><th>Value</th>
        <th class="l">Item</th><th>Pcs</th><th>Weight</th><th>Rate</th><th>Value</th>
      </tr>
    </thead>
    <tbody>${groups}</tbody>
    <tfoot>${grandRow}</tfoot>
  </table>
  <script>window.onload = () => { window.print(); }<\/script>
</body>
</html>`;

    const win = window.open("", "_blank");
    win.document.write(html);
    win.document.close();
  };

  // ── cell helpers (flat — horizontal separators only, no vertical rules) ──
  const th = "px-3 py-2 font-medium whitespace-nowrap";
  const td = "px-3 py-2 whitespace-nowrap";
  const R = "text-right tabular-nums";
  const L = "text-left";
  const dim = "text-gray-300";

  return (
    <div className="space-y-4">
      {/* Header + Print */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
          <FileText className="size-5 text-primary" />
          Barcode Value Report
        </h1>
        <Button
          size="sm"
          variant="outline"
          onClick={handlePrint}
          disabled={loading || filteredData.length === 0}
        >
          <Printer className="size-4 mr-1" />
          Print / PDF
        </Button>
      </div>

      {/* Filter card */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Gem className="size-4 text-primary" />
          <h2 className="text-sm font-semibold text-gray-800">Filters</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <Label className="text-xs">As on Date</Label>
            <Input type="date" value={asOnDate} onChange={(e) => setAsOnDate(e.target.value)} />
          </div>
          <div>
            <Label className="text-xs">Item</Label>
            <Select value={itemFilter} onValueChange={setItemFilter}>
              <SelectTrigger><SelectValue placeholder="All items" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All items</SelectItem>
                {items.map((it) => (
                  <SelectItem key={it.short_code} value={it.short_code}>
                    {it.item_name} ({it.short_code})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Purity</Label>
            <Select value={purityFilter} onValueChange={setPurityFilter}>
              <SelectTrigger><SelectValue placeholder="All purity" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All purity</SelectItem>
                {purities.map((p) => (
                  <SelectItem key={p.id ?? p.purity} value={p.purity}>{p.purity}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Search</Label>
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Item or barcode..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>
          <div className="flex items-end">
            <Button className="w-full" onClick={() => fetchData()} disabled={loading}>
              {loading ? "Loading..." : "Apply"}
            </Button>
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      )}

      {!loading && (
        <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between gap-2 bg-gray-50/50">
            <div className="flex items-center gap-2">
              <Gem className="size-4 text-primary" />
              <h3 className="text-sm font-semibold text-gray-800">In-Stock Barcodes</h3>
            </div>
            <span className="text-xs text-gray-500">As on {fmtDate(asOnDate)}</span>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
                <tr>
                  <th rowSpan={2} className={`${th} ${L}`}>Barcode</th>
                  <th rowSpan={2} className={`${th} ${L}`}>Design No</th>
                  <th rowSpan={2} className={`${th} ${L}`}>Order No</th>
                  <th rowSpan={2} className={`${th} ${L}`}>Purity</th>
                  <th rowSpan={2} className={`${th} ${R}`}>Pcs</th>
                  <th rowSpan={2} className={`${th} ${R}`}>Gw</th>
                  <th rowSpan={2} className={`${th} ${R}`}>Nw</th>
                  <th colSpan={5} className={`${th} text-center text-primary border-b border-gray-100`}>Stone</th>
                  <th colSpan={5} className={`${th} text-center text-primary border-b border-gray-100`}>Other</th>
                  <th rowSpan={2} className={`${th} ${R}`}>Making</th>
                  <th rowSpan={2} className={`${th} ${R}`}>Value</th>
                </tr>
                <tr>
                  <th className={`${th} ${L}`}>Pckt</th>
                  <th className={`${th} ${R}`}>Pcs</th>
                  <th className={`${th} ${R}`}>Weight</th>
                  <th className={`${th} ${R}`}>Rate</th>
                  <th className={`${th} ${R}`}>Value</th>
                  <th className={`${th} ${L}`}>Item</th>
                  <th className={`${th} ${R}`}>Pcs</th>
                  <th className={`${th} ${R}`}>Weight</th>
                  <th className={`${th} ${R}`}>Rate</th>
                  <th className={`${th} ${R}`}>Value</th>
                </tr>
              </thead>
              <tbody>
                {filteredData.map((item, idx) => {
                  const { rows, subtotal } = buildRows(item);
                  return (
                    <ReportGroup
                      key={item.short_code || idx}
                      item={item}
                      rows={rows}
                      subtotal={subtotal}
                      td={td}
                      R={R}
                      L={L}
                      dim={dim}
                    />
                  );
                })}
                {filteredData.length > 0 && (
                  <tr className="border-t-2 border-gray-200 bg-gray-50 font-bold text-gray-800">
                    <td colSpan={4} className={`${td} ${L}`}>
                      Grand Total ({grand.barcodes} barcode{grand.barcodes !== 1 ? "s" : ""})
                    </td>
                    <td className={`${td} ${R}`}>{grand.pcs}</td>
                    <td className={`${td} ${R}`}>{n3(grand.gw)}</td>
                    <td className={`${td} ${R}`}>{n3(grand.nw)}</td>
                    <td colSpan={10} className={td}></td>
                    <td className={td}></td>
                    <td className={`${td} ${R}`}>{money(grand.value)}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {filteredData.length === 0 && !loading && (
            <div className="text-center py-10 text-sm text-gray-400">
              No in-stock barcodes found for the selected date / filters.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ReportGroup({ item, rows, subtotal, td, R, L, dim }) {
  const n3 = (x) => (Number(x) || 0).toFixed(3);
  const money = (x) =>
    Math.round(Number(x) || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  return (
    <>
      <tr className="border-t border-gray-100 bg-gray-50/70">
        <td colSpan={COLS} className={`${td} font-semibold text-gray-800`}>
          {item.item_name} <span className="text-gray-400 font-normal">({item.short_code})</span>
        </td>
      </tr>
      {rows.map((r, i) => {
        const { bc, first, stone, other } = r;
        return (
          <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
            <td className={`${td} ${L} font-medium`}>{first ? bc.barcode : ""}</td>
            <td className={`${td} ${L}`}>{first ? bc.design_code || "" : ""}</td>
            <td className={`${td} ${L}`}>{first ? bc.order_no || "" : ""}</td>
            <td className={`${td} ${L}`}>{first ? bc.purity || "" : ""}</td>
            <td className={`${td} ${R}`}>{first ? (bc.pcs ?? "") : ""}</td>
            <td className={`${td} ${R}`}>{first ? n3(bc.gw) : ""}</td>
            <td className={`${td} ${R}`}>{first ? n3(bc.nw) : ""}</td>
            <td className={`${td} ${L}`}>{stone?.sub || <span className={dim}>·</span>}</td>
            <td className={`${td} ${R}`}>{stone ? (stone.pcs ?? "") : ""}</td>
            <td className={`${td} ${R}`}>{stone ? n3(stone.ct) : ""}</td>
            <td className={`${td} ${R}`}>{stone ? money(stone.rate) : ""}</td>
            <td className={`${td} ${R}`}>{stone ? money(stone.value) : ""}</td>
            <td className={`${td} ${L}`}>{other?.code || <span className={dim}>·</span>}</td>
            <td className={`${td} ${R}`}>{other ? (other.pcs ?? "") : ""}</td>
            <td className={`${td} ${R}`}>{other ? n3(other.gw) : ""}</td>
            <td className={`${td} ${R}`}>{other ? money(other.rate) : ""}</td>
            <td className={`${td} ${R}`}>{other ? money(other.value) : ""}</td>
            <td className={`${td} ${R}`}>{first ? money(bc.making_val) : ""}</td>
            <td className={`${td} ${R} font-semibold`}>{first ? money(bc.total_amount) : ""}</td>
          </tr>
        );
      })}
      <tr className="border-t border-gray-100 bg-gray-50/40 text-gray-700 font-medium">
        <td colSpan={4} className={`${td} ${L}`}>Subtotal</td>
        <td className={`${td} ${R}`}>{subtotal.pcs}</td>
        <td className={`${td} ${R}`}>{n3(subtotal.gw)}</td>
        <td className={`${td} ${R}`}>{n3(subtotal.nw)}</td>
        <td colSpan={10} className={td}></td>
        <td className={td}></td>
        <td className={`${td} ${R} font-semibold`}>{money(subtotal.value)}</td>
      </tr>
    </>
  );
}
