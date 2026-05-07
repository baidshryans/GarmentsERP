import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTable } from "@/table";
import { Building2, SquarePen, Plus, X, Check, Trash2, GitBranch, Globe, Upload, Image as ImageIcon } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { useF4Submit } from "@/hooks/useF4Submit";
import { fetchCompanies, createCompany, updateCompany, deleteCompany } from "@/services/apiService";

const emptyForm = {
  company_name: "",
  pan: "",
  tan: "",
  gstin: "",
  cin: "",
  phone: "",
  email: "",
  address: "",
  city: "",
  pincode: "",
  website: "",
  enforce_cash_limits: false,
  max_cash_receipt_limit: 199999,
  max_cash_payment_limit: 10000,
  bis_logo: null,        // File on upload, omitted when not changed
  company_logo: null,
};

// CIN format: L/U + 5 digits + 2 alpha (state) + 4 digits + 3 alpha (company type) + 6 digits
// e.g. U74999MH2011PTC123456 or L17110MH1973PLC019786
const CIN_REGEX = /^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$/;

function validateCIN(cin) {
  if (!cin || !cin.trim()) return "CIN is required for registered companies.";
  if (!CIN_REGEX.test(cin.trim().toUpperCase()))
    return "Invalid CIN format. Expected: L/U + 5 digits + state code + 4 digits + company type + 6 digits (e.g. U74999MH2011PTC123456)";
  return null;
}

