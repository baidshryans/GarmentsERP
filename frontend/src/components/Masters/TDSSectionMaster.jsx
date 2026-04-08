import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { Edit, Trash2, Plus, X, Check } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchTDSSections,
  createTDSSection,
  updateTDSSection,
  deleteTDSSection,
} from "@/services/apiService";

const emptyForm = {
  section_code: "",
  description: "",
  rate_individual: "",
  rate_company: "",
  rate_no_pan: "20",
  threshold_single: "",
  threshold_annual: "",
  is_active: true,
};

export default function TDSSectionMasterPage() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const res = await fetchTDSSections();
    if (res.success) {
      const d = res.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm((f) => ({ ...f, [name]: type === "checkbox" ? checked : value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.section_code.trim() || !form.description.trim()) return;
    setSubmitting(true);
    const payload = {
      section_code: form.section_code.trim().toUpperCase(),
      description: form.description.trim(),
      rate_individual: parseFloat(form.rate_individual) || 0,
      rate_company: parseFloat(form.rate_company) || 0,
      rate_no_pan: parseFloat(form.rate_no_pan) || 20,
      threshold_single: form.threshold_single ? parseFloat(form.threshold_single) : null,
      threshold_annual: form.threshold_annual ? parseFloat(form.threshold_annual) : null,
      is_active: form.is_active,
    };
    const res = editingId
      ? await updateTDSSection(editingId, payload)
      : await createTDSSection(payload);
    if (res.success) {
      toast({ title: editingId ? "TDS section updated" : "TDS section added" });
      reset();
      load();
    } else {
      const msg =
        typeof res.error === "object"
          ? Object.values(res.error).flat().join(", ")
          : res.error;
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setSubmitting(false);
  };

  useF4Submit(handleSubmit);

  const handleEdit = (row) => {
    setForm({
      section_code: row.section_code ?? "",
      description: row.description ?? "",
      rate_individual: row.rate_individual ?? "",
      rate_company: row.rate_company ?? "",
      rate_no_pan: row.rate_no_pan ?? "20",
      threshold_single: row.threshold_single ?? "",
      threshold_annual: row.threshold_annual ?? "",
      is_active: row.is_active ?? true,
    });
    setEditingId(row.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this TDS section?")) return;
    const res = await deleteTDSSection(id);
    if (res.success) {
      toast({ title: "TDS section deleted" });
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

  const fmtRate = (v) => v != null ? `${parseFloat(v).toFixed(3)}%` : "—";
  const fmtAmt = (v) => v != null ? `₹${parseFloat(v).toLocaleString('en-IN')}` : "—";

  const columns = [
    {
      header: "Action",
      cell: ({ row }) => (
        <div className="flex gap-3">
          <button onClick={() => handleEdit(row.original)} className="text-primary hover:text-primary">
            <Edit className="size-4" />
          </button>
          <button onClick={() => handleDelete(row.original.id)} className="text-red-500 hover:text-red-700">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", cell: ({ row }) => row.index + 1, size: 40 },
    { header: "Section", accessorKey: "section_code" },
    { header: "Description", accessorKey: "description" },
    { header: "Indiv %", cell: ({ row }) => fmtRate(row.original.rate_individual) },
    { header: "Co %", cell: ({ row }) => fmtRate(row.original.rate_company) },
    { header: "No PAN %", cell: ({ row }) => fmtRate(row.original.rate_no_pan) },
    { header: "Threshold (Single)", cell: ({ row }) => fmtAmt(row.original.threshold_single) },
    { header: "Threshold (Annual)", cell: ({ row }) => fmtAmt(row.original.threshold_annual) },
    { header: "Ledger", accessorKey: "ledger_name" },
    {
      header: "Active",
      cell: ({ row }) => (
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${row.original.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
          {row.original.is_active ? "Yes" : "No"}
        </span>
      ),
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-4">
      {/* Form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold">{editingId ? "Edit TDS Section" : "Add TDS Section"}</span>
            <button type="button" onClick={reset} className="text-muted-foreground hover:text-foreground">
              <X className="size-4" />
            </button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Section Code *</Label>
              <Input
                name="section_code"
                value={form.section_code}
                onChange={handleChange}
                placeholder="e.g. 194C"
                className="h-9 text-sm uppercase"
                maxLength={10}
                autoFocus
                readOnly={!!editingId}
                required
              />
            </div>
            <div className="flex flex-col gap-1 md:col-span-3">
              <Label className="text-xs">Description *</Label>
              <Input
                name="description"
                value={form.description}
                onChange={handleChange}
                placeholder="e.g. Payments to Contractors"
                className="h-9 text-sm"
                maxLength={200}
                required
              />
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Individual/HUF Rate %</Label>
              <Input name="rate_individual" type="number" step="0.001" value={form.rate_individual} onChange={handleChange} className="h-9 text-sm" placeholder="0.000" />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Company/Firm Rate %</Label>
              <Input name="rate_company" type="number" step="0.001" value={form.rate_company} onChange={handleChange} className="h-9 text-sm" placeholder="0.000" />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs">No PAN Rate %</Label>
              <Input name="rate_no_pan" type="number" step="0.001" value={form.rate_no_pan} onChange={handleChange} className="h-9 text-sm" placeholder="20.000" />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Single Payment Threshold (₹)</Label>
              <Input name="threshold_single" type="number" value={form.threshold_single} onChange={handleChange} className="h-9 text-sm" placeholder="e.g. 30000" />
            </div>
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Annual Threshold (₹)</Label>
              <Input name="threshold_annual" type="number" value={form.threshold_annual} onChange={handleChange} className="h-9 text-sm" placeholder="e.g. 100000" />
            </div>
          </div>
          <div className="flex items-center gap-3 mb-4">
            <input type="checkbox" id="is_active" name="is_active" checked={form.is_active} onChange={handleChange} className="h-4 w-4 accent-violet-600" />
            <label htmlFor="is_active" className="text-sm text-foreground/80">Active</label>
          </div>
          <div className="flex gap-3">
            <Button type="submit" size="sm" disabled={submitting} className="bg-primary hover:bg-primary text-white">
              <Check className="size-4 mr-1" />
              {editingId ? "Update" : "Save"}
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={reset}>
              <X className="size-4 mr-1" />
              Cancel
            </Button>
          </div>
        </form>
      )}

      {!showForm && (
        <div className="flex justify-end">
          <Button size="sm" className="bg-primary hover:bg-primary text-white" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add TDS Section
          </Button>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}
