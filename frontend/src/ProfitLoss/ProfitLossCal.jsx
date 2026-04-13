import { Fragment, useEffect, useState, useCallback } from 'react';
import { ChevronRight, ChevronDown, X, Loader2 } from 'lucide-react';
import apiClient from '@/services/apiClient';

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

/* ── Ledger rows (shown when a group is expanded) ── */
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
        <td colSpan={3} className="px-8 py-2 text-sm text-gray-400">
          <Loader2 className="inline size-3.5 animate-spin mr-1.5" />Loading ledgers...
        </td>
      </tr>
    );
  }
  if (!ledgers.length) {
    return (
      <tr>
        <td colSpan={3} className="px-8 py-1.5 text-xs text-gray-400 italic">No ledgers with balance</td>
      </tr>
    );
  }
  return ledgers.map((l) => {
    const bal = Number(l.balance || 0);
    return (
      <tr
        key={l.id}
        className="hover:bg-blue-50 cursor-pointer transition-colors"
        onClick={() => onLedgerClick(l)}
      >
        <td className="pl-12 pr-4 py-1 text-sm text-blue-700 underline decoration-dotted">
          {l.ac_name}
        </td>
        <td className="px-4 py-1 text-right text-sm font-mono">
          {bal > 0 ? fmt(bal) : ''}
        </td>
        <td className="px-4 py-1 text-right text-sm font-mono">
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="bg-white rounded-lg shadow-xl w-[90vw] max-w-3xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b">
          <h3 className="font-semibold text-gray-700 text-sm">
            {ledger.ac_name} — Transactions
          </h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
            <X className="size-4" />
          </button>
        </div>

        {/* Body */}
        <div className="overflow-auto flex-1 p-0">
          {loading ? (
            <div className="flex items-center justify-center py-12 text-gray-400 text-sm">
              <Loader2 className="size-4 animate-spin mr-2" /> Loading transactions...
            </div>
          ) : txns.length === 0 ? (
            <p className="text-center py-12 text-gray-400 text-sm">No transactions found.</p>
          ) : (
            <table className="w-full text-sm border-collapse">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Date</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Voucher No</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Type</th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600">Narration</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600">Debit (₹)</th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-gray-600">Credit (₹)</th>
                </tr>
              </thead>
              <tbody>
                {txns.map((t, i) => (
                  <tr key={i} className={i % 2 === 0 ? '' : 'bg-gray-50'}>
                    <td className="px-4 py-1.5 whitespace-nowrap">{fmtDate(t.voucher_main__date)}</td>
                    <td className="px-4 py-1.5 font-mono text-xs">{t.voucher_main__voucher_no}</td>
                    <td className="px-4 py-1.5">{t.voucher_main__voucher_type || '—'}</td>
                    <td className="px-4 py-1.5 text-gray-600 max-w-[200px] truncate">{t.voucher_main__narration || '—'}</td>
                    <td className="px-4 py-1.5 text-right font-mono">
                      {Number(t.debit) > 0 ? fmt(t.debit) : ''}
                    </td>
                    <td className="px-4 py-1.5 text-right font-mono">
                      {Number(t.credit) > 0 ? fmt(t.credit) : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-gray-300 font-semibold bg-gray-50">
                <tr>
                  <td colSpan={4} className="px-4 py-2 text-right text-xs text-gray-500">Total</td>
                  <td className="px-4 py-2 text-right font-mono">
                    {fmt(txns.reduce((s, t) => s + Number(t.debit || 0), 0))}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {fmt(txns.reduce((s, t) => s + Number(t.credit || 0), 0))}
                  </td>
                </tr>
              </tfoot>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Recursive expandable account-group rows ── */
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

    return (
      <Fragment key={item.id}>
        <tr
          className="hover:bg-gray-50 cursor-pointer transition-colors"
          onClick={() => toggle(item.id)}
        >
          <td className="px-4 py-1.5 text-sm" style={{ paddingLeft: 16 + depth * 16 }}>
            <span className="inline-flex items-center gap-1">
              {isExpanded
                ? <ChevronDown className="size-3.5 text-gray-400" />
                : <ChevronRight className="size-3.5 text-gray-400" />}
              <span className={hasChildren ? 'font-medium' : ''}>{item.name}</span>
            </span>
          </td>
          <td className="px-4 py-1.5 text-right text-sm font-mono">
            {!isCredit && !hasChildren ? fmt(bal) : ''}
          </td>
          <td className="px-4 py-1.5 text-right text-sm font-mono">
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
          <LedgerRows
            groupId={item.id}
            startDate={startDate}
            endDate={endDate}
            onLedgerClick={onLedgerClick}
          />
        )}
      </Fragment>
    );
  });
}

const SectionHeader = ({ label }) => (
  <tr className="bg-gray-200">
    <td className="px-4 py-2 font-semibold text-gray-700 text-sm" colSpan={3}>{label}</td>
  </tr>
);

const AmountRow = ({ label, debit, credit, highlight }) => (
  <tr className={highlight ? 'bg-green-50 font-semibold' : 'hover:bg-gray-50'}>
    <td className="px-4 py-1.5 text-sm">{label}</td>
    <td className="px-4 py-1.5 text-right text-sm font-mono">{debit != null ? fmt(debit) : '—'}</td>
    <td className="px-4 py-1.5 text-right text-sm font-mono">{credit != null ? fmt(credit) : '—'}</td>
  </tr>
);

export default function ProfitLossCal() {
  const [startDate, setStartDate] = useState(firstOfYear);
  const [endDate, setEndDate] = useState(today);
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [modalLedger, setModalLedger] = useState(null);

  const fetchData = () => {
    setLoading(true);
    setError('');
    apiClient
      .get(`/accounting/api/pnl?start_date=${startDate}&end_date=${endDate}`)
      .then((res) => setData(res.data))
      .catch(() => setError('Failed to fetch P&L data.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  return (
    <div className="min-h-screen w-full p-4 bg-white print:p-0">
      <h2 className="text-xl font-semibold text-center mb-4 text-gray-700">
        Profit &amp; Loss Statement
      </h2>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-end mb-4 print:hidden">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">From</label>
          <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)}
            className="border rounded px-2 h-9 text-sm" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500">To</label>
          <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)}
            className="border rounded px-2 h-9 text-sm" />
        </div>
        <button onClick={fetchData}
          className="h-9 px-4 rounded bg-primary text-white text-sm">
          Show
        </button>
        {data && (
          <button onClick={() => window.print()}
            className="h-9 px-4 rounded border text-sm ml-auto">
            Print
          </button>
        )}
      </div>

      <p className="text-xs text-gray-400 mb-3 print:hidden">
        Click on any account group to see ledger balances. Click a ledger to view transactions.
      </p>

      {loading && <p className="text-gray-500 text-sm">Loading...</p>}
      {error && <p className="text-red-500 text-sm">{error}</p>}

      {data && !loading && (
        <div className="w-full overflow-x-auto">
          <table className="w-full border-collapse text-sm border border-gray-300">
            <thead>
              <tr className="bg-gray-100">
                <th className="px-4 py-2.5 text-left border-b border-gray-300 text-gray-700">Particulars</th>
                <th className="px-4 py-2.5 text-right border-b border-gray-300 text-gray-700 w-36">Dr ({'\u20B9'})</th>
                <th className="px-4 py-2.5 text-right border-b border-gray-300 text-gray-700 w-36">Cr ({'\u20B9'})</th>
              </tr>
            </thead>
            <tbody>
              {/* Income */}
              <SectionHeader label="Income" />
              <AmountRow label="Gross Sales" credit={data.gross_sales} />
              {Number(data.sales_return) > 0 && (
                <AmountRow label="(-) Sales Returns" debit={data.sales_return} />
              )}
              <tr className="bg-gray-100 font-semibold">
                <td className="px-4 py-1.5 text-sm">Net Sales Revenue</td>
                <td className="px-4 py-1.5 text-right font-mono text-sm" />
                <td className="px-4 py-1.5 text-right font-mono text-sm">{fmt(data.sales_revenue)}</td>
              </tr>
              <AccountRows items={data.income} isCredit startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} />

              {/* COGS */}
              <SectionHeader label="Cost of Goods Sold" />
              <AmountRow label="Opening Stock" debit={data.opening_stock} />
              <AmountRow label="Gross Purchases" debit={data.purchases} />
              {Number(data.purchase_returns) > 0 && (
                <AmountRow label="(-) Purchase Returns" credit={data.purchase_returns} />
              )}
              <AmountRow label="(-) Closing Stock" credit={data.closing_stock} />
              <tr className="bg-gray-100 font-semibold">
                <td className="px-4 py-1.5 text-sm">Total COGS</td>
                <td className="px-4 py-1.5 text-right font-mono text-sm">{fmt(data.cogs)}</td>
                <td className="px-4 py-1.5 text-right font-mono text-sm" />
              </tr>

              {/* Direct Expenses */}
              <SectionHeader label="Direct Expenses" />
              <AccountRows items={data.direct_expenses} startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} />
              <tr className="bg-gray-100 font-semibold">
                <td className="px-4 py-1.5 text-sm">Total Direct Expenses</td>
                <td className="px-4 py-1.5 text-right font-mono text-sm">{fmt(data.direct_expenses_total)}</td>
                <td className="px-4 py-1.5 text-right font-mono text-sm" />
              </tr>

              {/* Gross Profit = Net Sales - COGS - Direct Expenses */}
              <tr className="bg-green-100 font-semibold border-t-2 border-gray-300">
                <td className="px-4 py-2 text-sm">
                  {Number(data.gross_profit) >= 0 ? 'Gross Profit' : 'Gross Loss'}
                </td>
                <td className="px-4 py-2 text-right font-mono text-sm">
                  {Number(data.gross_profit) < 0 ? fmt(data.gross_profit) : ''}
                </td>
                <td className="px-4 py-2 text-right font-mono text-sm">
                  {Number(data.gross_profit) >= 0 ? fmt(data.gross_profit) : ''}
                </td>
              </tr>

              {/* Indirect Expenses */}
              <SectionHeader label="Indirect Expenses" />
              <AccountRows items={data.indirect_expenses} startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} />
              <tr className="bg-gray-100 font-semibold">
                <td className="px-4 py-1.5 text-sm">Total Indirect Expenses</td>
                <td className="px-4 py-1.5 text-right font-mono text-sm">{fmt(data.indirect_expenses_total)}</td>
                <td className="px-4 py-1.5 text-right font-mono text-sm" />
              </tr>

              {/* Net Profit / Loss = Gross Profit - Indirect Expenses */}
              <tr className="bg-green-100 font-bold border-t-2 border-gray-300">
                <td className="px-4 py-2 text-sm">
                  {Number(data.net_profit) >= 0 ? 'Net Profit' : 'Net Loss'}
                </td>
                <td className="px-4 py-2 text-right font-mono text-sm">
                  {Number(data.net_profit) < 0 ? fmt(data.net_profit) : ''}
                </td>
                <td className="px-4 py-2 text-right font-mono text-sm">
                  {Number(data.net_profit) >= 0 ? fmt(data.net_profit) : ''}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Transaction Modal */}
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
