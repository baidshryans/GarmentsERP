import { createContext, useContext, useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/services/apiClient";
import { PERMISSIONS_KEY } from "./queryKeys";
import { makeCanAccess } from "@/lib/permissions";

const PermissionContext = createContext(null);

const EMPTY = { is_superuser: false, modules: {} };

async function fetchPermissions() {
  try {
    const res = await apiClient.get("/userauth/api/my-permissions/");
    return res.data;
  } catch {
    // On error behave permissively so a transient failure never locks a user
    // out of their own menu. The backend API remains the source of truth.
    return { is_superuser: true, modules: {} };
  }
}

// eslint-disable-next-line react/prop-types
export function PermissionProvider({ children }) {
  const queryClient = useQueryClient();
  const enabled =
    typeof window !== "undefined" && !!sessionStorage.getItem("Token");

  const { data, isSuccess } = useQuery({
    queryKey: PERMISSIONS_KEY,
    queryFn: fetchPermissions,
    enabled,
    staleTime: 10 * 60 * 1000,
    gcTime: 30 * 60 * 1000,
  });

  const snapshot = useMemo(
    () => ({
      loaded: isSuccess || !enabled,
      ...(data ?? EMPTY),
    }),
    [isSuccess, enabled, data]
  );

  const canAccess = useMemo(() => makeCanAccess(snapshot), [snapshot]);

  const refreshPermissions = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: PERMISSIONS_KEY });
  }, [queryClient]);

  const value = useMemo(
    () => ({ canAccess, refreshPermissions, permissionsLoaded: snapshot.loaded }),
    [canAccess, refreshPermissions, snapshot.loaded]
  );

  return (
    <PermissionContext.Provider value={value}>
      {children}
    </PermissionContext.Provider>
  );
}

export function usePermissions() {
  const ctx = useContext(PermissionContext);
  if (!ctx) throw new Error("usePermissions must be used inside <PermissionProvider>");
  return ctx;
}
