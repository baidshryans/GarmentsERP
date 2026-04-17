import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Collapsible, CollapsibleContent, CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useToast } from "@/hooks/use-toast";
import { fetchRefineryReport } from "@/services/apiService";
import {
  Flame, ArrowDownToLine, TrendingDown, Clock, ChevronDown, ChevronRight,
  RefreshCw, ArrowUpFromLine,
} from "lucide-react";

// ── Helpers ────────────────────────────────────────────────────────────────────

function fmtDate(d) {
  if (!d) return "—";
  const [y, m, day] = d.split("-");
  return `${day}-${m}-${y}`;
}

function fmtGw(val) {
  if (val == null) return "—";
  return Number(val).toFixed(3) + " g";
}

function SummaryCard({ icon: Icon, label, value, sub, colorClass = "text-foreground" }) {
  return (
    <div className="rounded-xl border bg-card p-4 flex items-start gap-3 shadow-sm">
      <div className={`mt-0.5 ${colorClass}`}>
        <Icon className="size-5" />
      </div>
      <div>
        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">{label}</p>
        <p className={`text-xl font-bold ${colorClass}`}>{value}</p>
        {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── Issue Detail Row (expandable) ─────────────────────────────────────────────

function IssueRow({ row }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <TableRow className="cursor-pointer hover:bg-muted/40 select-none">
          <TableCell className="w-6">
            {open
              ? <ChevronDown className="size-4 text-muted-foreground" />
              : <ChevronRight className="size-4 text-muted-foreground" />
            }
          </TableCell>
          <TableCell className="font-medium">{row.billno}</TableCell>
          <TableCell>{fmtDate(row.date)}</TableCell>
          <TableCell>{row.refiner}</TableCell>
          <TableCell className="text-right font-mono">{fmtGw(row.total_gw)}</TableCell>
          <TableCell>
            {row.rec_status
              ? <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-green-100 text-green-700 border border-green-200">Received</span>
              : <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">Pending</span>
            }
          </TableCell>
        </TableRow>
      </CollapsibleTrigger>
      <CollapsibleContent asChild>
        <TableRow>
          <TableCell colSpan={6} className="bg-muted/20 py-0 px-4">
            <div className="py-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase mb-2 tracking-wide">
                Issue Details
              </p>
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="text-muted-foreground border-b">
                    <th className="text-left py-1 pr-3">Item</th>
                    <th className="text-right py-1 pr-3">Pcs</th>
                    <th className="text-right py-1 pr-3">Ct</th>
                    <th className="text-right py-1 pr-3">GW (g)</th>
                    <th className="text-left py-1 pr-3">Purity</th>
                    <th className="text-left py-1">Packet</th>
                  </tr>
                </thead>
                <tbody>
                  {row.details.map((d, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-1 pr-3 font-mono">{d.item || "—"}</td>
                      <td className="py-1 pr-3 text-right">{d.pcs}</td>
                      <td className="py-1 pr-3 text-right">{Number(d.ct).toFixed(3)}</td>
                      <td className="py-1 pr-3 text-right font-semibold">{Number(d.gw).toFixed(3)}</td>
                      <td className="py-1 pr-3">{d.metal_purity}</td>
                      <td className="py-1">{d.packet}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TableCell>
        </TableRow>
      </CollapsibleContent>
    </Collapsible>
  );
}

// ── Receive Detail Row (expandable) ──────────────────────────────────────────

function ReceiveRow({ row }) {
  const [open, setOpen] = useState(false);
  const lossColor = row.total_gw > 0
    ? (row.total_loss_gw / row.total_gw) * 100
    : 0;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <CollapsibleTrigger asChild>
        <TableRow className="cursor-pointer hover:bg-muted/40 select-none">
          <TableCell className="w-6">
            {open
              ? <ChevronDown className="size-4 text-muted-foreground" />
              : <ChevronRight className="size-4 text-muted-foreground" />
            }
          </TableCell>
          <TableCell className="font-medium">{row.billno}</TableCell>
          <TableCell>{fmtDate(row.date)}</TableCell>
          <TableCell>{row.refiner}</TableCell>
          <TableCell className="text-right font-mono">{fmtGw(row.total_gw)}</TableCell>
          <TableCell className="text-right font-mono text-red-600">{fmtGw(row.total_loss_gw)}</TableCell>
          <TableCell className="text-right text-xs">
            <span className={lossColor > 5 ? "text-red-600 font-semibold" : "text-muted-foreground"}>
              {lossColor.toFixed(2)}%
            </span>
          </TableCell>
        </TableRow>
      </CollapsibleTrigger>
      <CollapsibleContent asChild>
        <TableRow>
          <TableCell colSpan={7} className="bg-muted/20 py-0 px-4">
            <div className="py-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase mb-2 tracking-wide">
                Receive Details
              </p>
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="text-muted-foreground border-b">
                    <th className="text-left py-1 pr-3">Ref Issue</th>
                    <th className="text-left py-1 pr-3">Item</th>
                    <th className="text-right py-1 pr-3">Pcs</th>
                    <th className="text-right py-1 pr-3">GW (g)</th>
                    <th className="text-right py-1 pr-3">Loss %</th>
                    <th className="text-right py-1 pr-3">Loss Wt (g)</th>
                    <th className="text-left py-1 pr-3">In Purity</th>
                    <th className="text-left py-1 pr-3">Conv Purity</th>
                    <th className="text-right py-1 pr-3">Conv NW (g)</th>
                    <th className="text-left py-1">Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {row.details.map((d, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-1 pr-3 font-mono text-blue-600">{d.issue_billno || "—"}</td>
                      <td className="py-1 pr-3 font-mono">{d.item || "—"}</td>
                      <td className="py-1 pr-3 text-right">{d.pcs}</td>
                      <td className="py-1 pr-3 text-right font-semibold">{Number(d.gw).toFixed(3)}</td>
                      <td className="py-1 pr-3 text-right text-red-600">{Number(d.loss_per).toFixed(3)}</td>
                      <td className="py-1 pr-3 text-right text-red-600 font-semibold">{Number(d.loss_wt).toFixed(3)}</td>
                      <td className="py-1 pr-3">{d.metal_purity}</td>
                      <td className="py-1 pr-3">{d.conv_purity}</td>
                      <td className="py-1 pr-3 text-right font-semibold text-green-700">{Number(d.conv_nw).toFixed(3)}</td>
                      <td className="py-1 text-muted-foreground">{d.remarks || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TableCell>
        </TableRow>
      </CollapsibleContent>
    </Collapsible>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────

function RefineryReport() {
  const { toast } = useToast();

  const today        = new Date().toISOString().slice(0, 10);
  const year         = new Date().getMonth() >= 3
    ? new Date().getFullYear()
    : new Date().getFullYear() - 1;
  const firstOfYear  = `${year}-04-01`;

  const [fromDate, setFromDate] = useState(firstOfYear);
  const [toDate,   setToDate]   = useState(today);
  const [refiner,  setRefiner]  = useState("__all__");

  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const params = {
      from_date: fromDate,
      to_date:   toDate,
    };
    if (refiner && refiner !== "__all__") params.refiner = refiner;

    const res = await fetchRefineryReport(params);
    setLoading(false);
    if (res.success) {
      setData(res.data);
    } else {
      toast({ title: "Error", description: "Failed to load refinery report.", variant: "destructive" });
    }
  }, [fromDate, toDate, refiner, toast]);

  useEffect(() => {
    load();
  }, [load]);

  const summary  = data?.summary  || {};
  const refiners = data?.refiners || [];
  const issues   = data?.issues   || [];
  const receives = data?.receives || [];
  const pending  = data?.pending_issues || [];

  return (
    <div className="space-y-6 p-1">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Flame className="size-6 text-orange-500" /> Refinery Report
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Track metal issued to and received from refiners with loss analysis
          </p>
        </div>
      </div>

      {/* ── Filters ── */}
      <div className="rounded-xl border bg-card p-4 flex flex-wrap gap-4 items-end">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input
            type="date"
            value={fromDate}
            onChange={e => setFromDate(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input
            type="date"
            value={toDate}
            onChange={e => setToDate(e.target.value)}
            className="w-40"
          />
        </div>
        <div className="flex flex-col gap-1 min-w-[200px]">
          <Label className="text-xs">Refiner</Label>
          <Select value={refiner} onValueChange={setRefiner}>
            <SelectTrigger>
              <SelectValue placeholder="All Refiners" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">— All Refiners —</SelectItem>
              {refiners.map(r => (
                <SelectItem key={r.id} value={String(r.id)}>{r.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={load} disabled={loading} className="gap-2">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </div>

      {/* ── Summary Cards ── */}
      {loading && !data ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
          <SummaryCard
            icon={ArrowUpFromLine}
            label="Total Issued"
            value={`${Number(summary.total_issued_gw ?? 0).toFixed(3)} g`}
            sub={`${issues.length} bill(s)`}
            colorClass="text-blue-600"
          />
          <SummaryCard
            icon={ArrowDownToLine}
            label="Total Received"
            value={`${Number(summary.total_recv_gw ?? 0).toFixed(3)} g`}
            sub={`${receives.length} bill(s)`}
            colorClass="text-green-600"
          />
          <SummaryCard
            icon={TrendingDown}
            label="Total Loss"
            value={`${Number(summary.total_loss_gw ?? 0).toFixed(3)} g`}
            colorClass="text-red-600"
          />
          <SummaryCard
            icon={Flame}
            label="Avg Loss %"
            value={`${Number(summary.avg_loss_pct ?? 0).toFixed(3)}%`}
            colorClass={Number(summary.avg_loss_pct) > 5 ? "text-red-600" : "text-orange-500"}
          />
          <SummaryCard
            icon={Clock}
            label="Pending Issues"
            value={summary.pending_count ?? 0}
            sub={`${Number(summary.pending_gw ?? 0).toFixed(3)} g pending`}
            colorClass={summary.pending_count > 0 ? "text-amber-600" : "text-muted-foreground"}
          />
          <SummaryCard
            icon={ArrowDownToLine}
            label="Net Returned"
            value={`${(Number(summary.total_recv_gw ?? 0) - Number(summary.total_loss_gw ?? 0)).toFixed(3)} g`}
            sub="after loss"
            colorClass="text-primary"
          />
        </div>
      )}

      {/* ── Tabs ── */}
      <Tabs defaultValue="issues">
        <TabsList className="mb-2">
          <TabsTrigger value="issues">
            Issues
            {issues.length > 0 && (
              <span className="ml-1.5 text-xs bg-blue-100 text-blue-700 rounded-full px-1.5 py-0.5 font-semibold">
                {issues.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="receives">
            Receives
            {receives.length > 0 && (
              <span className="ml-1.5 text-xs bg-green-100 text-green-700 rounded-full px-1.5 py-0.5 font-semibold">
                {receives.length}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger value="pending">
            Pending
            {pending.length > 0 && (
              <span className="ml-1.5 text-xs bg-amber-100 text-amber-700 rounded-full px-1.5 py-0.5 font-semibold">
                {pending.length}
              </span>
            )}
          </TabsTrigger>
        </TabsList>

        {/* Issues Tab */}
        <TabsContent value="issues">
          <div className="rounded-xl border bg-card overflow-hidden">
            {loading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 rounded" />)}
              </div>
            ) : issues.length === 0 ? (
              <div className="p-10 text-center text-muted-foreground">
                <ArrowUpFromLine className="size-10 mx-auto mb-2 opacity-30" />
                No refinery issues found for the selected period.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30">
                    <TableHead className="w-6" />
                    <TableHead>Bill No</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Refiner</TableHead>
                    <TableHead className="text-right">Total GW</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {issues.map(row => <IssueRow key={row.id} row={row} />)}
                </TableBody>
              </Table>
            )}
            {/* Footer total */}
            {!loading && issues.length > 0 && (
              <div className="border-t px-4 py-2 bg-muted/20 flex justify-end items-center gap-6 text-sm font-semibold">
                <span className="text-muted-foreground font-normal">{issues.length} bills</span>
                <span>Total: {Number(summary.total_issued_gw ?? 0).toFixed(3)} g</span>
              </div>
            )}
          </div>
        </TabsContent>

        {/* Receives Tab */}
        <TabsContent value="receives">
          <div className="rounded-xl border bg-card overflow-hidden">
            {loading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 rounded" />)}
              </div>
            ) : receives.length === 0 ? (
              <div className="p-10 text-center text-muted-foreground">
                <ArrowDownToLine className="size-10 mx-auto mb-2 opacity-30" />
                No refinery receives found for the selected period.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30">
                    <TableHead className="w-6" />
                    <TableHead>Bill No</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Refiner</TableHead>
                    <TableHead className="text-right">Total GW</TableHead>
                    <TableHead className="text-right">Loss Wt</TableHead>
                    <TableHead className="text-right">Loss %</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {receives.map(row => <ReceiveRow key={row.id} row={row} />)}
                </TableBody>
              </Table>
            )}
            {/* Footer total */}
            {!loading && receives.length > 0 && (
              <div className="border-t px-4 py-2 bg-muted/20 flex justify-end items-center gap-8 text-sm font-semibold">
                <span className="text-muted-foreground font-normal">{receives.length} bills</span>
                <span>Received: {Number(summary.total_recv_gw ?? 0).toFixed(3)} g</span>
                <span className="text-red-600">Loss: {Number(summary.total_loss_gw ?? 0).toFixed(3)} g</span>
                <span>Avg Loss: {Number(summary.avg_loss_pct ?? 0).toFixed(3)}%</span>
              </div>
            )}
          </div>
        </TabsContent>

        {/* Pending Tab */}
        <TabsContent value="pending">
          <div className="rounded-xl border bg-card overflow-hidden">
            {loading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 rounded" />)}
              </div>
            ) : pending.length === 0 ? (
              <div className="p-10 text-center text-muted-foreground">
                <Clock className="size-10 mx-auto mb-2 opacity-30" />
                <p className="font-medium text-green-600">All issues received!</p>
                <p className="text-sm mt-1">No pending refinery issues in the selected period.</p>
              </div>
            ) : (
              <>
                <div className="px-4 py-2 bg-amber-50 border-b border-amber-200 text-sm text-amber-800 font-medium">
                  {pending.length} issue(s) awaiting return from refiner — {Number(summary.pending_gw ?? 0).toFixed(3)} g outstanding
                </div>
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/30">
                      <TableHead className="w-6" />
                      <TableHead>Bill No</TableHead>
                      <TableHead>Issue Date</TableHead>
                      <TableHead>Refiner</TableHead>
                      <TableHead className="text-right">Issued GW</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {pending.map(row => <IssueRow key={row.id} row={row} />)}
                  </TableBody>
                </Table>
                <div className="border-t px-4 py-2 bg-amber-50 flex justify-end items-center gap-6 text-sm font-semibold text-amber-800">
                  <span>{pending.length} pending bill(s)</span>
                  <span>Total Outstanding: {Number(summary.pending_gw ?? 0).toFixed(3)} g</span>
                </div>
              </>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

export default RefineryReport;
