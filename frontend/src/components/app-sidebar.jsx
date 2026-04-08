import * as React from "react"
import { Link } from "react-router-dom"
import { Gem, LayoutTemplate, Home, AppWindow } from "lucide-react"

import { NavMain } from "@/components/nav-main"
import { NavUser } from "@/components/nav-user"
import { FiscalYearSwitcher } from "@/components/shared/FiscalYearSwitcher"
import { ExhibitionSwitcher } from "@/components/shared/ExhibitionSwitcher"
import { RetailSwitcher } from "@/components/shared/RetailSwitcher"
import { navData, navSections } from "@/config/navData"
import { useLayout } from "@/contexts/LayoutContext"
import { useLicense } from "@/contexts/LicenseContext"
import { getRetails } from "@/services/apiService"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
} from "@/components/ui/sidebar"

const user = {
  name:   JSON.parse(localStorage.getItem("user"))?.username ?? "",
  email:  JSON.parse(localStorage.getItem("user"))?.email    ?? "",
  avatar: "/avatars/shadcn.jpg",
}

/** Build visible items for each section by merging licensed parts */
function useLicensedSections() {
  const { isNavGroupLicensed } = useLicense()
  return navSections
    .map(({ label, parts }) => {
      const items = parts
        .filter(({ key }) => isNavGroupLicensed(key))
        .flatMap(({ items }) => items)
      return { label, items }
    })
    .filter(({ items }) => items.length > 0)
}

export function AppSidebar({ ...props }) {
  const { setLayout } = useLayout()
  const sections = useLicensedSections()
  const [companyName, setCompanyName] = React.useState("")

  React.useEffect(() => {
    getRetails().then((res) => {
      if (res.success && res.data.results?.length > 0) {
        setCompanyName(res.data.results[0].company_name || "")
      }
    })
  }, [])

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader className="border-b border-sidebar-border">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton size="lg" asChild>
              <a href="#">
                <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                  <Gem className="size-4" />
                </div>
                <div className="flex flex-col gap-0.5 leading-none">
                  <span className="font-semibold tracking-wide text-sidebar-accent-foreground">{companyName || "ERP"}</span>
                  <span className="text-xs text-sidebar-foreground/60">ERP v1.0.0</span>
                </div>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>

      <RetailSwitcher />
      <FiscalYearSwitcher />
      <ExhibitionSwitcher />

      <SidebarContent>
        {/* Home & Apps quick links */}
        <SidebarMenu className="px-2 pt-2">
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Home">
              <Link to="/" className="text-sidebar-foreground hover:text-sidebar-accent-foreground">
                <Home className="size-4" />
                <span>Home</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton asChild tooltip="Apps">
              <Link to="/apps" className="text-sidebar-foreground hover:text-sidebar-accent-foreground">
                <AppWindow className="size-4" />
                <span>Apps</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>

        {/* Module nav groups — filtered by license */}
        {sections.map(({ label, items }) => (
          <NavMain key={label} items={items} label={label} />
        ))}
      </SidebarContent>

      <SidebarFooter>
        <NavUser user={user} />
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={() => setLayout("topbar")}
              tooltip="Switch to top menu bar"
              className="text-muted-foreground hover:text-foreground"
            >
              <LayoutTemplate className="size-4" />
              <span>Switch to Top Menu</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}
