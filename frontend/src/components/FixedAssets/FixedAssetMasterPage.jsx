import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Plus, Pencil, Info } from "lucide-react";
import {
  fetchFixedAssets, createFixedAsset, updateFixedAsset,
  fetchITBlockRates, getLedgers,
} from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const STATUS_COLORS = {
  ACTIVE:            "bg-green-100 text-green-800",
  DISPOSED:          "bg-gray-100 text-gray-700",
  FULLY_DEPRECIATED: "bg-yellow-100 text-yellow-800",
};

const BLANK = {
  asset_code: "", asset_name: "", description: "",
  purchase_date: "", purchase_cost: "", residual_value: "",
  depreciation_method: "WDV", rate_or_life: "",
  it_block_category: "",
  accum_depreciation_ledger: "", depreciation_expense_ledger: "",
  status: "ACTIVE",
};

export default function FixedAssetMasterPage() {
  const { toast } = useToast();
  const [assets, setAssets]         = useState([]);
  const [blockRates, setBlockRates]  = useState([]);
  const [ledgers, setLedgers]        = useState([]);
  const [open, setOpen]              = useState(false);
  const [editId, setEditId]          = useState(null);
  const [editLedgerName, setEditLedgerName] = useState(""); // read-only display of auto-created ledger
  const [form, setForm]              = useState(BLANK);
  const [saving, setSaving]          = useState(false);

  useEffect(() => {
    load();
    fetchITBlockRates().then(r => r.success && setBlockRates(r.data));
    getLedgers().then(r => r.success && setLedgers(Array.isArray(r.data) ? r.data : (r.data.results || [])));
  }, []);

  async function load() {
    const r = await fetchFixedAssets();
    if (r.success) setAssets(Array.isArray(r.data) ? r.data : (r.data.results || []));
  }

  function openCreate() {
    setEditId(null);
    setEditLedgerName("");
    setForm(BLANK);
    setOpen(true);
  }

  function openEdit(a) {
    setEditId(a.id);
    // Show the name of the auto-created asset ledger (read-only)
    const ledger = ledgers.find(l => l.id === a.asset_ledger);
    setEditLedgerName(ledger ? ledger.ac_name : a.asset_ledger_name || "");
    setForm({
      asset_code: a.asset_code || "",
      asset_name: a.asset_name || "",
      description: a.description || "",
      purchase_date: a.purchase_date || "",
      purchase_cost: String(a.purchase_cost || ""),
      residual_value: String(a.residual_value || ""),
      depreciation_method: a.depreciation_method || "WDV",
      rate_or_life: String(a.rate_or_life || ""),
      it_block_category: a.it_block_category || "",
      accum_depreciation_ledger: a.accum_depreciation_ledger ? String(a.accum_depreciation_ledger) : "",
      depreciation_expense_ledger: a.depreciation_expense_ledger ? String(a.depreciation_expense_ledger) : "",
      status: a.status || "ACTIVE",
    });
    setOpen(true);
  }

  function set(k, v) { setForm(f => ({ ...f, [k]: v })); }

  function onSelectBlock(key) {
    const v = key === "__none__" ? "" : key;
    set("it_block_category", v);
    if (v) {
      const found = blockRates.find(b => b.key === key);
      if (found) {
        set("rate_or_life", found.rate);
        set("depreciation_method", "WDV");
      }
    }
  }

  function onCostChange(val) {
    set("purchase_cost", val);
    const cost = parseFloat(val);
    if (!isNaN(cost) && (!form.residual_value || form.residual_value === "0")) {
      set("residual_value", (cost * 0.05).toFixed(2));
    }
  }

  async function handleSave() {
    setSaving(true);
    const payload = {
      ...form,
      // asset_ledger is auto-created by the backend on create — not sent by frontend
      accum_depreciation_ledger:   form.accum_depreciation_ledger || null,
      depreciation_expense_ledger: form.depreciation_expense_ledger || null,
      it_block_category:           form.it_block_category || null,
    };
    const r = editId
      ? await updateFixedAsset(editId, payload)
      : await createFixedAsset(payload);
    setSaving(false);
    if (r.success) {
      toast({ title: editId ? "Asset updated." : "Asset created. Ledger auto-created in Ledger Master." });
      setOpen(false);
      load();
    } else {
      const msg = typeof r.error === "object"
        ? Object.values(r.error).flat().join(", ")
        : r.error;
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
  }

  const fmt = n => Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 });

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Fixed Asset Master</h2>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button size="sm" onClick={openCreate}>
              <Plus className="h-4 w-4 mr-1" /> Add Asset
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
            <SheetHeader>
              <SheetTitle>{editId ? "Edit Fixed Asset" : "New Fixed Asset"}</SheetTitle>
            </SheetHeader>
            <div className="mt-4 space-y-6 pb-8">

              {/* Basic Info */}
              <section className="space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Asset Details</h3>
                <div className="grid grid-cols-2 gap-3">
                  <F label="Asset Code *"><Input value={form.asset_code} onChange={e => set("asset_code", e.target.value)} /></F>
                  <F label="Asset Name *"><Input value={form.asset_name} onChange={e => set("asset_name", e.target.value)} /></F>
                  <F label="Description" className="col-span-2">
                    <Textarea rows={2} value={form.description} onChange={e => set("description", e.target.value)} />
                  </F>
                  <F label="Purchase Date *"><Input type="date" value={form.purchase_date} onChange={e => set("purchase_date", e.target.value)} /></F>
                  <F label="Purchase Cost (₹) *"><Input type="number" min="0" value={form.purchase_cost} onChange={e => onCostChange(e.target.value)} /></F>
                  <F label="Residual Value (₹)">
                    <Input type="number" min="0" value={form.residual_value} onChange={e => set("residual_value", e.target.value)} />
                    <p className="text-xs text-muted-foreground mt-0.5">Default = 5% of cost (Companies Act 2013)</p>
                  </F>
                  {editId && (
                    <F label="Status">
                      <Select value={form.status} onValueChange={v => set("status", v)}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="ACTIVE">Active</SelectItem>
                          <SelectItem value="DISPOSED">Disposed</SelectItem>
                          <SelectItem value="FULLY_DEPRECIATED">Fully Depreciated</SelectItem>
                        </SelectContent>
                      </Select>
                    </F>
                  )}
                </div>
              </section>

              {/* Depreciation Config */}
              <section className="space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Depreciation Configuration</h3>
                <div className="grid grid-cols-2 gap-3">
                  <F label="IT Act Block Category">
                    <Select value={form.it_block_category || "__none__"} onValueChange={v => onSelectBlock(v)}>
                      <SelectTrigger><SelectValue placeholder="— None (custom) —" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">— None (custom) —</SelectItem>
                        {blockRates.map(b => (
                          <SelectItem key={b.key} value={b.key}>{b.label} ({b.rate}%)</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground mt-0.5">Selecting a category auto-fills the WDV rate below</p>
                  </F>
                  <F label="Method">
                    <Select value={form.depreciation_method} onValueChange={v => set("depreciation_method", v)}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="WDV">WDV — Written Down Value (IT Act)</SelectItem>
                        <SelectItem value="SLM">SLM — Straight Line (Companies Act)</SelectItem>
                      </SelectContent>
                    </Select>
                  </F>
                  <F label={form.depreciation_method === "WDV" ? "WDV Rate (%)" : "Useful Life (years)"}>
                    <Input type="number" min="0" step="0.01" value={form.rate_or_life} onChange={e => set("rate_or_life", e.target.value)} />
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {form.depreciation_method === "WDV"
                        ? "e.g. 40 for computers, 15 for vehicles"
                        : "e.g. 10 for furniture, 3 for computers (Schedule II)"}
                    </p>
                  </F>
                </div>
              </section>

              {/* Ledger info + overrides */}
              <section className="space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Accounting Ledgers</h3>

                {/* Asset ledger — auto-created, read-only */}
                <div className="flex items-start gap-2 rounded-md bg-muted/50 border px-3 py-2">
                  <Info className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
                  <p className="text-xs text-muted-foreground">
                    {editId && editLedgerName
                      ? <>Asset ledger <span className="font-semibold text-foreground">"{editLedgerName}"</span> was auto-created in the Ledger Master under the appropriate Fixed Asset account group.</>
                      : <>On save, an asset ledger will be <span className="font-semibold text-foreground">automatically created</span> in the Ledger Master under the appropriate Fixed Asset account group (FA-PM, FA-LB, FA-FF, FA-CE, or FA-VH) based on the IT Act block category selected above.</>
                    }
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  <LedgerSelect
                    label="Accumulated Depreciation Ledger override"
                    value={form.accum_depreciation_ledger}
                    onChange={v => set("accum_depreciation_ledger", v)}
                    ledgers={ledgers}
                  />
                  <LedgerSelect
                    label="Depreciation Expense Ledger override"
                    value={form.depreciation_expense_ledger}
                    onChange={v => set("depreciation_expense_ledger", v)}
                    ledgers={ledgers}
                  />
                </div>
                <p className="text-xs text-muted-foreground">Leave blank to use the retail-wide defaults from Fixed Asset Settings.</p>
              </section>

              <Button onClick={handleSave} disabled={saving} className="w-full">
                {saving ? "Saving…" : editId ? "Update Asset" : "Create Asset"}
              </Button>
            </div>
          </SheetContent>
        </Sheet>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Code</TableHead>
              <TableHead>Asset Name</TableHead>
              <TableHead>Date</TableHead>
              <TableHead className="text-right">Cost</TableHead>
              <TableHead>Method</TableHead>
              <TableHead className="text-right">Accum. Dep.</TableHead>
              <TableHead className="text-right">Current WDV</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {assets.length === 0 && (
              <TableRow><TableCell colSpan={9} className="text-center text-muted-foreground py-10">No assets found. Add your first fixed asset.</TableCell></TableRow>
            )}
            {assets.map(a => (
              <TableRow key={a.id}>
                <TableCell className="font-mono text-xs">{a.asset_code}</TableCell>
                <TableCell>{a.asset_name}</TableCell>
                <TableCell className="text-sm">{a.purchase_date}</TableCell>
                <TableCell className="text-right text-sm">₹{fmt(a.purchase_cost)}</TableCell>
                <TableCell className="text-xs">
                  {a.depreciation_method === "WDV" ? `WDV ${a.rate_or_life}%` : `SLM ${a.rate_or_life}yr`}
                </TableCell>
                <TableCell className="text-right text-sm">₹{fmt(a.accumulated_depreciation)}</TableCell>
                <TableCell className="text-right text-sm font-medium">₹{fmt(a.current_wdv)}</TableCell>
                <TableCell>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[a.status] || ""}`}>
                    {a.status.replace("_", " ")}
                  </span>
                </TableCell>
                <TableCell>
                  <Button size="icon" variant="ghost" onClick={() => openEdit(a)}>
                    <Pencil className="w-4 h-4" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function F({ label, children, className = "" }) {
  return (
    <div className={`space-y-1 ${className}`}>
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}

function LedgerSelect({ label, value, onChange, ledgers }) {
  return (
    <F label={label}>
      <Select value={value || "__none__"} onValueChange={v => onChange(v === "__none__" ? "" : v)}>
        <SelectTrigger>
          <SelectValue placeholder="— Use settings default —" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__none__">— Use settings default —</SelectItem>
          {ledgers.map(l => (
            <SelectItem key={l.id} value={String(l.id)}>{l.ac_name}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </F>
  );
}
