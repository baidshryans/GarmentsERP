// Overview: value, buying rhythm, money owed, occasions, and profile capture.
import React, { useState } from "react";
import { CalendarHeart, Save } from "lucide-react";

import { ConfidenceNote, EmptyNote, LapseBadge, Money } from "../badges";

function Stat({ label, children, hint }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-800">{children}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

/**
 * Inline capture for the fields the CRM cannot work without.
 * No customer in this database has a date of birth yet, which is why the
 * occasion engine has nothing to fire on — this is where that gets fixed.
 */
function CaptureCard({ profile, onCapture }) {
  const { ledger, consent } = profile;
  const [dob, setDob] = useState(ledger.dob || "");
  const [anniversary, setAnniversary] = useState(ledger.anniversary || "");
  const [gender, setGender] = useState(consent?.gender || "");
  const [instagram, setInstagram] = useState(consent?.instagram || "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const missing = [
    !ledger.mobile1 && "mobile",
    !ledger.dob && "date of birth",
    !ledger.anniversary && "anniversary",
  ].filter(Boolean);

  const save = async () => {
    setSaving(true);
    setMessage("");
    const result = await onCapture({
      dob: dob || null,
      anniversary: anniversary || null,
      gender,
      instagram,
    });
    setSaving(false);
    setMessage(result.success ? "Saved." : "Could not save — please retry.");
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2">
        <CalendarHeart className="h-4 w-4 text-indigo-500" />
        <h3 className="font-medium text-slate-800">Profile details</h3>
      </div>

      {missing.length > 0 && (
        <p className="mt-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-xs text-amber-800">
          Missing {missing.join(", ")} — without these we cannot greet them or
          time an offer.
        </p>
      )}

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <label className="text-xs text-slate-600">
          Date of birth
          <input
            type="date"
            value={dob || ""}
            onChange={(e) => setDob(e.target.value)}
            className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-xs text-slate-600">
          Anniversary
          <input
            type="date"
            value={anniversary || ""}
            onChange={(e) => setAnniversary(e.target.value)}
            className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
          />
        </label>
        <label className="text-xs text-slate-600">
          Gender
          <select
            value={gender}
            onChange={(e) => setGender(e.target.value)}
            className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
          >
            <option value="">Not recorded</option>
            <option value="F">Female</option>
            <option value="M">Male</option>
            <option value="O">Other</option>
          </select>
        </label>
        <label className="text-xs text-slate-600">
          Instagram handle
          <input
            value={instagram}
            onChange={(e) => setInstagram(e.target.value)}
            placeholder="@handle"
            className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 text-sm"
          />
        </label>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={saving}
          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          <Save className="h-4 w-4" /> {saving ? "Saving…" : "Save"}
        </button>
        {message && <span className="text-xs text-slate-500">{message}</span>}
      </div>
    </div>
  );
}

export default function OverviewPanel({ profile, onCapture }) {
  const { snapshot, outstanding, occasions } = profile;
  const cadence = snapshot?.cadence;

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Lifetime value" hint={`${snapshot?.purchase_count_all || 0} purchases`}>
          <Money value={snapshot?.lifetime_value} />
        </Stat>
        <Stat label="Average bill">
          <Money value={snapshot?.avg_ticket} />
        </Stat>
        <Stat
          label="Typical range"
          hint="middle half of their bills"
        >
          <span className="text-base">
            <Money value={snapshot?.p25_ticket} /> – <Money value={snapshot?.p75_ticket} />
          </span>
        </Stat>
        <Stat
          label={outstanding?.direction === "advance" ? "Advance held" : "Outstanding"}
          hint={outstanding?.label}
        >
          <Money value={outstanding?.amount} />
        </Stat>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* ── buying rhythm ────────────────────────────────────────────── */}
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-800">Buying rhythm</h3>
          {cadence?.meaningful ? (
            <div className="mt-2 space-y-2">
              <p className="text-sm text-slate-700">{cadence.explainer}</p>
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <LapseBadge band={cadence.lapse_band} />
                {cadence.next_expected_date && (
                  <span className="text-slate-500">
                    Next purchase expected around <strong>{cadence.next_expected_date}</strong>
                  </span>
                )}
              </div>
            </div>
          ) : (
            <div className="mt-2 space-y-2">
              <EmptyNote>
                Not enough history to predict a buying pattern.
              </EmptyNote>
              <ConfidenceNote
                level={snapshot?.confidence}
                reason={cadence?.reason || snapshot?.confidence_reason}
              />
            </div>
          )}
        </div>

        {/* ── occasions ────────────────────────────────────────────────── */}
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-800">Occasions</h3>
          {occasions?.length ? (
            <ul className="mt-2 space-y-2">
              {occasions.map((o) => (
                <li key={o.occasion} className="flex items-center justify-between text-sm">
                  <span className="capitalize text-slate-700">{o.occasion}</span>
                  <span className="text-slate-500">
                    {o.date} · {o.days_until === 0 ? "today" : `in ${o.days_until} days`}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyNote>
              No birthday or anniversary recorded — add one below so greetings can go out.
            </EmptyNote>
          )}
        </div>
      </div>

      {/* ── engagement ───────────────────────────────────────────────────── */}
      {snapshot?.engagement_components?.length > 0 && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-800">
            Engagement · {snapshot.engagement_score}/100
          </h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {snapshot.engagement_components.map((c) => (
              <span
                key={c.key}
                className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs text-indigo-700"
              >
                {c.label} +{c.points}
              </span>
            ))}
          </div>
        </div>
      )}

      <CaptureCard profile={profile} onCapture={onCapture} />
    </div>
  );
}
