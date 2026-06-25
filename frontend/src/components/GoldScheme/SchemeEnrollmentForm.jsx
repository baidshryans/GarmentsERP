import { useState, useEffect } from "react";
import { formatNumber } from "@/lib/format";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Check, ArrowLeft } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  fetchSchemes, createSchemeEnrollment,
  getLedgers, getLedger, patchLedger,
} from "@/services/apiService";

const RELATIONSHIPS = [
  ["SPOUSE", "Spouse"], ["SON", "Son"], ["DAUGHTER", "Daughter"],
  ["FATHER", "Father"], ["MOTHER", "Mother"],
  ["BROTHER", "Brother"], ["SISTER", "Sister"], ["OTHER", "Other"],
];

const PAN_RE = /^[A-Z]{5}[0-9]{4}[A-Z]$/;
const AADHAAR_RE = /^[0-9]{12}$/;

export default function SchemeEnrollmentForm() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [schemes, setSchemes] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [customerSearch, setCustomerSearch] = useState("");
  const [selectedLedger, setSelectedLedger] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const [form, setForm] = useState({
    scheme: "", customer: "", installment_amount: "", start_date: "", remarks: "",
    pan: "", aadhar: "",
    nominee_name: "", nominee_mobile: "", nominee_address: "", nominee_relationship: "",
    file: null,
  });

  useEffect(() => {
    fetchSchemes().then((res) => {
      if (res.success) {
        const d = res.data;
        const list = Array.isArray(d) ? d : d?.results ?? [];
        setSchemes(list.filter((s) => s.is_active));
      }
    });
  }, []);

  useEffect(() => {
    if (customerSearch.length < 2 || form.customer) return;
    const timer = setTimeout(async () => {
      const res = await getLedgers({ search: customerSearch, type: "CO" });
      if (res.success) {
        const d = res.data;
        setCustomers(Array.isArray(d) ? d : d?.results ?? []);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [customerSearch, form.customer]);

  const pickCustomer = async (c) => {
    setForm((f) => ({ ...f, customer: String(c.id) }));
    setCustomerSearch(`${c.ac_name}${c.mobile1 ? ` — ${c.mobile1}` : ""}`);
    setCustomers([]);
    const res = await getLedger(c.id);
    if (res.success) {
      setSelectedLedger(res.data);
      setForm((f) => ({
        ...f,
        pan: res.data.pan || "",
        aadhar: res.data.aadhar || "",
      }));
    }
  };

  const clearCustomer = () => {
    setForm((f) => ({ ...f, customer: "", pan: "", aadhar: "" }));
    setSelectedLedger(null);
    setCustomerSearch("");
  };

  const selectedScheme = schemes.find((s) => String(s.id) === String(form.scheme));
  const needPan = selectedLedger && !selectedLedger.pan;
  const needAadhaar = selectedLedger && !selectedLedger.aadhar;

  const validate = () => {
    if (!form.scheme || !form.customer || !form.installment_amount) {
      return "Scheme, customer and amount are required.";
    }
    if (needPan && !PAN_RE.test(form.pan.trim().toUpperCase())) {
      return "PAN is required and must look like ABCDE1234F.";
    }
    if (needAadhaar && !AADHAAR_RE.test(form.aadhar.trim())) {
      return "Aadhaar is required and must be 12 digits.";
    }
    if (!form.nominee_name.trim() || !form.nominee_mobile.trim() || !form.nominee_relationship) {
      return "Nominee name, mobile and relationship are required.";
    }
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const err = validate();
    if (err) {
      toast({ title: "Cannot enroll", description: err, variant: "destructive" });
      return;
    }
    setSubmitting(true);

    if (needPan || needAadhaar) {
      const patch = {};
      if (needPan) patch.pan = form.pan.trim().toUpperCase();
      if (needAadhaar) patch.aadhar = form.aadhar.trim();
      const r = await patchLedger(form.customer, patch);
      if (!r.success) {
        toast({
          title: "KYC update failed",
          description: typeof r.error === "object" ? JSON.stringify(r.error) : String(r.error),
          variant: "destructive",
        });
        setSubmitting(false);
        return;
      }
    }

    const payload = {
      scheme: parseInt(form.scheme),
      customer: parseInt(form.customer),
      installment_amount: parseFloat(form.installment_amount),
      start_date: form.start_date || undefined,
      remarks: form.remarks,
      nominee: {
        name: form.nominee_name.trim(),
        mobile: form.nominee_mobile.trim(),
        address: form.nominee_address.trim(),
        relationship: form.nominee_relationship,
      },
    };
    if (form.file) payload.enrollment_form_file = form.file;

    const res = await createSchemeEnrollment(payload);
    if (res.success) {
      toast({ title: "Customer enrolled successfully" });
      navigate("/scheme/enrollments");
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : res.error;
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setSubmitting(false);
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <Button variant="ghost" onClick={() => navigate("/scheme/enrollments")}>
        <ArrowLeft className="size-4 mr-1" /> Back
      </Button>

      <Card>
        <CardHeader><CardTitle>New Scheme Enrollment</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label>Scheme *</Label>
              <Select value={String(form.scheme)} onValueChange={(v) => setForm((f) => ({ ...f, scheme: v }))}>
                <SelectTrigger><SelectValue placeholder="Select scheme" /></SelectTrigger>
                <SelectContent>
                  {schemes.map((s) => (
                    <SelectItem key={s.id} value={String(s.id)}>
                      {s.scheme_code} — {s.name} ({s.scheme_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedScheme && (
                <p className="text-sm text-muted-foreground mt-1">
                  {selectedScheme.tenure_months} months | Min ₹{formatNumber(selectedScheme.min_amount)}
                  {selectedScheme.max_amount ? ` | Max ₹${formatNumber(selectedScheme.max_amount)}` : " | No max"}
                </p>
              )}
            </div>

            <div>
              <Label>Customer * (search by name or mobile)</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="Type name or phone..."
                  value={customerSearch}
                  onChange={(e) => setCustomerSearch(e.target.value)}
                  disabled={!!form.customer}
                />
                {form.customer && (
                  <Button type="button" variant="ghost" onClick={clearCustomer}>Change</Button>
                )}
              </div>
              {customers.length > 0 && !form.customer && (
                <div className="border rounded mt-1 max-h-40 overflow-auto">
                  {customers.map((c) => (
                    <div key={c.id} className="px-3 py-1.5 hover:bg-accent cursor-pointer text-sm"
                      onClick={() => pickCustomer(c)}>
                      {c.ac_name}{c.mobile1 ? ` — ${c.mobile1}` : ""}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {selectedLedger && (needPan || needAadhaar) && (
              <Card className="bg-muted/40">
                <CardHeader className="pb-2"><CardTitle className="text-base">KYC details required</CardTitle></CardHeader>
                <CardContent className="grid grid-cols-2 gap-4">
                  {needPan && (
                    <div>
                      <Label>PAN *</Label>
                      <Input value={form.pan} onChange={(e) => setForm((f) => ({ ...f, pan: e.target.value.toUpperCase() }))}
                        placeholder="ABCDE1234F" maxLength={10} />
                    </div>
                  )}
                  {needAadhaar && (
                    <div>
                      <Label>Aadhaar *</Label>
                      <Input value={form.aadhar} onChange={(e) => setForm((f) => ({ ...f, aadhar: e.target.value.replace(/\D/g, "") }))}
                        placeholder="12-digit number" maxLength={12} />
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>{selectedScheme?.scheme_type === "LUMPSUM" ? "Lump Sum Amount" : "Monthly Installment"} (₹) *</Label>
                <Input type="number" value={form.installment_amount}
                  onChange={(e) => setForm((f) => ({ ...f, installment_amount: e.target.value }))} required />
              </div>
              <div>
                <Label>Start Date</Label>
                <Input type="date" value={form.start_date}
                  onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
              </div>
            </div>

            <Card className="bg-muted/40">
              <CardHeader className="pb-2"><CardTitle className="text-base">Nominee details</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Name *</Label>
                    <Input value={form.nominee_name}
                      onChange={(e) => setForm((f) => ({ ...f, nominee_name: e.target.value }))} required />
                  </div>
                  <div>
                    <Label>Mobile *</Label>
                    <Input value={form.nominee_mobile}
                      onChange={(e) => setForm((f) => ({ ...f, nominee_mobile: e.target.value.replace(/\D/g, "") }))}
                      maxLength={15} required />
                  </div>
                </div>
                <div>
                  <Label>Relationship *</Label>
                  <Select value={form.nominee_relationship}
                    onValueChange={(v) => setForm((f) => ({ ...f, nominee_relationship: v }))}>
                    <SelectTrigger><SelectValue placeholder="Select relationship" /></SelectTrigger>
                    <SelectContent>
                      {RELATIONSHIPS.map(([code, label]) => (
                        <SelectItem key={code} value={code}>{label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Address</Label>
                  <Textarea rows={2} value={form.nominee_address}
                    onChange={(e) => setForm((f) => ({ ...f, nominee_address: e.target.value }))} />
                </div>
              </CardContent>
            </Card>

            <div>
              <Label>Enrollment Form (PDF / JPG / PNG, optional)</Label>
              <Input type="file" accept=".pdf,.jpg,.jpeg,.png"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  if (file && file.size > 10 * 1024 * 1024) {
                    toast({ title: "File too large", description: "Max 10 MB", variant: "destructive" });
                    e.target.value = "";
                    return;
                  }
                  setForm((f) => ({ ...f, file }));
                }}
              />
            </div>

            <div>
              <Label>Remarks</Label>
              <Textarea rows={2} value={form.remarks}
                onChange={(e) => setForm((f) => ({ ...f, remarks: e.target.value }))} />
            </div>

            <Button type="submit" disabled={submitting}>
              <Check className="size-4 mr-1" /> Enroll Customer
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
