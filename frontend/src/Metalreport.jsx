import React, { useState, useEffect, useCallback, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SearchableComboBox } from "@/components/ui/SearchableComboBox";
import { useToast } from "@/hooks/use-toast";
import apiClient from "@/services/apiClient";
import { Coins, Filter, X } from "lucide-react";
import { isValidDateRange } from "@/lib/dateRange";

const purityLabel = (p) => {
  const s = String(p ?? '');
  return (s.endsWith('K') || s.endsWith('k')) ? s : s + 'K';
};

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

const today = new Date().toISOString().slice(0, 10);
const fyStart = (() => {
  const now = new Date();
  const yr = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
  return `${yr}-04-01`;
})();

export default function KarigarMetalLedger() {
  const { toast } = useToast();

  const [fromDate, setFromDate]       = useState(fyStart);
  const [toDate, setToDate]           = useState(today);
  const [karigarId, setKarigarId]     = useState("");      // empty = none selected
  const [karigarName, setKarigarName] = useState("");
  const [purityIds, setPurityIds]     = useState([]);      // multi-select
  const [reportType, setReportType]   = useState("main");

  const [karigars, setKarigars] = useState([]);
  const [purities, setPurities] = useState([]);
  const [data, setData]         = useState([]);
  const [loading, setLoading]   = useState(false);

  // Load filter sources — KARIGARS ONLY (role=KR)
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

  const togglePurity = (id) => {
    setPurityIds((prev) =>
      prev.includes(id) ? prev.filter((p) => p !== id) : [...prev, id]
    );
  };

  const load = useCallback(async () => {
    if (!karigarId) {
      toast({ title: "Please select a karigar first.", variant: "destructive" });
      return;
    }
    if (!isValidDateRange(fromDate, toDate)) {
      toast({ title: "From date cannot be after To date.", variant: "destructive" });
      return;
    }
    setLoading(true);
    const params = new URLSearchParams();
    params.append("date", fromDate);
    params.append("to_date", toDate);
    params.append("ledger_ids", String(karigarId));
    if (purityIds.length) params.append("purity_ids", purityIds.join(","));
    params.append("report_type", reportType);

    try {
      const res = await apiClient.get(`/manufacturing/api/metalreport?${params.toString()}`);
      const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
      setData(list);
    } catch (err) {
      toast({
        title: "Failed to load karigar metal report",
        description: err?.response?.data?.detail || err.message,
        variant: "destructive",
      });
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [fromDate, toDate, karigarId, purityIds, reportType, toast]);

  const totals = useMemo(() => {
    let opening = 0, issued = 0, received = 0, wastage = 0;
    data.forEach((kar) => {
      Object.entries(kar.per_purity || {}).forEach(([, pd]) => {
        opening += Number(pd.opening_gold_stock || 0);
        (pd.karigar_gold_issues_after_date || []).forEach((iss) =>
          (iss.issues || []).forEach((it) => { issued += Number(it.conv_wt || 0); })
        );
        (pd.karigar_receive_items_after_date || []).forEach((rec) =>
          (rec.items || []).forEach((it) => {
            received += Number(it.nw || 0);
            wastage  += Number(it.wastage || 0);
          })
        );
      });
    });
    return { opening, issued, received, wastage, balance: opening + issued - received - wastage };
  }, [data]);

  const purityById = useMemo(() => {
    const m = {};
    purities.forEach((p) => { m[String(p.id)] = p; });
    return m;
  }, [purities]);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="size-4 text-primary" />
          <h2 className="text-sm font-semibold text-gray-800">Filters</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
          {/* Karigar — required, searchable */}
          <div className="md:col-span-4">
            <Label className="text-xs">Karigar <span className="text-red-500">*</span></Label>
            <SearchableComboBox
              options={karigars}
              labelKey="ac_name"
              searchKeys={["ac_code", "mobile_number"]}
              value={karigarName}
              placeholder="Search karigar…"
              onSelect={(opt) => {
                setKarigarId(opt?.id ? String(opt.id) : "");
                setKarigarName(opt?.ac_name || "");
              }}
              onInputChange={(val) => {
                setKarigarName(val);
                if (!val) setKarigarId("");
              }}
            />
          </div>

          {/* Dates */}
          <div className="md:col-span-2">
            <Label className="text-xs">From Date</Label>
            <Input type="date" value={fromDate}
              onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} />
          </div>
          <div className="md:col-span-2">
            <Label className="text-xs">To Date</Label>
            <Input type="date" value={toDate}
              onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} />
          </div>

          {/* Report Type — toggle */}
          <div className="md:col-span-2">
            <Label className="text-xs">Report Type</Label>
            <Tabs value={reportType} onValueChange={setReportType}>
              <TabsList className="grid w-full grid-cols-2">
                <TabsTrigger value="main">Main</TabsTrigger>
                <TabsTrigger value="sample">Sample</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {/* Apply */}
          <div className="md:col-span-2">
            <Button className="w-full" onClick={load} disabled={loading || !karigarId}>
              {loading ? "Loading…" : "Apply Filters"}
            </Button>
          </div>

          {/* Purity multi-select chips */}
          <div className="md:col-span-12">
            <Label className="text-xs">Purities (leave empty for all)</Label>
            <div className="flex flex-wrap gap-2 mt-1">
              {purities.map((p) => {
                const id = String(p.id);
                const active = purityIds.includes(id);
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => togglePurity(id)}
                    className={`px-2.5 py-1 rounded-full border text-xs transition ${
                      active
                        ? "bg-primary text-white border-primary"
                        : "bg-white text-gray-700 border-gray-300 hover:border-primary hover:text-primary"
                    }`}
                  >
                    {purityLabel(p.purity)}
                    {active && <X className="inline size-3 ml-1 -mt-0.5" />}
                  </button>
                );
              })}
              {purityIds.length > 0 && (
                <button
                  type="button"
                  onClick={() => setPurityIds([])}
                  className="px-2.5 py-1 rounded-full border border-gray-300 text-xs text-gray-500 hover:text-red-600 hover:border-red-300"
                >
                  Clear
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Empty-state */}
      {!karigarId && !loading && (
        <div className="bg-white border border-dashed border-gray-200 rounded-xl p-8 text-center text-sm text-gray-500">
          Select a karigar above to load the metal ledger.
        </div>
      )}

      {/* Summary */}
      {karigarId && (
        <div className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 text-primary">
              <Coins className="size-4" />
              <span className="text-sm font-semibold">Karigar Metal Ledger ({reportType})</span>
            </div>
            <span className="text-xs text-gray-500">{data.length} karigars</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-5 text-xs gap-3">
            <div><div className="text-gray-500">Opening (g)</div><div className="font-semibold">{num(totals.opening)}</div></div>
            <div><div className="text-gray-500">Issued (g)</div><div className="font-semibold">{num(totals.issued)}</div></div>
            <div><div className="text-gray-500">Received (g)</div><div className="font-semibold">{num(totals.received)}</div></div>
            <div><div className="text-gray-500">Wastage (g)</div><div className="font-semibold text-amber-600">{num(totals.wastage)}</div></div>
            <div><div className="text-gray-500">Net Balance (g)</div><div className="font-semibold">{num(totals.balance)}</div></div>
          </div>
        </div>
      )}

      {/* Loading skeletons */}
      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      )}

      {/* Table */}
      {!loading && karigarId && (
        <div className="bg-white border border-gray-100 rounded-xl shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2 bg-gray-50/50">
            <Coins className="size-4 text-primary" />
            <h3 className="text-sm font-semibold text-gray-800">Metal Ledger Detail</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
                <tr>
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Vou No</th>
                  <th className="px-3 py-2 text-left">Description</th>
                  <th className="px-3 py-2 text-right">Issue (g)</th>
                  <th className="px-3 py-2 text-right">Receive (g)</th>
                  <th className="px-3 py-2 text-right">Add (g)</th>
                  <th className="px-3 py-2 text-right text-amber-600">Wastage (g)</th>
                  <th className="px-3 py-2 text-right">Balance (g)</th>
                  <th className="px-3 py-2 text-right">Fine Wt</th>
                </tr>
              </thead>
              <tbody>
                {data.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-3 py-8 text-center text-gray-400">
                      No metal ledger data for these filters.
                    </td>
                  </tr>
                ) : data.map((karigar) => (
                  <React.Fragment key={karigar.id}>
                    {Object.entries(karigar.per_purity || {}).map(([purity, pd]) => {
                      if (purityIds.length) {
                        const matchesSelected = purityIds.some((pid) => {
                          const p = purityById[pid];
                          return p && String(p.purity).toLowerCase() === String(purity).toLowerCase();
                        });
                        if (!matchesSelected) return null;
                      }
                      const txns = [];
                      (pd.karigar_gold_issues_after_date || []).forEach((iss) =>
                        (iss.issues || []).forEach((it) => txns.push({
                          type: "issue", date: iss.date1, billno: iss.billno,
                          conv_wt: Number(it.conv_wt || 0), net_wt: 0, add_wt: 0, wastage: 0,
                        }))
                      );
                      (pd.karigar_receive_items_after_date || []).forEach((rec) =>
                        (rec.items || []).forEach((it) => txns.push({
                          type: "receive", date: rec.date1, billno: rec.receive_slip_no,
                          conv_wt: 0,
                          net_wt: Number(it.nw || 0),
                          add_wt: Number(it.add_gw || 0),
                          wastage: Number(it.wastage || 0),
                        }))
                      );
                      txns.sort((a, b) => new Date(a.date) - new Date(b.date));
                      let bal = Number(pd.opening_gold_stock || 0);
                      const pur = parseFloat(purity) / 1000;

                      return (
                        <React.Fragment key={`${karigar.id}-${purity}`}>
                          <tr className="bg-violet-50/60 border-t border-violet-100">
                            <td colSpan={9} className="px-3 py-1.5 text-xs font-semibold text-primary">
                              {karigar.ac_name} — {purityLabel(purity)}
                            </td>
                          </tr>
                          <tr className="bg-gray-50/60 border-t border-gray-100">
                            <td className="px-3 py-2">{fmtDate(fromDate)}</td>
                            <td className="px-3 py-2"></td>
                            <td className="px-3 py-2 italic text-gray-500">Opening Balance</td>
                            <td className="px-3 py-2 text-right"></td>
                            <td className="px-3 py-2 text-right"></td>
                            <td className="px-3 py-2 text-right"></td>
                            <td className="px-3 py-2 text-right"></td>
                            <td className="px-3 py-2 text-right font-mono">{num(bal)}</td>
                            <td className="px-3 py-2 text-right font-mono">{num(bal * pur)}</td>
                          </tr>
                          {txns.map((t, ti) => {
                            const isIssue = t.type === "issue";
                            if (isIssue) bal += t.conv_wt;
                            else bal = bal - t.net_wt - t.wastage + t.add_wt;
                            return (
                              <tr key={ti} className="border-t border-gray-100 hover:bg-gray-50">
                                <td className="px-3 py-2 whitespace-nowrap">{fmtDate(t.date)}</td>
                                <td className="px-3 py-2 font-mono text-xs">{t.billno}</td>
                                <td className="px-3 py-2">{isIssue ? "Issue to Karigar" : "Receive from Karigar"}</td>
                                <td className="px-3 py-2 text-right font-mono">{isIssue ? num(t.conv_wt) : ""}</td>
                                <td className="px-3 py-2 text-right font-mono">{!isIssue ? num(t.net_wt) : ""}</td>
                                <td className="px-3 py-2 text-right font-mono">{!isIssue && t.add_wt ? num(t.add_wt) : ""}</td>
                                <td className="px-3 py-2 text-right font-mono text-amber-600">{!isIssue && t.wastage ? num(t.wastage) : ""}</td>
                                <td className="px-3 py-2 text-right font-mono">{num(bal)}</td>
                                <td className="px-3 py-2 text-right font-mono">{num(bal * pur)}</td>
                              </tr>
                            );
                          })}
                        </React.Fragment>
                      );
                    })}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
