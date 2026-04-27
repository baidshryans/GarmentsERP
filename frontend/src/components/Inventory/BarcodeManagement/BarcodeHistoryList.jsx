import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Label } from "@/components/ui/label"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select"
import { SearchableComboBox } from "@/components/ui/SearchableComboBox"
import { fetchBarcodeHistoryList, fetchBarcodeList } from "@/services/apiService"

const TRANS_LABELS = {
  PURCHASE: "Purchase",
  SALE: "Sale",
  SALE_RETURN: "Sale Return",
  KARIGAR_ISSUE: "Karigar Issue",
  KARIGAR_RECEIVE: "Karigar Receive",
  SPLIT: "Split",
  MERGE: "Merge",
  TRANSFER: "Transfer",
  ADJUSTMENT: "Adjustment",
}

const fmtWt = (v) => v != null ? Number(v).toLocaleString("en-IN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }) : "-"
const fmtDate = (v) => new Date(v).toLocaleString("en-GB").replaceAll("/", "-")

export default function BarcodeHistoryList() {
  const [barcodeOptions, setBarcodeOptions] = useState([])
  const [barcodeSearch, setBarcodeSearch] = useState("")
  const [selectedBarcode, setSelectedBarcode] = useState("")
  const [sortby, setSortby] = useState("-date")

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [hasSearched, setHasSearched] = useState(false)

  // Server-side barcode search for the combobox
  useEffect(() => {
    let cancelled = false
    const t = setTimeout(() => {
      fetchBarcodeList({ search: barcodeSearch, page: 1, page_size: 20 }).then((res) => {
        if (cancelled) return
        if (res.success) {
          const list = res.data.results ?? res.data ?? []
          setBarcodeOptions(list)
        }
      })
    }, 200)
    return () => { cancelled = true; clearTimeout(t) }
  }, [barcodeSearch])

  const loadHistory = (barcode, ordering) => {
    setError("")
    setLoading(true)
    setHasSearched(true)
    fetchBarcodeHistoryList({ search: barcode, page: 1, ordering }).then((res) => {
      if (res.success) {
        setRows(res.data.results ?? res.data ?? [])
      } else {
        setError(String(res.error))
        setRows([])
      }
      setLoading(false)
    })
  }

  const handleShow = () => {
    if (!selectedBarcode) {
      setError("Please select a barcode first")
      return
    }
    loadHistory(selectedBarcode, sortby)
  }

  const handleSortChange = (v) => {
    setSortby(v)
    if (hasSearched && selectedBarcode) loadHistory(selectedBarcode, v)
  }

  const handleClear = () => {
    setSelectedBarcode("")
    setBarcodeSearch("")
    setSortby("-date")
    setRows([])
    setHasSearched(false)
    setError("")
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Barcode selector */}
      <div className="flex flex-wrap gap-3 items-end">
        <div className="flex flex-col gap-1 w-72">
          <Label className="text-xs">Barcode</Label>
          <SearchableComboBox
            options={barcodeOptions}
            labelKey="barcode"
            searchKeys={["barcode"]}
            value={selectedBarcode}
            placeholder="Search barcode…"
            onInputChange={setBarcodeSearch}
            onSelect={(opt) => setSelectedBarcode(opt.barcode)}
          />
        </div>
        <Button size="sm" onClick={handleShow} disabled={!selectedBarcode || loading}>
          {loading ? "Loading…" : "Show"}
        </Button>
        <Button size="sm" variant="outline" onClick={handleClear} disabled={!hasSearched && !selectedBarcode}>
          Clear
        </Button>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Sort by</Label>
          <Select value={sortby} onValueChange={handleSortChange}>
            <SelectTrigger className="w-44 h-9">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="-date">Newest first</SelectItem>
              <SelectItem value="date">Oldest first</SelectItem>
              <SelectItem value="billno">Bill No ↑</SelectItem>
              <SelectItem value="-billno">Bill No ↓</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {!loading && hasSearched && !error && (
        <div className="rounded-lg border border-border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                  <th className="px-3 py-2.5 text-left font-semibold">Date & Time</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Barcode</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Item</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Pcs</th>
                  <th className="px-3 py-2.5 text-right font-semibold">Gw (g)</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Bill No</th>
                  <th className="px-3 py-2.5 text-left font-semibold">Type</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-10 text-center text-sm text-muted-foreground">
                      No transactions found for {selectedBarcode}
                    </td>
                  </tr>
                )}
                {rows.map((r, i) => (
                  <tr key={r.id ?? i} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/20" : ""}`}>
                    <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">{fmtDate(r.date)}</td>
                    <td className="px-3 py-2 text-xs font-mono">{r.barcode}</td>
                    <td className="px-3 py-2 text-xs">
                      {r.item_name
                        ? <span>{r.item_short_code && <span className="text-muted-foreground mr-1">{r.item_short_code}</span>}{r.item_name}</span>
                        : <span className="text-muted-foreground">-</span>}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{r.pcs ?? "-"}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-xs">{fmtWt(r.gw)}</td>
                    <td className="px-3 py-2 text-xs font-mono">{r.billno || "-"}</td>
                    <td className="px-3 py-2 text-xs">
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground">
                        {TRANS_LABELS[r.trans_type] || r.trans_type}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!hasSearched && !loading && (
        <p className="text-sm text-muted-foreground">Select a barcode and click Show to view its transaction history.</p>
      )}
    </div>
  )
}
