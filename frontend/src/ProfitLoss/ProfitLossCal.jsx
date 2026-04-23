import { Fragment, useEffect, useState, useCallback } from 'react';
import { ChevronRight, ChevronDown, X, Loader2, TrendingUp, TrendingDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import apiClient from '@/services/apiClient';
import { RetailScopePicker, applyRetailScopeParams } from '@/components/common/RetailScopePicker';
import { isValidDateRange } from '@/lib/dateRange';

const today = new Date().toISOString().split('T')[0];
const fy = new Date().getMonth() < 3 ? new Date().getFullYear() - 1 : new Date().getFullYear();
const firstOfYear = `${fy}-04-01`;

const fmt = (v) =>
  v != null && !isNaN(Number(v))
    ? Math.abs(Number(v)).toLocaleString('en-IN', { minimumFractionDigits: 2 })
    : '0.00';

const fmtDate = (d) => {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-IN');
};

/* ── Ledger rows ── */
function LedgerRows({ groupId, startDate, endDate, onLedgerClick }) {
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get(`/accounting/api/pnl-group-ledgers/?group_id=${groupId}&start_date=${startDate}&end_date=${endDate}`)
      .then((res) => setLedgers(res.data.ledgers || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [groupId, startDate, endDate]);

  if (loading) {
    return (
      <tr>
        <td colSpan={3} className="py-2 text-xs text-muted-foreground" style={{ paddingLeft: 56 }}>
          <Loader2 className="inline size-3 animate-spin mr-1.5" />Loading…
        </td>
      </tr>
    );
  }
  if (!ledgers.length) {
    return (
      <tr>
        <td colSpan={3} className="py-1.5 text-xs text-muted-foreground italic" style={{ paddingLeft: 56 }}>
          No ledgers with balance
        </td>
      </tr>
    );
  }
  return ledgers.map((l) => {
    const bal = Number(l.balance || 0);
    return (
      <tr
        key={l.id}
        className="hover:bg-accent/30 cursor-pointer transition-colors duration-150 group"
        onClick={() => onLedgerClick(l)}
      >
        <td className="py-1.5 pr-4 text-sm text-muted-foreground group-hover:text-foreground transition-colors" style={{ paddingLeft: 56 }}>
          <span className="border-b border-dotted border-border group-hover:border-foreground/40">
            {l.ac_name}
          </span>
        </td>
        <td className="px-3 py-1.5 text-right text-sm tabular-nums text-foreground">
          {bal > 0 ? fmt(bal) : ''}
        </td>
        <td className="px-3 py-1.5 text-right text-sm tabular-nums text-foreground">
          {bal < 0 ? fmt(bal) : ''}
        </td>
      </tr>
    );
  });
}

/* ── Transaction Modal ── */
function TransactionModal({ ledger, startDate, endDate, onClose }) {
  const [txns, setTxns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiClient
      .get(`/accounting/api/pnl-ledger-txns/?ledger_id=${ledger.id}&start_date=${startDate}&end_date=${endDate}`)
      .then((res) => setTxns(res.data.transactions || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [ledger.id, startDate, endDate]);

  const totalDr = txns.reduce((s, t) => s + Number(t.debit || 0), 0);
  const totalCr = txns.reduce((s, t) => s + Number(t.credit || 0), 0);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-card rounded-xl shadow-2xl w-[92vw] max-w-3xl max-h-[82vh] flex flex-col border border-border"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div>
            <p className="font-semibold text-foreground text-sm">{ledger.ac_name}</p>
            <p className="text-xs text-muted-foreground mt-0.5">Transaction ledger</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-accent rounded-lg transition-colors cursor-pointer">
            <X className="size-4 text-muted-foreground" />
          </button>
        </div>

        <div className="overflow-auto flex-1">
          {loading ? (
            <div className="flex items-center justify-center py-16 text-muted-foreground text-sm gap-2">
              <Loader2 className="size-4 animate-spin" /> Loading transactions…
            </div>
          ) : txns.length === 0 ? (
            <p className="text-center py-16 text-muted-foreground text-sm">No transactions in this period.</p>
          ) : (
            <table className="w-full text-sm border-collapse">
              <thead className="bg-muted/50 sticky top-0">
                <tr>
                  {['Date', 'Voucher No', 'Type', 'Narration', 'Dr (₹)', 'Cr (₹)'].map((h, i) => (
                    <th key={h} className={`px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide ${i >= 4 ? 'text-right' : 'text-left'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {txns.map((t, i) => (
                  <tr key={i} className="hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-2 text-muted-foreground whitespace-nowrap text-xs">{fmtDate(t.voucher_main__date)}</td>
                    <td className="px-4 py-2 tabular-nums text-xs text-foreground">{t.voucher_main__voucher_no}</td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">{t.voucher_main__voucher_type || '—'}</td>
                    <td className="px-4 py-2 text-muted-foreground max-w-[180px] truncate text-xs">{t.voucher_main__narration || '—'}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-xs text-rose-600">
                      {Number(t.debit) > 0 ? fmt(t.debit) : ''}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-xs text-emerald-600">
                      {Number(t.credit) > 0 ? fmt(t.credit) : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-border bg-muted/50">
                <tr>
                  <td colSpan={4} className="px-4 py-2.5 text-right text-xs font-semibold text-muted-foreground uppercase tracking-wide">Total</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-sm font-semibold text-rose-600">{fmt(totalDr)}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums text-sm font-semibold text-emerald-600">{fmt(totalCr)}</td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Recursive account-group rows ── */
function AccountRows({ items = [], isCredit = false, depth = 0, startDate, endDate, onLedgerClick }) {
  const [expanded, setExpanded] = useState({});

  const toggle = useCallback((id) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  }, []);

  if (!items.length) return null;
  return items.map((item) => {
    const bal = Number(item.balance || 0);
    const hasChildren = item.children?.length > 0;
    const isExpanded = expanded[item.id];
    const paddingLeft = 16 + depth * 20;

    return (
      <Fragment key={item.id}>
        <tr
          className="hover:bg-accent/30 cursor-pointer transition-colors duration-150 group"
          onClick={() => toggle(item.id)}
        >
          <td className="py-2 pr-4 text-sm text-foreground transition-colors" style={{ paddingLeft }}>
            <span className="inline-flex items-center gap-1.5">
              <span className="text-muted-foreground group-hover:text-foreground transition-colors flex-shrink-0">
                {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
              </span>
              <span className={hasChildren ? 'font-semibold text-foreground' : 'font-medium text-foreground'}>
                {item.name}
              </span>
            </span>
          </td>
          <td className="px-3 py-2 text-right text-sm tabular-nums text-foreground">
            {!isCredit && !hasChildren ? fmt(bal) : ''}
          </td>
          <td className="px-3 py-2 text-right text-sm tabular-nums text-foreground">
            {isCredit && !hasChildren ? fmt(bal) : ''}
          </td>
        </tr>
        {isExpanded && hasChildren && (
          <AccountRows
            items={item.children}
            isCredit={isCredit}
            depth={depth + 1}
            startDate={startDate}
            endDate={endDate}
            onLedgerClick={onLedgerClick}
          />
        )}
        {isExpanded && !hasChildren && (
          <LedgerRows groupId={item.id} startDate={startDate} endDate={endDate} onLedgerClick={onLedgerClick} />
        )}
      </Fragment>
    );
  });
}

/* ── Section header ── */
const SectionHeader = ({ label }) => (
  <tr className="bg-accent">
    <td className="px-4 py-2 font-semibold text-accent-foreground text-xs uppercase tracking-wider" colSpan={3}>
      {label}
    </td>
  </tr>
);

/* ── Plain indented amount row ── */
const AmountRow = ({ label, debit, credit }) => (
  <tr className="hover:bg-accent/30 transition-colors">
    <td className="px-4 py-1.5 text-sm text-muted-foreground pl-8">{label}</td>
    <td className="px-3 py-1.5 text-right text-sm tabular-nums text-foreground">
      {debit != null ? fmt(debit) : ''}
    </td>
    <td className="px-3 py-1.5 text-right text-sm tabular-nums text-foreground">
      {credit != null ? fmt(credit) : ''}
    </td>
  </tr>
);

/* ── Subtotal row ── */
const SubtotalRow = ({ label, debit, credit }) => (
  <tr className="bg-muted/50 border-t border-b border-border">
    <td className="px-4 py-2 text-sm font-semibold text-foreground">{label}</td>
    <td className="px-3 py-2 text-right text-sm tabular-nums font-semibold text-foreground">
      {debit != null ? fmt(debit) : ''}
    </td>
    <td className="px-3 py-2 text-right text-sm tabular-nums font-semibold text-foreground">
      {credit != null ? fmt(credit) : ''}
    </td>
  </tr>
);

/* ── Profit / Loss row ── */
const ProfitRow = ({ label, value }) => {
  const isProfit = Number(value) >= 0;
  return (
    <tr className={`border-t-2 border-border font-bold ${isProfit ? 'bg-emerald-50' : 'bg-rose-50'}`}>
      <td className="px-4 py-2.5 text-sm flex items-center gap-2">
        {isProfit
          ? <TrendingUp className="size-4 text-emerald-600" />
          : <TrendingDown className="size-4 text-rose-600" />}
        <span className={isProfit ? 'text-emerald-800' : 'text-rose-800'}>{label}</span>
      </td>
      <td className="px-3 py-2.5 text-right tabular-nums text-sm font-bold text-rose-700">
        {!isProfit ? fmt(value) : ''}
      </td>
      <td className="px-3 py-2.5 text-right tabular-nums text-sm font-bold text-emerald-700">
        {isProfit ? fmt(value) : ''}
      </td>
    </tr>
  );
};

export default function ProfitLossCal() {
  const [startDate, setStartDate] = useState(firstOfYear);
  const [endDate, setEndDate] = useState(today);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [modalLedger, setModalLedger] = useState(null);
  const [scope, setScope] = useState('all');
  const [selectedRetailIds, setSelectedRetailIds] = useState([]);

  const user = JSON.parse(sessionStorage.getItem('user') || '{}');
  const canViewCombined = user.is_superuser || ['admin', 'super admin'].includes((user.role || '').toLowerCase());

  const fetchData = () => {
    if (!isValidDateRange(startDate, endDate)) {
      setError('From date cannot be after To date.');
      return;
    }
    if (scope === 'selected' && selectedRetailIds.length === 0) {
      setError("Select at least one retail, or choose 'All retails (combined)'.");
      return;
    }
    setLoading(true);
    setError('');
    const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
    applyRetailScopeParams(params, scope, selectedRetailIds);
    apiClient
      .get(`/accounting/api/pnl?${params}`)
      .then((res) => setData(res.data))
      .catch(() => setError('Failed to fetch P&L data.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  return (
    <div className="flex flex-col gap-4 max-w-3xl mx-auto w-full">
      {/* ── Filters ── */}
      <div className="flex flex-wrap items-end gap-3 p-4 bg-muted/30 rounded-lg border border-border print:hidden">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">From</Label>
          <Input type="date" value={startDate} max={endDate || undefined} onChange={(e) => setStartDate(e.target.value)} className="h-9 w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">To</Label>
          <Input type="date" value={endDate} min={startDate || undefined} onChange={(e) => setEndDate(e.target.value)} className="h-9 w-36" />
        </div>
        {canViewCombined && (
          <RetailScopePicker
            scope={scope}
            selectedIds={selectedRetailIds}
            onChange={({ scope: s, selectedIds }) => { setScope(s); setSelectedRetailIds(selectedIds); }}
          />
        )}
        <Button size="sm" onClick={fetchData} disabled={loading} className="h-9">
          {loading ? <Loader2 className="size-4 animate-spin" /> : 'Show'}
        </Button>
        {data && (
          <Button size="sm" variant="outline" onClick={() => window.print()} className="h-9 ml-auto">
            Print
          </Button>
        )}
      </div>

      <p className="text-xs text-muted-foreground -mt-2 print:hidden">
        Click any account group to expand. Click a ledger to view transactions.
      </p>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {loading && !data && (
        <div className="flex items-center justify-center py-20 text-muted-foreground gap-2">
          <Loader2 className="size-5 animate-spin" />
          <span className="text-sm">Loading…</span>
        </div>
      )}

      {data && (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5 text-left font-semibold border-b border-border">Particulars</th>
                <th className="px-3 py-2.5 text-right font-semibold border-b border-border w-36">Dr (₹)</th>
                <th className="px-3 py-2.5 text-right font-semibold border-b border-border w-36">Cr (₹)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {/* Income */}
              <SectionHeader label="Income" />
              <AmountRow label="Gross Sales" credit={data.gross_sales} />
              {Number(data.sales_return) > 0 && (
                <AmountRow label="(−) Sales Returns" debit={data.sales_return} />
              )}
              <SubtotalRow label="Net Sales Revenue" credit={data.sales_revenue} />
              <AccountRows items={data.income} isCredit startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} />

              {/* COGS */}
              <SectionHeader label="Cost of Goods Sold" />
              <AmountRow label="Opening Stock" debit={data.opening_stock} />
              <AmountRow label="Gross Purchases" debit={data.purchases} />
              {Number(data.purchase_returns) > 0 && (
                <AmountRow label="(−) Purchase Returns" credit={data.purchase_returns} />
              )}
              {Number(data.transfer_in) > 0 && (
                <AmountRow label="(+) Transfers In (from other retails)" debit={data.transfer_in} />
              )}
              {Number(data.transfer_out) > 0 && (
                <AmountRow label="(−) Transfers Out (to other retails)" credit={data.transfer_out} />
              )}
              <AmountRow label="(−) Closing Stock" credit={data.closing_stock} />
              <SubtotalRow label="Total COGS" debit={data.cogs} />

              {/* Direct Expenses */}
              <SectionHeader label="Direct Expenses" />
              <AccountRows items={data.direct_expenses} startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} />
              <SubtotalRow label="Total Direct Expenses" debit={data.direct_expenses_total} />

              {/* Gross Profit */}
              <ProfitRow
                label={Number(data.gross_profit) >= 0 ? 'Gross Profit' : 'Gross Loss'}
                value={data.gross_profit}
              />

              {/* Indirect Expenses */}
              <SectionHeader label="Indirect Expenses" />
              <AccountRows items={data.indirect_expenses} startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} />
              <SubtotalRow label="Total Indirect Expenses" debit={data.indirect_expenses_total} />

              {/* Net Profit */}
              <ProfitRow
                label={Number(data.net_profit) >= 0 ? 'Net Profit' : 'Net Loss'}
                value={data.net_profit}
              />
            </tbody>
          </table>
        </div>
      )}

      {modalLedger && (
        <TransactionModal
          ledger={modalLedger}
          startDate={startDate}
          endDate={endDate}
          onClose={() => setModalLedger(null)}
        />
      )}
    </div>
  );
}
