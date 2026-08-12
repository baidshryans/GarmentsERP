// Today's call list — who to contact, why, and one tap to do it.
//
// Every row states its reason in plain English. A ranked list without
// justification gets ignored, and rightly so.
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageCircle, Phone, RefreshCw, StickyNote, UserSearch } from "lucide-react";

import { fetchWorklist, logCustomerNote } from "@/services/api/customerIntel";
import { ConfidenceNote, EmptyNote, Money, SegmentChip } from "./badges";

const REASON_STYLES = {
  occasion_today:         { label: "Birthday today",   cls: "bg-pink-100 text-pink-800" },
  occasion_soon:          { label: "Occasion soon",    cls: "bg-pink-50 text-pink-700" },
  order_ready:            { label: "Order ready",      cls: "bg-emerald-100 text-emerald-800" },
  scheme_matured:         { label: "Scheme maturing",  cls: "bg-teal-100 text-teal-800" },
  approval_overdue:       { label: "Goods out",        cls: "bg-red-100 text-red-800" },
  scheme_payment_overdue: { label: "Payment overdue",  cls: "bg-orange-100 text-orange-800" },
  catalog_intent:         { label: "Browsing",         cls: "bg-indigo-100 text-indigo-800" },
  receivable_overdue:     { label: "Owes money",       cls: "bg-amber-100 text-amber-800" },
  lapse_risk:             { label: "Slipping away",    cls: "bg-orange-100 text-orange-800" },
  due_to_buy:             { label: "Due to buy",       cls: "bg-blue-100 text-blue-800" },
  incomplete_profile:     { label: "Missing details",  cls: "bg-slate-100 text-slate-700" },
};

const FILTERS = [
  { value: "", label: "Everything" },
  { value: "occasion_today,occasion_soon", label: "Occasions" },
  { value: "order_ready,scheme_matured", label: "Ready / maturing" },
  { value: "approval_overdue,receivable_overdue", label: "Money & goods out" },
  { value: "lapse_risk,due_to_buy,catalog_intent", label: "Sales opportunities" },
  { value: "incomplete_profile", label: "Missing details" },
];

function waLink(mobile) {
  const digits = String(mobile || "").replace(/\D/g, "").slice(-10);
  return digits ? `https://wa.me/91${digits}` : null;
}

export default function Worklist() {
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reason, setReason] = useState("");
  const [includeContacted, setIncludeContacted] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchWorklist({
      reason,
      limit: 100,
      include_contacted: includeContacted ? "true" : "",
    });
    if (result.success) {
      setRows(result.data.results || []);
      setError("");
    } else {
      setError("Could not load the worklist.");
    }
    setLoading(false);
  }, [reason, includeContacted]);

  useEffect(() => { load(); }, [load]);

  // Logging the contact is what removes them from tomorrow's list.
  const logContact = async (row, how) => {
    await logCustomerNote(row.ledger_id, {
      channel: how,
      subject: "Contacted from the daily worklist",
      body: `Reason: ${row.reason}`,
    });
    setRows((current) => current.filter((r) => r.ledger_id !== row.ledger_id));
  };

  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-800">Today's calls</h1>
          <p className="text-sm text-slate-500">
            Ranked by why they need contacting and how much they're worth.
            Contacting someone hides them for a week.
          </p>
        </div>
        <button
          type="button"
          onClick={load}
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setReason(f.value)}
            className={`rounded-full px-3 py-1 text-sm ${
              reason === f.value
                ? "bg-indigo-600 text-white"
                : "border border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {f.label}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-1.5 text-xs text-slate-500">
          <input
            type="checkbox"
            checked={includeContacted}
            onChange={(e) => setIncludeContacted(e.target.checked)}
            className="h-3.5 w-3.5"
          />
          Include recently contacted
        </label>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-slate-500">Loading…</p>}

      {!loading && rows.length === 0 && (
        <EmptyNote>
          Nothing needs chasing right now. Everyone with a reason to be called
          has been contacted in the last week.
        </EmptyNote>
      )}

      <div className="space-y-2">
        {rows.map((row) => {
          const style = REASON_STYLES[row.reason_code] || {
            label: row.reason_code, cls: "bg-slate-100 text-slate-700",
          };
          const wa = waLink(row.mobile);
          return (
            <div
              key={row.ledger_id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-3"
            >
              <div className="min-w-[180px] flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(`/crm/customers/${row.ledger_id}`)}
                    className="font-medium text-slate-800 hover:text-indigo-700"
                  >
                    {row.ac_name}
                  </button>
                  <span className={`rounded px-2 py-0.5 text-xs font-medium ${style.cls}`}>
                    {style.label}
                  </span>
                  <SegmentChip segment={row.rfm_segment} />
                </div>
                <div className="mt-0.5 text-sm text-slate-600">{row.reason}</div>
                {row.other_reasons?.length > 0 && (
                  <div className="mt-0.5 text-xs text-slate-400">
                    also: {row.other_reasons.join(" · ")}
                  </div>
                )}
                {["lapse_risk", "due_to_buy"].includes(row.reason_code) && (
                  <div className="mt-1">
                    <ConfidenceNote level={row.confidence} showLabel={false} />
                  </div>
                )}
              </div>

              <div className="text-right">
                <div className="text-sm font-medium text-slate-700">
                  <Money value={row.lifetime_value} />
                </div>
                <div className="text-xs text-slate-400">lifetime</div>
              </div>

              <div className="flex items-center gap-1.5">
                {row.mobile && (
                  <a
                    href={`tel:${row.mobile}`}
                    onClick={() => logContact(row, "call")}
                    className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
                  >
                    <Phone className="h-3.5 w-3.5" /> Call
                  </a>
                )}
                {wa && (
                  <a
                    href={wa}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => logContact(row, "whatsapp")}
                    className="inline-flex items-center gap-1 rounded bg-emerald-600 px-2 py-1.5 text-xs text-white hover:bg-emerald-700"
                  >
                    <MessageCircle className="h-3.5 w-3.5" /> WhatsApp
                  </a>
                )}
                <button
                  type="button"
                  onClick={() => logContact(row, "note")}
                  title="Mark as handled"
                  className="rounded border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50"
                >
                  <StickyNote className="h-3.5 w-3.5" />
                </button>
                <button
                  type="button"
                  onClick={() => navigate(`/crm/customers/${row.ledger_id}`)}
                  title="Open the full profile"
                  className="rounded border border-slate-200 p-1.5 text-slate-500 hover:bg-slate-50"
                >
                  <UserSearch className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
