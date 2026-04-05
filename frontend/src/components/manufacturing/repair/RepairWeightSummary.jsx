const fmt = (n) => (parseFloat(n) || 0).toFixed(3);

export default function RepairWeightSummary({ receivedGw, returnedGw, losses }) {
  const received  = parseFloat(receivedGw)  || 0;
  const returned  = parseFloat(returnedGw)  || 0;
  const namedLoss = losses.reduce((sum, r) => sum + (parseFloat(r.loss_wt) || 0), 0);
  const balance   = received - returned - namedLoss;

  const balanceColor =
    Math.abs(balance) <= 0.005
      ? "text-green-600"
      : balance > 0.005
      ? "text-amber-600"
      : "text-red-600";

  const balanceLabel =
    Math.abs(balance) <= 0.005 ? "Reconciled" : balance > 0.005 ? "Unaccounted" : "Error";

  return (
    <div className="grid grid-cols-4 gap-3">
      <Cell label="Received (gw)" value={fmt(received)} />
      <Cell label="Returned (gw)" value={fmt(returned)} />
      <Cell label="Named Losses (g)" value={fmt(namedLoss)} />
      <div className="rounded-lg border bg-muted/10 p-3 text-center">
        <p className="text-[10px] text-muted-foreground mb-1">Balance</p>
        <p className={`text-lg font-semibold tabular-nums ${balanceColor}`}>{fmt(balance)}</p>
        <p className={`text-[10px] font-medium ${balanceColor}`}>{balanceLabel}</p>
      </div>
    </div>
  );
}

function Cell({ label, value }) {
  return (
    <div className="rounded-lg border bg-muted/10 p-3 text-center">
      <p className="text-[10px] text-muted-foreground mb-1">{label}</p>
      <p className="text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}
