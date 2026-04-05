import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { getGoldRate } from "../services/apiService";

const GoldRateContext = createContext(null);

const POLL_INTERVAL = 5 * 60 * 1000; // 5 minutes

export function GoldRateProvider({ children }) {
  const [goldRates, setGoldRates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  const fetchRates = useCallback(async () => {
    try {
      const today = new Date().toISOString().split("T")[0];
      const response = await getGoldRate(today);
      if (!response.success) throw new Error("Failed to fetch gold rates");
      setGoldRates(response.data);
      setError(null);
    } catch (err) {
      console.error("Error fetching gold rates:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Called by the gold rate form after saving new rates
  const refreshGoldRates = useCallback(() => {
    fetchRates();
  }, [fetchRates]);

  useEffect(() => {
    fetchRates();
    intervalRef.current = setInterval(fetchRates, POLL_INTERVAL);
    return () => clearInterval(intervalRef.current);
  }, [fetchRates]);

  return (
    <GoldRateContext.Provider value={{ goldRates, loading, error, refreshGoldRates }}>
      {children}
    </GoldRateContext.Provider>
  );
}

export function useGoldRates() {
  const ctx = useContext(GoldRateContext);
  if (!ctx) throw new Error("useGoldRates must be used within a GoldRateProvider");
  return ctx;
}
