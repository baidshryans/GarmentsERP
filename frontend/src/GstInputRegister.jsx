import { useState, useEffect, useRef } from 'react';
import { Search, Download, Printer } from 'lucide-react';
import { fetchGSTInputReport, fetchGstins, getFiscalYears } from "./services/apiService";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { isValidDateRange } from "@/lib/dateRange";

const today = () => new Date().toISOString().slice(0, 10);

const GstInputRegister = () => {
  const printRef = useRef(null);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState(today());
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
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


  const fmt = (amount) =>
    amount !== null && amount !== undefined ? Number(amount).toFixed(2) : '0.00';

  const formatDate = (dateString) =>
    new Date(dateString).toLocaleDateString('en-GB', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });

  const handlePrint = () => {
    const content = printRef.current?.innerHTML;
    if (!content) return;
    const win = window.open('', '_blank');
    win.document.write(`<!DOCTYPE html><html><head><title>GST Input Register</title>
      <style>
        body { font-family: Arial, sans-serif; font-size: 11px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ccc; padding: 4px 6px; text-align: left; }
        th { background: #f0f0f0; font-weight: bold; }
        .text-right { text-align: right; }
        tfoot tr { font-weight: bold; background: #f9f9f9; }
        h2 { font-size: 14px; margin-bottom: 8px; }
      </style></head><body>
      <h2>GST Input Register — ${startDate} to ${endDate}</h2>
      ${content}
      </body></html>`);
    win.document.close();
    win.focus();
    win.print();
    win.close();
  };

  const exportToCSV = () => {
    const headers = [
      'Date', 'Bill No.', 'Ref. No.', 'Party Name', 'GST IN', 'PAN No',
      'Bill Value', 'Goods Value', '+/- Before Tax', 'Taxable Amt',
      'SGST', 'CGST', 'IGST', 'UTGST', 'Add/Less'
    ];

    const rows = data.map(row => [
      formatDate(row.date),
      row.bill_no,
      row.ref_no || '',
      row.party_name,
      row.gstin || '',
      row.pan || '',
      fmt(row.bill_value),
      fmt(row.goods_value),
      fmt(row.before_tax),
      fmt(row.taxable_amount),
      fmt(row.sgst),
      fmt(row.cgst),
      fmt(row.igst),
      fmt(row.utgst),
      row.add_less || '',
    ]);

    const totalsRow = [
      'Totals', '', '', '', '', '',
      fmt(totals.bill_value),
      fmt(totals.goods_value),
      fmt(totals.before_tax),
      fmt(totals.taxable_amount),
      fmt(totals.sgst),
      fmt(totals.cgst),
      fmt(totals.igst),
      fmt(totals.utgst),
      '',
    ];

    const csvContent = [headers, ...rows, totalsRow]
      .map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
      .join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `GST_Input_Register_${startDate}_to_${endDate}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

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
            max={endDate || undefined}
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
            min={startDate || undefined}
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
        <Button size="sm" variant="outline" onClick={exportToCSV} disabled={loading || data.length === 0} className="h-9">
          <Download className="w-3.5 h-3.5 mr-1" />
          Export CSV
        </Button>
        <Button size="sm" variant="outline" onClick={handlePrint} disabled={loading || data.length === 0} className="h-9">
          <Printer className="w-3.5 h-3.5 mr-1" />
          Print
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

          <div className="rounded-lg border border-border overflow-hidden" ref={printRef}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Date</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Bill No.</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Ref. No.</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">Party Name</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">GST IN</th>
                    <th className="px-3 py-2.5 text-left font-semibold border-r border-border">PAN No</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Taxable Amt</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Bill Value</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">Goods Value</th>
                    <th className="px-3 py-2.5 text-right font-semibold border-r border-border">+/- Before Tax</th>
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
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.taxable_amount)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.bill_value)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.goods_value)}</td>
                        <td className="px-3 py-2 text-right border-r border-border/50">{fmt(row.before_tax)}</td>
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
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.taxable_amount)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.bill_value)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.goods_value)}</td>
                      <td className="px-3 py-2.5 text-right text-sm border-r border-border/50">{fmt(totals.before_tax)}</td>
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
