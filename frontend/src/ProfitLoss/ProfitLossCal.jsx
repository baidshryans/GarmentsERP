import { Fragment, useEffect, useState, useCallback, useRef } from 'react';
import { formatNumber, formatDate, getFormatConfig } from '@/lib/format';
import { ChevronRight, ChevronDown, X, Loader2, TrendingUp, TrendingDown, Printer } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import apiClient from '@/services/apiClient';
import { fetchCompanies } from '@/services/apiService';
import { RetailScopePicker, applyRetailScopeParams } from '@/components/common/RetailScopePicker';
import { isValidDateRange } from '@/lib/dateRange';
import { printReport } from '@/lib/printReport';

const today = new Date().toISOString().split('T')[0];
const fy = new Date().getMonth() < 3 ? new Date().getFullYear() - 1 : new Date().getFullYear();
const firstOfYear = `${fy}-04-01`;

const fmt = (v) =>
  v != null && !isNaN(Number(v))
    ? formatNumber(v, { minDecimals: 2, abs: true })
    : '0.00';

const fmtDate = (d) => {
  if (!d) return '—';
  return formatDate(d, 'numeric');
};

const toDdMm = (s) => {
  const [y, m, d] = (s || '').split('-');
  return y && m && d ? `${d}/${m}/${y}` : s;
};

/* ─────────────────────────────────────────────────────────────────────────────
   Extra CSS injected into the printReport window for P&L-specific row types
───────────────────────────────────────────────────────────────────────────── */
const PNL_EXTRA_CSS = `
  tr.pnl-section td {
    background: #f1f0fb !important;
    font-weight: 800;
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #3730a3;
    padding: 5px 8px;
    border-top: 1.5px solid #818cf8;
    border-bottom: 0.75px solid #c7d2fe;
  }
  tr.pnl-amt td {
    color: #64748b;
    padding: 3px 8px;
    border-bottom: none;
  }
  tr.pnl-group td {
    font-weight: 600;
    color: #1e293b;
    padding: 3.5px 8px;
    border-bottom: 0.4px solid #f1f5f9;
  }
  tr.pnl-subgroup td {
    font-weight: 500;
    color: #334155;
    padding: 3px 8px;
    border-bottom: 0.4px solid #f8fafc;
  }
  tr.pnl-ledger td {
    color: #64748b;
    font-size: 10px;
    padding: 2px 8px;
    border-bottom: none;
  }
  tr.pnl-subtotal td {
    font-weight: 700;
    color: #0f172a;
    background: #f8f7ff !important;
    border-top: 0.75px solid #94a3b8;
    border-bottom: 2.5px double #374151;
    padding: 4px 8px;
  }
  tr.pnl-profit td {
    font-weight: 800;
    color: #065f46;
    background: transparent !important;
    border-top: 2px solid #059669;
    padding: 6px 8px;
    font-size: 11.5px;
  }
  tr.pnl-loss td {
    font-weight: 800;
    color: #991b1b;
    background: transparent !important;
    border-top: 2px solid #dc2626;
    padding: 6px 8px;
    font-size: 11.5px;
  }
  /* Override the default alternating row tint for our rows */
  tr.pnl-amt, tr.pnl-group, tr.pnl-subgroup, tr.pnl-ledger,
  tr.pnl-subtotal, tr.pnl-profit, tr.pnl-loss {
    background: transparent !important;
  }
  th:nth-child(2), th:nth-child(3),
  td:nth-child(2), td:nth-child(3) {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  th:first-child { width: 62%; }
  th:nth-child(2), th:nth-child(3) { width: 19%; }
`;

/* ─────────────────────────────────────────────────────────────────────────────
   Returns true if an item (or any of its descendants) has a non-zero balance.
   Used to suppress entirely-zero subtrees from both screen and print views.
───────────────────────────────────────────────────────────────────────────── */
function hasNonZeroBalance(item) {
  if (!item.children?.length) {
    return Math.abs(Number(item.balance || 0)) >= 0.005;
  }
  return item.children.some(hasNonZeroBalance);
}

