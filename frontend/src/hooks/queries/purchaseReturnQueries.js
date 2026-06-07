// Shared React Query hooks for the Purchase Return forms.
//
// These wrap the existing `services/api/purchase.js` functions so the legacy
// `{success, data}` / `{success, error}` shape is unwrapped into something
// React Query can use directly — failures throw, successes return data.
//
// Co-locating the queryFns + keys here means any Purchase Return screen can
// invalidate the list/edit/initial caches with the same key references and
// caching behaviour stays consistent.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createPurchaseReturn,
  fetchPurchaseReturnForEdit,
  fetchPurchaseReturnInitialData,
  updatePurchaseReturnForEdit,
} from "@/services/apiService";

// Query keys — hierarchical so `invalidateQueries(['purchaseReturns'])`
// invalidates list pages AND individual record caches together. Module-local
// for now; promote to `export` when a cross-file consumer actually needs them.
const PURCHASE_RETURN_LIST_KEY = ["purchaseReturns"];
const PURCHASE_RETURN_INITIAL_KEY = ["purchaseReturnInitial"];
const purchaseReturnKey = (id) => ["purchaseReturn", String(id)];

function unwrap(result, fallbackMsg) {
  if (result?.success) return result.data;
  const err = result?.error;
  if (err instanceof Error) throw err;
  // Preserve the structured payload as `cause` so callers (e.g.
  // renderErrorTree) can still walk the original field-by-field error tree.
  const message =
    typeof err === "string"
      ? err
      : err?.detail || err?.error || fallbackMsg || "Request failed";
  const error = new Error(message);
  error.cause = err;
  throw error;
}

/**
 * Bundled masters needed by the Purchase Return form: ledgers (vendors),
 * items, purity, packets, retail_state, and a fresh next billno.
 * Cached briefly so navigating Add → List → Add doesn't refetch every time.
 */
export function usePurchaseReturnInitialData() {
  return useQuery({
    queryKey: PURCHASE_RETURN_INITIAL_KEY,
    queryFn: async () =>
      unwrap(
        await fetchPurchaseReturnInitialData(),
        "Failed to load Purchase Return form data"
      ),
    // Masters change rarely within a session — 5 minutes keeps the form snappy.
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Load an existing Purchase Return for the edit form. Disabled when there's
 * no id (i.e. the Add screen) so we don't kick off a useless request.
 */
export function usePurchaseReturnForEdit(id) {
  return useQuery({
    queryKey: id ? purchaseReturnKey(id) : ["purchaseReturn", "none"],
    queryFn: async () =>
      unwrap(
        await fetchPurchaseReturnForEdit(id),
        "Failed to load Purchase Return"
      ),
    enabled: !!id,
    // Edit-mode data shouldn't be reused across vouchers, but caching here
    // means Edit → List → same Edit reopens instantly.
    staleTime: 60 * 1000,
  });
}

/**
 * Save (create or update) a Purchase Return. On success, invalidates the
 * list cache so the table reflects the change without a manual reload, and
 * updates the per-record cache so a subsequent Edit shows fresh data.
 */
export function useSavePurchaseReturnMutation(id) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data) => {
      const result = id
        ? await updatePurchaseReturnForEdit(data, id)
        : await createPurchaseReturn(data);
      return unwrap(result, "Save failed");
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: PURCHASE_RETURN_LIST_KEY });
      const savedId = id || data?.id;
      if (savedId) {
        queryClient.setQueryData(purchaseReturnKey(savedId), data);
      }
    },
  });
}
