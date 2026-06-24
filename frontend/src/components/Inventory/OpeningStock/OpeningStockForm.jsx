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
  item_type: "",
  item_uom: "",
  ldgr: "",
  ldgr_name: "",
  purity: "",
  purity_label: "",
  packet: "",
  packet_label: "",
  pcs: "",
  gw: "",
  ct: "",
  wtd_avg_rate: "",
  // S items: user can pick between pcs or the item-master UOM (typically "ct").
  // Stored only on the form, not sent to the backend.
  s_uom_choice: "",
};

// Indian-format number helpers (en-IN, lakh/crore grouping)
const inr = (v) => {
  const n = parseFloat(v);
  if (!isFinite(n)) return "0.00";
  return n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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
        item_type: "",
        item_uom: "",
        ldgr: entry.ldgr ? String(entry.ldgr) : "",
        ldgr_name: entry.ldgr_name || "",
        purity: entry.purity ? String(entry.purity) : "",
        purity_label: entry.purity_label || "",
        packet: entry.packet ? String(entry.packet) : "",
        packet_label: entry.packet_label || "",
        pcs: String(entry.pcs),
        gw: String(entry.gw),
        ct: String(entry.ct),
        wtd_avg_rate: entry.wtd_avg_rate != null ? String(entry.wtd_avg_rate) : "",
        s_uom_choice: "",
      });
    });
  }, [id, isEdit]);

  // Re-hydrate item_type / item_uom once both items and form.item are known.
  useEffect(() => {
    if (!form.item || items.length === 0) return;
    const sel = items.find((m) => String(m.id) === String(form.item));
    if (!sel) return;
    const masterUom = (sel.uom || "").toLowerCase();
    setForm((f) => ({
      ...f,
      item_type: (sel.item_type || "").toUpperCase(),
      item_uom: masterUom,
      s_uom_choice: f.s_uom_choice || masterUom || "ct",
    }));
  }, [form.item, items]);

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
      wtd_avg_rate: parseFloat(form.wtd_avg_rate) || 0,
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
                  ? "bg-primary text-primary-foreground"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Item + Packet (Packet hidden for Raw items) */}
      <div className={`grid gap-3 mb-4 ${form.item_type !== "R" ? "grid-cols-1 sm:grid-cols-2" : "grid-cols-1"}`}>
        <div>
          <Label className="mb-1 block">Item *</Label>
          <SearchableComboBox
            options={items}
            labelKey="item_name"
            searchKeys={["short_code"]}
            value={form.item_name}
            placeholder="Search item…"
            onSelect={(opt) => {
              const masterUom = (opt.uom || "").toLowerCase();
              const type = (opt.item_type || "").toUpperCase();
              set({
                item: String(opt.id),
                item_name: opt.item_name,
                item_type: type,
                item_uom: masterUom,
                s_uom_choice: type === "S" ? (masterUom || "ct") : "",
                // R items cannot have a packet
                ...(type === "R" ? { packet: "", packet_label: "" } : {}),
              });
            }}
          />
        </div>
        {form.item_type !== "R" && (
          <div>
            <Label className="mb-1 block">Packet (optional)</Label>
            <SearchableComboBox
              options={packets}
              labelKey="pckt_no"
              value={form.packet_label}
              placeholder="Select packet…"
              onSelect={(opt) => {
                const patch = { packet: String(opt.id), packet_label: opt.pckt_no };
                if (opt.stone_item_id && opt.stone_item_name) {
                  patch.item = String(opt.stone_item_id);
                  patch.item_name = opt.stone_item_name;
                }
                set(patch);
              }}
            />
          </div>
        )}
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

      {/* Quantity inputs — UOM-aware */}
      {(() => {
        const isS = form.item_type === "S";
        const isR = form.item_type === "R";
        const masterUom = form.item_uom;
        // Which qty inputs to show:
        //  - S items: Pcs + CT + GW (GW auto-derives from CT ÷ 5).
        //  - R items: Pcs + GW.
        //  - Other items: respect the master UOM ("g" → Pcs + GW,
        //                 "ct" → Pcs + CT, "pcs" → Pcs only).
        const effectiveUom = isS ? "ct" : (masterUom || "g");
        const showPcs = true;
        const showCt  = isS || effectiveUom === "ct";
        const showGw  = isS || isR || effectiveUom === "g" || effectiveUom === "gm" || effectiveUom === "gms";
        const gwReadOnly = isS;

        // CT → GW auto-derive (1 ct = 0.2 g) for S items entering by ct
        const handleCtChange = (val) => {
          const ct = parseFloat(val);
          const patch = { ct: val };
          if (isS && !Number.isNaN(ct)) {
            patch.gw = (ct / 5).toFixed(3);
          }
          set(patch);
        };

        return (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
              {showPcs && (
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
              )}
              {showCt && (
                <div>
                  <Label className="mb-1 block">CT</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.001"
                    value={form.ct}
                    onChange={(e) => handleCtChange(e.target.value)}
                    placeholder="0.000"
                  />
                </div>
              )}
              {showGw && (
                <div>
                  <Label className="mb-1 block">GW (g){gwReadOnly && <span className="text-[10px] text-gray-400 ml-1">auto = ct ÷ 5</span>}</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.001"
                    value={form.gw}
                    onChange={(e) => set({ gw: e.target.value })}
                    placeholder="0.000"
                    readOnly={gwReadOnly}
                    className={gwReadOnly ? "bg-gray-50 cursor-not-allowed" : ""}
                  />
                </div>
              )}
            </div>

            {/* Weighted-avg rate + computed total */}
            {(() => {
              const primaryQty = isS
                ? parseFloat(form.ct || 0)
                : parseFloat(form.gw || 0);
              const rate = parseFloat(form.wtd_avg_rate || 0);
              const total = primaryQty * rate;
              const qtyLabel = isS ? "ct" : "g";
              return (
                <div className="grid grid-cols-2 gap-3 mb-4 p-3 rounded-lg bg-accent-50/40 border border-accent-100">
                  <div>
                    <Label className="mb-1 block">Weighted Avg Rate (₹ / {qtyLabel})</Label>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.wtd_avg_rate}
                      onChange={(e) => set({ wtd_avg_rate: e.target.value })}
                      placeholder="0.00"
                    />
                  </div>
                  <div>
                    <Label className="mb-1 block">Total Amount</Label>
                    <div className="h-10 px-3 flex items-center rounded-md border border-gray-200 bg-white text-sm font-semibold text-primary tabular-nums">
                      ₹ {inr(total)}
                    </div>
                  </div>
                </div>
              );
            })()}
          </>
        );
      })()}


      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      <div className="flex gap-3">
        <Button onClick={handleSave} disabled={saving}>
          {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {saving ? (isEdit ? "Updating…" : "Saving…") : (isEdit ? "Update" : "Save")}
        </Button>
        <Button variant="outline" onClick={() => navigate("/inventory/opening-stock")}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
