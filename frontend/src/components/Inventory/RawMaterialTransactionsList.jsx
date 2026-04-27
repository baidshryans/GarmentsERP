import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select"
import { Download, Filter, List } from "lucide-react"
import { getRawMaterialTransactions, getFiscalYears } from "@/services/apiService"

const TRANS_LABELS = {
  OPENING: "Opening Balance",
  PURCHASE: "Purchase",
  PURCHASE_RETURN: "Purchase Return",
  PURCHASE_DEL: "Purchase (Reversed)",
  KR_GOLD_ISSUE: "Karigar Gold Issue",
  KR_GOLD_ISSUE_DEL: "Gold Issue (Reversed)",
  KR_STONE_ISSUE: "Karigar Stone Issue",
  KR_STONE_ISSUE_DEL: "Stone Issue (Reversed)",
  KR_STONE_RETURN: "Karigar Stone Return",
  KR_STONE_RETURN_DEL: "Stone Return (Reversed)",
  ADJUSTMENT: "Manual Adjustment",
}

const fmtWt = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 3, maximumFractionDigits: 3 })
const fmtAmt = (v) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const today = new Date().toISOString().split("T")[0]

function exportCSV(data) {
  const headers = ["Date", "Item", "Trans Type", "Bill No", "Packet", "Purity", "Pcs", "Ct", "Gw", "Rate", "Amount"]
  const rows = data.map((r) => [
    new Date(r.date).toLocaleDateString("en-GB"),
    r.item_name || "",
    r.trans_type,
    r.billno || "",
    r.packet_no || "",
    r.purity_name || "",
    r.pcs, r.ct, r.gw, r.rate || "", r.amt || "",
  ])
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n")
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = `raw_material_transactions_${today}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function RawMaterialTransactionsList() {
  const [fromDate, setFromDate] = useState("")
  const [toDate, setToDate] = useState(today)
  const [search, setSearch] = useState("")
  const [transType, setTransType] = useState("")
  const [data, setData] = useState([])
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [fetched, setFetched] = useState(false)

  useEffect(() => {
    getFiscalYears().then((res) => {
      if (res.success) {
        const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
        const active = list.find((fy) => fy.is_active)
        if (active?.fy_start) setFromDate(active.fy_start)
        else {
          const now = new Date()
          const y = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear()
          setFromDate(`${y}-04-01`)
        }
      }
    })
  }, [])

  const fetchData = async (pg = 1) => {
    setLoading(true)
    setFetched(true)
    const params = { page: pg, ordering: "-date" }
    if (search) params.search = search
    if (transType) params.trans_type = transType
    if (fromDate) params.from_date = fromDate
    if (toDate) params.to_date = toDate
    const res = await getRawMaterialTransactions(params)
    if (res.success) {
      setData(res.data.results ?? res.data)
      setTotalPages(res.data.total_pages ?? 1)
      setTotalCount(res.data.count ?? 0)
    } else {
      setData([])
    }
    setLoading(false)
  }

  const handleSearch = () => { setPage(1); fetchData(1) }

  const handlePageChange = (pg) => { setPage(pg); fetchData(pg) }

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="p-4 bg-muted/30 rounded-lg border border-border space-y-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <List className="size-4" /> Raw Material Transactions
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1 min-w-52">
            <Label className="text-xs">Search (item name / bill no)</Label>
            <Input
              className="h-9"
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
          <div className="flex flex-col gap-1 w-44">
            <Label className="text-xs">Transaction Type</Label>
            <Select value={transType} onValueChange={setTransType}>
              <SelectTrigger className="h-9"><SelectValue placeholder="All types" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="">All types</SelectItem>
                {Object.entries(TRANS_LABELS).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1 w-36">
            <Label className="text-xs">From Date</Label>
            <Input type="date" className="h-9" value={fromDate} onChange={(e) => setFromDate(e.target.value)} max={toDate || undefined} />
          </div>
          <div className="flex flex-col gap-1 w-36">
            <Label className="text-xs">To Date</Label>
            <Input type="date" className="h-9" value={toDate} onChange={(e) => setToDate(e.target.value)} min={fromDate || undefined} />
          </div>
          <Button size="sm" onClick={handleSearch} disabled={loading} className="h-9">
            {loading ? "Loading…" : "Search"}
          </Button>
          {data.length > 0 && (
            <Button size="sm" variant="outline" onClick={() => exportCSV(data)} className="h-9 ml-auto">
              <Download className="w-3.5 h-3.5 mr-1.5" /> CSV
            </Button>
          )}
        </div>
      </div>

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(8)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
        </div>
      )}

      {!loading && fetched && (
        <>
          {totalCount > 0 && (
            <p className="text-xs text-muted-foreground">{totalCount.toLocaleString()} record{totalCount !== 1 ? "s" : ""} found</p>
          )}
          <div className="rounded-lg border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-3 py-2.5 text-left font-semibold">Date</th>
                    <th className="px-3 py-2.5 text-left font-semibold">Item</th>
                    <th className="px-3 py-2.5 text-left font-semibold">Type</th>
                    <th className="px-3 py-2.5 text-left font-semibold">Bill No</th>
                    <th className="px-3 py-2.5 text-left font-semibold">Packet</th>
                    <th className="px-3 py-2.5 text-left font-semibold">Purity</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Pcs</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Ct</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Gw (g)</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Rate</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {data.length === 0 && (
                    <tr>
                      <td colSpan={11} className="px-3 py-10 text-center text-sm text-muted-foreground">
                        No transactions found
                      </td>
                    </tr>
                  )}
                  {data.map((r, i) => {
                    const isOut = r.gw < 0 || r.ct < 0 || r.pcs < 0
                    const rowColor = isOut ? "text-red-700" : r.gw > 0 || r.ct > 0 || r.pcs > 0 ? "text-green-700" : ""
                    return (
                      <tr key={r.id} className={`border-t border-border/50 ${i % 2 === 1 ? "bg-muted/20" : ""}`}>
                        <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap">
                          {new Date(r.date).toLocaleDateString("en-GB")}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          {r.item_short_code && <span className="text-muted-foreground mr-1">{r.item_short_code}</span>}
                          {r.item_name || "-"}
                        </td>
                        <td className="px-3 py-2 text-xs">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground">
                            {TRANS_LABELS[r.trans_type] || r.trans_type}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs font-mono">{r.billno || "-"}</td>
                        <td className="px-3 py-2 text-xs">{r.packet_no || "-"}</td>
                        <td className="px-3 py-2 text-xs">{r.purity_name || "-"}</td>
                        <td className={`px-3 py-2 text-right tabular-nums text-xs ${rowColor}`}>
                          {r.pcs !== 0 ? (r.pcs > 0 ? `+${r.pcs}` : r.pcs) : "-"}
                        </td>
                        <td className={`px-3 py-2 text-right tabular-nums text-xs ${rowColor}`}>
                          {Math.abs(r.ct) > 0.001 ? (r.ct > 0 ? `+${fmtWt(r.ct)}` : fmtWt(r.ct)) : "-"}
                        </td>
                        <td className={`px-3 py-2 text-right tabular-nums text-xs font-medium ${rowColor}`}>
                          {Math.abs(r.gw) > 0.001 ? (r.gw > 0 ? `+${fmtWt(r.gw)}` : fmtWt(r.gw)) : "-"}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-xs">{r.rate ? fmtAmt(r.rate) : "-"}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-xs">{r.amt ? fmtAmt(r.amt) : "-"}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {totalPages > 1 && (
            <div className="flex justify-between items-center">
              <Button variant="outline" size="sm" onClick={() => handlePageChange(page - 1)} disabled={page === 1}>
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => handlePageChange(page + 1)} disabled={page === totalPages}>
                Next
              </Button>
            </div>
          )}
        </>
      )}

      {!loading && !fetched && (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="rounded-full bg-muted/50 p-4 mb-4">
            <List className="size-8 text-muted-foreground" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">Raw Material Transactions</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            Set your filters and click Search to view all raw material transactions.
          </p>
        </div>
      )}
    </div>
  )
}
