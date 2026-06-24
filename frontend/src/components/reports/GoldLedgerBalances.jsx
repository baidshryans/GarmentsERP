import React, { useState, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Loader2, Search, Printer, Scale,
  Users, ArrowUpFromLine, ArrowDownToLine, TrendingDown,
  ChevronDown, Check,
} from "lucide-react";
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

function fmtNum(val) {
  const n = parseFloat(val);
  return isNaN(n) ? 0 : n;
}

function fmtDate(d) {
  if (!d) return "";
  const [y, m, day] = d.split("-");
  return `${day}/${m}/${y}`;
}

// ── API ───────────────────────────────────────────────────────────────────────

async function fetchGoldLedger(params = {}) {
  const q = new URLSearchParams();
  if (params.date)               q.append("date", params.date);
  if (params.to_date)            q.append("to_date", params.to_date);
  if (params.ledger_ids?.length) q.append("ledger_ids", params.ledger_ids.join(","));
  if (params.purity_ids?.length) q.append("purity_ids", params.purity_ids.join(","));
  const res = await apiClient.get(`/manufacturing/api/metalreport?${q.toString()}`);
  return res.data;
}

async function fetchKarigarLedgers(search = "") {
  const q = search
    ? `?search=${encodeURIComponent(search)}&role=KR&page_size=200`
    : `?role=KR&page_size=200`;
  const res = await apiClient.get(`/contacts/api/ledger/${q}`);
  return (res.data.results ?? res.data) || [];
}

async function fetchPurities() {
  const res = await apiClient.get("/goldrates/api/purity/");
  return res.data || [];
}

// ── Balance compute ───────────────────────────────────────────────────────────

function computeBalances(purityData) {
  let periodIssued = 0, periodNW = 0, periodWaste = 0, periodAdd = 0;
  (purityData.karigar_gold_issues_after_date ?? []).forEach((h) =>
    (h.issues ?? []).forEach((item) => { periodIssued += fmtNum(item.conv_wt); })
  );
  (purityData.karigar_receive_items_after_date ?? []).forEach((r) =>
    (r.items ?? []).forEach((item) => {
      periodNW    += fmtNum(item.nw);
      periodWaste += fmtNum(item.wastage);
      periodAdd   += fmtNum(item.add_gw);
    })
  );
  const opening = fmtNum(purityData.opening_gold_stock);
  const closing = opening + periodIssued - periodNW - periodWaste + periodAdd;
  return { opening, periodIssued, periodNW, periodWaste, periodAdd, closing };
}

// ── FilterDropdown ────────────────────────────────────────────────────────────
// Generic floating panel triggered by a button

function FilterDropdown({ label, badge, icon: Icon, children }) {
  const [open, setOpen] = useState(false);
  const [panelStyle, setPanelStyle] = useState({});
  const triggerRef = useRef(null);
  const panelRef = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (
        triggerRef.current && !triggerRef.current.contains(e.target) &&
        panelRef.current  && !panelRef.current.contains(e.target)
      ) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (!open || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    setPanelStyle({
      position: "fixed",
      top: rect.bottom + 6,
      left: rect.left,
      minWidth: Math.max(rect.width, 220),
    });
  }, [open]);

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`
          inline-flex items-center gap-2 h-9 px-3.5 rounded-lg border text-sm
          transition-all duration-150 cursor-pointer select-none
          ${open
            ? "border-primary/60 bg-primary/5 text-primary shadow-sm"
            : "border-border bg-background text-foreground hover:border-primary/40 hover:bg-muted/40"
          }
        `}
      >
        {Icon && <Icon className="size-3.5 text-muted-foreground" />}
        <span className="font-medium text-xs">{label}</span>
        {badge !== null && (
          <span className={`
            text-[10px] font-semibold px-1.5 py-0.5 rounded-full leading-none
            ${open ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}
          `}>
            {badge}
          </span>
        )}
        <ChevronDown className={`size-3.5 text-muted-foreground transition-transform duration-150 ${open ? "rotate-180" : ""}`} />
      </button>

      {open && createPortal(
        <div
          ref={panelRef}
          style={panelStyle}
          className="z-[9999] bg-card border border-border rounded-xl shadow-xl overflow-hidden"
        >
          {children}
        </div>,
        document.body
      )}
    </div>
  );
}

