import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Check, ArrowLeft } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { fetchSchemeEnrollment, schemeEnrollmentPay, getLedgers } from "@/services/apiService";

const PAYMENT_MODES = [
  { value: "CASH", label: "Cash" },
  { value: "BANK", label: "Bank Transfer" },
  { value: "UPI", label: "UPI" },
  { value: "CHEQUE", label: "Cheque" },
  { value: "CARD", label: "Card" },
];

export default function SchemePaymentForm() {
  const { uuid } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [enrollment, setEnrollment] = useState(null);
  const [cashBankLedgers, setCashBankLedgers] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    amount: "", payment_mode: "CASH", payment_ledger: "", date: "", remarks: "",
  });

  useEffect(() => {
    fetchSchemeEnrollment(uuid).then((res) => {
      if (res.success) {
        setEnrollment(res.data);
        setForm((f) => ({ ...f, amount: String(res.data.installment_amount) }));
      }
    });
    // Fetch cash/bank ledgers for payment
    getLedgers({ type: "CA" }).then((res) => {
      if (res.success) {
        const d = res.data;
        const list = Array.isArray(d) ? d : d?.results ?? [];
        setCashBankLedgers(list);
      }
    });
    getLedgers({ type: "BA" }).then((res) => {
      if (res.success) {
        const d = res.data;
        const list = Array.isArray(d) ? d : d?.results ?? [];
        setCashBankLedgers((prev) => [...prev, ...list]);
      }
    });
  }, [uuid]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.amount || !form.payment_ledger) return;
    setSubmitting(true);

    const payload = {
      amount: parseFloat(form.amount),
      payment_mode: form.payment_mode,
      payment_ledger: parseInt(form.payment_ledger),
      date: form.date || undefined,
      remarks: form.remarks,
    };

    const res = await schemeEnrollmentPay(uuid, payload);
    if (res.success) {
      toast({ title: `Payment of ₹${Number(form.amount).toLocaleString("en-IN")} recorded` });
      navigate(`/scheme/enrollments/${uuid}/statement`);
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : res.error;
      toast({ title: "Error", description: msg, variant: "destructive" });
    }
    setSubmitting(false);
  };

  if (!enrollment) return <div className="p-4">Loading...</div>;

  return (
    <div className="space-y-4 max-w-xl">
      <Button variant="ghost" onClick={() => navigate(`/scheme/enrollments/${uuid}/statement`)}><ArrowLeft className="size-4 mr-1" /> Back</Button>

      <Card>
        <CardHeader>
          <CardTitle>Record Scheme Payment</CardTitle>
          <CardDescription>
            {enrollment.enrollment_no} — {enrollment.customer_name} — {enrollment.scheme_name}
            <br />
            Installment #{enrollment.payments_made + 1} of {enrollment.scheme_type === "LUMPSUM" ? "1" : enrollment.payments_made + enrollment.remaining_installments}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Amount (₹) *</Label>
                <Input type="number" value={form.amount}
                  onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))} required />
              </div>
              <div>
                <Label>Date</Label>
                <Input type="date" value={form.date}
                  onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Payment Mode</Label>
                <Select value={form.payment_mode} onValueChange={(v) => setForm((f) => ({ ...f, payment_mode: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{PAYMENT_MODES.map((m) => <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div>
                <Label>Payment Account *</Label>
                <Select value={String(form.payment_ledger)} onValueChange={(v) => setForm((f) => ({ ...f, payment_ledger: v }))}>
                  <SelectTrigger><SelectValue placeholder="Select cash/bank account" /></SelectTrigger>
                  <SelectContent>
                    {cashBankLedgers.map((l) => <SelectItem key={l.id} value={String(l.id)}>{l.ac_name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div><Label>Remarks</Label><Input value={form.remarks} onChange={(e) => setForm((f) => ({ ...f, remarks: e.target.value }))} /></div>

            <div className="text-sm text-muted-foreground">
              Paid so far: ₹{Number(enrollment.total_paid).toLocaleString("en-IN")} ({enrollment.payments_made} payments)
              {enrollment.gold_accumulated_wt > 0 && ` | Gold: ${Number(enrollment.gold_accumulated_wt).toFixed(3)}g`}
            </div>

            <Button type="submit" disabled={submitting}><Check className="size-4 mr-1" /> Record Payment</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
