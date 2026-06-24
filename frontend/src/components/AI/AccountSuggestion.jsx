import { useState, useCallback, useEffect } from "react";
import { Lightbulb, CheckCircle, X, Loader2 } from "lucide-react";
import { suggestAccounts } from "@/services/apiService";

/**
 * AccountSuggestion — shown below the narration field in journal entry forms.
 *
 * Props:
 *   narration (string): current narration value from the form
 *   voucherType (string): e.g. "PMNT", "RCPT", "JRNL"
 *   amount (number): optional transaction amount
 *   onApply({ debitAccount, creditAccount }): called when user clicks "Apply"
 *
 * Usage: attach onBlur of the narration field to trigger fetchSuggestion().
 * The parent can also call fetchSuggestion() directly via a ref if needed.
 */
export default function AccountSuggestion({ narration, voucherType = "JRNL", amount = 0, onApply }) {
  const [status, setStatus] = useState("idle"); // idle | loading | ready | dismissed | error
  const [suggestion, setSuggestion] = useState(null);
  const [error, setError] = useState("");

  // Auto-fetch when narration prop changes (triggered by parent on blur)
  useEffect(() => {
    if (narration && narration.trim().length >= 5) {
      fetchSuggestion();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [narration]);

  const fetchSuggestion = useCallback(async () => {
    const text = (narration || "").trim();
    if (!text || text.length < 5) return;

    setStatus("loading");
    setSuggestion(null);

    const result = await suggestAccounts(text, voucherType, amount);

    if (result.success && result.data?.debit_account && result.data?.credit_account) {
      setSuggestion(result.data);
      setStatus("ready");
    } else if (result.success && result.data?.error) {
      setError(result.data.error);
      setStatus("error");
    } else if (!result.success) {
      setError(result.error || "Suggestion failed");
      setStatus("error");
    } else {
      setStatus("idle");
    }
  }, [narration, voucherType, amount]);

  const handleApply = () => {
    if (suggestion && onApply) {
      onApply({
        debitAccount: suggestion.debit_account,
        creditAccount: suggestion.credit_account,
      });
    }
    setStatus("dismissed");
  };

  const handleDismiss = () => setStatus("dismissed");

  if (status === "idle" || status === "dismissed") return null;

  return (
    <div className="mt-1.5 rounded-lg border border-accent-200 bg-accent-50 px-3 py-2 text-sm">
      {status === "loading" && (
        <div className="flex items-center gap-2 text-primary">
          <Loader2 size={13} className="animate-spin" />
          <span className="text-xs">Getting account suggestion…</span>
        </div>
      )}

      {status === "ready" && suggestion && (
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <Lightbulb size={14} className="text-primary mt-0.5 shrink-0" />
            <div className="text-xs text-gray-700">
              <span className="font-medium">Suggested: </span>
              <span className="text-primary font-medium">Dr {suggestion.debit_account}</span>
              <span className="text-gray-500"> / </span>
              <span className="text-red-700 font-medium">Cr {suggestion.credit_account}</span>
              {suggestion.confidence != null && (
                <span className="ml-1.5 text-[10px] text-gray-400">
                  ({Math.round(suggestion.confidence * 100)}% confident)
                </span>
              )}
              {suggestion.reasoning && (
                <p className="text-gray-400 text-[10px] mt-0.5">{suggestion.reasoning}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={handleApply}
              className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-primary hover:bg-primary text-white transition-colors"
            >
              <CheckCircle size={11} />
              Apply
            </button>
            <button
              type="button"
              onClick={handleDismiss}
              className="p-0.5 text-gray-400 hover:text-gray-600"
            >
              <X size={12} />
            </button>
          </div>
        </div>
      )}

      {status === "error" && (
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs text-red-600 truncate">{error}</span>
          <button type="button" onClick={handleDismiss} className="text-gray-400 hover:text-gray-600">
            <X size={12} />
          </button>
        </div>
      )}
    </div>
  );
}

// Re-export fetchSuggestion so parent can call it imperatively
// Usage in parent: const suggestionRef = useRef(); onBlur={() => suggestionRef.current?.fetch()}
export function useAccountSuggestion() {
  const [trigger, setTrigger] = useState(0);
  const fetch = useCallback(() => setTrigger((t) => t + 1), []);
  return { trigger, fetch };
}
