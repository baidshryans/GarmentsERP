import { useCallback, useEffect, useState } from "react";
import { fetchUnbarcodedForPicker } from "../services/apiService";

/**
 * Fetches UnBarcodedMain pieces eligible for Sample Issue pickers:
 *   stk_status=True AND (kr_code IS NULL OR kr_code = karigarId)
 *
 * Pieces currently with *another* karigar are hidden.
 */
export default function useUnbarcodedList({ karigarId } = {}) {
  const [options, setOptions] = useState([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    const res = await fetchUnbarcodedForPicker({ karigar: karigarId });
    setLoading(false);
    if (res.success) setOptions(res.data || []);
    else setOptions([]);
  }, [karigarId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { options, loading, refresh };
}
