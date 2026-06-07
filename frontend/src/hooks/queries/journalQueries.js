// React Query hooks for the Journal / Receipt / Payment / Contra voucher screen.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createJournalEntry,
  fetchJournalEntryForEdit,
  fetchVoucherNoNext,
  updateJournalEntryForEdit,
} from "@/services/apiService";

// Module-local; promote to `export` when a cross-file consumer needs them.
const ACCOUNTING_VOUCHER_LIST_KEY = ["accountingVouchers"];
const journalKey = (id) => ["journalEntry", String(id)];
const voucherNoNextKey = (vouType) => ["voucherNoNext", vouType || ""];

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
 * Next voucher number for a journal type (JRNL / RCPT / PMNT / CONTRA).
 * Disabled in edit mode — the existing number comes from the record.
 * `staleTime: 0` so two concurrent tabs don't both grab the same number.
 */
export function useVoucherNoNext(vouType, { enabled = true } = {}) {
  return useQuery({
    queryKey: voucherNoNextKey(vouType),
    queryFn: async () => unwrap(await fetchVoucherNoNext(vouType), "Failed to load next voucher number"),
    enabled: enabled && !!vouType,
    staleTime: 0,
    refetchOnMount: "always",
  });
}

/**
 * Race-safe load of an existing journal entry for edit. Disabled when
 * there's no id. Eliminates the bare `.then()` callback at line 109 of
 * the legacy code (memory note: known race condition source).
 */
export function useJournalEntryForEdit(id) {
  return useQuery({
    queryKey: id ? journalKey(id) : ["journalEntry", "none"],
    queryFn: async () => unwrap(await fetchJournalEntryForEdit(id), "Failed to load voucher"),
    enabled: !!id,
    staleTime: 60 * 1000,
  });
}

/**
 * Create or update a journal entry. Invalidates the accounting voucher list
 * cache (used by AccountingVoucherList) on success.
 */
export function useSaveJournalEntryMutation(id) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (form) => {
      const result = id
        ? await updateJournalEntryForEdit(form, id)
        : await createJournalEntry(form);
      return unwrap(result, "Failed to save voucher");
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ACCOUNTING_VOUCHER_LIST_KEY });
      const savedId = id || data?.id;
      if (savedId) queryClient.setQueryData(journalKey(savedId), data);
    },
  });
}
