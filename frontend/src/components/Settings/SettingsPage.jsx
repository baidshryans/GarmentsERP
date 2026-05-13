import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Calculator,
  Database,
  Download,
  FolderOpen,
  Loader2,
  Shield,
  ShieldCheck,
  RotateCcw,
  Settings,
  Eye,
  EyeOff,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import { resetErp, fetchRetails, updateRetail, fetchCompanies, updateCompany, backupDatabaseDownload, backupDatabaseToPath, fetchCommissionLedgerConfig, setCommissionLedger, getLedgerList, fetchSystemSettings, updateSystemSettings } from "@/services/apiService";
import { Percent, Palette, Check } from "lucide-react";
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { useTheme, THEMES } from "@/contexts/ThemeContext";

export default function SettingsPage() {
  const navigate = useNavigate();
  const { toast } = useToast();

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-6">
      {/* General */}
      <Section title="General" icon={<Settings className="size-4" />}>
        <SettingRow
          title="ERP Setup Wizard"
          description="Run the initial setup flow � seed account groups, create retails, configure TDS/TCS, upload masters."
        >
          <Button
            size="sm"
            variant="outline"
            onClick={() => navigate("/settings/setup")}
          >
            Open Setup Wizard
          </Button>
        </SettingRow>
      </Section>

      {/* Appearance */}
      <Section title="Appearance" icon={<Palette className="size-4" />}>
        <ThemeSelector />
      </Section>

      {/* Database */}
      <Section title="Database" icon={<Database className="size-4" />}>
        <BackupDatabaseCard />
      </Section>

      {/* File Storage */}
      <Section title="File Storage" icon={<FolderOpen className="size-4" />}>
        <AttachmentStorageCard />
        <BarcodeImageStorageCard />
      </Section>

      {/* Compliance */}
      <Section title="Compliance" icon={<ShieldCheck className="size-4" />}>
        <CashLimitCard />
      </Section>

      {/* Salesperson Commission */}
      <Section title="Salesperson Commission" icon={<Percent className="size-4" />}>
        <CommissionLedgerCard />
      </Section>

      {/* Bill Calculation */}
      <Section title="Bill Calculation" icon={<Calculator className="size-4" />}>
        <BillCalcSettingCard />
        <GstBillCard />
      </Section>

      {/* Search & Input */}
      <Section title="Search & Input" icon={<Search className="size-4" />}>
        <SpellCheckCard />
      </Section>

      {/* Advanced / Danger */}
      <Section
        title="Advanced"
        icon={<Shield className="size-4" />}
        danger
      >
        <ResetErpCard />
      </Section>
    </div>
  );
}

// ─── Layout helpers ──────────────────────────────────────────────────────────

function ThemeSelector() {
  const { theme, setTheme } = useTheme();
  return (
    <SettingRow
      title="Color Theme"
      description="Switch the primary accent color used across buttons, links, and highlights."
    >
      <div className="flex items-center gap-3">
        {Object.entries(THEMES).map(([key, t]) => {
          const active = theme === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => setTheme(key)}
              title={t.label}
              className={`relative size-9 rounded-full border-2 transition ${
                active ? "border-foreground scale-110" : "border-border hover:scale-105"
              }`}
              style={{ backgroundColor: t.swatch }}
            >
              {active && <Check className="size-4 text-white absolute inset-0 m-auto" />}
            </button>
          );
        })}
      </div>
    </SettingRow>
  );
}

function Section({ title, icon, children, danger }) {
  return (
    <div
      className={`rounded-xl border shadow-sm overflow-hidden ${
        danger ? "border-red-200" : "border-border"
      }`}
    >
      <div
        className={`flex items-center gap-2 px-5 py-3 text-sm font-semibold ${
          danger
            ? "bg-red-50 text-red-800 border-b border-red-200"
            : "bg-muted/50 text-foreground border-b border-border"
        }`}
      >
        {icon}
        {title}
      </div>
      <div className="divide-y divide-border">{children}</div>
    </div>
  );
}

