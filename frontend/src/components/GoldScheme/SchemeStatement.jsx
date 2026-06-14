import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { DataTable } from "@/table";
import { ArrowLeft, CreditCard, Gift, XCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import {
  fetchSchemeStatement, fetchSchemeBenefit,
  redeemSchemeEnrollment, cancelSchemeEnrollment, getLedgers,
} from "@/services/apiService";

const SETTLEMENT_MODES = [
  ["REFUND", "Refund to cash/bank"],
  ["TRANSFER", "Transfer to customer (credit on their ledger)"],
];

const STATUS_COLORS = {
  ACTIVE: "bg-green-100 text-green-800",
  MATURED: "bg-blue-100 text-blue-800",
  REDEEMED: "bg-purple-100 text-purple-800",
  FORFEITED: "bg-red-100 text-red-800",
  CANCELLED: "bg-gray-100 text-gray-800",
};

export default function SchemeStatement() {
  const { uuid } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const [data, setData] = useState(null);
  const [benefit, setBenefit] = useState(null);
  const [cancelOpen, setCancelOpen] = useState(false);
  const [settlementMode, setSettlementMode] = useState("");
  const [refundLedger, setRefundLedger] = useState("");
  const [cashBankLedgers, setCashBankLedgers] = useState([]);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    Promise.all([getLedgers({ type: "CA" }), getLedgers({ type: "BA" })]).then(([ca, ba]) => {
      const pick = (r) => (r.success ? (Array.isArray(r.data) ? r.data : r.data?.results ?? []) : []);
      setCashBankLedgers([...pick(ca), ...pick(ba)]);
    });
  }, []);

  const load = async () => {
    const [stRes, bRes] = await Promise.all([
      fetchSchemeStatement(uuid),
      fetchSchemeBenefit(uuid),
    ]);
    if (stRes.success) setData(stRes.data);
    if (bRes.success) setBenefit(bRes.data);
  };

  useEffect(() => { load(); }, [uuid]);

  const openCancel = () => {
    setSettlementMode("");
    setRefundLedger("");
    setCancelOpen(true);
  };

  const confirmCancel = async () => {
    const hasBalance = Number(data?.enrollment?.total_paid) > 0;
    if (hasBalance && !settlementMode) {
      toast({ title: "Select what to do with the paid amount", variant: "destructive" });
      return;
    }
    if (hasBalance && settlementMode === "REFUND" && !refundLedger) {
      toast({ title: "Select the cash/bank account to refund from", variant: "destructive" });
      return;
    }
    setCancelling(true);
    const payload = { reason: "Cancelled by user" };
    if (hasBalance) {
      payload.settlement_mode = settlementMode;
      if (settlementMode === "REFUND") payload.refund_ledger = parseInt(refundLedger);
    }
    const res = await cancelSchemeEnrollment(uuid, payload);
    if (res.success) {
      toast({ title: "Enrollment cancelled" });
      setCancelOpen(false);
      load();
    } else {
      const msg = typeof res.error === "object" ? Object.values(res.error).flat().join(", ") : res.error;
      toast({ title: "Cancel failed", description: msg, variant: "destructive" });
    }
    setCancelling(false);
  };

  if (!data) return <div className="p-4">Loading...</div>;

  const e = data.enrollment;
  const payments = data.payments || [];
  const inr = (v) => `₹${Number(v).toLocaleString("en-IN")}`;

  const paymentColumns = [
    { accessorKey: "installment_number", header: "#" },
    { accessorKey: "date", header: "Date" },
    { accessorKey: "payment_no", header: "Payment #" },
    { accessorKey: "amount", header: "Amount", cell: ({ row }) => inr(row.original.amount) },
    { accessorKey: "payment_mode", header: "Mode" },
    { accessorKey: "payment_ledger_name", header: "Account" },
    { accessorKey: "gold_weight_added", header: "Gold (g)",
      cell: ({ row }) => {
        const wt = Number(row.original.gold_weight_added);
        return wt > 0 ? `${wt.toFixed(3)}g` : "-";
      }
    },
    { accessorKey: "gold_rate_at_payment", header: "Rate/g",
      cell: ({ row }) => {
        const r = Number(row.original.gold_rate_at_payment);
        return r > 0 ? inr(r) : "-";
      }
    },
    { accessorKey: "voucher_no", header: "Voucher" },
  ];

  return (
    <div className="space-y-4">
      <Button variant="ghost" onClick={() => navigate("/scheme/enrollments")}><ArrowLeft className="size-4 mr-1" /> Back</Button>

      {/* Summary Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{e.enrollment_no} — {e.customer_name}</CardTitle>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[e.status] || ""}`}>{e.status}</span>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div><span className="text-muted-foreground">Scheme</span><p className="font-medium">{e.scheme_name}</p></div>
            <div><span className="text-muted-foreground">Type</span><p className="font-medium">{e.scheme_type}</p></div>
            <div><span className="text-muted-foreground">Start Date</span><p className="font-medium">{e.start_date}</p></div>
            <div><span className="text-muted-foreground">Maturity Date</span><p className="font-medium">{e.maturity_date}</p></div>
            <div><span className="text-muted-foreground">Installment</span><p className="font-medium">{inr(e.installment_amount)}</p></div>
            <div><span className="text-muted-foreground">Total Paid</span><p className="font-medium text-green-700">{inr(e.total_paid)}</p></div>
            <div><span className="text-muted-foreground">Payments Made</span><p className="font-medium">{e.payments_made} / {e.scheme_type === "LUMPSUM" ? "1" : (e.payments_made + e.remaining_installments)}</p></div>
            {Number(e.gold_accumulated_wt) > 0 && (
              <div><span className="text-muted-foreground">Gold Accumulated</span><p className="font-medium text-yellow-700">{Number(e.gold_accumulated_wt).toFixed(3)}g</p></div>
            )}
            {e.locked_gold_rate && (
              <div><span className="text-muted-foreground">Locked Gold Rate</span><p className="font-medium">{inr(e.locked_gold_rate)}/g</p></div>
            )}
          </div>

          {/* Benefit */}
          {benefit?.gold_benefit && (
            <div className="mt-4 p-3 bg-green-50 rounded-lg border border-green-200">
              <p className="font-medium text-green-800">
                Current Benefit: {benefit.gold_benefit.lc_discount_pct}% off Making Charges
                ({benefit.gold_benefit.tier})
              </p>
              {benefit.diamond_benefit && (
                <p className="text-sm text-green-700 mt-1">
                  Diamond: {benefit.diamond_benefit.lc_discount_pct}% off LC + {benefit.diamond_benefit.value_discount_pct}% off value
                </p>
              )}
            </div>
          )}
          {!benefit?.gold_benefit && e.months_completed < 6 && (
            <p className="mt-4 text-sm text-muted-foreground">
              No benefit yet — minimum 6 months required.
            </p>
          )}

          {/* Actions */}
          <div className="mt-4 flex gap-2">
            {e.status === "ACTIVE" && (
              <Button onClick={() => navigate(`/scheme/enrollments/${uuid}/pay`)}>
                <CreditCard className="size-4 mr-1" /> Record Payment
              </Button>
            )}
            {(e.status === "ACTIVE" || e.status === "MATURED") && (
              <Button variant="outline" onClick={openCancel}>
                <XCircle className="size-4 mr-1" /> Cancel Enrollment
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Cancel Enrollment</DialogTitle></DialogHeader>
          {Number(e.total_paid) > 0 ? (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                The customer has paid {inr(e.total_paid)} into this scheme. Choose how to settle that amount.
              </p>
              <div>
                <Label>What to do with the paid amount *</Label>
                <Select value={settlementMode} onValueChange={setSettlementMode}>
                  <SelectTrigger><SelectValue placeholder="Select settlement" /></SelectTrigger>
                  <SelectContent>
                    {SETTLEMENT_MODES.map(([v, label]) => (
                      <SelectItem key={v} value={v}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {settlementMode === "REFUND" && (
                <div>
                  <Label>Refund from (cash/bank account) *</Label>
                  <Select value={String(refundLedger)} onValueChange={setRefundLedger}>
                    <SelectTrigger><SelectValue placeholder="Select cash/bank account" /></SelectTrigger>
                    <SelectContent>
                      {cashBankLedgers.map((l) => (
                        <SelectItem key={l.id} value={String(l.id)}>{l.ac_name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No payments have been made. The enrollment will simply be cancelled.
            </p>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCancelOpen(false)} disabled={cancelling}>Keep enrollment</Button>
            <Button variant="destructive" onClick={confirmCancel} disabled={cancelling}>
              {cancelling ? "Cancelling…" : "Cancel enrollment"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Payment History */}
      <Card>
        <CardHeader><CardTitle>Payment History</CardTitle></CardHeader>
        <CardContent>
          <DataTable columns={paymentColumns} data={payments} />
        </CardContent>
      </Card>
    </div>
  );
}
