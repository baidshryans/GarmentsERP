// What this customer actually buys — the basis for a relevant recommendation.
import React from "react";

import { EmptyNote, ShareBar } from "../badges";

function Section({ title, entries, subtitle }) {
  if (!entries?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="font-medium text-slate-800">{title}</h3>
      {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      <div className="mt-3 space-y-3">
        {entries.map((e, i) => (
          <ShareBar
            key={`${e.label}-${i}`}
            label={e.label}
            share={e.share}
            amount={e.amount}
            sublabel={
              [
                e.count ? `${e.count} line${e.count === 1 ? "" : "s"}` : null,
                e.gw ? `${e.gw}g` : null,
                e.ct ? `${e.ct}ct` : null,
              ].filter(Boolean).join(" · ") || null
            }
          />
        ))}
      </div>
    </div>
  );
}

export default function PreferencesPanel({ snapshot }) {
  const prefs = snapshot?.preferences;
  const stone = prefs?.stone || {};

  const hasAnything =
    prefs?.category?.length ||
    prefs?.purity?.length ||
    prefs?.metal_color?.length ||
    prefs?.design?.length ||
    Object.keys(stone).length;

  if (!hasAnything) {
    return (
      <EmptyNote>
        Nothing to summarise yet — preferences are derived from what this customer
        has bought, and there are no sold line items on record for them.
      </EmptyNote>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Section
        title="Categories"
        subtitle="Share of their spend by product type"
        entries={prefs?.category}
      />
      <Section
        title="Purity"
        subtitle="Which metal purities they choose"
        entries={prefs?.purity}
      />
      <Section title="Metal colour" entries={prefs?.metal_color} />
      <Section
        title="Designs"
        subtitle="Specific designs they have bought"
        entries={prefs?.design}
      />

      {stone.shape?.length > 0 && (
        <Section title="Stone shape" entries={stone.shape} />
      )}
      {stone.clarity?.length > 0 && (
        <Section title="Stone clarity" entries={stone.clarity} />
      )}
      {stone.color?.length > 0 && (
        <Section title="Stone colour" entries={stone.color} />
      )}

      {stone.solitaire && (
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="font-medium text-slate-800">Solitaires</h3>
          <p className="mt-2 text-sm text-slate-600">
            {stone.solitaire.count} solitaire line{stone.solitaire.count === 1 ? "" : "s"}
            {stone.solitaire.ct ? `, ${stone.solitaire.ct}ct total` : ""} — a
            solitaire buyer is worth a personal call when new stock lands.
          </p>
        </div>
      )}
    </div>
  );
}
