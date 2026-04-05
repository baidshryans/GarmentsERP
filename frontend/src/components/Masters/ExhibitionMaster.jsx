import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { DataTable } from "@/table";
import { Edit, Plus, X, Check, MapPin, Zap, ZapOff, Trash2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchExhibitions, createExhibition, updateExhibition, deleteExhibition,
  activateExhibition, deactivateExhibition, fetchStates,
} from "@/services/apiService";

const emptyForm = {
  name: "", gstin: "", state: "",
  address_line1: "", address_line2: "", address_line3: "",
  city: "", pincode: "", start_date: "", end_date: "",
};

export default function ExhibitionMaster() {
  const { toast } = useToast();
  const [rows, setRows] = useState([]);
  const [states, setStates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);
  const [toggling, setToggling] = useState(null); // id being toggled

  const load = async () => {
    setLoading(true);
    const [exhRes, stateRes] = await Promise.all([fetchExhibitions(), fetchStates()]);
    if (exhRes.success) setRows(Array.isArray(exhRes.data) ? exhRes.data : exhRes.data?.results ?? []);
    if (stateRes.success) setStates(Array.isArray(stateRes.data) ? stateRes.data : stateRes.data?.results ?? []);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleChange = (e) => setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  const handleSelect = (name, value) => setForm((f) => ({ ...f, [name]: value === "__none__" ? "" : value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.gstin.trim() || !form.address_line1.trim()) return;
    setSubmitting(true);
    const payload = { ...form, state: form.state || null };
    const res = editingId ? await updateExhibition(editingId, payload) : await createExhibition(payload);
    if (res.success) {
      toast({ title: editingId ? "Exhibition updated" : "Exhibition created" });
      reset();
      load();
    } else {
      const msg = typeof res.error === "object"
        ? Object.entries(res.error).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(" | ")
        : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setSubmitting(false);
  };

  useF4Submit(handleSubmit);

  const handleEdit = (row) => {
    setForm({
      name: row.name ?? "", gstin: row.gstin ?? "",
      state: row.state ? String(row.state) : "",
      address_line1: row.address_line1 ?? "", address_line2: row.address_line2 ?? "",
      address_line3: row.address_line3 ?? "", city: row.city ?? "",
      pincode: row.pincode ?? "",
      start_date: row.start_date ?? "", end_date: row.end_date ?? "",
    });
    setEditingId(row.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleToggle = async (row) => {
    setToggling(row.id);
    const res = row.is_active ? await deactivateExhibition(row.id) : await activateExhibition(row.id);
    if (res.success) {
      toast({ title: row.is_active ? "Exhibition deactivated" : "Exhibition activated — invoices will now use this address & GSTIN" });
      load();
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
    setToggling(null);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this exhibition profile?")) return;
    const res = await deleteExhibition(id);
    if (res.success) { toast({ title: "Deleted" }); load(); }
    else toast({ title: "Error", description: String(res.error), variant: "destructive" });
  };

  const reset = () => { setShowForm(false); setEditingId(null); setForm(emptyForm); };

  const columns = [
    {
      header: "Actions",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div className="flex items-center gap-2">
            <button onClick={() => handleEdit(r)} className="text-violet-500 hover:text-violet-700" title="Edit">
              <Edit className="size-4" />
            </button>
            <button
              onClick={() => handleToggle(r)}
              disabled={toggling === r.id}
              className={r.is_active ? "text-amber-500 hover:text-amber-700" : "text-muted-foreground hover:text-green-600"}
              title={r.is_active ? "Deactivate" : "Activate"}
            >
              {r.is_active ? <ZapOff className="size-4" /> : <Zap className="size-4" />}
            </button>
            <button onClick={() => handleDelete(r.id)} className="text-red-400 hover:text-red-600" title="Delete">
              <Trash2 className="size-4" />
            </button>
          </div>
        );
      },
    },
    { header: "#", cell: ({ row }) => row.index + 1, size: 40 },
    {
      header: "Status",
      accessorKey: "is_active",
      cell: ({ getValue }) => getValue()
        ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700"><Zap className="size-3" />Active</span>
        : <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-muted text-muted-foreground">Inactive</span>,
    },
    { header: "Exhibition Name", accessorKey: "name" },
    { header: "GSTIN", accessorKey: "gstin", cell: ({ getValue }) => <span className="font-mono text-xs">{getValue() || "—"}</span> },
    { header: "State", accessorKey: "state_name", cell: ({ getValue }) => getValue() || "—" },
    { header: "City", accessorKey: "city", cell: ({ getValue }) => getValue() || "—" },
    {
      header: "Period",
      cell: ({ row }) => {
        const { start_date, end_date } = row.original;
        if (!start_date && !end_date) return "—";
        return `${start_date || "?"} → ${end_date || "?"}`;
      },
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-5">

      {/* Active Exhibition Banner */}
      {rows.some(r => r.is_active) && (() => {
        const active = rows.find(r => r.is_active);
        return (
          <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <MapPin className="size-4 text-amber-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-amber-800">Exhibition Mode Active: {active.name}</p>
              <p className="text-xs text-amber-700 mt-0.5">
                All new sales invoices will use GSTIN <span className="font-mono">{active.gstin}</span> and the exhibition address.
              </p>
            </div>
          </div>
        );
      })()}

      {/* Form */}
      {showForm && (
        <div className="rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/40">
            <div className="flex items-center gap-2">
              <MapPin className="size-4 text-violet-600" />
              <span className="text-sm font-semibold">{editingId ? "Edit Exhibition" : "Add Exhibition Profile"}</span>
            </div>
            <button onClick={reset} className="text-muted-foreground hover:text-foreground"><X className="size-4" /></button>
          </div>

          <form onSubmit={handleSubmit} className="p-5">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">Exhibition Details</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-5">
              <div className="flex flex-col gap-1 md:col-span-2">
                <Label className="text-xs">Exhibition Name *</Label>
                <Input name="name" value={form.name} onChange={handleChange}
                  placeholder="e.g. Chennai Trade Fair Jan 2025" className="h-9 text-sm" required />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Temporary GSTIN *</Label>
                <Input name="gstin" value={form.gstin} onChange={handleChange}
                  placeholder="15-char GSTIN" className="h-9 text-sm font-mono" maxLength={30} required />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Start Date</Label>
                <Input type="date" name="start_date" value={form.start_date} onChange={handleChange} className="h-9 text-sm" />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">End Date</Label>
                <Input type="date" name="end_date" value={form.end_date} onChange={handleChange} className="h-9 text-sm" />
              </div>
            </div>

            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">Exhibition Venue Address</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              <div className="flex flex-col gap-1 md:col-span-2">
                <Label className="text-xs">Address Line 1 *</Label>
                <Input name="address_line1" value={form.address_line1} onChange={handleChange}
                  placeholder="Hall / Street / Door no." className="h-9 text-sm" required />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Address Line 2</Label>
                <Input name="address_line2" value={form.address_line2} onChange={handleChange}
                  placeholder="Area / Landmark" className="h-9 text-sm" />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Address Line 3</Label>
                <Input name="address_line3" value={form.address_line3} onChange={handleChange}
                  placeholder="District / Zone" className="h-9 text-sm" />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">City</Label>
                <Input name="city" value={form.city} onChange={handleChange} placeholder="City" className="h-9 text-sm" />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Pincode</Label>
                <Input name="pincode" value={form.pincode} onChange={handleChange} placeholder="6-digit pincode" className="h-9 text-sm" maxLength={10} />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">State</Label>
                <Select value={form.state || "__none__"} onValueChange={(v) => handleSelect("state", v)}>
                  <SelectTrigger className="h-9 text-sm"><SelectValue placeholder="Select state" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— Select state —</SelectItem>
                    {states.map((s) => <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex gap-3">
              <Button type="submit" size="sm" disabled={submitting || !form.name.trim() || !form.gstin.trim() || !form.address_line1.trim()}
                className="bg-violet-700 hover:bg-violet-800 text-white">
                <Check className="size-4 mr-1" />{editingId ? "Update" : "Save"}
              </Button>
              <Button type="button" variant="outline" size="sm" onClick={reset}>
                <X className="size-4 mr-1" />Cancel
              </Button>
            </div>
          </form>
        </div>
      )}

      {/* Header row */}
      {!showForm && (
        <div className="flex justify-end">
          <Button size="sm" className="bg-violet-700 hover:bg-violet-800 text-white" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />Add Exhibition
          </Button>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">{[...Array(3)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}</div>
      ) : (
        <DataTable
          columns={columns}
          data={rows}
          rowClassName={(row) => row.original.is_active ? "bg-amber-50/60" : ""}
        />
      )}
    </div>
  );
}
