import { useState, useEffect } from "react";
import { formatNumber } from "@/lib/format";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { SquarePen, Trash2, Plus, X, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { fetchSchemes, createScheme, updateScheme, deleteScheme } from "@/services/apiService";
import { fetchPurity } from "@/services/apiService";

const SCHEME_TYPES = [
  { value: "INSTALLMENT", label: "Monthly Installment" },
  { value: "ACCUMULATION", label: "Gold Accumulation" },
  { value: "LUMPSUM", label: "One-Time Lump Sum" },
];

const GOLD_PRICE_MODES = [
  { value: "CURRENT", label: "Current price at redemption" },
  { value: "ACCUMULATED", label: "Gold accumulated at each payment rate" },
  { value: "LOCKED", label: "Gold price locked at enrollment" },
];

const emptyTier = { product_type: "GOLD", min_months: "", max_months: "", lc_discount_pct: "", value_discount_pct: "0" };

const emptyForm = {
  name: "", scheme_code: "", scheme_type: "INSTALLMENT", gold_price_mode: "CURRENT",
  tenure_months: "11", min_amount: "1000", max_amount: "",
  accumulation_purity: "", has_diamond_benefit: false,
  is_active: true, description: "", terms_conditions: "",
  benefit_tiers: [],
};

export default function SchemeMasterPage() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [purities, setPurities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const [res, pRes] = await Promise.all([fetchSchemes(), fetchPurity()]);
    if (res.success) {
      const d = res.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    if (pRes.success) {
      const d = pRes.data;
      setPurities(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleChange = (e) => setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.scheme_code.trim()) return;
    setSubmitting(true);

    const payload = {
      ...form,
      tenure_months: parseInt(form.tenure_months) || 11,
      min_amount: parseFloat(form.min_amount) || 1000,
      max_amount: form.max_amount ? parseFloat(form.max_amount) : null,
      accumulation_purity: form.accumulation_purity || null,
      benefit_tiers: form.benefit_tiers.map((t) => ({
        ...t,
        min_months: parseInt(t.min_months),
        max_months: parseInt(t.max_months),
        lc_discount_pct: parseFloat(t.lc_discount_pct) || 0,
        value_discount_pct: parseFloat(t.value_discount_pct) || 0,
      })),
    };

    const res = editingId
      ? await updateScheme(editingId, payload)
      : await createScheme(payload);
    if (res.success) {
      toast({ title: editingId ? "Scheme updated" : "Scheme created" });
      reset();
      load();
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : res.error;
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setSubmitting(false);
  };

  const reset = () => { setForm(emptyForm); setEditingId(null); setShowForm(false); };

  const handleEdit = (row) => {
    setForm({
      name: row.name, scheme_code: row.scheme_code,
      scheme_type: row.scheme_type, gold_price_mode: row.gold_price_mode,
      tenure_months: String(row.tenure_months), min_amount: String(row.min_amount),
      max_amount: row.max_amount ? String(row.max_amount) : "",
      accumulation_purity: row.accumulation_purity || "",
      has_diamond_benefit: row.has_diamond_benefit,
      is_active: row.is_active, description: row.description || "",
      terms_conditions: row.terms_conditions || "",
      benefit_tiers: (row.benefit_tiers || []).map((t) => ({
        product_type: t.product_type,
        min_months: String(t.min_months), max_months: String(t.max_months),
        lc_discount_pct: String(t.lc_discount_pct), value_discount_pct: String(t.value_discount_pct),
      })),
    });
    setEditingId(row.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this scheme?")) return;
    const res = await deleteScheme(id);
    if (res.success) { toast({ title: "Scheme deleted" }); load(); }
    else toast({ title: "Error", description: String(res.error), variant: "destructive" });
  };

  const addTier = () => setForm((f) => ({ ...f, benefit_tiers: [...f.benefit_tiers, { ...emptyTier }] }));
  const removeTier = (idx) => setForm((f) => ({ ...f, benefit_tiers: f.benefit_tiers.filter((_, i) => i !== idx) }));
  const updateTier = (idx, field, value) => setForm((f) => ({
    ...f,
    benefit_tiers: f.benefit_tiers.map((t, i) => i === idx ? { ...t, [field]: value } : t),
  }));

  const columns = [
    { accessorKey: "scheme_code", header: "Code" },
    { accessorKey: "name", header: "Scheme Name" },
    { accessorKey: "scheme_type", header: "Type" },
    { accessorKey: "tenure_months", header: "Tenure (m)" },
    { accessorKey: "min_amount", header: "Min Amount", cell: ({ row }) => `₹${formatNumber(row.original.min_amount)}` },
    { accessorKey: "active_enrollments", header: "Enrollments" },
    { accessorKey: "is_active", header: "Active", cell: ({ row }) => row.original.is_active ? "Yes" : "No" },
    {
      id: "actions", header: "",
      cell: ({ row }) => (
        <div className="flex gap-1">
          <Button variant="ghost" size="icon" onClick={() => handleEdit(row.original)}><SquarePen className="size-4" /></Button>
          <Button variant="ghost" size="icon" onClick={() => handleDelete(row.original.id)}><Trash2 className="size-4 text-red-500" /></Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Gold Scheme Master</h2>
        <Button onClick={() => { reset(); setShowForm(true); }}><Plus className="size-4 mr-1" /> New Scheme</Button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="border rounded-lg p-4 space-y-4 bg-card">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><Label>Scheme Code *</Label><Input name="scheme_code" value={form.scheme_code} onChange={handleChange} required /></div>
            <div><Label>Scheme Name *</Label><Input name="name" value={form.name} onChange={handleChange} required /></div>
            <div><Label>Scheme Type</Label>
              <Select value={form.scheme_type} onValueChange={(v) => setForm((f) => ({ ...f, scheme_type: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{SCHEME_TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Gold Price Mode</Label>
              <Select value={form.gold_price_mode} onValueChange={(v) => setForm((f) => ({ ...f, gold_price_mode: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>{GOLD_PRICE_MODES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div><Label>Tenure (months)</Label><Input name="tenure_months" type="number" value={form.tenure_months} onChange={handleChange} /></div>
            <div><Label>Min Amount (₹)</Label><Input name="min_amount" type="number" value={form.min_amount} onChange={handleChange} /></div>
            <div><Label>Max Amount (₹)</Label><Input name="max_amount" type="number" value={form.max_amount} onChange={handleChange} placeholder="Unlimited" /></div>
            <div><Label>Accumulation Purity</Label>
              <Select value={form.accumulation_purity ? String(form.accumulation_purity) : "__none__"} onValueChange={(v) => setForm((f) => ({ ...f, accumulation_purity: v === "__none__" ? null : v }))}>
                <SelectTrigger><SelectValue placeholder="Select purity" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">None</SelectItem>
                  {purities.map((p) => <SelectItem key={p.id} value={String(p.id)}>{p.purity}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2 pt-6">
              <Checkbox checked={form.has_diamond_benefit} onCheckedChange={(v) => setForm((f) => ({ ...f, has_diamond_benefit: v }))} />
              <Label>Diamond ornament benefits</Label>
            </div>
          </div>

          <div><Label>Description</Label><Textarea name="description" value={form.description} onChange={handleChange} rows={2} /></div>

          {/* Benefit Tiers */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-base font-medium">Benefit Tiers (Making Charge Discounts)</Label>
              <Button type="button" variant="outline" size="sm" onClick={addTier}><Plus className="size-3 mr-1" /> Add Tier</Button>
            </div>
            {form.benefit_tiers.map((tier, idx) => (
              <div key={idx} className="grid grid-cols-6 gap-2 items-end">
                <div>
                  <Label className="text-xs">Type</Label>
                  <Select value={tier.product_type} onValueChange={(v) => updateTier(idx, "product_type", v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="GOLD">Gold</SelectItem>
                      <SelectItem value="DIAMOND">Diamond</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div><Label className="text-xs">From (months)</Label><Input type="number" value={tier.min_months} onChange={(e) => updateTier(idx, "min_months", e.target.value)} /></div>
                <div><Label className="text-xs">To (months)</Label><Input type="number" value={tier.max_months} onChange={(e) => updateTier(idx, "max_months", e.target.value)} /></div>
                <div><Label className="text-xs">LC Discount %</Label><Input type="number" value={tier.lc_discount_pct} onChange={(e) => updateTier(idx, "lc_discount_pct", e.target.value)} /></div>
                <div><Label className="text-xs">Value Discount %</Label><Input type="number" value={tier.value_discount_pct} onChange={(e) => updateTier(idx, "value_discount_pct", e.target.value)} /></div>
                <Button type="button" variant="ghost" size="icon" onClick={() => removeTier(idx)}><X className="size-4 text-red-500" /></Button>
              </div>
            ))}
          </div>

          <div className="flex gap-2">
            <Button type="submit" disabled={submitting}><Check className="size-4 mr-1" /> {editingId ? "Update" : "Create"}</Button>
            <Button type="button" variant="outline" onClick={reset}><X className="size-4 mr-1" /> Cancel</Button>
          </div>
        </form>
      )}

      {loading ? <Skeleton className="h-64" /> : <DataTable columns={columns} data={rows} />}
    </div>
  );
}
