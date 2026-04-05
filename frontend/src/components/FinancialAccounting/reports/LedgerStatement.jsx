import { useState, useEffect, useRef, useCallback } from "react";
import { getLedgers, getFiscalYears } from "@/services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Search } from "lucide-react";
import apiClient from "@/services/apiClient";

const today = new Date().toISOString().split("T")[0];

export default function LedgerStatement() {
  const [selectedLedger, setSelectedLedger] = useState(null); // { id, ac_name, ... }
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState(today);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Debounced ledger search
  const [searchTerm, setSearchTerm] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchLoading, setSearchLoading] = useState(false);
  const [dropdownRect, setDropdownRect] = useState(null);
  const timerRef = useRef(null);
  const wrapperRef = useRef(null);

  const updateDropdownRect = useCallback(() => {
    if (wrapperRef.current) {
      const r = wrapperRef.current.getBoundingClientRect();
      setDropdownRect({ top: r.bottom + window.scrollY, left: r.left + window.scrollX, width: r.width });
    }
  }, []);

  // Default from_date to FY start
  useEffect(() => {
    getFiscalYears().then((res) => {
      if (res.success) {
        const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
        const activeFy = data.find((fy) => fy.is_active);
        if (activeFy?.fy_start) {
          setFromDate(activeFy.fy_start);
        } else {
          // Fallback: April 1 of current FY
          const now = new Date();
          const fyYear = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
          setFromDate(`${fyYear}-04-01`);
        }
      }
    });
  }, []);

  // Close dropdown on outside click; reposition on scroll/resize
  useEffect(() => {
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    const handleReposition = () => { if (showDropdown) updateDropdownRect(); };
    document.addEventListener("mousedown", handleClick);
    window.addEventListener("scroll", handleReposition, true);
    window.addEventListener("resize", handleReposition);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      window.removeEventListener("scroll", handleReposition, true);
      window.removeEventListener("resize", handleReposition);
    };
  }, [showDropdown, updateDropdownRect]);

  // Debounced search
  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!searchTerm || searchTerm.length < 2) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }
    setSearchLoading(true);
    timerRef.current = setTimeout(async () => {
      const res = await getLedgers({ type: "", search: searchTerm });
      if (res.success) {
        setSuggestions(res.data.results || []);
        updateDropdownRect();
        setShowDropdown(true);
      }
      setSearchLoading(false);
    }, 300);
    return () => clearTimeout(timerRef.current);
  }, [searchTerm]);

  const handleSelectLedger = (ledger) => {
    setSelectedLedger(ledger);
    setSearchTerm(ledger.ac_name);
    setShowDropdown(false);
  };

  const fetchReport = async () => {
    if (!selectedLedger) { setError("Please select a ledger."); return; }
    setError("");
    setLoading(true);
    try {
      const res = await apiClient.get(
        `/accounting/api/ledger-statement/?ledger_id=${selectedLedger.id}&from_date=${fromDate}&to_date=${toDate}`
      );
      setReport(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load report.");
    }
    setLoading(false);
  };

  const fmt = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2 });
  const balLabel = (v) => {
    const n = Number(v);
    if (n === 0) return "—";
    return `${fmt(Math.abs(n))} ${n >= 0 ? "Dr" : "Cr"}`;
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        {/* Ledger search */}
        <div className="flex flex-col gap-1 min-w-64 relative" ref={wrapperRef}>
          <Label className="text-xs">Ledger Account</Label>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
            <Input
              className="h-9 pl-8 text-sm"
              placeholder="Search by name, mobile, phone…"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                if (selectedLedger && e.target.value !== selectedLedger.ac_name) {
                  setSelectedLedger(null);
                }
              }}
              onFocus={() => {
                if (suggestions.length > 0) { updateDropdownRect(); setShowDropdown(true); }
              }}
            />
          </div>
          {showDropdown && dropdownRect && (
            <div
              style={{
                position: "fixed",
                top: dropdownRect.top,
                left: dropdownRect.left,
                width: dropdownRect.width,
                zIndex: 9999,
              }}
              className="mt-1 max-h-64 overflow-y-auto rounded-lg border border-border bg-popover shadow-lg"
            >
              {searchLoading ? (
                <div className="px-3 py-4 text-xs text-muted-foreground">Searching…</div>
              ) : suggestions.length === 0 ? (
                <div className="px-3 py-4 text-xs text-muted-foreground">No results found.</div>
              ) : (
                suggestions.map((l) => (
                  <button
                    key={l.id}
                    type="button"
                    onMouseDown={(e) => { e.preventDefault(); handleSelectLedger(l); }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent/50 flex items-center justify-between gap-3 transition-colors"
                  >
                    <div className="flex flex-col min-w-0">
                      <span className="font-medium truncate">{l.ac_name}</span>
                      {(l.mobile1 || l.phone1) && (
                        <span className="text-[11px] text-muted-foreground">{l.mobile1 || l.phone1}</span>
                      )}
                    </div>
                    <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-medium text-muted-foreground shrink-0">{l.type}</span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="h-9 w-36" />
        </div>
        <Button size="sm" onClick={fetchReport} className="h-9" disabled={!selectedLedger}>Show</Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {report && !loading && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-foreground">{report.ledger_name}</h3>
              <p className="text-xs text-muted-foreground">
                {report.from_date} to {report.to_date}
              </p>
            </div>
            <div className="text-right text-sm">
              <p className="text-muted-foreground">Opening Balance</p>
              <p className="font-semibold">{balLabel(report.opening_balance)}</p>
            </div>
          </div>

          <div className="rounded-lg border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2.5 text-left font-semibold">Date</th>
                  <th className="px-4 py-2.5 text-left font-semibold">Voucher No</th>
                  <th className="px-4 py-2.5 text-left font-semibold">Type</th>
                  <th className="px-4 py-2.5 text-left font-semibold">Narration</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Debit</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Credit</th>
                  <th className="px-4 py-2.5 text-right font-semibold">Balance</th>
                </tr>
              </thead>
              <tbody>
                {report.transactions.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center py-8 text-muted-foreground">No transactions in this period.</td>
                  </tr>
                )}
                {report.transactions.map((t, i) => (
                  <tr key={i} className={`border-t border-border ${i % 2 === 1 ? "bg-muted/20" : ""} hover:bg-accent/30 transition-colors`}>
                    <td className="px-4 py-2">{t.date}</td>
                    <td className="px-4 py-2 font-mono text-xs">{t.voucher_no}</td>
                    <td className="px-4 py-2">
                      <span className="text-xs bg-muted px-1.5 py-0.5 rounded font-medium">{t.voucher_type}</span>
                    </td>
                    <td className="px-4 py-2 text-muted-foreground truncate max-w-48">{t.narration}</td>
                    <td className="px-4 py-2 text-right">{Number(t.debit) > 0 ? fmt(t.debit) : ""}</td>
                    <td className="px-4 py-2 text-right">{Number(t.credit) > 0 ? fmt(t.credit) : ""}</td>
                    <td className="px-4 py-2 text-right font-medium">{balLabel(t.running_balance)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-border bg-muted/50 font-semibold">
                  <td colSpan={4} className="px-4 py-2.5 text-sm">Closing Balance</td>
                  <td className="px-4 py-2.5 text-right text-sm">
                    {fmt(report.transactions.reduce((s, t) => s + Number(t.debit), 0))}
                  </td>
                  <td className="px-4 py-2.5 text-right text-sm">
                    {fmt(report.transactions.reduce((s, t) => s + Number(t.credit), 0))}
                  </td>
                  <td className="px-4 py-2.5 text-right text-sm">{balLabel(report.closing_balance)}</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
