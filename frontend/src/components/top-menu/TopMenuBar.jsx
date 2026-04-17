import { Link } from "react-router-dom"
import { Gem, ChevronDown, PanelLeft, Home, AppWindow } from "lucide-react"
import { NavSearch } from "@/components/NavSearch"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
  DropdownMenuLabel,
} from "@/components/ui/dropdown-menu"
import { NavUser } from "@/components/nav-user"
import { FiscalYearSwitcher } from "@/components/shared/FiscalYearSwitcher"
import { ExhibitionSwitcher } from "@/components/shared/ExhibitionSwitcher"
import { RetailSwitcher } from "@/components/shared/RetailSwitcher"
import { navSections } from "@/config/navData"
import { useLayout } from "@/contexts/LayoutContext"
import { useLicense } from "@/contexts/LicenseContext"

/** Build visible items for each section by merging licensed parts */
function useLicensedSections(isNavGroupLicensed) {
  return navSections
    .map(({ label, parts }) => {
      const items = parts
        .filter(({ key }) => isNavGroupLicensed(key))
        .flatMap(({ items }) => items)
      return { label, items }
    })
    .filter(({ items }) => items.length > 0)
}

// ── Recursive item renderer ───────────────────────────────────────────────────
// Renders either a plain DropdownMenuItem (leaf) or a DropdownMenuSub (group)

function NavItem({ item }) {
  if (item.items && item.items.length > 0) {
    return (
      <DropdownMenuSub>
        <DropdownMenuSubTrigger className="flex items-center gap-2 text-sm">
          {item.icon && <item.icon className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />}
          {item.title}
        </DropdownMenuSubTrigger>
        <DropdownMenuSubContent className="min-w-[200px]">
          {item.items.map((child) => (
            <NavItem key={child.title} item={child} />
          ))}
        </DropdownMenuSubContent>
      </DropdownMenuSub>
    )
  }

  return (
    <DropdownMenuItem asChild>
      <Link to={item.url} className="flex items-center gap-2 text-sm cursor-pointer">
        {item.icon && <item.icon className="w-3.5 h-3.5 shrink-0 text-muted-foreground" />}
        {item.title}
      </Link>
    </DropdownMenuItem>
  )
}

// ── One dropdown per nav section ──────────────────────────────────────────────

function SectionDropdown({ label, items }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-1 px-2.5 py-1 rounded text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors whitespace-nowrap outline-none data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground">
          {label}
          <ChevronDown className="w-3.5 h-3.5 opacity-60" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="start"
        sideOffset={8}
        className="min-w-[220px] max-h-[80vh] overflow-y-auto"
      >
        <DropdownMenuLabel className="text-xs text-muted-foreground font-normal px-2 py-1">
          {label}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {items.map((item) => (
          <NavItem key={item.title} item={item} />
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// ── Main TopMenuBar ───────────────────────────────────────────────────────────

const user = {
  name:   JSON.parse(localStorage.getItem("user"))?.username ?? "",
  email:  JSON.parse(localStorage.getItem("user"))?.email    ?? "",
  avatar: "/avatars/shadcn.jpg",
}

export function TopMenuBar() {
  const { setLayout } = useLayout()
  const { isNavGroupLicensed } = useLicense()
  const filteredSections = useLicensedSections(isNavGroupLicensed)

  return (
    <nav className="fixed top-0 inset-x-0 z-50 h-12 flex items-center bg-sidebar border-b border-sidebar-border px-3 gap-1">

      {/* ── Logo ── */}
      <div className="flex items-center gap-2 pr-3 border-r border-sidebar-border mr-1 shrink-0">
        <div className="flex aspect-square size-7 items-center justify-center rounded-md bg-sidebar-primary text-sidebar-primary-foreground">
          <Gem className="size-4" />
        </div>
        <span className="font-semibold text-sm tracking-wide text-sidebar-accent-foreground whitespace-nowrap">
          JEWEL INDIA
        </span>
      </div>

      {/* ── Home & Apps ── */}
      <Link to="/" className="flex items-center gap-1 px-2 py-1 rounded text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors whitespace-nowrap">
        <Home className="w-3.5 h-3.5" />
      </Link>
      <Link to="/apps" className="flex items-center gap-1 px-2 py-1 rounded text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors whitespace-nowrap">
        <AppWindow className="w-3.5 h-3.5" />
        <span>Apps</span>
      </Link>

      <div className="w-px h-5 bg-sidebar-border mx-0.5" />

      {/* ── Nav section dropdowns (scrollable) ── */}
      <div className="flex items-center gap-0.5 overflow-x-auto flex-1 scrollbar-none">
        {filteredSections.map((section) => (
          <SectionDropdown
            key={section.label}
            label={section.label}
            items={section.items}
          />
        ))}
      </div>

      {/* ── Search ── */}
      <NavSearch className="shrink-0" />

      {/* ── Right side: context switchers + user + toggle ── */}
      <div className="flex items-center gap-1 shrink-0 pl-2 border-l border-sidebar-border ml-1">
        <RetailSwitcher />
        <FiscalYearSwitcher />
        <ExhibitionSwitcher />
        <NavUser user={user} />

        {/* Switch back to sidebar */}
        <button
          onClick={() => setLayout("sidebar")}
          title="Switch to sidebar layout"
          className="p-1.5 rounded hover:bg-sidebar-accent text-sidebar-foreground hover:text-sidebar-accent-foreground transition-colors"
        >
          <PanelLeft className="size-4" />
        </button>
      </div>
    </nav>
  )
}
