const inr = (v) => `₹${Number(v || 0).toLocaleString("en-IN")}`;

const MODE_LABELS = {
  CASH: "Cash",
  BANK: "Bank",
  UPI: "UPI",
  CHEQUE: "Cheque",
  CARD: "Card",
};

export default function PaymentTimeline({ payments }) {
  if (!payments || payments.length === 0) {
    return <p className="text-sm text-muted-foreground text-center py-4">No payments yet.</p>;
  }

  return (
    <div className="space-y-3">
      {payments.map((p, idx) => (
        <div key={p.payment_no || idx} className="flex items-start gap-3">
          {/* Timeline dot and line */}
          <div className="flex flex-col items-center">
            <div className="w-2.5 h-2.5 rounded-full bg-primary mt-1.5" />
            {idx < payments.length - 1 && <div className="w-px flex-1 bg-border mt-1" />}
          </div>

          {/* Payment info */}
          <div className="flex-1 pb-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">
                #{p.installment_number} � {inr(p.amount)}
              </p>
              <span className="text-xs px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {MODE_LABELS[p.payment_mode] || p.payment_mode}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">{p.date}</p>
            {p.gold_weight_added > 0 && (
              <p className="text-xs text-yellow-700 mt-0.5">
                +{Number(p.gold_weight_added).toFixed(3)}g gold
              </p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
