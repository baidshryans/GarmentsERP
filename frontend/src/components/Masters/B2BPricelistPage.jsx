import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DataTable } from "@/table";
import { SquarePen, Plus, Trash2, X } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  fetchB2BPricelists,
  createB2BPricelist,
  updateB2BPricelist,
  deleteB2BPricelist,
  fetchPurity,
  fetchMainItem,
  fetchPackets,
} from "@/services/apiService";
import { MAKING_TYPES, MAKING_TYPE_LABELS, MAKING_TYPE_UNITS } from "@/lib/b2bPricing";

const emptyForm = {
  name: "",
  description: "",
  is_active: true,
  making_entries: [],
};

// Build stoneGroups from existing flat stone_overrides + loaded packets + stone items
function buildStoneGroups(stoneOverrides, allPackets, stoneItems) {
  if (!stoneOverrides?.length) return [];
  // Map packet number → packet object
  const packetMap = Object.fromEntries(allPackets.map(p => [p.pckt_no, p]));
  // Map item id → item object
  const itemMap = Object.fromEntries(stoneItems.map(it => [it.id, it]));

  // Group existing overrides by stone_item_id
  const grouped = {};
  for (const o of stoneOverrides) {
    const pkt = packetMap[o.packet];
    if (!pkt) continue;
    const itemId = pkt.stone_item_id;
    if (!grouped[itemId]) grouped[itemId] = [];
    grouped[itemId].push({ pckt_no: o.packet, rate: String(o.rate ?? "") });
  }

  return Object.entries(grouped).map(([itemId, overriddenPackets]) => {
    const item = itemMap[Number(itemId)];
    // All packets for this item
    const allItemPackets = allPackets.filter(p => p.stone_item_id === Number(itemId));
    // Merge: start with all packets, fill in rates from overrides
    const rateMap = Object.fromEntries(overriddenPackets.map(p => [p.pckt_no, p.rate]));
    const packets = allItemPackets.map(p => ({ pckt_no: p.pckt_no, rate: rateMap[p.pckt_no] ?? "" }));
    return {
      itemId: Number(itemId),
      itemCode: item?.short_code ?? String(itemId),
      itemName: item?.item_name ?? String(itemId),
      packets,
    };
  });
}

// Flatten stoneGroups → stone_overrides (only non-empty rates)
function flattenStoneGroups(stoneGroups) {
  const result = [];
  for (const grp of stoneGroups) {
    for (const p of grp.packets) {
      if (p.rate !== "" && p.rate !== null && p.rate !== undefined) {
        result.push({ packet: p.pckt_no, rate: p.rate });
      }
    }
  }
  return result;
}

