import { useState, useEffect } from 'react';
import { Search, TrendingUp, TrendingDown } from 'lucide-react';
import { fetchGSTOutputReport, fetchGstins, getFiscalYears } from "./services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const today = () => new Date().toISOString().slice(0, 10);

const GstOutputRegister = () => {
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

  useEffect(() => {
    if (startDate) fetchData();
  }, [startDate]);

  const getMergedAndSortedData = () => {
    if (!data) return [];

    const salesVouchers = data.salesvoucher?.map(item => ({
      ...item,
      type: 'SALE',
      billno: item.gst_billno,
      icon: TrendingUp,
    })) || [];

    const salesReturns = data.salesreturn?.map(item => ({
      ...item,
      type: 'RETURN',
      gst_billno: item.billno,
      icon: TrendingDown,
    })) || [];

    return [...salesVouchers, ...salesReturns].sort(
      (a, b) => new Date(a.date1) - new Date(b.date1)
    );
  };

  const fmt = (amount) =>
    new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount || 0);

  const formatDate = (dateString) =>
    new Date(dateString).toLocaleDateString('en-IN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });

  const rows = getMergedAndSortedData();

  const totals = rows.reduce(
    (acc, item) => ({
      billvalue: acc.billvalue + (item.billvalue || 0),
      beforetax: acc.beforetax + (item.beforetax || 0),
      taxableamount: acc.taxableamount + (item.taxableamount || 0),
    }),
    { billvalue: 0, beforetax: 0, taxableamount: 0 }
  );

  const totalSales = rows.filter(r => r.type === 'SALE').reduce((s, r) => s + (r.billvalue || 0), 0);
  const totalReturns = rows.filter(r => r.type === 'RETURN').reduce((s, r) => s + (r.billvalue || 0), 0);

  return (
    <div className="flex flex-col gap-5">
      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="h-9 w-36"
            style={{ colorScheme: 'light' }}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="h-9 w-36"
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
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && (
        <div className="flex flex-col gap-2">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-9 w-full" />
          ))}
        </div>
      )}

      {!loading && data && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between text-sm text-muted-foreground px-1">
            <span>
              {rows.length} transaction(s) — {formatDate(startDate)} to {formatDate(endDate)}
            </span>
            <span>
              Sales: <strong className="text-foreground">₹{fmt(totalSales)}</strong>
              {' / '}
              Returns: <strong className="text-foreground">₹{fmt(totalReturns)}</strong>
              {' / '}
              Net: <strong className="text-foreground">₹{fmt(totalSales - totalReturns)}</strong>
            </span>
          </div>

          <div className="rounded-lg border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Date</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Type</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">GST Bill No / Bill No</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Party Name</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">GSTIN</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">PAN</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Place of Supply</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Bill Value</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Before Tax</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Taxable Amt</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Add/Less</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">IGST %</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">SGST %</th>
                    <th className="px-3 py-2.5 text-right font-semibold">CGST %</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length === 0 ? (
                    <tr>
                      <td colSpan="14" className="px-3 py-10 text-center text-muted-foreground">
                        No data available for the selected date range.
                      </td>
                    </tr>
                  ) : (
                    rows.map((item, index) => (
                      <tr
                        key={index}
                        className={`border-t border-border/50 hover:bg-accent/30 transition-colors ${
                          index % 2 === 1 ? 'bg-muted/20' : ''
                        }`}
                      >
                        <td className="px-3 py-2 border-r border-border/50">{formatDate(item.date1)}</td>
                        <td className="px-3 py-2 border-r border-border/50">
                          <span className="text-xs bg-muted px-1.5 py-0.5 rounded font-medium">
                            {item.type}
                          </span>
                        </td>
                        <td className="px-3 py-2 border-r border-border/50 font-mono">{item.gst_billno || item.billno}</td>
                        <td className="px-3 py-2 border-r border-border/50">{item.partyname}</td>
                        <td className="px-3 py-2 border-r border-border/50">{item.gstin || '—'}</td>
                        <td className="px-3 py-2 border-r border-border/50">{item.pan || '—'}</td>
                        <td className="px-3 py-2 border-r border-border/50">{item.placeofsupply || '—'}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(item.billvalue)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(item.beforetax)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(item.taxableamount)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">
                          {item.add_less ? fmt(item.add_less) : '—'}
                        </td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{item.igst_per}%</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{item.sgst_per}%</td>
                        <td className="px-3 py-2 text-right">{item.cgst_per}%</td>
                      </tr>
                    ))
                  )}
                </tbody>
                {rows.length > 0 && (
                  <tfoot>
                    <tr className="border-t-2 border-border bg-muted/50 font-semibold text-foreground">
                      <td colSpan="7" className="px-3 py-2.5 text-sm">Totals</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.billvalue)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.beforetax)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.taxableamount)}</td>
                      <td colSpan="4" className="px-3 py-2.5" />
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
