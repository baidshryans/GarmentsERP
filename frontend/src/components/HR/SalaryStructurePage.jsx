import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle,
} from "@/components/ui/sheet";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Plus } from "lucide-react";
import {
  fetchEmployees, fetchSalaryStructures, createSalaryStructure,
  fetchDeductionConfig, saveDeductionConfig,
} from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const BLANK_STRUCT = {
  employee: "", effective_from: "",
  basic: "", hra: "", da: "", conveyance_allowance: "",
  medical_allowance: "", special_allowance: "",
};

const BLANK_CONFIG = {
  id: null, employee: "",
  pf_applicable: true, pf_above_ceiling: false,
  esi_applicable: false, pt_applicable: true,
  tds_monthly: "0", advance_recovery: "0",
};

export default function SalaryStructurePage() {
  const { toast } = useToast();
  const [employees, setEmployees]     = useState([]);
  const [selectedEmp, setSelectedEmp] = useState("");
  const [structures, setStructures]   = useState([]);
  const [sheetOpen, setSheetOpen]     = useState(false);
  const [form, setForm]               = useState(BLANK_STRUCT);
  const [config, setConfig]           = useState(BLANK_CONFIG);
  const [tab, setTab]                 = useState("structure"); // "structure" | "deductions"
  const [saving, setSaving]           = useState(false);

  useEffect(() => {
    fetchEmployees({ page_size: 9999 }).then(r => r.success && setEmployees(r.data.results || []));
  }, []);

  useEffect(() => {
    if (!selectedEmp) { setStructures([]); setConfig(BLANK_CONFIG); return; }
    fetchSalaryStructures({ employee: selectedEmp }).then(r => r.success && setStructures(Array.isArray(r.data) ? r.data : (r.data.results || [])));
    fetchDeductionConfig({ employee: selectedEmp }).then(r => {
      if (r.success && r.data.length > 0) {
        const c = r.data[0];
        setConfig({ ...c, id: c.id, tds_monthly: String(c.tds_monthly), advance_recovery: String(c.advance_recovery) });
      } else {
        setConfig({ ...BLANK_CONFIG, employee: selectedEmp });
      }
    });
  }, [selectedEmp]);

  function gross(f) {
    const fields = ["basic", "hra", "da", "conveyance_allowance", "medical_allowance", "special_allowance"];
    return fields.reduce((s, k) => s + (parseFloat(f[k]) || 0), 0);
  }

  function openAdd() {
    setForm({ ...BLANK_STRUCT, employee: selectedEmp });
    setTab("structure");
    setSheetOpen(true);
  }

  function setF(k, v) { setForm(f => ({ ...f, [k]: v })); }
  function setC(k, v) { setConfig(c => ({ ...c, [k]: v })); }

  async function saveStructure() {
    setSaving(true);
    const r = await createSalaryStructure({ ...form, employee: selectedEmp });
    setSaving(false);
    if (r.success) {
      toast({ title: "Salary structure saved." });
      fetchSalaryStructures({ employee: selectedEmp }).then(res => res.success && setStructures(Array.isArray(res.data) ? res.data : (res.data.results || [])));
      setTab("deductions");
    } else {
      toast({ title: "Error", description: Object.values(r.error || {}).flat().join(", ") || String(r.error), variant: "destructive" });
    }
  }

  async function saveConfig() {
    setSaving(true);
    const r = await saveDeductionConfig({ ...config, employee: selectedEmp });
    setSaving(false);
    if (r.success) {
      toast({ title: "Deduction config saved." });
      setConfig({ ...r.data, id: r.data.id, tds_monthly: String(r.data.tds_monthly), advance_recovery: String(r.data.advance_recovery) });
      setSheetOpen(false);
    } else {
      toast({ title: "Error", description: Object.values(r.error || {}).flat().join(", ") || String(r.error), variant: "destructive" });
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold">Salary Structure</h2>
        <div className="flex-1 max-w-xs">
          <Select value={selectedEmp} onValueChange={setSelectedEmp}>
            <SelectTrigger><SelectValue placeholder="Select employee�" /></SelectTrigger>
            <SelectContent>
              {employees.map(e => (
                <SelectItem key={e.id} value={String(e.id)}>{e.employee_code} � {e.full_name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {selectedEmp && (
          <Button size="sm" onClick={openAdd}><Plus className="size-4 mr-1" /> Add Structure</Button>
        )}
      </div>

      {selectedEmp && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Effective From</TableHead>
                <TableHead>Basic</TableHead>
                <TableHead>HRA</TableHead>
                <TableHead>DA</TableHead>
                <TableHead>Conv.</TableHead>
                <TableHead>Medical</TableHead>
                <TableHead>Special</TableHead>
                <TableHead>Gross CTC</TableHead>
                <TableHead>Active</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {structures.length === 0 && (
                <TableRow><TableCell colSpan={9} className="text-center text-muted-foreground py-6">No structures found.</TableCell></TableRow>
              )}
              {structures.map(s => (
                <TableRow key={s.id}>
                  <TableCell>{s.effective_from}</TableCell>
                  <TableCell>₹{Number(s.basic).toLocaleString("en-IN")}</TableCell>
                  <TableCell>₹{Number(s.hra).toLocaleString("en-IN")}</TableCell>
                  <TableCell>₹{Number(s.da).toLocaleString("en-IN")}</TableCell>
                  <TableCell>₹{Number(s.conveyance_allowance).toLocaleString("en-IN")}</TableCell>
                  <TableCell>₹{Number(s.medical_allowance).toLocaleString("en-IN")}</TableCell>
                  <TableCell>₹{Number(s.special_allowance).toLocaleString("en-IN")}</TableCell>
                  <TableCell className="font-semibold">₹{Number(s.gross_ctc).toLocaleString("en-IN")}</TableCell>
                  <TableCell>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${s.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>{s.is_active ? "Yes" : "No"}</span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="right" className="w-full sm:max-w-xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Salary Structure & Deductions</SheetTitle>
          </SheetHeader>

          {/* Tab toggle */}
          <div className="flex gap-2 mt-4 mb-4 border-b pb-2">
            <button onClick={() => setTab("structure")}
              className={`text-sm px-3 py-1 rounded ${tab === "structure" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
              Earnings
            </button>
            <button onClick={() => setTab("deductions")}
              className={`text-sm px-3 py-1 rounded ${tab === "deductions" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}>
              Deductions
            </button>
          </div>

          {tab === "structure" && (
            <div className="space-y-3">
              <EF label="Effective From *" type="date" value={form.effective_from} onChange={v => setF("effective_from", v)} />
              <EF label="Basic (₹)" type="number" value={form.basic} onChange={v => setF("basic", v)} />
              <EF label="HRA (₹)" type="number" value={form.hra} onChange={v => setF("hra", v)} />
              <EF label="DA (₹)" type="number" value={form.da} onChange={v => setF("da", v)} />
              <EF label="Conveyance Allowance (₹)" type="number" value={form.conveyance_allowance} onChange={v => setF("conveyance_allowance", v)} />
              <EF label="Medical Allowance (₹)" type="number" value={form.medical_allowance} onChange={v => setF("medical_allowance", v)} />
              <EF label="Special Allowance (₹)" type="number" value={form.special_allowance} onChange={v => setF("special_allowance", v)} />
              <div className="flex justify-between items-center p-3 rounded bg-muted text-sm">
                <span className="text-muted-foreground">Gross CTC</span>
                <span className="font-semibold">₹{gross(form).toLocaleString("en-IN")}</span>
              </div>
              <Button onClick={saveStructure} disabled={saving} className="w-full">
                {saving ? "Saving�" : "Save Earnings → Next"}
              </Button>
            </div>
          )}

          {tab === "deductions" && (
            <div className="space-y-4">
              <SwitchRow label="PF Applicable" checked={config.pf_applicable} onChange={v => setC("pf_applicable", v)} />
              {config.pf_applicable && (
                <SwitchRow
                  label="PF on Full Basic (uncap ceiling)"
                  sub="If off, PF is 12% of min(Basic, ₹15,000)"
                  checked={config.pf_above_ceiling}
                  onChange={v => setC("pf_above_ceiling", v)}
                />
              )}
              <SwitchRow label="ESI Applicable" sub="Active only if gross ≤ ₹21,000" checked={config.esi_applicable} onChange={v => setC("esi_applicable", v)} />
              <SwitchRow label="Professional Tax" checked={config.pt_applicable} onChange={v => setC("pt_applicable", v)} />
              <EF label="TDS Monthly (₹)" type="number" value={config.tds_monthly} onChange={v => setC("tds_monthly", v)} />
              <EF label="Advance Recovery (₹)" type="number" value={config.advance_recovery} onChange={v => setC("advance_recovery", v)} />
              <Button onClick={saveConfig} disabled={saving} className="w-full">
                {saving ? "Saving�" : "Save Deduction Config"}
              </Button>
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function EF({ label, type = "text", value, onChange }) {
  return (
    <div className="space-y-1">
      <Label className="text-xs">{label}</Label>
      <Input type={type} value={value} onChange={e => onChange(e.target.value)} min={type === "number" ? "0" : undefined} />
    </div>
  );
}

function SwitchRow({ label, sub, checked, onChange }) {
  return (
    <div className="flex items-center justify-between py-1">
      <div>
        <p className="text-sm">{label}</p>
        {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${checked ? "bg-primary" : "bg-muted"}`}
      >
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${checked ? "translate-x-6" : "translate-x-1"}`} />
      </button>
    </div>
  );
}
