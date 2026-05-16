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
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchRetailDiscountPricelists,
  createRetailDiscountPricelist,
  updateRetailDiscountPricelist,
  deleteRetailDiscountPricelist,
  fetchPurity,
} from "@/services/apiService";

const emptyForm = {
  name: "",
  description: "",
  is_active: true,
  rules: [],
};

export default function RetailDiscountPricelistPage() {
  const { toast } = useToast();

  const [rows, setRows]         = useState([]);
  const [purities, setPurities] = useState([]);
  const [loading, setLoading]   = useState(true);

  const [showForm, setShowForm]     = useState(false);
  const [editingId, setEditingId]   = useState(null);
  const [form, setForm]             = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const [plRes, purityRes] = await Promise.all([
      fetchRetailDiscountPricelists(),
      fetchPurity(),
    ]);
    if (plRes.success)     setRows(Array.isArray(plRes.data) ? plRes.data : plRes.data?.results ?? []);
    if (purityRes.success) setPurities(Array.isArray(purityRes.data) ? purityRes.data : purityRes.data?.results ?? []);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const openAdd = () => {
    setEditingId(null);
    setForm({ ...emptyForm, rules: [] });
    setShowForm(true);
  };

  const openEdit = (row) => {
    setEditingId(row.id);
    setForm({
      name: row.name,
      description: row.description || "",
      is_active: row.is_active,
      rules: row.rules?.map(r => ({ ...r })) || [],
    });
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this pricelist?")) return;
    const res = await deleteRetailDiscountPricelist(id);
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
    const res = editingId
      ? await updateRetailDiscountPricelist(editingId, form)
      : await createRetailDiscountPricelist(form);
    setSubmitting(false);
    if (res.success) {
      toast({ title: `Pricelist ${editingId ? "updated" : "created"}` });
      setShowForm(false);
      load();
    } else {
      toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  // F4 saves/updates the pricelist when the form is open
  useF4Submit(showForm ? handleSave : undefined);

  // ── Rule helpers ──────────────────────────────────────────────────────────

  const addRule = () => setForm(f => ({
    ...f, rules: [...f.rules, { purity: "", making_discount_pct: "", diamond_discount_pct: "" }],
  }));
  const removeRule = (i) => setForm(f => ({
    ...f, rules: f.rules.filter((_, idx) => idx !== i),
  }));
  const updateRule = (i, field, val) => setForm(f => ({
    ...f, rules: f.rules.map((r, idx) => idx === i ? { ...r, [field]: val } : r),
  }));

  // Already-used purities (prevent duplicates)
  const usedPurities = new Set(form.rules.map(r => r.purity).filter(Boolean));

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
      header: "Purity Rules",
      accessorKey: "rules",
      cell: ({ row }) => row.original.rules?.length || 0,
    },
  ];

  // ── Render ────────────────────────────────────────────────────────────────

  if (showForm) {
    return (
      <div className="flex flex-col gap-6 max-w-3xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{editingId ? "Edit" : "Add"} Retail Discount Pricelist</h2>
          <Button variant="ghost" size="icon" onClick={() => setShowForm(false)}><X className="size-4" /></Button>
        </div>

        {/* Basic info */}
        <div className="grid grid-cols-3 gap-4">
          <div>
            <Label>Name *</Label>
            <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder='e.g. "Gold Card Member"' />
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

        {/* ── Discount Rules ── */}
        <fieldset className="border rounded-lg p-4">
          <legend className="text-sm font-semibold px-2">Discount Rules (per purity)</legend>
          <p className="text-xs text-muted-foreground mb-3">
            Define making charge and diamond/stone discount percentages per purity. Leave a value at 0 for no discount.
          </p>

          {form.rules.length > 0 && (
            <div className="grid grid-cols-[140px_1fr_1fr_32px] gap-x-3 gap-y-1 mb-2 items-center">
              <span className="text-xs font-medium text-muted-foreground">Purity</span>
              <span className="text-xs font-medium text-muted-foreground">Making Discount %</span>
              <span className="text-xs font-medium text-muted-foreground">Diamond Discount %</span>
              <span />
            </div>
          )}

          {form.rules.map((r, i) => (
            <div key={i} className="grid grid-cols-[140px_1fr_1fr_32px] gap-x-3 gap-y-2 mb-2 items-center">
              <Select
                value={r.purity}
                onValueChange={v => updateRule(i, 'purity', v)}
              >
                <SelectTrigger><SelectValue placeholder="Purity" /></SelectTrigger>
                <SelectContent>
                  {purities
                    .filter(p => !usedPurities.has(p.purity) || p.purity === r.purity)
                    .map(p => <SelectItem key={p.purity} value={p.purity}>{p.purity}</SelectItem>)
                  }
                </SelectContent>
              </Select>
              <div className="flex items-center gap-1">
                <Input
                  type="number" step="0.01" min="0" max="100"
                  value={r.making_discount_pct}
                  onChange={e => updateRule(i, 'making_discount_pct', e.target.value)}
                  placeholder="0"
                />
                <span className="text-xs text-muted-foreground">%</span>
              </div>
              <div className="flex items-center gap-1">
                <Input
                  type="number" step="0.01" min="0" max="100"
                  value={r.diamond_discount_pct}
                  onChange={e => updateRule(i, 'diamond_discount_pct', e.target.value)}
                  placeholder="0"
                />
                <span className="text-xs text-muted-foreground">%</span>
              </div>
              <Button variant="ghost" size="icon" onClick={() => removeRule(i)}>
                <Trash2 className="w-3.5 h-3.5 text-destructive" />
              </Button>
            </div>
          ))}

          <Button
            variant="outline" size="sm" onClick={addRule} className="gap-1"
            disabled={form.rules.length >= purities.length}
          >
            <Plus className="w-3.5 h-3.5" /> Add Rule
          </Button>
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
        <h2 className="text-lg font-semibold">Retail Discount Pricelists</h2>
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
