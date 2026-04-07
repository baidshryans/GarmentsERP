import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  Circle,
  Loader2,
  ChevronRight,
  ChevronDown,
  FolderOpen,
  Folder,
  Upload,
  Database,
  XCircle,
  ArrowRight,
  ArrowLeft,
  RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import {
  getSetupStatus,
  seedAccountGroups,
  seedTdsTcs,
  getChartOfAccounts,
  createRetail,
  fetchStates,
  getFiscalYears,
  createFiscalYear,
  uploadHSNCSV,
  uploadItemGroupCSV,
  uploadItemCSV,
  uploadPacketGroupCSV,
  uploadPacketCSV,
  createCompany,
  fetchCompanies,
  createBranch,
  fetchBranches,
  createGstin,
  fetchGstins,
  setupRollback,
  seedStates,
} from "@/services/apiService";

// ═══════════════════════════════════════════════════════════════════════════════
// Step definitions
// ═══════════════════════════════════════════════════════════════════════════════
const STEPS = [
  { key: "company", label: "Company", description: "Create the parent company entity" },
  { key: "branch", label: "Branch", description: "Add at least one branch under the company" },
  { key: "gstin", label: "GSTIN", description: "Register the GSTIN that owns GST ledgers" },
  { key: "accounts", label: "Account Groups", description: "Seed the chart of accounts hierarchy" },
  { key: "retail", label: "Create Retail", description: "Set up your first retail location" },
  { key: "tds", label: "TDS & TCS Sections", description: "Seed tax deduction sections and ledgers" },
  { key: "fiscal", label: "Fiscal Year", description: "Create and activate a fiscal year" },
  { key: "masters", label: "Upload Masters", description: "Import HSN, items, packets via CSV" },
  { key: "review", label: "Review & Finish", description: "Verify setup and start using the ERP" },
];

// ═══════════════════════════════════════════════════════════════════════════════
// Mini components
// ═══════════════════════════════════════════════════════════════════════════════

