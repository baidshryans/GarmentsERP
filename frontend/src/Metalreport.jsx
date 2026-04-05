import React, { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2, Search, SlidersHorizontal } from "lucide-react";
import apiClient from "@/services/apiClient";

async function fetchMetalReport(params = {}) {
    try {
        const q = new URLSearchParams();
        if (params.date) q.append('date', params.date);
        if (params.to_date) q.append('to_date', params.to_date);
        if (params.ledger_ids?.length) q.append('ledger_ids', params.ledger_ids.join(','));
        if (params.purity_ids?.length) q.append('purity_ids', params.purity_ids.join(','));
        if (params.report_type) q.append('report_type', params.report_type);
        const url = `/manufacturing/api/metalreport${q.toString() ? '?' + q.toString() : ''}`;
        const res = await apiClient.get(url);
        return { success: true, data: res.data };
    } catch (e) {
        return { success: false, data: [], error: e.message };
    }
}

async function fetchKarigarLedgers(search = "") {
    try {
        const q = search ? `?search=${encodeURIComponent(search)}&type=KR` : `?type=KR`;
        const res = await apiClient.get(`/contacts/api/ledger/${q}`);
        return (res.data.results ?? res.data) || [];
    } catch {
        return [];
    }
}

async function fetchPurities() {
    try {
        const res = await apiClient.get('/goldrates/api/purity/');
        return res.data || [];
    } catch {
        return [];
    }
}

function fmtDate(d) {
    if (!d) return '';
    return new Date(d).toLocaleDateString('en-IN');
}

const today = new Date().toISOString().split('T')[0];
const fyStart = (() => {
    const now = new Date();
    const yr = now.getMonth() < 3 ? now.getFullYear() - 1 : now.getFullYear();
    return `${yr}-04-01`;
})();

const TH = ({ children, className = "" }) => (
    <th className={`px-3 py-2 text-left text-xs font-semibold text-muted-foreground whitespace-nowrap border-b border-border ${className}`}>
        {children}
    </th>
);
const TD = ({ children, className = "" }) => (
    <td className={`px-3 py-2 text-sm border-b border-border ${className}`}>{children}</td>
);

