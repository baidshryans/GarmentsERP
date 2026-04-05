import { createContext, useContext, useState, useEffect, useCallback } from "react"
import apiClient from "@/services/apiClient"

const LicenseContext = createContext(null)

export function LicenseProvider({ children }) {
  const [license, setLicense] = useState({
    loaded: false,
    company: "",
    status: "",
    start_date: null,
    end_date: null,
    licensed_apps: [],
    nav_groups: [],
  })

  const fetchLicense = useCallback(async () => {
    try {
      const res = await apiClient.get("/licensing/api/my-apps/")
      setLicense({ loaded: true, ...res.data })
    } catch {
      // If licensing endpoint fails (no company yet, etc.), allow all nav groups
      setLicense((prev) => ({ ...prev, loaded: true }))
    }
  }, [])

  useEffect(() => {
    // Only fetch if user is authenticated
    if (localStorage.getItem("Token")) {
      fetchLicense()
    }
  }, [fetchLicense])

  const isAppLicensed = useCallback(
    (appCode) => {
      if (!license.loaded) return true // Don't block while loading
      if (license.licensed_apps.length === 0 && !license.company) return true // No licensing set up
      return license.licensed_apps.includes(appCode)
    },
    [license]
  )

  const isNavGroupLicensed = useCallback(
    (navKey) => {
      if (!license.loaded) return true
      if (license.nav_groups.length === 0 && !license.company) return true // No licensing set up
      return license.nav_groups.includes(navKey)
    },
    [license]
  )

  return (
    <LicenseContext.Provider value={{ license, isAppLicensed, isNavGroupLicensed, refreshLicense: fetchLicense }}>
      {children}
    </LicenseContext.Provider>
  )
}

export function useLicense() {
  const ctx = useContext(LicenseContext)
  if (!ctx) throw new Error("useLicense must be used inside <LicenseProvider>")
  return ctx
}
