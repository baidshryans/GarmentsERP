// React Query hooks for the Purchase Voucher Add/Edit screen.
//
// Pairs with `masters.js` (shared lookup hooks) to fully replace the
// 130-line Promise.all initial-data effect that PurchaseVoucher.jsx
// used to mount.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createPurchaseVoucher,
  fetchPurchaseVoucherForEdit,
  fetchPVNoNext,
  updatePurchaseVoucherForEdit,
} from "@/services/apiService";

// Module-local; promote to `export` when a cross-file consumer needs them.
const PURCHASE_VOUCHER_LIST_KEY = ["purchaseVouchers"];
const purchaseVoucherKey = (id) => ["purchaseVoucher", String(id)];
const nextPVNoKey = (vouType) => ["purchaseVoucherNextNo", vouType || "Vendor"];

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
  // Preserve the HTTP status code (legacy error shape includes `result.status`
  // for the PV create/update paths) so callers can branch on it.
  if (result?.status) error.status = result.status;
  throw error;
}

/**
 * Fetch the next billno for a new PV. Disabled in edit mode (id present)
 * since the existing billno comes from the record itself.
 *
 * `staleTime: 0` — the auto-generated next number should reflect server state
 * each time the screen mounts, otherwise two tabs could write the same number.
 */
export function useNextPVNo(vouType, { enabled = true } = {}) {
  return useQuery({
    queryKey: nextPVNoKey(vouType),
    queryFn: async () => unwrap(await fetchPVNoNext(vouType), "Failed to load next PV number"),
    enabled,
    staleTime: 0,
    refetchOnMount: "always",
  });
}

/**
 * Load an existing Purchase Voucher for edit. Disabled when there's no id.
 * Race-safe: switching between PV ids in quick succession won't land stale
 * data over fresh data — React Query keys responses by id.
 */
export function usePurchaseVoucherForEdit(id) {
  return useQuery({
    queryKey: id ? purchaseVoucherKey(id) : ["purchaseVoucher", "none"],
    queryFn: async () => unwrap(await fetchPurchaseVoucherForEdit(id), "Failed to load Purchase Voucher"),
    enabled: !!id,
    staleTime: 60 * 1000,
  });
}

/**
 * Create or update a Purchase Voucher. On success invalidates the list cache
 * and seeds the per-record cache so the next Edit is instant.
 */
export function useSavePurchaseVoucherMutation(id) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data) => {
      const result = id
        ? await updatePurchaseVoucherForEdit(data, id)
        : await createPurchaseVoucher(data);
      return unwrap(result, "Failed to save Purchase Voucher");
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: PURCHASE_VOUCHER_LIST_KEY });
      const savedId = id || data?.id;
      if (savedId) {
        queryClient.setQueryData(purchaseVoucherKey(savedId), data);
      }
    },
  });
}
