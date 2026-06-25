import { useState, useEffect, useRef } from 'react';
import { formatNumber, formatDate } from '@/lib/format';
import { Search, Printer } from 'lucide-react';
import { fetchGSTOutputReport, fetchGstins, getFiscalYears } from "./services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { isValidDateRange } from "@/lib/dateRange";

const today = () => new Date().toISOString().slice(0, 10);

// Indian state code → full name
const STATE_NAMES = {
  AP:"Andhra Pradesh", AR:"Arunachal Pradesh", AS:"Assam", BR:"Bihar",
  CT:"Chhattisgarh", CG:"Chhattisgarh", GA:"Goa", GJ:"Gujarat",
  HR:"Haryana", HP:"Himachal Pradesh", JK:"Jammu and Kashmir",
  JH:"Jharkhand", KA:"Karnataka", KL:"Kerala", MP:"Madhya Pradesh",
  MH:"Maharashtra", MN:"Manipur", ML:"Meghalaya", MZ:"Mizoram",
  NL:"Nagaland", OR:"Odisha", OD:"Odisha", PB:"Punjab", RJ:"Rajasthan",
  SK:"Sikkim", TN:"Tamil Nadu", TG:"Telangana", TS:"Telangana",
  TR:"Tripura", UP:"Uttar Pradesh", UT:"Uttarakhand", UK:"Uttarakhand",
  WB:"West Bengal", AN:"Andaman and Nicobar Islands", CH:"Chandigarh",
  DN:"Dadra and Nagar Haveli", DD:"Daman and Diu", DL:"Delhi",
  LA:"Ladakh", LD:"Lakshadweep", PY:"Puducherry",
};
const stateName = (code) => STATE_NAMES[(code || '').toUpperCase()] || code || '—';

