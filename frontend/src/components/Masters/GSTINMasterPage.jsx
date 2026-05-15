import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { SquarePen, Plus, X, Check, Trash2, ShieldCheck } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchGSTINMasters,
  createGSTINMaster,
  updateGSTINMaster,
  deleteGSTINMaster,
  fetchStates,
} from "@/services/apiService";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const emptyForm = {
  gstin: "",
  state: "",
};

const LedgerChip = ({ label, name }) =>
  name ? (
    <span className="inline-block text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
      {label}: {name}
    </span>
  ) : null;

export default function GSTINMasterPage() {
  const { toast } = useToast();
  const [rows, setRows]       = useState([]);
  const [states, setStates]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm]         = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const [gstRes, stRes] = await Promise.all([
      fetchGSTINMasters(),
      fetchStates(),
    ]);
    if (gstRes.success) {
      const d = gstRes.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    if (stRes.success) {
      const d = stRes.data;
      setStates(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((f) => ({ ...f, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.gstin.trim()) return;
    setSubmitting(true);

    const payload = {
      gstin: form.gstin.trim().toUpperCase(),
      state: form.state || null,
    };

    const res = editingId
      ? await updateGSTINMaster(editingId, payload)
      : await createGSTINMaster(payload);

    if (res.success) {
      toast({ title: editingId ? "GSTIN updated" : "GSTIN created" });
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
      gstin:  row.gstin ?? "",
      state:  row.state ? String(row.state) : "",
    });
    setEditingId(row.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete GSTIN "${row.gstin}"?`)) return;
    const res = await deleteGSTINMaster(row.id);
    if (res.success) {
      toast({ title: "GSTIN deleted" });
      load();
    } else {
      const msg = typeof res.error === "object" ? JSON.stringify(res.error) : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
  };

  const reset = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
  };

  const columns = [
    {
      header: "Actions",
      size: 80,
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleEdit(row.original)}
            className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors"
            title="Edit"
          >
            <SquarePen className="size-4" />
          </button>
          <button
            onClick={() => handleDelete(row.original)}
            className="p-1.5 rounded text-red-500 hover:bg-red-50 transition-colors"
            title="Delete"
          >
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", size: 40, cell: ({ row }) => row.index + 1 },
    {
      header: "GSTIN",
      accessorKey: "gstin",
      cell: ({ row }) => (
        <span className="font-mono text-[13px] font-semibold tracking-wide text-primary">
          {row.original.gstin}
        </span>
      ),
    },
    {
      header: "State",
      accessorKey: "state_name",
      cell: ({ row }) =>
        row.original.state_name ? (
          <span className="text-xs">{row.original.state_name}</span>
        ) : (
          <span className="text-xs text-muted-foreground/40">—</span>
        ),
    },
    {
      header: "GST Ledgers",
      cell: ({ row }) => {
        const r = row.original;
        return (
          <div className="flex flex-wrap gap-1">
            <LedgerChip label="Out CGST"  name={r.output_cgst_name} />
            <LedgerChip label="Out SGST"  name={r.output_sgst_name} />
            <LedgerChip label="Out IGST"  name={r.output_igst_name} />
            <LedgerChip label="In CGST"   name={r.input_cgst_name}  />
            <LedgerChip label="In SGST"   name={r.input_sgst_name}  />
            <LedgerChip label="In IGST"   name={r.input_igst_name}  />
          </div>
        );
      },
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-5">

      {/* Form card */}
      {showForm && (
        <div className="rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/40">
            <div className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-muted-foreground" />
              <span className="text-sm font-semibold">
                {editingId ? "Edit GSTIN" : "Add GSTIN"}
              </span>
            </div>
            <button onClick={reset} className="text-muted-foreground hover:text-foreground">
              <X className="size-4" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-5">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              GST Registration Details
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-5">

              <div className="flex flex-col gap-1">
                <Label className="text-xs">GSTIN *</Label>
                <Input
                  name="gstin"
                  value={form.gstin}
                  onChange={handleChange}
                  placeholder="e.g. 27AAAAA0000A1Z5"
                  className="h-9 text-sm font-mono uppercase"
                  maxLength={15}
                  autoFocus
                  required
                />
              </div>

              <div className="flex flex-col gap-1">
                <Label className="text-xs">State</Label>
                <Select
                  value={form.state ? String(form.state) : "__none__"}
                  onValueChange={(v) =>
                    setForm((f) => ({ ...f, state: v === "__none__" ? "" : v }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="Select state…" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— No state —</SelectItem>
                    {states.map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

            </div>

            {editingId && (
              <p className="text-[11px] text-muted-foreground mb-4">
                GST input/output ledgers are auto-managed by the system and will appear in the table after saving.
              </p>
            )}

            <div className="flex gap-3">
              <Button
                type="submit"
                size="sm"
                disabled={submitting || !form.gstin.trim()}
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

      {/* Header row */}
      {!showForm && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            GSTIN registrations for this organisation. GST ledgers are auto-created on save.
          </p>
          <Button
            size="sm"
            className="bg-primary hover:bg-primary text-white"
            onClick={() => setShowForm(true)}
          >
            <Plus className="size-4 mr-1" />
            Add GSTIN
          </Button>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}
