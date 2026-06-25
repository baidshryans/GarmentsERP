import { createContext, useContext, useMemo } from 'react';
import { INR_CONFIG, setFormatConfig, formatMoney, formatNumber, formatDate, formatWords } from '@/lib/format';

const CurrencyContext = createContext(null);

export function CurrencyProvider({ children, config = INR_CONFIG }) {
  // Phase 1: push the (hardcoded INR) config into the format module.
  // Phase 2: `config` will be sourced from the active retail.
  setFormatConfig(config);
  const value = useMemo(() => ({
    config, formatMoney, formatNumber, formatDate, formatWords,
  }), [config]);
  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useFormat() {
  const ctx = useContext(CurrencyContext);
  if (!ctx) throw new Error('useFormat must be used within CurrencyProvider');
  return ctx;
}
