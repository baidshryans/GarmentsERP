import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
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
import { SquarePen, Plus, X, Check, Store, Zap, BarChart2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import {
  fetchRetails,
  createRetail,
  updateRetail,
  fetchStates,
  fetchBranches,
  fetchGstins,
} from "@/services/apiService";
import { COUNTRIES } from "@/components/ui/PhoneInput";

const emptyForm = {
  retail_name: "",
  retail_code: "",
  gstin_master: "",
  email: "",
  phone: "",
  address_line1: "",
  address_line2: "",
  address_line3: "",
  city: "",
  pincode: "",
  state: "",
  branch: "",
  is_exhibition: false,
  max_cash_receipt_limit: 199999,
  max_cash_payment_limit: 10000,
  default_country_code: "IN",
};

export default function RetailMasterPage() {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [rows, setRows]         = useState([]);
  const [states, setStates]     = useState([]);
  const [branches, setBranches] = useState([]);
  const [gstins, setGstins]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm]         = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    setLoading(true);
    const [retailRes, stateRes, branchRes, gstinRes] = await Promise.all([
      fetchRetails(),
      fetchStates(),
      fetchBranches(),
      fetchGstins(),
    ]);
    if (retailRes.success) {
      const d = retailRes.data;
      setRows(Array.isArray(d) ? d : d?.results ?? []);
    }
    if (stateRes.success) {
      const d = stateRes.data;
      setStates(Array.isArray(d) ? d : d?.results ?? []);
    }
    if (branchRes.success) {
      const d = branchRes.data;
      setBranches(Array.isArray(d) ? d : d?.results ?? []);
    }
    if (gstinRes.success) {
      const d = gstinRes.data;
      setGstins(Array.isArray(d) ? d : d?.results ?? []);
    }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleChange = (e) => {
    const { name, type, checked, value } = e.target;
    setForm((f) => ({ ...f, [name]: type === "checkbox" ? checked : value }));
  };

  const handleSelect = (name, value) =>
    setForm((f) => ({ ...f, [name]: value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.retail_name.trim() || !form.retail_code.trim()) return;
    setSubmitting(true);

    const payload = { ...form };
    // Send nulls for optional empty strings on create
    if (!payload.gstin_master) payload.gstin_master = null;
    if (!payload.email)   payload.email  = null;
    if (!payload.state)   payload.state  = null;
    if (!payload.branch)  payload.branch = null;

    const res = editingId
      ? await updateRetail(editingId, payload)
      : await createRetail(payload);

    if (res.success) {
      toast({ title: editingId ? "Retail updated" : "Retail added" });
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
      retail_name: row.retail_name ?? "",
      retail_code: row.retail_code ?? "",
      gstin_master: row.gstin_master ?? "",
      email: row.email ?? "",
      phone: row.phone ?? "",
      address_line1: row.address_line1 ?? "",
      address_line2: row.address_line2 ?? "",
      address_line3: row.address_line3 ?? "",
      city: row.city ?? "",
      pincode: row.pincode ?? "",
      state: row.state ? String(row.state) : "",
      branch: row.branch ? String(row.branch) : "",
      is_exhibition: row.is_exhibition ?? false,
      max_cash_receipt_limit: row.max_cash_receipt_limit ?? 199999,
      max_cash_payment_limit: row.max_cash_payment_limit ?? 10000,
      default_country_code: row.default_country_code ?? "IN",
    });
    setEditingId(row.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const reset = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
  };

  const columns = [
    {
      header: "Action",
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
            onClick={() => navigate(`/setup/retail/${row.original.id}/analytics`)}
            className="text-sky-500 hover:text-sky-700"
            title="Analytics"
          >
            <BarChart2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", cell: ({ row }) => row.index + 1, size: 40 },
    { header: "Code", accessorKey: "retail_code" },
    { header: "Retail Name", accessorKey: "retail_name" },
    {
      header: "Type",
      cell: ({ row }) => row.original.is_exhibition
        ? <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-100 text-amber-800"><Zap className="size-3" />Exhibition</span>
        : <span className="text-xs text-muted-foreground">Regular</span>,
    },
    { header: "GSTIN", accessorKey: "gstin_master_str" },
    { header: "Phone", accessorKey: "phone" },
    { header: "City", accessorKey: "city" },
    { header: "State", accessorKey: "state_name" },
    {
      header: "Branch",
      cell: ({ row }) => row.original.branch_name
        ? <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-accent-100 text-primary">{row.original.branch_name}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-5">

      {/* Form Card */}
      {showForm && (
        <div className="rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/40">
            <div className="flex items-center gap-2">
              <Store className="size-4 text-muted-foreground" />
              <span className="text-sm font-semibold">
                {editingId ? "Edit Retail" : "Add New Retail"}
              </span>
            </div>
            <button onClick={reset} className="text-muted-foreground hover:text-foreground">
              <X className="size-4" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-5">
            {/* Section: Basic Info */}
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Basic Information
            </p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Retail Name *</Label>
                <Input
                  name="retail_name"
                  value={form.retail_name}
                  onChange={handleChange}
                  placeholder="e.g. Jewel India"
                  className="h-9 text-sm"
                  maxLength={100}
                  autoFocus
                  required
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Retail Code *</Label>
                <Input
                  name="retail_code"
                  value={form.retail_code}
                  onChange={handleChange}
                  placeholder="e.g. R001"
                  className="h-9 text-sm"
                  maxLength={100}
                  required
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">GSTIN</Label>
                <Select
                  value={form.gstin_master ? String(form.gstin_master) : "__none__"}
                  onValueChange={(v) => handleSelect("gstin_master", v === "__none__" ? "" : v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="Select GSTIN" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">— No GSTIN —</SelectItem>
                    {gstins.map((g) => (
                      <SelectItem key={g.id} value={String(g.id)}>
                        {g.gstin}{g.legal_name ? ` — ${g.legal_name}` : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Email</Label>
                <Input
                  type="email"
                  name="email"
                  value={form.email}
                  onChange={handleChange}
                  placeholder="contact@example.com"
                  className="h-9 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Phone *</Label>
                <Input
                  name="phone"
                  value={form.phone}
                  onChange={handleChange}
                  placeholder="10-digit number"
                  className="h-9 text-sm"
                  maxLength={15}
                  required
                />
              </div>
              <div className="flex flex-col gap-1 justify-end">
                <Label className="text-xs invisible">Exhibition</Label>
                <label className="flex items-center gap-2 h-9 cursor-pointer select-none group">
                  <input
                    type="checkbox"
                    name="is_exhibition"
                    checked={form.is_exhibition}
                    onChange={handleChange}
                    className="size-4 rounded border-gray-300 accent-accent-700 cursor-pointer"
                  />
                  <span className="text-sm text-muted-foreground group-hover:text-foreground flex items-center gap-1">
                    <Zap className="size-3.5 text-amber-500" />
                    Exhibition Retail
                  </span>
                </label>
              </div>
            </div>

            {/* Section: Address */}
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
              Address
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
              <div className="flex flex-col gap-1 md:col-span-2">
                <Label className="text-xs">Address Line 1 {form.is_exhibition ? "" : "*"}</Label>
                <Input
                  name="address_line1"
                  value={form.address_line1}
                  onChange={handleChange}
                  placeholder="Street / Door no."
                  className="h-9 text-sm"
                  maxLength={100}
                  required={!form.is_exhibition}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Address Line 2</Label>
                <Input
                  name="address_line2"
                  value={form.address_line2}
                  onChange={handleChange}
                  placeholder="Area / Landmark"
                  className="h-9 text-sm"
                  maxLength={100}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Address Line 3</Label>
                <Input
                  name="address_line3"
                  value={form.address_line3}
                  onChange={handleChange}
                  placeholder="District / Zone"
                  className="h-9 text-sm"
                  maxLength={100}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">City</Label>
                <Input
                  name="city"
                  value={form.city}
                  onChange={handleChange}
                  placeholder="City"
                  className="h-9 text-sm"
                  maxLength={100}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Pincode</Label>
                <Input
                  name="pincode"
                  value={form.pincode}
                  onChange={handleChange}
                  placeholder="6-digit pincode"
                  className="h-9 text-sm"
                  maxLength={10}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">State</Label>
                <Select
                  value={form.state ? String(form.state) : ""}
                  onValueChange={(v) => handleSelect("state", v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="Select state" />
                  </SelectTrigger>
                  <SelectContent>
                    {states.map((s) => (
                      <SelectItem key={s.id} value={String(s.id)}>
                        {s.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Branch <span className="text-muted-foreground font-normal">(analytics grouping)</span></Label>
                <Select
                  value={form.branch ? String(form.branch) : "__none__"}
                  onValueChange={(v) => handleSelect("branch", v === "__none__" ? "" : v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue placeholder="No branch" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">No branch</SelectItem>
                    {branches.map((b) => (
                      <SelectItem key={b.id} value={String(b.id)}>
                        {b.branch_name} ({b.branch_code})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">Default Mobile Country</Label>
                <Select
                  value={form.default_country_code || "IN"}
                  onValueChange={(v) => handleSelect("default_country_code", v)}
                >
                  <SelectTrigger className="h-9 text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="max-h-72 overflow-y-auto">
                    {COUNTRIES.map((c) => (
                      <SelectItem key={c.code} value={c.code}>
                        {c.flag} {c.dial} {c.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <Button
                type="submit"
                size="sm"
                disabled={submitting || !form.retail_name.trim() || !form.retail_code.trim()}
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
        <div className="flex justify-end">
          <Button size="sm" className="bg-primary hover:bg-primary text-white" onClick={() => setShowForm(true)}>
            <Plus className="size-4 mr-1" />
            Add Retail
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
