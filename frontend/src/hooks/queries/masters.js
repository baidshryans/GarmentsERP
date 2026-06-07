// Shared React Query hooks for master data used across voucher forms.
//
// Each hook wraps an existing `services/api/*` function and unwraps the
// legacy `{success,data}` / `{success,error}` shape into the typed
// `data` / `error` React Query expects.
//
// Why a shared cache matters here:
//  - Opening Purchase → Sales → Purchase Return today fetches the ledger
//    list THREE times. With these hooks, the second and third screens get
//    the cached list instantly.
//  - 5-min `staleTime` matches how rarely these masters actually change.

import { useQuery } from "@tanstack/react-query";
import {
  fetchHSNs,
  fetchMainItem,
  fetchPackets,
  fetchPos,
  fetchPurity,
  fetchSalesperson,
  getLedgers,
} from "@/services/apiService";

const MASTERS_STALE = 5 * 60 * 1000; // 5 minutes

// Most master endpoints return either `data.results` (DRF paginated)
// or `data` (plain array). Normalise here so call sites don't repeat the dance.
function asArray(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.results)) return data.results;
  return [];
}

function unwrap(result, fallbackMsg) {
  if (result?.success) return result.data;
  const err = result?.error;
  if (err instanceof Error) throw err;
  const message =
    typeof err === "string"
      ? err
      : err?.detail || err?.error || fallbackMsg || "Request failed";
  const error = new Error(message);
  error.cause = err;
  throw error;
}

// ── Ledgers (vendors / customers / karigars) ────────────────────────────────
// Keyed by the role-filter and page size so different screens can share
// the same query when they ask for the same filter.
export function useLedgers({ type, page_size = 10000, enabled = true } = {}) {
  return useQuery({
    queryKey: ["ledgers", { type, page_size }],
    queryFn: async () => {
      const res = await getLedgers({ type, page_size });
      return asArray(unwrap(res, "Failed to load ledgers"));
    },
    enabled,
    staleTime: MASTERS_STALE,
  });
}

// ── Salespeople ─────────────────────────────────────────────────────────────
export function useSalespeople() {
  return useQuery({
    queryKey: ["salespeople"],
    queryFn: async () => asArray(unwrap(await fetchSalesperson(), "Failed to load salespeople")),
    staleTime: MASTERS_STALE,
  });
}

// ── Items (main item master) ────────────────────────────────────────────────
// `filter` is passed straight to fetchMainItem; cache key includes it so
// type=M and the unfiltered call cache separately.
export function useItems(filter) {
  return useQuery({
    queryKey: ["items", filter ?? null],
    queryFn: async () => asArray(unwrap(await fetchMainItem(filter), "Failed to load items")),
    staleTime: MASTERS_STALE,
  });
}

// ── Purity master ───────────────────────────────────────────────────────────
export function usePurities() {
  return useQuery({
    queryKey: ["purities"],
    queryFn: async () => asArray(unwrap(await fetchPurity(), "Failed to load purities")),
    staleTime: MASTERS_STALE,
  });
}

// ── Packets ─────────────────────────────────────────────────────────────────
export function usePackets() {
  return useQuery({
    queryKey: ["packets"],
    queryFn: async () => asArray(unwrap(await fetchPackets(), "Failed to load packets")),
    staleTime: MASTERS_STALE,
  });
}

// ── HSN master ──────────────────────────────────────────────────────────────
export function useHsnList() {
  return useQuery({
    queryKey: ["hsns"],
    queryFn: async () => asArray(unwrap(await fetchHSNs(), "Failed to load HSN list")),
    staleTime: MASTERS_STALE,
  });
}

// ── PO list ─────────────────────────────────────────────────────────────────
// `fetchPos(slip_type)` returns `{po_no}` not a list — leave the raw payload.
export function usePos(slipType) {
  return useQuery({
    queryKey: ["pos", slipType ?? null],
    queryFn: async () => unwrap(await fetchPos(slipType), "Failed to load POs"),
    staleTime: MASTERS_STALE,
  });
}
