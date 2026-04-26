import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  fetchItems,
  fetchPurity,
  fetchPackets,
  getLedgers,
  getOpeningInventoryById,
  createOpeningInventory,
  updateOpeningInventory,
} from "@/services/apiService";

const TYPE_OPTIONS = [
  { key: "SH", label: "Showroom" },
  { key: "KR", label: "Karigar" },
  { key: "CO", label: "Customer" },
];

const empty = {
  type: "SH",
  item: "",
  item_name: "",
  ldgr: "",
  ldgr_name: "",
  purity: "",
  purity_label: "",
  packet: "",
  packet_label: "",
  pcs: "",
  gw: "",
  ct: "",
};

export default function OpeningStockForm() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { toast } = useToast();
  const isEdit = Boolean(id);

  const [form, setForm] = useState({ ...empty, type: searchParams.get("type") || "SH" });
  const [items, setItems] = useState([]);
  const [purities, setPurities] = useState([]);
  const [packets, setPackets] = useState([]);
  const [ledgers, setLedgers] = useState([]);
  const [ledgerSearch, setLedgerSearch] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  // Load reference data
  useEffect(() => {
    fetchItems().then((r) => r.success && setItems(r.data || []));
    fetchPurity().then((r) => r.success && setPurities(
      Array.isArray(r.data) ? r.data : r.data?.results ?? []
    ));
    fetchPackets().then((r) => r.success && setPackets(
      Array.isArray(r.data) ? r.data : r.data?.results ?? []
    ));
  }, []);

  // Load ledgers when type changes or user types in ledger search
  useEffect(() => {
    if (form.type === "SH") return;
    getLedgers({ search: ledgerSearch, type: form.type, page_size: 50 }).then((r) => {
      if (r.success) {
        const data = r.data;
        setLedgers(Array.isArray(data) ? data : data.results ?? []);
      }
    });
  }, [form.type, ledgerSearch]);

  // Load existing entry in edit mode
  useEffect(() => {
    if (!isEdit) return;
    getOpeningInventoryById(id).then((r) => {
      if (!r.success) {
        setError("Failed to load entry. Please refresh and try again.");
        return;
      }
      const entry = r.data;
      setForm({
        type: entry.type,
        item: String(entry.item),
        item_name: entry.item_name,
        ldgr: entry.ldgr ? String(entry.ldgr) : "",
        ldgr_name: entry.ldgr_name || "",
        purity: entry.purity ? String(entry.purity) : "",
        purity_label: entry.purity_label || "",
        packet: entry.packet ? String(entry.packet) : "",
        packet_label: entry.packet_label || "",
        pcs: String(entry.pcs),
        gw: String(entry.gw),
        ct: String(entry.ct),
      });
    });
  }, [id, isEdit]);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const handleTypeChange = (newType) => {
    set({ type: newType, ldgr: "", ldgr_name: "" });
  };

  const validate = () => {
    if (!form.item) return "Item is required.";
    if ((form.type === "KR" || form.type === "CO") && !form.ldgr)
      return `${form.type === "KR" ? "Karigar" : "Customer"} is required for this type.`;
    return null;
  };

  const handleSave = async () => {
    const err = validate();
    if (err) { setError(err); return; }
    setError("");
    setSaving(true);

    const payload = {
      item: parseInt(form.item),
      ldgr: form.ldgr ? parseInt(form.ldgr) : null,
      purity: form.purity ? parseInt(form.purity) : null,
      packet: form.packet ? parseInt(form.packet) : null,
      type: form.type,
      pcs: parseInt(form.pcs) || 0,
      gw: parseFloat(form.gw) || 0,
      ct: parseFloat(form.ct) || 0,
    };

    try {
      const res = isEdit
        ? await updateOpeningInventory(id, payload)
        : await createOpeningInventory(payload);
      if (res.success) {
        toast({ title: isEdit ? "Entry updated" : "Entry created" });
        navigate("/inventory/opening-stock");
      } else {
        const msg = typeof res.error === "object"
          ? Object.values(res.error).flat().join(", ")
          : String(res.error);
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  const partyLabel = form.type === "KR" ? "Karigar" : "Customer";

  return (
    <div className="p-4 max-w-lg">
      <h1 className="text-xl font-semibold mb-6">
        {isEdit ? "Edit Opening Stock" : "Add Opening Stock"}
      </h1>

      {/* Type selector */}
      <div className="mb-5">
        <Label className="mb-2 block">Type *</Label>
        <div className="flex gap-2">
          {TYPE_OPTIONS.map((t) => (
            <button
              key={t.key}
              onClick={() => handleTypeChange(t.key)}
              className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
                form.type === t.key
                  ? "bg-blue-500 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Item */}
      <div className="mb-4">
        <Label className="mb-1 block">Item *</Label>
        <SearchableComboBox
          options={items}
          labelKey="item_name"
          searchKeys={["short_code"]}
          value={form.item_name}
          placeholder="Search item…"
          onSelect={(opt) => set({ item: String(opt.id), item_name: opt.item_name })}
        />
      </div>

      {/* Karigar / Customer — only for KR and CO */}
      {(form.type === "KR" || form.type === "CO") && (
        <div className="mb-4">
          <Label className="mb-1 block">{partyLabel} *</Label>
          <SearchableComboBox
            options={ledgers}
            labelKey="ac_name"
            value={form.ldgr_name}
            placeholder={`Search ${partyLabel.toLowerCase()}…`}
            onInputChange={setLedgerSearch}
            onSelect={(opt) => set({ ldgr: String(opt.id), ldgr_name: opt.ac_name })}
          />
        </div>
      )}

      {/* Purity */}
      <div className="mb-4">
        <Label className="mb-1 block">Purity</Label>
        <SearchableComboBox
          options={purities}
          labelKey="purity"
          value={form.purity_label}
          placeholder="Select purity…"
          onSelect={(opt) => set({ purity: String(opt.id), purity_label: opt.purity })}
        />
      </div>

      {/* Pcs / GW / CT */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div>
          <Label className="mb-1 block">Pcs</Label>
          <Input
            type="number"
            min="0"
            value={form.pcs}
            onChange={(e) => set({ pcs: e.target.value })}
            placeholder="0"
          />
        </div>
        <div>
          <Label className="mb-1 block">GW (g)</Label>
          <Input
            type="number"
            min="0"
            step="0.001"
            value={form.gw}
            onChange={(e) => set({ gw: e.target.value })}
            placeholder="0.000"
          />
        </div>
        <div>
          <Label className="mb-1 block">CT</Label>
          <Input
            type="number"
            min="0"
            step="0.001"
            value={form.ct}
            onChange={(e) => set({ ct: e.target.value })}
            placeholder="0.000"
          />
        </div>
      </div>

      {/* Packet (optional) */}
      <div className="mb-6">
        <Label className="mb-1 block">Packet (optional)</Label>
        <SearchableComboBox
          options={packets}
          labelKey="pckt_no"
          value={form.packet_label}
          placeholder="Select packet…"
          onSelect={(opt) => set({ packet: String(opt.id), packet_label: opt.pckt_no })}
        />
      </div>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      <div className="flex gap-3">
        <Button onClick={handleSave} disabled={saving}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Save
        </Button>
        <Button variant="outline" onClick={() => navigate("/inventory/opening-stock")}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
