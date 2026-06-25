import { useEffect, useState } from 'react';
import { getFiscalYears } from '@/services/apiService';

// Returns { activeFy, min, max } where min/max are 'YYYY-MM-DD' strings
// for <input type="date" min={min} max={max} />. Falls back to undefined
// (no restriction) until loaded or if no active FY exists.
export function useActiveFiscalYear() {
  const [activeFy, setActiveFy] = useState(null);
  useEffect(() => {
    let alive = true;
    getFiscalYears().then((r) => {
      if (alive && r.success) {
        setActiveFy((r.data || []).find((fy) => fy.is_active) || null);
      }
    });
    return () => { alive = false; };
  }, []);
  return {
    activeFy,
    min: activeFy?.fy_start || undefined,
    max: activeFy?.fy_end || undefined,
  };
}
