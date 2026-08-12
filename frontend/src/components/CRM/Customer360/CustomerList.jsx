// The customer book: who they are, what they're worth, and when they're due.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, SlidersHorizontal, UserSearch } from "lucide-react";

import { fetchCustomers } from "@/services/api/customerIntel";
import {
  ConfidenceNote,
  EmptyNote,
  LapseBadge,
  Money,
  RfmBadge,
  SegmentChip,
} from "./badges";

const SEGMENTS = [
  "champion", "loyal", "cant_lose", "at_risk", "hibernating", "lost",
  "new", "promising", "potential_loyalist", "needs_attention", "about_to_sleep",
];

const ORDERINGS = [
  { value: "-lifetime_value",     label: "Lifetime value" },
  { value: "-net_spend",          label: "Recent spend" },
  { value: "-last_purchase_date", label: "Most recent purchase" },
  { value: "-days_since_last",    label: "Longest silent" },
  { value: "-engagement_score",   label: "Most engaged" },
  { value: "ac_name",             label: "Name (A–Z)" },
];

const PAGE_SIZE = 25;

export default function CustomerList() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [segment, setSegment] = useState("");
  const [lapse, setLapse] = useState("");
  const [ordering, setOrdering] = useState("-lifetime_value");
  const [buyersOnly, setBuyersOnly] = useState(true);
  const [minSpend, setMinSpend] = useState("");
  const [silentDays, setSilentDays] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(q), 350);
    return () => clearTimeout(timer);
  }, [q]);

  const filters = useMemo(() => ({
    q: debouncedQ,
    rfm_segment: segment,
    lapse_band: lapse,
    ordering,
    buyers_only: buyersOnly ? "true" : "false",
    min_spend: minSpend,
    silent_days: silentDays,
    page,
    page_size: PAGE_SIZE,
  }), [debouncedQ, segment, lapse, ordering, buyersOnly, minSpend, silentDays, page]);

  // Any filter change invalidates the current page number.
  useEffect(() => {
    setPage(1);
  }, [debouncedQ, segment, lapse, ordering, buyersOnly, minSpend, silentDays]);

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchCustomers(filters);
    if (result.success) {
      setRows(result.data.results || []);
      setCount(result.data.count || 0);
      setError("");
    } else {
      setRows([]);
      setError(
        typeof result.error === "string"
          ? result.error
          : result.error?.detail || "Could not load customers.",
      );
    }
    setLoading(false);
  }, [filters]);

  useEffect(() => { load(); }, [load]);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));

  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search name, mobile or email…"
            className="w-full rounded-md border border-slate-200 py-2 pl-9 pr-3 text-sm focus:border-indigo-400 focus:outline-none"
          />
        </div>

        <select
          value={ordering}
          onChange={(e) => setOrdering(e.target.value)}
          className="rounded-md border border-slate-200 px-3 py-2 text-sm"
        >
          {ORDERINGS.map((o) => (
            <option key={o.value} value={o.value}>Sort: {o.label}</option>
          ))}
        </select>

        <button
          type="button"
          onClick={() => setShowFilters((v) => !v)}
          className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm ${
            showFilters ? "border-indigo-300 bg-indigo-50 text-indigo-700" : "border-slate-200 text-slate-600"
          }`}
        >
          <SlidersHorizontal className="h-4 w-4" /> Filters
        </button>
      </div>

      {showFilters && (
        <div className="grid gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 sm:grid-cols-2 lg:grid-cols-5">
          <label className="text-xs text-slate-600">
            Segment
            <select
              value={segment}
              onChange={(e) => setSegment(e.target.value)}
              className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
            >
              <option value="">Any</option>
              {SEGMENTS.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
              ))}
            </select>
          </label>

          <label className="text-xs text-slate-600">
            Lapse risk
            <select
              value={lapse}
              onChange={(e) => setLapse(e.target.value)}
              className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
            >
              <option value="">Any</option>
              {["healthy", "due", "at_risk", "lapsed"].map((b) => (
                <option key={b} value={b}>{b.replace(/_/g, " ")}</option>
              ))}
            </select>
          </label>

          <label className="text-xs text-slate-600">
            Min lifetime spend
            <input
              type="number"
              value={minSpend}
              onChange={(e) => setMinSpend(e.target.value)}
              placeholder="e.g. 100000"
              className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
            />
          </label>

          <label className="text-xs text-slate-600">
            Silent for at least (days)
            <input
              type="number"
              value={silentDays}
              onChange={(e) => setSilentDays(e.target.value)}
              placeholder="e.g. 180"
              className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
            />
          </label>

          <label className="flex items-end gap-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={buyersOnly}
              onChange={(e) => setBuyersOnly(e.target.checked)}
              className="mb-2 h-4 w-4"
            />
            <span className="mb-1.5">Only customers who have bought</span>
          </label>
        </div>
      )}

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>{loading ? "Loading…" : `${count.toLocaleString("en-IN")} customer${count === 1 ? "" : "s"}`}</span>
        {totalPages > 1 && (
          <span className="flex items-center gap-2">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40"
            >
              Previous
            </button>
            <span>Page {page} of {totalPages}</span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded border border-slate-200 px-2 py-1 disabled:opacity-40"
            >
              Next
            </button>
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {!loading && !error && rows.length === 0 && (
        <EmptyNote>
          No customers match these filters.
          {buyersOnly && " Try unchecking “Only customers who have bought”."}
        </EmptyNote>
      )}

      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-slate-200">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Customer</th>
                <th className="px-3 py-2">Segment</th>
                <th className="px-3 py-2 text-right">Lifetime value</th>
                <th className="px-3 py-2 text-right">Bills</th>
                <th className="px-3 py-2">Last purchase</th>
                <th className="px-3 py-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => navigate(`/crm/customers/${row.ledger_id}`)}
                  className="cursor-pointer hover:bg-indigo-50/40"
                >
                  <td className="px-3 py-2">
                    <div className="font-medium text-slate-800">{row.ac_name}</div>
                    <div className="text-xs text-slate-500">
                      {row.mobile1 || "no mobile"}{row.city ? ` · ${row.city}` : ""}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <SegmentChip segment={row.rfm_segment} />
                      <RfmBadge
                        cell={row.rfm_cell}
                        r={row.r_score}
                        f={row.f_score}
                        m={row.m_score}
                        basis={row.scoring_basis}
                      />
                    </div>
                  </td>
                  <td className="px-3 py-2 text-right font-medium tabular-nums">
                    <Money value={row.lifetime_value} />
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                    {row.purchase_count_all}
                  </td>
                  <td className="px-3 py-2 text-slate-600">
                    {row.last_purchase_date || "—"}
                    {row.days_since_last != null && (
                      <span className="block text-xs text-slate-400">
                        {row.days_since_last} days ago
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {/* Lapse risk is only shown where there is enough history
                        to justify it; otherwise the confidence note explains
                        why there is no verdict. */}
                    {row.confidence === "medium" || row.confidence === "high" ? (
                      <LapseBadge band={row.lapse_band} />
                    ) : (
                      <ConfidenceNote level={row.confidence} reason={row.confidence_reason} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="flex items-center gap-2 text-xs text-slate-400">
        <UserSearch className="h-3.5 w-3.5" />
        Scores refresh nightly. Cadence and lapse risk need at least two purchases before they mean anything.
      </p>
    </div>
  );
}
