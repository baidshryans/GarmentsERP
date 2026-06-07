import { createContext, useContext, useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/apiClient";
import { LICENSE_KEY } from "./queryKeys";

const LicenseContext = createContext(null);

const EMPTY_LICENSE = {
  company: "",
  status: "",
  start_date: null,
  end_date: null,
  licensed_apps: [],
  nav_groups: [],
};

async function fetchLicense() {
  try {
    const res = await apiClient.get("/licensing/api/my-apps/");
    return res.data;
  } catch {
    // If licensing endpoint fails (no company yet, etc.), behave as "no licensing
    // set up" — the gating logic below allows everything in that case.
    return EMPTY_LICENSE;
  }
}

// eslint-disable-next-line react/prop-types
export function LicenseProvider({ children }) {
  const queryClient = useQueryClient();

  // Only fetch when authenticated. The token is stored at login; the gate runs
  // on every render but `enabled` controls the actual fetch.
  const enabled =
    typeof window !== "undefined" && !!sessionStorage.getItem("Token");

  const { data, isSuccess } = useQuery({
    queryKey: LICENSE_KEY,
    queryFn: fetchLicense,
    enabled,
    // License rarely changes — cache aggressively. Manual refresh is available
    // via refreshLicense() after admin actions.
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  // Stable object identity so callbacks below don't re-create on every render.
  const license = useMemo(
    () => ({
      loaded: isSuccess || !enabled, // unauthenticated → don't block UI
      ...(data ?? EMPTY_LICENSE),
    }),
    [isSuccess, enabled, data]
  );

  const refreshLicense = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: LICENSE_KEY });
  }, [queryClient]);

  const isAppLicensed = useCallback(
    (appCode) => {
      if (!license.loaded) return true; // Don't block while loading
      if (license.licensed_apps.length === 0 && !license.company) return true; // No licensing set up
      return license.licensed_apps.includes(appCode);
    },
    [license]
  );

  const isNavGroupLicensed = useCallback(
    (navKey) => {
      // System/Settings is always accessible — never license-gated
      if (navKey === "navSettings") return true;
      if (!license.loaded) return true;
      if (license.nav_groups.length === 0 && !license.company) return true; // No licensing set up
      return license.nav_groups.includes(navKey);
    },
    [license]
  );

  return (
    <LicenseContext.Provider
      value={{ license, isAppLicensed, isNavGroupLicensed, refreshLicense }}
    >
      {children}
    </LicenseContext.Provider>
  );
}

export function useLicense() {
  const ctx = useContext(LicenseContext);
  if (!ctx) throw new Error("useLicense must be used inside <LicenseProvider>");
  return ctx;
}
