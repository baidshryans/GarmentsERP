import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select"
import { History } from "lucide-react"
import { fetchBarcodeHistoryList } from "@/services/apiService"

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
  const [params, setParams] = useSearchParams()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const search = params.get("search") || ""
  const sortby = params.get("sortby") || "-date"

  useEffect(() => {
    setLoading(true)
    fetchBarcodeHistoryList({ search, page, ordering: sortby }).then((res) => {
      if (res.success) {
        setRows(res.data.results ?? res.data)
        setTotalPages(res.data.total_pages ?? 1)
      } else {
        setError(String(res.error))
      }
      setLoading(false)
    })
  }, [search, page, sortby])

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <Input
          type="text"
          value={search}
          onChange={(e) => { setParams({ search: e.target.value, sortby }); setPage(1) }}
          placeholder="Search barcode, bill no, item…"
          className="max-w-xs h-9"
        />
        <Select value={sortby} onValueChange={(v) => setParams({ search, sortby: v })}>
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

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {!loading && error && <p className="text-sm text-destructive">Error: {error}</p>}

      {!loading && !error && (
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
                      No transactions found
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

      {/* Pagination */}
      {!loading && totalPages > 1 && (
        <div className="flex justify-between items-center">
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(p - 1, 1))} disabled={page === 1}>
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
          <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.min(p + 1, totalPages))} disabled={page === totalPages}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
