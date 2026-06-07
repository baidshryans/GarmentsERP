// React Query hooks for the Sales Return Add/Edit screen.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createSalesReturn,
  fetchSaleReturnInitialData,
  fetchSalesReturnById,
  updateSalesReturn,
} from "@/services/apiService";

// Module-local; promote to `export` when a cross-file consumer needs them.
const SALES_RETURN_LIST_KEY = ["salesReturns"];
const salesReturnKey = (id) => ["salesReturn", String(id)];

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

export function useSaleReturnInitialData() {
  return useQuery({
    queryKey: ["saleReturnInitial"],
    queryFn: async () =>
      unwrap(await fetchSaleReturnInitialData(), "Failed to load Sales Return form data"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useSalesReturnForEdit(id) {
  return useQuery({
    queryKey: id ? salesReturnKey(id) : ["salesReturn", "none"],
    queryFn: async () => unwrap(await fetchSalesReturnById(id), "Failed to load Sales Return"),
    enabled: !!id,
    staleTime: 60 * 1000,
  });
}

export function useSaveSalesReturnMutation(id) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data) => {
      const result = id
        ? await updateSalesReturn(data, id)
        : await createSalesReturn(data);
      return unwrap(result, "Failed to save Sales Return");
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: SALES_RETURN_LIST_KEY });
      const savedId = id || data?.id;
      if (savedId) queryClient.setQueryData(salesReturnKey(savedId), data);
    },
  });
}
