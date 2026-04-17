import { useState, useEffect, useRef, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { Search } from "lucide-react"
import { navSections } from "@/config/navData"
import { useLicense } from "@/contexts/LicenseContext"

/** Recursively flatten nav items into searchable entries */
function flattenItems(items, sectionLabel, parentTitle = "") {
  const result = []
  for (const item of items) {
    if (item.items && item.items.length > 0) {
      result.push(...flattenItems(item.items, sectionLabel, item.title))
    } else if (item.url && item.url !== "#") {
      result.push({
        title: item.title,
        url: item.url,
        section: sectionLabel,
        parent: parentTitle,
        icon: item.icon ?? null,
        searchText: `${sectionLabel} ${parentTitle} ${item.title}`.toLowerCase(),
      })
    }
  }
  return result
}

export function NavSearch({ className = "" }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState("")
  const [activeIndex, setActiveIndex] = useState(0)
  const inputRef = useRef(null)
  const navigate = useNavigate()
  const { isNavGroupLicensed } = useLicense()

  // Build flat searchable list from licensed nav items
  const allItems = navSections
    .flatMap(({ label, parts }) => {
      const items = parts
        .filter(({ key }) => isNavGroupLicensed(key))
        .flatMap(({ items }) => items)
      return flattenItems(items, label)
    })

  const results = query.trim()
    ? allItems.filter((item) => item.searchText.includes(query.toLowerCase()))
    : []

  // Open on Ctrl+K / Cmd+K
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault()
        setOpen((v) => !v)
      }
      if (e.key === "Escape") setOpen(false)
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setQuery("")
      setActiveIndex(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  const go = useCallback(
    (url) => {
      navigate(url)
      setOpen(false)
    },
    [navigate]
  )

  const handleKey = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      setActiveIndex((i) => Math.min(i + 1, results.length - 1))
    } else if (e.key === "ArrowUp") {
      e.preventDefault()
      setActiveIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === "Enter" && results[activeIndex]) {
      go(results[activeIndex].url)
    }
  }

  return (
    <>
      {/* Trigger button */}
      <button
        onClick={() => setOpen(true)}
        className={`flex items-center gap-2 px-2.5 py-1.5 rounded-md text-sm text-muted-foreground border border-input bg-background hover:bg-accent hover:text-accent-foreground transition-colors ${className}`}
        title="Search navigation (Ctrl+K)"
      >
        <Search className="w-3.5 h-3.5 shrink-0" />
        <span className="hidden sm:inline text-xs">Search…</span>
        <kbd className="hidden sm:inline ml-1 px-1 py-0.5 text-[10px] rounded bg-muted text-muted-foreground border border-border font-mono leading-none">
          Ctrl K
        </kbd>
      </button>

      {/* Modal overlay */}
      {open && (
        <div
          className="fixed inset-0 z-[200] flex items-start justify-center pt-[15vh] bg-black/40 backdrop-blur-sm"
          onClick={() => setOpen(false)}
        >
          <div
            className="w-full max-w-lg mx-4 bg-background rounded-xl shadow-2xl border border-border overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Search input */}
            <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
              <Search className="size-4 text-muted-foreground shrink-0" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => { setQuery(e.target.value); setActiveIndex(0) }}
                onKeyDown={handleKey}
                placeholder="Search menus…"
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              />
              <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground border border-border font-mono">Esc</kbd>
            </div>

            {/* Results */}
            <div className="max-h-80 overflow-y-auto py-1">
              {query.trim() === "" && (
                <p className="text-xs text-muted-foreground text-center py-6">
                  Start typing to search all menus…
                </p>
              )}
              {query.trim() !== "" && results.length === 0 && (
                <p className="text-xs text-muted-foreground text-center py-6">
                  No results for "{query}"
                </p>
              )}
              {results.map((item, i) => (
                <button
                  key={item.url}
                  onClick={() => go(item.url)}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                    i === activeIndex ? "bg-accent text-accent-foreground" : "hover:bg-accent/50"
                  }`}
                >
                  {item.icon
                    ? <item.icon className="size-4 shrink-0 text-muted-foreground" />
                    : <Search className="size-4 shrink-0 text-muted-foreground opacity-40" />
                  }
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium">{item.title}</span>
                    <span className="ml-2 text-xs text-muted-foreground">
                      {item.parent ? `${item.section} › ${item.parent}` : item.section}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