function StepIndicator({ steps, current, completed }) {
  return (
    <nav className="flex gap-1 overflow-x-auto pb-2">
      {steps.map((s, i) => {
        const done = completed.has(s.key);
        const active = i === current;
        return (
          <div
            key={s.key}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
              active
                ? "bg-violet-100 text-violet-800 border border-violet-200"
                : done
                ? "bg-green-50 text-green-700"
                : "text-muted-foreground"
            }`}
          >
            {done ? (
              <CheckCircle2 className="size-3.5 text-green-600" />
            ) : active ? (
              <Circle className="size-3.5 text-violet-600" />
            ) : (
              <Circle className="size-3.5 text-gray-300" />
            )}
            {s.label}
          </div>
        );
      })}
    </nav>
  );
}

// ─── Account tree (read-only) ──────────────────────────────────────────────
function parseName(raw) {
  const idx = raw.indexOf(" - ");
  if (idx === -1) return { code: "", name: raw };
  return { code: raw.slice(0, idx), name: raw.slice(idx + 3) };
}

function collectExpandable(nodes, acc = new Set()) {
  nodes.forEach((n) => {
    if (n.children?.length) {
      acc.add(n.id);
      collectExpandable(n.children, acc);
    }
  });
  return acc;
}

function AccountTree({ tree }) {
  const [expanded, setExpanded] = useState(() => collectExpandable(tree));

  const toggle = (id) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const renderNode = (node, level) => {
    const has = node.children?.length > 0;
    const open = expanded.has(node.id);
    const { code, name } = parseName(node.name);
    return (
      <div key={node.id}>
        <div
          className={`flex items-center gap-2 py-1.5 px-2 rounded text-sm ${
            level === 0 ? "font-semibold bg-violet-50 border border-violet-100 mb-0.5" : "hover:bg-gray-50"
          }`}
          style={{ paddingLeft: `${level * 20 + 8}px` }}
        >
          <button
            onClick={() => has && toggle(node.id)}
            className={`shrink-0 w-4 h-4 flex items-center justify-center ${has ? "cursor-pointer text-violet-600" : "opacity-0"}`}
          >
            {has && (open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />)}
          </button>
          {has ? (
            open ? <FolderOpen className="size-3.5 text-violet-500" /> : <Folder className="size-3.5 text-violet-400" />
          ) : (
            <div className="size-3.5" />
          )}
          <span className="text-[11px] bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-500">{code}</span>
          <span className="truncate">{name}</span>
        </div>
        {has && open && node.children.map((c) => renderNode(c, level + 1))}
      </div>
    );
  };

  return <div className="max-h-[400px] overflow-y-auto border rounded-lg p-2 bg-white">{tree.map((n) => renderNode(n, 0))}</div>;
}

// ─── CSV upload card (reused from ImportDataPage pattern) ──────────────────
const CSV_TABLES = [
  { key: "hsn", label: "HSN Master", fn: uploadHSNCSV, hint: "hsn_no, description, hsn_type, hsn_per_cgst, hsn_per_igst" },
  { key: "item_group", label: "Item Group Master", fn: uploadItemGroupCSV, hint: "id, name, short_code" },
  { key: "item", label: "Item Master", fn: uploadItemCSV, hint: "id, short_code, item_name, item_type, uom, hsn_no" },
  { key: "packet_group", label: "Packet Group Master", fn: uploadPacketGroupCSV, hint: "packet_group_name" },
  { key: "packet", label: "Packet Master", fn: uploadPacketCSV, hint: "pckt_no, stone_id, rate_for_retail, rate_for_wholesale, solitare, customer, packet_group" },
];

function CsvCard({ label, fn, hint }) {
  const ref = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handle = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setResult(null);
    setError("");
    const res = await fn(file);
    if (res.success) setResult(res.data);
    else setError(typeof res.error === "string" ? res.error : JSON.stringify(res.error));
    setUploading(false);
    e.target.value = "";
  };

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{label}</p>
          <p className="text-[11px] text-muted-foreground">{hint}</p>
        </div>
        <button
          onClick={() => ref.current?.click()}
          disabled={uploading}
          className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md bg-violet-600 hover:bg-violet-700 text-white disabled:opacity-50 shrink-0"
        >
          {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
          {uploading ? "Uploading..." : "Upload CSV"}
        </button>
        <input ref={ref} type="file" accept=".csv" onChange={handle} className="hidden" />
      </div>
      {result && (
        <div className="mt-2 text-xs flex gap-3">
          <span className="text-green-700">Created: <strong>{result.created}</strong></span>
          <span className="text-violet-700">Updated: <strong>{result.updated}</strong></span>
          {result.errors?.length > 0 && <span className="text-red-600">Errors: <strong>{result.errors.length}</strong></span>}
        </div>
      )}
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// Main Wizard
// ═══════════════════════════════════════════════════════════════════════════════

export default function SetupWizard() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [current, setCurrent] = useState(0);
  const [completed, setCompleted] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  // Step-specific state
  const [setupStatus, setSetupStatus] = useState(null);
  const [accountTree, setAccountTree] = useState([]);
  const [states, setStates] = useState([]);
  const [retailForm, setRetailForm] = useState({ retail_code: "", retail_name: "", email: "", phone: "", bill_series: "", address_line1: "", city: "", pincode: "", state: "", branch: "", gstin_master: "" });
  const [fyForm, setFyForm] = useState({ fy_code: "", fy_start: "", fy_end: "" });
  const [companyForm, setCompanyForm] = useState({ company_name: "", pan: "", phone: "", email: "", address: "", city: "", state: "", pincode: "" });
  const [branchForm, setBranchForm] = useState({ branch_name: "", branch_code: "", state: "", description: "", company: "" });
  const [gstinForm, setGstinForm] = useState({ gstin: "", legal_name: "", branch: "", state: "" });
  const [companies, setCompanies] = useState([]);
  const [branches, setBranches] = useState([]);
  const [gstins, setGstins] = useState([]);

  // Wipe data if the user closes the tab/browser before clicking Finish
  useEffect(() => {
    const handler = () => {
      if (sessionStorage.getItem("erpSetupComplete") === "true") return;
      try {
        const baseUrl = sessionStorage.getItem("baseUrl") || "";
        const token = localStorage.getItem("Token");
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${baseUrl}/userauth/api/setup/rollback/`, false);
        if (token) xhr.setRequestHeader("Authorization", `Token ${token}`);
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(JSON.stringify({}));
      } catch (e) { /* swallow */ }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  // Load status on mount — also auto-seed states if missing
  useEffect(() => {
    (async () => {
      let res = await getSetupStatus();
      // Auto-seed Indian states silently on first run
      if (res.success && !res.data.states_seeded) {
        await seedStates();
        res = await getSetupStatus();
      }
      if (res.success) {
        setSetupStatus(res.data);
        const done = new Set();
        if (res.data.company_created) done.add("company");
        if (res.data.branch_created) done.add("branch");
        if (res.data.gstin_created) done.add("gstin");
        if (res.data.account_groups_seeded) done.add("accounts");
        if (res.data.retails_created) done.add("retail");
        if (res.data.tds_tcs_seeded) done.add("tds");
        if (res.data.fiscal_years_created) done.add("fiscal");
        if (res.data.masters_uploaded) done.add("masters");
        setCompleted(done);
        // Jump to first incomplete step
        const idx = STEPS.findIndex((s) => !done.has(s.key));
        if (idx >= 0) setCurrent(idx);
      }
      setLoading(false);
    })();
  }, []);

  const markDone = (key) => setCompleted((prev) => new Set(prev).add(key));
  const next = () => setCurrent((c) => Math.min(c + 1, STEPS.length - 1));
  const prev = () => setCurrent((c) => Math.max(c - 1, 0));

  const refreshStatus = async () => {
    const res = await getSetupStatus();
    if (res.success) setSetupStatus(res.data);
  };

  // ─── Step: Seed Account Groups ──────────────────────────────────────────
  const handleSeedAccounts = async () => {
    setBusy(true);
    const res = await seedAccountGroups();
    if (res.success) {
      toast({ title: "Account groups seeded successfully" });
      markDone("accounts");
      // Load tree for display
      const tree = await getChartOfAccounts();
      if (tree.success) setAccountTree(Array.isArray(tree.data) ? tree.data : []);
      await refreshStatus();
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
    setBusy(false);
  };

  const loadTree = async () => {
    const tree = await getChartOfAccounts();
    if (tree.success) setAccountTree(Array.isArray(tree.data) ? tree.data : []);
  };

  useEffect(() => {
    const stepKey = STEPS[current]?.key;
    if (states.length === 0 && ["company", "branch", "gstin", "retail"].includes(stepKey)) {
      fetchStates().then((r) => { if (r.success) setStates(r.data || []); });
    }
    if (stepKey === "branch") {
      fetchCompanies().then((r) => {
        if (r.success) {
          const list = Array.isArray(r.data) ? r.data : (r.data?.results || []);
          setCompanies(list);
          if (list.length && !branchForm.company) {
            setBranchForm((f) => ({ ...f, company: list[0].id }));
          }
        }
      });
    }
    if (stepKey === "gstin") {
      fetchBranches().then((r) => {
        if (r.success) {
          const list = Array.isArray(r.data) ? r.data : (r.data?.results || []);
          setBranches(list);
          if (list.length && !gstinForm.branch) {
            setGstinForm((f) => ({ ...f, branch: list[0].id }));
          }
        }
      });
    }
    if (stepKey === "retail") {
      fetchBranches().then((r) => {
        if (r.success) {
          const list = Array.isArray(r.data) ? r.data : (r.data?.results || []);
          setBranches(list);
          if (list.length && !retailForm.branch) {
            setRetailForm((f) => ({ ...f, branch: list[0].id }));
          }
        }
      });
      fetchGstins().then((r) => {
        if (r.success) {
          const list = Array.isArray(r.data) ? r.data : (r.data?.results || []);
          setGstins(list);
          if (list.length && !retailForm.gstin_master) {
            setRetailForm((f) => ({ ...f, gstin_master: list[0].id }));
          }
        }
      });
    }
    if (stepKey === "accounts" && completed.has("accounts") && accountTree.length === 0) loadTree();
  }, [current]);

  // ─── Step: Create Company ───────────────────────────────────────────────
  const handleCreateCompany = async () => {
    if (!companyForm.company_name.trim()) {
      toast({ title: "Company name is required", variant: "destructive" });
      return;
    }
    setBusy(true);
    const res = await createCompany(companyForm);
    if (res.success) {
      toast({ title: `Company "${companyForm.company_name}" created with operational ledgers` });
      markDone("company");
      await refreshStatus();
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setBusy(false);
  };

  // ─── Step: Create Branch ────────────────────────────────────────────────
  const handleCreateBranch = async () => {
    if (!branchForm.branch_name.trim() || !branchForm.branch_code.trim() || !branchForm.state || !branchForm.company) {
      toast({ title: "Branch name, code, company and state are required", variant: "destructive" });
      return;
    }
    setBusy(true);
    const res = await createBranch(branchForm);
    if (res.success) {
      toast({ title: `Branch "${branchForm.branch_code}" created` });
      markDone("branch");
      await refreshStatus();
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setBusy(false);
  };

  // ─── Step: Create GSTIN ─────────────────────────────────────────────────
  const handleCreateGstin = async () => {
    if (!gstinForm.gstin.trim() || !gstinForm.branch || !gstinForm.state) {
      toast({ title: "GSTIN, branch and state are required", variant: "destructive" });
      return;
    }
    setBusy(true);
    const res = await createGstin(gstinForm);
    if (res.success) {
      toast({ title: `GSTIN "${gstinForm.gstin}" created with 6 GST register ledgers` });
      markDone("gstin");
      await refreshStatus();
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setBusy(false);
  };

  // ─── Step: Create Retail ────────────────────────────────────────────────
  const handleCreateRetail = async () => {
    const required = ["retail_code", "retail_name", "email", "phone", "bill_series", "address_line1", "state", "branch", "gstin_master"];
    const missing = required.filter((k) => !String(retailForm[k] || "").trim());
    if (missing.length) {
      toast({ title: `Missing required fields: ${missing.join(", ")}`, variant: "destructive" });
      return;
    }
    setBusy(true);
    const res = await createRetail(retailForm);
    if (res.success) {
      toast({ title: `Retail "${retailForm.retail_code}" created with cash ledger` });
      markDone("retail");
      setRetailForm({ retail_code: "", retail_name: "", email: "", phone: "", bill_series: "", address_line1: "", city: "", pincode: "", state: "", branch: "", gstin_master: "" });
      await refreshStatus();
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setBusy(false);
  };

  // ─── Step: Seed TDS & TCS ──────────────────────────────────────────────
  const handleSeedTds = async () => {
    setBusy(true);
    const res = await seedTdsTcs();
    if (res.success) {
      toast({ title: "TDS & TCS sections and ledgers seeded" });
      markDone("tds");
      await refreshStatus();
    } else {
      toast({ title: "Error", description: String(res.error), variant: "destructive" });
    }
    setBusy(false);
  };

  // ─── Step: Fiscal Year ─────────────────────────────────────────────────
  const handleCreateFY = async () => {
    if (!fyForm.fy_code.trim() || !fyForm.fy_start || !fyForm.fy_end) {
      toast({ title: "All fiscal year fields are required", variant: "destructive" });
      return;
    }
    setBusy(true);
    const res = await createFiscalYear(fyForm);
    if (res.success) {
      toast({ title: `Fiscal year "${fyForm.fy_code}" created` });
      markDone("fiscal");
      await refreshStatus();
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : String(res.error);
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setBusy(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="size-6 animate-spin text-violet-600" />
      </div>
    );
  }

  const step = STEPS[current];

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-5">
      {/* Step indicator */}
      <StepIndicator steps={STEPS} current={current} completed={completed} />

      {/* Step content card */}
      <div className="rounded-xl border border-border bg-card p-6 shadow-sm min-h-[400px] flex flex-col">
        <div className="mb-5">
          <h2 className="text-lg font-semibold">{step.label}</h2>
          <p className="text-sm text-muted-foreground">{step.description}</p>
        </div>

        <div className="flex-1">
          {/* ── Step: Company ───────────────────────────────────── */}
          {step.key === "company" && (
            <div className="flex flex-col gap-4">
              {completed.has("company") ? (
                <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                  <CheckCircle2 className="size-4" />
                  Company created — 7 operational ledgers (Discount, Round Off, Hallmark, Making Charges, etc.) auto-generated.
                </div>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    Create your parent company. On save, 7 company-wide operational ledgers
                    (Discount, Round Off, Hallmark Charge, Making Receive, Gold Conversion,
                    Carriage Inward, Making Charge Purchase) are auto-created.
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div className="flex flex-col gap-1 md:col-span-2">
                      <Label className="text-xs">Company Name *</Label>
                      <Input value={companyForm.company_name} onChange={(e) => setCompanyForm((f) => ({ ...f, company_name: e.target.value }))} className="h-9 text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">PAN</Label>
                      <Input value={companyForm.pan} onChange={(e) => setCompanyForm((f) => ({ ...f, pan: e.target.value.toUpperCase() }))} className="h-9 text-sm uppercase" maxLength={10} />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Phone</Label>
                      <Input value={companyForm.phone} onChange={(e) => setCompanyForm((f) => ({ ...f, phone: e.target.value }))} className="h-9 text-sm" />
                    </div>
                    <div className="flex flex-col gap-1 md:col-span-2">
                      <Label className="text-xs">Email</Label>
                      <Input type="email" value={companyForm.email} onChange={(e) => setCompanyForm((f) => ({ ...f, email: e.target.value }))} className="h-9 text-sm" />
                    </div>
                    <div className="flex flex-col gap-1 md:col-span-3">
                      <Label className="text-xs">Address</Label>
                      <Input value={companyForm.address} onChange={(e) => setCompanyForm((f) => ({ ...f, address: e.target.value }))} className="h-9 text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">City</Label>
                      <Input value={companyForm.city} onChange={(e) => setCompanyForm((f) => ({ ...f, city: e.target.value }))} className="h-9 text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">State</Label>
                      <select value={companyForm.state} onChange={(e) => setCompanyForm((f) => ({ ...f, state: e.target.value }))} className="h-9 text-sm rounded-md border border-input bg-background px-3">
                        <option value="">Select state</option>
                        {states.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                      </select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Pincode</Label>
                      <Input value={companyForm.pincode} onChange={(e) => setCompanyForm((f) => ({ ...f, pincode: e.target.value }))} className="h-9 text-sm" maxLength={6} />
                    </div>
                  </div>
                  <Button onClick={handleCreateCompany} disabled={busy} className="self-start bg-violet-700 hover:bg-violet-800 text-white">
                    {busy ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : null}
                    Create Company
                  </Button>
                </>
              )}
            </div>
          )}

          {/* ── Step: Branch ────────────────────────────────────── */}
          {step.key === "branch" && (
            <div className="flex flex-col gap-4">
              {completed.has("branch") ? (
                <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                  <CheckCircle2 className="size-4" />
                  Branch created.
                </div>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    Branches are organisational groupings under the company. GSTINs and retails attach to branches.
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div className="flex flex-col gap-1 md:col-span-2">
                      <Label className="text-xs">Branch Name *</Label>
                      <Input value={branchForm.branch_name} onChange={(e) => setBranchForm((f) => ({ ...f, branch_name: e.target.value }))} className="h-9 text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Branch Code *</Label>
                      <Input value={branchForm.branch_code} onChange={(e) => setBranchForm((f) => ({ ...f, branch_code: e.target.value.toUpperCase() }))} className="h-9 text-sm uppercase" maxLength={20} />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Company *</Label>
                      <select value={branchForm.company} onChange={(e) => setBranchForm((f) => ({ ...f, company: e.target.value }))} className="h-9 text-sm rounded-md border border-input bg-background px-3">
                        <option value="">Select company</option>
                        {companies.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
                      </select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">State *</Label>
                      <select value={branchForm.state} onChange={(e) => setBranchForm((f) => ({ ...f, state: e.target.value }))} className="h-9 text-sm rounded-md border border-input bg-background px-3">
                        <option value="">Select state</option>
                        {states.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                      </select>
                    </div>
                    <div className="flex flex-col gap-1 md:col-span-3">
                      <Label className="text-xs">Description</Label>
                      <Input value={branchForm.description} onChange={(e) => setBranchForm((f) => ({ ...f, description: e.target.value }))} className="h-9 text-sm" />
                    </div>
                  </div>
                  <Button onClick={handleCreateBranch} disabled={busy || !completed.has("company")} className="self-start bg-violet-700 hover:bg-violet-800 text-white">
                    {busy ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : null}
                    Create Branch
                  </Button>
                  {!completed.has("company") && (
                    <div className="flex items-center gap-2 text-amber-600 text-xs bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
                      <XCircle className="size-3.5" />
                      Create the company in the previous step first.
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Step: GSTIN ─────────────────────────────────────── */}
          {step.key === "gstin" && (
            <div className="flex flex-col gap-4">
              {completed.has("gstin") ? (
                <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                  <CheckCircle2 className="size-4" />
                  GSTIN created — 6 GST register ledgers (Input/Output CGST, SGST, IGST) auto-generated.
                </div>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    Register the GSTIN for this branch. On save, 6 GST register ledgers
                    (Input/Output CGST, SGST, IGST) are auto-created and owned by this GSTIN.
                  </p>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">GSTIN *</Label>
                      <Input value={gstinForm.gstin} onChange={(e) => setGstinForm((f) => ({ ...f, gstin: e.target.value.toUpperCase() }))} className="h-9 text-sm uppercase" maxLength={15} />
                    </div>
                    <div className="flex flex-col gap-1 md:col-span-2">
                      <Label className="text-xs">Legal Name</Label>
                      <Input value={gstinForm.legal_name} onChange={(e) => setGstinForm((f) => ({ ...f, legal_name: e.target.value }))} className="h-9 text-sm" />
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">Branch *</Label>
                      <select value={gstinForm.branch} onChange={(e) => setGstinForm((f) => ({ ...f, branch: e.target.value }))} className="h-9 text-sm rounded-md border border-input bg-background px-3">
                        <option value="">Select branch</option>
                        {branches.map((b) => <option key={b.id} value={b.id}>{b.branch_name} ({b.branch_code})</option>)}
                      </select>
                    </div>
                    <div className="flex flex-col gap-1">
                      <Label className="text-xs">State *</Label>
                      <select value={gstinForm.state} onChange={(e) => setGstinForm((f) => ({ ...f, state: e.target.value }))} className="h-9 text-sm rounded-md border border-input bg-background px-3">
                        <option value="">Select state</option>
                        {states.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                      </select>
                    </div>
                  </div>
                  <Button onClick={handleCreateGstin} disabled={busy || !completed.has("branch")} className="self-start bg-violet-700 hover:bg-violet-800 text-white">
                    {busy ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : null}
                    Create GSTIN
                  </Button>
                  {!completed.has("branch") && (
                    <div className="flex items-center gap-2 text-amber-600 text-xs bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
                      <XCircle className="size-3.5" />
                      Create a branch in the previous step first.
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* ── Step 1: Account Groups ──────────────────────────── */}
          {step.key === "accounts" && (
            <div className="flex flex-col gap-4">
              {completed.has("accounts") ? (
                <>
                  <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                    <CheckCircle2 className="size-4" />
                    {setupStatus?.account_groups_count} account groups are configured
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Review the chart of accounts tree below. You can edit groups later from
                    Accounting &rarr; Account Tree. System groups (Cash, TDS Payable, etc.) are
                    auto-assigned when retails and TDS sections are created.
                  </p>
                  {accountTree.length > 0 && <AccountTree tree={accountTree} />}
                  <Button variant="outline" size="sm" onClick={handleSeedAccounts} disabled={busy} className="self-start">
                    <RotateCcw className="size-3.5 mr-1.5" /> Re-run Seed
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    This will create the standard Indian chart of account groups: Assets, Liabilities,
                    Capital, Income, and Expenses with all relevant sub-groups. This must be done before
                    creating retails so that system ledgers (Cash, TDS Payable, etc.) can be assigned to
                    the correct account groups.
                  </p>
                  <Button onClick={handleSeedAccounts} disabled={busy} className="self-start bg-violet-700 hover:bg-violet-800 text-white">
                    {busy ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : <Database className="size-4 mr-1.5" />}
                    Seed Account Groups
                  </Button>
                </>
              )}
            </div>
          )}

          {/* ── Step 2: Create Retail ──────────────────────────── */}
          {step.key === "retail" && (
            <div className="flex flex-col gap-4">
              {completed.has("retail") && (
                <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                  <CheckCircle2 className="size-4" />
                  {setupStatus?.retails_count} retail(s) created
                </div>
              )}
              <p className="text-sm text-muted-foreground">
                Create your retail location. A Cash ledger will be auto-created and assigned to the
                Cash-in-Hand account group.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Retail Code *</Label>
                  <Input
                    value={retailForm.retail_code}
                    onChange={(e) => setRetailForm((f) => ({ ...f, retail_code: e.target.value.toUpperCase() }))}
                    placeholder="e.g. JI01"
                    className="h-9 text-sm uppercase"
                    maxLength={10}
                  />
                </div>
                <div className="flex flex-col gap-1 md:col-span-2">
                  <Label className="text-xs">Retail Name *</Label>
                  <Input
                    value={retailForm.retail_name}
                    onChange={(e) => setRetailForm((f) => ({ ...f, retail_name: e.target.value }))}
                    placeholder="e.g. Jewel India - Karol Bagh"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Email *</Label>
                  <Input type="email" value={retailForm.email} onChange={(e) => setRetailForm((f) => ({ ...f, email: e.target.value }))} className="h-9 text-sm" />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Phone *</Label>
                  <Input value={retailForm.phone} onChange={(e) => setRetailForm((f) => ({ ...f, phone: e.target.value }))} className="h-9 text-sm" />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Bill Series *</Label>
                  <Input value={retailForm.bill_series} onChange={(e) => setRetailForm((f) => ({ ...f, bill_series: e.target.value.toUpperCase() }))} className="h-9 text-sm uppercase" maxLength={20} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Branch *</Label>
                  <select value={retailForm.branch} onChange={(e) => setRetailForm((f) => ({ ...f, branch: e.target.value }))} className="h-9 text-sm rounded-md border border-input bg-background px-3">
                    <option value="">Select branch</option>
                    {branches.map((b) => <option key={b.id} value={b.id}>{b.branch_name} ({b.branch_code})</option>)}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">GSTIN *</Label>
                  <select value={retailForm.gstin_master} onChange={(e) => setRetailForm((f) => ({ ...f, gstin_master: e.target.value }))} className="h-9 text-sm rounded-md border border-input bg-background px-3">
                    <option value="">Select GSTIN</option>
                    {gstins.map((g) => <option key={g.id} value={g.id}>{g.gstin}</option>)}
                  </select>
                </div>
                <div className="flex flex-col gap-1 md:col-span-3">
                  <Label className="text-xs">Address Line 1 *</Label>
                  <Input value={retailForm.address_line1} onChange={(e) => setRetailForm((f) => ({ ...f, address_line1: e.target.value }))} className="h-9 text-sm" />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">City</Label>
                  <Input value={retailForm.city} onChange={(e) => setRetailForm((f) => ({ ...f, city: e.target.value }))} className="h-9 text-sm" />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Pincode</Label>
                  <Input value={retailForm.pincode} onChange={(e) => setRetailForm((f) => ({ ...f, pincode: e.target.value }))} className="h-9 text-sm" maxLength={6} />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">State</Label>
                  <select
                    value={retailForm.state}
                    onChange={(e) => setRetailForm((f) => ({ ...f, state: e.target.value }))}
                    className="h-9 text-sm rounded-md border border-input bg-background px-3"
                  >
                    <option value="">Select state</option>
                    {states.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <Button onClick={handleCreateRetail} disabled={busy} className="self-start bg-violet-700 hover:bg-violet-800 text-white">
                {busy ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : null}
                Create Retail
              </Button>
            </div>
          )}

          {/* ── Step 3: TDS & TCS ─────────────────────────────── */}
          {step.key === "tds" && (
            <div className="flex flex-col gap-4">
              {completed.has("tds") ? (
                <>
                  <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                    <CheckCircle2 className="size-4" />
                    {setupStatus?.tds_count} TDS and {setupStatus?.tcs_count} TCS sections configured
                  </div>
                  <p className="text-sm text-muted-foreground">
                    TDS Payable and TCS Payable ledgers have been created for each retail and linked to
                    their respective sections. You can manage them later from Masters &rarr; TDS/TCS Sections.
                  </p>
                  <Button variant="outline" size="sm" onClick={handleSeedTds} disabled={busy} className="self-start">
                    <RotateCcw className="size-3.5 mr-1.5" /> Re-run Seed
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-sm text-muted-foreground">
                    This will create TDS sections (194C, 194H, 194I, 194J, 194Q) and TCS section
                    (206C1H) along with their respective payable ledgers for each retail. Retails must
                    be created first.
                  </p>
                  {!completed.has("retail") && (
                    <div className="flex items-center gap-2 text-amber-600 text-xs bg-amber-50 px-3 py-2 rounded-lg border border-amber-200">
                      <XCircle className="size-3.5" />
                      Create at least one retail in the previous step first.
                    </div>
                  )}
                  <Button
                    onClick={handleSeedTds}
                    disabled={busy || !completed.has("retail")}
                    className="self-start bg-violet-700 hover:bg-violet-800 text-white"
                  >
                    {busy ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : <Database className="size-4 mr-1.5" />}
                    Seed TDS & TCS
                  </Button>
                </>
              )}
            </div>
          )}

          {/* ── Step 4: Fiscal Year ───────────────────────────── */}
          {step.key === "fiscal" && (
            <div className="flex flex-col gap-4">
              {completed.has("fiscal") && (
                <div className="flex items-center gap-2 text-green-700 text-sm font-medium">
                  <CheckCircle2 className="size-4" />
                  Fiscal year configured
                </div>
              )}
              <p className="text-sm text-muted-foreground">
                Create your current financial year. In India, the FY typically runs from April 1 to March 31.
                You can manage fiscal years later from Masters &rarr; Fiscal Years.
              </p>
              <div className="grid grid-cols-3 gap-3">
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">FY Code *</Label>
                  <Input
                    value={fyForm.fy_code}
                    onChange={(e) => setFyForm((f) => ({ ...f, fy_code: e.target.value }))}
                    placeholder="e.g. 2025-26"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">Start Date *</Label>
                  <Input
                    type="date"
                    value={fyForm.fy_start}
                    onChange={(e) => setFyForm((f) => ({ ...f, fy_start: e.target.value }))}
                    className="h-9 text-sm"
                  />
                </div>
                <div className="flex flex-col gap-1">
                  <Label className="text-xs">End Date *</Label>
                  <Input
                    type="date"
                    value={fyForm.fy_end}
                    onChange={(e) => setFyForm((f) => ({ ...f, fy_end: e.target.value }))}
                    className="h-9 text-sm"
                  />
                </div>
              </div>
              <Button onClick={handleCreateFY} disabled={busy} className="self-start bg-violet-700 hover:bg-violet-800 text-white">
                {busy ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : null}
                Create Fiscal Year
              </Button>
            </div>
          )}

          {/* ── Step 5: Upload Masters (CSV) ──────────────────── */}
          {step.key === "masters" && (
            <div className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                Upload CSV files for your master data. This step is optional — you can also do this later
                from Import Master Data. Upload in order: HSN &rarr; Item Group &rarr; Item &rarr; Packet
                Group &rarr; Packet.
              </p>
              {CSV_TABLES.map((t) => (
                <CsvCard key={t.key} label={t.label} fn={t.fn} hint={t.hint} />
              ))}
              <Button variant="outline" size="sm" onClick={() => { markDone("masters"); }} className="self-start">
                Skip this step
              </Button>
            </div>
          )}

          {/* ── Step 6: Review & Finish ───────────────────────── */}
          {step.key === "review" && (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Review the setup status below. You can go back to any step to complete or re-run it.
              </p>
              <div className="rounded-lg border border-border divide-y">
                {STEPS.filter((s) => s.key !== "review").map((s) => (
                  <div key={s.key} className="flex items-center justify-between px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      {completed.has(s.key) ? (
                        <CheckCircle2 className="size-4 text-green-600" />
                      ) : (
                        <Circle className="size-4 text-gray-300" />
                      )}
                      <span className="text-sm font-medium">{s.label}</span>
                    </div>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                      completed.has(s.key) ? "bg-green-50 text-green-700" : "bg-gray-100 text-gray-500"
                    }`}>
                      {completed.has(s.key) ? "Done" : "Pending"}
                    </span>
                  </div>
                ))}
              </div>
              <Button
                onClick={() => {
                  sessionStorage.setItem("erpSetupComplete", "true");
                  navigate("/");
                }}
                disabled={!setupStatus?.is_setup_complete}
                className="self-start bg-violet-700 hover:bg-violet-800 text-white disabled:opacity-50"
              >
                {setupStatus?.is_setup_complete ? "Go to Dashboard" : "Complete all required steps first"}
                <ArrowRight className="size-4 ml-1.5" />
              </Button>
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-border">
          <Button variant="outline" size="sm" onClick={prev} disabled={current === 0}>
            <ArrowLeft className="size-3.5 mr-1" /> Previous
          </Button>
          <Button variant="outline" size="sm" onClick={next} disabled={current === STEPS.length - 1}>
            Next <ArrowRight className="size-3.5 ml-1" />
          </Button>
        </div>
      </div>
    </div>
  );
}
