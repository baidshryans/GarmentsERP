import { useState, useEffect, useRef, useCallback } from "react";
import { getLedgers, getFiscalYears, fetchCompanies } from "@/services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Search, Printer, Download, X } from "lucide-react";
import apiClient from "@/services/apiClient";
import { printReport } from "@/lib/printReport";
import { isValidDateRange } from "@/lib/dateRange";

const today = new Date().toISOString().split("T")[0];

const fmt = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2 });
const balLabel = (v) => {
  const n = Number(v);
  if (n === 0) return "—";
  return `${fmt(Math.abs(n))} ${n >= 0 ? "Dr" : "Cr"}`;
};
const toDdMm = (s) => {
  const [y, m, d] = (s || "").split("-");
  return y && m && d ? `${d}-${m}-${y}` : s;
};

export default function LedgerStatement() {
  const [selectedLedgers, setSelectedLedgers] = useState([]); // [{ id, ac_name, ... }, ...]
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState(today);
  const [reports, setReports] = useState([]); // parallel to selectedLedgers, in fetch order
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [companyName, setCompanyName] = useState("");

  useEffect(() => {
    fetchCompanies().then((res) => {
      if (res.success) {
        const results = res.data?.results || res.data || [];
        if (results.length > 0) setCompanyName(results[0].company_name || "");
      }
    });
  }, []);

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

  const addLedger = (ledger) => {
    setSelectedLedgers((prev) => (prev.some((l) => l.id === ledger.id) ? prev : [...prev, ledger]));
    setSearchTerm("");
    setSuggestions([]);
    setShowDropdown(false);
  };

  const removeLedger = (id) => {
    setSelectedLedgers((prev) => prev.filter((l) => l.id !== id));
    setReports((prev) => prev.filter((r) => r.__ledger_id !== id));
  };

  const fetchReport = async () => {
    if (!isValidDateRange(fromDate, toDate)) {
      setError("From date cannot be after To date.");
      return;
    }
    if (selectedLedgers.length === 0) { setError("Please select at least one ledger."); return; }
    setError("");
    setLoading(true);
    setReports([]);
    try {
      const results = await Promise.all(
        selectedLedgers.map((l) =>
          apiClient
            .get(`/accounting/api/ledger-statement/?ledger_id=${l.id}&from_date=${fromDate}&to_date=${toDate}`)
            .then((res) => ({ ...res.data, __ledger_id: l.id }))
            .catch((e) => ({ __ledger_id: l.id, __error: e.response?.data?.error || "Failed to load." , ledger_name: l.ac_name }))
        )
      );
      setReports(results);
    } catch (e) {
      setError("Failed to load one or more ledger statements.");
    }
    setLoading(false);
  };

  const buildReportTableHtml = (report) => {
    const totalDr = report.transactions.reduce((s, t) => s + Number(t.debit), 0);
    const totalCr = report.transactions.reduce((s, t) => s + Number(t.credit), 0);
    const rows = report.transactions.map((t, i) => `
      <tr${i % 2 === 1 ? ' style="background:#fafafa"' : ""}>
        <td>${toDdMm(t.date)}</td>
        <td class="font-mono">${t.voucher_no || ""}</td>
        <td>${t.voucher_type || ""}</td>
        <td>${(t.narration || "").replace(/</g, "&lt;")}</td>
        <td style="text-align:right" class="tabular-nums">${Number(t.debit) > 0 ? fmt(t.debit) : ""}</td>
        <td style="text-align:right" class="tabular-nums">${Number(t.credit) > 0 ? fmt(t.credit) : ""}</td>
        <td style="text-align:right" class="tabular-nums">${balLabel(t.running_balance)}</td>
      </tr>
    `).join("");
    return `
      <div style="margin:14px 0 6px;display:flex;justify-content:space-between;font-size:12px;border-bottom:1px solid #cbd5e1;padding-bottom:4px">
        <div><strong>${report.ledger_name}</strong></div>
        <div><strong>Opening:</strong> ${balLabel(report.opening_balance)}</div>
      </div>
      <table>
        <thead>
          <tr>
            <th style="text-align:left">Date</th>
            <th style="text-align:left">Voucher No</th>
            <th style="text-align:left">Type</th>
            <th style="text-align:left">Narration</th>
            <th style="text-align:right">Debit</th>
            <th style="text-align:right">Credit</th>
            <th style="text-align:right">Balance</th>
          </tr>
        </thead>
        <tbody>
          ${rows || `<tr><td colspan="7" style="text-align:center;padding:12px;color:#64748b">No transactions in this period.</td></tr>`}
        </tbody>
        <tfoot>
          <tr class="totals-row">
            <td colspan="4">Closing Balance</td>
            <td style="text-align:right" class="tabular-nums">${fmt(totalDr)}</td>
            <td style="text-align:right" class="tabular-nums">${fmt(totalCr)}</td>
            <td style="text-align:right" class="tabular-nums">${balLabel(report.closing_balance)}</td>
          </tr>
        </tfoot>
      </table>
    `;
  };

  const handlePrint = () => {
    const usable = reports.filter((r) => !r.__error);
    if (usable.length === 0) return;
    const sections = usable
      .map((r, i) => `<section${i > 0 ? ' style="page-break-before:always"' : ""}>${buildReportTableHtml(r)}</section>`)
      .join("");
    const title = usable.length === 1
      ? `Ledger Statement — ${usable[0].ledger_name}`
      : `Ledger Statements (${usable.length} ledgers)`;
    printReport({
      title,
      subtitle: `${toDdMm(fromDate)} to ${toDdMm(toDate)}`,
      html: sections,
      landscape: true,
      company: companyName,
    });
  };

  const handleDownloadCsv = () => {
    const usable = reports.filter((r) => !r.__error);
    if (usable.length === 0) return;
    const esc = (v) => {
      const s = v == null ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [];
    usable.forEach((report, idx) => {
      if (idx > 0) lines.push("");
      lines.push(`Ledger:,${esc(report.ledger_name)}`);
      lines.push(`Period:,${report.from_date} to ${report.to_date}`);
      lines.push(`Opening Balance:,${report.opening_balance}`);
      lines.push("");
      lines.push(["Date", "Voucher No", "Type", "Narration", "Debit", "Credit", "Running Balance"].join(","));
      for (const t of report.transactions) {
        lines.push([t.date, t.voucher_no, t.voucher_type, t.narration, t.debit, t.credit, t.running_balance].map(esc).join(","));
      }
      const totalDr = report.transactions.reduce((s, t) => s + Number(t.debit), 0);
      const totalCr = report.transactions.reduce((s, t) => s + Number(t.credit), 0);
      lines.push(["", "", "", "Closing Balance", totalDr, totalCr, report.closing_balance].map(esc).join(","));
    });

    const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const baseName = usable.length === 1
      ? (usable[0].ledger_name || "ledger").replace(/[^a-z0-9]+/gi, "_")
      : `${usable.length}_ledgers`;
    a.href = url;
    a.download = `ledger_statement_${baseName}_${fromDate}_to_${toDate}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const hasReports = reports.length > 0;

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        {/* Ledger search */}
        <div className="flex flex-col gap-1 min-w-64 relative" ref={wrapperRef}>
          <Label className="text-xs">Ledger Accounts (add multiple)</Label>
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 size-3.5 text-muted-foreground" />
            <Input
              className="h-9 pl-8 text-sm"
              placeholder="Search by name, mobile, phone…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
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
                suggestions.map((l) => {
                  const alreadyPicked = selectedLedgers.some((s) => s.id === l.id);
                  return (
                    <button
                      key={l.id}
                      type="button"
                      disabled={alreadyPicked}
                      onMouseDown={(e) => { e.preventDefault(); if (!alreadyPicked) addLedger(l); }}
                      className={`w-full text-left px-3 py-2 text-sm flex items-center justify-between gap-3 transition-colors ${alreadyPicked ? "opacity-50 cursor-not-allowed" : "hover:bg-accent/50"}`}
                    >
                      <div className="flex flex-col min-w-0">
                        <span className="font-medium truncate">{l.ac_name}{alreadyPicked && <span className="ml-2 text-[10px] text-muted-foreground">(added)</span>}</span>
                        {(l.mobile1 || l.phone1) && (
                          <span className="text-[11px] text-muted-foreground">{l.mobile1 || l.phone1}</span>
                        )}
                      </div>
                      <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded font-medium text-muted-foreground shrink-0">{l.type}</span>
                    </button>
                  );
                })
              )}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} className="h-9 w-36" />
        </div>
        <Button size="sm" onClick={fetchReport} className="h-9" disabled={selectedLedgers.length === 0}>
          Show {selectedLedgers.length > 1 ? `(${selectedLedgers.length})` : ""}
        </Button>
        {hasReports && (
          <>
            <Button size="sm" variant="outline" onClick={handlePrint} className="h-9 ml-auto gap-1.5">
              <Printer className="size-4" /> Print
            </Button>
            <Button size="sm" variant="outline" onClick={handleDownloadCsv} className="h-9 gap-1.5">
              <Download className="size-4" /> CSV
            </Button>
          </>
        )}
      </div>

      {/* Selected ledger chips */}
      {selectedLedgers.length > 0 && (
        <div className="flex flex-wrap gap-2 -mt-2">
          {selectedLedgers.map((l) => (
            <span
              key={l.id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-accent/60 border border-border text-xs font-medium"
            >
              {l.ac_name}
              <button
                type="button"
                onClick={() => removeLedger(l.id)}
                className="hover:bg-destructive/20 rounded-full p-0.5"
                aria-label={`Remove ${l.ac_name}`}
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
          {selectedLedgers.length > 1 && (
            <button
              type="button"
              onClick={() => { setSelectedLedgers([]); setReports([]); }}
              className="text-xs text-muted-foreground hover:text-foreground underline"
            >
              Clear all
            </button>
          )}
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {/* Render each ledger report */}
      {!loading && reports.map((report) => {
        if (report.__error) {
          return (
            <div key={report.__ledger_id} className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
              <strong>{report.ledger_name}:</strong> {report.__error}
            </div>
          );
        }
        const totalDr = report.transactions.reduce((s, t) => s + Number(t.debit), 0);
        const totalCr = report.transactions.reduce((s, t) => s + Number(t.credit), 0);
        return (
          <div key={report.__ledger_id} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-foreground">{report.ledger_name}</h3>
                <p className="text-xs text-muted-foreground">
                  {toDdMm(report.from_date)} to {toDdMm(report.to_date)}
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
                      <td className="px-4 py-2">{toDdMm(t.date)}</td>
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
                    <td className="px-4 py-2.5 text-right text-sm">{fmt(totalDr)}</td>
                    <td className="px-4 py-2.5 text-right text-sm">{fmt(totalCr)}</td>
                    <td className="px-4 py-2.5 text-right text-sm">{balLabel(report.closing_balance)}</td>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        );
      })}
    </div>
  );
}
