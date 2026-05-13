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
import { SquarePen, Plus, Trash2, X, Zap } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  fetchSalesOffers,
  createSalesOffer,
  updateSalesOffer,
  deleteSalesOffer,
  fetchPurity,
} from "@/services/apiService";

const emptyForm = {
  name: "",
  start_date: "",
  end_date: "",
  diamond_discount_pct: "",
  is_active: false,
  rules: [],
};

const MAKING_TYPES = [
  { value: "flat",     label: "Flat ₹/g" },
  { value: "discount", label: "% Discount on Making" },
];

export default function SalesOfferPage() {
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
    const [offRes, purityRes] = await Promise.all([
      fetchSalesOffers(),
      fetchPurity(),
    ]);
    if (offRes.success)     setRows(Array.isArray(offRes.data) ? offRes.data : offRes.data?.results ?? []);
    if (purityRes.success)  setPurities(Array.isArray(purityRes.data) ? purityRes.data : purityRes.data?.results ?? []);
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
      start_date: row.start_date || "",
      end_date: row.end_date || "",
      diamond_discount_pct: row.diamond_discount_pct ?? "",
      is_active: row.is_active,
      rules: row.rules?.map(r => ({ ...r })) || [],
    });
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this offer?")) return;
    const res = await deleteSalesOffer(id);
    if (res.success) {
      toast({ title: "Offer deleted" });
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
    const payload = {
      ...form,
      start_date:           form.start_date || null,
      end_date:             form.end_date   || null,
      diamond_discount_pct: form.diamond_discount_pct || 0,
    };
    const res = editingId
      ? await updateSalesOffer(editingId, payload)
      : await createSalesOffer(payload);
    setSubmitting(false);
    if (res.success) {
      toast({ title: `Offer ${editingId ? "updated" : "created"}` });
      setShowForm(false);
      load();
    } else {
      toast({ title: "Save failed", description: JSON.stringify(res.error), variant: "destructive" });
    }
  };

  // ── Rule helpers ──────────────────────────────────────────────────────────

  const addRule = () => setForm(f => ({
    ...f, rules: [...f.rules, { purity: "", making_type: "flat", making_value: "" }],
  }));
  const removeRule = (i) => setForm(f => ({
    ...f, rules: f.rules.filter((_, idx) => idx !== i),
  }));
  const updateRule = (i, field, val) => setForm(f => ({
    ...f, rules: f.rules.map((r, idx) => idx === i ? { ...r, [field]: val } : r),
  }));

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
    { header: "Offer Name", accessorKey: "name" },
    { header: "Start Date", accessorKey: "start_date", cell: ({ row }) => row.original.start_date || "—" },
    { header: "End Date",   accessorKey: "end_date",   cell: ({ row }) => row.original.end_date   || "—" },
    {
      header: "Diamond Disc %",
      accessorKey: "diamond_discount_pct",
      cell: ({ row }) => `${row.original.diamond_discount_pct ?? 0}%`,
    },
    {
      header: "Purity Rules",
      accessorKey: "rules",
      cell: ({ row }) => row.original.rules?.length || 0,
    },
    {
      header: "Active",
      accessorKey: "is_active",
      cell: ({ row }) => row.original.is_active
        ? <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-orange-100 text-orange-700">Active</span>
        : <span className="text-xs text-muted-foreground">Inactive</span>,
    },
  ];

  // ── Render ────────────────────────────────────────────────────────────────

  if (showForm) {
    return (
      <div className="flex flex-col gap-6 max-w-3xl">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">{editingId ? "Edit" : "New"} Sales Offer</h2>
          <Button variant="ghost" size="icon" onClick={() => setShowForm(false)}><X className="size-4" /></Button>
        </div>

        {/* Basic info */}
        <div className="grid grid-cols-2 gap-4">
          <div className="col-span-2">
            <Label>Offer Name *</Label>
            <Input value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} placeholder='e.g. "Dhanteras Offer 2025"' />
          </div>
          <div>
            <Label>Start Date</Label>
            <Input type="date" value={form.start_date} onChange={e => setForm(f => ({ ...f, start_date: e.target.value }))} />
          </div>
          <div>
            <Label>End Date</Label>
            <Input type="date" value={form.end_date} onChange={e => setForm(f => ({ ...f, end_date: e.target.value }))} />
          </div>
          <div>
            <Label>Diamond / Stone Discount %</Label>
            <div className="flex items-center gap-1">
              <Input
                type="number" step="0.01" min="0" max="100"
                value={form.diamond_discount_pct}
                onChange={e => setForm(f => ({ ...f, diamond_discount_pct: e.target.value }))}
                placeholder="0"
              />
              <span className="text-xs text-muted-foreground">%</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">Applied on all diamond/stone items across purities.</p>
          </div>
          <div className="flex items-end gap-2">
            <Checkbox checked={form.is_active} onCheckedChange={v => setForm(f => ({ ...f, is_active: v }))} id="is_active" />
            <Label htmlFor="is_active">Set as Active Offer</Label>
          </div>
        </div>

        {/* ── Making Charge Rules ── */}
        <fieldset className="border rounded-lg p-4">
          <legend className="text-sm font-semibold px-2">Making Charge Rules (per purity)</legend>
          <p className="text-xs text-muted-foreground mb-3">
            <strong>Flat ₹/g</strong>: use a fixed making rate per gram net weight.<br />
            <strong>% Discount on Making</strong>: reduce the standard making charge by a percentage.
          </p>

          {form.rules.length > 0 && (
            <div className="grid grid-cols-[140px_180px_1fr_32px] gap-x-3 gap-y-1 mb-2 items-center">
              <span className="text-xs font-medium text-muted-foreground">Purity</span>
              <span className="text-xs font-medium text-muted-foreground">Making Type</span>
              <span className="text-xs font-medium text-muted-foreground">Value</span>
              <span />
            </div>
          )}

          {form.rules.map((r, i) => (
            <div key={i} className="grid grid-cols-[140px_180px_1fr_32px] gap-x-3 gap-y-2 mb-2 items-center">
              <Select value={r.purity} onValueChange={v => updateRule(i, 'purity', v)}>
                <SelectTrigger><SelectValue placeholder="Purity" /></SelectTrigger>
                <SelectContent>
                  {purities
                    .filter(p => !usedPurities.has(p.purity) || p.purity === r.purity)
                    .map(p => <SelectItem key={p.purity} value={p.purity}>{p.purity}</SelectItem>)
                  }
                </SelectContent>
              </Select>
              <Select value={r.making_type} onValueChange={v => updateRule(i, 'making_type', v)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {MAKING_TYPES.map(t => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
              <div className="flex items-center gap-1">
                <Input
                  type="number" step="0.01" min="0"
                  value={r.making_value}
                  onChange={e => updateRule(i, 'making_value', e.target.value)}
                  placeholder={r.making_type === 'flat' ? "₹/g" : "%"}
                />
                <span className="text-xs text-muted-foreground">{r.making_type === 'flat' ? '₹/g' : '%'}</span>
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
            <Plus className="w-3.5 h-3.5" /> Add Purity Rule
          </Button>
        </fieldset>

        <div className="flex gap-3">
          <Button onClick={handleSave} disabled={submitting}>
            {submitting ? "Saving..." : editingId ? "Update Offer" : "Create Offer"}
          </Button>
          <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Sales Offers</h2>
          <p className="text-xs text-muted-foreground">
            Company-wide promotional offers. Only one offer can be active at a time.
            Offers apply to retail customers only — B2B customers use their own pricelist.
          </p>
        </div>
        <Button size="sm" className="gap-1.5" onClick={openAdd}>
          <Plus className="size-4" /> New Offer
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