export default function CompanyMasterPage() {
  const { toast }   = useToast();
  const [rows, setRows]               = useState([]);
  const [loading, setLoading]         = useState(true);
  const [showForm, setShowForm]       = useState(false);
  const [editingId, setEditingId]     = useState(null);
  const [form, setForm]               = useState(emptyForm);
  const [submitting, setSubmitting]   = useState(false);
  const [cinError, setCinError]       = useState(null);
  // Existing-logo preview URLs come from the server in edit mode; new uploads
  // overlay them by setting form.bis_logo / form.company_logo to a File.
  const [existingBisLogo, setExistingBisLogo]         = useState(null);
  const [existingCompanyLogo, setExistingCompanyLogo] = useState(null);

  const load = async () => {
    setLoading(true);
    const res = await fetchCompanies();
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
    if (name === "cin") setCinError(validateCIN(value));
  };

  const handleFile = (name) => (e) => {
    const file = e.target.files?.[0] || null;
    setForm((f) => ({ ...f, [name]: file }));
  };

  const clearLogo = (name) => {
    // Empty string tells DRF to clear the field; existing preview is dropped.
    setForm((f) => ({ ...f, [name]: "" }));
    if (name === "bis_logo")     setExistingBisLogo(null);
    if (name === "company_logo") setExistingCompanyLogo(null);
  };

  /* Strip File-typed fields that the user did not touch so we don't send
     stale `null`s on PATCH (which would clear server-side files). */
  const buildSubmitPayload = () => {
    const out = { ...form };
    if (out.bis_logo === null)     delete out.bis_logo;
    if (out.company_logo === null) delete out.company_logo;
    return out;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.company_name.trim()) return;
    const cinErr = validateCIN(form.cin);
    if (cinErr) { setCinError(cinErr); return; }
    setSubmitting(true);

    const payload = buildSubmitPayload();
    const res = editingId
      ? await updateCompany(editingId, payload)
      : await createCompany(payload);

    if (res.success) {
      toast({ title: editingId ? "Company updated" : "Company created" });
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
      company_name:           row.company_name           ?? "",
      pan:                    row.pan                    ?? "",
      tan:                    row.tan                    ?? "",
      gstin:                  row.gstin                  ?? "",
      cin:                    row.cin                    ?? "",
      phone:                  row.phone                  ?? "",
      email:                  row.email                  ?? "",
      address:                row.address                ?? "",
      city:                   row.city                   ?? "",
      pincode:                row.pincode                ?? "",
      website:                row.website                ?? "",
      enforce_cash_limits:    row.enforce_cash_limits    ?? false,
      max_cash_receipt_limit: row.max_cash_receipt_limit ?? 199999,
      max_cash_payment_limit: row.max_cash_payment_limit ?? 10000,
      bis_logo: null,
      company_logo: null,
    });
    setExistingBisLogo(row.bis_logo || null);
    setExistingCompanyLogo(row.company_logo || null);
    setEditingId(row.id);
    setShowForm(true);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleDelete = async (row) => {
    if (!window.confirm(
      `Delete company "${row.company_name}"? All linked branches will be unlinked but not deleted.`
    )) return;
    const res = await deleteCompany(row.id);
    if (res.success) {
      toast({ title: "Company deleted" });
      load();
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
  };

  const reset = () => {
    setShowForm(false);
    setEditingId(null);
    setForm(emptyForm);
    setCinError(null);
    setExistingBisLogo(null);
    setExistingCompanyLogo(null);
  };

  const columns = [
    {
      header: "Actions",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <button onClick={() => handleEdit(row.original)} className="p-1.5 rounded text-primary hover:bg-primary/10 transition-colors" title="Edit">
            <SquarePen className="size-4" />
          </button>
          <button onClick={() => handleDelete(row.original)} className="text-rose-400 hover:text-rose-600" title="Delete">
            <Trash2 className="size-4" />
          </button>
        </div>
      ),
    },
    { header: "#", cell: ({ row }) => row.index + 1, size: 40 },
    {
      header: "Company Name",
      accessorKey: "company_name",
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <Building2 className="size-3.5 text-primary flex-shrink-0" />
          <span className="font-semibold text-gray-800">{row.original.company_name}</span>
        </div>
      ),
    },
    { header: "PAN", accessorKey: "pan" },
    { header: "TAN", accessorKey: "tan" },
    { header: "Phone", accessorKey: "phone" },
    { header: "Email", accessorKey: "email" },
    {
      header: "Branches",
      accessorKey: "branch_count",
      cell: ({ row }) => (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-violet-100 text-primary">
          <GitBranch className="size-3" />
          {row.original.branch_count ?? 0}
        </span>
      ),
    },
    {
      header: "Retail Locations",
      accessorKey: "retail_count",
      cell: ({ row }) => (
        <span className="text-xs text-gray-500">{row.original.retail_count ?? 0}</span>
      ),
    },
  ];

  return (
    <div className="p-4 flex flex-col gap-5">

      {/* Form Card */}
      {showForm && (
        <div className="rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/40">
            <div className="flex items-center gap-2">
              <Building2 className="size-4 text-muted-foreground" />
              <span className="text-sm font-semibold">
                {editingId ? "Edit Company" : "Add New Company"}
              </span>
            </div>
            <button onClick={reset} className="text-muted-foreground hover:text-foreground">
              <X className="size-4" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-5 space-y-5">

            {/* Identity */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Company Identity
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex flex-col gap-1 md:col-span-2">
                  <Label className="text-xs">Company Name *</Label>
                  <Input
                    name="company_name"
                    value={form.company_name}
                    onChange={handleChange}
                    placeholder="e.g. Jewel India Private Limited"
                    className="h-9 text-sm"
                    autoFocus
                    required
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Website</Label>
                  <Input
                    name="website"
                    value={form.website}
                    onChange={handleChange}
                    placeholder="https://..."
                    className="h-9 text-sm"
                  />
                </div>
              </div>
            </div>

            {/* Tax & Compliance */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Tax & Compliance
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">PAN</Label>
                  <Input
                    name="pan"
                    value={form.pan}
                    onChange={handleChange}
                    placeholder="AAAAA0000A"
                    className="h-9 text-sm uppercase"
                    maxLength={10}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">TAN</Label>
                  <Input
                    name="tan"
                    value={form.tan}
                    onChange={handleChange}
                    placeholder="AAAA00000A"
                    className="h-9 text-sm uppercase"
                    maxLength={10}
                  />
                </div>
                <div className="flex flex-col gap-1 md:col-span-2">
                  <Label className="text-xs">GSTIN <span className="text-muted-foreground font-normal">(company-level, if any)</span></Label>
                  <Input
                    name="gstin"
                    value={form.gstin}
                    onChange={handleChange}
                    placeholder="15 digit GSTIN"
                    className="h-9 text-sm uppercase"
                    maxLength={15}
                  />
                </div>
                <div className="flex flex-col gap-1 md:col-span-2">
                  <Label className="text-xs">
                    CIN * <span className="text-muted-foreground font-normal">(Corporate Identification Number)</span>
                  </Label>
                  <Input
                    name="cin"
                    value={form.cin}
                    onChange={handleChange}
                    onBlur={(e) => setCinError(validateCIN(e.target.value))}
                    placeholder="e.g. U74999MH2011PTC123456"
                    className={`h-9 text-sm uppercase ${cinError ? "border-red-400 focus-visible:ring-red-300" : ""}`}
                    maxLength={21}
                    required
                  />
                  {cinError && (
                    <p className="text-xs text-red-500 mt-0.5">{cinError}</p>
                  )}
                  <p className="text-[11px] text-muted-foreground">
                    Format: L/U · 5 digits · state (2 letters) · 4 digits · company type (3 letters) · 6 digits
                  </p>
                </div>
              </div>
            </div>

            {/* Cash Compliance Limits */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Cash Compliance Limits
                </p>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    name="enforce_cash_limits"
                    checked={form.enforce_cash_limits}
                    onChange={handleChange}
                    className="size-4 accent-primary cursor-pointer"
                  />
                  <span className="text-xs text-muted-foreground">
                    Enforce limits
                  </span>
                </label>
              </div>
              <div className={`grid grid-cols-1 md:grid-cols-2 gap-4 transition-opacity ${form.enforce_cash_limits ? "" : "opacity-40 pointer-events-none"}`}>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">
                    Cash Limit / Customer / FY (₹){" "}
                    <span className="text-muted-foreground font-normal">Sec 269ST</span>
                  </Label>
                  <Input
                    type="number"
                    name="max_cash_receipt_limit"
                    value={form.max_cash_receipt_limit}
                    onChange={handleChange}
                    placeholder="199999"
                    className="h-9 text-sm"
                    min="0"
                    disabled={!form.enforce_cash_limits}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">
                    Cash Limit / Party / Day (₹){" "}
                    <span className="text-muted-foreground font-normal">Sec 40A(3)</span>
                  </Label>
                  <Input
                    type="number"
                    name="max_cash_payment_limit"
                    value={form.max_cash_payment_limit}
                    onChange={handleChange}
                    placeholder="10000"
                    className="h-9 text-sm"
                    min="0"
                    disabled={!form.enforce_cash_limits}
                  />
                </div>
              </div>
            </div>

            {/* Contact */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Contact Details
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Phone</Label>
                  <Input
                    name="phone"
                    value={form.phone}
                    onChange={handleChange}
                    placeholder="+91 98765 43210"
                    className="h-9 text-sm"
                    maxLength={20}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Email</Label>
                  <Input
                    name="email"
                    type="email"
                    value={form.email}
                    onChange={handleChange}
                    placeholder="info@company.com"
                    className="h-9 text-sm"
                  />
                </div>
              </div>
            </div>

            {/* Address */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Registered Address
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex flex-col gap-1 md:col-span-3">
                  <Label className="text-xs">Street Address</Label>
                  <Textarea
                    name="address"
                    value={form.address}
                    onChange={handleChange}
                    placeholder="Registered office address"
                    className="text-sm resize-none"
                    rows={2}
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">City</Label>
                  <Input
                    name="city"
                    value={form.city}
                    onChange={handleChange}
                    placeholder="Kolkata"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Pincode</Label>
                  <Input
                    name="pincode"
                    value={form.pincode}
                    onChange={handleChange}
                    placeholder="700001"
                    className="h-9 text-sm"
                    maxLength={10}
                  />
                </div>
              </div>
            </div>

            {/* Branding — logos used on printed invoices */}
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground mb-3">
                Branding · Invoice Print
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <LogoField
                  label="BIS Hallmark Logo"
                  hint="Shown top-left on the tax invoice"
                  fileValue={form.bis_logo}
                  existingUrl={existingBisLogo}
                  onChange={handleFile("bis_logo")}
                  onClear={() => clearLogo("bis_logo")}
                />
                <LogoField
                  label="Company Logo"
                  hint="Shown top-right on the tax invoice"
                  fileValue={form.company_logo}
                  existingUrl={existingCompanyLogo}
                  onChange={handleFile("company_logo")}
                  onClear={() => clearLogo("company_logo")}
                />
              </div>
            </div>

            <div className="flex gap-3 pt-1">
              <Button
                type="submit"
                size="sm"
                disabled={submitting || !form.company_name.trim() || !!cinError || !form.cin.trim()}
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

      {/* Header */}
      {!showForm && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            The company is the top of the hierarchy: <span className="font-medium text-gray-700">Company → Branch → Retail</span>.
            PAN, TAN, phone, email and address from here are printed on all invoices.
          </p>
          <Button
            size="sm"
            className="bg-primary hover:bg-primary text-white"
            onClick={() => setShowForm(true)}
          >
            <Plus className="size-4 mr-1" />
            Add Company
          </Button>
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      ) : rows.length === 0 && !showForm ? (
        <div className="rounded-lg border border-dashed border-violet-200 bg-violet-50/40 p-10 text-center">
          <Building2 className="mx-auto size-8 text-violet-300 mb-2" />
          <p className="text-sm font-medium text-gray-600">No company set up yet</p>
          <p className="text-xs text-gray-400 mt-1">
            Create your company record to have its details appear on all printed invoices.
          </p>
          <Button
            size="sm"
            className="mt-4 bg-primary hover:bg-primary text-white"
            onClick={() => setShowForm(true)}
          >
            <Plus className="size-4 mr-1" />
            Set Up Company
          </Button>
        </div>
      ) : (
        <DataTable columns={columns} data={rows} />
      )}
    </div>
  );
}

/* Reusable logo upload field with preview, change, and clear actions. */
function LogoField({ label, hint, fileValue, existingUrl, onChange, onClear }) {
  // Local preview of a freshly chosen file (before upload).
  const [localPreview, setLocalPreview] = useState(null);
  useEffect(() => {
    if (fileValue instanceof File) {
      const url = URL.createObjectURL(fileValue);
      setLocalPreview(url);
      return () => URL.revokeObjectURL(url);
    }
    setLocalPreview(null);
  }, [fileValue]);

  const previewUrl = localPreview || existingUrl;
  const cleared = fileValue === "";

  return (
    <div className="flex flex-col gap-1.5">
      <Label className="text-xs">
        {label} <span className="text-muted-foreground font-normal">· {hint}</span>
      </Label>
      <div className="flex items-stretch gap-3 rounded-md border border-border p-2 bg-muted/20">
        <div className="flex items-center justify-center w-20 h-20 rounded border border-dashed border-border bg-background overflow-hidden flex-shrink-0">
          {previewUrl && !cleared ? (
            <img src={previewUrl} alt={label} className="max-w-full max-h-full object-contain" />
          ) : (
            <ImageIcon className="size-5 text-muted-foreground" />
          )}
        </div>
        <div className="flex flex-col justify-center gap-1.5 flex-1 min-w-0">
          <label className="inline-flex items-center gap-1.5 px-2 h-7 rounded bg-primary text-white text-xs font-medium cursor-pointer hover:opacity-90 w-fit">
            <Upload className="size-3.5" />
            {previewUrl && !cleared ? "Replace" : "Upload"}
            <input
              type="file"
              accept="image/png,image/jpeg,image/svg+xml,image/webp"
              onChange={onChange}
              className="hidden"
            />
          </label>
          {(previewUrl || fileValue instanceof File) && !cleared && (
            <button
              type="button"
              onClick={onClear}
              className="inline-flex items-center gap-1 text-[11px] text-rose-500 hover:text-rose-600 w-fit"
            >
              <X className="size-3" /> Remove
            </button>
          )}
          <p className="text-[10px] text-muted-foreground truncate">
            {fileValue instanceof File
              ? fileValue.name
              : cleared
                ? "Will be removed on save"
                : existingUrl
                  ? "Currently uploaded"
                  : "PNG, JPG, SVG, or WebP"}
          </p>
        </div>
      </div>
    </div>
  );
}
