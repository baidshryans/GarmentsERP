// Line-by-line purchase detail — what the header-level history page cannot show.
import React from "react";

import { EmptyNote, Money } from "../badges";

export default function PurchasesPanel({ profile }) {
  const lines = profile.line_items || [];

  if (!lines.length) {
    return <EmptyNote>No sold line items on record for this customer.</EmptyNote>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-3 py-2">Date</th>
            <th className="px-3 py-2">Bill</th>
            <th className="px-3 py-2">Item</th>
            <th className="px-3 py-2">Design</th>
            <th className="px-3 py-2">Purity</th>
            <th className="px-3 py-2 text-right">Pcs</th>
            <th className="px-3 py-2 text-right">Gross wt</th>
            <th className="px-3 py-2 text-right">Amount</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {lines.map((line) => (
            <tr key={line.id} className="hover:bg-slate-50">
              <td className="whitespace-nowrap px-3 py-2 text-slate-600">{line.date || "—"}</td>
              <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-slate-500">
                {line.bill_no}
              </td>
              <td className="px-3 py-2 text-slate-800">
                {line.item || "—"}
                {line.category && (
                  <span className="block text-xs text-slate-400">{line.category}</span>
                )}
              </td>
              <td className="px-3 py-2 text-slate-600">{line.design_no || "—"}</td>
              <td className="px-3 py-2 text-slate-600">
                {line.purity || "—"}
                {line.metal_color && (
                  <span className="block text-xs text-slate-400">{line.metal_color}</span>
                )}
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-600">{line.pcs ?? "—"}</td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                {line.gw != null ? `${line.gw}g` : "—"}
              </td>
              <td className="px-3 py-2 text-right font-medium tabular-nums">
                <Money value={line.amount} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-slate-100 px-3 py-2 text-xs text-slate-400">
        Showing the most recent {lines.length} line{lines.length === 1 ? "" : "s"}.
      </p>
    </div>
  );
}
