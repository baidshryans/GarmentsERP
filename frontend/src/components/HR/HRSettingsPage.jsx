import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Lock } from "lucide-react";
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
  const [locked, setLocked]   = useState(false);
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    getLedgers().then(r => r.success && setLedgers(Array.isArray(r.data) ? r.data : (r.data.results || [])));
    fetchHRSettings().then(r => {
      if (r.success) {
        setForm(r.data);
        setLocked(!!r.data.locked);
      }
    });
  }, []);

  function set(k, v) { setForm(f => ({ ...f, [k]: v || null })); }

  async function handleSave() {
    setSaving(true);
    const r = await saveHRSettings(form);
    setSaving(false);
    if (r.success) toast({ title: "HR settings saved." });
    else toast({ title: "Error", description: r.error?.detail || "Save failed.", variant: "destructive" });
  }

  const getLedgerName = (id) => {
    const l = ledgers.find(l => String(l.id) === String(id));
    return l ? l.ac_name : id ? `Ledger #${id}` : "—";
  };

  return (
    <TooltipProvider>
      <div className="p-4 max-w-xl space-y-6">
        <h2 className="text-lg font-semibold">HR Settings — Salary Ledger Mapping</h2>
        <p className="text-sm text-muted-foreground">
          Map each payroll component to an accounting ledger. These ledgers are used when a salary slip is approved to create the journal entry.
        </p>

        {locked && (
          <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            <Lock className="h-4 w-4 shrink-0" />
            Ledger mappings are locked because salary slips have been approved using these ledgers.
          </div>
        )}

        <div className="space-y-4">
          {FIELDS.map(({ key, label }) => (
            <div key={key} className="space-y-1">
              <Label className="text-xs flex items-center gap-1">
                {label}
                {locked && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Lock className="h-3 w-3 text-amber-500 cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent>
                      Cannot change — salary slips have been approved using this ledger.
                    </TooltipContent>
                  </Tooltip>
                )}
              </Label>
              {locked ? (
                <div className="flex h-9 items-center rounded-md border bg-muted px-3 text-sm text-muted-foreground">
                  {getLedgerName(form[key])}
                </div>
              ) : (
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
              )}
            </div>
          ))}
        </div>

        {!locked && (
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save Settings"}
          </Button>
        )}
      </div>
    </TooltipProvider>
  );
}