function SettingRow({ title, description, children }) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

// ─── Compliance Limits (Sec 269ST + Sec 40A(3)) ──────────────────────────────

function CommissionLedgerCard() {
  const { toast } = useToast();
  const [ledgers, setLedgers]   = useState([]);
  const [current, setCurrent]   = useState(null);   // { commission_ldgr_id, commission_ldgr_name }
  const [selected, setSelected] = useState("");
  const [saving, setSaving]     = useState(false);

  useEffect(() => {
    Promise.all([fetchCommissionLedgerConfig(), getLedgerList()]).then(([cfgRes, ldgrRes]) => {
      if (cfgRes.success) {
        setCurrent(cfgRes.data);
        setSelected(cfgRes.data.commission_ldgr_id ? String(cfgRes.data.commission_ldgr_id) : "");
      }
      if (ldgrRes.success) {
        const list = Array.isArray(ldgrRes.data) ? ldgrRes.data : ldgrRes.data?.results || [];
        setLedgers(list.filter(l => l.ac_group_name === "Expenses"));
      }
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const id = selected && selected !== "__none__" ? Number(selected) : null;
    const res = await setCommissionLedger(id);
    if (res.success) {
      setCurrent(res.data);
      toast({ title: "Commission ledger saved" });
    } else {
      toast({ title: "Error", description: JSON.stringify(res.error), variant: "destructive" });
    }
    setSaving(false);
  };

  return (
    <div className="px-5 py-4 flex flex-col gap-3">
      <p className="text-sm font-medium">Commission Expense Ledger</p>
      <p className="text-xs text-muted-foreground">
        Select the expense ledger to debit when creating salesperson commission journal vouchers.
        Journal voucher creation is disabled until this is configured.
        {current?.commission_ldgr_name && (
          <span className="ml-1 font-medium text-foreground">
            Currently: <span className="text-primary">{current.commission_ldgr_name}</span>
          </span>
        )}
      </p>
      <div className="flex gap-2 items-center max-w-md">
        <Select value={selected} onValueChange={v => setSelected(v)}>
          <SelectTrigger>
            <SelectValue placeholder="� Select expense ledger �" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">� None (disable JV creation) �</SelectItem>
            {ledgers.map(l => (
              <SelectItem key={l.id} value={String(l.id)}>
                {l.ac_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Saving�" : "Save"}
        </Button>
      </div>
      {ledgers.length === 0 && (
        <p className="text-xs text-amber-600">
          No ledgers found in the Expenses account group. Create an expense ledger first.
        </p>
      )}
    </div>
  );
}

// ─── Bill Calculation Settings ───────────────────────────────────────────────

function BillCalcSettingCard() {
  const { toast } = useToast();
  const [enabled, setEnabled] = useState(false);
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    fetchSystemSettings().then((res) => {
      if (res.success) setEnabled(!!res.data.bill_total_auto_calc);
    });
  }, []);

  const handleToggle = async () => {
    const next = !enabled;
    setEnabled(next);
    setSaving(true);
    const res = await updateSystemSettings({ bill_total_auto_calc: next });
    setSaving(false);
    if (res.success) {
      toast({ title: next ? "Auto-Calculate enabled" : "Auto-Calculate disabled" });
    } else {
      setEnabled(!next);
      toast({ title: "Failed to save setting", variant: "destructive" });
    }
  };

  return (
    <SettingRow
      title="Auto-Calculate from Total"
      description="When enabled, you can enter the desired bill total in Sale & Sale Return and click Calculate to auto-derive Discount and GST."
    >
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        disabled={saving}
        onClick={handleToggle}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
          enabled ? "bg-green-600" : "bg-muted-foreground/30"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
            enabled ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </SettingRow>
  );
}

// ─── Spell Check & Fuzzy Search Setting ─────────────────────────────────────

function SpellCheckCard() {
  const { toast } = useToast();
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    fetchSystemSettings().then((res) => {
      if (res.success) setEnabled(!!res.data.spell_check_enabled);
    });
  }, []);

  const handleToggle = async () => {
    const next = !enabled;
    setEnabled(next);
    setSaving(true);
    const res = await updateSystemSettings({ spell_check_enabled: next });
    setSaving(false);
    if (res.success) {
      toast({ title: next ? "Spell Check & Fuzzy Search enabled" : "Spell Check & Fuzzy Search disabled" });
    } else {
      setEnabled(!next);
      toast({ title: "Failed to save setting", variant: "destructive" });
    }
  };

  return (
    <SettingRow
      title="Spell Check & Fuzzy Search"
      description="Enable browser spell checking on address / notes fields, and fuzzy matching in account group & picker searches."
    >
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        disabled={saving}
        onClick={handleToggle}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
          enabled ? "bg-green-600" : "bg-muted-foreground/30"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
            enabled ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </SettingRow>
  );
}

// ─── GST Bill Number Setting ─────────────────────────────────────────────────

function GstBillCard() {
  const { toast } = useToast();
  const [enabled, setEnabled] = useState(false);
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    fetchSystemSettings().then((res) => {
      if (res.success) setEnabled(!!res.data.enable_gst_bill);
    });
  }, []);

  const handleToggle = async () => {
    const next = !enabled;
    setEnabled(next);
    setSaving(true);
    const res = await updateSystemSettings({ enable_gst_bill: next });
    setSaving(false);
    if (res.success) {
      toast({ title: next ? "GST Bill Number enabled" : "GST Bill Number disabled" });
    } else {
      setEnabled(!next);
      toast({ title: "Failed to save setting", variant: "destructive" });
    }
  };

  return (
    <SettingRow
      title="GST Bill Number"
      description="When enabled, a separate GST bill number is auto-generated for each sales voucher in the format GST/&lt;retail code&gt;/&lt;FY&gt;/NNNNN (e.g. GST/R001/26-27/00001). The field becomes mandatory on the sales voucher."
    >
      <button
        type="button"
        role="switch"
        aria-checked={enabled}
        disabled={saving}
        onClick={handleToggle}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
          enabled ? "bg-green-600" : "bg-muted-foreground/30"
        }`}
      >
        <span
          className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
            enabled ? "translate-x-6" : "translate-x-1"
          }`}
        />
      </button>
    </SettingRow>
  );
}

