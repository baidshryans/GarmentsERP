import { useState, useRef, useEffect, useCallback } from "react"
import { createPortal } from "react-dom"
import { cn } from "@/lib/utils"

/**
 * Searchable combo box with keyboard navigation.
 *
 * Keyboard:
 *   ArrowDown / ArrowUp  — navigate the suggestion list
 *   Tab                  — select highlighted item AND move focus to next field
 *   Enter                — select highlighted item (stay in field)
 *   Escape               — close dropdown
 *
 * Props:
 *   options        {Array}    — array of objects to search through
 *   labelKey       {string}   — property to display as text (default "ac_name")
 *   searchKeys     {Array}    — additional keys to search across (default [])
 *   value          {string}   — controlled display value (sync from watch())
 *   onSelect       {fn(opt)}  — called when user selects an option
 *   onInputChange  {fn(val)}  — optional: called on every keystroke (for server-side search)
 *   placeholder    {string}
 *   className      {string}
 *   disabled       {bool}
 *   autoFocus      {bool}
 */
export function SearchableComboBox({
  options = [],
  labelKey = "ac_name",
  searchKeys = [],
  value = "",
  onSelect,
  onInputChange,
  placeholder = "Search…",
  className = "",
  disabled = false,
  autoFocus = false,
  tabIndex,
}) {
  const [open, setOpen] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)
  const [inputVal, setInputVal] = useState(value ?? "")
  const [dropdownStyle, setDropdownStyle] = useState({})
  const inputRef = useRef(null)
  const listRef = useRef(null)

  // Sync when parent updates the value (e.g. after reset() in edit mode)
  useEffect(() => {
    setInputVal(value ?? "")
  }, [value])

  const filtered = (options ?? []).filter((opt) => {
    const q = (inputVal ?? "").toLowerCase()
    if (!q) return true
    const keys = [labelKey, ...searchKeys]
    return keys.some((k) => String(opt[k] ?? "").toLowerCase().includes(q))
  })

  const select = useCallback(
    (opt) => {
      setInputVal(opt[labelKey] ?? "")
      setOpen(false)
      setActiveIndex(-1)
      onSelect?.(opt)
    },
    [labelKey, onSelect]
  )

  const handleKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault()
      if (!open) { setOpen(true); setActiveIndex(0); return }
      setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
      return
    }
    if (e.key === "ArrowUp") {
      e.preventDefault()
      if (!open) return
      setActiveIndex((i) => Math.max(i - 1, 0))
      return
    }
    if (e.key === "Tab") {
      // Select highlighted item (if any), then let Tab advance focus naturally
      if (open && activeIndex >= 0 && filtered[activeIndex]) {
        select(filtered[activeIndex])
      }
      setOpen(false)
      return
    }
    if (e.key === "Enter") {
      if (open && activeIndex >= 0 && filtered[activeIndex]) {
        e.preventDefault()
        select(filtered[activeIndex])
      }
      return
    }
    if (e.key === "Escape") {
      setOpen(false)
      setActiveIndex(-1)
    }
  }

  // Scroll highlighted item into view
  useEffect(() => {
    if (activeIndex >= 0 && listRef.current) {
      listRef.current.children[activeIndex]?.scrollIntoView({ block: "nearest" })
    }
  }, [activeIndex])

  // Recompute dropdown position whenever it opens or window scrolls/resizes
  useEffect(() => {
    if (!open || !inputRef.current) return
    const update = () => {
      const rect = inputRef.current.getBoundingClientRect()
      setDropdownStyle({
        position: "fixed",
        top: rect.bottom + 4,
        left: rect.left,
        width: rect.width,
      })
    }
    update()
    window.addEventListener("scroll", update, true)
    window.addEventListener("resize", update)
    return () => {
      window.removeEventListener("scroll", update, true)
      window.removeEventListener("resize", update)
    }
  }, [open])

  return (
    <div className={cn("relative", className)}>
      <input
        ref={inputRef}
        value={inputVal}
        disabled={disabled}
        placeholder={placeholder}
        autoFocus={autoFocus}
        tabIndex={tabIndex}
        autoComplete="off"
        onChange={(e) => {
          const val = e.target.value
          setInputVal(val)
          setOpen(true)
          setActiveIndex(-1)
          onInputChange?.(val)
        }}
        onKeyDown={handleKeyDown}
        onFocus={() => { if ((inputVal ?? "").length > 0 || filtered.length > 0) setOpen(true) }}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className={cn(
          "flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors",
          "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-50"
        )}
      />
      {open && filtered.length > 0 && createPortal(
        <div
          ref={listRef}
          style={dropdownStyle}
          className="z-[9999] bg-popover border border-border rounded-md shadow-md max-h-60 overflow-y-auto"
        >
          {filtered.map((opt, i) => (
            <div
              key={opt.id ?? i}
              className={cn(
                "px-3 py-2 text-sm cursor-pointer select-none",
                i === activeIndex
                  ? "bg-accent text-accent-foreground"
                  : "hover:bg-accent/50"
              )}
              onMouseDown={(e) => { e.preventDefault(); select(opt) }}
              onMouseEnter={() => setActiveIndex(i)}
            >
              {opt[labelKey]}
            </div>
          ))}
        </div>,
        document.body
      )}
    </div>
  )
}
