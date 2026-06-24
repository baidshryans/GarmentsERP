import { useEffect, useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Pencil, Trash2, Plus, Store, Hammer, Users, PackageOpen, Loader2 } from "lucide-react";
import { getOpeningInventory, deleteOpeningInventory } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const TABS = [
  { key: "SH", label: "Showroom", icon: Store  },
  { key: "KR", label: "Karigar",  icon: Hammer },
  { key: "CO", label: "Customer", icon: Users  },
];

const inr = (v) => {
  const n = parseFloat(v);
  if (!isFinite(n)) return "—";
  return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

// Primary qty for valuation: ct for Stone (S) items, gw for everything else.
const primaryQty = (row) => {
  const isStone = (row.item_type || "").toUpperCase() === "S";
  return parseFloat((isStone ? row.ct : row.gw) || 0);
};

export default function OpeningStockList() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("SH");
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setEntries([]);
    getOpeningInventory(activeTab).then((res) => {
      if (cancelled) return;
      setLoading(false);
      if (res.success) {
        const data = res.data;
        setEntries(Array.isArray(data) ? data : data.results ?? []);
      } else {
        toast({ title: "Error loading entries", variant: "destructive" });
      }
    });
    return () => { cancelled = true; };
  }, [activeTab, toast]);

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this opening stock entry?")) return;
    setDeleting(id);
    const res = await deleteOpeningInventory(id);
    setDeleting(null);
    if (res.success) {
      toast({ title: "Entry deleted" });
      setEntries((prev) => prev.filter((e) => e.id !== id));
    } else {
      toast({ title: "Delete failed", variant: "destructive" });
    }
  };

  const handleAdd = () => navigate(`/inventory/opening-stock/add?type=${activeTab}`);
  const handleEdit = (id) => navigate(`/inventory/opening-stock/${id}/edit`);

  // Aggregate summary metrics
  const summary = useMemo(() => {
    const totals = entries.reduce(
      (acc, r) => ({
        pcs: acc.pcs + (parseInt(r.pcs) || 0),
        gw: acc.gw + (parseFloat(r.gw) || 0),
        ct: acc.ct + (parseFloat(r.ct) || 0),
        amt: acc.amt + primaryQty(r) * (parseFloat(r.wtd_avg_rate) || 0),
      }),
      { pcs: 0, gw: 0, ct: 0, amt: 0 },
    );
    return { ...totals, count: entries.length };
  }, [entries]);

  const showLedger = activeTab === "KR" || activeTab === "CO";
  const ledgerHeader = activeTab === "KR" ? "Karigar" : "Customer";
  const totalColSpan = showLedger ? 9 : 8;

  return (
    <div className="px-6 py-4 w-full">
      {/* Header */}
      <div className="flex items-start justify-between mb-5 gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-gray-800">Opening Stock</h1>
          <p className="text-xs text-gray-500 mt-0.5">
            Seed inventory carried over from the previous period. Feeds the Closing Stock valuation.
          </p>
        </div>
        <Button size="sm" onClick={handleAdd} className="gap-1.5">
          <Plus size={14} /> Add Entry
        </Button>
      </div>

      {/* Tabs — segmented control */}
      <div className="inline-flex gap-1 bg-gray-100 rounded-lg p-1 mb-5">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`inline-flex items-center gap-1.5 px-4 py-1.5 text-sm rounded-md font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
              activeTab === key
                ? "bg-white text-primary shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Summary metrics */}
      {!loading && entries.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          {[
            { label: "Entries", value: summary.count, format: (v) => v.toLocaleString("en-IN") },
            { label: "Total Pcs", value: summary.pcs, format: (v) => v.toLocaleString("en-IN") },
            { label: activeTab === "KR" ? "Total GW (g)" : "Total Weight", value: summary.gw, format: (v) => v.toFixed(3) },
            { label: "Total Amount", value: summary.amt, format: inr, emphasis: true },
          ].map((m) => (
            <div key={m.label} className="rounded-lg border border-gray-100 bg-white px-4 py-3 shadow-sm">
              <p className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">{m.label}</p>
              <p className={`mt-1 text-lg tabular-nums ${m.emphasis ? "font-bold text-primary" : "font-semibold text-gray-800"}`}>
                {m.emphasis && "₹ "}{m.format(m.value)}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Table card */}
      <div className="rounded-xl border border-gray-100 bg-white shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 text-gray-400 text-sm">
            <Loader2 size={16} className="animate-spin mr-2" /> Loading entries…
          </div>
        ) : entries.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
            <div className="size-12 rounded-full bg-accent-50 flex items-center justify-center mb-3">
              <PackageOpen size={22} className="text-primary" />
            </div>
            <p className="text-sm font-semibold text-gray-700">No opening stock entries</p>
            <p className="text-xs text-gray-500 mt-1 max-w-sm">
              {`No ${activeTab === "SH" ? "Showroom" : activeTab === "KR" ? "Karigar" : "Customer"} entries yet. Add one or bulk-upload via Import Master Data.`}
            </p>
            <Button size="sm" onClick={handleAdd} className="mt-4 gap-1.5">
              <Plus size={14} /> Add Entry
            </Button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50/60">
                  <th className="px-3 py-2.5 text-center text-[10px] font-semibold text-gray-500 uppercase tracking-wider w-20">Actions</th>
                  <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Item</th>
                  <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Packet</th>
                  {showLedger && (
                    <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-gray-500 uppercase tracking-wider">{ledgerHeader}</th>
                  )}
                  <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Purity</th>
                  <th className="px-3 py-2.5 text-right text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Pcs</th>
                  <th className="px-3 py-2.5 text-right text-[10px] font-semibold text-gray-500 uppercase tracking-wider">GW</th>
                  <th className="px-3 py-2.5 text-right text-[10px] font-semibold text-gray-500 uppercase tracking-wider">CT</th>
                  <th className="px-3 py-2.5 text-right text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Wtd Avg Rate</th>
                  <th className="px-3 py-2.5 text-right text-[10px] font-semibold text-gray-500 uppercase tracking-wider">Amount</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((row) => {
                  const amount = primaryQty(row) * parseFloat(row.wtd_avg_rate || 0);
                  const hasPcs = parseInt(row.pcs) > 0;
                  const hasGw  = parseFloat(row.gw) > 0;
                  const hasCt  = parseFloat(row.ct) > 0;
                  const hasRate = parseFloat(row.wtd_avg_rate) > 0;
                  const rateUnit = (row.item_type || "").toUpperCase() === "S" ? "ct" : "g";
                  return (
                    <tr
                      key={row.id}
                      className="border-t border-gray-100 hover:bg-accent-50/30 transition-colors"
                    >
                      <td className="px-3 py-2 text-center whitespace-nowrap">
                        <div className="inline-flex items-center gap-1">
                          <button
                            type="button"
                            onClick={() => handleEdit(row.id)}
                            aria-label={`Edit ${row.item_name}`}
                            title="Edit"
                            className="inline-flex items-center justify-center size-7 rounded-md text-primary hover:bg-accent-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-1 transition-colors"
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(row.id)}
                            disabled={deleting === row.id}
                            aria-label={`Delete ${row.item_name}`}
                            title="Delete"
                            className="inline-flex items-center justify-center size-7 rounded-md text-red-500 hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 focus-visible:ring-offset-1 disabled:opacity-40 transition-colors"
                          >
                            {deleting === row.id ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                          </button>
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex flex-col">
                          <span className="text-gray-800 font-medium">{row.item_name}</span>
                          {row.item_short_code && (
                            <span className="text-[10px] font-mono text-gray-400">{row.item_short_code}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-gray-500">{row.packet_label || "—"}</td>
                      {showLedger && (
                        <td className="px-3 py-2 text-gray-700">{row.ldgr_name || "—"}</td>
                      )}
                      <td className="px-3 py-2 text-gray-600">{row.purity_label || "—"}</td>
                      <td className={`px-3 py-2 text-right tabular-nums ${hasPcs ? "text-gray-700" : "text-gray-300"}`}>
                        {hasPcs ? row.pcs : "—"}
                      </td>
                      <td className={`px-3 py-2 text-right tabular-nums ${hasGw ? "text-gray-700" : "text-gray-300"}`}>
                        {hasGw ? Number(row.gw).toFixed(3) : "—"}
                      </td>
                      <td className={`px-3 py-2 text-right tabular-nums ${hasCt ? "text-gray-700" : "text-gray-300"}`}>
                        {hasCt ? Number(row.ct).toFixed(3) : "—"}
                      </td>
                      <td className={`px-3 py-2 text-right tabular-nums ${hasRate ? "text-gray-700" : "text-gray-300"}`}>
                        {hasRate ? (
                          <>
                            {inr(row.wtd_avg_rate)}
                            <span className="ml-1 text-[10px] text-gray-400">/{rateUnit}</span>
                          </>
                        ) : "—"}
                      </td>
                      <td className={`px-3 py-2 text-right tabular-nums font-semibold ${amount > 0 ? "text-primary" : "text-gray-300"}`}>
                        {amount > 0 ? inr(amount) : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-accent-200 bg-accent-50/60">
                  <td
                    colSpan={totalColSpan}
                    className="px-3 py-2.5 text-right text-[11px] uppercase tracking-wider text-gray-600 font-semibold"
                  >
                    Total
                  </td>
                  <td className="px-3 py-2.5 text-right tabular-nums font-bold text-primary">
                    ₹ {inr(summary.amt)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
