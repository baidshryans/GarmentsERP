import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Search, Download, SlidersHorizontal } from "lucide-react";
import {
    fetchPacketWiseStoneReportAPI,
    fetchPacketDataAPI,
    fetchItemDataAPI
} from "@/services/apiService";

function formatDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-IN");
}

const today = new Date().toISOString().split("T")[0];
const fyStart = (() => {
    const now = new Date();
    const yr = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
    return `${yr}-04-01`;
})();

export default function PacketWiseStoneReport() {
    const [data, setData] = useState([]);
    const [filteredData, setFilteredData] = useState([]);
    const [packetData, setPacketData] = useState([]);
    const [itemData, setItemData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [searched, setSearched] = useState(false);
    const [filters, setFilters] = useState({
        packet: { all: true, selected: [] },
        item: { all: true, selected: [] },
        fromDate: fyStart,
        toDate: today,
        reportFormat: "CT"
    });

    useEffect(() => {
        const load = async () => {
            const [pr, ir] = await Promise.all([fetchPacketDataAPI(), fetchItemDataAPI()]);
            if (pr.success) {
                setPacketData(pr.data);
                setFilters(f => ({ ...f, packet: { all: true, selected: pr.data.map(p => p.id) } }));
            }
            if (ir.success) {
                setItemData(ir.data);
                setFilters(f => ({ ...f, item: { all: true, selected: ir.data.map(i => i.id) } }));
            }
        };
        load();
    }, []);

    const handleSearch = async () => {
        setLoading(true);
        setError(null);
        const toISO = (d) => d.split('/').reverse().join('-');
        const p = {
            from_date: filters.fromDate.includes('/') ? toISO(filters.fromDate) : filters.fromDate,
            to_date: filters.toDate.includes('/') ? toISO(filters.toDate) : filters.toDate,
            packet_ids: filters.packet.all ? [] : filters.packet.selected,
            item_ids: filters.item.all ? [] : filters.item.selected,
        };
        const res = await fetchPacketWiseStoneReportAPI(p);
        if (res.success) { setData(res.data); setFilteredData(res.data); setSearched(true); }
        else setError(res.error || "Failed to fetch data");
        setLoading(false);
    };

    const handleFilter = (type, id, checked) => {
        setFilters(prev => {
            const src = type === 'packet' ? packetData : itemData;
            const key = type;
            if (id === 'all') {
                return { ...prev, [key]: { all: checked, selected: checked ? src.map(x => x.id) : [] } };
            }
            const newSel = checked
                ? [...prev[key].selected, id]
                : prev[key].selected.filter(x => x !== id);
            return { ...prev, [key]: { all: newSel.length === src.length, selected: newSel } };
        });
    };

    const getW = (val, gw) => filters.reportFormat === "GW" && gw != null ? gw : val;

    const hasTransactions = (p) =>
        p.purchase?.length || p.purchase_return?.length || p.sales?.length ||
        p.stone_receive?.length || p.stone_issue?.length || p.opening_quantity > 0;

    const calcClosing = (row) => ({
        pcs: Math.max(0, row.opening.pcs + row.purchase_approval.pcs + row.purchase.pcs + row.receive.pcs - row.issue.pcs - row.sale.pcs - row.purchase_return.pcs),
        weight: Math.max(0, row.opening.weight + row.purchase_approval.weight + row.purchase.weight + row.receive.weight - row.issue.weight - row.sale.weight - row.purchase_return.weight),
    });

    const processPacketData = (packets) => {
        return packets.filter(hasTransactions).map(packet => {
            const transactions = [];
            const push = (arr, type, dateFn, pcsFn, wFn, gwFn) =>
                arr?.forEach(item => transactions.push({
                    date: dateFn(item), type,
                    pcs: pcsFn(item), weight: getW(wFn(item), gwFn ? gwFn(item) : null)
                }));
            push(packet.purchase, 'purchase', i => i.date, i => i.pcs || 0, i => i.ct || 0, i => i.gw || 0);
            push(packet.purchase_return, 'purchase_return', i => i.date, i => i.pcs || 0, i => i.ct || 0, i => i.gw || 0);
            push(packet.sales, 'sale', i => i.date, i => i.pcs || 0, i => i.ct || 0, i => i.gw || 0);
            push(packet.stone_receive, 'receive', i => i.date, i => i.return_pcs || 0, i => i.return_ct || 0, i => i.return_gw || 0);
            push(packet.stone_issue, 'issue', i => i.date, i => i.pcs || 0, i => i.ct || 0, i => i.gw || 0);

            const grouped = transactions.reduce((acc, t) => {
                const d = t.date || 'No Date';
                if (!acc[d]) acc[d] = {
                    opening: { pcs: 0, weight: 0 }, purchase_approval: { pcs: 0, weight: 0 },
                    purchase: { pcs: 0, weight: 0 }, receive: { pcs: 0, weight: 0 },
                    issue: { pcs: 0, weight: 0 }, sale: { pcs: 0, weight: 0 }, purchase_return: { pcs: 0, weight: 0 }
                };
                acc[d][t.type].pcs += t.pcs;
                acc[d][t.type].weight += t.weight;
                return acc;
            }, {});

            const sorted = Object.keys(grouped).sort((a, b) => new Date(a) - new Date(b));
            let runPcs = packet.opening_quantity || 0, runWt = packet.opening_quantity || 0;
            const dateTransactions = sorted.map(date => {
                const row = { date, ...grouped[date], opening: { pcs: runPcs, weight: runWt } };
                const c = calcClosing(row);
                runPcs = c.pcs; runWt = c.weight;
                return row;
            });
            return { packet, dateTransactions };
        });
    };

    const fmt = (v) => v ? parseFloat(v).toFixed(3) : "";

    const TH = ({ children, colSpan, className = "" }) => (
        <th colSpan={colSpan} className={`px-2 py-2 text-xs font-semibold text-muted-foreground whitespace-nowrap text-center ${className}`}>
            {children}
        </th>
    );
    const TD = ({ children, className = "" }) => (
        <td className={`px-2 py-1.5 text-xs text-center border-b border-border ${className}`}>{children}</td>
    );

    const COLS = ["Opening","Purchase Appr.","Purchase","Receive","Issue","Sale","Purch. Return","Closing"];
    const fmt_ = filters.reportFormat;

    return (
        <div className="flex flex-col gap-5">
            {/* Filters panel */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-muted/30">
                    <SlidersHorizontal className="size-4 text-violet-600" />
                    <span className="text-sm font-semibold">Filters</span>
                </div>
                <div className="p-4">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        {/* Item filter */}
                        <div className="flex flex-col gap-1">
                            <Label className="text-xs font-medium">Item</Label>
                            <div className="border border-border rounded-lg max-h-44 overflow-y-auto bg-background p-2 space-y-1.5">
                                <div className="flex items-center gap-2">
                                    <Checkbox checked={filters.item.all} onCheckedChange={c => handleFilter('item','all',c)} />
                                    <label className="text-xs">All</label>
                                </div>
                                {itemData.map(item => (
                                    <div key={item.id} className="flex items-center gap-2">
                                        <Checkbox
                                            checked={filters.item.selected.includes(item.id)}
                                            onCheckedChange={c => handleFilter('item', item.id, c)}
                                        />
                                        <label className="text-xs truncate">{item.short_code || item.item_name}</label>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Packet filter */}
                        <div className="flex flex-col gap-1">
                            <Label className="text-xs font-medium">Packet</Label>
                            <div className="border border-border rounded-lg max-h-44 overflow-y-auto bg-background p-2 space-y-1.5">
                                <div className="flex items-center gap-2">
                                    <Checkbox checked={filters.packet.all} onCheckedChange={c => handleFilter('packet','all',c)} />
                                    <label className="text-xs">All</label>
                                </div>
                                {packetData.map(pkt => (
                                    <div key={pkt.id} className="flex items-center gap-2">
                                        <Checkbox
                                            checked={filters.packet.selected.includes(pkt.id)}
                                            onCheckedChange={c => handleFilter('packet', pkt.id, c)}
                                        />
                                        <label className="text-xs truncate">{pkt.pckt_no || pkt.name}</label>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Date + format */}
                        <div className="md:col-span-2 flex flex-col gap-3">
                            <div className="flex flex-wrap gap-3 items-end">
                                <div className="flex flex-col gap-1">
                                    <Label className="text-xs">From Date</Label>
                                    <Input type="date" value={filters.fromDate} onChange={e => setFilters(f => ({...f, fromDate: e.target.value}))} className="h-9 text-sm w-40" />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label className="text-xs">To Date</Label>
                                    <Input type="date" value={filters.toDate} onChange={e => setFilters(f => ({...f, toDate: e.target.value}))} className="h-9 text-sm w-40" />
                                </div>
                            </div>
                            <div className="flex gap-4">
                                {["CT","GW"].map(fmt => (
                                    <label key={fmt} className="flex items-center gap-1.5 text-sm cursor-pointer">
                                        <input type="radio" name="fmt" checked={filters.reportFormat === fmt}
                                            onChange={() => setFilters(f => ({...f, reportFormat: fmt}))} className="accent-violet-600" />
                                        Report ({fmt})
                                    </label>
                                ))}
                            </div>
                            <Button onClick={handleSearch} disabled={loading} className="bg-violet-700 hover:bg-violet-800 text-white h-9 self-start">
                                {loading ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : <Search className="size-4 mr-1.5" />}
                                {loading ? "Loading..." : "Search"}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div>
            )}

            {/* Table */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/30">
                    <div className="text-sm font-semibold">
                        Packet Wise Stone Report
                        {searched && <span className="ml-2 text-xs font-normal text-muted-foreground">({filters.reportFormat}) · {filters.fromDate} — {filters.toDate}</span>}
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-muted/50 border-b-2 border-border">
                            <tr>
                                <TH>Date</TH>
                                {COLS.map(c => <TH key={c} colSpan={2}>{c}</TH>)}
                            </tr>
                            <tr className="border-b border-border">
                                <TH></TH>
                                {COLS.map(c => (
                                    <React.Fragment key={c}>
                                        <TH>Pcs</TH><TH>{fmt_}</TH>
                                    </React.Fragment>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {!searched && !loading && (
                                <tr><TD colSpan={17} className="py-12 text-muted-foreground border-b-0">Use the filters above and click Search.</TD></tr>
                            )}
                            {loading && (
                                <tr><TD colSpan={17} className="py-12 border-b-0"><Loader2 className="size-5 animate-spin text-violet-500 mx-auto" /></TD></tr>
                            )}
                            {searched && !loading && filteredData.length === 0 && (
                                <tr><TD colSpan={17} className="py-12 text-muted-foreground border-b-0">No data found.</TD></tr>
                            )}
                            {!loading && processPacketData(filteredData).map((pd, pi) => (
                                <React.Fragment key={pd.packet.id || pi}>
                                    {/* Packet header */}
                                    <tr className="bg-violet-50 border-b border-violet-200">
                                        <td colSpan={17} className="px-3 py-1.5 text-xs font-semibold text-violet-800">
                                            {pd.packet.pckt_no}
                                        </td>
                                    </tr>
                                    {pd.dateTransactions.map((row, ri) => {
                                        const c = calcClosing(row);
                                        const cell = (v) => <TD className="tabular-nums">{v || ""}</TD>;
                                        const wt = (v) => <TD className="tabular-nums font-mono text-xs">{fmt(v) !== "0.000" ? fmt(v) : ""}</TD>;
                                        return (
                                            <tr key={ri} className="hover:bg-muted/20 transition-colors">
                                                <TD className="whitespace-nowrap">{formatDate(row.date)}</TD>
                                                {cell(row.opening.pcs)}{wt(row.opening.weight)}
                                                {cell("")}{wt(null)}
                                                {cell(row.purchase.pcs)}{wt(row.purchase.weight)}
                                                {cell(row.receive.pcs)}{wt(row.receive.weight)}
                                                {cell(row.issue.pcs)}{wt(row.issue.weight)}
                                                {cell(row.sale.pcs)}{wt(row.sale.weight)}
                                                {cell(row.purchase_return.pcs)}{wt(row.purchase_return.weight)}
                                                {cell(c.pcs)}{wt(c.weight)}
                                            </tr>
                                        );
                                    })}
                                </React.Fragment>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
