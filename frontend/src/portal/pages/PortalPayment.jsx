import { useState, useEffect } from "react";
import { formatMoney } from "@/lib/format";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, CheckCircle, Loader2, QrCode } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { portalFetchEnrollment, portalPayInstallment } from "../api/portalApiService";

const inr = (v) => formatMoney(v, { space: false });

export default function PortalPayment() {
  const { enrollmentNo } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [enrollment, setEnrollment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [amount, setAmount] = useState("");
  const [paymentState, setPaymentState] = useState("idle"); // idle | processing | success | error
  const [paymentResult, setPaymentResult] = useState(null);

  useEffect(() => {
    portalFetchEnrollment(enrollmentNo).then((res) => {
      if (res.success) {
        setEnrollment(res.data.enrollment);
        setAmount(String(res.data.enrollment.installment_amount));
      }
      setLoading(false);
    });
  }, [enrollmentNo]);

  const handlePay = async () => {
    if (!amount || Number(amount) <= 0) return;
    setPaymentState("processing");

    // Simulate 3-second UPI processing delay
    await new Promise((r) => setTimeout(r, 3000));

    const res = await portalPayInstallment({
      enrollment_no: enrollmentNo,
      amount: Number(amount),
      upi_reference: `MOCK-${Date.now()}`,
    });

    if (res.success) {
      setPaymentState("success");
      setPaymentResult(res.data);
    } else {
      setPaymentState("error");
      toast({ title: "Payment Failed", description: String(res.error), variant: "destructive" });
      setPaymentState("idle");
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-48" />
      </div>
    );
  }

  if (!enrollment) {
    return <p className="text-center text-muted-foreground py-8">Enrollment not found.</p>;
  }

  // Success state
  if (paymentState === "success" && paymentResult) {
    return (
      <div className="flex flex-col items-center justify-center py-12 space-y-4">
        <div className="size-16 rounded-full bg-green-100 flex items-center justify-center">
          <CheckCircle className="size-10 text-green-600" />
        </div>
        <h2 className="text-lg font-semibold text-green-800">Payment Successful!</h2>
        <p className="text-sm text-muted-foreground text-center">
          {inr(paymentResult.payment.amount)} paid for installment #{paymentResult.payment.installment_number}
        </p>
        <Card className="w-full max-w-xs">
          <CardContent className="pt-4 text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Payment #</span>
              <span className="font-medium">{paymentResult.payment.payment_no}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Date</span>
              <span className="font-medium">{paymentResult.payment.date}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Total Paid</span>
              <span className="font-medium text-green-700">{inr(paymentResult.enrollment.total_paid)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Remaining</span>
              <span className="font-medium">{paymentResult.enrollment.remaining_installments} installment(s)</span>
            </div>
          </CardContent>
        </Card>
        <Button onClick={() => navigate(`/portal/enrollment/${enrollmentNo}`)} className="mt-4">
          Back to Scheme
        </Button>
      </div>
    );
  }

  // Processing state
  if (paymentState === "processing") {
    return (
      <div className="flex flex-col items-center justify-center py-16 space-y-6">
        <div className="size-40 border-2 border-dashed border-muted rounded-lg flex items-center justify-center">
          <QrCode className="size-24 text-muted-foreground/40" />
        </div>
        <div className="text-center">
          <p className="text-sm font-medium">Scan QR or pay via UPI</p>
          <p className="text-xs text-muted-foreground mt-1">shop@upi (mock)</p>
        </div>
        <div className="flex items-center gap-2 text-primary">
          <Loader2 className="size-4 animate-spin" />
          <span className="text-sm">Processing payment of {inr(amount)}...</span>
        </div>
      </div>
    );
  }

  // Input state
  const e = enrollment;
  const totalInstallments = e.payments_made + e.remaining_installments;

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate(`/portal/enrollment/${enrollmentNo}`)}>
        <ArrowLeft className="size-4 mr-1" /> Back
      </Button>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Pay Installment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Enrollment summary */}
          <div className="p-3 bg-muted/50 rounded-lg text-sm space-y-1">
            <p className="font-medium">{e.scheme_name}</p>
            <p className="text-xs text-muted-foreground">{e.enrollment_no}</p>
            <div className="flex justify-between mt-2">
              <span className="text-muted-foreground">Installment #</span>
              <span className="font-medium">{e.payments_made + 1} of {totalInstallments}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Paid so far</span>
              <span className="font-medium text-green-700">{inr(e.total_paid)}</span>
            </div>
          </div>

          {/* Amount input */}
          <div>
            <Label>Amount (₹)</Label>
            <Input
              type="number"
              value={amount}
              onChange={(ev) => setAmount(ev.target.value)}
              min={1}
            />
            <p className="text-xs text-muted-foreground mt-1">
              Suggested: {inr(e.installment_amount)}
            </p>
          </div>

          {/* Pay button */}
          <Button className="w-full" onClick={handlePay} disabled={!amount || Number(amount) <= 0}>
            Pay {inr(amount)} via UPI
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
