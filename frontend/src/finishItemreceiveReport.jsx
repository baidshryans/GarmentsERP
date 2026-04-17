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
import { PackageCheck, Filter } from "lucide-react";

function fmtDate(d) {
  if (!d) return "—";
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

export default function FinishedItemReceiveReport() {
  const { toast } = useToast();

  const [fromDate, setFromDate]   = useState(firstOfMonth);
  const [toDate, setToDate]       = useState(today);
  const [karigarId, setKarigarId] = useState("all");
  const [purityId, setPurityId]   = useState("all");
  const [statusFilter, setStatusFilter] = useState("finished"); // finished | pending | all

  const [karigars, setKarigars] = useState([]);
  const [purities, setPurities] = useState([]);
  const [items, setItems]       = useState([]);
  const [loading, setLoading]   = useState(false);

  // Load filter sources
  useEffect(() => {
    apiClient.get("/contacts/api/ledger/?role=KR&page_size=500")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setKarigars(list);
      }).catch(() => {});
    apiClient.get("/goldrates/api/purity/")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setPurities(list);
      }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.append("date_from", fromDate);
    params.append("date_to", toDate);
    if (karigarId && karigarId !== "all") params.append("karigar_ldgr", karigarId);
    if (purityId && purityId !== "all")   params.append("purity", purityId);
    if (statusFilter === "finished")      params.append("finish_status", "true");
    else if (statusFilter === "pending")  params.append("finish_status", "false");
    params.append("page_size", "500");

    try {
      const res = await apiClient.get(
        `/manufacturing/api/karigar-receive-item-report?${params.toString()}`
      );
      const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setItems(list);
    } catch (err) {
      toast({
        title: "Failed to load finished item receive report",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, karigarId, purityId, statusFilter, toast]);

  useEffect(() => { load(); }, [load]);

  const summary = useMemo(() => ({
    rows:    items.length,
    karigars: new Set(items.map((r) => r.karigar_name).filter(Boolean)).size,
    pcs:     items.reduce((s, r) => s + Number(r.pcs || 0), 0),
    gw:      items.reduce((s, r) => s + Number(r.gw  || 0), 0),
    nw:      items.reduce((s, r) => s + Number(r.nw  || 0), 0),
    pending: items.reduce((s, r) => s + Number(r.pending_pcs || 0), 0),
  }), [items]);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="size-4 text-primary" />
          <h2 className="text-sm font-semibold text-gray-800">Filters</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-6 gap-3">
          <div>
            <Label className="text-xs">From Date</Label>
            <Input type="date" value={fromDate}
              onChange={(e) => setFromDate(e.target.value)} />
          </div>
          <div>
            <Label className="text-xs">To Date</Label>
            <Input type="date" value={toDate}
              onChange={(e) => setToDate(e.target.value)} />
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
          <div>
            <Label className="text-xs">Status</Label>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="finished">Finished</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="all">All</SelectItem>
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

      {/* Summary */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-primary">
            <PackageCheck className="size-4" />
            <span className="text-sm font-semibold">Finished Item Receive Summary</span>
          </div>
          <span className="text-xs text-gray-500">
            {summary.rows} rows · {summary.karigars} karigars
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 text-xs gap-3">
          <div><div className="text-gray-500">Pieces Received</div><div className="font-semibold">{summary.pcs}</div></div>
          <div><div className="text-gray-500">Gross Wt (g)</div><div className="font-semibold">{num(summary.gw)}</div></div>
          <div><div className="text-gray-500">Net Wt (g)</div><div className="font-semibold">{num(summary.nw)}</div></div>
          <div><div className="text-gray-500">Pending Pcs</div><div className="font-semibold text-amber-600">{summary.pending}</div></div>
          <div><div className="text-gray-500">Status Filter</div><div className="font-semibold capitalize">{statusFilter}</div></div>
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
            <PackageCheck className="size-4 text-primary" />
            <h3 className="text-sm font-semibold text-gray-800">Receive Lines</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Slip No</th>
                  <th className="px-3 py-2 text-left">Karigar</th>
                  <th className="px-3 py-2 text-left">Item</th>
                  <th className="px-3 py-2 text-left">Purity</th>
                  <th className="px-3 py-2 text-right">Pcs</th>
                  <th className="px-3 py-2 text-right">Gw (g)</th>
                  <th className="px-3 py-2 text-right">Nw (g)</th>
                  <th className="px-3 py-2 text-right text-amber-600">Pending Pcs</th>
                  <th className="px-3 py-2 text-right text-amber-600">Pending Gw</th>
                  <th className="px-3 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {items.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="px-3 py-8 text-center text-gray-400">
                      No finished item receives in this range.
                    </td>
                  </tr>
                ) : items.map((r) => (
                  <tr key={r.id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.receive_date)}</td>
                    <td className="px-3 py-2 font-medium">{r.receive_slip || "—"}</td>
                    <td className="px-3 py-2">{r.karigar_name || "—"}</td>
                    <td className="px-3 py-2">{r.item}</td>
                    <td className="px-3 py-2">{r.purity}{typeof r.purity === "number" ? "" : "K"}</td>
                    <td className="px-3 py-2 text-right">{r.pcs}</td>
                    <td className="px-3 py-2 text-right">{num(r.gw)}</td>
                    <td className="px-3 py-2 text-right">{num(r.nw)}</td>
                    <td className="px-3 py-2 text-right text-amber-600">{r.pending_pcs || 0}</td>
                    <td className="px-3 py-2 text-right text-amber-600">{num(r.pending_gw)}</td>
                    <td className="px-3 py-2">
                      {r.finish_status ? (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">Finished</span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">Pending</span>
                      )}
                    </td>
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
