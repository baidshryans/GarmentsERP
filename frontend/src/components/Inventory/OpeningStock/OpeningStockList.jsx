import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Pencil, Trash2 } from "lucide-react";
import { getOpeningInventory, deleteOpeningInventory } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const TABS = [
  { key: "SH", label: "Showroom" },
  { key: "KR", label: "Karigar" },
  { key: "CO", label: "Customer" },
];

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

  const handleAdd = () => {
    navigate(`/inventory/opening-stock/add?type=${activeTab}`);
  };

  const handleEdit = (id) => {
    navigate(`/inventory/opening-stock/${id}/edit`);
  };

  return (
    <div className="p-4">
      <div className="flex justify-between items-center mb-4">
        <h1 className="text-xl font-semibold">Opening Stock</h1>
        <Button size="sm" onClick={handleAdd}>+ Add New</Button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 mb-4">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-5 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? "border-primary text-primary"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-gray-500">Loading�</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-gray-50 text-gray-600 text-left">
                <th className="px-3 py-2 border border-gray-200 text-center">Actions</th>
                <th className="px-3 py-2 border border-gray-200">Packet</th>
                {activeTab === "KR" && <th className="px-3 py-2 border border-gray-200">Karigar</th>}
                {activeTab === "CO" && <th className="px-3 py-2 border border-gray-200">Customer</th>}
                <th className="px-3 py-2 border border-gray-200">Item</th>
                <th className="px-3 py-2 border border-gray-200">Purity</th>
                <th className="px-3 py-2 border border-gray-200 text-right">Pcs</th>
                <th className="px-3 py-2 border border-gray-200 text-right">GW</th>
                <th className="px-3 py-2 border border-gray-200 text-right">CT</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 ? (
                <tr>
                  <td
                    colSpan={activeTab === "SH" ? 7 : 8}
                    className="px-3 py-6 text-center text-gray-400 border border-gray-200"
                  >
                    No entries found. Click &quot;+ Add New&quot; to create one.
                  </td>
                </tr>
              ) : (
                entries.map((row, idx) => (
                  <tr key={row.id} className={idx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                    <td className="px-3 py-2 border border-gray-200 text-center whitespace-nowrap">
                      <button
                        onClick={() => handleEdit(row.id)}
                        className="text-primary hover:opacity-70 mr-3"
                        title="Edit"
                      >
                        <Pencil size={14} />
                      </button>
                      <button
                        onClick={() => handleDelete(row.id)}
                        className="text-red-500 hover:text-red-700 disabled:opacity-40"
                        title="Delete"
                        disabled={deleting === row.id}
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                    <td className="px-3 py-2 border border-gray-200 text-gray-500">
                      {row.packet_label || "�"}
                    </td>
                    {(activeTab === "KR" || activeTab === "CO") && (
                      <td className="px-3 py-2 border border-gray-200">{row.ldgr_name || "�"}</td>
                    )}
                    <td className="px-3 py-2 border border-gray-200">{row.item_name}</td>
                    <td className="px-3 py-2 border border-gray-200">{row.purity_label || "�"}</td>
                    <td className="px-3 py-2 border border-gray-200 text-right">{row.pcs ?? "�"}</td>
                    <td className="px-3 py-2 border border-gray-200 text-right">{row.gw != null ? Number(row.gw).toFixed(3) : "�"}</td>
                    <td className="px-3 py-2 border border-gray-200 text-right">{row.ct != null ? Number(row.ct).toFixed(3) : "�"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
