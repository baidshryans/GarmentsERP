import { createContext, useContext, useState } from "react"

const LayoutContext = createContext(null)

export function LayoutProvider({ children }) {
  const [layout, setLayoutState] = useState(
    () => localStorage.getItem("erp_nav_layout") || "sidebar"
  )

  const setLayout = (val) => {
    localStorage.setItem("erp_nav_layout", val)
    setLayoutState(val)
  }

  return (
    <LayoutContext.Provider value={{ layout, setLayout }}>
      {children}
    </LayoutContext.Provider>
  )
}

export function useLayout() {
  const ctx = useContext(LayoutContext)
  if (!ctx) throw new Error("useLayout must be used inside <LayoutProvider>")
  return ctx
}
