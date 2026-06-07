// React Query hooks for the Sales Voucher Add/Edit screen.
//
// The Sales Voucher form is one of the most fetch-heavy screens in the app:
// it loads bundled masters + exhibitions + today's gold rates + system
// settings + bank ledgers + the active offer + the voucher being edited.
// The legacy implementation mixed all of that into one 160-line useEffect
// and used a manual `cancelled` flag as a hand-rolled race guard (memory
// obs S693 / 6084).  React Query's query-keyed responses make that
// race-condition class of bug structurally impossible.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createSalesVoucher,
  fetchActiveOffer,
  fetchExhibitions,
  fetchSaleVoucherInitialData,
  fetchSalesVoucherwithID,
  fetchSystemSettings,
  getGoldRate,
  getLedgers,
  updateSalesVoucher,
} from "@/services/apiService";

// Module-local; promote to `export` when a cross-file consumer needs them.
const SALES_VOUCHER_LIST_KEY = ["salesVouchers"];
const salesVoucherKey = (id) => ["salesVoucher", String(id)];

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
  if (result?.status) error.status = result.status;
  throw error;
}

/**
 * Bundled masters for the Sales Voucher form: states, ledgers (customers),
 * salespersons, hsns, items, purity, packets, plus a fresh next billno and
 * retail_state_code. 5-min cache — most of this rarely changes per session.
 */
export function useSaleVoucherInitialData() {
  return useQuery({
    queryKey: ["saleVoucherInitial"],
    queryFn: async () =>
      unwrap(await fetchSaleVoucherInitialData(), "Failed to load Sales Voucher form data"),
    staleTime: 5 * 60 * 1000,
  });
}

/** Exhibition profiles — short list, cache aggressively. */
export function useExhibitions() {
  return useQuery({
    queryKey: ["exhibitions"],
    queryFn: async () => {
      const res = await fetchExhibitions();
      const data = unwrap(res, "Failed to load exhibitions");
      return Array.isArray(data) ? data : (data?.results ?? []);
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Today's gold rates as a `{ purity_name: selling_rate }` map. The Sales
 * form uses this map directly; transforming inside the queryFn keeps the
 * component lean and the cache shape is small.
 */
export function useTodayGoldRateMap() {
  return useQuery({
    queryKey: ["goldRates", "todayMap"],
    queryFn: async () => {
      const today = new Date().toISOString().split("T")[0];
      const data = unwrap(await getGoldRate(today), "Failed to load gold rates");
      const map = {};
      (Array.isArray(data) ? data : []).forEach((r) => {
        if (r.purity_name) map[r.purity_name] = r.selling_rate || r.rate;
      });
      return map;
    },
    // Today's rates change rarely within a session; the GoldRateContext
    // refetches separately on a 5-min interval.
    staleTime: 5 * 60 * 1000,
  });
}

/** System settings — auto-calc flags, GST-bill toggle, etc. */
export function useSystemSettings() {
  return useQuery({
    queryKey: ["systemSettings"],
    queryFn: async () => unwrap(await fetchSystemSettings(), "Failed to load system settings"),
    staleTime: 10 * 60 * 1000,
  });
}

/** Bank ledgers — used by the bank-payment row dropdown. */
export function useBankLedgers() {
  return useQuery({
    queryKey: ["ledgers", { type: "BA", page: 1 }],
    queryFn: async () => {
      const data = unwrap(await getLedgers({ type: "BA", page: 1 }), "Failed to load bank ledgers");
      return Array.isArray(data) ? data : (data?.results ?? []);
    },
    staleTime: 5 * 60 * 1000,
  });
}

/** Active offer (campaign / discount) — may be `null`. */
export function useActiveOffer() {
  return useQuery({
    queryKey: ["activeOffer"],
    queryFn: async () => {
      const res = await fetchActiveOffer();
      // fetchActiveOffer returns success even when no offer; unwrap handles that.
      return res.success ? res.data : null;
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Load an existing Sales Voucher for edit. Disabled when there's no id.
 * Race-safe: switching ids quickly cannot land stale data over fresh —
 * React Query keys responses by id. This eliminates the hand-rolled
 * `cancelled` flag that the legacy useEffect needed.
 */
export function useSalesVoucherForEdit(id) {
  return useQuery({
    queryKey: id ? salesVoucherKey(id) : ["salesVoucher", "none"],
    queryFn: async () =>
      unwrap(await fetchSalesVoucherwithID(id), "Failed to load Sales Voucher"),
    enabled: !!id,
    staleTime: 60 * 1000,
  });
}

/** Create or update a Sales Voucher. Invalidates the list cache on success. */
export function useSaveSalesVoucherMutation(id) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data) => {
      const result = id
        ? await updateSalesVoucher(data, id)
        : await createSalesVoucher(data);
      return unwrap(result, "Failed to save Sales Voucher");
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: SALES_VOUCHER_LIST_KEY });
      const savedId = id || data?.id;
      if (savedId) {
        queryClient.setQueryData(salesVoucherKey(savedId), data);
      }
    },
  });
}
