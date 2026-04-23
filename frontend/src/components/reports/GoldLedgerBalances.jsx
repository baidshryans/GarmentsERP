import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, Search, SlidersHorizontal, Printer, Scale } from "lucide-react";
import apiClient from "@/services/apiClient";
import { useToast } from "@/hooks/use-toast";
import { isValidDateRange } from "@/lib/dateRange";

// ── Helpers ───────────────────────────────────────────────────────────────────

const today = new Date().toISOString().split("T")[0];
const fyStart = (() => {
  const now = new Date();
  const yr = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
  return `${yr}-04-01`;
})();

function fmt(val, decimals = 3) {
  const n = parseFloat(val);
  if (isNaN(n) || n === 0) return "—";
  return n.toFixed(decimals);
}

function fmtNum(val, decimals = 3) {
  const n = parseFloat(val);
  if (isNaN(n)) return 0;
  return n;
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function fetchGoldLedger(params = {}) {
  const q = new URLSearchParams();
  if (params.date)        q.append("date", params.date);
  if (params.to_date)     q.append("to_date", params.to_date);
  if (params.ledger_ids?.length)  q.append("ledger_ids", params.ledger_ids.join(","));
  if (params.purity_ids?.length)  q.append("purity_ids", params.purity_ids.join(","));
  const res = await apiClient.get(`/manufacturing/api/metalreport?${q.toString()}`);
  return res.data;
}

async function fetchKarigarLedgers(search = "") {
  const q = search ? `?search=${encodeURIComponent(search)}&type=KR` : `?type=KR`;
  const res = await apiClient.get(`/contacts/api/ledger/${q}`);
  return (res.data.results ?? res.data) || [];
}

async function fetchPurities() {
  const res = await apiClient.get("/goldrates/api/purity/");
  return res.data || [];
}

// ── Compute closing balance from API data for one karigar/purity ──────────────

function computeBalances(purityData) {
  let periodIssued = 0;
  let periodNW     = 0;
  let periodWaste  = 0;
  let periodAdd    = 0;

  (purityData.karigar_gold_issues_after_date ?? []).forEach((header) =>
    (header.issues ?? []).forEach((item) => {
      periodIssued += fmtNum(item.conv_wt);
    })
  );

  (purityData.karigar_receive_items_after_date ?? []).forEach((recv) =>
    (recv.items ?? []).forEach((item) => {
      periodNW    += fmtNum(item.nw);
      periodWaste += fmtNum(item.wastage);
      periodAdd   += fmtNum(item.add_gw);
    })
  );

  const opening = fmtNum(purityData.opening_gold_stock);
  const closing = opening + periodIssued - periodNW - periodWaste + periodAdd;

  return { opening, periodIssued, periodNW, periodWaste, periodAdd, closing };
}

// ── Table helpers ─────────────────────────────────────────────────────────────

const TH = ({ children, className = "" }) => (
  <th
    className={`px-2.5 py-2 text-xs font-semibold text-muted-foreground whitespace-nowrap border-b border-border text-right ${className}`}
  >
    {children}
  </th>
);
const TD = ({ children, className = "" }) => (
  <td className={`px-2.5 py-2 text-xs border-b border-border text-right font-mono ${className}`}>
    {children}
  </td>
);

// ── Main component ────────────────────────────────────────────────────────────

export default function GoldLedgerBalances() {
  const { toast } = useToast();

  const [purities, setPurities]               = useState([]);
  const [karigarList, setKarigarList]         = useState([]);
  const [filteredKarigar, setFilteredKarigar] = useState([]);
  const [karigarSearch, setKarigarSearch]     = useState("");

  const [fromDate, setFromDate] = useState(fyStart);
  const [toDate, setToDate]     = useState(today);

  const [selPurity, setSelPurity]   = useState({ all: true, ids: [] });
  const [selKarigar, setSelKarigar] = useState({ all: true, ids: [] });

  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

  // Load master data on mount
  useEffect(() => {
    fetchPurities().then((ps) => {
      setPurities(ps);
      setSelPurity({ all: true, ids: ps.map((p) => p.id) });
    });
    fetchKarigarLedgers().then((ks) => {
      setKarigarList(ks);
      setFilteredKarigar(ks);
      setSelKarigar({ all: true, ids: ks.map((k) => k.id) });
    });
  }, []);

  // Debounced karigar search
  useEffect(() => {
    const t = setTimeout(() => {
      fetchKarigarLedgers(karigarSearch).then(setFilteredKarigar);
    }, 300);
    return () => clearTimeout(t);
  }, [karigarSearch]);

  // Purity toggle
  const togglePurity = (id, checked) => {
    if (id === "all") {
      setSelPurity({ all: checked, ids: checked ? purities.map((p) => p.id) : [] });
    } else {
      setSelPurity((prev) => {
        const ids = checked ? [...prev.ids, id] : prev.ids.filter((x) => x !== id);
        return { all: ids.length === purities.length, ids };
      });
    }
  };

  // Karigar toggle
  const toggleKarigar = (id, checked) => {
    if (id === "all") {
      setSelKarigar({ all: checked, ids: checked ? karigarList.map((k) => k.id) : [] });
    } else {
      setSelKarigar((prev) => {
        const ids = checked ? [...prev.ids, id] : prev.ids.filter((x) => x !== id);
        return { all: ids.length === karigarList.length, ids };
      });
    }
  };

  const handleSearch = async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      toast({ title: "From date cannot be after To date.", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const result = await fetchGoldLedger({
        date:        fromDate,
        to_date:     toDate,
        ledger_ids:  selKarigar.all ? [] : selKarigar.ids,
        purity_ids:  selPurity.all  ? [] : selPurity.ids,
      });
      setData(result);
      setFetched(true);
    } catch (e) {
      toast({
        title: "Failed to load report",
        description: e.response?.data?.error || e.message,
        variant: "destructive",
      });
    }
    setLoading(false);
  };

  // Which purities to render as columns (resolved from response)
  const activePurities = purities.filter(
    (p) => selPurity.all || selPurity.ids.includes(p.id)
  );
  const purityKeys = activePurities.map((p) => ({
    id: p.id,
    label: p.purity,
    key: p.purity.toLowerCase().replace(" ", "_"),
  }));

  // Grand totals across all karigars per purity
  const grandTotals = purityKeys.map(({ key }) => {
    const totals = { opening: 0, periodIssued: 0, periodNW: 0, periodWaste: 0, periodAdd: 0, closing: 0 };
    data.forEach((karigar) => {
      const pd = karigar.per_purity?.[key];
      if (!pd) return;
      const b = computeBalances(pd);
      totals.opening      += b.opening;
      totals.periodIssued += b.periodIssued;
      totals.periodNW     += b.periodNW;
      totals.periodWaste  += b.periodWaste;
      totals.periodAdd    += b.periodAdd;
      totals.closing      += b.closing;
    });
    return totals;
  });

  const hasData = fetched && data.length > 0;

  return (
    <div className="flex flex-col gap-5">
      {/* ── Filters ── */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-muted/30">
          <SlidersHorizontal className="size-4 text-primary" />
          <span className="text-sm font-semibold">Filters</span>
          {fetched && (
            <span className="ml-auto text-xs text-muted-foreground">
              {fromDate} — {toDate}
            </span>
          )}
        </div>

        <div className="p-4 grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Karigar */}
          <div className="flex flex-col gap-1">
            <Label className="text-xs font-medium">Karigar</Label>
            <div className="border border-border rounded-lg bg-background max-h-48 overflow-y-auto p-2 space-y-1.5">
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={selKarigar.all}
                  onCheckedChange={(c) => toggleKarigar("all", c)}
                />
                <span className="text-xs">All</span>
              </label>
              {filteredKarigar.map((k) => (
                <label key={k.id} className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={selKarigar.ids.includes(k.id)}
                    onCheckedChange={(c) => toggleKarigar(k.id, c)}
                  />
                  <span className="text-xs truncate">{k.ac_name}</span>
                </label>
              ))}
            </div>
            <Input
              placeholder="Search karigar…"
              value={karigarSearch}
              onChange={(e) => setKarigarSearch(e.target.value)}
              className="h-8 text-xs mt-1"
            />
          </div>

          {/* Purity */}
          <div className="flex flex-col gap-1">
            <Label className="text-xs font-medium">Purity</Label>
            <div className="border border-border rounded-lg bg-background max-h-48 overflow-y-auto p-2 space-y-1.5">
              <label className="flex items-center gap-2 cursor-pointer">
                <Checkbox
                  checked={selPurity.all}
                  onCheckedChange={(c) => togglePurity("all", c)}
                />
                <span className="text-xs">All</span>
              </label>
              {purities.map((p) => (
                <label key={p.id} className="flex items-center gap-2 cursor-pointer">
                  <Checkbox
                    checked={selPurity.ids.includes(p.id)}
                    onCheckedChange={(c) => togglePurity(p.id, c)}
                  />
                  <span className="text-xs">{p.purity}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Dates + Search */}
          <div className="md:col-span-2 flex flex-col gap-3 justify-start">
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <Label className="text-xs">From Date (Opening as on)</Label>
                <Input
                  type="date"
                  value={fromDate}
                  onChange={(e) => setFromDate(e.target.value)}
                  max={toDate || undefined}
                  className="h-9 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label className="text-xs">To Date</Label>
                <Input
                  type="date"
                  value={toDate}
                  onChange={(e) => setToDate(e.target.value)}
                  min={fromDate || undefined}
                  className="h-9 text-sm"
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Opening balance is calculated as on <strong>From Date</strong>. Transactions between From and To Date are shown as period movements.
            </p>
            <div className="flex gap-2 mt-auto">
              <Button
                onClick={handleSearch}
                disabled={loading}
                className="bg-primary hover:bg-primary text-white h-9"
              >
                {loading ? (
                  <Loader2 className="size-4 mr-1.5 animate-spin" />
                ) : (
                  <Search className="size-4 mr-1.5" />
                )}
                {loading ? "Loading…" : "Generate Report"}
              </Button>
              {hasData && (
                <Button
                  variant="outline"
                  className="h-9"
                  onClick={() => window.print()}
                >
                  <Printer className="size-4 mr-1.5" />
                  Print
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Report Table ── */}
      {!fetched && !loading && (
        <div className="rounded-xl border border-border bg-card shadow-sm flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
          <Scale className="size-10 opacity-30" />
          <p className="text-sm">Select filters and click Generate Report to view gold ledger balances.</p>
        </div>
      )}

      {loading && (
        <div className="rounded-xl border border-border bg-card shadow-sm flex items-center justify-center py-16">
          <Loader2 className="size-6 animate-spin text-primary" />
        </div>
      )}

      {fetched && !loading && data.length === 0 && (
        <div className="rounded-xl border border-border bg-card shadow-sm flex flex-col items-center justify-center py-16 gap-2 text-muted-foreground">
          <Scale className="size-10 opacity-30" />
          <p className="text-sm">No karigar gold ledger data found for the selected criteria.</p>
        </div>
      )}

      {hasData && (
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-border bg-muted/30 flex items-center gap-3">
            <Scale className="size-4 text-primary" />
            <span className="text-sm font-semibold">Gold Ledger Balances</span>
            <span className="text-xs text-muted-foreground ml-1">
              {fromDate} → {toDate}
            </span>
            <span className="ml-auto text-xs text-muted-foreground">
              {data.length} karigar{data.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 sticky top-0 z-10">
                <tr>
                  <th
                    className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground border-b border-border whitespace-nowrap"
                    rowSpan={2}
                  >
                    Karigar
                  </th>
                  {purityKeys.map(({ label }) => (
                    <th
                      key={label}
                      colSpan={6}
                      className="px-2 py-1 text-center text-xs font-bold text-primary border-b border-border border-l border-violet-200 bg-violet-50/60 whitespace-nowrap"
                    >
                      {label}
                    </th>
                  ))}
                </tr>
                <tr className="bg-muted/30">
                  {purityKeys.map(({ label }) => (
                    <React.Fragment key={label}>
                      <TH className="border-l border-violet-200">Opening</TH>
                      <TH>Issued</TH>
                      <TH>Received</TH>
                      <TH>Wastage</TH>
                      <TH>Add Wt</TH>
                      <TH className="text-primary font-bold">Closing</TH>
                    </React.Fragment>
                  ))}
                </tr>
              </thead>

              <tbody>
                {data.map((karigar) => (
                  <tr key={karigar.id} className="hover:bg-muted/20 transition-colors">
                    <td className="px-3 py-2 text-xs font-medium border-b border-border whitespace-nowrap">
                      {karigar.ac_name}
                    </td>
                    {purityKeys.map(({ key, label }, pi) => {
                      const pd = karigar.per_purity?.[key];
                      if (!pd) {
                        return (
                          <React.Fragment key={key}>
                            {[...Array(6)].map((_, i) => (
                              <TD key={i} className={i === 0 ? "border-l border-violet-200" : ""}>—</TD>
                            ))}
                          </React.Fragment>
                        );
                      }
                      const { opening, periodIssued, periodNW, periodWaste, periodAdd, closing } =
                        computeBalances(pd);
                      return (
                        <React.Fragment key={key}>
                          <TD className="border-l border-violet-200">{fmt(opening)}</TD>
                          <TD>{fmt(periodIssued)}</TD>
                          <TD>{fmt(periodNW)}</TD>
                          <TD>{fmt(periodWaste)}</TD>
                          <TD>{fmt(periodAdd)}</TD>
                          <TD
                            className={`font-bold ${
                              closing < 0
                                ? "text-green-700"
                                : closing > 0
                                ? "text-amber-700"
                                : "text-muted-foreground"
                            }`}
                          >
                            {fmt(Math.abs(closing))}
                            {closing < 0 ? " Cr" : closing > 0 ? " Dr" : ""}
                          </TD>
                        </React.Fragment>
                      );
                    })}
                  </tr>
                ))}
              </tbody>

              {/* Grand Total */}
              <tfoot className="bg-violet-50/70 border-t-2 border-violet-300">
                <tr>
                  <td className="px-3 py-2.5 text-xs font-bold text-primary border-b border-border">
                    Grand Total
                  </td>
                  {grandTotals.map((tot, pi) => (
                    <React.Fragment key={pi}>
                      <TD className="border-l border-violet-200 font-bold text-primary">
                        {fmt(tot.opening)}
                      </TD>
                      <TD className="font-bold text-primary">{fmt(tot.periodIssued)}</TD>
                      <TD className="font-bold text-primary">{fmt(tot.periodNW)}</TD>
                      <TD className="font-bold text-primary">{fmt(tot.periodWaste)}</TD>
                      <TD className="font-bold text-primary">{fmt(tot.periodAdd)}</TD>
                      <TD
                        className={`font-bold text-base ${
                          tot.closing < 0
                            ? "text-green-700"
                            : tot.closing > 0
                            ? "text-amber-700"
                            : "text-muted-foreground"
                        }`}
                      >
                        {fmt(Math.abs(tot.closing))}
                        {tot.closing < 0 ? " Cr" : tot.closing > 0 ? " Dr" : ""}
                      </TD>
                    </React.Fragment>
                  ))}
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Legend */}
          <div className="px-5 py-3 border-t border-border bg-muted/20 flex flex-wrap gap-4 text-xs text-muted-foreground">
            <span><strong>Opening</strong> = Balance with karigar as on From Date</span>
            <span><strong>Issued</strong> = Gold issued in the period</span>
            <span><strong>Received</strong> = Net weight received back</span>
            <span><strong>Wastage</strong> = Wastage deducted on receive</span>
            <span><strong>Add Wt</strong> = Additional weight received</span>
            <span><strong className="text-amber-700">Dr</strong> = Gold outstanding (karigar owes)</span>
            <span><strong className="text-green-700">Cr</strong> = Over-received</span>
          </div>
        </div>
      )}
    </div>
  );
}