function CashLimitCard() {
  const { toast } = useToast();
  const [companies, setCompanies] = useState([]);
  const [values, setValues] = useState({});
  const [saving, setSaving] = useState({});

  useEffect(() => {
    fetchCompanies().then((res) => {
      if (res.success) {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setCompanies(list);
        const v = {};
        list.forEach((c) => {
          v[`${c.id}_receipt`] = c.max_cash_receipt_limit ?? 199999;
          v[`${c.id}_payment`] = c.max_cash_payment_limit ?? 10000;
        });
        setValues(v);
      }
    });
  }, []);

  const handleSave = async (companyId, field) => {
    const key = `${companyId}_${field}`;
    setSaving((s) => ({ ...s, [key]: true }));
    const payload = field === "receipt"
      ? { max_cash_receipt_limit: Number(values[key]) }
      : { max_cash_payment_limit: Number(values[key]) };
    const res = await updateCompany(companyId, payload);
    if (res.success) {
      toast({ title: "Saved", description: "Limit updated successfully." });
    } else {
      toast({ title: "Error", description: "Failed to save.", variant: "destructive" });
    }
    setSaving((s) => ({ ...s, [key]: false }));
  };

  if (companies.length === 0) {
    return <div className="px-5 py-4 text-xs text-muted-foreground">No companies found.</div>;
  }

  return companies.map((c) => (
    <div key={c.id} className="divide-y divide-border">
      <LimitRow
        label={c.company_name}
        sublabel="Max cash receivable per customer per financial year"
        badge="Sec 269ST"
        fieldKey={`${c.id}_receipt`}
        values={values}
        saving={saving}
        onChange={(k, v) => setValues((prev) => ({ ...prev, [k]: v }))}
        onSave={() => handleSave(c.id, "receipt")}
      />
      <LimitRow
        label={null}
        sublabel="Max cash payable to a single party per day"
        badge="Sec 40A(3)"
        fieldKey={`${c.id}_payment`}
        values={values}
        saving={saving}
        onChange={(k, v) => setValues((prev) => ({ ...prev, [k]: v }))}
        onSave={() => handleSave(c.id, "payment")}
      />
    </div>
  ));
}

