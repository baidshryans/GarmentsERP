import { useState, useEffect } from "react";
import { formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import { Download, Filter, BookOpen } from "lucide-react";
import { getRawMaterialLedger, fetchMainItem, getFiscalYears } from "@/services/apiService";
import { isValidDateRange } from "@/lib/dateRange";

const fmtWt = (v) => formatNumber(v, { decimals: 3 });
const fmtAmt = (v) => formatNumber(v, { decimals: 2 });
const today = new Date().toISOString().split("T")[0];

const TRANS_LABELS = {
  OPENING: "Opening Balance",
  PURCHASE: "Purchase",
  PURCHASE_RETURN: "Purchase Return",
  PURCHASE_DEL: "Purchase (Reversed)",
  KR_GOLD_ISSUE: "Karigar Gold Issue",
  KR_GOLD_ISSUE_DEL: "Gold Issue (Reversed)",
  KR_STONE_ISSUE: "Karigar Stone Issue",
  KR_STONE_ISSUE_DEL: "Stone Issue (Reversed)",
  KR_STONE_RETURN: "Karigar Stone Return",
  KR_STONE_RETURN_DEL: "Stone Return (Reversed)",
  ADJUSTMENT: "Manual Adjustment",
};

function exportCSV(data, itemName) {
  const headers = ["Date", "Trans Type", "Bill No", "Packet", "Purity", "Pcs", "Ct", "Gw", "Rate", "Amount", "Running Pcs", "Running Ct", "Running Gw"];
  const rows = data.map((r) => [
    new Date(r.date).toLocaleDateString("en-GB"),
    r.trans_type, r.billno || "", r.packet || "", r.purity || "-",
    r.pcs, r.ct, r.gw, r.rate, r.amt,
    r.running_pcs, r.running_ct, r.running_gw,
  ]);
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `raw_material_ledger_${itemName || "all"}_${today}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function RawMaterialLedger() {
  const [items, setItems] = useState([]);
  const [itemFilter, setItemFilter] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState(today);
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  useEffect(() => {
    fetchMainItem().then((r) => { if (r.success) setItems(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])); });
    getFiscalYears().then((res) => {
      if (res.success) {
        const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
        const activeFy = data.find((fy) => fy.is_active);
        if (activeFy?.fy_start) {
          setFromDate(activeFy.fy_start);
        } else {
          const now = new Date();
          const fyYear = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
          setFromDate(`${fyYear}-04-01`);
        }
      }
    });
  }, []);

  const handleSearch = async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      alert("From date cannot be after To date.");
      return;
    }
    if (!itemFilter) return;
    setLoading(true);
    setFetched(true);
    const params = { item: itemFilter };
    if (fromDate) params.from_date = fromDate;
    if (toDate) params.to_date = toDate;
    const res = await getRawMaterialLedger(params);
    if (res.success) {
      setData(res.data.results || []);
    } else {
      setData([]);
    }
    setLoading(false);
  };

  const selectedItemName = items.find((i) => String(i.id) === itemFilter)?.item_name || "";

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="p-4 bg-muted/30 rounded-lg border border-border space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <Filter className="size-4" /> Raw Material Ledger
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1 min-w-56">
            <Label className="text-xs">Item (required)</Label>
            <Select value={itemFilter} onValueChange={setItemFilter}>
              <SelectTrigger className="h-9"><SelectValue placeholder="Select item..." /></SelectTrigger>
              <SelectContent>
                {items.map((it) => (
                  <SelectItem key={it.id} value={String(it.id)}>
                    {it.short_code} - {it.item_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1 w-36">
            <Label className="text-xs">From Date</Label>
            <Input type="date" className="h-9" value={fromDate} onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} />
          </div>
          <div className="flex flex-col gap-1 w-36">
            <Label className="text-xs">To Date</Label>
            <Input type="date" className="h-9" value={toDate} onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} />
          </div>
          <Button size="sm" onClick={handleSearch} disabled={loading || !itemFilter} className="h-9">
            {loading ? "Loading..." : "Search"}
          </Button>
          {data.length > 0 && (
            <Button size="sm" variant="outline" onClick={() => exportCSV(data, selectedItemName)} className="h-9 ml-auto">
              <Download className="w-3.5 h-3.5 mr-1.5" /> CSV
            </Button>
          )}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {/* Table */}
      {!loading && data.length > 0 && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-3 py-2.5 text-left font-semibold">Date</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Type</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Bill No</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Packet</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Purity</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Pcs</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Ct</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Gw (g)</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Rate</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Amount</th>
                  <th className="px-3 py-2.5 text-right font-semibold bg-muted/80">Bal Pcs</th>
                  <th className="px-3 py-2.5 text-right font-semibold bg-muted/80">Bal Ct</th>
                  <th className="px-3 py-2.5 text-right font-semibold bg-muted/80">Bal Gw</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r, i) => {
                  const isPositive = r.gw > 0 || r.ct > 0 || r.pcs > 0;
                  const rowColor = isPositive ? "text-green-700" : "text-red-700";
                  return (
                    <tr key={r.id} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/20" : ""}`}>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {new Date(r.date).toLocaleDateString("en-GB")}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        {TRANS_LABELS[r.trans_type] || r.trans_type}
                      </td>
                      <td className="px-3 py-2 text-xs font-mono">{r.billno || "-"}</td>
                      <td className="px-3 py-2 text-xs">{r.packet || "-"}</td>
                      <td className="px-3 py-2 text-xs">{r.purity || "-"}</td>
                      <td className={`px-3 py-2 text-right tabular-nums text-xs ${rowColor}`}>
                        {r.pcs !== 0 ? (r.pcs > 0 ? `+${r.pcs}` : r.pcs) : "-"}
                      </td>
                      <td className={`px-3 py-2 text-right tabular-nums text-xs ${rowColor}`}>
                        {Math.abs(r.ct) > 0.001 ? (r.ct > 0 ? `+${fmtWt(r.ct)}` : fmtWt(r.ct)) : "-"}
                      </td>
                      <td className={`px-3 py-2 text-right tabular-nums text-xs font-medium ${rowColor}`}>
                        {Math.abs(r.gw) > 0.001 ? (r.gw > 0 ? `+${fmtWt(r.gw)}` : fmtWt(r.gw)) : "-"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs">
                        {r.rate ? fmtAmt(r.rate) : "-"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs">
                        {r.amt ? fmtAmt(r.amt) : "-"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs font-semibold bg-muted/30">
                        {r.running_pcs}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs font-semibold bg-muted/30">
                        {fmtWt(r.running_ct)}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-xs font-semibold bg-muted/30">
                        {fmtWt(r.running_gw)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty states */}
      {!loading && fetched && data.length === 0 && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-muted/50 p-4 mb-4">
            <BookOpen className="size-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">No transactions found</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            No raw material transactions for this item in the selected date range.
          </p>
        </div>
      )}

      {!loading && !fetched && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-muted/50 p-4 mb-4">
            <BookOpen className="size-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">Raw Material Movement Ledger</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Select an item to view its transaction history with running balances.
          </p>
        </div>
      )}
    </div>
  );
}
