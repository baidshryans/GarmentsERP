import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Plus, Pencil } from "lucide-react";
import { fetchEmployees, createEmployeeWithUser, updateEmployee, fetchStates } from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const BLANK_FORM = {
  // User fields (create only)
  username: "", password: "", email: "", first_name: "", last_name: "",
  // Employee fields
  employee_code: "", full_name: "", designation: "", department: "",
  date_of_joining: "", date_of_birth: "", gender: "",
  address_line1: "", address_line2: "", city: "", state: null, pincode: "",
  bank_name: "", account_no: "", ifsc_code: "",
  pan_number: "", pf_number: "", esi_number: "",
};

export default function EmployeeMasterPage() {
  const { toast } = useToast();
  const [employees, setEmployees] = useState([]);
  const [states, setStates]       = useState([]);
  const [open, setOpen]           = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm]           = useState(BLANK_FORM);
  const [saving, setSaving]       = useState(false);

  useEffect(() => {
    loadEmployees();
    fetchStates().then(r => r.success && setStates(Array.isArray(r.data) ? r.data : (r.data.results || [])));
  }, []);

  async function loadEmployees() {
    const r = await fetchEmployees();
    if (r.success) setEmployees(Array.isArray(r.data) ? r.data : (r.data.results || []));
  }

  function openCreate() {
    setEditingId(null);
    setForm(BLANK_FORM);
    setOpen(true);
  }

  function openEdit(emp) {
    setEditingId(emp.id);
    setForm({
      ...BLANK_FORM,
      employee_code: emp.employee_code,
      full_name: emp.full_name,
      designation: emp.designation || "",
      department: emp.department || "",
      date_of_joining: emp.date_of_joining || "",
      date_of_birth: emp.date_of_birth || "",
      gender: emp.gender || "",
      address_line1: emp.address_line1 || "",
      address_line2: emp.address_line2 || "",
      city: emp.city || "",
      state: emp.state ? String(emp.state) : null,
      pincode: emp.pincode || "",
      bank_name: emp.bank_name || "",
      account_no: emp.account_no || "",
      ifsc_code: emp.ifsc_code || "",
      pan_number: emp.pan_number || "",
      pf_number: emp.pf_number || "",
      esi_number: emp.esi_number || "",
    });
    setOpen(true);
  }

  function set(field, value) {
    setForm(f => ({ ...f, [field]: value }));
  }

  async function handleSave() {
    setSaving(true);
    let result;
    if (editingId) {
      const payload = { ...form };
      delete payload.username; delete payload.password;
      delete payload.email; delete payload.first_name; delete payload.last_name;
      result = await updateEmployee(editingId, payload);
    } else {
      result = await createEmployeeWithUser(form);
    }
    setSaving(false);
    if (result.success) {
      toast({ title: editingId ? "Employee updated." : "Employee created." });
      setOpen(false);
      loadEmployees();
    } else {
      const msg = typeof result.error === "object"
        ? Object.values(result.error).flat().join(", ")
        : result.error;
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Employee Master</h2>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button size="sm" onClick={openCreate}>
              <Plus className="h-4 w-4 mr-1" /> Add Employee
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-full sm:max-w-2xl overflow-y-auto">
            <SheetHeader>
              <SheetTitle>{editingId ? "Edit Employee" : "New Employee"}</SheetTitle>
            </SheetHeader>
            <div className="mt-4 space-y-6 pb-6">

              {/* User Account — create only */}
              {!editingId && (
                <section className="space-y-3">
                  <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                    ERP Login Account
                  </h3>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Username *"><Input value={form.username} onChange={e => set("username", e.target.value)} /></Field>
                    <Field label="Password *"><Input type="password" value={form.password} onChange={e => set("password", e.target.value)} /></Field>
                    <Field label="First Name"><Input value={form.first_name} onChange={e => set("first_name", e.target.value)} /></Field>
                    <Field label="Last Name"><Input value={form.last_name} onChange={e => set("last_name", e.target.value)} /></Field>
                    <Field label="Email" className="col-span-2"><Input type="email" value={form.email} onChange={e => set("email", e.target.value)} /></Field>
                  </div>
                </section>
              )}

              {/* Personal Info */}
              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Personal Info</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Employee Code *"><Input value={form.employee_code} onChange={e => set("employee_code", e.target.value)} /></Field>
                  <Field label="Full Name *"><Input value={form.full_name} onChange={e => set("full_name", e.target.value)} /></Field>
                  <Field label="Designation"><Input value={form.designation} onChange={e => set("designation", e.target.value)} /></Field>
                  <Field label="Department"><Input value={form.department} onChange={e => set("department", e.target.value)} /></Field>
                  <Field label="Date of Joining *"><Input type="date" value={form.date_of_joining} onChange={e => set("date_of_joining", e.target.value)} /></Field>
                  <Field label="Date of Birth"><Input type="date" value={form.date_of_birth} onChange={e => set("date_of_birth", e.target.value)} /></Field>
                  <Field label="Gender">
                    <Select value={form.gender} onValueChange={v => set("gender", v)}>
                      <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="M">Male</SelectItem>
                        <SelectItem value="F">Female</SelectItem>
                        <SelectItem value="O">Other</SelectItem>
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
              </section>

              {/* Address */}
              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Address</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Address Line 1" className="col-span-2"><Input value={form.address_line1} onChange={e => set("address_line1", e.target.value)} /></Field>
                  <Field label="Address Line 2" className="col-span-2"><Input value={form.address_line2} onChange={e => set("address_line2", e.target.value)} /></Field>
                  <Field label="City"><Input value={form.city} onChange={e => set("city", e.target.value)} /></Field>
                  <Field label="Pincode"><Input value={form.pincode} onChange={e => set("pincode", e.target.value)} /></Field>
                  <Field label="State" className="col-span-2">
                    <Select value={form.state || ""} onValueChange={v => set("state", v || null)}>
                      <SelectTrigger><SelectValue placeholder="Select state" /></SelectTrigger>
                      <SelectContent>
                        {states.map(s => <SelectItem key={s.id} value={String(s.id)}>{s.state_name}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </Field>
                </div>
              </section>

              {/* Bank Details */}
              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Bank Details</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Bank Name"><Input value={form.bank_name} onChange={e => set("bank_name", e.target.value)} /></Field>
                  <Field label="Account No"><Input value={form.account_no} onChange={e => set("account_no", e.target.value)} /></Field>
                  <Field label="IFSC Code"><Input value={form.ifsc_code} onChange={e => set("ifsc_code", e.target.value)} /></Field>
                </div>
              </section>

              {/* Compliance */}
              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Compliance</h3>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="PAN Number"><Input value={form.pan_number} onChange={e => set("pan_number", e.target.value)} /></Field>
                  <Field label="PF Number"><Input value={form.pf_number} onChange={e => set("pf_number", e.target.value)} /></Field>
                  <Field label="ESI Number"><Input value={form.esi_number} onChange={e => set("esi_number", e.target.value)} /></Field>
                </div>
              </section>

              <Button onClick={handleSave} disabled={saving} className="w-full">
                {saving ? "Saving…" : editingId ? "Update Employee" : "Create Employee"}
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
              <TableHead>Name</TableHead>
              <TableHead>Designation</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Joined</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {employees.length === 0 && (
              <TableRow><TableCell colSpan={7} className="text-center text-muted-foreground py-8">No employees found.</TableCell></TableRow>
            )}
            {employees.map(emp => (
              <TableRow key={emp.id}>
                <TableCell className="font-mono text-xs">{emp.employee_code}</TableCell>
                <TableCell>{emp.full_name}</TableCell>
                <TableCell>{emp.designation}</TableCell>
                <TableCell>{emp.department}</TableCell>
                <TableCell>{emp.date_of_joining}</TableCell>
                <TableCell>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${emp.is_active ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"}`}>
                    {emp.is_active ? "Active" : "Inactive"}
                  </span>
                </TableCell>
                <TableCell>
                  <Button size="icon" variant="ghost" onClick={() => openEdit(emp)}>
                    <Pencil className="h-3.5 w-3.5" />
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

function Field({ label, children, className = "" }) {
  return (
    <div className={`space-y-1 ${className}`}>
      <Label className="text-xs">{label}</Label>
      {children}
    </div>
  );
}
