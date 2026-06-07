// React Query hooks for the Quotation Add/Edit screen.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createQuotation,
  fetchQuotationById,
  fetchQuotationInitialData,
  updateQuotation,
} from "@/services/apiService";

// Module-local; promote to `export` when a cross-file consumer needs them.
const QUOTATION_LIST_KEY = ["quotations"];
const quotationKey = (id) => ["quotation", String(id)];

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

export function useQuotationInitialData() {
  return useQuery({
    queryKey: ["quotationInitial"],
    queryFn: async () =>
      unwrap(await fetchQuotationInitialData(), "Failed to load Quotation form data"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useQuotationForEdit(id) {
  return useQuery({
    queryKey: id ? quotationKey(id) : ["quotation", "none"],
    queryFn: async () => unwrap(await fetchQuotationById(id), "Failed to load Quotation"),
    enabled: !!id,
    staleTime: 60 * 1000,
  });
}

export function useSaveQuotationMutation(id) {
  const queryClient = useQueryClient();
  return useMutation({
    // Note: updateQuotation has signature (id, payload), createQuotation has (payload).
    mutationFn: async (payload) => {
      const result = id
        ? await updateQuotation(id, payload)
        : await createQuotation(payload);
      return unwrap(result, "Failed to save Quotation");
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: QUOTATION_LIST_KEY });
      const savedId = id || data?.id;
      if (savedId) queryClient.setQueryData(quotationKey(savedId), data);
    },
  });
}
