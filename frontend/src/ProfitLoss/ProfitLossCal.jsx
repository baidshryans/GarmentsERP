
import React, { useEffect, useState } from 'react';

const ProfitLossCal = () => {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/accounting/api/pnl')
      .then((res) => res.json())
      .then(setData)
      .catch(() => setError('Failed to fetch P&L data.'))
      .finally(() => setLoading(false));
  }, []);

  const formatAmount = (value) => {
    return value && !isNaN(value)
      ? value.toLocaleString('en-IN', { minimumFractionDigits: 2 })
      : '0';
  };

  const renderAccountRows = (items, isCredit = false) =>
    items.map((item) => (
      <tr key={item.id} className="hover:bg-gray-50">
        <td className="px-4 py-2 text-sm">{item.name}</td>
        <td className="px-4 py-2 text-right text-sm font-mono">
          {!isCredit ? formatAmount(item.balance) : '-'}
        </td>
        <td className="px-4 py-2 text-right text-sm font-mono">
          {isCredit ? formatAmount(item.balance) : '-'}
        </td>
      </tr>
    ));

  if (loading) return <div className="p-6 text-gray-600">Loading...</div>;
  if (error || !data) return <div className="p-6 text-red-500">{error}</div>;

  return (
    <div className="min-h-screen w-full p-4 bg-white print:p-0">
      {/* Centered Heading */}
      <h2 className="text-xl font-semibold text-center mb-4 text-gray-700 print:text-lg">
        Profit & Loss Statement
      </h2>

      <div className="w-full overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gray-100">
              <th className="px-4 py-3 text-left border-b border-gray-300 text-gray-700">Particulars</th>
              <th className="px-4 py-3 text-right border-b border-gray-300 text-gray-700">Amount</th>
              <th className="px-4 py-3 text-right border-b border-gray-300 text-gray-700">Amount</th>
            </tr>
          </thead>
          <tbody>
            {/* Income Section */}
            <tr className="bg-gray-300">
              <td className="px-4 py-2 font-medium text-gray-700" colSpan="3">Income</td>
            </tr>
            {renderAccountRows(data.income, true)}

            {/* COGS Section */}
            <tr className="bg-gray-300">
              <td className="px-4 py-2 font-medium text-gray-700" colSpan="3">Cost of Goods Sold</td>
            </tr>
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-2">Opening Stock</td>
              <td className="px-4 py-2 text-right font-mono">{formatAmount(data.opening_stock)}</td>
              <td className="px-4 py-2 text-right">-</td>
            </tr>
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-2">Purchase Account</td>
              <td className="px-4 py-2 text-right font-mono">{formatAmount(data.purchases)}</td>
              <td className="px-4 py-2 text-right">-</td>
            </tr>
            <tr className="hover:bg-gray-50">
              <td className="px-4 py-2">Closing Stock</td>
              <td className="px-4 py-2 text-right font-mono text-red-500">{formatAmount(data.closing_stock)}</td>
              <td className="px-4 py-2 text-right">-</td>
            </tr>
            {renderAccountRows(data.expenses.filter(e => e.name === 'Making Charge Paid'), false)}
            {renderAccountRows(data.expenses.filter(e => e.name === 'Direct Expenses'), false)}

            {/* Gross Profit */}
            <tr className="bg-green-100">
              <td className="px-4 py-2 font-medium text-gray-700">Gross Profit</td>
              <td className="px-4 py-2 text-right font-mono">
                {data.gross_profit < 0 ? '-' : formatAmount(data.gross_profit)}
              </td>
              <td className="px-4 py-2 text-right font-mono">
                {data.gross_profit < 0 ? formatAmount(Math.abs(data.gross_profit)) : '-'}
              </td>
            </tr>

            {/* Indirect Expenses */}
            <tr className="bg-gray-100">
              <td className="px-4 py-2 font-medium text-gray-700" colSpan="3">Indirect Expenses</td>
            </tr>
            {renderAccountRows(
              data.expenses.find(e => e.name === 'Indirect Expenses')?.children || [],
              false
            )}

            {/* Net Profit or Loss */}
            <tr className="bg-green-100">
              <td className="px-4 py-2 font-medium text-gray-700">
                {data.net_profit < 0 ? 'Net Loss' : 'Net Profit'}
              </td>
              <td className="px-4 py-2 text-right font-mono">
                {data.net_profit < 0 ? '-' : formatAmount(data.net_profit)}
              </td>
              <td className="px-4 py-2 text-right font-mono">
                {data.net_profit < 0 ? formatAmount(Math.abs(data.net_profit)) : '-'}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Print Button */}
      {/* <div className="flex justify-end mt-4 print:hidden">
        <button
          onClick={() => window.print()}
          className="bg-primary hover:bg-violet-300 text-white w-24 px-4 py-2 rounded text-sm shadow-sm transition-colors"
        >
          Print 
        </button>
      </div> */}
    </div>
  );
};

export default ProfitLossCal;