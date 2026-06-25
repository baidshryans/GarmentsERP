import { useEffect, useState } from "react";
import { formatNumber } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { CheckCircle, XCircle, Calculator } from "lucide-react";
import {
  generateDepreciationSuggestion, postDepreciation,
} from "@/services/apiService";
import { useToast } from "@/hooks/use-toast";

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

  // worksheet held entirely in local state — never persisted as a "suggestion"
  const [worksheet, setWorksheet]   = useState(null);

  const [generating, setGenerating] = useState(false);
  const [posting, setPosting]       = useState(false);

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
      const lines = (r.data.lines || []).map(l => ({
        ...l,
        overridden: false,
      }));
      setWorksheet({ ...r.data, lines });
    } else {
      toast({ title: "Error", description: r.error?.detail || JSON.stringify(r.error), variant: "destructive" });
    }
  }

  function handleLineChange(assetId, newAmount) {
    setWorksheet(prev => {
      if (!prev) return prev;
      const updatedLines = prev.lines.map(l => {
        if (l.asset_id !== assetId) return l;
        return {
          ...l,
          approved_amount: newAmount,
          overridden: parseFloat(newAmount) !== parseFloat(l.calculated_amount),
        };
      });
      const total = updatedLines.reduce((s, l) => s + parseFloat(l.approved_amount || 0), 0);
      return { ...prev, lines: updatedLines, total_amount: total.toFixed(2) };
    });
  }

  async function handlePost() {
    if (!worksheet) return;
    setPosting(true);
    const r = await postDepreciation({
      label:     worksheet.label,
      period_to: worksheet.period_to,
      lines:     worksheet.lines.map(l => ({
        asset_id:        l.asset_id,
        approved_amount: l.approved_amount,
        narration:       l.narration,
      })),
    });
    setPosting(false);
    if (r.success) {
      toast({ title: `Posted. Voucher: ${r.data.voucher_no}` });
      setWorksheet(null);
    } else {
      toast({ title: "Error", description: r.error?.detail || JSON.stringify(r.error), variant: "destructive" });
    }
  }

  function handleDiscard() {
    setWorksheet(null);
  }

  const fmt = n => formatNumber(n, { minDecimals: 2 });

  return (
    <div className="p-4 space-y-6">
      <h2 className="text-lg font-semibold">Depreciation Worksheet</h2>

      {/* Generate form */}
      {!worksheet && (
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
              <Label className="text-xs">Narration Label</Label>
              <Input value={label} onChange={e => setLabel(e.target.value)} placeholder="e.g. FY 24-25 Annual Depreciation" />
            </div>
          </div>
          <Button onClick={handleGenerate} disabled={generating} size="sm">
            <Calculator className="size-4 mr-1.5" />
            {generating ? "Calculating…" : "Generate Suggestion"}
          </Button>
          <p className="text-xs text-muted-foreground">
            This computes depreciation for all active assets. Nothing is saved until you post the journal entry.
          </p>
        </div>
      )}

      {/* Worksheet */}
      {worksheet && (
        <div className="rounded-lg border bg-card space-y-0">
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <div>
              <p className="font-semibold text-sm">{worksheet.label}</p>
              <p className="text-xs text-muted-foreground">{worksheet.period_from} → {worksheet.period_to}</p>
            </div>
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">DRAFT</span>
          </div>

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
                {worksheet.lines.map(line => (
                  <TableRow key={line.asset_id} className={line.overridden ? "bg-amber-50/60" : ""}>
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
                        onChange={val => handleLineChange(line.asset_id, val)}
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

          <div className="flex items-center justify-between px-4 py-3 border-t bg-muted/30">
            <div className="text-sm">
              <span className="text-muted-foreground">Total Depreciation: </span>
              <span className="font-bold text-base">₹{fmt(worksheet.total_amount)}</span>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleDiscard} className="text-destructive border-destructive/30">
                <XCircle className="size-4 mr-1" /> Discard
              </Button>
              <Button size="sm" onClick={handlePost} disabled={posting}>
                <CheckCircle className="size-4 mr-1" />
                {posting ? "Posting…" : "Post Journal Entry"}
              </Button>
            </div>
          </div>
          <p className="text-xs text-muted-foreground px-4 pb-3">
            Highlighted rows have been manually overridden. Posting will create a DEPR journal entry in the accounting module. The worksheet itself is not saved.
          </p>
        </div>
      )}
    </div>
  );
}

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
