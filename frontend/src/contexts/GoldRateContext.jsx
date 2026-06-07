import { createContext, useContext, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getGoldRate } from "../services/apiService";
import { GOLD_RATES_KEY } from "./queryKeys";

const GoldRateContext = createContext(null);

const POLL_INTERVAL = 5 * 60 * 1000; // 5 minutes

async function fetchTodayGoldRates() {
  const today = new Date().toISOString().split("T")[0];
  const response = await getGoldRate(today);
  if (!response?.success) {
    throw new Error(
      typeof response?.error === "string"
        ? response.error
        : "Failed to fetch gold rates"
    );
  }
  return response.data;
}

// eslint-disable-next-line react/prop-types
export function GoldRateProvider({ children }) {
  const queryClient = useQueryClient();

  const {
    data: goldRates = [],
    isLoading: loading,
    error,
  } = useQuery({
    queryKey: GOLD_RATES_KEY,
    queryFn: fetchTodayGoldRates,
    refetchInterval: POLL_INTERVAL,
    // Keep the previous data visible while we refetch on the interval so the UI
    // doesn't blink. Today's rate doesn't change often within a 5-min window.
    staleTime: POLL_INTERVAL,
  });

  // Called by the gold rate form after saving new rates.
  const refreshGoldRates = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: GOLD_RATES_KEY });
  }, [queryClient]);

  return (
    <GoldRateContext.Provider
      value={{
        goldRates,
        loading,
        error: error ? error.message : null,
        refreshGoldRates,
      }}
    >
      {children}
    </GoldRateContext.Provider>
  );
}

export function useGoldRates() {
  const ctx = useContext(GoldRateContext);
  if (!ctx) throw new Error("useGoldRates must be used within a GoldRateProvider");
  return ctx;
}
