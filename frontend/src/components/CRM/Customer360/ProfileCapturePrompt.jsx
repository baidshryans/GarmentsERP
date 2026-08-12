// A nudge at the billing counter to capture the details the CRM cannot work
// without.
//
// This is where profile completeness actually comes from: the customer is
// standing in front of you. Asking staff to go and fill these in later does not
// happen — hence a prompt at the exact moment of contact.
//
// Deliberately non-blocking. Billing is the priority; this must never get in
// the way of finishing a sale.
import React, { useEffect, useState } from "react";
import { CalendarHeart, Check, X } from "lucide-react";

import {
  fetchCustomerSocial,
  updateCustomerSocial,
} from "@/services/api/customerIntel";

export default function ProfileCapturePrompt({ ledgerId, ledgerName }) {
  const [missing, setMissing] = useState([]);
  const [dob, setDob] = useState("");
  const [anniversary, setAnniversary] = useState("");
  const [open, setOpen] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDismissed(false);
    setSaved(false);
    setOpen(false);
    setMissing([]);
    if (!ledgerId) return;

    let active = true;
    fetchCustomerSocial(ledgerId).then((result) => {
      if (!active || !result.success) return;
      const gaps = [];
      if (!result.data.dob) gaps.push("date of birth");
      if (!result.data.anniversary) gaps.push("anniversary");
      setDob(result.data.dob || "");
      setAnniversary(result.data.anniversary || "");
      setMissing(gaps);
    });
    return () => { active = false; };
  }, [ledgerId]);

  if (!ledgerId || dismissed || missing.length === 0) return null;

  const save = async () => {
    setSaving(true);
    const result = await updateCustomerSocial(ledgerId, {
      dob: dob || null,
      anniversary: anniversary || null,
      consent_source: "billing_counter",
    });
    setSaving(false);
    if (result.success) {
      setSaved(true);
      setTimeout(() => setDismissed(true), 1200);
    }
  };

  if (saved) {
    return (
      <div className="mb-3 flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
        <Check className="h-4 w-4" /> Saved — we can wish them from now on.
      </div>
    );
  }

  return (
    <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2 text-sm text-amber-900">
        <CalendarHeart className="h-4 w-4 shrink-0" />
        <span>
          We don't have {ledgerName ? <strong>{ledgerName}</strong> : "this customer"}
          's {missing.join(" or ")}. Ask while they're here?
        </span>
        {!open && (
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="rounded bg-amber-600 px-2 py-1 text-xs text-white hover:bg-amber-700"
          >
            Add now
          </button>
        )}
        <button
          type="button"
          onClick={() => setDismissed(true)}
          className="ml-auto rounded p-1 text-amber-700 hover:bg-amber-100"
          title="Not now"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {open && (
        <div className="mt-2 flex flex-wrap items-end gap-3">
          {missing.includes("date of birth") && (
            <label className="text-xs text-amber-900">
              Date of birth
              <input
                type="date"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                className="mt-1 block rounded border border-amber-300 bg-white px-2 py-1 text-sm"
              />
            </label>
          )}
          {missing.includes("anniversary") && (
            <label className="text-xs text-amber-900">
              Anniversary
              <input
                type="date"
                value={anniversary}
                onChange={(e) => setAnniversary(e.target.value)}
                className="mt-1 block rounded border border-amber-300 bg-white px-2 py-1 text-sm"
              />
            </label>
          )}
          <button
            type="button"
            onClick={save}
            disabled={saving || (!dob && !anniversary)}
            className="rounded bg-amber-600 px-3 py-1.5 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      )}
    </div>
  );
}
