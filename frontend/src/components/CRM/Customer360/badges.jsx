// Shared display atoms for Customer 360.
//
// The confidence indicators here are not decoration. Most customers in this
// database have bought exactly once, which makes frequency, cadence and lapse
// risk undefined for them. These components are what stop the UI from
// presenting a computed-looking number that has nothing behind it.

import React from "react";

const SEGMENT_STYLES = {
  champion:            { label: "Champion",           cls: "bg-emerald-100 text-emerald-800 border-emerald-200" },
  loyal:               { label: "Loyal",              cls: "bg-teal-100 text-teal-800 border-teal-200" },
  cant_lose:           { label: "Can't Lose",         cls: "bg-red-100 text-red-800 border-red-200" },
  at_risk:             { label: "At Risk",            cls: "bg-orange-100 text-orange-800 border-orange-200" },
  hibernating:         { label: "Hibernating",        cls: "bg-slate-100 text-slate-700 border-slate-200" },
  lost:                { label: "Lost",               cls: "bg-slate-200 text-slate-600 border-slate-300" },
  new:                 { label: "New",                cls: "bg-blue-100 text-blue-800 border-blue-200" },
  promising:           { label: "Promising",          cls: "bg-sky-100 text-sky-800 border-sky-200" },
  potential_loyalist:  { label: "Potential Loyalist", cls: "bg-indigo-100 text-indigo-800 border-indigo-200" },
  needs_attention:     { label: "Needs Attention",    cls: "bg-amber-100 text-amber-800 border-amber-200" },
  about_to_sleep:      { label: "About to Sleep",     cls: "bg-yellow-100 text-yellow-800 border-yellow-200" },
};

const LAPSE_STYLES = {
  healthy: { label: "Healthy", cls: "bg-emerald-100 text-emerald-800" },
  due:     { label: "Due",     cls: "bg-blue-100 text-blue-800" },
  at_risk: { label: "At Risk", cls: "bg-orange-100 text-orange-800" },
  lapsed:  { label: "Lapsed",  cls: "bg-red-100 text-red-800" },
  never:   { label: "Never bought", cls: "bg-slate-100 text-slate-600" },
};

const CONFIDENCE_STYLES = {
  high:   { label: "High confidence",   dot: "bg-emerald-500" },
  medium: { label: "Medium confidence", dot: "bg-amber-500" },
  low:    { label: "Low confidence",    dot: "bg-orange-400" },
  none:   { label: "No history",        dot: "bg-slate-300" },
};

export function SegmentChip({ segment }) {
  if (!segment) return null;
  const style = SEGMENT_STYLES[segment] || {
    label: segment.replace(/_/g, " "),
    cls: "bg-slate-100 text-slate-700 border-slate-200",
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${style.cls}`}>
      {style.label}
    </span>
  );
}

export function LapseBadge({ band }) {
  if (!band) return null;
  const style = LAPSE_STYLES[band] || { label: band, cls: "bg-slate-100 text-slate-700" };
  return (
    <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${style.cls}`}>
      {style.label}
    </span>
  );
}

/** The R/F/M cell, e.g. 545. Hovering explains each digit. */
export function RfmBadge({ cell, r, f, m, basis }) {
  if (!cell) return null;
  const title =
    `Recency ${r}/5 · Frequency ${f}/5 · Monetary ${m}/5` +
    (basis === "absolute"
      ? " — scored against fixed value bands"
      : " — scored against this branch's active customers");
  return (
    <span
      title={title}
      className="inline-flex items-center gap-px rounded bg-slate-800 px-1.5 py-0.5 font-mono text-xs text-white"
    >
      {cell}
    </span>
  );
}

/** A dot plus the reason, e.g. "1 purchase — not enough to predict a pattern". */
export function ConfidenceNote({ level, reason, showLabel = true }) {
  const style = CONFIDENCE_STYLES[level] || CONFIDENCE_STYLES.none;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-500" title={reason || style.label}>
      <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
      {showLabel && <span>{reason || style.label}</span>}
    </span>
  );
}

export function Money({ value, className = "" }) {
  const n = Number(value || 0);
  return (
    <span className={className}>
      {n.toLocaleString("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 })}
    </span>
  );
}

/** A labelled horizontal share bar, used for preference vectors. */
export function ShareBar({ label, share, amount, sublabel }) {
  const pct = Math.round((share || 0) * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="truncate font-medium text-slate-700" title={label}>{label}</span>
        <span className="shrink-0 tabular-nums text-slate-500">
          {pct}%{amount != null && <> · <Money value={amount} /></>}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
      </div>
      {sublabel && <div className="text-xs text-slate-400">{sublabel}</div>}
    </div>
  );
}

export function EmptyNote({ children }) {
  return (
    <p className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-center text-sm text-slate-500">
      {children}
    </p>
  );
}
