// React Query hooks for the Credit / Debit Note screen.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createCreditDebitNote,
  fetchNextCNDNNumber,
  fetchOutstandingBills,
} from "@/services/apiService";

// Module-local; promote to `export` when a cross-file consumer needs them.
const CREDIT_DEBIT_NOTE_LIST_KEY = ["creditDebitNotes"];

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

/**
 * Next CN/DN number — keyed by noteType so switching between Credit Note and
 * Debit Note refetches automatically and races are impossible.
 * `staleTime: 0` so two concurrent tabs don't grab the same number.
 */
export function useNextCNDNNumber(noteType) {
  return useQuery({
    queryKey: ["cndnNextNo", noteType],
    queryFn: async () => unwrap(await fetchNextCNDNNumber(noteType), "Failed to load next note number"),
    enabled: !!noteType,
    staleTime: 0,
    refetchOnMount: "always",
  });
}

/**
 * Outstanding bills for a party — keyed by (ldgrId, kind). Disabled when no
 * party is selected. Race-safe: changing party rapidly cannot land stale
 * outstanding bills over the latest selection.
 */
export function useOutstandingBills(ldgrId, kind) {
  return useQuery({
    queryKey: ["outstandingBills", ldgrId ?? null, kind],
    queryFn: async () => {
      const res = await fetchOutstandingBills(ldgrId, kind);
      return res.success ? (res.data || []) : [];
    },
    enabled: !!ldgrId,
    staleTime: 30 * 1000,
  });
}

export function useCreateCreditDebitNoteMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload) =>
      unwrap(await createCreditDebitNote(payload), "Failed to save note"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CREDIT_DEBIT_NOTE_LIST_KEY });
    },
  });
}
