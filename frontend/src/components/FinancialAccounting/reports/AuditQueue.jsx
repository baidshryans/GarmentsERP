import { useState } from "react";
import { formatNumber } from "@/lib/format";
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
import {
  ChevronDown, ChevronRight, CheckCircle2, Clock,
  ShieldCheck, ShieldOff, Paperclip, X, FileText,
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { isValidDateRange } from "@/lib/dateRange";

const today = new Date().toISOString().split("T")[0];
const fyStart = (() => {
  const now = new Date();
  const yr = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
  return `${yr}-04-01`;
})();

const VOUCHER_TYPE_LABELS = {
  JRNL: "Journal", PMNT: "Payment", RCPT_SALE: "Receipt", "RCPT-SALE": "Receipt",
  CONTRA: "Contra", SALE: "Sale", "SALE-RET": "Sale Return",
  "PURC-SC": "Purchase", "PURC-CO": "Purchase (OG)", "PURC-RET": "Purchase Return",
};

const fmt = (v) =>
  formatNumber(v, { decimals: 2 });

const isImage = (url) => /\.(jpe?g|png|gif|webp|bmp|svg)(\?|$)/i.test(url);

// ── Lightbox ──────────────────────────────────────────────────────────────────

function Lightbox({ url, onClose }) {
  if (!url) return null;
  return (
    <div
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <button
        className="absolute top-4 right-4 text-white/70 hover:text-white"
        onClick={onClose}
      >
        <X className="size-7" />
      </button>
      <img
        src={url}
        alt="Attachment"
        className="max-h-[90vh] max-w-[90vw] rounded-lg shadow-2xl object-contain"
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  );
}

// ── Attachment strip ──────────────────────────────────────────────────────────

function AttachmentStrip({ attachments, onPreview }) {
  if (!attachments?.length) return null;
  return (
    <div className="px-4 py-2 border-t border-border bg-muted/10 flex flex-wrap gap-2">
      {attachments.map((url, i) => (
        isImage(url) ? (
          <button
            key={i}
            type="button"
            onClick={() => onPreview(url)}
            className="rounded overflow-hidden border border-border hover:border-primary transition-colors"
            title="View attachment"
          >
            <img src={url} alt={`attachment-${i + 1}`} className="h-16 w-24 object-cover" />
          </button>
        ) : (
          <a
            key={i}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded border border-border bg-background text-xs hover:bg-muted/40 transition-colors"
          >
            <FileText className="size-3.5 text-muted-foreground" />
            Attachment {i + 1}
          </a>
        )
      ))}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function AuditQueue() {
  const { toast } = useToast();

  const [fromDate, setFromDate] = useState(fyStart);
  const [toDate,   setToDate]   = useState(today);
  const [show,     setShow]     = useState("unaudited");
  const [vtFilter, setVtFilter] = useState("all");   // voucher type filter
  const [report,   setReport]   = useState(null);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");

  // Selection
  const [selected, setSelected] = useState(new Set());
  const [notes,    setNotes]    = useState("");
  const [saving,   setSaving]   = useState(false);

  // Row expansion
  const [expanded, setExpanded] = useState({});

  // Lightbox
  const [lightbox, setLightbox] = useState(null);

  // ── Fetch ─────────────────────────────────────────────────────────────────
  const fetchReport = async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      setError("From date cannot be after To date.");
      return;
    }
    setError(""); setLoading(true); setSelected(new Set()); setExpanded({});
    try {
      const res = await apiClient.get(
        `/accounting/api/audit-queue/?from_date=${fromDate}&to_date=${toDate}&show=${show}`
      );
      setReport(res.data);
      setVtFilter("all");
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load audit queue.");
    }
    setLoading(false);
  };

  // ── Filtered vouchers (client-side type filter) ───────────────────────────
  const allVouchers     = report?.vouchers ?? [];
  const visibleVouchers = vtFilter === "all"
    ? allVouchers
    : allVouchers.filter((v) => v.voucher_type === vtFilter);

  // Available voucher types from the loaded report
  const availableTypes = [...new Set(allVouchers.map((v) => v.voucher_type))].sort();

  // ── Selection helpers ─────────────────────────────────────────────────────
  const toggleOne = (id) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const allIds      = visibleVouchers.map((v) => v.id);
  const allSelected = allIds.length > 0 && allIds.every((id) => selected.has(id));
  const toggleAll   = () => setSelected(allSelected ? new Set() : new Set(allIds));

  // ── Mark / Unmark ─────────────────────────────────────────────────────────
  const handleMark = async () => {
    if (!selected.size) return;
    setSaving(true);
    try {
      const res = await apiClient.post("/accounting/api/audit-mark/", {
        voucher_ids: [...selected], notes,
      });
      toast({ title: `Marked ${res.data.marked} voucher(s) as audited.` });
      setNotes("");
      await fetchReport();
    } catch (e) {
      toast({ title: e.response?.data?.error || "Failed to mark.", variant: "destructive" });
    }
    setSaving(false);
  };

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

  const anyAudited   = [...selected].some((id) => allVouchers.find((v) => v.id === id)?.is_audited);
  const anyUnaudited = [...selected].some((id) => !allVouchers.find((v) => v.id === id)?.is_audited);

  return (
    <div className="flex flex-col gap-5 p-4">

      <Lightbox url={lightbox} onClose={() => setLightbox(null)} />

      {/* ── Filter bar ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Show</Label>
          <Select value={show} onValueChange={setShow}>
            <SelectTrigger className="h-9 w-36 text-sm"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="unaudited">Unaudited</SelectItem>
              <SelectItem value="audited">Audited</SelectItem>
              <SelectItem value="all">All</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Voucher type filter — appears after report is loaded */}
        {availableTypes.length > 0 && (
          <div className="flex flex-col gap-1">
            <Label className="text-xs">Voucher Type</Label>
            <Select value={vtFilter} onValueChange={setVtFilter}>
              <SelectTrigger className="h-9 w-40 text-sm"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {availableTypes.map((t) => (
                  <SelectItem key={t} value={t}>
                    {VOUCHER_TYPE_LABELS[t] ?? t}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <Button size="sm" onClick={fetchReport} className="h-9">Load</Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* ── Bulk action bar ───────────────────────────────────────────────── */}
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
            <span>
              {visibleVouchers.length}
              {vtFilter !== "all" && ` of ${allVouchers.length}`}
              {" "}voucher(s) — {report.from_date} to {report.to_date}
            </span>
            <div className="flex items-center gap-3">
              {allIds.length > 0 && (
                <label className="flex items-center gap-1.5 cursor-pointer text-xs">
                  <Checkbox checked={allSelected} onCheckedChange={toggleAll} className="size-3.5" />
                  Select all
                </label>
              )}
            </div>
          </div>

          {visibleVouchers.length === 0 && (
            <div className="text-center py-16 text-muted-foreground border rounded-lg">
              No vouchers found for this filter.
            </div>
          )}

          {/* Voucher rows */}
          {visibleVouchers.map((v) => (
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
                    ? <ChevronDown  className="size-4 text-muted-foreground shrink-0" />
                    : <ChevronRight className="size-4 text-muted-foreground shrink-0" />
                  }
                  <span className="font-mono text-xs text-muted-foreground w-52 shrink-0 whitespace-nowrap">{v.voucher_no}</span>
                  <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded font-medium shrink-0">
                    {VOUCHER_TYPE_LABELS[v.voucher_type] ?? v.voucher_type}
                  </span>
                  <span className="text-sm font-medium truncate max-w-xs">{v.narration}</span>
                  <span className="ml-auto text-sm font-semibold shrink-0">{fmt(v.amount)}</span>
                  <span className="text-xs text-muted-foreground shrink-0 w-24 text-right">{v.date}</span>
                </button>

                {/* Attachment count badge */}
                {v.attachments?.length > 0 && (
                  <button
                    type="button"
                    title={`${v.attachments.length} attachment(s) — click to expand`}
                    onClick={() => toggle(v.id)}
                    className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground shrink-0"
                  >
                    <Paperclip className="size-3.5" />
                    <span>{v.attachments.length}</span>
                  </button>
                )}

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

              {/* Expanded detail */}
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
                            {Number(line.debit)  > 0 ? fmt(line.debit)  : ""}
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

                  {/* Audit note */}
                  {v.is_audited && v.audit_notes && (
                    <div className="px-4 py-2 text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 border-t border-green-200 dark:border-green-800">
                      <span className="font-semibold">Audit note:</span> {v.audit_notes}
                    </div>
                  )}

                  {/* Attachments */}
                  <AttachmentStrip attachments={v.attachments} onPreview={setLightbox} />
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