export default function KarigarMetalLedger() {
    const [data, setData] = useState([]);
    const [ledgers, setLedgers] = useState([]);
    const [filteredLedgers, setFilteredLedgers] = useState([]);
    const [purities, setPurities] = useState([]);
    const [searchTerm, setSearchTerm] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [searched, setSearched] = useState(false);
    const [filters, setFilters] = useState({
        karigar: { all: true, selected: [] },
        purity: { all: true, selected: [] },
        fromDate: fyStart,
        toDate: today,
        reportType: "Main",
    });

    useEffect(() => {
        fetchKarigarLedgers().then(ls => {
            setLedgers(ls);
            setFilteredLedgers(ls);
            setFilters(f => ({ ...f, karigar: { all: true, selected: ls.map(l => l.id) } }));
        });
        fetchPurities().then(ps => {
            setPurities(ps);
            setFilters(f => ({ ...f, purity: { all: true, selected: ps.map(p => p.purity) } }));
        });
    }, []);

    useEffect(() => {
        const t = setTimeout(async () => {
            const ls = await fetchKarigarLedgers(searchTerm);
            setFilteredLedgers(ls);
        }, 300);
        return () => clearTimeout(t);
    }, [searchTerm]);

    const handleKarigar = (id, checked) => {
        if (id === 'all') {
            setFilters(f => ({ ...f, karigar: { all: checked, selected: checked ? ledgers.map(l => l.id) : [] } }));
        } else {
            setFilters(f => {
                const sel = checked ? [...f.karigar.selected, id] : f.karigar.selected.filter(x => x !== id);
                return { ...f, karigar: { all: sel.length === ledgers.length, selected: sel } };
            });
        }
    };

    const handlePurity = (val, checked) => {
        if (val === 'all') {
            setFilters(f => ({ ...f, purity: { all: checked, selected: checked ? purities.map(p => p.purity) : [] } }));
        } else {
            setFilters(f => {
                const sel = checked ? [...f.purity.selected, val] : f.purity.selected.filter(x => x !== val);
                return { ...f, purity: { all: sel.length === purities.length, selected: sel } };
            });
        }
    };

    const handleSearch = async () => {
        setLoading(true);
        setError(null);
        const purityIds = filters.purity.all ? [] :
            filters.purity.selected.map(v => purities.find(p => p.purity === v)?.id).filter(Boolean);
        const res = await fetchMetalReport({
            date: filters.fromDate,
            to_date: filters.toDate,
            ledger_ids: filters.karigar.all ? [] : filters.karigar.selected,
            purity_ids: purityIds,
            report_type: filters.reportType.toLowerCase(),
        });
        if (res.success) { setData(res.data); setSearched(true); }
        else setError(res.error || "Failed to fetch");
        setLoading(false);
    };

    return (
        <div className="flex flex-col gap-5">
            {/* Filters */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="flex items-center gap-2 px-5 py-3 border-b border-border bg-muted/30">
                    <SlidersHorizontal className="size-4 text-violet-600" />
                    <span className="text-sm font-semibold">Filters</span>
                    {searched && (
                        <span className="ml-auto text-xs text-muted-foreground">
                            {filters.fromDate} — {filters.toDate} · {filters.reportType}
                        </span>
                    )}
                </div>
                <div className="p-4 grid grid-cols-1 md:grid-cols-4 gap-4">
                    {/* Karigar */}
                    <div className="flex flex-col gap-1">
                        <Label className="text-xs font-medium">Karigar</Label>
                        <div className="border border-border rounded-lg bg-background max-h-44 overflow-y-auto p-2 space-y-1.5">
                            <div className="flex items-center gap-2">
                                <Checkbox checked={filters.karigar.all} onCheckedChange={c => handleKarigar('all', c)} />
                                <label className="text-xs">All</label>
                            </div>
                            {filteredLedgers.map(l => (
                                <div key={l.id} className="flex items-center gap-2">
                                    <Checkbox
                                        checked={filters.karigar.selected.includes(l.id)}
                                        onCheckedChange={c => handleKarigar(l.id, c)}
                                    />
                                    <label className="text-xs truncate">{l.ac_name}</label>
                                </div>
                            ))}
                        </div>
                        <Input
                            placeholder="Search karigar..."
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                            className="h-8 text-xs mt-1"
                        />
                    </div>

                    {/* Purity */}
                    <div className="flex flex-col gap-1">
                        <Label className="text-xs font-medium">Purity</Label>
                        <div className="border border-border rounded-lg bg-background max-h-44 overflow-y-auto p-2 space-y-1.5">
                            <div className="flex items-center gap-2">
                                <Checkbox checked={filters.purity.all} onCheckedChange={c => handlePurity('all', c)} />
                                <label className="text-xs">All</label>
                            </div>
                            {purities.map(p => (
                                <div key={p.id} className="flex items-center gap-2">
                                    <Checkbox
                                        checked={filters.purity.selected.includes(p.purity)}
                                        onCheckedChange={c => handlePurity(p.purity, c)}
                                    />
                                    <label className="text-xs">{p.purity}K</label>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Date + type */}
                    <div className="md:col-span-2 flex flex-col gap-3">
                        <div className="grid grid-cols-2 gap-3">
                            <div className="flex flex-col gap-1">
                                <Label className="text-xs">From Date</Label>
                                <Input type="date" value={filters.fromDate} onChange={e => setFilters(f => ({...f, fromDate: e.target.value}))} className="h-9 text-sm" />
                            </div>
                            <div className="flex flex-col gap-1">
                                <Label className="text-xs">To Date</Label>
                                <Input type="date" value={filters.toDate} onChange={e => setFilters(f => ({...f, toDate: e.target.value}))} className="h-9 text-sm" />
                            </div>
                        </div>
                        <div className="flex gap-4">
                            {["Main","Sample"].map(t => (
                                <label key={t} className="flex items-center gap-1.5 text-sm cursor-pointer">
                                    <input type="radio" name="rtype" checked={filters.reportType === t}
                                        onChange={() => setFilters(f => ({...f, reportType: t}))} className="accent-violet-600" />
                                    {t}
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

            {/* Error */}
            {error && (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div>
            )}

            {/* Table */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-border bg-muted/30 text-sm font-semibold">
                    Karigar Metal Ledger ({filters.reportType})
                    {!filters.purity.all && (
                        <span className="ml-2 text-xs font-normal text-muted-foreground">
                            Purity: {filters.purity.selected.join(', ')}
                        </span>
                    )}
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-muted/50">
                            <tr>
                                <TH>Vou Date</TH>
                                <TH>Vou No.</TH>
                                <TH>Description</TH>
                                <TH className="text-right">Issue</TH>
                                <TH className="text-right">Receive</TH>
                                <TH className="text-right">Add</TH>
                                <TH className="text-right">Wastage</TH>
                                <TH className="text-right">Balance</TH>
                                <TH className="text-right">Fine Wt</TH>
                                <TH className="text-right">Fine Bal</TH>
                            </tr>
                        </thead>
                        <tbody>
                            {!searched && !loading && (
                                <tr><TD colSpan={10} className="text-center py-12 text-muted-foreground text-sm border-b-0">Select filters and click Search.</TD></tr>
                            )}
                            {loading && (
                                <tr><TD colSpan={10} className="text-center py-12 border-b-0"><Loader2 className="size-5 animate-spin text-violet-500 mx-auto" /></TD></tr>
                            )}
                            {searched && !loading && data.length === 0 && (
                                <tr><TD colSpan={10} className="text-center py-12 text-muted-foreground text-sm border-b-0">No data found.</TD></tr>
                            )}
                            {!loading && data.map((karigar) => (
                                <React.Fragment key={karigar.id}>
                                    {Object.entries(karigar.per_purity).map(([purity, purityData]) => {
                                        if (!filters.purity.all && !filters.purity.selected.includes(purity)) return null;
                                        const txns = [];
                                        purityData.karigar_gold_issues_after_date?.forEach(issue =>
                                            issue.issues?.forEach(item => txns.push({
                                                type: 'issue', date: issue.date1, billno: issue.billno,
                                                conv_wt: item.conv_wt || 0, net_wt: 0, add_wt: 0, wastage: 0,
                                            }))
                                        );
                                        purityData.karigar_receive_items_after_date?.forEach(recv =>
                                            recv.items?.forEach(item => txns.push({
                                                type: 'receive', date: recv.date1, billno: recv.receive_slip_no,
                                                conv_wt: 0, net_wt: item.nw || 0, add_wt: item.add_gw || 0, wastage: item.wastage || 0,
                                            }))
                                        );
                                        txns.sort((a, b) => new Date(a.date) - new Date(b.date));
                                        let bal = purityData.opening_gold_stock;
                                        const pur = parseFloat(purity) / 1000;

                                        return (
                                            <React.Fragment key={`${karigar.id}-${purity}`}>
                                                {/* Karigar + purity header */}
                                                <tr className="bg-violet-50 border-b border-violet-200">
                                                    <td colSpan={10} className="px-3 py-1.5 text-xs font-semibold text-violet-800">
                                                        {karigar.ac_name} — {purity}K
                                                    </td>
                                                </tr>
                                                {/* Opening row */}
                                                <tr className="bg-muted/20">
                                                    <TD>{fmtDate(filters.fromDate)}</TD>
                                                    <TD></TD>
                                                    <TD className="text-muted-foreground italic">Opening Balance as on date</TD>
                                                    <TD className="text-right"></TD>
                                                    <TD className="text-right"></TD>
                                                    <TD className="text-right"></TD>
                                                    <TD className="text-right"></TD>
                                                    <TD className="text-right font-mono text-xs">{purityData.opening_gold_stock.toFixed(3)}</TD>
                                                    <TD className="text-right font-mono text-xs">{(purityData.opening_gold_stock * pur).toFixed(3)}</TD>
                                                    <TD className="text-right font-mono text-xs">{(purityData.opening_gold_stock * pur).toFixed(3)}</TD>
                                                </tr>
                                                {/* Transactions */}
                                                {txns.map((t, ti) => {
                                                    const isIssue = t.type === 'issue';
                                                    if (isIssue) bal += t.conv_wt;
                                                    else bal = bal - t.net_wt - t.wastage + t.add_wt;
                                                    return (
                                                        <tr key={ti} className="hover:bg-muted/20 transition-colors">
                                                            <TD className="whitespace-nowrap">{fmtDate(t.date)}</TD>
                                                            <TD className="font-mono text-xs">{t.billno}</TD>
                                                            <TD>{isIssue ? 'Issue to Karigar' : 'Receive from Karigar'}</TD>
                                                            <TD className="text-right font-mono text-xs">{isIssue ? t.conv_wt.toFixed(3) : ""}</TD>
                                                            <TD className="text-right font-mono text-xs">{!isIssue ? t.net_wt.toFixed(3) : ""}</TD>
                                                            <TD className="text-right font-mono text-xs">{!isIssue ? t.add_wt.toFixed(3) : ""}</TD>
                                                            <TD className="text-right font-mono text-xs">{!isIssue ? t.wastage.toFixed(3) : ""}</TD>
                                                            <TD className="text-right font-mono text-xs">{bal.toFixed(3)}</TD>
                                                            <TD className="text-right font-mono text-xs">{isIssue ? (t.conv_wt * pur).toFixed(3) : (t.net_wt * pur).toFixed(3)}</TD>
                                                            <TD className="text-right font-mono text-xs">{(bal * pur).toFixed(3)}</TD>
                                                        </tr>
                                                    );
                                                })}
                                            </React.Fragment>
                                        );
                                    })}
                                    {/* Karigar total row */}
                                    <tr className="bg-muted/50 font-semibold border-t-2 border-border">
                                        <td colSpan={3} className="px-3 py-2 text-xs text-right text-muted-foreground">
                                            {karigar.ac_name} — Total Fine Weight
                                        </td>
                                        {[...Array(7)].map((_, i) => <td key={i} />)}
                                    </tr>
                                </React.Fragment>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
