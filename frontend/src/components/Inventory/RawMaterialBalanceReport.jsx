import { useState, useEffect, useRef } from "react";
import { formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import { Download, Filter, Package } from "lucide-react";
import { getRawMaterialBalance, fetchMainItem } from "@/services/apiService";

const ITEM_TYPES = [
  { value: "__all__", label: "All Types" },
  { value: "M", label: "Metal" },
  { value: "R", label: "Raw" },
  { value: "S", label: "Stone" },
  { value: "O", label: "Other" },
  { value: "C", label: "Coin" },
];

const fmtWt = (v) => formatNumber(v, { decimals: 3 });
const fmtQty = (v) => formatNumber(v);

function exportCSV(data) {
  const headers = ["Item", "Item Name", "Type", "Packet", "Purity", "Pcs", "Ct", "Gw"];
  const rows = data.map((r) => [
    r.item, `"${r.item_name}"`, r.item_type, r.packet || "", r.purity || "",
    r.pcs, r.ct, r.gw,
  ]);
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `raw_material_balance_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function RawMaterialBalanceReport() {
  const [itemType, setItemType] = useState("__all__");
  const [items, setItems] = useState([]);
  const [itemFilter, setItemFilter] = useState("__all__");
  const [data, setData] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  useEffect(() => {
    fetchMainItem().then((r) => { if (r.success) setItems(Array.isArray(r.data) ? r.data : r.data?.results ?? []); });
  }, []);

  const handleSearch = async () => {
    setLoading(true);
    setFetched(true);
    const params = {};
    if (itemType !== "__all__") params.item_type = itemType;
    if (itemFilter !== "__all__") params.item = itemFilter;
    const res = await getRawMaterialBalance(params);
    if (res.success) {
      setData(res.data.results || []);
      setSummary(res.data.summary || null);
    } else {
      setData([]);
      setSummary(null);
    }
    setLoading(false);
  };

  useEffect(() => { handleSearch(); }, []);

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="p-4 bg-muted/30 rounded-lg border border-border space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <Filter className="size-4" /> Raw Material Balance
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1 w-40">
            <Label className="text-xs">Item Type</Label>
            <Select value={itemType} onValueChange={setItemType}>
              <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
              <SelectContent>
                {ITEM_TYPES.map((t) => (
                  <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1 min-w-48">
            <Label className="text-xs">Item</Label>
            <Select value={itemFilter} onValueChange={setItemFilter}>
              <SelectTrigger className="h-9"><SelectValue placeholder="All items" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All items</SelectItem>
                {items.map((it) => (
                  <SelectItem key={it.id || it.short_code} value={String(it.id || it.short_code)}>
                    {it.short_code} - {it.item_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button size="sm" onClick={handleSearch} disabled={loading} className="h-9">
            {loading ? "Loading..." : "Search"}
          </Button>
          {data.length > 0 && (
            <Button size="sm" variant="outline" onClick={() => exportCSV(data)} className="h-9 ml-auto">
              <Download className="w-3.5 h-3.5 mr-1.5" /> CSV
            </Button>
          )}
        </div>
      </div>

      {/* Summary cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[
            { label: "Items", value: summary.count },
            { label: "Total Pcs", value: fmtQty(summary.total_pcs) },
            { label: "Total Ct", value: fmtWt(summary.total_ct) },
            { label: "Total Gw (g)", value: fmtWt(summary.total_gw) },
          ].map((c) => (
            <div key={c.label} className="p-3 rounded-lg border border-border bg-muted/20 text-center">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider">{c.label}</p>
              <p className="text-lg font-semibold tabular-nums">{c.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {/* Table */}
      {!loading && data.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-3 py-2.5 text-left font-semibold">Item</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Name</th>
                  <th className="px-3 py-2.5 text-center font-semibold">Type</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Packet</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Purity</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Pcs</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Ct</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Gw (g)</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r, i) => (
                  <tr key={r.id} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/20" : ""}`}>
                    <td className="px-3 py-2 text-xs font-mono font-semibold">{r.item}</td>
                    <td className="px-3 py-2 text-xs">{r.item_name}</td>
                    <td className="px-3 py-2 text-xs text-center">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        r.item_type === "M" ? "bg-amber-100 text-amber-800" :
                        r.item_type === "S" ? "bg-blue-100 text-blue-800" :
                        r.item_type === "R" ? "bg-green-100 text-green-800" :
                        "bg-gray-100 text-gray-700"
                      }`}>
                        {r.item_type}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs">{r.packet || "-"}</td>
                    <td className="px-3 py-2 text-xs">{r.purity || "-"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{r.pcs}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{fmtWt(r.ct)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs font-medium">{fmtWt(r.gw)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="bg-muted/50 font-semibold text-xs border-t-2 border-border">
                  <td colSpan={5} className="px-3 py-2">Total</td>
                  <td className="px-3 py-2 text-right tabular-nums">{summary ? fmtQty(summary.total_pcs) : ""}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{summary ? fmtWt(summary.total_ct) : ""}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{summary ? fmtWt(summary.total_gw) : ""}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}

      {/* Empty */}
      {!loading && fetched && data.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-muted/50 p-4 mb-4">
            <Package className="size-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">No raw material stock found</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Raw material balances are updated automatically from purchases and karigar issues.
          </p>
        </div>
      )}
    </div>
  );
}
