import React, { useState, useEffect } from 'react';
import { useForm, Controller } from "react-hook-form";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchPurchaseFinished, fetchPurity, fetchReceivedFinished, getLedgers } from './services/apiService';
import { Select, SelectTrigger, SelectContent, SelectItem, SelectValue } from "@/components/ui/select";
import { FieldContainer } from "@/Utils";


const FinishedItemRecReport = () => {
  const [showTable, setShowTable] = useState(false);
  const [fromDate, setFromDate] = useState('12/03/2025');
  const [toDate, setToDate] = useState('12/03/2025');
  const [karigars, setKarigars] = useState([]);
  const [purity, setPurityData] = useState([]);
  const [purchase, setPurchase] = useState([]);
  const [receive, setReceive] = useState([]);
  const { register } = useForm({
    defaultValues: {
      purchase: false,
      receive: false
    }
  });

  const { control } = useForm({
    defaultValues: {
      form: {
        document: "",
      },
    },
  });
  useEffect(() => {
    async function fetchData() {
      const [karigars, pur] = await Promise.all([getLedgers(), fetchPurity()]);
      if (karigars.success) setKarigars(karigars.data.results);
      if (pur.success) setPurityData(pur.data.results);
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
    ],

    purity: [
      { id: 'all', name: 'All', checked: false },
      { id: '100', name: '100', checked: false },
      { id: '14', name: '14', checked: false },
      { id: '18', name: '18', checked: false },
      { id: '22', name: '22', checked: true },
      { id: '24', name: '24', checked: false }
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
  // const handleCheckboxChange = (section, itemId, fun) => {
  //   fun((prevData) => {
  //     console.log(prevData)
  //     const updatedSection = [...prevData];

  //     // Find the item and toggle its checked status
  //     const itemIndex = updatedSection.findIndex(item => item.id === itemId);
  //     if (itemIndex !== -1) {
  //       updatedSection[itemIndex] = {
  //         ...updatedSection[itemIndex],
  //         checked: !updatedSection[itemIndex].checked
  //       };
  //     }

  //     console.log(updatedSection)

  //     return [

  //       ...updatedSection
  //     ];
  //   });
  // };

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


              <label>{item.name}</label>
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

  const renderPuritysSection = (title, items, section) => {
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
                onCheckedChange={(checked) => handleCheckboxChange(section, item.id, setPurityData)}
              />


              <label className="ml-2">{item.purity}</label>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const handleCheckboxChange = (checked, type) => {
    if (type === "purchase") {
      setPurchase(checked);
      if (checked) fetchPurchaseFinished();
    } else if (type === "receive") {
      setReceive(checked);
      if (checked) fetchReceivedFinished();
    }
  };

  const onGo = () => {
    const checkedKarigars = karigars.filter(k => k.checked).map(k => k.id);
    const checkedPurity = purity.filter(p => p.checked).map(p => p.id);

    console.log('Selected Karigars:', checkedKarigars);
    console.log('Selected Purity:', checkedPurity);
    console.log('From Date:', fromDate);
    console.log('To Date:', toDate);
    console.log('Receive Selected:', receive);
    console.log('Purchase Selected:', purchase);

    // fetchIDGenerationReport(fromDate, toDate, checkedPurity[0], checkedKarigars, checkedItem)
    // if (type == "receive"){

    //  }else {}

  }
  return (
    <div className="w-full max-w-6xl mx-auto font-sans">
      <div className="border border-gray-300 rounded p-4 bg-white">
        <div className="text-center font-bold text-violet-900 mb-4">FINISH ITEM RECEIVE DAY BOOK</div>

        <div className="grid grid-cols-4 gap-4 mb-4 ">
          {renderKarigarsSection('Karigars', karigars, 'Karigars')}
          {renderPuritysSection('Purity', purity, 'purity')}
        </div>

        {/* Date Range Selection */}
        <div className="flex items-center mb-6 gap-5">
          <div className="flex items-center mr-4 ">
            <Label className="mr-2" htmlFor="date">FROM</Label>
            <Input type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="border border-gray-300 p-1 w-24" />
          </div>

          <div className="flex items-center mr-4 ">
            <Label className="mr-2" htmlFor="date">TO</Label>
            <Input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="border border-gray-300 p-1 w-24"
            />
          </div>
          
          <FieldContainer className="flex items-center mr-4">
            <Label htmlFor="document" className="text-nowrap">DOCUMENT</Label>

            <Controller
              name="form.document"
              control={control}
              render={({ field }) => (
                <Select onValueChange={field.onChange} value={field.value}>
                  <SelectTrigger>
                    <SelectValue>{field.value || "Select an option"}</SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem id="receive"
                      checked={receive}
                      onCheckedChange={(checked) => handleCheckboxChange(checked, "receive")} value="Receive">Receive</SelectItem>
                    <SelectItem id="purchase"
                      checked={purchase}
                      onCheckedChange={(checked) => handleCheckboxChange(checked, "purchase")} value="Purchase">Purchase</SelectItem>
                  </SelectContent>
                </Select>
              )}
            />
          </FieldContainer>
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
              <div className="font-bold">Finish Item Receive Day Book of Purity:{purityData}</div>
              <div>From {fromDate} To {toDate}</div>
            </div>

            {/* Main Table */}
            <div className="overflow-x-auto">
              <table className="w-full border-collapse border border-gray-300 text-sm">
                <thead>
                  <tr className="bg-gray-100">
                    <th className="border border-gray-300 p-1">Bill No</th>
                    <th className="border border-gray-300 p-1">St/Or No</th>
                    <th className="border border-gray-300 p-1">Issue Slip No.</th>
                    <th className="border border-gray-300 p-1">Artisan Name</th>
                    <th className="border border-gray-300 p-1">Purity</th>
                    <th className="border border-gray-300 p-1">Pcs</th>

                    <th className="border border-gray-300 p-1">Item Name</th>
                    <th className="border border-gray-300 p-1">Gr.Wt.</th>
                    <th className="border border-gray-300 p-1">Nt.Wt.</th>
                  </tr>

                </thead>
                <tbody>
                  {reportData.map((row, index) => (
                    <>
                      <tr key={`row-${index}`}>
                        <td className="border border-gray-300 p-1">{row.bill_no}</td>

                        <td className="border border-gray-300 p-1 ">{row.st_no}</td>
                        <td className="border border-gray-300 p-1 ">{row.issue_slip_no}</td>

                        <td className="border border-gray-300 p-1">{row.artisan_name}</td>
                        <td className="border border-gray-300 p-1">{row.purity}</td>
                        <td className="border border-gray-300 p-1">{row.pcs}</td>
                        <td className="border border-gray-300 p-1">{row.item}</td>
                        <td className="border border-gray-300 p-1">{row.gr_wt}</td>
                        <td className="border border-gray-300 p-1">{row.nt_wt}</td>

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

export default FinishedItemRecReport;