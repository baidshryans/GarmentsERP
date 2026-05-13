import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { ChevronDown, ChevronRight, CheckCircle, XCircle, Calculator } from "lucide-react";
import {
  fetchDepreciationSuggestions, generateDepreciationSuggestion,
  updateSuggestionLine, approveDepreciationSuggestion, rejectDepreciationSuggestion,
} from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

const STATUS_COLORS = {
  PENDING:  "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-green-100 text-green-800",
  REJECTED: "bg-red-100 text-red-800",
};

const MONTHS = ["", "April", "May", "June", "July", "August", "September",
  "October", "November", "December", "January", "February", "March"];

function fyOptions() {
  const now = new Date();
  const yr  = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  return Array.from({ length: 3 }, (_, i) => {
    const y = yr - i;
    return {
      value: `${y}-${y + 1}`,
      from:  `${y}-04-01`,
      to:    `${y + 1}-03-31`,
      label: `FY ${String(y).slice(-2)}-${String(y + 1).slice(-2)}`,
    };
  });
}

export default function DepreciationWorksheetPage() {
  const { toast } = useToast();
  const fyList = fyOptions();

  const [fy, setFy]                 = useState(fyList[0].value);
  const [periodFrom, setPeriodFrom] = useState(fyList[0].from);
  const [periodTo, setPeriodTo]     = useState(fyList[0].to);
  const [label, setLabel]           = useState(`FY ${fyList[0].label.slice(3)} Annual Depreciation`);

  const [pending, setPending]       = useState(null);   // current PENDING suggestion
  const [history, setHistory]       = useState([]);     // APPROVED/REJECTED
  const [histOpen, setHistOpen]     = useState(false);

  const [generating, setGenerating] = useState(false);
  const [approving, setApproving]   = useState(false);

  const loadSuggestions = useCallback(async () => {
    const r = await fetchDepreciationSuggestions();
    if (!r.success) return;
    const all = Array.isArray(r.data) ? r.data : (r.data.results || []);
    setPending(all.find(s => s.status === "PENDING") || null);
    setHistory(all.filter(s => s.status !== "PENDING"));
  }, []);

  useEffect(() => { loadSuggestions(); }, [loadSuggestions]);

  function onFyChange(val) {
    setFy(val);
    const found = fyList.find(f => f.value === val);
    if (found) {
      setPeriodFrom(found.from);
      setPeriodTo(found.to);
      setLabel(`FY ${found.label.slice(3)} Annual Depreciation`);
    }
  }

  async function handleGenerate() {
    if (!label.trim()) { toast({ title: "Enter a label." }); return; }
    setGenerating(true);
    const r = await generateDepreciationSuggestion({
      period_from: periodFrom,
      period_to:   periodTo,
      label:       label.trim(),
    });
    setGenerating(false);
    if (r.success) {
      toast({ title: "Suggestion generated." });
      setPending(r.data);
    } else {
      toast({ title: "Error", description: r.error?.detail || JSON.stringify(r.error), variant: "destructive" });
    }
  }

  async function handleLineChange(lineId, newAmount) {
    const r = await updateSuggestionLine(lineId, { approved_amount: newAmount });
    if (r.success) {
      setPending(prev => {
        if (!prev) return prev;
        const updatedLines = prev.lines.map(l =>
          l.id === lineId ? { ...l, approved_amount: newAmount, overridden: r.data.overridden } : l
        );
        const total = updatedLines.reduce((s, l) => s + parseFloat(l.approved_amount || 0), 0);
        return { ...prev, lines: updatedLines, total_amount: total.toFixed(2) };
      });
    }
  }

  async function handleApprove() {
    if (!pending) return;
    setApproving(true);
    const r = await approveDepreciationSuggestion(pending.id);
    setApproving(false);
    if (r.success) {
      toast({ title: `Approved. Voucher: ${r.data.voucher_no}` });
      setPending(null);
      setHistory(h => [r.data, ...h]);
    } else {
      toast({ title: "Error", description: r.error?.detail || JSON.stringify(r.error), variant: "destructive" });
    }
  }

  async function handleReject() {
    if (!pending) return;
    const r = await rejectDepreciationSuggestion(pending.id);
    if (r.success) {
      toast({ title: "Suggestion rejected." });
      loadSuggestions();
    } else {
      toast({ title: "Error", description: r.error?.detail || r.error, variant: "destructive" });
    }
  }

  const fmt = n => Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 });

  return (
    <div className="p-4 space-y-6">
      <h2 className="text-lg font-semibold">Depreciation Worksheet</h2>

      {/* Generate form */}
      {!pending && (
        <div className="rounded-lg border p-4 space-y-4 bg-card">
          <h3 className="text-sm font-medium">Generate Depreciation Suggestion</h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="space-y-1">
              <Label className="text-xs">Financial Year</Label>
              <Select value={fy} onValueChange={onFyChange}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {fyList.map(f => <SelectItem key={f.value} value={f.value}>{f.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Period From</Label>
              <Input type="date" value={periodFrom} onChange={e => setPeriodFrom(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Period To</Label>
              <Input type="date" value={periodTo} onChange={e => setPeriodTo(e.target.value)} />
            </div>
            <div className="space-y-1 col-span-2 sm:col-span-4">
              <Label className="text-xs">Suggestion Label</Label>
              <Input value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. FY 24-25 Annual Depreciation" />
            </div>
          </div>
          <Button onClick={handleGenerate} disabled={generating} size="sm">
            <Calculator className="size-4 mr-1.5" />
            {generating ? "Calculating…" : "Generate Suggestion"}
          </Button>
          <p className="text-xs text-muted-foreground">
            This will compute depreciation for all active assets. No journal entry is created until you approve.
          </p>
        </div>
      )}

      {/* Pending suggestion worksheet */}
      {pending && (
        <div className="rounded-lg border bg-card space-y-0">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <div>
              <p className="font-semibold text-sm">{pending.label}</p>
              <p className="text-xs text-muted-foreground">{pending.period_from} → {pending.period_to}</p>
            </div>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS.PENDING}`}>PENDING</span>
          </div>

          {/* Worksheet table */}
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Asset</TableHead>
                  <TableHead>Method</TableHead>
                  <TableHead className="text-right">Cost</TableHead>
                  <TableHead className="text-right">Opening WDV</TableHead>
                  <TableHead className="text-right">Calc. Dep.</TableHead>
                  <TableHead className="text-right w-36">Amount (₹)</TableHead>
                  <TableHead>Narration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pending.lines.map(line => (
                  <TableRow key={line.id} className={line.overridden ? "bg-amber-50/60" : ""}>
                    <TableCell>
                      <p className="font-mono text-xs">{line.asset_code}</p>
                      <p className="text-sm">{line.asset_name}</p>
                    </TableCell>
                    <TableCell className="text-xs">
                      {line.asset_method === "WDV"
                        ? `WDV ${line.asset_rate_or_life}%`
                        : `SLM ${line.asset_rate_or_life}yr`}
                    </TableCell>
                    <TableCell className="text-right text-sm">₹{fmt(line.purchase_cost)}</TableCell>
                    <TableCell className="text-right text-sm">₹{fmt(line.opening_wdv)}</TableCell>
                    <TableCell className="text-right text-sm text-muted-foreground">₹{fmt(line.calculated_amount)}</TableCell>
                    <TableCell className="text-right">
                      <AmountInput
                        value={line.approved_amount}
                        overridden={line.overridden}
                        onChange={val => handleLineChange(line.id, val)}
                      />
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-48 truncate" title={line.narration}>
                      {line.narration}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-4 py-3 border-t bg-muted/30">
            <div className="text-sm">
              <span className="text-muted-foreground">Total Depreciation: </span>
              <span className="font-bold text-base">₹{fmt(pending.total_amount)}</span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleReject} className="text-destructive border-destructive/30">
                <XCircle className="size-4 mr-1" /> Reject
              </Button>
              <Button size="sm" onClick={handleApprove} disabled={approving}>
                <CheckCircle className="size-4 mr-1" />
                {approving ? "Posting…" : "Approve & Post Journal Entry"}
              </Button>
            </div>
          </div>
          <p className="text-xs text-muted-foreground px-4 pb-3">
            Highlighted rows have been manually overridden. Approving will create a DEPR journal entry in the accounting module.
          </p>
        </div>
      )}

      {/* Past suggestions */}
      {history.length > 0 && (
        <div className="rounded-lg border bg-card">
          <button
            className="flex items-center gap-2 px-4 py-3 w-full text-left text-sm font-medium"
            onClick={() => setHistOpen(o => !o)}
          >
            {histOpen ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
            Past Suggestions ({history.length})
          </button>
          {histOpen && (
            <div className="border-t">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Label</TableHead>
                    <TableHead>Period</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Voucher</TableHead>
                    <TableHead>Approved By</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map(s => (
                    <TableRow key={s.id}>
                      <TableCell className="text-sm">{s.label}</TableCell>
                      <TableCell className="text-xs">{s.period_from} → {s.period_to}</TableCell>
                      <TableCell className="text-right text-sm">₹{fmt(s.total_amount)}</TableCell>
                      <TableCell>
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[s.status] || ""}`}>
                          {s.status}
                        </span>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{s.voucher_no || "—"}</TableCell>
                      <TableCell className="text-xs">{s.approved_by_name || "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Inline editable amount input — debounced save on blur */
function AmountInput({ value, overridden, onChange }) {
  const [local, setLocal] = useState(String(value));

  useEffect(() => { setLocal(String(value)); }, [value]);

  function handleBlur() {
    const parsed = parseFloat(local);
    if (!isNaN(parsed) && parsed >= 0) {
      onChange(parsed.toFixed(2));
    } else {
      setLocal(String(value));
    }
  }

  return (
    <Input
      type="number"
      min="0"
      step="0.01"
      value={local}
      onChange={e => setLocal(e.target.value)}
      onBlur={handleBlur}
      className={`w-32 text-right ${overridden ? "border-amber-400 bg-amber-50" : ""}`}
    />
  );
}
