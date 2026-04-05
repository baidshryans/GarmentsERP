import React, { useState, useEffect } from 'react';
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchJobStatusReport, getLedgers } from './services/apiService';

const JoborderReport = () => {
  const [showTable, setShowTable] = useState(false);
  const [fromDate, setFromDate] = useState('12/03/2025');
  const [toDate, setToDate] = useState('12/03/2025');
  const [karigars, setKarigars] = useState([]);

  useEffect(() => {
    async function fetchData() {
      const [karigars] = await Promise.all([getLedgers()]);
      if (karigars.success) setKarigars(karigars.data.results);
    } fetchData();
  }, []);

  // Sample JSON data for each filter section
  const [data, setData] = useState({
    karigar: [
      { id: 'all', name: 'All', checked: false },
      { id: 'aditya_rhodium', name: 'Aditya Rhodium', checked: false },
      { id: 'ajit_sasmal', name: 'Ajit Sasmal', checked: false },
      { id: 'amit_dhakar', name: 'Amit Dhakar', checked: false },
      { id: 'amit_kanjilal', name: 'Amit Kanjilal', checked: false },
      { id: 'amit_soni', name: 'Amit Soni', checked: false }
    ]
  });

  // Sample report data
  const reportData = [
    {
      date: '12/03/2025',
      barcode: 'QBC',
      subBarcode: '1101578241',
      ply: '22',
      pcs: '1',
      gw: '27.420',
      net: '26.190',
      stone: {
        code: 'Subhid Santra',
        sub: '',
        pcs: '',
        wt: '',
        rate: ''
      },
      stoneCode: '7944',
      other: {
        code: 'K0063',
        items: [
          { name: 'LK', pcs: '0', ply: '', wt: '1.230', rate: '0' },
          { name: 'MCH', pcs: '1', ply: '', wt: '0.000', rate: '1500' },
          { name: 'SC1', pcs: '13', ply: '', wt: '0.000', rate: '75' }
        ]
      },
      making: '10.00 %',
      otherAmount: '0.00',
      orderNo: '',
      invNo: '',
      invDt: ''
    },
    {
      date: '',
      barcode: 'GCH',
      subBarcode: '1120161113',
      ply: '22',
      pcs: '1',
      gw: '5.220',
      net: '1.620',
      stone: {
        code: 'Subhid Santra',
        sub: '',
        pcs: '',
        wt: '',
        rate: ''
      },
      stoneCode: '',
      other: {
        code: 'K0185',
        items: [
          { name: 'CC', pcs: '0', ply: '', wt: '3.400', rate: '0' }
        ]
      },
      making: '10.00 %',
      otherAmount: '0.00',
      orderNo: 'CA2501326',
      invNo: '',
      invDt: '02/03/2025'
    }
  ];

  // Function to handle checkbox changes
  const handleCheckboxChange = (section, itemId, fun) => {
    fun((prevData) => {
      console.log(prevData)
      const updatedSection = [...prevData];

      // Find the item and toggle its checked status
      const itemIndex = updatedSection.findIndex(item => item.id === itemId);
      if (itemIndex !== -1) {
        updatedSection[itemIndex] = {
          ...updatedSection[itemIndex],
          checked: !updatedSection[itemIndex].checked
        };
      }

      console.log(updatedSection)

      return [

        ...updatedSection
      ];
    });
  };

  // Render a checkbox section
  const renderCheckboxSection = (title, items, section) => {
    return (
      <div>
        <div className="font-bold mb-1 ">{title}</div>
        <div className="border border-gray-300 h-32 overflow-y-auto ">
          {items.map(item => (
            <div
              key={item.id}
              className={`flex items-center p-2 ${item.name === '22' && section === 'purity' && item.checked ? 'bg-violet-700 text-white' : ''}`}
            >
              <Checkbox id="fix_rate" checked={item.checked}
                onCheckedChange={(checked) => handleCheckboxChange(section, item.id)}
              />


              <label className="ml-2">{item.name}</label>
            </div>
          ))}
        </div>
      </div>
    );
  };
  const renderKarigarsSection = (title, items, section) => {
    return (
      <div>
        <div className="font-bold mb-1 ">{title}</div>
        <div className="border border-gray-300 h-32 overflow-y-auto ">
          {items.map(item => (
            <div
              key={item.id}
              className={`flex items-center p-2 ${item.name === '22' && section === 'purity' && item.checked ? 'bg-violet-700 text-white' : ''}`}
            >
              <Checkbox id="fix_rate" checked={item.checked}
                onCheckedChange={(checked) => handleCheckboxChange(section, item.id, setKarigars)}
              />


              <label className="ml-2">{item.ac_name}</label>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const onGo = () => {
    const checkedKarigars = karigars.filter(k => k.checked).map(k => k.id);
    
    console.log('Selected Karigars:', checkedKarigars);
    console.log('From Date:', fromDate);
    console.log('To Date:', toDate);
    fetchJobStatusReport(fromDate,toDate,checkedKarigars)
    
  }
  return (
    <div className="w-full max-w-6xl mx-auto font-sans">
      <div className="border border-gray-300 rounded p-4 bg-white">
        <div className="text-center font-bold text-violet-900 mb-4">KARIGAR WISE WORk ORDER REPORT</div>

        <div className="grid grid-cols-3 gap-4 mb-4">
          {renderKarigarsSection('Karigar', karigars, 'Karigar')}

        </div>

        {/* Date Range Selection */}
        <div className="flex items-center mb-6">
          <div className="flex items-center mr-4">
            <Checkbox id="fix_rate" />
            <Label className="mr-2">All</Label>
          </div>
          <div className="flex items-center mr-4">
            <Checkbox id="fix_rate" />
            <Label className="mr-2">Executed</Label>
          </div>
          <div className="flex items-center mr-4">
            <Checkbox id="fix_rate" />
            <Label className="mr-2">Not Executed</Label>
          </div>

        </div>
        <div className="flex items-center mb-6">
          <div className="flex items-center mr-4">
            <Label className="mr-2" htmlFor="date">FROM</Label>
            <Input type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="border border-gray-300 p-1 w-24" />
          </div>

          <div className="flex items-center mr-4">
            <Label className="mr-2" htmlFor="date">TO</Label>
            <Input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="border border-gray-300 p-1 w-24"
            />
          </div>
          <div className="flex items-center mr-4">
            <Label className="mr-2" htmlFor="type">Type</Label>
            <Input
              type="text"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="border border-gray-300 p-1 w-24"
            />
          </div>
          <div className="flex items-center mr-4">
            <Label className="mr-2" htmlFor="date">date</Label>
            <Input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="border border-gray-300 p-1 w-24"
            />
          </div>
          <button
            className="bg-violet-600 text-white px-4 py-1 rounded"
            onClick={onGo}
          >
            GO
          </button>
        </div>

        {/* Print options */}
        {showTable && (
          <div className="text-right text-violet-600 mb-2">
            <button className="mr-2">Print</button>
            <button>Export</button>
          </div>
        )}

        {/* Report Header and Table */}
        {showTable && (
          <div>
            <div className="text-center mb-4">
              <div className="font-bold">Karigar Wise Work Order Report of From {fromDate} To {toDate}</div>

            </div>

            {/* Main Table */}
            <div className="overflow-x-auto">
              <table className="w-full border-collapse border border-gray-300 text-sm">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="border border-gray-300 p-1">Date</th>
                    <th className="border border-gray-300 p-1">Work Order</th>
                    <th className="border border-gray-300 p-1">Design Code</th>
                    <th className="border border-gray-300 p-1">Order</th>
                    <th className="border border-gray-300 p-1">Cust Dt</th>
                    <th className="border border-gray-300 p-1">Description</th>
                    <th className="border border-gray-300 p-1" >Wt</th>
                    <th className="border border-gray-300 p-1">Size</th>
                    <th className="border border-gray-300 p-1">Rec Nw</th>
                    <th className="border border-gray-300 p-1">Remarks</th>
                    <th className="border border-gray-300 p-1">User Remarks</th>
                  </tr>

                </thead>
                <tbody>
                  {reportData.map((row, index) => (
                    <>
                      <tr key={`row-${index}`}>
                        <td className="border border-gray-300 p-1">{row.date}</td>
                        <td className="border border-gray-300 p-1 text-center">{row.ply}</td>
                        <td className="border border-gray-300 p-1 text-center">{row.pcs}</td>
                        <td className="border border-gray-300 p-1 text-right">{row.gw}</td>
                        <td className="border border-gray-300 p-1 text-right">{row.net}</td>
                        <td className="border border-gray-300 p-1">{row.stone.code}</td>
                        <td className="border border-gray-300 p-1">{row.stone.sub}</td>
                        <td className="border border-gray-300 p-1">{row.stone.pcs}</td>
                        <td className="border border-gray-300 p-1">{row.stone.wt}</td>
                        <td className="border border-gray-300 p-1">{row.stone.rate}</td>
                        <td className="border border-gray-300 p-1">{row.stone.rate}</td>
                      </tr>
                      {/* Render additional rows for other items */}
                      {/* {row.other.items.slice(1).map((item, itemIndex) => (
                        <tr key={`row-${index}-item-${itemIndex}`}>
                          <td className="border border-gray-300 p-1" colSpan="11"></td>
                          <td className="border border-gray-300 p-1">{item.name}</td>
                          <td className="border border-gray-300 p-1 text-center">{item.pcs}</td>
                          <td className="border border-gray-300 p-1">{item.ply}</td>
                          <td className="border border-gray-300 p-1 text-right">{item.wt}</td>
                          <td className="border border-gray-300 p-1 text-right">{item.rate}</td>
                          <td className="border border-gray-300 p-1" colSpan="4"></td>
                        </tr>
                      ))} */}
                      {/* Summary row for each barcode section */}
                      {/* <tr key={`summary-${index}`} className="bg-gray-50">
                        <td className="border border-gray-300 p-1" colSpan="3"></td>
                        <td className="border border-gray-300 p-1 text-center font-bold">1</td>
                        <td className="border border-gray-300 p-1 text-right font-bold">
                          {index === 0 ? '27.420' : '5.220'}
                        </td>
                        <td className="border border-gray-300 p-1 text-right font-bold">
                          {index === 0 ? '26.190' : '1.620'}
                        </td>
                        <td className="border border-gray-300 p-1" colSpan="14"></td>
                      </tr> */}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default JoborderReport;