import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DataTable } from "@/table";
import { Edit, Plus, X, Check, Hammer, Trash2, Info } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchKarigarMaking,
  createKarigarMaking,
  updateKarigarMaking,
  deleteKarigarMaking,
  getLedgers,
  fetchMainItem,
  fetchPurity,
} from "@/services/apiService";

// ── Empty form ────────────────────────────────────────────────────────────────
const emptyForm = {
  karigar: "",
  kr_code: "",
  item: "",
  purity: "",
  making_per_gm: "",
  making_per_pc: "",
  loss_rate: "",
};

// ── Helper ────────────────────────────────────────────────────────────────────
function fmt(v) {
  if (v === null || v === undefined || v === "") return "—";
  return Number(v).toLocaleString("en-IN");
}

export default function KarigarMakingPage() {
  const { toast } = useToast();

  // ── Data ──────────────────────────────────────────────────────────────────
  const [rows, setRows]         = useState([]);
  const [karigars, setKarigars] = useState([]);
  const [items, setItems]       = useState([]);
  const [purities, setPurities] = useState([]);
  const [loading, setLoading]   = useState(true);

  // ── Form state ────────────────────────────────────────────────────────────
  const [showForm, setShowForm]     = useState(false);
  const [editingId, setEditingId]   = useState(null);
  const [form, setForm]             = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  // ── Load master data ──────────────────────────────────────────────────────
  const load = async () => {
    setLoading(true);
    const [makingRes, karigarRes, itemRes, purityRes] = await Promise.all([
      fetchKarigarMaking(),
      getLedgers({ type: "KR", page: 1 }),   // karigar ledgers
      fetchMainItem(),
      fetchPurity(),
    ]);
    if (makingRes.success)  setRows(Array.isArray(makingRes.data) ? makingRes.data : makingRes.data?.results ?? []);
    if (karigarRes.success) setKarigars(karigarRes.data?.results ?? karigarRes.data ?? []);
    if (itemRes.success)    setItems(Array.isArray(itemRes.data) ? itemRes.data : itemRes.data?.results ?? []);
    if (purityRes.success)  setPurities(Array.isArray(purityRes.data) ? purityRes.data : purityRes.data?.results ?? []);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  // ── Form handlers ─────────────────────────────────────────────────────────
  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: value }));
  };

  const handleSelect = (name, value) =>
    setForm(f => ({ ...f, [name]: value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.karigar || !form.item || !form.purity) return;
    setSubmitting(true);

    const payload = {
      karigar: parseInt(form.karigar),
      kr_code: form.kr_code || "",
      item: parseInt(form.item),
      purity: parseInt(form.purity),
      making_per_gm: parseFloat(form.making_per_gm) || 0,
      making_per_pc: parseFloat(form.making_per_pc) || 0,
      loss_rate: parseFloat(form.loss_rate) || 0,
    };

    const res = editingId
      ? await updateKarigarMaking(editingId, payload)
      : await createKarigarMaking(payload);

    if (res.success) {
      toast({ title: editingId ? "Rate updated" : "Rate added" });
      reset();
      load();
    } else {
      const msg =
        typeof res.error === "object"
          ? Object.entries(res.error)
              .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
              .join(" | ")
          : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setSubmitting(false);
  };

  useF4Submit(handleSubmit);

  const handleEdit = (row) => {
    setForm({
      karigar:       row.karigar   ? String(row.karigar)  : "",
      kr_code:       row.kr_code   ?? "",
      item:          row.item      ? String(row.item)     : "",
      purity:        row.purity    ? String(row.purity)   : "",
      making_per_gm: row.making_per_gm ?? "",
      making_per_pc: row.making_per_pc ?? "",
      loss_rate:     row.loss_rate ?? "",
    });
    setEditingId(row.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete rate for ${row.karigar_name} / ${row.item_name} / ${row.purity_name}?`)) return;
    const res = await deleteKarigarMaking(row.id);
    if (res.success) {
      toast({ title: "Rate deleted" });
      load();
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
  };

  const reset = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
  };

  // ── Columns ───────────────────────────────────────────────────────────────
  const columns = [
    {
      header: "Actions",
      size: 80,
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleEdit(row.original)}
            className="text-primary hover:text-primary"
            title="Edit"
          >
            <Edit className="size-4" />
          </button>
          <button
            onClick={() => handleDelete(row.original)}
            className="text-rose-400 hover:text-rose-600"
            title="Delete"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", size: 40, cell: ({ row }) => row.index + 1 },
    {
      header: "Karigar",
      cell: ({ row }) => (
        <div className="flex flex-col gap-0.5">
          <span className="font-medium text-sm">{row.original.karigar_name}</span>
          {row.original.kr_code && (
            <span className="text-[10px] text-muted-foreground font-mono">{row.original.kr_code}</span>
          )}
        </div>
      ),
    },
    {
      header: "Item",
      cell: ({ row }) => (
        <div className="flex flex-col gap-0.5">
          <span className="text-sm">{row.original.item_name}</span>
          <span className="text-[10px] text-muted-foreground">{row.original.item_code}</span>
        </div>
      ),
    },
    {
      header: "Purity",
      accessorKey: "purity_name",
      cell: ({ getValue }) => (
        <span className="inline-flex px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
          {getValue()}
        </span>
      ),
    },
    {
      header: "Making / Gm (₹)",
      accessorKey: "making_per_gm",
      cell: ({ getValue }) => (
        <span className="font-mono text-sm font-semibold text-primary">
          ₹{fmt(getValue())}
        </span>
      ),
    },
    {
      header: "Making / Pc (₹)",
      accessorKey: "making_per_pc",
      cell: ({ getValue }) => (
        <span className="font-mono text-sm">₹{fmt(getValue())}</span>
      ),
    },
    {
      header: "Loss Rate (%)",
      accessorKey: "loss_rate",
      cell: ({ getValue }) => (
        <span className="font-mono text-sm">{getValue() ?? "—"}</span>
      ),
    },
  ];

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="p-4 flex flex-col gap-5">

      {/* ── Form card ─────────────────────────────────────────────────────── */}
      {showForm && (
        <div className="rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/40">
            <div className="flex items-center gap-2">
              <Hammer className="size-4 text-muted-foreground" />
              <span className="text-sm font-semibold">
                {editingId ? "Edit Making Rate" : "Add Making Rate"}
              </span>
            </div>
            <button onClick={reset} className="text-muted-foreground hover:text-foreground">
              <X className="size-4" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-5">

            {/* Section: Karigar & Item */}
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Karigar &amp; Item
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">

              {/* Karigar */}
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Karigar *</Label>
                <Select
                  value={form.karigar ? String(form.karigar) : ""}
                  onValueChange={v => handleSelect("karigar", v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="Select karigar" />
                  </SelectTrigger>
                  <SelectContent>
                    {karigars.map(k => (
                      <SelectItem key={k.id} value={String(k.id)}>
                        {k.ac_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Karigar Code */}
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Karigar Code</Label>
                <Input
                  name="kr_code"
                  value={form.kr_code}
                  onChange={handleChange}
                  placeholder="e.g. KR01"
                  className="h-9 text-sm font-mono"
                  maxLength={10}
                />
              </div>

              {/* Item */}
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Item *</Label>
                <Select
                  value={form.item ? String(form.item) : ""}
                  onValueChange={v => handleSelect("item", v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="Select item" />
                  </SelectTrigger>
                  <SelectContent>
                    {items.map(it => (
                      <SelectItem key={it.id} value={String(it.id)}>
                        {it.item_name} ({it.short_code})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Purity */}
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Purity *</Label>
                <Select
                  value={form.purity ? String(form.purity) : ""}
                  onValueChange={v => handleSelect("purity", v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="Select purity" />
                  </SelectTrigger>
                  <SelectContent>
                    {purities.map(p => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.purity}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Section: Rate Details */}
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Making Rates &amp; Loss
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">

              <div className="flex flex-col gap-1">
                <Label className="text-xs">
                  Making per Gram (₹)
                </Label>
                <Input
                  type="number"
                  name="making_per_gm"
                  value={form.making_per_gm}
                  onChange={handleChange}
                  placeholder="0"
                  className="h-9 text-sm"
                  min="0"
                  step="1"
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">Making per Piece (₹)</Label>
                <Input
                  type="number"
                  name="making_per_pc"
                  value={form.making_per_pc}
                  onChange={handleChange}
                  placeholder="0"
                  className="h-9 text-sm"
                  min="0"
                  step="1"
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">
                  Loss Rate (%)
                  <span className="ml-1 font-normal text-muted-foreground">melting / wastage</span>
                </Label>
                <Input
                  type="number"
                  name="loss_rate"
                  value={form.loss_rate}
                  onChange={handleChange}
                  placeholder="0.000"
                  className="h-9 text-sm"
                  min="0"
                  step="0.001"
                />
              </div>
            </div>

            {/* Info note */}
            <div className="flex items-start gap-2 rounded-md bg-sky-50 border border-sky-200 px-3 py-2 mb-5">
              <Info className="size-3.5 text-sky-600 shrink-0 mt-0.5" />
              <p className="text-xs text-sky-700">
                Making rates are used as <strong>defaults</strong> when issuing work to this karigar for the selected item and purity.
                You can override them on individual job work slips.
              </p>
            </div>

            <div className="flex gap-3">
              <Button
                type="submit"
                size="sm"
                disabled={submitting || !form.karigar || !form.item || !form.purity}
                className="bg-primary hover:bg-primary text-white"
              >
                <Check className="size-4 mr-1" />
                {editingId ? "Update" : "Save"}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={reset}>
                <X className="size-4 mr-1" />
                Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* ── Header row ────────────────────────────────────────────────────── */}
      {!showForm && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Define default making rates and loss percentages per karigar, item, and purity combination.
          </p>
          <Button
            size="sm"
            className="bg-primary hover:bg-primary text-white"
            onClick={() => setShowForm(true)}
          >
            <Plus className="size-4 mr-1" />
            Add Rate
          </Button>
        </div>
      )}

      {/* ── Table ─────────────────────────────────────────────────────────── */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border py-14 flex flex-col items-center gap-3 text-center">
          <Hammer className="size-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No making rates defined yet.</p>
          <p className="text-xs text-muted-foreground">
            Add a rate for each karigar–item–purity combination to set their default making charges.
          </p>
          <Button
            size="sm"
            className="bg-primary hover:bg-primary text-white mt-2"
            onClick={() => setShowForm(true)}
          >
            <Plus className="size-4 mr-1" />
            Add First Rate
          </Button>
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}
