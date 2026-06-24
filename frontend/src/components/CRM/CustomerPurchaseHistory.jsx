import { useState, useEffect, useRef, useCallback } from "react";
import { getLedgers, getFiscalYears } from "@/services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import apiClient from "@/services/apiClient";
import { isValidDateRange } from "@/lib/dateRange";

const today = new Date().toISOString().split("T")[0];

const TYPE_COLORS = {
  Sale:     "bg-green-100 text-green-800",
  Return:   "bg-red-100 text-red-800",
  Order:    "bg-amber-100 text-amber-800",
  Approval: "bg-blue-100 text-blue-800",
};

export default function CustomerPurchaseHistory() {
  const [selectedLedger, setSelectedLedger] = useState(null);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState(today);
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("All");

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

  useEffect(() => {
    getFiscalYears().then((res) => {
      if (res.success) {
        const data = Array.isArray(res.data) ? res.data : res.data?.results ?? [];
        const activeFy = data.find((fy) => fy.is_active);
        if (activeFy?.fy_start) setFromDate(activeFy.fy_start);
        else {
          const now = new Date();
          const fyYear = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
          setFromDate(`${fyYear}-04-01`);
        }
      }
    });
  }, []);

  useEffect(() => {
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) setShowDropdown(false);
    };
    document.addEventListener("mousedown", handleClick);
    window.addEventListener("scroll", updateDropdownRect, true);
    window.addEventListener("resize", updateDropdownRect);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      window.removeEventListener("scroll", updateDropdownRect, true);
      window.removeEventListener("resize", updateDropdownRect);
    };
  }, [updateDropdownRect]);

  const handleSearchChange = (e) => {
    const v = e.target.value;
    setSearchTerm(v);
    setSelectedLedger(null);
    clearTimeout(timerRef.current);
    if (!v.trim()) { setSuggestions([]); setShowDropdown(false); return; }
    timerRef.current = setTimeout(async () => {
      setSearchLoading(true);
      const res = await getLedgers({ search: v, type: "CO,DL,SD,SC", page_size: 15 });
      if (res.success) {
        const items = res.data?.results ?? res.data ?? [];
        setSuggestions(items);
        setShowDropdown(true);
        updateDropdownRect();
      }
      setSearchLoading(false);
    }, 300);
  };

  const handleSelect = (ledger) => {
    setSelectedLedger(ledger);
    setSearchTerm(ledger.ac_name);
    setShowDropdown(false);
    setReport(null);
    setError("");
  };

  const handleFetch = async () => {
    if (!selectedLedger) return;
    if (!isValidDateRange(fromDate, toDate)) {
      setError("From date cannot be after To date.");
      return;
    }
    setLoading(true);
    setError("");
    setReport(null);
    try {
      const params = new URLSearchParams({ ledger_id: selectedLedger.id });
      if (fromDate) params.set("from_date", fromDate);
      if (toDate) params.set("to_date", toDate);
      const res = await apiClient.get(`/sales/api/customer-history/?${params}`);
      setReport(res.data);
    } catch (e) {
      setError(e.response?.data?.error || "Failed to load history");
    }
    setLoading(false);
  };

  const filtered = report?.transactions?.filter(
    (r) => filter === "All" || r.doc_type === filter
  ) ?? [];

  const docTypes = ["All", "Sale", "Return", "Order", "Approval"];

  return (
    <div className="container mt-5 max-w-5xl">
      <h6 className="text-lg font-semibold mb-4">Customer Purchase History</h6>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end mb-5">
        <div ref={wrapperRef} className="relative flex-1 min-w-[200px]">
          <label className="text-xs text-gray-500 mb-1 block">Customer / Ledger</label>
          <Input
            value={searchTerm}
            onChange={handleSearchChange}
            onFocus={() => { if (suggestions.length) { setShowDropdown(true); updateDropdownRect(); } }}
            placeholder="Search by name..."
          />
          {showDropdown && suggestions.length > 0 && dropdownRect && (
            <div
              className="fixed z-50 bg-white border border-gray-200 rounded shadow-lg overflow-y-auto"
              style={{ top: dropdownRect.top, left: dropdownRect.left, width: dropdownRect.width, maxHeight: 240 }}
            >
              {searchLoading && <div className="px-3 py-2 text-xs text-gray-400">Searching…</div>}
              {suggestions.map((s) => (
                <div
                  key={s.id}
                  className="px-3 py-2 hover:bg-accent-50 cursor-pointer text-sm"
                  onMouseDown={() => handleSelect(s)}
                >
                  <span className="font-medium">{s.ac_name}</span>
                  {s.mobile1 && <span className="ml-2 text-xs text-gray-400">{s.mobile1}</span>}
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="text-xs text-gray-500 mb-1 block">From</label>
          <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} className="w-36" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">To</label>
          <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} className="w-36" />
        </div>
        <Button onClick={handleFetch} disabled={!selectedLedger || loading}>
          {loading ? "Loading…" : "Fetch History"}
        </Button>
      </div>

      {error && <div className="text-red-500 text-sm mb-4">{error}</div>}

      {loading && (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {report && !loading && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            {[
              { label: "Total Sales", value: `₹${report.summary.total_sales.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`, color: "text-green-700" },
              { label: "Total Returns", value: `₹${report.summary.total_returns.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`, color: "text-red-600" },
              { label: "Net Purchases", value: `₹${report.summary.net.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`, color: "text-primary font-semibold" },
              { label: "Open Orders", value: report.summary.order_count, color: "text-amber-700" },
            ].map((c) => (
              <div key={c.label} className="rounded-lg border border-gray-200 bg-white p-3 shadow-sm">
                <p className="text-xs text-gray-500">{c.label}</p>
                <p className={`text-lg font-semibold ${c.color}`}>{c.value}</p>
              </div>
            ))}
          </div>

          {/* Filter tabs */}
          <div className="flex gap-2 mb-3 flex-wrap">
            {docTypes.map((t) => (
              <button
                key={t}
                onClick={() => setFilter(t)}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
                  filter === t
                    ? "bg-primary text-white border-primary"
                    : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Table */}
          {filtered.length === 0 ? (
            <p className="text-gray-400 text-sm">No transactions found.</p>
          ) : (
            <div className="overflow-x-auto rounded border border-gray-200">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-600 uppercase">
                  <tr>
                    <th className="px-3 py-2 text-left">Date</th>
                    <th className="px-3 py-2 text-left">Type</th>
                    <th className="px-3 py-2 text-left">Doc No</th>
                    <th className="px-3 py-2 text-right">Amount (₹)</th>
                    <th className="px-3 py-2 text-right">Tax (₹)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((r, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-3 py-2 whitespace-nowrap">
                        {new Date(r.date).toLocaleDateString("en-GB").replaceAll("/", "-")}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[r.doc_type] || ""}`}>
                          {r.doc_type}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">{r.doc_no}</td>
                      <td className="px-3 py-2 text-right">{r.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                      <td className="px-3 py-2 text-right text-gray-500">{r.tax.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
