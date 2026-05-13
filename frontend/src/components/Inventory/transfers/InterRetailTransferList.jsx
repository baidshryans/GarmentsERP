import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, Eye, Loader2 } from "lucide-react";
import { fetchInterRetailTransfers, fetchRetails } from "@/services/apiService";

const STATUS_STYLES = {
  draft:      "bg-muted text-muted-foreground",
  in_transit: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  received:   "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  cancelled:  "bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300",
};

const StatusBadge = ({ status }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium uppercase tracking-wide ${STATUS_STYLES[status] || "bg-muted"}`}>
    {status}
  </span>
);

const fmt = (v) => Number(v || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function InterRetailTransferList() {
  const [vouchers, setVouchers] = useState([]);
  const [retails, setRetails] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({ status: "", from_retail: "", to_retail: "", date_from: "", date_to: "" });

  const retailById = useMemo(() => Object.fromEntries(retails.map((r) => [r.id, r])), [retails]);

  useEffect(() => {
    fetchRetails().then((res) => {
      if (res.success) setRetails(res.data?.results || res.data || []);
    });
  }, []);

  const load = async () => {
    setLoading(true);
    const res = await fetchInterRetailTransfers(filters);
    setVouchers(res.success ? (res.data?.results || res.data || []) : []);
    setLoading(false);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Inter-Retail Transfers</h2>
        <Link to="/inventory/inter-retail-transfer/new">
          <Button size="sm" className="gap-1.5"><Plus className="size-4" /> New Transfer</Button>
        </Link>
      </div>

      <div className="flex flex-wrap gap-3 items-end p-3 rounded-lg border border-border bg-muted/20">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Status</Label>
          <select
            value={filters.status}
            onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
            className="h-9 rounded-md border border-border bg-background px-2 text-sm"
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="in_transit">In Transit</option>
            <option value="received">Received</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Retail</Label>
          <select
            value={filters.from_retail}
            onChange={(e) => setFilters((f) => ({ ...f, from_retail: e.target.value }))}
            className="h-9 rounded-md border border-border bg-background px-2 text-sm"
          >
            <option value="">Any</option>
            {retails.map((r) => <option key={r.id} value={r.id}>{r.retail_name}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Retail</Label>
          <select
            value={filters.to_retail}
            onChange={(e) => setFilters((f) => ({ ...f, to_retail: e.target.value }))}
            className="h-9 rounded-md border border-border bg-background px-2 text-sm"
          >
            <option value="">Any</option>
            {retails.map((r) => <option key={r.id} value={r.id}>{r.retail_name}</option>)}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From Date</Label>
          <Input type="date" value={filters.date_from} onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value }))} className="h-9 w-40" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To Date</Label>
          <Input type="date" value={filters.date_to} onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value }))} className="h-9 w-40" />
        </div>
        <Button size="sm" onClick={load} disabled={loading} className="h-9">
          {loading ? <Loader2 className="size-4 animate-spin" /> : "Apply"}
        </Button>
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left">Voucher #</th>
              <th className="px-3 py-2 text-left">Date</th>
              <th className="px-3 py-2 text-left">From</th>
              <th className="px-3 py-2 text-left">To</th>
              <th className="px-3 py-2 text-right">Items</th>
              <th className="px-3 py-2 text-right">Value (₹)</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {vouchers.length === 0 && (
              <tr><td colSpan={8} className="px-3 py-6 text-center text-muted-foreground text-sm">
                {loading ? "Loading�" : "No transfers found."}
              </td></tr>
            )}
            {vouchers.map((v) => {
              const itemCount = v.items?.length || 0;
              const totalValue = (v.items || []).reduce((s, it) => s + Number(it.transfer_value || 0), 0);
              return (
                <tr key={v.id} className="hover:bg-muted/20">
                  <td className="px-3 py-2 font-mono text-xs">{v.voucher_no}</td>
                  <td className="px-3 py-2">{v.transfer_date}</td>
                  <td className="px-3 py-2">{v.from_retail_name || retailById[v.from_retail]?.retail_name || v.from_retail}</td>
                  <td className="px-3 py-2">{v.to_retail_name || retailById[v.to_retail]?.retail_name || v.to_retail}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{itemCount}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{fmt(totalValue)}</td>
                  <td className="px-3 py-2"><StatusBadge status={v.status} /></td>
                  <td className="px-3 py-2 text-right">
                    <Link to={`/inventory/inter-retail-transfer/${v.id}`}>
                      <Button size="sm" variant="outline" className="h-7 gap-1"><Eye className="size-3.5" />View</Button>
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
