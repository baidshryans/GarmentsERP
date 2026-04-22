import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Download, Hammer, Package } from "lucide-react";
import { getSemiFinishedStock } from "@/services/apiService";

const fmtWt = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const fmtQty = (v) => Number(v).toLocaleString("en-IN");

function exportCSV(wipData, pendingData) {
  let csv = "\uFEFF";

  // WIP section
  csv += "WITH KARIGAR (WIP)\n";
  csv += "Karigar,Issue Slip,Issue Date,Item,Item Name,Purity,Pcs,Approx Wt,Design,Days Pending\n";
  for (const r of wipData) {
    csv += [
      `"${r.karigar || ""}"`, r.issue_slip_no, r.issue_date, r.item, `"${r.item_name || ""}"`,
      r.purity || "", r.pcs, r.approx_wt || "", r.design_code || "", r.days_pending || "",
    ].join(",") + "\n";
  }

  csv += "\nPENDING BARCODE\n";
  csv += "Item,Item Name,Purity,Pcs,Gw,Nw,Design,Created Date,Source,Voucher No\n";
  for (const r of pendingData) {
    csv += [
      r.item, `"${r.item_name || ""}"`, r.purity || "", r.pcs, r.gw, r.nw,
      r.design_code || "", r.created_date || "", r.created_from || "", r.voucher_no || "",
    ].join(",") + "\n";
  }

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `semi_finished_stock_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function SemiFinishedStockReport() {
  const [tab, setTab] = useState("wip");
  const [wipData, setWipData] = useState([]);
  const [pendingData, setPendingData] = useState([]);
  const [wipSummary, setWipSummary] = useState(null);
  const [pendingSummary, setPendingSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const res = await getSemiFinishedStock();
    if (res.success) {
      setWipData(res.data.with_karigar || []);
      setPendingData(res.data.pending_barcode || []);
      setWipSummary(res.data.with_karigar_summary || null);
      setPendingSummary(res.data.pending_barcode_summary || null);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  return (
    <div className="flex flex-col gap-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded-lg border border-primary/20 bg-primary/5 text-center">
          <p className="text-[10px] text-primary uppercase tracking-wider">With Karigar</p>
          <p className="text-lg font-semibold text-primary tabular-nums">{wipSummary?.count || 0} items</p>
          <p className="text-xs text-primary">{fmtWt(wipSummary?.total_approx_wt || 0)} g approx</p>
        </div>
        <div className="p-3 rounded-lg border border-primary/20 bg-primary/5 text-center">
          <p className="text-[10px] text-primary uppercase tracking-wider">WIP Pcs</p>
          <p className="text-lg font-semibold text-primary tabular-nums">{fmtQty(wipSummary?.total_pcs || 0)}</p>
        </div>
        <div className="p-3 rounded-lg border border-violet-200 bg-violet-50/50 text-center">
          <p className="text-[10px] text-primary uppercase tracking-wider">Pending Barcode</p>
          <p className="text-lg font-semibold text-primary tabular-nums">{pendingSummary?.count || 0} items</p>
          <p className="text-xs text-primary">{fmtWt(pendingSummary?.total_gw || 0)} g</p>
        </div>
        <div className="p-3 rounded-lg border border-violet-200 bg-violet-50/50 text-center">
          <p className="text-[10px] text-primary uppercase tracking-wider">Pending Pcs</p>
          <p className="text-lg font-semibold text-primary tabular-nums">{fmtQty(pendingSummary?.total_pcs || 0)}</p>
        </div>
      </div>

      {/* Tabs + Export */}
      <div className="flex items-center gap-2">
        <div className="flex rounded-lg border border-border overflow-hidden">
          <button
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              tab === "wip" ? "bg-primary text-white" : "bg-muted/30 text-muted-foreground hover:bg-muted/50"
            }`}
            onClick={() => setTab("wip")}
          >
            <Hammer className="w-3.5 h-3.5 inline mr-1.5" />
            With Karigar ({wipSummary?.count || 0})
          </button>
          <button
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              tab === "pending" ? "bg-primary text-white" : "bg-muted/30 text-muted-foreground hover:bg-muted/50"
            }`}
            onClick={() => setTab("pending")}
          >
            <Package className="w-3.5 h-3.5 inline mr-1.5" />
            Pending Barcode ({pendingSummary?.count || 0})
          </button>
        </div>
        <Button size="sm" variant="outline" onClick={() => exportCSV(wipData, pendingData)} className="h-8 ml-auto">
          <Download className="w-3.5 h-3.5 mr-1.5" /> CSV
        </Button>
        <Button size="sm" variant="outline" onClick={load} disabled={loading} className="h-8">
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {/* WIP Table */}
      {!loading && tab === "wip" && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-primary/10 text-xs uppercase tracking-wider text-primary">
                  <th className="px-3 py-2.5 text-left font-semibold">Karigar</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Issue Slip</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Issue Date</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Item</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Purity</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Pcs</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Approx Wt</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Design</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Days</th>
                </tr>
              </thead>
              <tbody>
                {wipData.length === 0 && (
                  <tr><td colSpan={9} className="text-center py-8 text-sm text-muted-foreground">No items currently with karigar.</td></tr>
                )}
                {wipData.map((r, i) => (
                  <tr key={r.id} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/20" : ""}`}>
                    <td className="px-3 py-2 text-xs font-medium">{r.karigar || "-"}</td>
                    <td className="px-3 py-2 text-xs font-mono">{r.issue_slip_no}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {r.issue_date ? new Date(r.issue_date).toLocaleDateString("en-GB") : "-"}
                    </td>
                    <td className="px-3 py-2 text-xs">
                      <span className="font-medium">{r.item}</span>
                      {r.item_name && <span className="text-muted-foreground ml-1">{r.item_name}</span>}
                    </td>
                    <td className="px-3 py-2 text-xs">{r.purity || "-"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{r.pcs}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{r.approx_wt ? fmtWt(r.approx_wt) : "-"}</td>
                    <td className="px-3 py-2 text-xs">{r.design_code || "-"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                        r.days_pending > 30 ? "bg-red-100 text-red-700" :
                        r.days_pending > 14 ? "bg-amber-100 text-amber-700" :
                        "bg-green-100 text-green-700"
                      }`}>
                        {r.days_pending}d
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pending Barcode Table */}
      {!loading && tab === "pending" && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-violet-50 text-xs uppercase tracking-wider text-primary">
                  <th className="px-3 py-2.5 text-left font-semibold">Item</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Purity</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Pcs</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Gw (g)</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Nw (g)</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Design</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Created</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Source</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Voucher</th>
                </tr>
              </thead>
              <tbody>
                {pendingData.length === 0 && (
                  <tr><td colSpan={9} className="text-center py-8 text-sm text-muted-foreground">No items pending barcode creation.</td></tr>
                )}
                {pendingData.map((r, i) => (
                  <tr key={r.id} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/20" : ""}`}>
                    <td className="px-3 py-2 text-xs">
                      <span className="font-medium">{r.item}</span>
                      {r.item_name && <span className="text-muted-foreground ml-1">{r.item_name}</span>}
                    </td>
                    <td className="px-3 py-2 text-xs">{r.purity || "-"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{r.pcs || 0}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs font-medium">{fmtWt(r.gw)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{fmtWt(r.nw)}</td>
                    <td className="px-3 py-2 text-xs">{r.design_code || "-"}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {r.created_date ? new Date(r.created_date).toLocaleDateString("en-GB") : "-"}
                    </td>
                    <td className="px-3 py-2 text-xs">{r.created_from || "-"}</td>
                    <td className="px-3 py-2 text-xs font-mono">{r.voucher_no || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