/* ─────────────────────────────────────────────────────────────────────────────
   Collect all leaf-group IDs (no children) from an account-group tree
───────────────────────────────────────────────────────────────────────────── */
function collectLeafGroupIds(items = []) {
  const ids = [];
  for (const item of items) {
    if (item.children?.length > 0) {
      ids.push(...collectLeafGroupIds(item.children));
    } else {
      ids.push(item.id);
    }
  }
  return ids;
}

/* ─────────────────────────────────────────────────────────────────────────────
   Build the full P&L HTML string for printReport
   ledgersByGroupId = { [group_id]: [{ ac_name, balance }] }
───────────────────────────────────────────────────────────────────────────── */
function buildPnlHtml(data, ledgersByGroupId = {}) {
  // Returns empty string for zero or null so cells stay blank
  const f = (v) =>
    v != null && !isNaN(Number(v)) && Math.abs(Number(v)) >= 0.005
      ? formatNumber(v, { minDecimals: 2, abs: true })
      : '';

  const row = (cls, label, dr, cr, indent = 0) =>
    `<tr class="${cls}">
      <td style="padding-left:${8 + indent}px">${label}</td>
      <td>${dr != null ? f(dr) : ''}</td>
      <td>${cr != null ? f(cr) : ''}</td>
    </tr>`;

  const sectionRow = (label) =>
    `<tr class="pnl-section"><td colspan="3">${label}</td></tr>`;

  const subtotalRow = (label, dr, cr) =>
    `<tr class="pnl-subtotal">
      <td>${label}</td>
      <td>${dr != null ? f(dr) : ''}</td>
      <td>${cr != null ? f(cr) : ''}</td>
    </tr>`;

  const profitRow = (label, value) => {
    const isProfit = Number(value) >= 0;
    return `<tr class="${isProfit ? 'pnl-profit' : 'pnl-loss'}">
      <td>${label}</td>
      <td>${!isProfit ? f(value) : ''}</td>
      <td>${isProfit ? f(value) : ''}</td>
    </tr>`;
  };

  // Recursive group renderer
  function groupRows(items, isCredit = false, depth = 0) {
    let html = '';
    for (const item of items) {
      if (!hasNonZeroBalance(item)) continue;
      const bal = Number(item.balance || 0);
      const hasChildren = item.children?.length > 0;
      const indent = depth * 14;
      const cls = depth === 0 ? 'pnl-group' : 'pnl-subgroup';

      html += `<tr class="${cls}">
        <td style="padding-left:${8 + indent}px">${item.name}</td>
        <td>${!isCredit && !hasChildren ? f(bal) : ''}</td>
        <td>${isCredit && !hasChildren ? f(bal) : ''}</td>
      </tr>`;

      if (hasChildren) {
        html += groupRows(item.children, isCredit, depth + 1);
      } else {
        const ledgers = ledgersByGroupId[item.id] || [];
        for (const l of ledgers) {
          const lbal = Number(l.balance || 0);
          const lbalAbs = Math.abs(lbal);
          html += `<tr class="pnl-ledger">
            <td style="padding-left:${8 + indent + 14}px">${l.ac_name}</td>
            <td>${!isCredit && lbalAbs >= 0.005 ? f(lbal) : ''}</td>
            <td>${isCredit && lbalAbs >= 0.005 ? f(lbal) : ''}</td>
          </tr>`;
        }
      }
    }
    return html;
  }

  let body = '';

  // ── Income ──
  body += sectionRow('Income');
  body += row('pnl-amt', 'Gross Sales', null, data.gross_sales, 4);
  if (Number(data.sales_return) > 0)
    body += row('pnl-amt', '(−) Sales Returns', data.sales_return, null, 4);
  body += subtotalRow('Net Sales Revenue', null, data.sales_revenue);
  body += groupRows(data.income || [], true, 0);

  // ── COGS ──
  body += sectionRow('Cost of Goods Sold');
  body += row('pnl-amt', 'Opening Stock', data.opening_stock, null, 4);
  body += groupRows(data.purchases_tree || [], false, 0);
  if (Number(data.transfer_in) > 0)
    body += row('pnl-amt', '(+) Transfers In', data.transfer_in, null, 4);
  if (Number(data.transfer_out) > 0)
    body += row('pnl-amt', '(−) Transfers Out', null, data.transfer_out, 4);
  body += row('pnl-amt', '(−) Closing Stock', null, data.closing_stock, 4);
  body += subtotalRow('Total COGS', data.cogs, null);

  // ── Direct Expenses ──
  body += sectionRow('Direct Expenses');
  body += groupRows(data.direct_expenses || [], false, 0);
  body += subtotalRow('Total Direct Expenses', data.direct_expenses_total, null);

  body += profitRow(Number(data.gross_profit) >= 0 ? 'Gross Profit' : 'Gross Loss', data.gross_profit);

  // ── Indirect Expenses ──
  body += sectionRow('Indirect Expenses');
  body += groupRows(data.indirect_expenses || [], false, 0);
  body += subtotalRow('Total Indirect Expenses', data.indirect_expenses_total, null);

  body += profitRow(Number(data.net_profit) >= 0 ? 'Net Profit' : 'Net Loss', data.net_profit);

  return `<table>
    <thead>
      <tr>
        <th style="text-align:left">Particulars</th>
        <th>Dr (₹)</th>
        <th>Cr (₹)</th>
      </tr>
    </thead>
    <tbody>${body}</tbody>
  </table>`;
}

