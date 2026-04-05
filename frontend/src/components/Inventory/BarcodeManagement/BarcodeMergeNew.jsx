import React, { useState } from 'react';
import { useF4Submit } from "@/hooks/useF4Submit";

const BarcodeMerge = () => {
  const [showTable, setShowTable] = useState(true);
  const [dateOption, setDateOption] = useState('month');
  const [fromDate, setFromDate] = useState('01/04/2024');
  const [toDate, setToDate] = useState('14/03/2025');
  const [month, setMonth] = useState('MAR');
  const [year, setYear] = useState('2025');
  
  const handleSubmit = (e) => {
    e.preventDefault();
    setShowTable(true);
  };

  useF4Submit(handleSubmit);

  const reportData = [
    {
      date: '12/03/2025',
      oldBarcode: '1101978241',
      oldItem: 'G&G',
      oldItemDesc: 'Gold Bangles 22K',
      oldGw: '27.420',
      oldNw: '26.190',
      oldDiaWt: '',
      oldOthCt: '',
      oldOthGm: '1.230',
      newBarcode: '1354627488',
      newItem: 'JOT',
      newItemDesc: 'Jadau Otta 22K',
      newGw: '3.210',
      newNw: '2.830',
      newDiaWt: '',
      newOthCt: '',
      newOthGm: '0.380'
    },
    {
      date: '11/03/2025',
      oldBarcode: '1169492387',
      oldItem: 'PB',
      oldItemDesc: 'Polki Bangle 18K',
      oldGw: '41.270',
      oldNw: '34.680',
      oldDiaWt: '4.715',
      oldOthCt: '18.450',
      oldOthGm: '1.960',
      newBarcode: '1372072287',
      newItem: 'G&G',
      newItemDesc: 'Gold Bangles 22K',
      newGw: '24.210',
      newNw: '23.360',
      newDiaWt: '',
      newOthCt: '',
      newOthGm: '0.850'
    },
    {
      date: '11/03/2025',
      oldBarcode: '1169492387',
      oldItem: 'PB',
      oldItemDesc: 'Polki Bangle 18K',
      oldGw: '41.270',
      oldNw: '34.680',
      oldDiaWt: '4.715',
      oldOthCt: '18.450',
      oldOthGm: '1.960',
      newBarcode: '1239105219',
      newItem: 'PB',
      newItemDesc: 'Polki Bangle 18K',
      newGw: '35.230',
      newNw: '30.720',
      newDiaWt: '3.510',
      newOthCt: '18.450',
      newOthGm: '0.220'
    },
    {
      date: '02/03/2025',
      oldBarcode: '1287826671',
      oldItem: 'GAS',
      oldItemDesc: 'Half Set - A Series 22K',
      oldGw: '113.760',
      oldNw: '105.290',
      oldDiaWt: '2.100',
      oldOthCt: '34.200',
      oldOthGm: '1.210',
      newBarcode: '1285061032',
      newItem: 'PoHS',
      newItemDesc: 'Polki Half Set 18K',
      newGw: '6.040',
      newNw: '3.960',
      newDiaWt: '1.205',
      newOthCt: '',
      newOthGm: '1.040'
    },
    {
      date: '02/03/2025',
      oldBarcode: '1287826671',
      oldItem: 'GAS',
      oldItemDesc: 'Half Set - A Series 22K',
      oldGw: '113.760',
      oldNw: '105.290',
      oldDiaWt: '2.100',
      oldOthCt: '34.200',
      oldOthGm: '1.210',
      newBarcode: '1143562938',
      newItem: 'JOT',
      newItemDesc: 'Jadau Otta 22K',
      newGw: '7.840',
      newNw: '7.060',
      newDiaWt: '0.230',
      newOthCt: '',
      newOthGm: '0.560'
    },
    {
      date: '02/03/2025',
      oldBarcode: '1287826671',
      oldItem: 'GAS',
      oldItemDesc: 'Half Set - A Series 22K',
      oldGw: '113.760',
      oldNw: '105.290',
      oldDiaWt: '2.100',
      oldOthCt: '34.200',
      oldOthGm: '1.210',
      newBarcode: '1376727570',
      newItem: 'GAS',
      newItemDesc: 'Half Set - A Series 22K',
      newGw: '95.590',
      newNw: '87.330',
      newDiaWt: '1.870',
      newOthCt: '34.200',
      newOthGm: '1.050'
    },
    {
      date: '04/03/2025',
      oldBarcode: '1363913026',
      oldItem: 'DNK',
      oldItemDesc: 'Diamond Necklace 18K',
      oldGw: '26.360',
      oldNw: '25.800',
      oldDiaWt: '2.815',
      oldOthCt: '',
      oldOthGm: '',
      newBarcode: '414695',
      newItem: 'GGH',
      newItemDesc: 'GHARI 22K',
      newGw: '10.000',
      newNw: '10.000',
      newDiaWt: '',
      newOthCt: '',
      newOthGm: ''
    },
    {
      date: '04/03/2025',
      oldBarcode: '1363913026',
      oldItem: 'DNK',
      oldItemDesc: 'Diamond Necklace 18K',
      oldGw: '26.360',
      oldNw: '25.800',
      oldDiaWt: '2.815',
      oldOthCt: '',
      oldOthGm: '',
      newBarcode: '1203932209',
      newItem: 'DNK',
      newItemDesc: 'Diamond Necklace 18K',
      newGw: '19.760',
      newNw: '19.200',
      newDiaWt: '2.815',
      newOthCt: '',
      newOthGm: ''
    },
    {
      date: '09/03/2025',
      oldBarcode: '1366303239',
      oldItem: 'GAS',
      oldItemDesc: 'Half Set - A Series 22K',
      oldGw: '102.150',
      oldNw: '97.580',
      oldDiaWt: '',
      oldOthCt: '123.400',
      oldOthGm: '19.690',
      newBarcode: '1408401018',
      newItem: 'DNK',
      newItemDesc: 'Diamond Necklace 18K',
      newGw: '6.600',
      newNw: '6.600',
      newDiaWt: '',
      newOthCt: '',
      newOthGm: ''
    },
    {
      date: '09/03/2025',
      oldBarcode: '1366303239',
      oldItem: 'GAS',
      oldItemDesc: 'Half Set - A Series 22K',
      oldGw: '102.150',
      oldNw: '97.580',
      oldDiaWt: '',
      oldOthCt: '123.400',
      oldOthGm: '19.690',
      newBarcode: '1027155820',
      newItem: 'GAS',
      newItemDesc: 'Half Set - A Series 22K',
      newGw: '101.400',
      newNw: '96.930',
      newDiaWt: '',
      newOthCt: '123.400',
      newOthGm: '19.790'
    },
    {
      date: '09/03/2025',
      oldBarcode: '1366303239',
      oldItem: 'GAS',
      oldItemDesc: 'Half Set - A Series 22K',
      oldGw: '102.150',
      oldNw: '97.580',
      oldDiaWt: '',
      oldOthCt: '123.400',
      oldOthGm: '19.690',
      newBarcode: '1170668429',
      newItem: 'GHS',
      newItemDesc: 'Half Set - A Series 22K',
      newGw: '0.750',
      newNw: '0.650',
      newDiaWt: '',
      newOthCt: '',
      newOthGm: '0.100'
    }
  ];

  // Calculate totals
  const totals = reportData.reduce((acc, row) => {
    return {
      oldGw: (parseFloat(acc.oldGw) + parseFloat(row.oldGw)).toFixed(3),
      oldNw: (parseFloat(acc.oldNw) + parseFloat(row.oldNw)).toFixed(3),
      oldDiaWt: row.oldDiaWt ? (parseFloat(acc.oldDiaWt) + parseFloat(row.oldDiaWt)).toFixed(3) : acc.oldDiaWt,
      oldOthCt: row.oldOthCt ? (parseFloat(acc.oldOthCt) + parseFloat(row.oldOthCt)).toFixed(3) : acc.oldOthCt,
      oldOthGm: row.oldOthGm ? (parseFloat(acc.oldOthGm) + parseFloat(row.oldOthGm)).toFixed(3) : acc.oldOthGm,
      newGw: (parseFloat(acc.newGw) + parseFloat(row.newGw)).toFixed(3),
      newNw: (parseFloat(acc.newNw) + parseFloat(row.newNw)).toFixed(3),
      newDiaWt: row.newDiaWt ? (parseFloat(acc.newDiaWt) + parseFloat(row.newDiaWt)).toFixed(3) : acc.newDiaWt,
      newOthCt: row.newOthCt ? (parseFloat(acc.newOthCt) + parseFloat(row.newOthCt)).toFixed(3) : acc.newOthCt,
      newOthGm: row.newOthGm ? (parseFloat(acc.newOthGm) + parseFloat(row.newOthGm)).toFixed(3) : acc.newOthGm,
    };
  }, {
    oldGw: "0.000",
    oldNw: "0.000",
    oldDiaWt: "0.000",
    oldOthCt: "0.000",
    oldOthGm: "0.000",
    newGw: "0.000",
    newNw: "0.000",
    newDiaWt: "0.000",
    newOthCt: "0.000",
    newOthGm: "0.000"
  });


  const displayTotals = {
    oldGw: "310.960",
    oldNw: "249.540",
    oldDiaWt: "9.630",
    oldOthCt: "176.050",
    oldOthGm: "24.290",
    newGw: "310.960",
    newNw: "249.540",
    newDiaWt: "9.630",
    newOthCt: "176.050",
    newOthGm: "24.290"
  };

  return (
    <div className="w-full max-w-screen-lg mx-auto bg-white">
      <div className="text-center text-violet-700 font-bold mb-2">
        <a href="#" className="underline">BARCODE MERGE REPORT</a>
      </div>
      
      <form onSubmit={handleSubmit} className="flex items-center justify-center gap-2 mb-4">
        <div className="flex items-center">
          <input
            type="radio"
            id="from"
            name="dateType"
            checked={dateOption === 'from'}
            onChange={() => setDateOption('from')}
            className="mr-1"
          />
          <label htmlFor="from" className="mr-2">FROM</label>
          <input
            type="text"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            className="border p-1 w-24 text-sm"
          />
          <span className="mx-1">TO</span>
          <input
            type="text"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            className="border p-1 w-24 text-sm mr-1"
          />
        </div>
        
        <div className="flex items-center">
          <input
            type="radio"
            id="month"
            name="dateType"
            checked={dateOption === 'month'}
            onChange={() => setDateOption('month')}
            className="mr-1"
          />
          <label htmlFor="month" className="mr-2">MONTH</label>
          <select 
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="border p-1 text-sm w-16 mr-1"
          >
            <option value="JAN">JAN</option>
            <option value="FEB">FEB</option>
            <option value="MAR">MAR</option>
            <option value="APR">APR</option>
            <option value="MAY">MAY</option>
            <option value="JUN">JUN</option>
            <option value="JUL">JUL</option>
            <option value="AUG">AUG</option>
            <option value="SEP">SEP</option>
            <option value="OCT">OCT</option>
            <option value="NOV">NOV</option>
            <option value="DEC">DEC</option>
          </select>
          
          <span className="mr-1">YEAR</span>
          <select 
            value={year}
            onChange={(e) => setYear(e.target.value)}
            className="border p-1 text-sm w-16 mr-2"
          >
            <option value="2022">2022</option>
            <option value="2023">2023</option>
            <option value="2024">2024</option>
            <option value="2025">2025</option>
          </select>
        </div>
        
        <button
          type="submit"
          className="bg-violet-500 text-white px-3 py-1 rounded"
        >
          GO
        </button>
        
        <div className="ml-8">
          <a href="#" className="text-violet-600 underline text-sm">[PRINT]</a>
        </div>
      </form>
      
      {showTable && (
        <div>
          <div className="text-center font-bold mb-2">
            BARCODE MERGE REPORT
          </div>
          <div className="text-center mb-4">
            From : 01/03/2025 To : 31/03/2025
          </div>
          
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-xs">
              <thead>
                <tr className="bg-gray-100">
                  <th colSpan="6" className="border px-2 py-1 text-center">Old Detail</th>
                  <th colSpan="6" className="border px-2 py-1 text-center">New Detail</th>
                </tr>
                <tr className="bg-gray-100">
                  <th className="border px-2 py-1">Date</th>
                  <th className="border px-2 py-1">Barcode</th>
                  <th className="border px-2 py-1">Item</th>
                  <th className="border px-2 py-1">Gw</th>
                  <th className="border px-2 py-1">Nw</th>
                  <th className="border px-2 py-1">Dia Wt</th>
                  <th className="border px-2 py-1">Oth Ct</th>
                  <th className="border px-2 py-1">Oth Gm</th>
                  <th className="border px-2 py-1">Barcode</th>
                  <th className="border px-2 py-1">Item</th>
                  <th className="border px-2 py-1">Gw</th>
                  <th className="border px-2 py-1">Nw</th>
                  <th className="border px-2 py-1">Dia Wt</th>
                  <th className="border px-2 py-1">Oth Ct</th>
                  <th className="border px-2 py-1">Oth Gm</th>
                </tr>
              </thead>
              <tbody>
                {reportData.map((row, index) => (
                  <tr key={index}>
                    <td className="border px-2 py-1">{row.date}</td>
                    <td className="border px-2 py-1">{row.oldBarcode}</td>
                    <td className="border px-2 py-1">
                      {row.oldItem}
                      <div className="text-gray-600 italic">{row.oldItemDesc}</div>
                    </td>
                    <td className="border px-2 py-1 text-right">{row.oldGw}</td>
                    <td className="border px-2 py-1 text-right">{row.oldNw}</td>
                    <td className="border px-2 py-1 text-right">{row.oldDiaWt}</td>
                    <td className="border px-2 py-1 text-right">{row.oldOthCt}</td>
                    <td className="border px-2 py-1 text-right">{row.oldOthGm}</td>
                    <td className="border px-2 py-1">{row.newBarcode}</td>
                    <td className="border px-2 py-1">
                      {row.newItem}
                      <div className="text-gray-600 italic">{row.newItemDesc}</div>
                    </td>
                    <td className="border px-2 py-1 text-right">{row.newGw}</td>
                    <td className="border px-2 py-1 text-right">{row.newNw}</td>
                    <td className="border px-2 py-1 text-right">{row.newDiaWt}</td>
                    <td className="border px-2 py-1 text-right">{row.newOthCt}</td>
                    <td className="border px-2 py-1 text-right">{row.newOthGm}</td>
                  </tr>
                ))}
                <tr className="font-bold bg-gray-100">
                  <td className="border px-2 py-1 text-right" colSpan="3">Total</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.oldGw}</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.oldNw}</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.oldDiaWt}</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.oldOthCt}</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.oldOthGm}</td>
                  <td className="border px-2 py-1" colSpan="2"></td>
                  <td className="border px-2 py-1 text-right">{displayTotals.newGw}</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.newNw}</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.newDiaWt}</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.newOthCt}</td>
                  <td className="border px-2 py-1 text-right">{displayTotals.newOthGm}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default BarcodeMerge;