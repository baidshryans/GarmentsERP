import { Outlet } from "react-router-dom"
import { Toaster } from "@/components/ui/toaster"
import { SidebarProvider } from "@/components/ui/sidebar"
import AIAssistant from "@/components/AI/AIAssistant"
import { TopMenuBar } from "./TopMenuBar"

export function TopBarLayout() {
  return (
    // SidebarProvider is required here only to satisfy useSidebar() calls
    // inside RetailSwitcher, FiscalYearSwitcher, ExhibitionSwitcher and NavUser
    // (they use isMobile from it). No <Sidebar> component is rendered.
    <SidebarProvider>
      <div className="w-full">
        <TopMenuBar />
        {/* mt-12 offsets content below the 48 px fixed topbar */}
        <main className="mt-12 min-h-screen bg-background">
          <div className="mx-auto w-full max-w-screen-2xl min-w-0 overflow-x-auto">
            <Outlet />
          </div>
        </main>
        <Toaster />
        <AIAssistant />
      </div>
    </SidebarProvider>
  )
}