// ── Table helpers ─────────────────────────────────────────────────────────────

const TH = ({ children, className = "" }) => (
  <th className={`px-2.5 py-2 text-[11px] font-semibold text-muted-foreground whitespace-nowrap border-b border-border text-right ${className}`}>
    {children}
  </th>
);
const TD = ({ children, className = "" }) => (
  <td className={`px-2.5 py-2 text-xs border-b border-border text-right font-mono ${className}`}>
    {children}
  </td>
);

function ClosingBadge({ value }) {
  if (value === 0 || isNaN(value)) return <span className="text-muted-foreground text-xs">—</span>;
  if (value < 0) {
    return (
      <span className="inline-flex items-center gap-0.5 bg-green-50 text-green-700 border border-green-200 rounded px-1.5 py-0.5 text-[11px] font-semibold whitespace-nowrap">
        {Math.abs(value).toFixed(3)} Cr
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-0.5 bg-amber-50 text-amber-700 border border-amber-200 rounded px-1.5 py-0.5 text-[11px] font-semibold whitespace-nowrap">
      {value.toFixed(3)} Dr
    </span>
  );
}

function KpiCard({ icon: Icon, iconClass, label, value, sub }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 flex items-start gap-3 shadow-sm">
      <div className={`rounded-lg p-2 shrink-0 ${iconClass}`}>
        <Icon className="size-4" />
      </div>
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-medium">{label}</p>
        <p className="text-xl font-bold font-mono mt-0.5 leading-tight">{value}</p>
        {sub && <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function GoldLedgerBalances() {
  const { toast } = useToast();

  const [purities, setPurities]               = useState([]);
  const [karigarList, setKarigarList]         = useState([]);
  const [filteredKarigar, setFilteredKarigar] = useState([]);
  const [karigarSearch, setKarigarSearch]     = useState("");

  const [fromDate, setFromDate] = useState(fyStart);
  const [toDate, setToDate]     = useState(today);

  const [selPurity,  setSelPurity]  = useState({ all: true, ids: [] });
  const [selKarigar, setSelKarigar] = useState({ all: true, ids: [] });

  const [data, setData]       = useState([]);
  const [loading, setLoading] = useState(false);
  const [fetched, setFetched] = useState(false);

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

  useEffect(() => {
    const t = setTimeout(() => {
      fetchKarigarLedgers(karigarSearch).then(setFilteredKarigar);
    }, 300);
    return () => clearTimeout(t);
  }, [karigarSearch]);

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
        date:       fromDate,
        to_date:    toDate,
        ledger_ids: selKarigar.all ? [] : selKarigar.ids,
        purity_ids: selPurity.all  ? [] : selPurity.ids,
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

  const activePurities = purities.filter((p) => selPurity.all || selPurity.ids.includes(p.id));
  const purityKeys = activePurities.map((p) => ({
    id: p.id,
    label: p.purity,
    key: p.purity.toLowerCase().replace(" ", "_"),
  }));

  const grandTotals = purityKeys.map(({ key }) => {
    const t = { opening: 0, periodIssued: 0, periodNW: 0, periodWaste: 0, periodAdd: 0, closing: 0 };
    data.forEach((k) => {
      const pd = k.per_purity?.[key];
      if (!pd) return;
      const b = computeBalances(pd);
      t.opening      += b.opening;
      t.periodIssued += b.periodIssued;
      t.periodNW     += b.periodNW;
      t.periodWaste  += b.periodWaste;
      t.periodAdd    += b.periodAdd;
      t.closing      += b.closing;
    });
    return t;
  });

  const kpiIssued   = grandTotals.reduce((s, t) => s + t.periodIssued, 0);
  const kpiReceived = grandTotals.reduce((s, t) => s + t.periodNW, 0);
  const kpiDrTotal  = grandTotals.reduce((s, t) => s + Math.max(0, t.closing), 0);

  const karigarBadge = selKarigar.all ? "All" : `${selKarigar.ids.length}`;
  const purityBadge  = selPurity.all  ? "All" : `${selPurity.ids.length}`;

  const hasData = fetched && data.length > 0;

  return (
    <div className="flex flex-col gap-5">

      {/* ── Compact Filter Card ── */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {/* Title bar */}
        <div className="px-5 py-3 border-b border-border bg-gradient-to-r from-primary/5 to-accent-500/5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-1.5">
              <Scale className="size-4 text-primary" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-foreground">Gold Ledger Balances</h1>
              <p className="text-[10px] text-muted-foreground">Karigar-wise gold stock movement</p>
            </div>
          </div>
          {fetched && (
            <span className="text-[10px] bg-muted rounded-full px-3 py-1 text-muted-foreground font-mono">
              {fmtDate(fromDate)} → {fmtDate(toDate)}
            </span>
          )}
        </div>

        {/* Filter bar — single compact row */}
        <div className="px-4 py-3 flex flex-wrap items-center gap-2">

          {/* Karigar multi-select */}
          <FilterDropdown label="Karigar" badge={karigarBadge} icon={Users}>
            <div className="p-2 border-b border-border">
              <Input
                placeholder="Search karigar…"
                value={karigarSearch}
                onChange={(e) => setKarigarSearch(e.target.value)}
                className="h-7 text-xs"
                autoFocus
              />
            </div>
            <div className="max-h-52 overflow-y-auto p-2 space-y-0.5">
              {/* All toggle */}
              <label className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-muted/50 cursor-pointer">
                <Checkbox
                  checked={selKarigar.all}
                  onCheckedChange={(c) => toggleKarigar("all", c)}
                />
                <span className="text-xs font-semibold">All karigars</span>
                <span className="ml-auto text-[10px] text-muted-foreground">{karigarList.length}</span>
              </label>
              <div className="my-1 border-t border-border/50" />
              {filteredKarigar.map((k) => (
                <label key={k.id} className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-muted/50 cursor-pointer group">
                  <Checkbox
                    checked={selKarigar.ids.includes(k.id)}
                    onCheckedChange={(c) => toggleKarigar(k.id, c)}
                  />
                  <span className="text-xs truncate text-muted-foreground group-hover:text-foreground transition-colors">
                    {k.ac_name}
                  </span>
                  {selKarigar.ids.includes(k.id) && (
                    <Check className="size-3 text-primary ml-auto shrink-0" />
                  )}
                </label>
              ))}
              {filteredKarigar.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-3">No karigars found</p>
              )}
            </div>
          </FilterDropdown>

          {/* Purity multi-select */}
          <FilterDropdown label="Purity" badge={purityBadge} icon={null}>
            <div className="p-3 space-y-1">
              <label className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg hover:bg-muted/50 cursor-pointer">
                <Checkbox
                  checked={selPurity.all}
                  onCheckedChange={(c) => togglePurity("all", c)}
                />
                <span className="text-xs font-semibold">All purities</span>
              </label>
              <div className="border-t border-border/50 my-1" />
              {/* Pill grid */}
              <div className="grid grid-cols-3 gap-1.5 pt-0.5">
                {purities.map((p) => {
                  const selected = selPurity.ids.includes(p.id);
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => togglePurity(p.id, !selected)}
                      className={`
                        px-2 py-1.5 rounded-lg text-[11px] font-semibold border transition-all duration-100 cursor-pointer
                        ${selected
                          ? "bg-primary text-primary-foreground border-primary shadow-sm"
                          : "bg-background text-muted-foreground border-border hover:border-primary/50 hover:text-foreground"
                        }
                      `}
                    >
                      {p.purity}
                    </button>
                  );
                })}
              </div>
            </div>
          </FilterDropdown>

          {/* Divider */}
          <div className="h-6 w-px bg-border mx-1" />

          {/* Date range */}
          <div className="flex items-center gap-1.5">
            <div className="flex flex-col gap-0.5">
              <label className="text-[9px] uppercase tracking-wider text-muted-foreground px-0.5">From</label>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                max={toDate || undefined}
                className="h-8 text-xs px-2.5 rounded-lg border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring w-[130px]"
              />
            </div>
            <span className="text-muted-foreground text-sm mt-4">→</span>
            <div className="flex flex-col gap-0.5">
              <label className="text-[9px] uppercase tracking-wider text-muted-foreground px-0.5">To</label>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                min={fromDate || undefined}
                className="h-8 text-xs px-2.5 rounded-lg border border-border bg-background focus:outline-none focus:ring-1 focus:ring-ring w-[130px]"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-end gap-2 ml-auto">
            <Button onClick={handleSearch} disabled={loading} className="h-9">
              {loading
                ? <Loader2 className="size-4 mr-1.5 animate-spin" />
                : <Search className="size-4 mr-1.5" />}
              {loading ? "Loading…" : "Generate"}
            </Button>
            {hasData && (
              <Button variant="outline" className="h-9" onClick={() => window.print()}>
                <Printer className="size-4 mr-1.5" />
                Print
              </Button>
            )}
          </div>
        </div>

        {/* Helper text */}
        <div className="px-5 pb-2.5 text-[10px] text-muted-foreground/70">
          Opening balance calculated <em>as on</em> From Date · Period movements shown between From → To
        </div>
      </div>

      {/* ── KPI Cards ── */}
      {hasData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiCard icon={Users}            iconClass="bg-primary/10 text-primary"       label="Karigars"         value={data.length}                                    sub={`${purityKeys.length} purit${purityKeys.length !== 1 ? "ies" : "y"}`} />
          <KpiCard icon={ArrowUpFromLine}  iconClass="bg-amber-100 text-amber-600"      label="Total Issued"     value={kpiIssued   > 0 ? kpiIssued.toFixed(3)   : "—"} sub="grams issued in period" />
          <KpiCard icon={ArrowDownToLine} iconClass="bg-green-100 text-green-600"      label="Total Received"   value={kpiReceived > 0 ? kpiReceived.toFixed(3) : "—"} sub="net weight returned" />
          <KpiCard icon={TrendingDown}     iconClass={kpiDrTotal > 0 ? "bg-amber-100 text-amber-600" : "bg-muted text-muted-foreground"} label="Net Outstanding" value={kpiDrTotal > 0 ? kpiDrTotal.toFixed(3) : "—"} sub="gold with karigars (Dr)" />
        </div>
      )}

      {/* ── Loading skeleton ── */}
      {loading && (
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-border bg-muted/30 flex items-center gap-3">
            <Skeleton className="h-4 w-4 rounded" />
            <Skeleton className="h-4 w-56" />
          </div>
          <div className="p-4 space-y-2">
            {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-8 w-full rounded" />)}
          </div>
        </div>
      )}

      {/* ── Empty prompt ── */}
      {!fetched && !loading && (
        <div className="rounded-xl border border-border bg-gradient-to-br from-muted/30 to-background shadow-sm flex flex-col items-center justify-center py-20 gap-3">
          <div className="rounded-full bg-muted p-4">
            <Scale className="size-7 text-muted-foreground/50" />
          </div>
          <p className="text-sm font-medium text-muted-foreground">No report generated yet</p>
          <p className="text-xs text-muted-foreground/70">Select filters above and click Generate</p>
        </div>
      )}

      {/* ── No results ── */}
      {fetched && !loading && data.length === 0 && (
        <div className="rounded-xl border border-border bg-gradient-to-br from-muted/30 to-background shadow-sm flex flex-col items-center justify-center py-20 gap-3">
          <div className="rounded-full bg-muted p-4">
            <Scale className="size-7 text-muted-foreground/50" />
          </div>
          <p className="text-sm font-medium text-muted-foreground">No data found</p>
          <p className="text-xs text-muted-foreground/70">No karigar gold ledger data for the selected criteria.</p>
        </div>
      )}

      {/* ── Report Table ── */}
      {hasData && (
        <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-border bg-muted/30 flex items-center gap-3">
            <Scale className="size-4 text-primary" />
            <span className="text-sm font-semibold">Period Statement</span>
            <span className="text-xs text-muted-foreground font-mono">{fmtDate(fromDate)} → {fmtDate(toDate)}</span>
            <span className="ml-auto text-xs text-muted-foreground">{data.length} karigar{data.length !== 1 ? "s" : ""}</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead className="sticky top-0 z-10">
                <tr>
                  <th rowSpan={2} className="px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground border-b border-border whitespace-nowrap bg-muted/50 sticky left-0 z-20">
                    Karigar
                  </th>
                  {purityKeys.map(({ label }) => (
                    <th key={label} colSpan={6} className="px-2 py-1.5 text-center text-xs font-bold border-b border-border border-l border-accent-200 bg-accent-100 text-accent-800 whitespace-nowrap">
                      {label}
                    </th>
                  ))}
                </tr>
                <tr className="bg-muted/60">
                  {purityKeys.map(({ label }) => (
                    <React.Fragment key={label}>
                      <TH className="border-l border-accent-200">Opening</TH>
                      <TH>Issued</TH>
                      <TH>Received</TH>
                      <TH>Wastage</TH>
                      <TH>Add Wt</TH>
                      <TH className="text-primary">Closing</TH>
                    </React.Fragment>
                  ))}
                </tr>
              </thead>

              <tbody>
                {data.map((karigar, ri) => (
                  <tr key={karigar.id} className={`hover:bg-primary/5 transition-colors duration-150 ${ri % 2 === 0 ? "" : "bg-muted/10"}`}>
                    <td className="px-3 py-2 text-xs font-medium border-b border-border whitespace-nowrap sticky left-0 bg-inherit z-10">
                      {karigar.ac_name}
                    </td>
                    {purityKeys.map(({ key }) => {
                      const pd = karigar.per_purity?.[key];
                      if (!pd) return (
                        <React.Fragment key={key}>
                          {[...Array(6)].map((_, i) => (
                            <TD key={i} className={i === 0 ? "border-l border-accent-200 text-muted-foreground/40" : "text-muted-foreground/40"}>—</TD>
                          ))}
                        </React.Fragment>
                      );
                      const { opening, periodIssued, periodNW, periodWaste, periodAdd, closing } = computeBalances(pd);
                      return (
                        <React.Fragment key={key}>
                          <TD className="border-l border-accent-200">{fmt(opening)}</TD>
                          <TD>{fmt(periodIssued)}</TD>
                          <TD>{fmt(periodNW)}</TD>
                          <TD>{fmt(periodWaste)}</TD>
                          <TD>{fmt(periodAdd)}</TD>
                          <td className="px-2.5 py-2 text-right border-b border-border">
                            <ClosingBadge value={closing} />
                          </td>
                        </React.Fragment>
                      );
                    })}
                  </tr>
                ))}
              </tbody>

              <tfoot>
                <tr className="bg-gradient-to-r from-accent-50 to-indigo-50 border-t-2 border-accent-300">
                  <td className="px-3 py-2.5 text-xs font-bold text-primary border-b border-accent-200 sticky left-0 bg-gradient-to-r from-accent-50 to-accent-50 z-10">
                    Grand Total
                  </td>
                  {grandTotals.map((tot, pi) => (
                    <React.Fragment key={pi}>
                      <TD className="border-l border-accent-200 font-bold text-primary">{fmt(tot.opening)}</TD>
                      <TD className="font-bold text-primary">{fmt(tot.periodIssued)}</TD>
                      <TD className="font-bold text-primary">{fmt(tot.periodNW)}</TD>
                      <TD className="font-bold text-primary">{fmt(tot.periodWaste)}</TD>
                      <TD className="font-bold text-primary">{fmt(tot.periodAdd)}</TD>
                      <td className="px-2.5 py-2.5 text-right border-b border-accent-200">
                        <ClosingBadge value={tot.closing} />
                      </td>
                    </React.Fragment>
                  ))}
                </tr>
              </tfoot>
            </table>
          </div>

          {/* Legend */}
          <div className="px-5 py-3 border-t border-border bg-muted/10 flex flex-wrap gap-x-5 gap-y-1.5 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-muted-foreground/40 inline-block" /><strong>Opening</strong> — balance as on From Date</span>
            <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-amber-400 inline-block" /><strong>Issued</strong> — gold issued in period</span>
            <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-green-400 inline-block" /><strong>Received</strong> — net weight returned</span>
            <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-red-400 inline-block" /><strong>Wastage</strong> — wastage on receive</span>
            <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-blue-400 inline-block" /><strong>Add Wt</strong> — additional weight</span>
            <span className="flex items-center gap-1.5"><span className="inline-flex items-center bg-amber-50 text-amber-700 border border-amber-200 rounded px-1 text-[9px] font-semibold">Dr</span> gold outstanding</span>
            <span className="flex items-center gap-1.5"><span className="inline-flex items-center bg-green-50 text-green-700 border border-green-200 rounded px-1 text-[9px] font-semibold">Cr</span> over-received</span>
          </div>
        </div>
      )}
    </div>
  );
}
