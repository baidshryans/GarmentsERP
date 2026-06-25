import { useEffect, useState } from "react";
import { formatNumber } from "@/lib/format";
import { useNavigate, useParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Pencil, Trash2, Send, PackageCheck, XCircle, Loader2, ArrowLeft } from "lucide-react";
import {
  fetchInterRetailTransfer, deleteInterRetailTransfer,
  sendInterRetailTransfer, receiveInterRetailTransfer, cancelInterRetailTransfer,
} from "@/services/apiService";

const STATUS_STYLES = {
  draft:      "bg-muted text-muted-foreground",
  in_transit: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  received:   "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  cancelled:  "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
};

const fmt = (v) => formatNumber(v, { decimals: 2 });
const fmtWt = (v) => formatNumber(v, { decimals: 3 });

export default function InterRetailTransferDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [v, setV] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    const res = await fetchInterRetailTransfer(id);
    if (res.success) setV(res.data);
    else setError(typeof res.error === "string" ? res.error : JSON.stringify(res.error));
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  const runAction = async (name, fn, confirmMsg) => {
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setBusy(true); setError("");
    const res = await fn(id);
    setBusy(false);
    if (res.success) await load();
    else setError(typeof res.error === "string" ? res.error : (res.error?.detail || JSON.stringify(res.error)));
  };

  const onDelete = async () => {
    if (!window.confirm("Delete this draft voucher?")) return;
    setBusy(true); setError("");
    const res = await deleteInterRetailTransfer(id);
    setBusy(false);
    if (res.success) navigate("/inventory/inter-retail-transfer");
    else setError(typeof res.error === "string" ? res.error : (res.error?.detail || JSON.stringify(res.error)));
  };

  if (loading) return <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Loading…</div>;
  if (!v) return <div className="text-sm text-destructive">{error || "Not found."}</div>;

  const totalValue = (v.items || []).reduce((s, it) => s + Number(it.transfer_value || 0), 0);
  const isDraft = v.status === "draft";
  const isInTransit = v.status === "in_transit";
  const isReceived = v.status === "received";

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link to="/inventory/inter-retail-transfer">
            <Button size="icon" variant="ghost" className="h-8 w-8"><ArrowLeft className="size-4" /></Button>
          </Link>
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-3">
              <span className="font-mono">{v.voucher_no}</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium uppercase ${STATUS_STYLES[v.status] || "bg-muted"}`}>{v.status}</span>
            </h2>
            <p className="text-xs text-muted-foreground">Transfer Date: {v.transfer_date}{v.received_at && ` · Received: ${new Date(v.received_at).toLocaleString()}`}</p>
          </div>
        </div>
        <div className="flex gap-2">
          {isDraft && (
            <>
              <Link to={`/inventory/inter-retail-transfer/${id}/edit`}>
                <Button size="sm" variant="outline" className="gap-1.5"><Pencil className="size-3.5" />Edit</Button>
              </Link>
              <Button size="sm" variant="destructive" onClick={onDelete} disabled={busy} className="gap-1.5">
                <Trash2 className="size-3.5" />Delete
              </Button>
              <Button size="sm" onClick={() => runAction("send", sendInterRetailTransfer, "Mark as sent (in transit)?")}
                      disabled={busy} className="gap-1.5">
                <Send className="size-3.5" />Send
              </Button>
            </>
          )}
          {isInTransit && (
            <Button size="sm" onClick={() => runAction("receive", receiveInterRetailTransfer, "Mark as received? This finalises the transfer.")}
                    disabled={busy} className="gap-1.5">
              <PackageCheck className="size-3.5" />Receive
            </Button>
          )}
          {(isDraft || isInTransit) && (
            <Button size="sm" variant="outline" onClick={() => runAction("cancel", cancelInterRetailTransfer, "Cancel this voucher?")}
                    disabled={busy} className="gap-1.5">
              <XCircle className="size-3.5" />Cancel
            </Button>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-3 rounded-lg border border-border">
          <p className="text-xs text-muted-foreground">From Retail</p>
          <p className="font-medium mt-0.5">{v.from_retail_name || v.from_retail}</p>
        </div>
        <div className="p-3 rounded-lg border border-border">
          <p className="text-xs text-muted-foreground">To Retail</p>
          <p className="font-medium mt-0.5">{v.to_retail_name || v.to_retail}</p>
        </div>
        <div className="p-3 rounded-lg border border-border">
          <p className="text-xs text-muted-foreground">Total Transfer Value</p>
          <p className="font-semibold text-lg mt-0.5 tabular-nums">₹ {fmt(totalValue)}</p>
        </div>
      </div>

      {v.narration && (
        <div className="p-3 rounded-lg border border-border bg-muted/10">
          <p className="text-xs text-muted-foreground">Narration</p>
          <p className="text-sm">{v.narration}</p>
        </div>
      )}

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left w-12">#</th>
              <th className="px-3 py-2 text-left">Item</th>
              <th className="px-3 py-2 text-right">Pcs</th>
              <th className="px-3 py-2 text-right">GW</th>
              <th className="px-3 py-2 text-right">CT</th>
              <th className="px-3 py-2 text-right">Primary Qty</th>
              <th className="px-3 py-2 text-right">Rate (₹)</th>
              <th className="px-3 py-2 text-right">Value (₹)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {(v.items || []).map((it, i) => (
              <tr key={it.id || i}>
                <td className="px-3 py-2 text-muted-foreground">{i + 1}</td>
                <td className="px-3 py-2">{it.item_name} <span className="text-[10px] text-muted-foreground">[{it.item_type}]</span></td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(it.qty_pcs)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtWt(it.qty_gw)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtWt(it.qty_ct)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtWt(it.primary_qty)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmt(it.source_avg_rate)}</td>
                <td className="px-3 py-2 text-right tabular-nums font-medium">{fmt(it.transfer_value)}</td>
              </tr>
            ))}
          </tbody>
          <tfoot className="bg-muted/30">
            <tr>
              <td colSpan={7} className="px-3 py-2 text-right font-semibold">Total</td>
              <td className="px-3 py-2 text-right font-semibold tabular-nums">{fmt(totalValue)}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {isReceived && (
        <p className="text-xs text-muted-foreground">
          Inventory has been attributed to the destination retail. Linked barcodes/unbarcoded stock had their retail updated.
        </p>
      )}
      {isInTransit && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Stock is in transit — still attributed to the source retail in closing-stock calculations.
        </p>
      )}
    </div>
  );
}
