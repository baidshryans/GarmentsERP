// Customer 360 — everything we know about one customer, in one place.
import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, MessageCircle, Phone } from "lucide-react";

import {
  fetchCustomerProfile,
  fetchCustomerTimeline,
  logCustomerNote,
  updateCustomerSocial,
} from "@/services/api/customerIntel";
import { ConfidenceNote, EmptyNote, Money, RfmBadge, SegmentChip } from "./badges";
import OverviewPanel from "./panels/OverviewPanel";
import PreferencesPanel from "./panels/PreferencesPanel";
import PurchasesPanel from "./panels/PurchasesPanel";
import RelationshipsPanel from "./panels/RelationshipsPanel";
import TimelinePanel from "./panels/TimelinePanel";

const TABS = [
  { key: "overview",      label: "Overview" },
  { key: "preferences",   label: "What they buy" },
  { key: "purchases",     label: "Purchases" },
  { key: "relationships", label: "Orders & schemes" },
  { key: "timeline",      label: "Timeline" },
];

export default function CustomerProfile() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [profile, setProfile] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("overview");

  const load = useCallback(async () => {
    setLoading(true);
    const result = await fetchCustomerProfile(id);
    if (result.success) {
      setProfile(result.data);
      setError("");
    } else {
      setError(
        typeof result.error === "string"
          ? result.error
          : result.error?.detail || "Could not load this customer.",
      );
    }
    setLoading(false);
  }, [id]);

  const loadTimeline = useCallback(async () => {
    const result = await fetchCustomerTimeline(id, { page_size: 50 });
    if (result.success) setTimeline(result.data.results || []);
  }, [id]);

  useEffect(() => { load(); loadTimeline(); }, [load, loadTimeline]);

  const handleNote = async (body) => {
    const result = await logCustomerNote(id, { body });
    if (result.success) await loadTimeline();
    return result;
  };

  const handleCapture = async (payload) => {
    const result = await updateCustomerSocial(id, payload);
    if (result.success) await load();
    return result;
  };

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Loading customer…</div>;
  }
  if (error) {
    return (
      <div className="p-6">
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      </div>
    );
  }

  const { ledger, snapshot } = profile;
  const mobile = ledger.mobile1;

  return (
    <div className="space-y-4 p-4">
      <button
        type="button"
        onClick={() => navigate("/crm/customers")}
        className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
      >
        <ArrowLeft className="h-4 w-4" /> All customers
      </button>

      {/* ── header ─────────────────────────────────────────────────────── */}
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-xl font-semibold text-slate-800">
              {ledger.salutation ? `${ledger.salutation} ` : ""}{ledger.ac_name}
            </h1>
            <div className="text-sm text-slate-500">
              {[mobile, ledger.email, ledger.city].filter(Boolean).join(" · ") || "No contact details on file"}
            </div>
            {snapshot && (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <SegmentChip segment={snapshot.rfm_segment} />
                <RfmBadge
                  cell={snapshot.rfm_cell}
                  r={snapshot.r_score}
                  f={snapshot.f_score}
                  m={snapshot.m_score}
                  basis={snapshot.scoring_basis}
                />
                <ConfidenceNote
                  level={snapshot.confidence}
                  reason={snapshot.confidence_reason}
                />
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-xs uppercase tracking-wide text-slate-400">Lifetime value</div>
              <div className="text-2xl font-semibold text-slate-800">
                <Money value={snapshot?.lifetime_value} />
              </div>
              <div className="text-xs text-slate-500">
                {snapshot?.purchase_count_all || 0} purchase
                {snapshot?.purchase_count_all === 1 ? "" : "s"}
              </div>
            </div>

            {mobile && (
              <div className="flex flex-col gap-2">
                <a
                  href={`tel:${mobile}`}
                  className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                >
                  <Phone className="h-4 w-4" /> Call
                </a>
                <a
                  href={`https://wa.me/91${String(mobile).replace(/\D/g, "").slice(-10)}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-700"
                >
                  <MessageCircle className="h-4 w-4" /> WhatsApp
                </a>
              </div>
            )}
          </div>
        </div>

        {profile.consent?.opted_out && (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
            This customer has opted out of marketing messages. Campaigns will skip them.
          </div>
        )}
      </div>

      {/* ── tabs ───────────────────────────────────────────────────────── */}
      <div className="flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm ${
              tab === t.key
                ? "border-indigo-500 font-medium text-indigo-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <OverviewPanel profile={profile} onCapture={handleCapture} />
      )}
      {tab === "preferences" && <PreferencesPanel snapshot={snapshot} />}
      {tab === "purchases" && <PurchasesPanel profile={profile} />}
      {tab === "relationships" && <RelationshipsPanel profile={profile} />}
      {tab === "timeline" && (
        <TimelinePanel events={timeline} onNote={handleNote} />
      )}

      {!snapshot && (
        <EmptyNote>
          No analytics have been computed for this customer yet. They appear after the
          nightly rebuild (<code>manage.py rebuild_customer_profiles</code>).
        </EmptyNote>
      )}
    </div>
  );
}
