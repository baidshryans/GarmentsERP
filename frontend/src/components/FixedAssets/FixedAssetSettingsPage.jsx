import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { fetchFASettings, saveFASettings, getLedgers } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

export default function FixedAssetSettingsPage() {
  const { toast } = useToast();
  const [ledgers, setLedgers] = useState([]);
  const [form, setForm]       = useState({});
  const [saving, setSaving]   = useState(false);

  useEffect(() => {
    getLedgers().then(r => r.success && setLedgers(Array.isArray(r.data) ? r.data : (r.data.results || [])));
    fetchFASettings().then(r => r.success && setForm(r.data));
  }, []);

  function set(k, v) { setForm(f => ({ ...f, [k]: v || null })); }

  async function handleSave() {
    setSaving(true);
    const r = await saveFASettings(form);
    setSaving(false);
    if (r.success) toast({ title: "Fixed asset settings saved." });
    else toast({ title: "Error", description: r.error?.detail || "Save failed.", variant: "destructive" });
  }

  return (
    <div className="p-4 max-w-xl space-y-6">
      <h2 className="text-lg font-semibold">Fixed Asset Settings</h2>

      <div className="rounded-lg border p-4 space-y-1 bg-muted/30">
        <p className="text-sm font-medium">How these ledgers are used</p>
        <ul className="text-xs text-muted-foreground space-y-0.5 list-disc list-inside">
          <li><strong>Depreciation Expense:</strong> Debited when depreciation is approved (P&L — Indirect Expenses)</li>
          <li><strong>Accumulated Depreciation:</strong> Credited when depreciation is approved (Balance Sheet — contra-asset under Fixed Assets)</li>
          <li>Individual assets can override these defaults in the Asset Master.</li>
        </ul>
      </div>

      <div className="space-y-4">
        <div className="space-y-1">
          <Label className="text-xs">Default Depreciation Expense Ledger *</Label>
          <Select
            value={form.default_depreciation_expense_ldgr ? String(form.default_depreciation_expense_ldgr) : "__none__"}
            onValueChange={v => set("default_depreciation_expense_ldgr", v === "__none__" ? "" : v)}
          >
            <SelectTrigger><SelectValue placeholder="Select ledger…" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">— None —</SelectItem>
              {ledgers.map(l => <SelectItem key={l.id} value={String(l.id)}>{l.ac_name}</SelectItem>)}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">Suggested: create a ledger "Depreciation" under Indirect Expenses</p>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Default Accumulated Depreciation Ledger *</Label>
          <Select
            value={form.default_accum_depreciation_ldgr ? String(form.default_accum_depreciation_ldgr) : "__none__"}
            onValueChange={v => set("default_accum_depreciation_ldgr", v === "__none__" ? "" : v)}
          >
            <SelectTrigger><SelectValue placeholder="Select ledger…" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">— None —</SelectItem>
              {ledgers.map(l => <SelectItem key={l.id} value={String(l.id)}>{l.ac_name}</SelectItem>)}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">Suggested: create "Accumulated Depreciation" under Fixed Assets (contra)</p>
        </div>
      </div>

      <Button onClick={handleSave} disabled={saving}>
        {saving ? "Saving…" : "Save Settings"}
      </Button>
    </div>
  );
}
