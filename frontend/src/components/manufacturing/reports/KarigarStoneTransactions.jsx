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
import { Gem, ArrowDownToLine, ArrowUpFromLine } from "lucide-react";

// ── Helpers ─────────────────────────────────────────────────────────────────
function fmtDate(d) {
  if (!d) return "—";
  const dt = new Date(d);
  return dt.toLocaleDateString("en-GB").replaceAll("/", "-");
}

function num(n) {
  if (n === null || n === undefined || n === "") return "0.000";
  return Number(n).toFixed(3);
}

// ── Main Component ──────────────────────────────────────────────────────────
function KarigarStoneTransactions() {
  const { toast } = useToast();

  const today        = new Date().toISOString().slice(0, 10);
  const firstOfMonth = today.slice(0, 8) + "01";

  const [fromDate, setFromDate]     = useState(firstOfMonth);
  const [toDate, setToDate]         = useState(today);
  const [karigarId, setKarigarId]   = useState("all");
  const [txnType, setTxnType]       = useState("both"); // both | issue | receive

  const [karigars, setKarigars]     = useState([]);
  const [issues, setIssues]         = useState([]);
  const [receives, setReceives]     = useState([]);
  const [loading, setLoading]       = useState(false);

  // Load karigar list once
  useEffect(() => {
    apiClient.get("/contacts/api/ledger/?role=KR&page_size=500")
      .then(res => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setKarigars(list);
      })
      .catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.append("date_from", fromDate);
    params.append("date_to", toDate);
    if (karigarId && karigarId !== "all") params.append("karigar_ldgr", karigarId);
    params.append("page_size", "500");

    const calls = [];
    if (txnType === "both" || txnType === "issue") {
      calls.push(apiClient.get(`/manufacturing/api/karigar-stone-issue/?${params.toString()}`));
    } else {
      calls.push(Promise.resolve({ data: { results: [] } }));
    }
    if (txnType === "both" || txnType === "receive") {
      calls.push(apiClient.get(`/manufacturing/api/karigar-stone-receive/?${params.toString()}`));
    } else {
      calls.push(Promise.resolve({ data: { results: [] } }));
    }

    try {
      const [issueRes, recRes] = await Promise.all(calls);
      const iList = Array.isArray(issueRes.data) ? issueRes.data : (issueRes.data?.results ?? []);
      const rList = Array.isArray(recRes.data)   ? recRes.data   : (recRes.data?.results ?? []);
      setIssues(iList);
      setReceives(rList);
    } catch (err) {
      toast({
        title: "Failed to load transactions",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, karigarId, txnType, toast]);

  useEffect(() => { load(); }, [load]);

  // Flatten header → items for table rendering
  const issueRows = useMemo(() => {
    const out = [];
    issues.forEach((h) => {
      (h.karigarstoneissue_set || []).forEach((it) => {
        out.push({
          id: `i-${h.id}-${it.id}`,
          date: h.date1,
          billno: h.billno,
          karigar: h.karigar_ldgr_name,
          item: it.item_name || it.item || "—",
          pcs: it.pcs,
          ct: it.ct,
          gw: it.gw,
          rate: it.rate,
          taxable: it.taxable_value,
          total: it.tot_val,
        });
      });
    });
    return out;
  }, [issues]);

  const receiveRows = useMemo(() => {
    const out = [];
    receives.forEach((h) => {
      (h.karigarstonereceive_set || []).forEach((it) => {
        out.push({
          id: `r-${h.id}-${it.id}`,
          date: h.date1,
          billno: h.billno,
          karigar: h.karigar_ldgr_name,
          item: it.item_name || it.item || "—",
          ret_pcs: it.return_pcs,
          ret_ct: it.return_ct,
          ret_gw: it.return_gw,
          brk_pcs: it.broken_pcs,
          brk_gw: it.broken_gw,
          loss_pcs: it.loss_pcs,
          loss_gw: it.loss_gw,
          total: it.tot_val,
        });
      });
    });
    return out;
  }, [receives]);

  // Summary
  const issueSummary = useMemo(() => ({
    count: issueRows.length,
    pcs:   issueRows.reduce((s, r) => s + Number(r.pcs || 0), 0),
    gw:    issueRows.reduce((s, r) => s + Number(r.gw  || 0), 0),
    ct:    issueRows.reduce((s, r) => s + Number(r.ct  || 0), 0),
  }), [issueRows]);

  const receiveSummary = useMemo(() => ({
    count: receiveRows.length,
    pcs:   receiveRows.reduce((s, r) => s + Number(r.ret_pcs || 0), 0),
    gw:    receiveRows.reduce((s, r) => s + Number(r.ret_gw  || 0), 0),
    brk:   receiveRows.reduce((s, r) => s + Number(r.brk_gw  || 0), 0),
    loss:  receiveRows.reduce((s, r) => s + Number(r.loss_gw || 0), 0),
  }), [receiveRows]);

  const showIssue   = txnType === "both" || txnType === "issue";
  const showReceive = txnType === "both" || txnType === "receive";

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Gem className="size-4 text-primary" />
          <h2 className="text-sm font-semibold text-gray-800">Filters</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <Label htmlFor="from" className="text-xs">From Date</Label>
            <Input id="from" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="to" className="text-xs">To Date</Label>
            <Input id="to" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
          </div>
          <div>
            <Label className="text-xs">Karigar</Label>
            <Select value={karigarId} onValueChange={setKarigarId}>
              <SelectTrigger><SelectValue placeholder="All karigars" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Karigars</SelectItem>
                {karigars.map((k) => (
                  <SelectItem key={k.id} value={String(k.id)}>{k.ac_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Transaction Type</Label>
            <Select value={txnType} onValueChange={setTxnType}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="both">Issue &amp; Receive</SelectItem>
                <SelectItem value="issue">Issue Only</SelectItem>
                <SelectItem value="receive">Receive Only</SelectItem>
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

      {/* Summary cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {showIssue && (
          <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 text-primary">
                <ArrowUpFromLine className="size-4" />
                <span className="text-sm font-semibold">Stone Issues</span>
              </div>
              <span className="text-xs text-gray-500">{issueSummary.count} rows</span>
            </div>
            <div className="grid grid-cols-3 text-xs gap-2">
              <div><div className="text-gray-500">Pieces</div><div className="font-semibold">{issueSummary.pcs}</div></div>
              <div><div className="text-gray-500">Gross Wt (g)</div><div className="font-semibold">{num(issueSummary.gw)}</div></div>
              <div><div className="text-gray-500">Carats</div><div className="font-semibold">{num(issueSummary.ct)}</div></div>
            </div>
          </div>
        )}
        {showReceive && (
          <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2 text-primary">
                <ArrowDownToLine className="size-4" />
                <span className="text-sm font-semibold">Stone Receives</span>
              </div>
              <span className="text-xs text-gray-500">{receiveSummary.count} rows</span>
            </div>
            <div className="grid grid-cols-4 text-xs gap-2">
              <div><div className="text-gray-500">Returned Pcs</div><div className="font-semibold">{receiveSummary.pcs}</div></div>
              <div><div className="text-gray-500">Returned (g)</div><div className="font-semibold">{num(receiveSummary.gw)}</div></div>
              <div><div className="text-gray-500">Broken (g)</div><div className="font-semibold text-red-600">{num(receiveSummary.brk)}</div></div>
              <div><div className="text-gray-500">Loss (g)</div><div className="font-semibold text-amber-600">{num(receiveSummary.loss)}</div></div>
            </div>
          </div>
        )}
      </div>

      {/* Tables */}
      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      )}

      {!loading && showIssue && (
        <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2 bg-gray-50/50">
            <ArrowUpFromLine className="size-4 text-primary" />
            <h3 className="text-sm font-semibold text-gray-800">Stone Issues</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Bill No</th>
                  <th className="px-3 py-2 text-left">Karigar</th>
                  <th className="px-3 py-2 text-left">Item</th>
                  <th className="px-3 py-2 text-right">Pcs</th>
                  <th className="px-3 py-2 text-right">Carats</th>
                  <th className="px-3 py-2 text-right">Gross Wt (g)</th>
                  <th className="px-3 py-2 text-right">Rate</th>
                  <th className="px-3 py-2 text-right">Taxable</th>
                  <th className="px-3 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {issueRows.length === 0 ? (
                  <tr><td colSpan={10} className="px-3 py-6 text-center text-gray-400">No stone issues in this range.</td></tr>
                ) : issueRows.map((r) => (
                  <tr key={r.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2">{fmtDate(r.date)}</td>
                    <td className="px-3 py-2 font-medium">{r.billno}</td>
                    <td className="px-3 py-2">{r.karigar}</td>
                    <td className="px-3 py-2">{r.item}</td>
                    <td className="px-3 py-2 text-right">{r.pcs}</td>
                    <td className="px-3 py-2 text-right">{num(r.ct)}</td>
                    <td className="px-3 py-2 text-right">{num(r.gw)}</td>
                    <td className="px-3 py-2 text-right">{r.rate}</td>
                    <td className="px-3 py-2 text-right">{r.taxable}</td>
                    <td className="px-3 py-2 text-right font-semibold">{r.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!loading && showReceive && (
        <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2 bg-gray-50/50">
            <ArrowDownToLine className="size-4 text-primary" />
            <h3 className="text-sm font-semibold text-gray-800">Stone Receives</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Bill No</th>
                  <th className="px-3 py-2 text-left">Karigar</th>
                  <th className="px-3 py-2 text-left">Item</th>
                  <th className="px-3 py-2 text-right">Ret Pcs</th>
                  <th className="px-3 py-2 text-right">Ret Ct</th>
                  <th className="px-3 py-2 text-right">Ret Gw</th>
                  <th className="px-3 py-2 text-right text-red-600">Broken Pcs</th>
                  <th className="px-3 py-2 text-right text-red-600">Broken Gw</th>
                  <th className="px-3 py-2 text-right text-amber-600">Loss Pcs</th>
                  <th className="px-3 py-2 text-right text-amber-600">Loss Gw</th>
                  <th className="px-3 py-2 text-right">Total</th>
                </tr>
              </thead>
              <tbody>
                {receiveRows.length === 0 ? (
                  <tr><td colSpan={12} className="px-3 py-6 text-center text-gray-400">No stone receives in this range.</td></tr>
                ) : receiveRows.map((r) => (
                  <tr key={r.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2">{fmtDate(r.date)}</td>
                    <td className="px-3 py-2 font-medium">{r.billno}</td>
                    <td className="px-3 py-2">{r.karigar}</td>
                    <td className="px-3 py-2">{r.item}</td>
                    <td className="px-3 py-2 text-right">{r.ret_pcs}</td>
                    <td className="px-3 py-2 text-right">{num(r.ret_ct)}</td>
                    <td className="px-3 py-2 text-right">{num(r.ret_gw)}</td>
                    <td className="px-3 py-2 text-right text-red-600">{r.brk_pcs}</td>
                    <td className="px-3 py-2 text-right text-red-600">{num(r.brk_gw)}</td>
                    <td className="px-3 py-2 text-right text-amber-600">{r.loss_pcs}</td>
                    <td className="px-3 py-2 text-right text-amber-600">{num(r.loss_gw)}</td>
                    <td className="px-3 py-2 text-right font-semibold">{r.total}</td>
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

export default KarigarStoneTransactions;
