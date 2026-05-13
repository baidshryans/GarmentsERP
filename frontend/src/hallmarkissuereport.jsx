import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectTrigger, SelectContent, SelectItem, SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/hooks/use-toast";
import apiClient from "@/services/apiClient";
import { ShieldCheck, ArrowUpFromLine, Filter } from "lucide-react";
import { isValidDateRange } from "@/lib/dateRange";

// ── Helpers ─────────────────────────────────────────────────────────────────
function fmtDate(d) {
  if (!d) return "�";
  const dt = new Date(d);
  if (isNaN(dt)) return d;
  return dt.toLocaleDateString("en-GB").replaceAll("/", "-");
}

function num(n, dp = 3) {
  if (n === null || n === undefined || n === "") return (0).toFixed(dp);
  return Number(n).toFixed(dp);
}

const today        = new Date().toISOString().slice(0, 10);
const firstOfMonth = today.slice(0, 8) + "01";

export default function HallmarkIssueReport() {
  const { toast } = useToast();

  const [fromDate, setFromDate] = useState(firstOfMonth);
  const [toDate, setToDate]     = useState(today);
  const [centerId, setCenterId] = useState("all");
  const [purityId, setPurityId] = useState("all");

  const [centers, setCenters]   = useState([]);
  const [purities, setPurities] = useState([]);
  const [issues, setIssues]     = useState([]);
  const [loading, setLoading]   = useState(false);

  // Load filter sources once
  useEffect(() => {
    apiClient.get("/contacts/api/ledger/?page_size=500")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setCenters(list);
      })
      .catch(() => {});
    apiClient.get("/goldrates/api/purity/")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setPurities(list);
      })
      .catch(() => {});
  }, []);

  const load = useCallback(async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      toast({ title: "From date cannot be after To date.", variant: "destructive" });
      return;
    }
    setLoading(true);
    const params = new URLSearchParams();
    params.append("start_date", fromDate);
    params.append("end_date", toDate);
    if (centerId && centerId !== "all") params.append("ledger_ids", centerId);
    if (purityId && purityId !== "all") params.append("purity_id", purityId);

    try {
      const res = await apiClient.get(
        `/manufacturing/api/hallmark-issue-report?${params.toString()}`
      );
      const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setIssues(list);
    } catch (err) {
      toast({
        title: "Failed to load hallmark issue report",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
      setIssues([]);
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, centerId, purityId, toast]);

  useEffect(() => { load(); }, [load]);

  const centerNameById = useMemo(() => {
    const m = {};
    centers.forEach((c) => { m[c.id] = c.ac_name; });
    return m;
  }, [centers]);

  const purityById = useMemo(() => {
    const m = {};
    purities.forEach((p) => { m[p.id] = p.purity; });
    return m;
  }, [purities]);

  // Flatten HallmarkIssue → HallmarkIssueItem
  const rows = useMemo(() => {
    const out = [];
    issues.forEach((iss) => {
      (iss.hallmarkissueitem_set || []).forEach((it) => {
        out.push({
          id: `${iss.id}-${it.id}`,
          slip:    iss.issue_slip_no,
          date:    iss.date1,
          center:  iss.hallmark_center_name || centerNameById[iss.hallmark_center] || `#${iss.hallmark_center}`,
          sl:      it.sl_no,
          pcs:     it.pcs,
          gw:      it.gw,
          nw:      it.nw,
          purity:  purityById[it.purity] || it.purity,
          received: it.rec_status,
          remarks: it.remarks || "",
        });
      });
    });
    return out;
  }, [issues, centerNameById, purityById]);

  const summary = useMemo(() => ({
    rows:     rows.length,
    centers:  new Set(rows.map((r) => r.center)).size,
    pcs:      rows.reduce((s, r) => s + Number(r.pcs || 0), 0),
    gw:       rows.reduce((s, r) => s + Number(r.gw  || 0), 0),
    nw:       rows.reduce((s, r) => s + Number(r.nw  || 0), 0),
    pending:  rows.filter((r) => !r.received).length,
    received: rows.filter((r) => r.received).length,
  }), [rows]);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="size-4 text-primary" />
          <h2 className="text-sm font-semibold text-gray-800">Filters</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <Label htmlFor="from" className="text-xs">From Date</Label>
            <Input id="from" type="date" value={fromDate}
              onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} />
          </div>
          <div>
            <Label htmlFor="to" className="text-xs">To Date</Label>
            <Input id="to" type="date" value={toDate}
              onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} />
          </div>
          <div>
            <Label className="text-xs">Hallmark Center</Label>
            <Select value={centerId} onValueChange={setCenterId}>
              <SelectTrigger><SelectValue placeholder="All centers" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Centers</SelectItem>
                {centers.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>{c.ac_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Purity</Label>
            <Select value={purityId} onValueChange={setPurityId}>
              <SelectTrigger><SelectValue placeholder="All purities" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Purities</SelectItem>
                {purities.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.purity}K</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <Button className="w-full" onClick={load} disabled={loading}>
              {loading ? "Loading..." : "Apply Filters"}
            </Button>
          </div>
        </div>
      </div>

      {/* Summary card */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-primary">
            <ShieldCheck className="size-4" />
            <span className="text-sm font-semibold">Hallmark Issue Summary</span>
          </div>
          <span className="text-xs text-gray-500">
            {summary.rows} rows � {summary.centers} centers
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 text-xs gap-3">
          <div><div className="text-gray-500">Pieces</div><div className="font-semibold">{summary.pcs}</div></div>
          <div><div className="text-gray-500">Gross Wt (g)</div><div className="font-semibold">{num(summary.gw)}</div></div>
          <div><div className="text-gray-500">Net Wt (g)</div><div className="font-semibold">{num(summary.nw)}</div></div>
          <div><div className="text-gray-500">Pending</div><div className="font-semibold text-amber-600">{summary.pending}</div></div>
          <div><div className="text-gray-500">Received Back</div><div className="font-semibold text-emerald-700">{summary.received}</div></div>
        </div>
      </div>

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      )}

      {/* Table */}
      {!loading && (
        <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2 bg-gray-50/50">
            <ArrowUpFromLine className="size-4 text-primary" />
            <h3 className="text-sm font-semibold text-gray-800">Issue Lines</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Slip No</th>
                  <th className="px-3 py-2 text-left">Hallmark Center</th>
                  <th className="px-3 py-2 text-right">Sl</th>
                  <th className="px-3 py-2 text-left">Purity</th>
                  <th className="px-3 py-2 text-right">Pcs</th>
                  <th className="px-3 py-2 text-right">Gw (g)</th>
                  <th className="px-3 py-2 text-right">Nw (g)</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-left">Remarks</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-3 py-8 text-center text-gray-400">
                      No hallmark issue records in this range.
                    </td>
                  </tr>
                ) : rows.map((r) => (
                  <tr key={r.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.date)}</td>
                    <td className="px-3 py-2 font-medium">{r.slip}</td>
                    <td className="px-3 py-2">{r.center}</td>
                    <td className="px-3 py-2 text-right">{r.sl}</td>
                    <td className="px-3 py-2">{r.purity}{typeof r.purity === "number" ? "" : "K"}</td>
                    <td className="px-3 py-2 text-right">{r.pcs}</td>
                    <td className="px-3 py-2 text-right">{num(r.gw)}</td>
                    <td className="px-3 py-2 text-right">{num(r.nw)}</td>
                    <td className="px-3 py-2">
                      {r.received ? (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">Received</span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">Pending</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-gray-500">{r.remarks}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
