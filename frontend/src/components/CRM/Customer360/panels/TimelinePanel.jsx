// Every interaction we have had with this customer, newest first.
import React, { useState } from "react";
import { Send } from "lucide-react";

import { EmptyNote } from "../badges";

const CHANNEL_STYLES = {
  whatsapp: "bg-emerald-100 text-emerald-700",
  email:    "bg-blue-100 text-blue-700",
  sms:      "bg-sky-100 text-sky-700",
  call:     "bg-violet-100 text-violet-700",
  walk_in:  "bg-amber-100 text-amber-700",
  catalog:  "bg-indigo-100 text-indigo-700",
  portal:   "bg-teal-100 text-teal-700",
  note:     "bg-slate-100 text-slate-700",
};

function formatWhen(value) {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString("en-IN");
}

export default function TimelinePanel({ events, onNote }) {
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!body.trim()) return;
    setSaving(true);
    setError("");
    const result = await onNote(body.trim());
    setSaving(false);
    if (result.success) setBody("");
    else setError("Could not save the note.");
  };

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="font-medium text-slate-800">Log an interaction</h3>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={2}
          placeholder="Called about the bangle set — wants to see new stock after Diwali."
          className="mt-2 w-full rounded border border-slate-200 px-3 py-2 text-sm focus:border-indigo-400 focus:outline-none"
        />
        <div className="mt-2 flex items-center gap-3">
          <button
            type="button"
            onClick={submit}
            disabled={saving || !body.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-3 py-1.5 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            <Send className="h-4 w-4" /> {saving ? "Saving…" : "Add note"}
          </button>
          {error && <span className="text-xs text-red-600">{error}</span>}
        </div>
      </div>

      {events?.length ? (
        <ol className="space-y-3">
          {events.map((event) => (
            <li key={event.id} className="rounded-lg border border-slate-200 bg-white p-3">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span
                  className={`rounded px-2 py-0.5 font-medium ${
                    CHANNEL_STYLES[event.channel] || "bg-slate-100 text-slate-700"
                  }`}
                >
                  {event.channel.replace(/_/g, " ")}
                </span>
                <span className="text-slate-400">
                  {event.direction === "in" ? "received" : event.direction === "sys" ? "system" : "sent"}
                </span>
                <span className="ml-auto text-slate-400">{formatWhen(event.occurred_at)}</span>
              </div>
              {event.subject && (
                <div className="mt-1.5 text-sm font-medium text-slate-800">{event.subject}</div>
              )}
              {event.body && (
                <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{event.body}</p>
              )}
              {event.status === "failed" && event.error_message && (
                <p className="mt-1 text-xs text-red-600">Failed: {event.error_message}</p>
              )}
              {event.created_by_name && (
                <p className="mt-1 text-xs text-slate-400">by {event.created_by_name}</p>
              )}
            </li>
          ))}
        </ol>
      ) : (
        <EmptyNote>
          Nothing logged yet. Notes, greetings, campaign sends and catalog opens all
          appear here once they happen.
        </EmptyNote>
      )}
    </div>
  );
}
