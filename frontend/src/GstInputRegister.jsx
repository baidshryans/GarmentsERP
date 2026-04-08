import { useState, useEffect } from 'react';
import { Search } from 'lucide-react';
import { fetchGSTInputReport, fetchGstins } from "./services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";

const GstInputRegister = () => {
  const [startDate, setStartDate] = useState('2025-02-01');
  const [endDate, setEndDate] = useState('2025-08-28');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [gstins, setGstins] = useState([]);
  const [gstinId, setGstinId] = useState('');

  useEffect(() => {
    fetchGstins().then(r => {
      if (r.success) setGstins(r.data?.results || r.data || []);
    });
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await fetchGSTInputReport(startDate, endDate, gstinId);
      setTimeout(() => {
        setData(result);
        setLoading(false);
      }, 1000);
    } catch (err) {
      setError('Failed to fetch data. Please try again.');
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const fmt = (amount) =>
    amount !== null && amount !== undefined ? Number(amount).toFixed(2) : '0.00';

  const formatDate = (dateString) =>
    new Date(dateString).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });

  const totals = data.reduce(
    (acc, row) => ({
      bill_value: acc.bill_value + (row.bill_value || 0),
      goods_value: acc.goods_value + (row.goods_value || 0),
      before_tax: acc.before_tax + (row.before_tax || 0),
      taxable_amount: acc.taxable_amount + (row.taxable_amount || 0),
      sgst: acc.sgst + (row.sgst || 0),
      cgst: acc.cgst + (row.cgst || 0),
      igst: acc.igst + (row.igst || 0),
      utgst: acc.utgst + (row.utgst || 0),
    }),
    { bill_value: 0, goods_value: 0, before_tax: 0, taxable_amount: 0, sgst: 0, cgst: 0, igst: 0, utgst: 0 }
  );

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

      {!loading && (
        <div className="flex flex-col gap-3">
          {data.length > 0 && (
            <p className="text-sm text-muted-foreground px-1">
              {data.length} record(s) — {formatDate(startDate)} to {formatDate(endDate)}
            </p>
          )}

          <div className="rounded-lg border border-border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Date</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Bill No.</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Ref. No.</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Party Name</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">GST IN</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">PAN No</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Bill Value</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Goods Value</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">+/- Before Tax</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Taxable Amt</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">SGST</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">CGST</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">IGST</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">UTGST</th>
                    <th className="px-3 py-2.5 text-right font-semibold">Add/Less</th>
                  </tr>
                </thead>
                <tbody>
                  {data.length === 0 ? (
                    <tr>
                      <td colSpan="15" className="px-3 py-10 text-center text-muted-foreground">
                        No data found for the selected date range.
                      </td>
                    </tr>
                  ) : (
                    data.map((row, index) => (
                      <tr
                        key={index}
                        className={`border-t border-border/50 hover:bg-accent/30 transition-colors ${
                          index % 2 === 1 ? 'bg-muted/20' : ''
                        }`}
                      >
                        <td className="px-3 py-2 border-r border-border/50">{formatDate(row.date)}</td>
                        <td className="px-3 py-2 border-r border-border/50">{row.bill_no}</td>
                        <td className="px-3 py-2 border-r border-border/50">{row.ref_no || '—'}</td>
                        <td className="px-3 py-2 border-r border-border/50 max-w-32 truncate">{row.party_name}</td>
                        <td className="px-3 py-2 border-r border-border/50">{row.gstin || '—'}</td>
                        <td className="px-3 py-2 border-r border-border/50">{row.pan || '—'}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.bill_value)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.goods_value)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.before_tax)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.taxable_amount)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.sgst)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.cgst)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.igst)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.utgst)}</td>
                        <td className="px-3 py-2 text-right">{row.add_less || '—'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
                {data.length > 0 && (
                  <tfoot>
                    <tr className="border-t-2 border-border bg-muted/50 font-semibold text-foreground">
                      <td colSpan="6" className="px-3 py-2.5 text-sm">Totals</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.bill_value)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.goods_value)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.before_tax)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.taxable_amount)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.sgst)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.cgst)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.igst)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.utgst)}</td>
                      <td className="px-3 py-2.5 text-right text-sm">—</td>
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

export default GstInputRegister;
