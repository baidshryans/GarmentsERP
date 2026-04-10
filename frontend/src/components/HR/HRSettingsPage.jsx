import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { fetchHRSettings, saveHRSettings, getLedgers } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const FIELDS = [
  { key: "salary_expense_ldgr",   label: "Salary Expense Ledger"   },
  { key: "employee_payable_ldgr", label: "Employee Payable Ledger" },
  { key: "pf_payable_ldgr",       label: "PF Payable Ledger"       },
  { key: "esi_payable_ldgr",      label: "ESI Payable Ledger"      },
  { key: "pt_payable_ldgr",       label: "Prof. Tax Payable Ledger" },
  { key: "tds_payable_ldgr",      label: "TDS Payable Ledger"      },
];

export default function HRSettingsPage() {
  const { toast } = useToast();
  const [ledgers, setLedgers] = useState([]);
  const [form, setForm]       = useState({});
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    getLedgers().then(r => r.success && setLedgers(Array.isArray(r.data) ? r.data : (r.data.results || [])));
    fetchHRSettings().then(r => r.success && setForm(r.data));
  }, []);

  function set(k, v) { setForm(f => ({ ...f, [k]: v || null })); }

  async function handleSave() {
    setSaving(true);
    const r = await saveHRSettings(form);
    setSaving(false);
    if (r.success) toast({ title: "HR settings saved." });
    else toast({ title: "Error", description: r.error?.detail || "Save failed.", variant: "destructive" });
  }

  return (
    <div className="p-4 max-w-xl space-y-6">
      <h2 className="text-lg font-semibold">HR Settings — Salary Ledger Mapping</h2>
      <p className="text-sm text-muted-foreground">
        Map each payroll component to an accounting ledger. These ledgers are used when a salary slip is approved to create the journal entry.
      </p>

      <div className="space-y-4">
        {FIELDS.map(({ key, label }) => (
          <div key={key} className="space-y-1">
            <Label className="text-xs">{label}</Label>
            <Select value={form[key] ? String(form[key]) : "__none__"} onValueChange={v => set(key, v === "__none__" ? "" : v)}>
              <SelectTrigger>
                <SelectValue placeholder="Select ledger…" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">— None —</SelectItem>
                {ledgers.map(l => (
                  <SelectItem key={l.id} value={String(l.id)}>{l.ac_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ))}
      </div>

      <Button onClick={handleSave} disabled={saving}>
        {saving ? "Saving…" : "Save Settings"}
      </Button>
    </div>
  );
}
