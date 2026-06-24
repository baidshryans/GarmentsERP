import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { SquarePen, Plus, X, Check, GitBranch, Trash2, BarChart2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { useNavigate } from "react-router-dom";
import {
  fetchBranches,
  createBranch,
  updateBranch,
  deleteBranch,
  fetchCompanies,
} from "@/services/apiService";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const emptyForm = {
  company: "",
  branch_name: "",
  branch_code: "",
  description: "",
};

export default function BranchMasterPage() {
  const { toast } = useToast();
  const navigate  = useNavigate();
  const [rows, setRows]           = useState([]);
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm]           = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const [branchRes, companyRes] = await Promise.all([fetchBranches(), fetchCompanies()]);
    if (branchRes.success) {
      const d = branchRes.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    if (companyRes.success) {
      const d = companyRes.data;
      setCompanies(Array.isArray(d) ? d : d?.results ?? []);
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
    if (!form.branch_name.trim() || !form.branch_code.trim()) return;
    setSubmitting(true);

    const res = editingId
      ? await updateBranch(editingId, form)
      : await createBranch(form);

    if (res.success) {
      toast({ title: editingId ? "Branch updated" : "Branch created" });
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
      company:     row.company     ?? "",
      branch_name: row.branch_name ?? "",
      branch_code: row.branch_code ?? "",
      description: row.description ?? "",
    });
    setEditingId(row.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (row) => {
    if (!window.confirm(`Delete branch "${row.branch_name}"? This will unlink its retail locations but will not delete them.`)) return;
    const res = await deleteBranch(row.id);
    if (res.success) {
      toast({ title: "Branch deleted" });
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

  const columns = [
    {
      header: "Actions",
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
            onClick={() => navigate(`/setup/branch/${row.original.id}/analytics`)}
            className="text-sky-500 hover:text-sky-700"
            title="Analytics"
          >
            <BarChart2 className="size-4" />
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
    { header: "#", cell: ({ row }) => row.index + 1, size: 40 },
    { header: "Branch Code", accessorKey: "branch_code" },
    { header: "Branch Name", accessorKey: "branch_name" },
    {
      header: "Company",
      accessorKey: "company_name",
      cell: ({ row }) => row.original.company_name
        ? <span className="text-xs text-primary font-medium">{row.original.company_name}</span>
        : <span className="text-xs text-gray-300">—</span>,
    },
    {
      header: "Retail Locations",
      accessorKey: "retail_count",
      cell: ({ row }) => (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-accent-100 text-primary">
          {row.original.retail_count ?? 0} location{row.original.retail_count !== 1 ? "s" : ""}
        </span>
      ),
    },
    { header: "Description", accessorKey: "description" },
  ];

  return (
    <div className="p-4 flex flex-col gap-5">

      {/* Form Card */}
      {showForm && (
        <div className="rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/40">
            <div className="flex items-center gap-2">
              <GitBranch className="size-4 text-muted-foreground" />
              <span className="text-sm font-semibold">
                {editingId ? "Edit Branch" : "Add New Branch"}
              </span>
            </div>
            <button onClick={reset} className="text-muted-foreground hover:text-foreground">
              <X className="size-4" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-5">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Branch Information
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-5">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Company</Label>
                <Select
                  value={form.company ? String(form.company) : "__none__"}
                  onValueChange={(v) => setForm((f) => ({ ...f, company: v === "__none__" ? null : Number(v) }))}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="Select company…" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— No company —</SelectItem>
                    {companies.map((c) => (
                      <SelectItem key={c.id} value={String(c.id)}>{c.company_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Branch Name *</Label>
                <Input
                  name="branch_name"
                  value={form.branch_name}
                  onChange={handleChange}
                  placeholder="e.g. South Zone"
                  className="h-9 text-sm"
                  maxLength={100}
                  autoFocus
                  required
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Branch Code *</Label>
                <Input
                  name="branch_code"
                  value={form.branch_code}
                  onChange={handleChange}
                  placeholder="e.g. SZ"
                  className="h-9 text-sm"
                  maxLength={20}
                  required
                />
              </div>
              <div className="flex flex-col gap-1 md:col-span-1">
                <Label className="text-xs">Description</Label>
                <Input
                  name="description"
                  value={form.description}
                  onChange={handleChange}
                  placeholder="Optional note about this branch"
                  className="h-9 text-sm"
                />
              </div>
            </div>

            <div className="flex gap-3">
              <Button
                type="submit"
                size="sm"
                disabled={submitting || !form.branch_name.trim() || !form.branch_code.trim()}
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
            Branch master groups retail locations for analytics and performance tracking.
          </p>
          <Button
            size="sm"
            className="bg-primary hover:bg-primary text-white"
            onClick={() => setShowForm(true)}
          >
            <Plus className="size-4 mr-1" />
            Add Branch
          </Button>
        </div>
      )}

      {/* Table */}
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
