import React, { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, Search, SlidersHorizontal } from "lucide-react";
import apiClient from "@/services/apiClient";
import { fetchPacketWiseStoneReportAPI } from "@/services/apiService";

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
    const [packetData, setPacketData] = useState([]);
    const [itemData, setItemData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [packetsLoading, setPacketsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [searched, setSearched] = useState(false);

    const [fromDate, setFromDate] = useState(fyStart);
    const [toDate, setToDate] = useState(today);
    const [selectedItems, setSelectedItems] = useState([]); // [] means all
    const [selectedPackets, setSelectedPackets] = useState([]); // [] means all

    // Load Type S items once
    useEffect(() => {
        apiClient.get("/mastersconfig/api/item/?item_type=S&page_size=500")
            .then((res) => {
                const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
                setItemData(list);
            }).catch(() => setItemData([]));
    }, []);

    // Reload packets whenever item selection changes
    useEffect(() => {
        setPacketsLoading(true);
        const url = selectedItems.length
            ? `/mastersconfig/api/packet/?item_ids=${selectedItems.join(',')}`
            : `/mastersconfig/api/packet/`;
        apiClient.get(url)
            .then((res) => {
                const list = Array.isArray(res.data) ? res.data : (res.data?.results ?? []);
                setPacketData(list);
                // Drop selected packets that are no longer in scope
                setSelectedPackets((prev) => prev.filter((id) => list.some((p) => p.id === id)));
            })
            .catch(() => setPacketData([]))
            .finally(() => setPacketsLoading(false));
    }, [selectedItems]);

    const toggleItem = (id) => {
        setSelectedItems((prev) =>
            prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
        );
    };
    const togglePacket = (id) => {
        setSelectedPackets((prev) =>
            prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
        );
    };
    const toggleAllItems = (checked) =>
        setSelectedItems(checked ? itemData.map((i) => i.id) : []);
    const toggleAllPackets = (checked) =>
        setSelectedPackets(checked ? packetData.map((p) => p.id) : []);

    const handleSearch = useCallback(async () => {
        setLoading(true);
        setError(null);
        const p = {
            from_date: fromDate,
            to_date: toDate,
            packet_ids: selectedPackets,
            item_ids: selectedItems,
        };
        const res = await fetchPacketWiseStoneReportAPI(p);
        if (res.success) { setData(res.data); setSearched(true); }
        else setError(res.error || "Failed to fetch data");
        setLoading(false);
    }, [fromDate, toDate, selectedPackets, selectedItems]);

    const hasTransactions = (p) =>
        p.purchase?.length || p.purchase_return?.length || p.sales?.length ||
        p.stone_receive?.length || p.stone_issue?.length || p.opening_quantity > 0;

    const calcClosing = (row) => ({
        pcs: Math.max(0, row.opening.pcs + row.purchase_approval.pcs + row.purchase.pcs + row.receive.pcs - row.issue.pcs - row.sale.pcs - row.purchase_return.pcs),
        weight: Math.max(0, row.opening.weight + row.purchase_approval.weight + row.purchase.weight + row.receive.weight - row.issue.weight - row.sale.weight - row.purchase_return.weight),
    });

    const processPacketData = (packets) => {
        return packets.filter(hasTransactions).map((packet) => {
            const transactions = [];
            const push = (arr, type, dateFn, pcsFn, wFn) =>
                arr?.forEach((item) => transactions.push({
                    date: dateFn(item), type,
                    pcs: pcsFn(item), weight: wFn(item),
                }));
            push(packet.purchase, 'purchase', i => i.date, i => i.pcs || 0, i => i.ct || 0);
            push(packet.purchase_return, 'purchase_return', i => i.date, i => i.pcs || 0, i => i.ct || 0);
            push(packet.sales, 'sale', i => i.date, i => i.pcs || 0, i => i.ct || 0);
            push(packet.stone_receive, 'receive', i => i.date, i => i.return_pcs || 0, i => i.return_ct || 0);
            push(packet.stone_issue, 'issue', i => i.date, i => i.pcs || 0, i => i.ct || 0);

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
            const dateTransactions = sorted.map((date) => {
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
    const TD = ({ children, className = "", colSpan }) => (
        <td colSpan={colSpan} className={`px-2 py-1.5 text-xs text-center border-b border-border ${className}`}>{children}</td>
    );

    const COLS = ["Opening","Purchase Appr.","Purchase","Receive","Issue","Sale","Purch. Return","Closing"];
    const allItemsChecked = itemData.length > 0 && selectedItems.length === itemData.length;
    const allPacketsChecked = packetData.length > 0 && selectedPackets.length === packetData.length;
    const processed = processPacketData(data);

    return (
        <div className="flex flex-col gap-5">
            {/* Filters panel */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-muted/30">
                    <SlidersHorizontal className="size-4 text-primary" />
                    <span className="text-sm font-semibold">Filters</span>
                </div>
                <div className="p-4">
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        {/* Item filter (Type S) */}
                        <div className="flex flex-col gap-1">
                            <Label className="text-xs font-medium">
                                Items (Type S) <span className="text-muted-foreground">— {selectedItems.length || "all"}</span>
                            </Label>
                            <div className="border border-border rounded-lg max-h-44 overflow-y-auto bg-background p-2 space-y-1.5">
                                <div className="flex items-center gap-2">
                                    <Checkbox checked={allItemsChecked} onCheckedChange={(c) => toggleAllItems(!!c)} />
                                    <label className="text-xs font-medium">All</label>
                                </div>
                                {itemData.map((item) => (
                                    <div key={item.id} className="flex items-center gap-2">
                                        <Checkbox
                                            checked={selectedItems.includes(item.id)}
                                            onCheckedChange={() => toggleItem(item.id)}
                                        />
                                        <label className="text-xs truncate">{item.short_code || item.item_name}</label>
                                    </div>
                                ))}
                                {itemData.length === 0 && (
                                    <div className="text-xs text-muted-foreground italic">No Type S items.</div>
                                )}
                            </div>
                        </div>

                        {/* Packet filter (filtered by selected items) */}
                        <div className="flex flex-col gap-1">
                            <Label className="text-xs font-medium">
                                Packets <span className="text-muted-foreground">— {selectedPackets.length || "all"}</span>
                            </Label>
                            <div className="border border-border rounded-lg max-h-44 overflow-y-auto bg-background p-2 space-y-1.5">
                                {packetsLoading && (
                                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                        <Loader2 className="size-3 animate-spin" /> Loading…
                                    </div>
                                )}
                                {!packetsLoading && (
                                    <>
                                        <div className="flex items-center gap-2">
                                            <Checkbox checked={allPacketsChecked} onCheckedChange={(c) => toggleAllPackets(!!c)} />
                                            <label className="text-xs font-medium">All</label>
                                        </div>
                                        {packetData.map((pkt) => (
                                            <div key={pkt.id} className="flex items-center gap-2">
                                                <Checkbox
                                                    checked={selectedPackets.includes(pkt.id)}
                                                    onCheckedChange={() => togglePacket(pkt.id)}
                                                />
                                                <label className="text-xs truncate">{pkt.pckt_no || pkt.name}</label>
                                            </div>
                                        ))}
                                        {packetData.length === 0 && (
                                            <div className="text-xs text-muted-foreground italic">
                                                {selectedItems.length ? "No packets for selected items." : "No packets."}
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>

                        {/* Dates + search */}
                        <div className="md:col-span-2 flex flex-col gap-3">
                            <div className="flex flex-wrap gap-3 items-end">
                                <div className="flex flex-col gap-1">
                                    <Label className="text-xs">From Date</Label>
                                    <Input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="h-9 text-sm w-40" />
                                </div>
                                <div className="flex flex-col gap-1">
                                    <Label className="text-xs">To Date</Label>
                                    <Input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="h-9 text-sm w-40" />
                                </div>
                            </div>
                            <Button onClick={handleSearch} disabled={loading} className="bg-primary hover:bg-primary text-white h-9 self-start">
                                {loading ? <Loader2 className="size-4 mr-1.5 animate-spin" /> : <Search className="size-4 mr-1.5" />}
                                {loading ? "Loading..." : "Search"}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>

            {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div>
            )}

            {/* Table */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="flex items-center justify-between px-5 py-3 border-b border-border bg-muted/30">
                    <div className="text-sm font-semibold">
                        Packet Wise Stone Report
                        {searched && <span className="ml-2 text-xs font-normal text-muted-foreground">{fromDate} — {toDate}</span>}
                    </div>
                    <span className="text-xs text-muted-foreground">{processed.length} packets</span>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-muted/50 border-b-2 border-border">
                            <tr>
                                <TH>Date</TH>
                                {COLS.map((c) => <TH key={c} colSpan={2}>{c}</TH>)}
                            </tr>
                            <tr className="border-b border-border">
                                <TH></TH>
                                {COLS.map((c) => (
                                    <React.Fragment key={c}>
                                        <TH>Pcs</TH><TH>Ct</TH>
                                    </React.Fragment>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {!searched && !loading && (
                                <tr><TD colSpan={17} className="py-12 text-muted-foreground border-b-0">Use the filters above and click Search.</TD></tr>
                            )}
                            {loading && (
                                <tr><TD colSpan={17} className="py-12 border-b-0"><Loader2 className="size-5 animate-spin text-primary mx-auto" /></TD></tr>
                            )}
                            {searched && !loading && processed.length === 0 && (
                                <tr><TD colSpan={17} className="py-12 text-muted-foreground border-b-0">No data found.</TD></tr>
                            )}
                            {!loading && processed.map((pd, pi) => (
                                <React.Fragment key={pd.packet.id || pi}>
                                    <tr className="bg-violet-50 border-b border-violet-200">
                                        <td colSpan={17} className="px-3 py-1.5 text-xs font-semibold text-primary">
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