function LimitRow({ label, sublabel, badge, fieldKey, values, saving, onChange, onSave }) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-3.5">
      <div className="min-w-0 flex-1">
        {label && <p className="text-sm font-medium truncate mb-0.5">{label}</p>}
        <p className="text-xs text-muted-foreground">
          {sublabel}
          <span className="ml-1.5 px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono">{badge}</span>
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-sm text-muted-foreground font-medium">₹</span>
        <Input
          type="number"
          className="h-8 text-sm w-32"
          value={values[fieldKey] ?? ""}
          min={0}
          onChange={(e) => onChange(fieldKey, e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSave()}
        />
        <Button
          size="sm"
          className="h-8 bg-primary hover:bg-primary text-white"
          onClick={onSave}
          disabled={saving[fieldKey]}
        >
          {saving[fieldKey] ? <Loader2 className="size-3.5 animate-spin" /> : "Save"}
        </Button>
      </div>
    </div>
  );
}

// ─── Attachment Storage Path ─────────────────────────────────────────────────

function AttachmentStorageCard() {
  const { toast } = useToast();
  const [path, setPath]       = useState("");
  const [savedPath, setSavedPath] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    fetchSystemSettings().then((res) => {
      setLoading(false);
      if (res.success) {
        setSavedPath(res.data.attachment_storage_path || "");
        setPath(res.data.attachment_storage_path || "");
      } else {
        toast({ title: "Could not load storage settings", variant: "destructive" });
      }
    });
  }, []);

  const handleSave = async () => {
    if (!path.trim()) {
      toast({ title: "Path cannot be empty", variant: "destructive" });
      return;
    }
    setSaving(true);
    const res = await updateSystemSettings({ attachment_storage_path: path.trim() });
    setSaving(false);
    if (res.success) {
      setSavedPath(res.data.attachment_storage_path || path.trim());
      toast({ title: "Storage path saved", description: res.data.attachment_storage_path });
    } else {
      const msg = res.error?.attachment_storage_path?.[0] || res.error?.detail || JSON.stringify(res.error);
      toast({ title: "Failed to save", description: msg, variant: "destructive" });
    }
  };

  return (
    <div className="px-5 py-4 flex flex-col gap-3">
      <div>
        <p className="text-sm font-medium">Attachment Storage Location</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          Absolute path on the <strong>server</strong> where uploaded purchase attachments are stored.
          If left empty the default media folder is used. Changing this path does{" "}
          <strong>not</strong> move files that were already uploaded.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" /> Loading�
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2 max-w-xl">
            <FolderOpen className="size-4 text-muted-foreground shrink-0" />
            <Input
              className="h-8 text-sm flex-1 font-mono"
              placeholder={`e.g. C:\\ERP\\Attachments  or  /srv/erp/attachments`}
              value={path}
              onChange={(e) => setPath(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
            />
            <Button
              size="sm"
              className="bg-primary hover:bg-primary text-white shrink-0"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : "Save"}
            </Button>
          </div>

          {savedPath ? (
            <p className="text-xs text-green-700 font-mono break-all">
              ✓ Currently saving to: {savedPath}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground font-mono">
              Using default media folder (no custom path set).
            </p>
          )}

          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mt-1">
            ⚠ Make sure the server process has <strong>write permission</strong> to this directory.
            Files already uploaded will remain in their original location.
          </p>
        </>
      )}
    </div>
  );
}

// ─── Barcode Image Storage Path ──────────────────────────────────────────────