export default function B2BPricelistPage() {
  const { toast } = useToast();

  const [rows, setRows]           = useState([]);
  const [purities, setPurities]   = useState([]);
  const [items, setItems]         = useState([]);   // all items (for making charges)
  const [stoneItems, setStoneItems] = useState([]); // type=S items
  const [packets, setPackets]     = useState([]);
  const [loading, setLoading]     = useState(true);

  const [showForm, setShowForm]     = useState(false);
  const [editingId, setEditingId]   = useState(null);
  const [form, setForm]             = useState(emptyForm);
  const [stoneGroups, setStoneGroups] = useState([]); // UI state for stone overrides
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const [plRes, purityRes, itemRes, stoneRes, packetRes] = await Promise.all([
      fetchB2BPricelists(),
      fetchPurity(),
      fetchMainItem(),
      fetchMainItem({ type: "S" }),
      fetchPackets(),
    ]);
    if (plRes.success)     setRows(Array.isArray(plRes.data) ? plRes.data : plRes.data?.results ?? []);
    if (purityRes.success) setPurities(Array.isArray(purityRes.data) ? purityRes.data : purityRes.data?.results ?? []);
    if (itemRes.success)   setItems(Array.isArray(itemRes.data) ? itemRes.data : itemRes.data?.results ?? []);
    if (stoneRes.success)  setStoneItems(Array.isArray(stoneRes.data) ? stoneRes.data : stoneRes.data?.results ?? []);
    if (packetRes.success) setPackets(Array.isArray(packetRes.data) ? packetRes.data : packetRes.data?.results ?? []);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const openAdd = () => {
    setEditingId(null);
    setForm({ ...emptyForm, making_entries: [] });
    setStoneGroups([]);
    setShowForm(true);
  };

  const openEdit = (row) => {
    setEditingId(row.id);
    setForm({
      name: row.name,
      description: row.description || "",
      is_active: row.is_active,
      making_entries: row.making_entries?.map(m => ({ ...m })) || [],
    });
    setStoneGroups(buildStoneGroups(row.stone_overrides || [], packets, stoneItems));
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this pricelist?")) return;
    const res = await deleteB2BPricelist(id);
    if (res.success) {
      toast({ title: "Pricelist deleted" });
      load();
    } else {
      toast({ title: "Delete failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast({ title: "Name is required", variant: "destructive" });
      return;
    }
    setSubmitting(true);
    const payload = { ...form, stone_overrides: flattenStoneGroups(stoneGroups) };
    const res = editingId
      ? await updateB2BPricelist(editingId, payload)
      : await createB2BPricelist(payload);
    setSubmitting(false);
    if (res.success) {
      toast({ title: `Pricelist ${editingId ? "updated" : "created"}` });
      setShowForm(false);
      load();
    } else {
      toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  // ── Making / Tunch rule helpers ───────────────────────────────────────────

  const addMaking = () => setForm(f => ({
    ...f,
    making_entries: [
      ...f.making_entries,
      { purity: null, item: null, making_type: "per_gram", making_value: "", min_making_grams: "" },
    ],
  }));
  const removeMaking = (i) => setForm(f => ({
    ...f, making_entries: f.making_entries.filter((_, idx) => idx !== i),
  }));
  const updateMaking = (i, field, val) => setForm(f => ({
    ...f,
    making_entries: f.making_entries.map((m, idx) => {
      if (idx !== i) return m;
      const next = { ...m, [field]: val };
      // A Flat Value rule has no minimum — clear it in the same update, or the
      // server rejects the save on a stale value left behind by the switch.
      if (field === "making_type" && val === "val") next.min_making_grams = "";
      return next;
    }),
  }));

  // ── Stone group helpers ───────────────────────────────────────────────────

  const addStoneGroup = (itemId) => {
    const item = stoneItems.find(it => it.id === Number(itemId));
    if (!item) return;
    // Don't add if already present
    if (stoneGroups.some(g => g.itemId === item.id)) {
      toast({ title: `${item.item_name} is already added`, variant: "destructive" });
      return;
    }
    const itemPackets = packets
      .filter(p => p.stone_item_id === item.id)
      .map(p => ({ pckt_no: p.pckt_no, rate: "" }));
    setStoneGroups(gs => [...gs, { itemId: item.id, itemCode: item.short_code, itemName: item.item_name, packets: itemPackets }]);
  };

  const removeStoneGroup = (gi) => setStoneGroups(gs => gs.filter((_, i) => i !== gi));

  const updateStoneRate = (gi, pi, val) => setStoneGroups(gs =>
    gs.map((g, i) => i !== gi ? g : {
      ...g,
      packets: g.packets.map((p, j) => j !== pi ? p : { ...p, rate: val }),
    })
  );

  // ── Table columns ─────────────────────────────────────────────────────────

  const columns = [
    {
      header: "Action",
      accessorKey: "id",
      cell: ({ row }) => (
        <div className="flex gap-1.5">
          <button onClick={() => openEdit(row.original)} className="p-1 rounded text-primary hover:bg-primary/10">
            <SquarePen className="size-4" />
          </button>
          <button onClick={() => handleDelete(row.original.id)} className="p-1 rounded text-destructive hover:bg-red-50">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "Name", accessorKey: "name" },
    { header: "Description", accessorKey: "description" },
    {
      header: "Active",
      accessorKey: "is_active",
      cell: ({ row }) => row.original.is_active ? "Yes" : "No",
    },
    {
      header: "Pricing Rules",
      accessorKey: "making_entries",
      cell: ({ row }) => row.original.making_entries?.length || 0,
    },
    {
      header: "Stone Overrides",
      accessorKey: "stone_overrides",
      cell: ({ row }) => row.original.stone_overrides?.length || 0,
    },
  ];

  // ── Stone item selector (stateless dropdown) ──────────────────────────────

  const addedItemIds = new Set(stoneGroups.map(g => g.itemId));
  const availableStoneItems = stoneItems.filter(it => !addedItemIds.has(it.id));

  // ── Render ────────────────────────────────────────────────────────────────

  if (showForm) {
    return (
      <div className="flex flex-col gap-6 max-w-4xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{editingId ? "Edit" : "Add"} B2B Pricelist</h2>
          <Button variant="ghost" size="icon" onClick={() => setShowForm(false)}><X className="size-4" /></Button>
        </div>

        {/* Basic info */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <Label>Name *</Label>
            <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder='e.g. "Tier A Dealers"' />
          </div>
          <div>
            <Label>Description</Label>
            <Input value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          </div>
          <div className="flex items-end gap-2">
            <Checkbox checked={form.is_active} onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))} id="is_active" />
            <Label htmlFor="is_active">Active</Label>
          </div>
        </div>

        {/* ── Making / Tunch Rules ── */}
        <fieldset className="border rounded-lg p-4">
          <legend className="text-sm font-semibold px-2">Making / Tunch Rules</legend>
          <p className="text-xs text-muted-foreground mb-3">
            Leave purity/item blank for a default rule. More specific rules (purity+item) take priority.
            <br />
            <span className="font-medium">Per Gram</span> charges the value for every gram.{" "}
            <span className="font-medium">Flat Value</span> is a fixed amount and overrides everything else.{" "}
            <span className="font-medium">Tunch % Markup</span> adds the % on top of the purity (22K + 8% = 99.6% of
            pure gold rate) and charges nothing in the making column.{" "}
            <span className="font-medium">% of Gold Value</span> charges that % of the gold amount.
            <br />
            <span className="font-medium">Min g</span> is the minimum making charge in grams — a lighter item is
            charged as if it weighed this much. It does not apply to Flat Value.
          </p>
          {form.making_entries.map((m, i) => (
            <div key={i} className="flex items-center gap-3 mb-2">
              <Select value={m.purity || "__all__"} onValueChange={v => updateMaking(i, 'purity', v === "__all__" ? null : v)}>
                <SelectTrigger className="w-32"><SelectValue placeholder="All Purities" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All Purities</SelectItem>
                  {purities.map(p => <SelectItem key={p.purity} value={p.purity}>{p.purity}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={m.item || "__all__"} onValueChange={v => updateMaking(i, 'item', v === "__all__" ? null : v)}>
                <SelectTrigger className="w-36"><SelectValue placeholder="All Items" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All Items</SelectItem>
                  {items.map(it => <SelectItem key={it.short_code} value={it.short_code}>{it.item_name || it.short_code}</SelectItem>)}
                </SelectContent>
              </Select>
              <Select value={m.making_type} onValueChange={v => updateMaking(i, 'making_type', v)}>
                <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {MAKING_TYPES.map(t => (
                    <SelectItem key={t} value={t}>{MAKING_TYPE_LABELS[t]}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input type="number" step="0.01" className="w-28" value={m.making_value} onChange={e => updateMaking(i, 'making_value', e.target.value)} placeholder="Value" />
              <span className="text-xs text-muted-foreground w-8">{MAKING_TYPE_UNITS[m.making_type] || ""}</span>
              <Input
                type="number"
                step="0.001"
                className="w-24"
                value={m.making_type === "val" ? "" : (m.min_making_grams ?? "")}
                onChange={e => updateMaking(i, 'min_making_grams', e.target.value)}
                placeholder="Min g"
                disabled={m.making_type === "val"}
                title={m.making_type === "val"
                  ? "A Flat Value rule has no minimum — it is already a fixed amount."
                  : "Minimum making charge in grams. A lighter item is charged as if it weighed this much."}
              />
              <Button variant="ghost" size="icon" onClick={() => removeMaking(i)}><Trash2 className="w-3.5 h-3.5 text-destructive" /></Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addMaking} className="gap-1">
            <Plus className="w-3.5 h-3.5" /> Add Rule
          </Button>
        </fieldset>

        {/* ── Stone Rate Overrides ── */}
        <fieldset className="border rounded-lg p-4">
          <legend className="text-sm font-semibold px-2">Stone Rate Overrides</legend>
          <p className="text-xs text-muted-foreground mb-3">
            Select a stone item to see all its packets and set custom rates. Leave a packet's rate blank to use its default wholesale rate.
          </p>

          {/* Per-item groups */}
          {stoneGroups.map((grp, gi) => (
            <div key={grp.itemId} className="mb-4 border rounded-md">
              {/* Group header */}
              <div className="flex items-center justify-between px-3 py-2 bg-muted/40 rounded-t-md">
                <span className="text-sm font-medium">{grp.itemName} <span className="text-xs text-muted-foreground">({grp.itemCode})</span></span>
                <Button variant="ghost" size="icon" onClick={() => removeStoneGroup(gi)}>
                  <X className="w-3.5 h-3.5 text-destructive" />
                </Button>
              </div>

              {/* Packets grid */}
              {grp.packets.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">No packets found for this item.</p>
              ) : (
                <div className="p-3 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-3">
                  {grp.packets.map((pkt, pi) => (
                    <div key={pkt.pckt_no} className="flex items-center gap-2">
                      <span className="text-xs w-20 shrink-0 text-muted-foreground">{pkt.pckt_no}</span>
                      <Input
                        type="number"
                        step="0.01"
                        className="h-7 text-xs"
                        value={pkt.rate}
                        onChange={e => updateStoneRate(gi, pi, e.target.value)}
                        placeholder="Rate"
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {/* Add stone item */}
          {availableStoneItems.length > 0 && (
            <div className="flex items-center gap-2 mt-1">
              <Select onValueChange={addStoneGroup}>
                <SelectTrigger className="w-52">
                  <SelectValue placeholder="Add stone item..." />
                </SelectTrigger>
                <SelectContent>
                  {availableStoneItems.map(it => (
                    <SelectItem key={it.id} value={String(it.id)}>
                      {it.item_name} ({it.short_code})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          {availableStoneItems.length === 0 && stoneItems.length > 0 && (
            <p className="text-xs text-muted-foreground mt-1">All stone items have been added.</p>
          )}
          {stoneItems.length === 0 && (
            <p className="text-xs text-muted-foreground mt-1">No stone items found in item master.</p>
          )}
        </fieldset>

        <div className="flex gap-3">
          <Button onClick={handleSave} disabled={submitting}>
            {submitting ? "Saving..." : editingId ? "Update Pricelist" : "Create Pricelist"}
          </Button>
          <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">B2B Pricelists</h2>
        <Button size="sm" className="gap-1.5" onClick={openAdd}>
          <Plus className="size-4" /> Add Pricelist
        </Button>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="w-full h-10" />)}
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}
