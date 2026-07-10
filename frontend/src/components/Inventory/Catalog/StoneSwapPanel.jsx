import { useState, useEffect, useRef } from "react";
import { formatMoney } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { FlaskConical, RotateCcw, Loader2 } from "lucide-react";
import { fetchSwapCandidates, simulateCatalogPrice } from "@/services/apiService";

const inr = (n) => formatMoney(n, { decimals: 0, space: false });

// What-if stone swap simulator (internal staff only — not rendered on the
// public catalog). Lets the user swap packet-linked stone lines to another
// packet with an overlapping sieve size (e.g. diamond ↔ lab-grown diamond)
// or to a manual rate, and shows the repriced breakdown plus the delta.
export default function StoneSwapPanel({ design, tier = "retail", pricelist = null }) {
  const [open, setOpen] = useState(false);
  const [candidates, setCandidates] = useState({});   // packetId -> [candidate]
  const [overrides, setOverrides] = useState({});     // detailId -> {packet_id, rate}
  const [sim, setSim] = useState(null);
  const [simLoading, setSimLoading] = useState(false);
  const debounceRef = useRef(null);

  const lines = (design.details || []).filter((x) => x.packet);
  const tierRate = (p) =>
    tier === "b2b" ? (p.rate_for_wholesale ?? p.rate_for_retail) : p.rate_for_retail;

  useEffect(() => {
    if (!open) return;
    const ids = [...new Set(lines.map((l) => l.packet.id))].filter((id) => !(id in candidates));
    ids.forEach(async (id) => {
      const res = await fetchSwapCandidates(id);
      setCandidates((c) => ({ ...c, [id]: res.success ? res.data.candidates : [] }));
    });
  }, [open]);

  // Debounced re-simulation whenever overrides change.
  useEffect(() => {
    if (!open) return;
    clearTimeout(debounceRef.current);
    const entries = Object.entries(overrides).filter(([, o]) => o && o.rate !== "");
    if (entries.length === 0) { setSim(null); return; }
    debounceRef.current = setTimeout(async () => {
      setSimLoading(true);
      const res = await simulateCatalogPrice(design.id, {
        tier,
        pricelist,
        overrides: entries.map(([detail_id, o]) => ({
          detail_id: Number(detail_id),
          packet_id: o.packet_id,
          rate: Number(o.rate),
        })),
      });
      setSim(res.success ? res.data : null);
      setSimLoading(false);
    }, 400);
    return () => clearTimeout(debounceRef.current);
  }, [overrides, open, tier, pricelist]);

  if (lines.length === 0) return null;

  const setLine = (detailId, patch) =>
    setOverrides((o) => ({ ...o, [detailId]: { ...o[detailId], ...patch } }));
  const resetLine = (detailId) =>
    setOverrides((o) => { const n = { ...o }; delete n[detailId]; return n; });

  const pickCandidate = (line, value) => {
    if (value === "") { resetLine(line.detail_id); return; }
    if (value === "manual") {
      setLine(line.detail_id, { packet_id: null, rate: line.rate ?? "" });
      return;
    }
    const cand = (candidates[line.packet.id] || []).find((c) => c.id === Number(value));
    if (cand) setLine(line.detail_id, { packet_id: cand.id, rate: tierRate(cand) ?? "" });
  };

  const grouped = (list) => {
    const g = {};
    for (const c of list) {
      const k = c.stone_item?.name || "Other";
      (g[k] = g[k] || []).push(c);
    }
    return g;
  };

  const delta = sim ? sim.delta : null;

  return (
    <div className="rounded-lg border bg-card p-4">
      <button type="button" className="w-full flex items-center justify-between"
        onClick={() => setOpen((v) => !v)}>
        <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
          <FlaskConical className="size-3.5" /> WHAT IF — SWAP STONES
        </span>
        <span className="text-xs text-muted-foreground">{open ? "Hide" : "Show"}</span>
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {lines.map((line) => {
            const ov = overrides[line.detail_id];
            const cands = candidates[line.packet.id];
            return (
              <div key={line.detail_id} className="rounded border bg-muted/20 p-3 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <div>
                    <span className="font-medium">{line.sub_item}</span>{" "}
                    <span className="text-muted-foreground text-xs">
                      {line.packet.pckt_no} · sieve {line.packet.sieve_min ?? "—"}–{line.packet.sieve_max ?? "—"}
                      {line.ct ? ` · ${line.ct} ct` : ""} {line.pcs ? `· ${line.pcs} pcs` : ""}
                    </span>
                  </div>
                  {ov && (
                    <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs"
                      onClick={() => resetLine(line.detail_id)}>
                      <RotateCcw className="size-3" /> Reset
                    </Button>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <select
                    className="h-9 rounded-md border bg-background px-2 text-sm min-w-52"
                    value={ov ? (ov.packet_id ?? "manual") : ""}
                    onChange={(e) => pickCandidate(line, e.target.value)}
                  >
                    <option value="">Keep original</option>
                    {cands === undefined && <option disabled>Loading packets…</option>}
                    {Object.entries(grouped(cands || [])).map(([group, list]) => (
                      <optgroup key={group} label={group}>
                        {list.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.pckt_no} · sieve {c.sieve_min ?? "—"}–{c.sieve_max ?? "—"}
                            {c.color ? ` · ${c.color}` : ""}{c.clarity ? ` ${c.clarity}` : ""}
                            {" · "}₹{tierRate(c) ?? "—"}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                    <option value="manual">Other stone / manual rate…</option>
                  </select>
                  {ov && (
                    <label className="flex items-center gap-1.5 text-sm">
                      <span className="text-muted-foreground text-xs">Rate/ct</span>
                      <input
                        type="number" min="0"
                        className="h-9 w-28 rounded-md border bg-background px-2 text-sm"
                        value={ov.rate}
                        onChange={(e) => setLine(line.detail_id, { rate: e.target.value })}
                      />
                    </label>
                  )}
                </div>
              </div>
            );
          })}

          {(sim || simLoading) && (
            <div className="rounded border bg-muted/20 p-3">
              <div className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-2">
                SIMULATED PRICE {simLoading && <Loader2 className="size-3 animate-spin" />}
              </div>
              {sim && (
                <div className="space-y-1 text-sm">
                  {(sim.simulated.component_lines || []).map((c, i) => (
                    <div key={i} className={`flex justify-between ${c.overridden ? "font-medium" : ""}`}>
                      <span className={c.overridden ? "" : "text-muted-foreground"}>
                        {c.name}{c.ct ? ` (${c.ct} ct)` : ""}{c.overridden ? " *" : ""}
                      </span>
                      <span>{inr(c.amount)}</span>
                    </div>
                  ))}
                  <div className="border-t my-2" />
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">GST ({sim.simulated.gst_pct}%)</span>
                    <span>{inr(sim.simulated.gst)}</span>
                  </div>
                  <div className="flex justify-between text-base font-bold">
                    <span>New total</span><span>{inr(sim.simulated.total_price)}</span>
                  </div>
                  <div className={`flex justify-between text-sm font-semibold ${delta > 0 ? "text-red-600" : "text-emerald-600"}`}>
                    <span>vs original ({inr(sim.original.total_price)})</span>
                    <span>{delta > 0 ? "+" : "−"}{inr(Math.abs(delta))}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