function BarcodeImageStorageCard() {
  const { toast } = useToast();
  const [path, setPath]       = useState("");
  const [savedPath, setSavedPath] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    fetchSystemSettings().then((res) => {
      setLoading(false);
      if (res.success) {
        setSavedPath(res.data.barcode_image_storage_path || "");
        setPath(res.data.barcode_image_storage_path || "");
      }
    });
  }, []);

  const handleSave = async () => {
    setSaving(true);
    const res = await updateSystemSettings({ barcode_image_storage_path: path.trim() });
    setSaving(false);
    if (res.success) {
      setSavedPath(res.data.barcode_image_storage_path || path.trim());
      toast({ title: "Barcode image path saved", description: res.data.barcode_image_storage_path || "Using default media folder" });
    } else {
      const msg = res.error?.barcode_image_storage_path?.[0] || res.error?.detail || JSON.stringify(res.error);
      toast({ title: "Failed to save", description: msg, variant: "destructive" });
    }
  };

  return (
    <div className="px-5 py-4 flex flex-col gap-3">
      <div>
        <p className="text-sm font-medium">Barcode Image Storage Location</p>
        <p className="text-xs text-muted-foreground mt-0.5">
          Absolute path on the <strong>server</strong> where barcode design images are stored.
          If left empty the default media folder is used. Changing this path does{" "}
          <strong>not</strong> move files that were already uploaded.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="size-3.5 animate-spin" /> Loading...
        </div>
      ) : (
        <>
          <div className="flex items-center gap-2 max-w-xl">
            <FolderOpen className="size-4 text-muted-foreground shrink-0" />
            <Input
              className="h-8 text-sm flex-1 font-mono"
              placeholder={`e.g. C:\\ERP\\BarcodeImages  or  /srv/erp/barcode-images`}
              value={path}
              onChange={(e) => setPath(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSave()}
            />
            <Button
              size="sm"
              className="bg-primary hover:bg-primary text-white shrink-0"
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : "Save"}
            </Button>
          </div>

          {savedPath ? (
            <p className="text-xs text-green-700 font-mono break-all">
              Currently saving to: {savedPath}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground font-mono">
              Using default media folder (no custom path set).
            </p>
          )}

          <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mt-1">
            Make sure the server process has <strong>write permission</strong> to this directory.
            Files already uploaded will remain in their original location.
          </p>
        </>
      )}
    </div>
  );
}

// ─── Database Backup ─────────────────────────────────────────────────────────

function BackupDatabaseCard() {
  const { toast } = useToast();
  const [path, setPath] = useState("");
  const [status, setStatus] = useState("idle"); // idle | busy
  const [lastSaved, setLastSaved] = useState("");

  const handleDownload = async () => {
    setStatus("busy");
    const res = await backupDatabaseDownload();
    setStatus("idle");
    if (res.success) {
      toast({ title: "Backup downloaded", description: "Check your browser's downloads folder." });
    } else {
      toast({ title: "Backup failed", description: res.error, variant: "destructive" });
    }
  };

  const handleSaveToPath = async () => {
    if (!path.trim()) {
      toast({ title: "Please enter a folder path", variant: "destructive" });
      return;
    }
    setStatus("busy");
    const res = await backupDatabaseToPath(path.trim());
    setStatus("idle");
    if (res.success) {
      setLastSaved(res.data.saved_to);
      toast({ title: "Backup saved", description: res.data.saved_to });
    } else {
      const msg = res.error?.detail || JSON.stringify(res.error);
      toast({ title: "Backup failed", description: msg, variant: "destructive" });
    }
  };

  return (
    <div className="px-5 py-4 flex flex-col gap-4">
      {/* Download to browser */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-medium">Download Backup</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Creates a point-in-time copy of the database and downloads it via your browser.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="shrink-0"
          onClick={handleDownload}
          disabled={status === "busy"}
        >
          {status === "busy" ? (
            <Loader2 className="size-3.5 mr-1.5 animate-spin" />
          ) : (
            <Download className="size-3.5 mr-1.5" />
          )}
          Download
        </Button>
      </div>

      {/* Save to a custom server-side folder */}
      <div className="border-t border-border pt-4 flex flex-col gap-2">
        <div>
          <p className="text-sm font-medium">Save to Folder</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Save the backup file directly to a folder on this computer (server path).
          </p>
        </div>
        <div className="flex items-center gap-2">
          <FolderOpen className="size-4 text-muted-foreground shrink-0" />
          <Input
            className="h-8 text-sm flex-1 font-mono"
            placeholder="e.g. C:\Backups\ERP\"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSaveToPath()}
          />
          <Button
            size="sm"
            className="bg-primary hover:bg-primary text-white shrink-0"
            onClick={handleSaveToPath}
            disabled={status === "busy"}
          >
            {status === "busy" ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              "Save"
            )}
          </Button>
        </div>
        {lastSaved && (
          <p className="text-xs text-green-700 font-mono break-all">
            ✓ Saved to: {lastSaved}
          </p>
        )}
      </div>
    </div>
  );
}

