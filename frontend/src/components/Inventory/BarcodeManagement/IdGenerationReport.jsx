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
import { Barcode, Filter } from "lucide-react";
import { isValidDateRange } from "@/lib/dateRange";

const purityLabel = (p) => {
  const s = String(p ?? '');
  return (s.endsWith('K') || s.endsWith('k')) ? s : s + 'K';
};

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

export default function IDGenerationReport() {
  const { toast } = useToast();

  // Filters
  const [fromDate, setFromDate]   = useState(firstOfMonth);
  const [toDate, setToDate]       = useState(today);
  const [artisanId, setArtisanId] = useState("all");
  const [itemId, setItemId]       = useState("all");
  const [purityId, setPurityId]   = useState("all");
  const [userVal, setUserVal]     = useState("all");

  // Master data
  const [artisans, setArtisans] = useState([]);
  const [items, setItems]       = useState([]);
  const [purities, setPurities] = useState([]);
  const [users, setUsers]       = useState([]);

  // Data
  const [rows, setRows]       = useState([]);
  const [loading, setLoading] = useState(false);

  // Load filter sources once
  useEffect(() => {
    apiClient.get("/contacts/api/ledger/?role=KR&page_size=500")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setArtisans(list);
      }).catch(() => {});

    apiClient.get("/mastersconfig/api/item/?item_type=M&page_size=500")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setItems(list);
      }).catch(() => {});

    apiClient.get("/goldrates/api/purity/")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setPurities(list);
      }).catch(() => {});

    apiClient.get("/userauth/api/users/?page_size=500")
      .then((res) => {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
        setUsers(list);
      }).catch(() => {});
  }, []);

  // Lookup maps for display
  const itemNameById   = useMemo(() => Object.fromEntries(items.map((i)    => [i.id, i.short_code || i.item_name])), [items]);
  const purityById     = useMemo(() => Object.fromEntries(purities.map((p) => [p.id, p.purity])), [purities]);
  const artisanNameById = useMemo(() => Object.fromEntries(artisans.map((a) => [a.id, a.ac_name])), [artisans]);

  const load = useCallback(async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      toast({ title: "From date cannot be after To date.", variant: "destructive" });
      return;
    }
    setLoading(true);
    const params = new URLSearchParams();
    params.append("from_date", fromDate);
    params.append("to_date", toDate);
    if (artisanId !== "all") params.append("artisan_ids", artisanId);
    if (itemId    !== "all") params.append("item_ids",    itemId);
    if (purityId  !== "all") params.append("purity_ids",  purityId);
    if (userVal   !== "all") params.append("user_ids",    userVal);

    try {
      const res = await apiClient.get(
        `/inventory/api/barcode-creation-report?${params.toString()}`
      );
      const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setRows(list);
    } catch (err) {
      toast({
        title: "Failed to load ID generation report",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, artisanId, itemId, purityId, userVal, toast]);

  const summary = useMemo(() => ({
    rows: rows.length,
    pcs:  rows.reduce((s, r) => s + Number(r.pcs || 0), 0),
    gw:   rows.reduce((s, r) => s + Number(r.gw  || 0), 0),
    nw:   rows.reduce((s, r) => s + Number(r.nw  || 0), 0),
    stonePcs: rows.reduce((s, r) => s + (r.stone_details || []).reduce((a, d) => a + Number(d.pcs || 0), 0), 0),
    stoneCt:  rows.reduce((s, r) => s + (r.stone_details || []).reduce((a, d) => a + Number(d.ct  || 0), 0), 0),
  }), [rows]);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="size-4 text-primary" />
          <h2 className="text-sm font-semibold text-gray-800">Filters</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-7 gap-3">
          <div>
            <Label className="text-xs">From Date</Label>
            <Input type="date" value={fromDate}
              onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} />
          </div>
          <div>
            <Label className="text-xs">To Date</Label>
            <Input type="date" value={toDate}
              onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} />
          </div>
          <div>
            <Label className="text-xs">Artisan (Karigar)</Label>
            <Select value={artisanId} onValueChange={setArtisanId}>
              <SelectTrigger><SelectValue placeholder="All artisans" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Artisans</SelectItem>
                {artisans.map((a) => (
                  <SelectItem key={a.id} value={String(a.id)}>{a.ac_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label className="text-xs">Item (Type M)</Label>
            <Select value={itemId} onValueChange={setItemId}>
              <SelectTrigger><SelectValue placeholder="All items" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Items</SelectItem>
                {items.map((i) => (
                  <SelectItem key={i.id} value={String(i.id)}>{i.short_code || i.item_name}</SelectItem>
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
            <Label className="text-xs">User</Label>
            <Select value={userVal} onValueChange={setUserVal}>
              <SelectTrigger><SelectValue placeholder="All users" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Users</SelectItem>
                {users.map((u) => (
                  <SelectItem key={u.id} value={String(u.username || u.name || u.id)}>
                    {u.username || u.name || u.email}
                  </SelectItem>
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

      {/* Summary */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2 text-primary">
            <Barcode className="size-4" />
            <span className="text-sm font-semibold">ID Generation Summary</span>
          </div>
          <span className="text-xs text-gray-500">{summary.rows} barcodes</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 text-xs gap-3">
          <div><div className="text-gray-500">Pieces</div><div className="font-semibold">{summary.pcs}</div></div>
          <div><div className="text-gray-500">Gross Wt (g)</div><div className="font-semibold">{num(summary.gw)}</div></div>
          <div><div className="text-gray-500">Net Wt (g)</div><div className="font-semibold">{num(summary.nw)}</div></div>
          <div><div className="text-gray-500">Stone Pcs</div><div className="font-semibold">{summary.stonePcs}</div></div>
          <div><div className="text-gray-500">Stone Carats</div><div className="font-semibold">{num(summary.stoneCt)}</div></div>
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
            <Barcode className="size-4 text-primary" />
            <h3 className="text-sm font-semibold text-gray-800">Generated Barcodes</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Barcode</th>
                  <th className="px-3 py-2 text-left">Item</th>
                  <th className="px-3 py-2 text-left">Purity</th>
                  <th className="px-3 py-2 text-right">Pcs</th>
                  <th className="px-3 py-2 text-right">Gw (g)</th>
                  <th className="px-3 py-2 text-right">Nw (g)</th>
                  <th className="px-3 py-2 text-left">Karigar</th>
                  <th className="px-3 py-2 text-right">Stone Pcs</th>
                  <th className="px-3 py-2 text-right">Stone Ct</th>
                  <th className="px-3 py-2 text-right">Making</th>
                  <th className="px-3 py-2 text-left">Created By</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={12} className="px-3 py-8 text-center text-gray-400">
                      Set filters and click Apply Filters to load the report.
                    </td>
                  </tr>
                ) : rows.map((r) => {
                  const stonePcs = (r.stone_details || []).reduce((a, d) => a + Number(d.pcs || 0), 0);
                  const stoneCt  = (r.stone_details || []).reduce((a, d) => a + Number(d.ct  || 0), 0);
                  return (
                    <tr key={r.id} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-3 py-2 whitespace-nowrap">{fmtDate(r.created_date)}</td>
                      <td className="px-3 py-2 font-mono text-xs">{r.barcode}</td>
                      <td className="px-3 py-2">{itemNameById[r.item] || `#${r.item}`}</td>
                      <td className="px-3 py-2">{purityById[r.purity] ? purityLabel(purityById[r.purity]) : `#${r.purity}`}</td>
                      <td className="px-3 py-2 text-right">{r.pcs || 0}</td>
                      <td className="px-3 py-2 text-right">{num(r.gw)}</td>
                      <td className="px-3 py-2 text-right">{num(r.nw)}</td>
                      <td className="px-3 py-2">{artisanNameById[r.kr_code] || "�"}</td>
                      <td className="px-3 py-2 text-right">{stonePcs || ""}</td>
                      <td className="px-3 py-2 text-right">{stoneCt ? num(stoneCt) : ""}</td>
                      <td className="px-3 py-2 text-right">{r.making_val ? `${r.making_val}` : ""}</td>
                      <td className="px-3 py-2 text-gray-500">{r.created_by || "�"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