/* ── Ledger rows (screen only) ── */
function LedgerRows({ groupId, startDate, endDate, onLedgerClick, grossCredit = false }) {
  const [ledgers, setLedgers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const gc = grossCredit ? '&gross_credit=true' : '';
    apiClient
      .get(`/accounting/api/pnl-group-ledgers/?group_id=${groupId}&start_date=${startDate}&end_date=${endDate}${gc}`)
      .then((res) => setLedgers(res.data.ledgers || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [groupId, startDate, endDate]);

  if (loading) return (
    <tr>
      <td colSpan={3} className="py-2 text-xs text-muted-foreground" style={{ paddingLeft: 56 }}>
        <Loader2 className="inline size-3 animate-spin mr-1.5" />Loading…
      </td>
    </tr>
  );

  if (!ledgers.length) return (
    <tr>
      <td colSpan={3} className="py-1.5 text-xs text-muted-foreground italic" style={{ paddingLeft: 56 }}>
        No ledgers with balance
      </td>
    </tr>
  );

  return ledgers.map((l) => {
    const bal = Number(l.balance || 0);
    return (
      <tr
        key={l.id}
        className="hover:bg-accent/30 cursor-pointer transition-colors duration-150 group"
        onClick={() => onLedgerClick?.(l)}
      >
        <td className="py-1 pr-4 text-sm text-muted-foreground group-hover:text-foreground transition-colors" style={{ paddingLeft: 56 }}>
          <span className="border-b border-dotted border-border group-hover:border-foreground/40">{l.ac_name}</span>
        </td>
        <td className="px-3 py-1 text-right text-sm tabular-nums">{bal > 0 ? fmt(bal) : ''}</td>
        <td className="px-3 py-1 text-right text-sm tabular-nums">{bal < 0 ? fmt(bal) : ''}</td>
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
      <div className="bg-card rounded-xl shadow-2xl w-[92vw] max-w-3xl max-h-[82vh] flex flex-col border border-border" onClick={(e) => e.stopPropagation()}>
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
                  {['Date', 'Voucher No', 'Type', 'Narration', `Dr (${getFormatConfig().symbol})`, `Cr (${getFormatConfig().symbol})`].map((h, i) => (
                    <th key={h} className={`px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wide ${i >= 4 ? 'text-right' : 'text-left'}`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {txns.map((t, i) => (
                  <tr key={i} className="hover:bg-accent/30 transition-colors">
                    <td className="px-4 py-2 text-muted-foreground whitespace-nowrap text-xs">{fmtDate(t.voucher_main__date)}</td>
                    <td className="px-4 py-2 tabular-nums text-xs">{t.voucher_main__voucher_no}</td>
                    <td className="px-4 py-2 text-xs text-muted-foreground">{t.voucher_main__voucher_type || '—'}</td>
                    <td className="px-4 py-2 text-muted-foreground max-w-[180px] truncate text-xs">{t.voucher_main__narration || '—'}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-xs text-rose-600">{Number(t.debit) > 0 ? fmt(t.debit) : ''}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-xs text-emerald-600">{Number(t.credit) > 0 ? fmt(t.credit) : ''}</td>
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

/* ── Print Mode Modal ── */
function PrintModal({ onClose, onPrint }) {
  const [preparing, setPreparing] = useState(null);

  const handle = async (mode) => {
    setPreparing(mode);
    try {
      await onPrint(mode);
    } finally {
      setPreparing(null);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={!preparing ? onClose : undefined}>
      <div className="bg-card rounded-xl shadow-2xl border border-border w-80 p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2.5 mb-1">
          <Printer className="size-4 text-muted-foreground" />
          <h3 className="font-semibold text-sm text-foreground">Print Profit &amp; Loss</h3>
        </div>
        <p className="text-xs text-muted-foreground mb-5 pl-7">Choose the level of detail:</p>

        <div className="flex flex-col gap-2.5">
          <button
            disabled={!!preparing}
            onClick={() => handle('groups')}
            className="w-full text-left px-4 py-3 rounded-lg border border-border hover:bg-accent transition-colors disabled:opacity-50 cursor-pointer"
          >
            <p className="text-sm font-medium text-foreground">Groups only</p>
            <p className="text-xs text-muted-foreground mt-0.5">Collapsed — group totals, no individual ledgers</p>
          </button>

          <button
            disabled={!!preparing}
            onClick={() => handle('expanded')}
            className="w-full text-left px-4 py-3 rounded-lg border border-primary/40 bg-primary/5 hover:bg-primary/10 transition-colors disabled:opacity-50 cursor-pointer"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-foreground">Full detail</p>
              {preparing === 'expanded' && <Loader2 className="size-3.5 animate-spin text-muted-foreground" />}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">Expanded — includes all ledger balances under each group</p>
          </button>
        </div>

        {!preparing && (
          <button onClick={onClose} className="mt-4 w-full text-xs text-muted-foreground hover:text-foreground transition-colors py-1.5 cursor-pointer">
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Recursive account-group rows (screen) ── */
function AccountRows({ items = [], isCredit = false, grossCredit = false, depth = 0, startDate, endDate, onLedgerClick, expandAll }) {
  const [expanded, setExpanded] = useState({});
  const itemsRef = useRef(items);
  itemsRef.current = items;

  useEffect(() => {
    if (expandAll === null || expandAll === undefined) return;
    setExpanded(itemsRef.current.reduce((acc, item) => ({ ...acc, [item.id]: expandAll }), {}));
  }, [expandAll]);

  const toggle = useCallback((id) => setExpanded((prev) => ({ ...prev, [id]: !prev[id] })), []);

  if (!items.length) return null;

  return items
    .filter(hasNonZeroBalance)
    .map((item) => {
    const bal = Number(item.balance || 0);
    const hasChildren = item.children?.length > 0;
    const isExpanded = !!expanded[item.id];
    const pl = 16 + depth * 20;

    return (
      <Fragment key={item.id}>
        <tr className="hover:bg-accent/30 cursor-pointer transition-colors duration-150 group" onClick={() => toggle(item.id)}>
          <td className="py-2 pr-4 text-sm" style={{ paddingLeft: pl }}>
            <span className="inline-flex items-center gap-1.5">
              <span className="text-muted-foreground group-hover:text-foreground transition-colors flex-shrink-0">
                {isExpanded ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
              </span>
              <span className={depth === 0 ? 'font-semibold text-foreground' : 'font-medium text-foreground/80'}>
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
          <AccountRows items={item.children} isCredit={isCredit} grossCredit={grossCredit} depth={depth + 1}
            startDate={startDate} endDate={endDate} onLedgerClick={onLedgerClick} expandAll={expandAll} />
        )}
        {isExpanded && !hasChildren && (
          <LedgerRows groupId={item.id} startDate={startDate} endDate={endDate} onLedgerClick={onLedgerClick} grossCredit={grossCredit} />
        )}
      </Fragment>
    );
  });
}

const SectionHeader = ({ label }) => (
  <tr className="bg-accent">
    <td className="px-4 py-2 font-semibold text-accent-foreground text-xs uppercase tracking-wider" colSpan={3}>{label}</td>
  </tr>
);

const AmountRow = ({ label, debit, credit }) => (
  <tr className="hover:bg-accent/30 transition-colors">
    <td className="py-1.5 text-sm text-muted-foreground" style={{ paddingLeft: 32, paddingRight: 16 }}>{label}</td>
    <td className="px-3 py-1.5 text-right text-sm tabular-nums text-foreground">{debit != null ? fmt(debit) : ''}</td>
    <td className="px-3 py-1.5 text-right text-sm tabular-nums text-foreground">{credit != null ? fmt(credit) : ''}</td>
  </tr>
);

const SubtotalRow = ({ label, debit, credit }) => (
  <tr className="bg-muted/50 border-t border-b border-border">
    <td className="px-4 py-2 text-sm font-semibold text-foreground">{label}</td>
    <td className="px-3 py-2 text-right text-sm tabular-nums font-semibold text-foreground">{debit != null ? fmt(debit) : ''}</td>
    <td className="px-3 py-2 text-right text-sm tabular-nums font-semibold text-foreground">{credit != null ? fmt(credit) : ''}</td>
  </tr>
);

const ProfitRow = ({ label, value }) => {
  const isProfit = Number(value) >= 0;
  return (
    <tr className={`border-t-2 border-border font-bold ${isProfit ? 'bg-emerald-50' : 'bg-rose-50'}`}>
      <td className="px-4 py-2.5 text-sm">
        <span className="inline-flex items-center gap-2">
          {isProfit ? <TrendingUp className="size-4 text-emerald-600" /> : <TrendingDown className="size-4 text-rose-600" />}
          <span className={isProfit ? 'text-emerald-800' : 'text-rose-800'}>{label}</span>
        </span>
      </td>
      <td className="px-3 py-2.5 text-right tabular-nums text-sm font-bold text-rose-700">{!isProfit ? fmt(value) : ''}</td>
      <td className="px-3 py-2.5 text-right tabular-nums text-sm font-bold text-emerald-700">{isProfit ? fmt(value) : ''}</td>
    </tr>
  );
};

/* ═══════════════════════════════════════════════════════════════════════════
   Main component
═══════════════════════════════════════════════════════════════════════════ */
export default function ProfitLossCal() {
  const [startDate, setStartDate]   = useState(firstOfYear);
  const [endDate, setEndDate]       = useState(today);
  const [data, setData]             = useState(null);
  const [error, setError]           = useState('');
  const [loading, setLoading]       = useState(false);
  const [modalLedger, setModalLedger]   = useState(null);
  const [scope, setScope]               = useState('all');
  const [selectedRetailIds, setSelectedRetailIds] = useState([]);
  const [expandAll, setExpandAll]       = useState(null);
  const [showPrintModal, setShowPrintModal] = useState(false);
  const [companyName, setCompanyName]   = useState('');

  const user = JSON.parse(sessionStorage.getItem('user') || '{}');
  const canViewCombined = user.is_superuser || ['admin', 'super admin'].includes((user.role || '').toLowerCase());

  useEffect(() => {
    fetchCompanies().then((res) => {
      const results = res.data?.results || res.data || [];
      if (results.length > 0) setCompanyName(results[0].company_name || '');
    }).catch(() => {});
  }, []);

  const fetchData = useCallback(() => {
    if (!isValidDateRange(startDate, endDate)) { setError('From date cannot be after To date.'); return; }
    if (scope === 'selected' && selectedRetailIds.length === 0) {
      setError("Select at least one retail, or choose 'All retails (combined)'."); return;
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
  }, [startDate, endDate, scope, selectedRetailIds]);

  useEffect(() => { fetchData(); }, []);

  /* ── Print: builds HTML and opens via printReport (new window, multi-page safe) ── */
  const handlePrint = useCallback(async (mode) => {
    if (!data) return;

    let ledgersByGroupId = {};

    if (mode === 'expanded') {
      const allLeafIds = [
        ...collectLeafGroupIds(data.income || []),
        ...collectLeafGroupIds(data.purchases_tree || []),
        ...collectLeafGroupIds(data.direct_expenses || []),
        ...collectLeafGroupIds(data.indirect_expenses || []),
      ];
      const results = await Promise.all(
        allLeafIds.map((id) =>
          apiClient
            .get(`/accounting/api/pnl-group-ledgers/?group_id=${id}&start_date=${startDate}&end_date=${endDate}`)
            .then((res) => ({ id, ledgers: res.data.ledgers || [] }))
            .catch(() => ({ id, ledgers: [] }))
        )
      );
      for (const { id, ledgers } of results) ledgersByGroupId[id] = ledgers;
    }

    const html = buildPnlHtml(data, ledgersByGroupId);

    printReport({
      title: 'Profit & Loss Account',
      subtitle: `${toDdMm(startDate)} to ${toDdMm(endDate)}`,
      company: companyName,
      html,
      extraCss: PNL_EXTRA_CSS,
    });
  }, [data, startDate, endDate, companyName]);

  const toggleExpandAll = () => setExpandAll((prev) => (prev === true ? false : true));

  return (
    <div className="flex flex-col gap-4 max-w-3xl mx-auto w-full">

      {/* ── Toolbar ── */}
      <div className="flex flex-wrap items-end gap-2.5 p-4 bg-muted/30 rounded-lg border border-border">
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
            scope={scope} selectedIds={selectedRetailIds}
            onChange={({ scope: s, selectedIds }) => { setScope(s); setSelectedRetailIds(selectedIds); }}
          />
        )}
        <Button size="sm" onClick={fetchData} disabled={loading} className="h-9">
          {loading ? <Loader2 className="size-4 animate-spin" /> : 'Show'}
        </Button>

        {data && (
          <>
            <div className="w-px self-stretch bg-border mx-0.5" />
            <Button size="sm" variant="ghost" className="h-9 text-xs gap-1.5" onClick={toggleExpandAll}>
              {expandAll === true
                ? <><ChevronDown className="size-3.5" />Collapse All</>
                : <><ChevronRight className="size-3.5" />Expand All</>}
            </Button>
            <Button size="sm" variant="outline" className="h-9 gap-1.5" onClick={() => setShowPrintModal(true)}>
              <Printer className="size-3.5" />Print
            </Button>
          </>
        )}
      </div>

      <p className="text-xs text-muted-foreground -mt-2">
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
              <SectionHeader label="Income" />
              <AmountRow label="Gross Sales" credit={data.gross_sales} />
              {Number(data.sales_return) > 0 && <AmountRow label="(−) Sales Returns" debit={data.sales_return} />}
              <SubtotalRow label="Net Sales Revenue" credit={data.sales_revenue} />
              <AccountRows items={data.income} isCredit startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} expandAll={expandAll} />

              <SectionHeader label="Cost of Goods Sold" />
              <AmountRow label="Opening Stock" debit={data.opening_stock} />
              <AccountRows items={data.purchases_tree || []} isCredit={false} startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} expandAll={expandAll} />
              {Number(data.transfer_in) > 0 && <AmountRow label="(+) Transfers In (from other retails)" debit={data.transfer_in} />}
              {Number(data.transfer_out) > 0 && <AmountRow label="(−) Transfers Out (to other retails)" credit={data.transfer_out} />}
              <AmountRow label="(−) Closing Stock" credit={data.closing_stock} />
              <SubtotalRow label="Total COGS" debit={data.cogs} />

              <SectionHeader label="Direct Expenses" />
              <AccountRows items={data.direct_expenses} startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} expandAll={expandAll} />
              <SubtotalRow label="Total Direct Expenses" debit={data.direct_expenses_total} />

              <ProfitRow label={Number(data.gross_profit) >= 0 ? 'Gross Profit' : 'Gross Loss'} value={data.gross_profit} />

              <SectionHeader label="Indirect Expenses" />
              <AccountRows items={data.indirect_expenses} startDate={startDate} endDate={endDate} onLedgerClick={setModalLedger} expandAll={expandAll} />
              <SubtotalRow label="Total Indirect Expenses" debit={data.indirect_expenses_total} />

              <ProfitRow label={Number(data.net_profit) >= 0 ? 'Net Profit' : 'Net Loss'} value={data.net_profit} />
            </tbody>
          </table>
        </div>
      )}

      {showPrintModal && (
        <PrintModal onClose={() => setShowPrintModal(false)} onPrint={handlePrint} />
      )}
      {modalLedger && (
        <TransactionModal ledger={modalLedger} startDate={startDate} endDate={endDate} onClose={() => setModalLedger(null)} />
      )}
    </div>
  );
}
