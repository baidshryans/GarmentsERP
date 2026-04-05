import React, { useState, useEffect } from 'react';
import { Search, Calendar, FileText, Download } from 'lucide-react';
import { fetchItemWiseBarcode } from './services/apiService';

const ItemwiseBarcodeReport = () => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({
    fromDate: '2024-02-01',
    toDate: '2025-02-01',
    searchTerm: ''
  });

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      // const response = await fetch(
      //   `http://127.0.0.1:8000/inventory/api/item-barcode-report/?from_date=${filters.fromDate}&to_date=${filters.toDate}`
      // );
     const result = await fetchItemWiseBarcode(filters.fromDate,filters.toDate);

      // if (!response.ok) {
      //   throw new Error('Failed to fetch data');
      // }
      // const result = await response.json();
      setData(result);
    } catch (err) {
      setError(err.message);
      // Fallback to sample data for demonstration
      setData([
        {
          "barcodemain_set": [],
          "short_code": "GNR"
        },
        {
          "barcodemain_set": [
            {
              "barcode": "9820622078093",
              "stone": [
                {
                  "id": 18,
                  "pcs": 1,
                  "ct": 1.0,
                  "gw": 0.2,
                  "rate": 1,
                  "amt": 1,
                  "barcode": 5,
                  "packet": 668,
                  "item": 33
                }
              ],
              "other": []
            },
            {
              "barcode": "8456079896747",
              "stone": [
                {
                  "id": 6,
                  "pcs": 1,
                  "ct": 0.01,
                  "gw": 0.0,
                  "rate": 2,
                  "amt": 0,
                  "barcode": 6,
                  "packet": 656,
                  "item": 33
                },
                {
                  "id": 7,
                  "pcs": 2,
                  "ct": 0.02,
                  "gw": 0.1,
                  "rate": 3,
                  "amt": 50,
                  "barcode": 6,
                  "packet": 657,
                  "item": 34
                }
              ],
              "other": []
            }
          ],
          "short_code": "APT"
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleFilterChange = (field, value) => {
    setFilters(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleSearch = () => {
    fetchData();
  };

  const filteredData = data.filter(item =>
    item.short_code?.toLowerCase().includes(filters.searchTerm.toLowerCase()) ||
    item.barcodemain_set?.some(barcode =>
      barcode.barcode?.includes(filters.searchTerm)
    )
  );

  const calculateTotals = (stones) => {
    return stones.reduce((acc, stone) => ({
      pcs: acc.pcs + (stone.pcs || 0),
      ct: acc.ct + (stone.ct || 0),
      gw: acc.gw + (stone.gw || 0),
      amt: acc.amt + (stone.amt || 0)
    }), { pcs: 0, ct: 0, gw: 0, amt: 0 });
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-semibold text-gray-800 flex items-center gap-2">
              <FileText className="h-6 w-6" />
              Itemwise Barcode Report
            </h1>
          </div>

          {/* Filters */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">From Date</label>
              <div className="relative">
                <input
                  type="date"
                  value={filters.fromDate}
                  onChange={(e) => handleFilterChange('fromDate', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  style={{
                    colorScheme: 'light'
                  }}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">To Date</label>
              <div className="relative">
                <input
                  type="date"
                  value={filters.toDate}
                  onChange={(e) => handleFilterChange('toDate', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  style={{
                    colorScheme: 'light'
                  }}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search by code or barcode..."
                  value={filters.searchTerm}
                  onChange={(e) => handleFilterChange('searchTerm', e.target.value)}
                  className="w-full px-3 py-2 pl-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  style={{
                    colorScheme: 'light'
                  }}
                />
              </div>
            </div>
            <div className="flex items-end">
              <button
                onClick={handleSearch}
                className="w-28 px-3 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors disabled:bg-gray-400"
              >
                Search
              </button>
            </div>
          </div>
        </div>

        {/* Loading and Error States */}
        {loading && (
          <div className="bg-white rounded-lg shadow-sm p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading report data...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <p className="text-red-700">Error: {error}</p>
            <p className="text-sm text-red-600 mt-1">Showing sample data for demonstration</p>
          </div>
        )}

        {/* Report Table */}
        {!loading && (
          <div className="bg-white rounded-lg shadow-sm overflow-hidden border border-gray-400">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse border border-gray-400">
                <thead className="bg-gray-50">
                  <tr className="border border-gray-300">
                    <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300">Barcode</th>
                    <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300">Packet</th>
                    <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300">Pcs</th>
                    <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300">Gw</th>
                    <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300">Nw</th>
                    <th colSpan="4" className="px-4 py-3 text-center text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300 bg-violet-50">Stone</th>
                    <th colSpan="4" className="px-4 py-3 text-center text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300 bg-green-50">Other</th>
                    <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300">Making</th>
                    <th className="px-4 py-3 text-left text-xs font-bold text-gray-500 uppercase tracking-wider border border-gray-300">Value</th>
                  </tr>
                  <tr className="bg-gray-50 border border-gray-300">
                    <th className="px-4 py-2 border border-gray-300"></th>
                    <th className="px-4 py-2 border border-gray-300"></th>
                    <th className="px-4 py-2 border border-gray-300"></th>
                    <th className="px-4 py-2 border border-gray-300"></th>
                    <th className="px-4 py-2 border border-gray-300"></th>
                    <th className="px-2 py-2 text-xs text-gray-500 border border-gray-300 bg-violet-50">Pcs</th>
                    <th className="px-2 py-2 text-xs text-gray-500 border border-gray-300 bg-violet-50">Weight</th>
                    <th className="px-2 py-2 text-xs text-gray-500 border border-gray-300 bg-violet-50">Rate</th>
                    <th className="px-2 py-2 text-xs text-gray-500 border border-gray-300 bg-violet-50">Value</th>
                    <th className="px-2 py-2 text-xs text-gray-500 border border-gray-300 bg-green-50">Item</th>
                    <th className="px-2 py-2 text-xs text-gray-500 border border-gray-300 bg-green-50">Pcs</th>
                    <th className="px-2 py-2 text-xs text-gray-500 border border-gray-300 bg-green-50">Weight</th>
                    <th className="px-2 py-2 text-xs text-gray-500 border border-gray-300 bg-green-50">Rate</th>
                    <th className="px-4 py-2 border border-gray-300"></th>
                    <th className="px-4 py-2 border border-gray-300"></th>
                  </tr>
                </thead>
                <tbody className="bg-white">
                  {filteredData.map((item, itemIndex) => {
                    if (!item.barcodemain_set || item.barcodemain_set.length === 0) {
                      return (
                        <React.Fragment key={itemIndex}>
                          {/* Short Code Row */}
                          <tr className="bg-gray-200 border border-gray-400">
                            <td colSpan="15" className="px-4 py-3 text-sm font-bold text-gray-800 border border-gray-400">
                              {item.short_code}
                            </td>
                          </tr>
                          {/* No Data Row */}
                          <tr className="hover:bg-gray-50 border border-gray-400">
                            <td className="px-4 py-3 text-sm text-gray-500 border border-gray-400">No barcode available</td>
                            <td colSpan="14" className="px-4 py-3 text-sm text-gray-500 italic border border-gray-400">No barcode data available</td>
                          </tr>
                        </React.Fragment>
                      );
                    }

                    return (
                      <React.Fragment key={itemIndex}>
                        {/* Short Code Row */}
                        <tr className="bg-gray-200 border border-gray-400">
                          <td colSpan="15" className="px-4 py-3 text-sm font-bold text-gray-800 border border-gray-400">
                            {item.short_code}
                          </td>
                        </tr>

                        {/* Barcode Data Rows */}
                        {item.barcodemain_set.map((barcodeItem, barcodeIndex) => {
                          const stones = barcodeItem.stone || [];
                          const others = barcodeItem.other || [];
                          const stoneTotals = calculateTotals(stones);

                          return stones.length > 0 ? stones.map((stone, stoneIndex) => (
                            <tr key={`${itemIndex}-${barcodeIndex}-${stoneIndex}`} className="hover:bg-gray-50 border border-gray-400">
                              {stoneIndex === 0 && (
                                <td 
                                  rowSpan={stones.length} 
                                  className="px-4 py-3 text-sm text-gray-900 text-center align-middle border border-gray-400 bg-gray-100 font-semibold"
                                >
                                  <div className="flex items-center justify-center h-full">
                                    {barcodeItem.barcode}
                                  </div>
                                </td>
                              )}
                              <td className="px-4 py-3 text-sm text-gray-900 border border-gray-400">{stone.packet || '-'}</td>
                              <td className="px-4 py-3 text-sm text-gray-900 border border-gray-400">{stone.pcs || 0}</td>
                              <td className="px-4 py-3 text-sm text-gray-900 border border-gray-400">{(stone.gw || 0).toFixed(3)}</td>
                              <td className="px-4 py-3 text-sm text-gray-900 border border-gray-400">{(stone.ct || 0).toFixed(3)}</td>
                              <td className="px-2 py-3 text-sm text-gray-900 border border-gray-400">{stone.pcs || 0}</td>
                              <td className="px-2 py-3 text-sm text-gray-900 border border-gray-400">{(stone.ct || 0).toFixed(3)}</td>
                              <td className="px-2 py-3 text-sm text-gray-900 border border-gray-400">{stone.rate || 0}</td>
                              <td className="px-2 py-3 text-sm text-gray-900 border border-gray-400">{(stone.amt || 0).toFixed(2)}</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              {stoneIndex === 0 && (
                                <td 
                                  rowSpan={stones.length} 
                                  className="px-4 py-3 text-sm text-gray-900 border border-gray-400 align-middle text-center bg-gray-100"
                                >
                                  22.00
                                </td>
                              )}
                              {stoneIndex === 0 && (
                                <td 
                                  rowSpan={stones.length} 
                                  className="px-4 py-3 text-sm text-gray-900 align-middle text-center bg-gray-100 border border-gray-400 font-semibold"
                                >
                                  ₹{(stoneTotals.amt * 22).toFixed(2)}
                                </td>
                              )}
                            </tr>
                          )) : (
                            <tr key={`${itemIndex}-${barcodeIndex}`} className="hover:bg-gray-50 border border-gray-400">
                              <td className="px-4 py-3 text-sm text-gray-900 text-center border border-gray-400 bg-gray-100 font-semibold">
                                {barcodeItem.barcode}
                              </td>
                              <td className="px-4 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-4 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-4 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-4 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-2 py-3 text-sm text-gray-500 border border-gray-400">-</td>
                              <td className="px-4 py-3 text-sm text-gray-500 border border-gray-400 bg-gray-100">-</td>
                              <td className="px-4 py-3 text-sm text-gray-500 bg-gray-100 border border-gray-400">-</td>
                            </tr>
                          );
                        })}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {filteredData.length === 0 && !loading && (
              <div className="text-center py-8 text-gray-500">
                No data found for the selected criteria
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ItemwiseBarcodeReport;








