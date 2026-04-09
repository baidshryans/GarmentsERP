import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Check, ArrowLeft } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { fetchSchemes, createSchemeEnrollment, getLedgers } from "@/services/apiService";

export default function SchemeEnrollmentForm() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [schemes, setSchemes] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [customerSearch, setCustomerSearch] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    scheme: "", customer: "", installment_amount: "", start_date: "", remarks: "",
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
    if (customerSearch.length < 2) return;
    const timer = setTimeout(async () => {
      const res = await getLedgers({ search: customerSearch });
      if (res.success) {
        const d = res.data;
        setCustomers(Array.isArray(d) ? d : d?.results ?? []);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [customerSearch]);

  const selectedScheme = schemes.find((s) => String(s.id) === String(form.scheme));

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.scheme || !form.customer || !form.installment_amount) return;
    setSubmitting(true);

    const payload = {
      scheme: parseInt(form.scheme),
      customer: parseInt(form.customer),
      installment_amount: parseFloat(form.installment_amount),
      start_date: form.start_date || undefined,
      remarks: form.remarks,
    };

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
      <Button variant="ghost" onClick={() => navigate("/scheme/enrollments")}><ArrowLeft className="h-4 w-4 mr-1" /> Back</Button>

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
                  {selectedScheme.tenure_months} months | Min ₹{Number(selectedScheme.min_amount).toLocaleString("en-IN")}
                  {selectedScheme.max_amount ? ` | Max ₹${Number(selectedScheme.max_amount).toLocaleString("en-IN")}` : " | No max"}
                </p>
              )}
            </div>

            <div>
              <Label>Customer *</Label>
              <Input
                placeholder="Search customer name..."
                value={customerSearch}
                onChange={(e) => setCustomerSearch(e.target.value)}
              />
              {customers.length > 0 && !form.customer && (
                <div className="border rounded mt-1 max-h-40 overflow-auto">
                  {customers.map((c) => (
                    <div key={c.id} className="px-3 py-1.5 hover:bg-accent cursor-pointer text-sm"
                      onClick={() => { setForm((f) => ({ ...f, customer: String(c.id) })); setCustomerSearch(c.ac_name); setCustomers([]); }}
                    >
                      {c.ac_name} {c.display_name !== c.ac_name ? `(${c.display_name})` : ""}
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>{selectedScheme?.scheme_type === "LUMPSUM" ? "Lump Sum Amount" : "Monthly Installment"} (₹) *</Label>
                <Input name="installment_amount" type="number" value={form.installment_amount}
                  onChange={(e) => setForm((f) => ({ ...f, installment_amount: e.target.value }))} required />
              </div>
              <div>
                <Label>Start Date</Label>
                <Input name="start_date" type="date" value={form.start_date}
                  onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} />
              </div>
            </div>

            <div><Label>Remarks</Label><Textarea value={form.remarks} onChange={(e) => setForm((f) => ({ ...f, remarks: e.target.value }))} rows={2} /></div>

            <Button type="submit" disabled={submitting}><Check className="h-4 w-4 mr-1" /> Enroll Customer</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
