import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import apiClient from "@/services/apiClient";
import { ChevronDown, ChevronRight, CheckCircle2, Clock, ShieldCheck, ShieldOff } from "lucide-react";
import { useToast } from "@/hooks/use-toast";

const today = new Date().toISOString().split("T")[0];

const VOUCHER_TYPE_LABELS = {
  JRNL: "Journal", PMNT: "Payment", RCPT_SALE: "Receipt", "RCPT-SALE": "Receipt",
  CONTRA: "Contra", SALE: "Sale", "SALE-RET": "Sale Return",
  "PURC-SC": "Purchase", "PURC-RET": "Purchase Return",
};

const fmt = (v) =>
  Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function AuditQueue() {
  const { toast } = useToast();

  const [fromDate, setFromDate] = useState(today);
  const [toDate,   setToDate]   = useState(today);
  const [show,     setShow]     = useState("unaudited");
  const [report,   setReport]   = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");

  // Selection
  const [selected, setSelected] = useState(new Set());
  const [notes,    setNotes]    = useState("");
  const [saving,   setSaving]   = useState(false);

  // Row expansion
  const [expanded, setExpanded] = useState({});

  // ── Fetch ─────────────────────────────────────────────────────────────────
  const fetchReport = async () => {
    setError(""); setLoading(true); setSelected(new Set()); setExpanded({});
    try {
      const res = await apiClient.get(
        `/accounting/api/audit-queue/?from_date=${fromDate}&to_date=${toDate}&show=${show}`
      );
      setReport(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load audit queue.");
    }
    setLoading(false);
  };

  // ── Selection helpers ─────────────────────────────────────────────────────
  const toggleOne = (id) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const allIds  = (report?.vouchers ?? []).map((v) => v.id);
  const allSelected = allIds.length > 0 && allIds.every((id) => selected.has(id));
  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(allIds));

  // ── Mark as audited ───────────────────────────────────────────────────────
  const handleMark = async () => {
    if (!selected.size) return;
    setSaving(true);
    try {
      const res = await apiClient.post("/accounting/api/audit-mark/", {
        voucher_ids: [...selected],
        notes,
      });
      toast({ title: `Marked ${res.data.marked} voucher(s) as audited.` });
      setNotes("");
      await fetchReport();
    } catch (e) {
      toast({ title: e.response?.data?.error || "Failed to mark.", variant: "destructive" });
    }
    setSaving(false);
  };

  // ── Unmark ────────────────────────────────────────────────────────────────
  const handleUnmark = async () => {
    if (!selected.size) return;
    setSaving(true);
    try {
      const res = await apiClient.delete("/accounting/api/audit-mark/", {
        data: { voucher_ids: [...selected] },
      });
      toast({ title: `Unmarked ${res.data.unmarked} voucher(s).` });
      await fetchReport();
    } catch (e) {
      toast({ title: e.response?.data?.error || "Failed to unmark.", variant: "destructive" });
    }
    setSaving(false);
  };

  const toggle = (vno) =>
    setExpanded((prev) => ({ ...prev, [vno]: !prev[vno] }));

  const anyAudited   = [...selected].some((id) => report?.vouchers.find((v) => v.id === id)?.is_audited);
  const anyUnaudited = [...selected].some((id) => !report?.vouchers.find((v) => v.id === id)?.is_audited);

  return (
    <div className="flex flex-col gap-5 p-4">

      {/* ── Filter bar ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Show</Label>
          <Select value={show} onValueChange={setShow}>
            <SelectTrigger className="h-9 w-36 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="unaudited">Unaudited</SelectItem>
              <SelectItem value="audited">Audited</SelectItem>
              <SelectItem value="all">All</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button size="sm" onClick={fetchReport} className="h-9">Load</Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* ── Bulk action bar (visible when items are selected) ─────────────── */}
      {report && selected.size > 0 && (
        <div className="flex flex-wrap items-end gap-3 p-3 rounded-lg border border-primary/30 bg-primary/5">
          <div className="flex flex-col gap-1 flex-1 min-w-48">
            <Label className="text-xs">Audit Notes (optional)</Label>
            <Textarea
              rows={1}
              className="text-sm resize-none"
              placeholder="e.g. Verified against physical records…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          <div className="flex gap-2">
            {anyUnaudited && (
              <Button size="sm" className="gap-1.5 h-9" onClick={handleMark} disabled={saving}>
                <ShieldCheck className="size-4" />
                {saving ? "Saving…" : `Mark ${selected.size} Audited`}
              </Button>
            )}
            {anyAudited && (
              <Button size="sm" variant="outline" className="gap-1.5 h-9" onClick={handleUnmark} disabled={saving}>
                <ShieldOff className="size-4" />
                {saving ? "Saving…" : `Unmark ${selected.size}`}
              </Button>
            )}
          </div>
          <span className="text-xs text-muted-foreground self-end pb-2">
            {selected.size} selected
          </span>
        </div>
      )}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
        </div>
      )}

      {report && !loading && (
        <div className="flex flex-col gap-2">
          {/* Summary row */}
          <div className="flex items-center justify-between text-sm text-muted-foreground px-1">
            <span>{report.count} voucher(s) — {report.from_date} to {report.to_date}</span>
            <div className="flex items-center gap-3">
              {allIds.length > 0 && (
                <label className="flex items-center gap-1.5 cursor-pointer text-xs">
                  <Checkbox checked={allSelected} onCheckedChange={toggleAll} className="size-3.5" />
                  Select all
                </label>
              )}
            </div>
          </div>

          {report.vouchers.length === 0 && (
            <div className="text-center py-16 text-muted-foreground border rounded-lg">
              No vouchers found for this filter.
            </div>
          )}

          {/* Voucher rows */}
          {report.vouchers.map((v) => (
            <div
              key={v.id}
              className={`rounded-lg border overflow-hidden transition-colors ${
                v.is_audited ? "border-green-200 dark:border-green-800" : "border-border"
              } ${selected.has(v.id) ? "ring-2 ring-primary/40" : ""}`}
            >
              {/* Header row */}
              <div className="flex items-center gap-2 px-3 py-2.5 bg-muted/30 hover:bg-muted/50 transition-colors">
                <Checkbox
                  checked={selected.has(v.id)}
                  onCheckedChange={() => toggleOne(v.id)}
                  className="size-4 shrink-0"
                />

                <button
                  className="flex items-center gap-2 flex-1 min-w-0 text-left"
                  onClick={() => toggle(v.id)}
                >
                  {expanded[v.id]
                    ? <ChevronDown className="size-4 text-muted-foreground shrink-0" />
                    : <ChevronRight className="size-4 text-muted-foreground shrink-0" />
                  }
                  <span className="font-mono text-xs text-muted-foreground w-28 shrink-0">{v.voucher_no}</span>
                  <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-medium shrink-0">
                    {VOUCHER_TYPE_LABELS[v.voucher_type] ?? v.voucher_type}
                  </span>
                  <span className="text-sm font-medium truncate">{v.narration}</span>
                  <span className="ml-auto text-sm font-semibold shrink-0">{fmt(v.amount)}</span>
                  <span className="text-xs text-muted-foreground shrink-0 w-24 text-right">{v.date}</span>
                </button>

                {/* Audit badge */}
                {v.is_audited ? (
                  <span className="flex items-center gap-1 text-[11px] font-medium text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/30 px-2 py-0.5 rounded-full border border-green-200 dark:border-green-700 shrink-0">
                    <CheckCircle2 className="size-3" />
                    {v.audited_by} · {v.audited_at}
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[11px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/30 px-2 py-0.5 rounded-full border border-amber-200 dark:border-amber-700 shrink-0">
                    <Clock className="size-3" />
                    Pending
                  </span>
                )}
              </div>

              {/* Expanded detail lines */}
              {expanded[v.id] && (
                <div>
                  <table className="w-full text-sm border-t border-border">
                    <thead>
                      <tr className="text-xs uppercase tracking-wider text-muted-foreground bg-muted/20">
                        <th className="px-4 py-2 text-left font-semibold">Account</th>
                        <th className="px-4 py-2 text-right font-semibold w-32">Debit</th>
                        <th className="px-4 py-2 text-right font-semibold w-32">Credit</th>
                        <th className="px-4 py-2 text-left font-semibold">Ref / Cheque</th>
                      </tr>
                    </thead>
                    <tbody>
                      {v.lines.map((line, i) => (
                        <tr key={i} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/10" : ""}`}>
                          <td className="px-4 py-1.5">{line.account}</td>
                          <td className="px-4 py-1.5 text-right tabular-nums">
                            {Number(line.debit) > 0 ? fmt(line.debit) : ""}
                          </td>
                          <td className="px-4 py-1.5 text-right tabular-nums">
                            {Number(line.credit) > 0 ? fmt(line.credit) : ""}
                          </td>
                          <td className="px-4 py-1.5 text-muted-foreground text-xs">
                            {line.ref_bill_no || line.chq_no || line.party_bank_name || ""}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {v.is_audited && v.audit_notes && (
                    <div className="px-4 py-2 text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border-t border-green-200 dark:border-green-800">
                      <span className="font-semibold">Audit note:</span> {v.audit_notes}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {!report && !loading && (
        <div className="text-center py-16 text-sm text-muted-foreground">
          Select a date range and click <strong>Load</strong> to view vouchers for audit.
        </div>
      )}
    </div>
  );
}
