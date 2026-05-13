import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { fetchEmployees, bulkGeneratePayslip, approvePayslip, fetchSalarySlips } from "@/services/apiService";
import SalarySlipView from "./SalarySlipView";
import { useToast } from "@/hooks/use-toast";

const MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const STATUS_COLORS = {
  DRAFT: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-blue-100 text-blue-800",
  PAID: "bg-green-100 text-green-800",
};

export default function SalaryProcessingPage() {
  const now = new Date();
  const [month, setMonth]         = useState(String(now.getMonth() + 1));
  const [year, setYear]           = useState(String(now.getFullYear()));
  const [employees, setEmployees] = useState([]);
  const [rows, setRows]           = useState([]);      // { employee, days_worked, slip }
  const [selected, setSelected]   = useState([]);
  const { toast } = useToast();
  const [loading, setLoading]     = useState(false);
  const [generating, setGenerating] = useState(false);
  const [viewSlip, setViewSlip]   = useState(null);

  async function loadEmployees() {
    setLoading(true);
    const [empR, slipR] = await Promise.all([
      fetchEmployees(),
      fetchSalarySlips({ month, year }),
    ]);
    setLoading(false);
    if (!empR.success) { toast({ title: "Error", description: "Failed to load employees.", variant: "destructive" }); return; }

    const slipMap = {};
    const slips = slipR.success ? (Array.isArray(slipR.data) ? slipR.data : (slipR.data.results || [])) : [];
    slips.forEach(s => { slipMap[s.employee] = s; });

    const empList = Array.isArray(empR.data) ? empR.data : (empR.data.results || []);
    setRows(empList.map(emp => ({
      employee: emp,
      days_worked: "26",
      slip: slipMap[emp.id] || null,
    })));
    setSelected([]);
  }

  function toggleSelect(id) {
    setSelected(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id]);
  }

  function toggleAll(checked) {
    setSelected(checked ? rows.map(r => r.employee.id) : []);
  }

  function setDays(empId, value) {
    setRows(rs => rs.map(r => r.employee.id === empId ? { ...r, days_worked: value } : r));
  }

  async function handleGenerate() {
    const entries = rows
      .filter(r => selected.includes(r.employee.id))
      .map(r => ({ employee_id: r.employee.id, days_worked: r.days_worked }));
    if (!entries.length) { toast({ title: "Select at least one employee." }); return; }

    setGenerating(true);
    const r = await bulkGeneratePayslip({ month, year, entries });
    setGenerating(false);

    if (r.success) {
      const { results, errors } = r.data;
      toast({ title: `Generated ${results.length} slip(s).` });
      if (errors.length) toast({ title: "Errors", description: errors.map(e => e.error).join(", "), variant: "destructive" });
      await loadEmployees();
    } else {
      toast({ title: "Error", description: r.error?.detail || "Failed to generate.", variant: "destructive" });
    }
  }

  async function handleApprove(slipId) {
    const r = await approvePayslip(slipId);
    if (r.success) {
      toast({ title: "Slip approved." });
      await loadEmployees();
    } else {
      toast({ title: "Error", description: r.error?.detail || "Approval failed.", variant: "destructive" });
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-end gap-3 flex-wrap">
        <h2 className="text-lg font-semibold">Salary Processing</h2>
        <div className="space-y-1">
          <Label className="text-xs">Month</Label>
          <select
            className="border rounded px-2 py-1 text-sm bg-background"
            value={month}
            onChange={e => setMonth(e.target.value)}
          >
            {MONTH_NAMES.slice(1).map((m, i) => (
              <option key={i + 1} value={String(i + 1)}>{m}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Year</Label>
          <Input className="w-24" type="number" value={year} onChange={e => setYear(e.target.value)} />
        </div>
        <Button variant="outline" onClick={loadEmployees} disabled={loading}>
          {loading ? "Loading…" : "Load Employees"}
        </Button>
        {rows.length > 0 && (
          <Button onClick={handleGenerate} disabled={generating}>
            {generating ? "Generating…" : `Generate Selected (${selected.length})`}
          </Button>
        )}
      </div>

      {rows.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10">
                  <Checkbox checked={selected.length === rows.length} onCheckedChange={toggleAll} />
                </TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Designation</TableHead>
                <TableHead>Days Worked</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(({ employee: emp, days_worked, slip }) => (
                <TableRow key={emp.id}>
                  <TableCell>
                    <Checkbox
                      checked={selected.includes(emp.id)}
                      onCheckedChange={() => toggleSelect(emp.id)}
                    />
                  </TableCell>
                  <TableCell className="font-mono text-xs">{emp.employee_code}</TableCell>
                  <TableCell>{emp.full_name}</TableCell>
                  <TableCell>{emp.designation}</TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      min="0" max="31" step="0.5"
                      value={days_worked}
                      onChange={e => setDays(emp.id, e.target.value)}
                      className="w-20"
                    />
                  </TableCell>
                  <TableCell>
                    {slip ? (
                      <button
                        onClick={() => setViewSlip(slip)}
                        className={`px-2 py-0.5 rounded text-xs font-medium cursor-pointer ${STATUS_COLORS[slip.status]}`}
                      >
                        {slip.status}
                      </button>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {slip && slip.status === "DRAFT" && (
                      <Button size="sm" variant="outline" onClick={() => handleApprove(slip.id)}>
                        Approve
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Slip Preview Modal */}
      {viewSlip && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setViewSlip(null)}>
          <div className="bg-background rounded-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto p-4" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold">Salary Slip</h3>
              <button onClick={() => setViewSlip(null)} className="text-muted-foreground hover:text-foreground text-xl leading-none">&times;</button>
            </div>
            <SalarySlipView slip={viewSlip} />
          </div>
        </div>
      )}
    </div>
  );
}