const GstOutputRegister = () => {
  const printRef = useRef(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState(today());
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [gstins, setGstins] = useState([]);
  const [gstinId, setGstinId] = useState('');

  useEffect(() => {
    fetchGstins().then(r => {
      if (r.success) setGstins(r.data?.results || r.data || []);
    });
    getFiscalYears().then(r => {
      if (r.success) {
        const active = (r.data?.results || r.data || []).find(fy => fy.is_active);
        if (active?.fy_start) setStartDate(active.fy_start);
      }
    });
  }, []);

  const fetchData = async () => {
    if (!isValidDateRange(startDate, endDate)) {
      setError('From date cannot be after To date.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await fetchGSTOutputReport(startDate, endDate, gstinId);
      setData(result);
    } catch (err) {
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  };

  const getMergedAndSortedData = () => {
    if (!data) return [];
    const salesVouchers = (data.salesvoucher || []).map(item => ({
      ...item,
      type: 'SALE',
      billno: item.gst_billno,
    }));
    const salesReturns = (data.salesreturn || []).map(item => ({
      ...item,
      type: 'RETURN',
      gst_billno: item.billno,
    }));
    return [...salesVouchers, ...salesReturns].sort(
      (a, b) => new Date(a.date1) - new Date(b.date1)
    );
  };

  const fmt = (v) =>
    formatNumber(v, { decimals: 2 });
  const fmt3 = (v) =>
    formatNumber(v, { decimals: 3 });
  const formatDate = (d) =>
    formatDate(d, 'numeric');

  const rows = getMergedAndSortedData();

  const totals = rows.reduce((acc, r) => ({
    billvalue:    acc.billvalue    + (Number(r.billvalue)    || 0),
    discount_amt: acc.discount_amt + (Number(r.discount_amt) || 0),
    taxableamount:acc.taxableamount+ (Number(r.taxableamount)|| 0),
    cgst_amt:     acc.cgst_amt     + (Number(r.cgst_amt)     || 0),
    sgst_amt:     acc.sgst_amt     + (Number(r.sgst_amt)     || 0),
    igst_amt:     acc.igst_amt     + (Number(r.igst_amt)     || 0),
    sale_gw:      acc.sale_gw      + (Number(r.sale_gw)      || 0),
  }), { billvalue:0, discount_amt:0, taxableamount:0, cgst_amt:0, sgst_amt:0, igst_amt:0, sale_gw:0 });

  const handlePrint = () => {
    const content = printRef.current?.innerHTML;
    if (!content) return;
    const win = window.open('', '_blank');
    win.document.write(`<!DOCTYPE html><html><head><title>GST Output Register</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 10px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 3px 5px; text-align: left; }
        th { background: #f0f0f0; font-weight: bold; }
        .tr { text-align: right; }
        tfoot tr { font-weight: bold; background: #f9f9f9; }
        h2 { font-size: 13px; margin-bottom: 6px; }
      </style></head><body>
      <h2>GST Output Register — ${startDate} to ${endDate}</h2>
      ${content}
      </body></html>`);
    win.document.close();
    win.focus();
    win.print();
    win.close();
  };

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input
            type="date" value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            max={endDate || undefined} className="h-9 w-36"
            style={{ colorScheme: 'light' }}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input
            type="date" value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            min={startDate || undefined} className="h-9 w-36"
            style={{ colorScheme: 'light' }}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">GSTIN</Label>
          <select
            value={gstinId}
            onChange={(e) => setGstinId(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          >
            <option value="">All</option>
            {gstins.map((g) => (
              <option key={g.id} value={g.id}>{g.gstin}</option>
            ))}
          </select>
        </div>
        <Button size="sm" onClick={fetchData} disabled={loading} className="h-9">
          <Search className="w-3.5 h-3.5 mr-1" />
          Show
        </Button>
        <Button size="sm" variant="outline" onClick={handlePrint} disabled={loading || !data || rows.length === 0} className="h-9">
          <Printer className="w-3.5 h-3.5 mr-1" />
          Print
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-9 w-full" />)}
        </div>
      )}

      {!loading && !data && (
        <div className="text-center py-16 text-sm text-muted-foreground">
          Select a date range and click <strong>Show</strong> to load the register.
        </div>
      )}

      {!loading && data && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between text-sm text-muted-foreground px-1">
            <span>{rows.length} transaction(s) — {formatDate(startDate)} to {formatDate(endDate)}</span>
          </div>

          <div className="rounded-lg border border-border overflow-hidden" ref={printRef}>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">Date</th>
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">Type</th>
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">GST Bill No</th>
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">Party Name</th>
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">GSTIN</th>
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">PAN</th>
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">HSN</th>
                    <th className="px-2 py-2 text-right font-semibold border-r border-border">Sale Wt</th>
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">UOM</th>
                    <th className="px-2 py-2 text-right font-semibold border-r border-border">Taxable Amt</th>
                    <th className="px-2 py-2 text-right font-semibold border-r border-border">Discount</th>
                    <th className="px-2 py-2 text-right font-semibold border-r border-border">CGST</th>
                    <th className="px-2 py-2 text-right font-semibold border-r border-border">SGST</th>
                    <th className="px-2 py-2 text-right font-semibold border-r border-border">IGST</th>
                    <th className="px-2 py-2 text-right font-semibold border-r border-border">Bill Value</th>
                    <th className="px-2 py-2 text-left font-semibold border-r border-border">Place of Supply</th>
                    <th className="px-2 py-2 text-right font-semibold">Add/Less</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan="17" className="px-3 py-10 text-center text-muted-foreground">
                        No data available for the selected date range.
                      </td>
                    </tr>
                  ) : rows.map((item, index) => (
                    <tr
                      key={index}
                      className={`border-t border-border/50 hover:bg-accent/30 transition-colors ${
                        index % 2 === 1 ? 'bg-muted/20' : ''
                      }`}
                    >
                      <td className="px-2 py-1.5 border-r border-border/50 whitespace-nowrap">{formatDate(item.date1)}</td>
                      <td className="px-2 py-1.5 border-r border-border/50">
                        <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                          item.type === 'SALE'
                            ? 'bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            : 'bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        }`}>
                          {item.type === 'SALE' ? 'TAX INVOICE' : 'CREDIT NOTE'}
                        </span>
                      </td>
                      <td className="px-2 py-1.5 border-r border-border/50 font-mono text-xs">{item.gst_billno || item.billno || '—'}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 max-w-36 truncate">{item.partyname}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 font-mono text-xs">{item.gstin || '—'}</td>
                      <td className="px-2 py-1.5 border-r border-border/50">{item.pan || '—'}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 font-mono">{item.hsn || '—'}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 text-right tabular-nums">{item.sale_gw ? fmt3(item.sale_gw) : '—'}</td>
                      <td className="px-2 py-1.5 border-r border-border/50">{item.uom || '—'}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 text-right tabular-nums">{fmt(item.taxableamount)}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 text-right tabular-nums">{item.discount_amt ? fmt(item.discount_amt) : '—'}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 text-right tabular-nums">{fmt(item.cgst_amt)}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 text-right tabular-nums">{fmt(item.sgst_amt)}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 text-right tabular-nums">{fmt(item.igst_amt)}</td>
                      <td className="px-2 py-1.5 border-r border-border/50 text-right tabular-nums">{fmt(item.billvalue)}</td>
                      <td className="px-2 py-1.5 border-r border-border/50">{stateName(item.placeofsupply)}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{item.add_less ? fmt(item.add_less) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
                {rows.length > 0 && (
                  <tfoot>
                    <tr className="border-t-2 border-border bg-muted/50 font-semibold text-foreground">
                      <td colSpan="7" className="px-2 py-2 text-sm">Totals</td>
                      <td className="px-2 py-2 text-right text-sm border-r border-border/50 tabular-nums">{fmt3(totals.sale_gw)}</td>
                      <td className="px-2 py-2 border-r border-border/50" />
                      <td className="px-2 py-2 text-right text-sm border-r border-border/50 tabular-nums">{fmt(totals.taxableamount)}</td>
                      <td className="px-2 py-2 text-right text-sm border-r border-border/50 tabular-nums">{fmt(totals.discount_amt)}</td>
                      <td className="px-2 py-2 text-right text-sm border-r border-border/50 tabular-nums">{fmt(totals.cgst_amt)}</td>
                      <td className="px-2 py-2 text-right text-sm border-r border-border/50 tabular-nums">{fmt(totals.sgst_amt)}</td>
                      <td className="px-2 py-2 text-right text-sm border-r border-border/50 tabular-nums">{fmt(totals.igst_amt)}</td>
                      <td className="px-2 py-2 text-right text-sm border-r border-border/50 tabular-nums">{fmt(totals.billvalue)}</td>
                      <td colSpan="2" className="px-2 py-2" />
                    </tr>
                  </tfoot>
                )}
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GstOutputRegister;
