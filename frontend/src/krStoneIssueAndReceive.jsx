import React, { useState, useEffect } from 'react';
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchGroup, fetchKarigarReceiveReport, fetchKarigarStoneIssueReport, fetchMainItem, fetchPurity, fetchShape, getLedgers } from './services/apiService';
import { useForm } from 'react-hook-form';

const KrStoneIssueAndReceive = () => {
    const [showTable, setShowTable] = useState(false);
    const [fromDate, setFromDate] = useState('12/03/2025');
    const [toDate, setToDate] = useState('12/03/2025');
    const [karigars, setKarigars] = useState([]);
    const [groups, setGroups] = useState([]);
    const [shapes, setShapes] = useState([]);
    const [issue, setIssue] = useState([]);
    const [receive, setReceive] = useState([]);
    const { register } = useForm({
        defaultValues: {
            issue: false,
            receive: false
        }
    });
    useEffect(() => {
        async function fetchData() {
            const [karigars, groups, shapes,issue,receive] = await Promise.all([getLedgers(), fetchGroup(), fetchShape(),fetchKarigarStoneIssueReport(),fetchKarigarReceiveReport()]);
            if (karigars.success) setKarigars(karigars.data.results);
            if (groups.success) setGroups(groups.data.results);
            if (shapes.success) setShapes(shapes.data.results);
            if(issue.success)setIssue(issue.data.results);
            if(receive.success)setReceive(receive.date.results);
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
        group: [
            { id: 'all', name: 'All', checked: false },
            { id: 'aps', name: 'APS', checked: false },
            { id: 'bball', name: 'BBALL', checked: false },
            { id: 'beg', name: 'BEG', checked: false },
            { id: 'bnk', name: 'BNK', checked: false },
            { id: 'chn', name: 'CHN', checked: false }
        ],
        shape: [
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
    //     fun((prevData) => {
    //         console.log(prevData)
    //         const updatedSection = [...prevData];

    //         // Find the item and toggle its checked status
    //         const itemIndex = updatedSection.findIndex(item => item.id === itemId);
    //         if (itemIndex !== -1) {
    //             updatedSection[itemIndex] = {
    //                 ...updatedSection[itemIndex],
    //                 checked: !updatedSection[itemIndex].checked
    //             };
    //         }

    //         console.log(updatedSection)

    //         return [

    //             ...updatedSection
    //         ];
    //     });
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
                            className={`flex items-center p-2 ${item.name === '22' && section === 'purity' && item.checked ? 'bg-primary text-white' : ''}`}
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
                            className={`flex items-center p-2 ${item.name === '22' && section === 'purity' && item.checked ? 'bg-primary text-white' : ''}`}
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


    const renderGroupSection = (title, items, section) => {
        return (
            <div>
                <div className="font-bold mb-1 ">{title}</div>
                <div className="border border-gray-300 h-32 overflow-y-auto ">
                    {items.map(item => (
                        <div
                            key={item.id}
                            className={`flex items-center p-2 ${item.name === '22' && section === 'purity' && item.checked ? 'bg-primary text-white' : ''}`}
                        >
                            <Checkbox id="fix_rate" checked={item.checked}
                                onCheckedChange={(checked) => handleCheckboxChange(section, item.id, setGroups)}
                            />


                            <label className="ml-2">{item.item_group_name
                            }</label>
                        </div>
                    ))}
                </div>
            </div>
        );
    };
    const renderShapeSection = (title, items, section) => {
        return (
            <div>
                <div className="font-bold mb-1 ">{title}</div>
                <div className="border border-gray-300 h-32 overflow-y-auto ">
                    {items.map(item => (
                        <div
                            key={item.id}
                            className={`flex items-center p-2 ${item.name === '22' && section === 'purity' && item.checked ? 'bg-primary text-white' : ''}`}
                        >
                            <Checkbox id="fix_rate" checked={item.checked}
                                onCheckedChange={(checked) => handleCheckboxChange(section, item.id, setShapes)}
                            />


                            <label className="ml-2">{item.shape_name}</label>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    const renderIssueSection = (title, items, section) => {
        return (
            <div>
                <div className="font-bold mb-1 ">{title}</div>
                <div className="border border-gray-300 h-32 overflow-y-auto ">
                    {items.map(item => (
                        <div
                            key={item.id}
                            className={`flex items-center p-2 ${item.name === '22' && section === 'purity' && item.checked ? 'bg-primary text-white' : ''}`}
                        >
                            <Checkbox id="fix_rate" checked={item.checked}
                                onCheckedChange={(checked) => handleCheckboxChange(section, item.id, setIssue)}
                            />


                            <label className="ml-2">{item.issue}</label>
                        </div>
                    ))}
                </div>
            </div>
        );
    };

    const handleCheckboxChange = (checked, type) => {
        if (type === "issue") {
            setIssue(checked);
            if (checked) fetchKarigarStoneIssueReport();
        } else if (type === "receive") {
            setReceive(checked);
            if (checked) fetchKarigarReceiveReport();
        }
    };

    const onGo = () => {
        const checkedKarigars = karigars.filter(k => k.checked).map(k => k.id);
        const checkedGroups = groups.filter(p => p.checked).map(p => p.id);
        const checkedShapes = shapes.filter(s => s.checked).map(s => s.id);
        // const checkedUsers = users.filter(u => u.checked).map(u => u.id);
        // const selectedIssue = issue.filter(i => i.checked).map(i => i.id);

        console.log('Selected Karigars:', checkedKarigars);
        console.log('Selected Group:', checkedGroups);
        console.log('Selected Shape:', checkedShapes);
        // console.log('Selected Users:', checkedUsers);
        console.log('From Date:', fromDate);
        console.log('To Date:', toDate);
        console.log('Issue Selected:', issue);
        console.log('Receive Selected:', receive);

    }

    return (
        <div className="w-full max-w-6xl mx-auto font-sans">
            <div className="border border-gray-300 rounded p-4 bg-white">
                <div className="text-center font-bold text-primary mb-4">KARIGAR ISSUE/RECEIVE REGISTER</div>

                <div className="grid grid-cols-4 gap-4 mb-4">
                    {renderKarigarsSection('Karigar', karigars, 'Karigar')}
                    {renderGroupSection('Group', groups, 'Group')}
                    {renderShapeSection('Shape', shapes, 'Shape')}
                </div>

                {/* Date Range Selection */}
                <div className="flex items-center mb-6">
                    <div className="flex items-center mr-4">
                        <Checkbox
                            id="issue"
                            checked={issue}
                            onCheckedChange={(checked) => handleCheckboxChange(checked, "issue")}
                        />
                        <Label className="mr-2" htmlFor="issue">Issue</Label>
                    </div>

                    <div className="flex items-center mr-4">
                        <Checkbox
                            id="receive"
                            checked={receive}
                            onCheckedChange={(checked) => handleCheckboxChange(checked, "receive")}
                        />
                        <Label className="mr-2" htmlFor="receive">Receive</Label>
                    </div>
                    <div className="flex items-center mr-4">
                        <Label className="mr-2" htmlFor="fromDate">FROM</Label>
                        <Input
                            type="date"
                            {...register("fromDate")}
                            defaultValue={fromDate}
                            className="border border-gray-300 p-1 w-24"
                        />
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
                    <button
                        className="bg-primary text-white px-4 py-1 rounded"
                        onClick={onGo}
                    >
                        GO
                    </button>
                </div>

                {/* Print options */}
                {showTable && (
                    <div className="text-right text-primary mb-2">
                        <button className="mr-2">Print</button>
                        <button>Export</button>
                    </div>
                )}

                {/* Report Header and Table */}
                {showTable && (
                    <div>
                        <div className="text-left mb-4">
                            <div className="font-bold">Karigar wise Receive Register Between {fromDate} and  {toDate}</div>

                        </div>

                        {/* Main Table */}
                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse border border-gray-300 text-sm">
                                <thead>
                                    <tr className="bg-gray-100">
                                        <th className="border border-gray-300 p-1">Date</th>
                                        <th className="border border-gray-300 p-1">Karigar</th>
                                        <th className="border border-gray-300 p-1">Design No</th>
                                        <th className="border border-gray-300 p-1">Set Name</th>
                                        <th className="border border-gray-300 p-1">Slip No</th>
                                        <th className="border border-gray-300 p-1">Particulars</th>
                                        <th className="border border-gray-300 p-1">Pcs</th>
                                        <th className="border border-gray-300 p-1">Wt(cts)</th>
                                        <th className="border border-gray-300 p-1 ">Wt(gms)</th>
                                    </tr>

                                </thead>
                                <tbody>
                                    {reportData.map((row, index) => (
                                        <>
                                            <tr key={`row-${index}`}>
                                                <td className="border border-gray-300 p-1">{row.date}</td>

                                                <td className="border border-gray-300 p-1 text-center">{row.Karigar}</td>
                                                <td className="border border-gray-300 p-1 text-center">{row.design_no}</td>
                                                <td className="border border-gray-300 p-1 text-right">{row.name}</td>
                                                <td className="border border-gray-300 p-1 text-right">{row.slip_no}</td>

                                                <td className="border border-gray-300 p-1 text-right">{row.particulars}</td>
                                                <td className="border border-gray-300 p-1 text-right">{row.pcs}</td>
                                                <td className="border border-gray-300 p-1 text-right">{row.wt}</td>
                                                <td className="border border-gray-300 p-1 text-right">{row.wt}</td>

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

export default KrStoneIssueAndReceive;