// ─── Reset ERP ───────────────────────────────────────────────────────────────

function ResetErpCard() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [phase, setPhase] = useState("idle"); // idle | confirm | processing | done
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");

  const handleReset = async () => {
    if (!password) {
      setError("Password is required.");
      return;
    }
    setError("");
    setPhase("processing");

    const res = await resetErp(password);
    if (res.success) {
      setPhase("done");
      toast({ title: "ERP has been reset", description: `${res.data.truncated_count} tables cleared.` });
    } else {
      setPhase("confirm");
      const msg = res.error?.error || res.error?.detail || "Reset failed.";
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    }
  };

  if (phase === "done") {
    return (
      <div className="px-5 py-6 flex flex-col items-center gap-3 text-center">
        <RotateCcw className="size-8 text-green-600" />
        <p className="text-sm font-medium">ERP has been reset successfully.</p>
        <p className="text-xs text-muted-foreground">
          All data has been cleared. User accounts are preserved.
        </p>
        <Button
          size="sm"
          className="bg-primary hover:bg-primary text-white mt-2"
          onClick={() => navigate("/settings/setup")}
        >
          Run Setup Wizard
        </Button>
      </div>
    );
  }

  return (
    <div className="px-5 py-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="size-5 text-red-500 mt-0.5 shrink-0" />
        <div className="flex-1">
          <p className="text-sm font-medium text-red-800">Reset ERP</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            This will permanently delete <strong>all transactional and master data</strong> � vouchers,
            ledgers, purchases, sales, inventory, account groups, and more. User accounts, roles, and
            permissions will be preserved. This action <strong>cannot be undone</strong>.
          </p>
        </div>
      </div>

      {phase === "idle" && (
        <div className="mt-4 flex justify-end">
          <Button
            size="sm"
            variant="destructive"
            onClick={() => setPhase("confirm")}
          >
            <AlertTriangle className="size-3.5 mr-1.5" />
            Reset ERP Data
          </Button>
        </div>
      )}

      {(phase === "confirm" || phase === "processing") && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-50/50 p-4">
          <p className="text-xs font-medium text-red-700 mb-3">
            Enter your password to confirm the reset:
          </p>
          <div className="flex items-end gap-3">
            <div className="flex flex-col gap-1 flex-1">
              <Label className="text-xs">Password</Label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  className="h-9 text-sm pr-9"
                  disabled={phase === "processing"}
                  onKeyDown={(e) => e.key === "Enter" && handleReset()}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2 top-2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>
            <Button
              size="sm"
              variant="destructive"
              onClick={handleReset}
              disabled={phase === "processing"}
            >
              {phase === "processing" ? (
                <Loader2 className="size-4 mr-1.5 animate-spin" />
              ) : (
                <RotateCcw className="size-3.5 mr-1.5" />
              )}
              {phase === "processing" ? "Resetting..." : "Confirm Reset"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => { setPhase("idle"); setPassword(""); setError(""); }}
              disabled={phase === "processing"}
            >
              Cancel
            </Button>
          </div>
          {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        </div>
      )}
    </div>
  );
}
