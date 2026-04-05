import { Toaster } from "@/components/ui/toaster"
import {
    SidebarInset,
    SidebarProvider,
} from "@/components/ui/sidebar"
import { Outlet } from "react-router-dom"
import { AppSidebar } from "./components/app-sidebar"
import AIAssistant from "./components/AI/AIAssistant"
import { GoldRateProvider } from "./contexts/GoldRateContext"
import { LayoutProvider, useLayout } from "./contexts/LayoutContext"
import { TopBarLayout } from "./components/top-menu/TopBarLayout"

function LayoutRouter() {
    const { layout } = useLayout()

    if (layout === "topbar") {
        return <TopBarLayout />
    }

    return (
        <SidebarProvider>
            <AppSidebar />
            <SidebarInset className="min-w-0 overflow-x-hidden">
                <div className="min-w-0 overflow-x-auto">
                    <Outlet />
                </div>
                <Toaster />
                <AIAssistant />
            </SidebarInset>
        </SidebarProvider>
    )
}

export function Page() {
    return (
        <GoldRateProvider>
            <LayoutProvider>
                <LayoutRouter />
            </LayoutProvider>
        </GoldRateProvider>
    )
}
