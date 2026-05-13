import { useState, useEffect, useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectTrigger,
  SelectContent,
  SelectItem,
  SelectValue,
} from "@/components/ui/select";
import { Download, Filter, X } from "lucide-react";
import {
  getUnbarcodedStockReport,
  fetchItems,
  fetchPurity,
  getLedgers,
} from "@/services/apiService";

const SOURCE_CHOICES = [
  { code: "KAR_REC", label: "Karigar Receipt" },
  { code: "PUR_VOU", label: "Purchase Voucher" },
  { code: "BAR_CONV", label: "Barcode Conversion" },
  { code: "MANUAL", label: "Manual" },
  { code: "OP_STK", label: "Opening Stock" },
];

const METAL_COLORS = ["Yellow", "White", "Rose", "Mixed"];

function fyDefaultDates() {
  const now = new Date();
  const y = now.getFullYear();
  const fyStart = now.getMonth() >= 3 ? new Date(y, 3, 1) : new Date(y - 1, 3, 1);
  const fmt = (d) => d.toISOString().slice(0, 10);
  return { date_from: fmt(fyStart), date_to: fmt(now) };
}

export default function UnbarcodedStockReport() {
  const initialDates = useMemo(fyDefaultDates, []);
  const [filters, setFilters] = useState({
    stk_status: "active",
    source: [],
    item: "",
    purity: "",
    kr_code: "",
    design_code: "",
    label: "",
    metal_color: "",
    date_from: initialDates.date_from,
    date_to: initialDates.date_to,
    gw_min: "",
    gw_max: "",
    nw_min: "",
    nw_max: "",
  });

  const [rows, setRows] = useState([]);
  const [totals, setTotals] = useState({ pcs: 0, gw: 0, nw: 0, value: 0, count: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [items, setItems] = useState([]);
  const [purities, setPurities] = useState([]);
  const [karigars, setKarigars] = useState([]);

  useEffect(() => {
    (async () => {
      const [it, pu, kg] = await Promise.all([
        fetchItems({ page_size: 10000 }),
        fetchPurity(),
        getLedgers({ type: "KR", page_size: 10000 }),
      ]);
      if (it.success) setItems(it.data || []);
      if (pu.success) {
        const list = Array.isArray(pu.data) ? pu.data : pu.data?.results || [];
        setPurities(list);
      }
      if (kg.success) {
        const list = Array.isArray(kg.data) ? kg.data : kg.data?.results || [];
        setKarigars(list);
      }
    })();
  }, []);

  const update = (k) => (v) => setFilters((f) => ({ ...f, [k]: v }));

  const toggleSource = (code) => {
    setFilters((f) => ({
      ...f,
      source: f.source.includes(code)
        ? f.source.filter((c) => c !== code)
        : [...f.source, code],
    }));
  };

  const buildParams = () => {
    const { source, ...rest } = filters;
    const p = { ...rest };
    if (source && source.length) p.source = source.join(",");
    return p;
  };

  const fetchData = async () => {
    setLoading(true);
    setError("");
    const res = await getUnbarcodedStockReport(buildParams());
    setLoading(false);
    if (!res.success) {
      setError(typeof res.error === "string" ? res.error : "Failed to load report");
      setRows([]);
      setTotals({ pcs: 0, gw: 0, nw: 0, value: 0, count: 0 });
      return;
    }
    setRows(res.data?.rows || []);
    setTotals(res.data?.totals || { pcs: 0, gw: 0, nw: 0, value: 0, count: 0 });
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resetFilters = () => {
    setFilters({
      stk_status: "active",
      source: [],
      item: "",
      purity: "",
      kr_code: "",
      design_code: "",
      label: "",
      metal_color: "",
      date_from: initialDates.date_from,
      date_to: initialDates.date_to,
      gw_min: "",
      gw_max: "",
      nw_min: "",
      nw_max: "",
    });
  };

  const exportCsv = () => {
    if (!rows.length) return;
    const headers = [
      "Label", "Item", "Purity", "Pcs", "Gross Wt", "Net Wt", "HUID",
      "Design", "Karigar", "Customer Order", "Color", "Size",
      "Source", "Stock Status", "Created Date", "Voucher", "Value", "Total",
    ];
    const escape = (v) => {
      const s = v == null ? "" : String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [headers.join(",")];
    rows.forEach((r) => {
      lines.push([
        r.label, r.item_name, r.purity, r.pcs, r.gw, r.nw, r.huid,
        r.design_code, r.kr_code_name, r.customer_order_no, r.metal_color, r.size,
        r.source_label, r.stk_status ? "In Stock" : "Sold", r.created_date,
        r.voucher_no, r.value, r.total_amount,
      ].map(escape).join(","));
    });
    const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `unbarcoded-stock-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Unbarcoded Stock Report</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={exportCsv} disabled={!rows.length}>
            <Download className="h-4 w-4 mr-1" /> Export CSV
          </Button>
        </div>
      </div>

      <div className="border rounded-md p-4 bg-card">
        <div className="flex items-center gap-2 mb-3 text-sm font-medium">
          <Filter className="h-4 w-4" /> Filters
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <Label className="text-xs">From Date</Label>
            <Input
              type="date"
              value={filters.date_from}
              onChange={(e) => update("date_from")(e.target.value)}
            />
          </div>
          <div>
            <Label className="text-xs">To Date</Label>
            <Input
              type="date"
              value={filters.date_to}
              onChange={(e) => update("date_to")(e.target.value)}
            />
          </div>

          <div>
            <Label className="text-xs">Stock Status</Label>
            <Select
              value={filters.stk_status}
              onValueChange={update("stk_status")}
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="active">In Stock (Active)</SelectItem>
                <SelectItem value="sold">Sold / Out</SelectItem>
                <SelectItem value="all">All</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs">Item</Label>
            <Select value={filters.item || "all"} onValueChange={(v) => update("item")(v === "all" ? "" : v)}>
              <SelectTrigger><SelectValue placeholder="All items" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All items</SelectItem>
                {items.map((it) => (
                  <SelectItem key={it.id} value={String(it.id)}>
                    {it.item_name || it.short_code}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs">Purity</Label>
            <Select value={filters.purity || "all"} onValueChange={(v) => update("purity")(v === "all" ? "" : v)}>
              <SelectTrigger><SelectValue placeholder="All purities" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All purities</SelectItem>
                {purities.map((p) => (
                  <SelectItem key={p.id} value={String(p.id)}>{p.purity}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs">Karigar</Label>
            <Select value={filters.kr_code || "all"} onValueChange={(v) => update("kr_code")(v === "all" ? "" : v)}>
              <SelectTrigger><SelectValue placeholder="All karigars" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All karigars</SelectItem>
                {karigars.map((k) => (
                  <SelectItem key={k.id} value={String(k.id)}>
                    {k.ac_name || k.name || `#${k.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs">Metal Color</Label>
            <Select value={filters.metal_color || "all"} onValueChange={(v) => update("metal_color")(v === "all" ? "" : v)}>
              <SelectTrigger><SelectValue placeholder="Any" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Any</SelectItem>
                {METAL_COLORS.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <Label className="text-xs">Design Code</Label>
            <Input
              value={filters.design_code}
              onChange={(e) => update("design_code")(e.target.value)}
              placeholder="Contains�"
            />
          </div>

          <div>
            <Label className="text-xs">Label / Tag</Label>
            <Input
              value={filters.label}
              onChange={(e) => update("label")(e.target.value)}
              placeholder="Contains�"
            />
          </div>

          <div>
            <Label className="text-xs">Gross Wt Min</Label>
            <Input
              type="number"
              step="0.001"
              value={filters.gw_min}
              onChange={(e) => update("gw_min")(e.target.value)}
            />
          </div>
          <div>
            <Label className="text-xs">Gross Wt Max</Label>
            <Input
              type="number"
              step="0.001"
              value={filters.gw_max}
              onChange={(e) => update("gw_max")(e.target.value)}
            />
          </div>
          <div>
            <Label className="text-xs">Net Wt Min</Label>
            <Input
              type="number"
              step="0.001"
              value={filters.nw_min}
              onChange={(e) => update("nw_min")(e.target.value)}
            />
          </div>
          <div>
            <Label className="text-xs">Net Wt Max</Label>
            <Input
              type="number"
              step="0.001"
              value={filters.nw_max}
              onChange={(e) => update("nw_max")(e.target.value)}
            />
          </div>
        </div>

        <div className="mt-4">
          <Label className="text-xs">Source (Created From)</Label>
          <div className="flex flex-wrap gap-2 mt-1">
            {SOURCE_CHOICES.map((s) => {
              const active = filters.source.includes(s.code);
              return (
                <button
                  type="button"
                  key={s.code}
                  onClick={() => toggleSource(s.code)}
                  className={`px-3 py-1 rounded-full text-xs border ${
                    active
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background border-input hover:bg-muted"
                  }`}
                >
                  {s.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <Button variant="ghost" onClick={resetFilters}>
            <X className="h-4 w-4 mr-1" /> Reset
          </Button>
          <Button onClick={fetchData} disabled={loading}>
            {loading ? "Loading�" : "Apply"}
          </Button>
        </div>
      </div>

      {error && (
        <div className="border border-destructive/40 bg-destructive/10 text-destructive text-sm p-2 rounded">
          {error}
        </div>
      )}

      <div className="border rounded-md bg-card">
        <div className="flex flex-wrap items-center gap-4 p-3 border-b text-sm">
          <span><b>Rows:</b> {totals.count}</span>
          <span><b>Pcs:</b> {totals.pcs}</span>
          <span><b>Gross Wt:</b> {Number(totals.gw || 0).toFixed(3)}</span>
          <span><b>Net Wt:</b> {Number(totals.nw || 0).toFixed(3)}</span>
          <span><b>Value:</b> ₹ {Number(totals.value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40">
              <tr className="text-left">
                <th className="p-2">Date</th>
                <th className="p-2">Label</th>
                <th className="p-2">Item</th>
                <th className="p-2">Purity</th>
                <th className="p-2 text-right">Pcs</th>
                <th className="p-2 text-right">GW</th>
                <th className="p-2 text-right">NW</th>
                <th className="p-2">HUID</th>
                <th className="p-2">Design</th>
                <th className="p-2">Karigar</th>
                <th className="p-2">Order</th>
                <th className="p-2">Color</th>
                <th className="p-2">Source</th>
                <th className="p-2">Status</th>
                <th className="p-2 text-right">Total</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    <td className="p-2" colSpan={15}>
                      <Skeleton className="h-5 w-full" />
                    </td>
                  </tr>
                ))
              ) : rows.length === 0 ? (
                <tr>
                  <td className="p-6 text-center text-muted-foreground" colSpan={15}>
                    No unbarcoded stock matched the selected filters.
                  </td>
                </tr>
              ) : (
                rows.map((r) => (
                  <tr key={r.id} className="border-t">
                    <td className="p-2 whitespace-nowrap">{r.created_date}</td>
                    <td className="p-2">{r.label}</td>
                    <td className="p-2">{r.item_name}</td>
                    <td className="p-2">{r.purity}</td>
                    <td className="p-2 text-right">{r.pcs}</td>
                    <td className="p-2 text-right">{Number(r.gw).toFixed(3)}</td>
                    <td className="p-2 text-right">{Number(r.nw).toFixed(3)}</td>
                    <td className="p-2">{r.huid || ""}</td>
                    <td className="p-2">{r.design_code || ""}</td>
                    <td className="p-2">{r.kr_code_name || ""}</td>
                    <td className="p-2">{r.customer_order_no || ""}</td>
                    <td className="p-2">{r.metal_color || ""}</td>
                    <td className="p-2">{r.source_label || ""}</td>
                    <td className="p-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          r.stk_status
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-rose-100 text-rose-700"
                        }`}
                      >
                        {r.stk_status ? "In Stock" : "Sold"}
                      </span>
                    </td>
                    <td className="p-2 text-right">
                      {Number(r.total_amount || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
