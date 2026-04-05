
import React, { useState, useEffect } from 'react';
import { fetchProfitDemo } from '../services/apiService';

const ProfitLossAccount = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [expanded, setExpanded] = useState({
    income: true,
    cogs: true,
    expenses: true
  });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/accounting/api/pnl');
        if (!response.ok) throw new Error('Network response was not ok');
        const json = await response.json();

        // const result= await fetchProfitDemo();
        setData(json);
      
      } catch (err) {
        setError('Failed to fetch financial data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const formatCurrency = (value) => {
    return value?.toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }) || '0.00';
  };

  const toggleSection = (section) => {
    setExpanded(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const renderAccountItems = (items, level = 0) => {
    return items?.map(item => (
      <React.Fragment key={item.id}>
        <tr className="hover:bg-gray-50">
          <td className="px-4 py-2 border">
            <div style={{ paddingLeft: `${level * 16}px` }} className="text-sm">
              {item.name}
            </div>
          </td>
          <td className="px-4 py-2 border text-right font-mono text-sm">
            {formatCurrency(item.balance)}
          </td>
        </tr>
        {item.children && renderAccountItems(item.children, level + 1)}
      </React.Fragment>
    ));
  };

  if (loading) return (
    <div className="flex items-center justify-center h-screen text-gray-600">
      <div className="text-lg">Loading financial data...</div>
    </div>
  );

  if (error) return (
    <div className="flex items-center justify-center h-screen text-red-500">
      <div className="text-lg">{error}</div>
    </div>
  );

  if (!data) return null;

  return (
    <div className="min-h-screen bg-gray-50 p-4 print:p-0">
      <div className="max-w-screen-2xl mx-auto bg-white rounded-lg shadow-sm overflow-hidden print:shadow-none print:rounded-none">
        {/* Header */}
        <div className="p-4 border-b print:border-b-0">
          <h1 className="text-xl font-medium text-gray-700 text-center">Profit and Loss Statement</h1>
          <p className="text-gray-500 text-sm text-center">{new Date().toLocaleDateString()}</p>
        </div>

        {/* Single Table Layout */}
        <div className="p-4 print:p-0">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-gray-100">
                <th className="px-4 py-2 border text-left text-sm font-medium text-gray-700">Particulars</th>
                <th className="px-4 py-2 border text-right text-sm font-medium text-gray-700">Amount (₹)</th>
              </tr>
            </thead>
            <tbody>
              {/* Income Section */}
              <tr 
                className="bg-gray-300 hover:bg-gray-100 cursor-pointer" 
                onClick={() => toggleSection('income')}
              >
                <td className="px-4 py-2 border font-medium text-gray-700" colSpan={2}>
                  <div className="flex items-center">
                    <span className="inline-block w-6 text-gray-600">
                      {expanded.income ? '▼' : '▶'}
                    </span>
                    <span>Income</span>
                  </div>
                </td>
              </tr>
              {expanded.income && (
                <>
                  <tr>
                    <td className="px-4 py-2 border pl-10 text-sm">Sales Revenue</td>
                    <td className="px-4 py-2 border text-right font-mono text-sm">
                      {formatCurrency(data.sales_revenue)}
                    </td>
                  </tr>
                  {renderAccountItems(data.income, 2)}
                  <tr className="bg-gray-50">
                    <td className="px-4 py-2 border font-medium">Total Income</td>
                    <td className="px-4 py-2 border text-right font-mono font-medium">
                      {formatCurrency(data.sales_revenue)}
                    </td>
                  </tr>
                </>
              )}

              {/* COGS Section */}
              <tr 
                className="bg-gray-300 hover:bg-gray-100 cursor-pointer" 
                onClick={() => toggleSection('cogs')}
              >
                <td className="px-4 py-2 border font-medium text-gray-700" colSpan={2}>
                  <div className="flex items-center">
                    <span className="inline-block w-6 text-gray-600">
                      {expanded.cogs ? '▼' : '▶'}
                    </span>
                    <span>Cost of Goods Sold</span>
                  </div>
                </td>
              </tr>
              {expanded.cogs && (
                <>
                  <tr>
                    <td className="px-4 py-2 border pl-10 text-sm">Opening Inventory</td>
                    <td className="px-4 py-2 border text-right font-mono text-sm">
                      {formatCurrency(data.opening_stock)}
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 border pl-10 text-sm">Purchases</td>
                    <td className="px-4 py-2 border text-right font-mono text-sm">
                      {formatCurrency(data.purchases)}
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 border pl-10 text-sm">Purchase Returns</td>
                    <td className="px-4 py-2 border text-right font-mono text-sm">
                      {formatCurrency(data.purchase_returns)}
                    </td>
                  </tr>
                  <tr>
                    <td className="px-4 py-2 border pl-10 text-sm">Closing Inventory</td>
                    <td className="px-4 py-2 border text-right font-mono text-sm">
                      {formatCurrency(data.closing_stock)}
                    </td>
                  </tr>
                  <tr className="bg-gray-50">
                    <td className="px-4 py-2 border font-medium">Total COGS</td>
                    <td className="px-4 py-2 border text-right font-mono font-medium">
                      {formatCurrency(data.cogs)}
                    </td>
                  </tr>
                </>
              )}

              {/* Gross Profit */}
              <tr className="bg-gray-100">
                <td className="px-4 py-2 border font-medium text-gray-700">Gross Profit</td>
                <td className="px-4 py-2 border text-right font-mono font-medium">
                  {formatCurrency(data.gross_profit)}
                </td>
              </tr>

              {/* Expenses Section */}
              <tr 
                className="bg-gray-300 hover:bg-gray-100 cursor-pointer" 
                onClick={() => toggleSection('expenses')}
              >
                <td className="px-4 py-2 border font-medium text-gray-700" colSpan={2}>
                  <div className="flex items-center">
                    <span className="inline-block w-6 text-gray-600">
                      {expanded.expenses ? '▼' : '▶'}
                    </span>
                    <span>Operating Expenses</span>
                  </div>
                </td>
              </tr>
              {expanded.expenses && (
                <>
                  {renderAccountItems(data.expenses, 2)}
                  <tr className="bg-gray-50">
                    <td className="px-4 py-2 border font-medium">Total Expenses</td>
                    <td className="px-4 py-2 border text-right font-mono font-medium">
                      {formatCurrency(data.total_expenses)}
                    </td>
                  </tr>
                </>
              )}

              {/* Net Profit/Loss */}
              <tr className="bg-gray-100">
                <td className="px-4 py-2 border font-medium text-gray-700">
                  {data.net_profit >= 0 ? 'Net Profit' : 'Net Loss'}
                </td>
                <td className="px-4 py-2 border text-right font-mono font-medium">
                  {formatCurrency(data.net_profit)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Print Button */}
        {/* <div className="p-4 flex justify-end print:hidden">
          <button
            onClick={() => window.print()}
            className="px-4 py-1.5 bg-violet-400 hover:bg-gray-300 text-gray-700 text-sm font-normal rounded shadow-sm transition-colors"
          >
            Print Statement
          </button>
        </div> */}
      </div>
    </div>
  );
};

export default ProfitLossAccount;