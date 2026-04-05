
import React from 'react';

const StoneReceive = ({ data }) => {
  // Debug: Log the incoming data
  console.log("StoneReceive received data:", data);
  console.log("Data type:", typeof data);
  console.log("Is array:", Array.isArray(data));
  
 
  // Use provided data or default data - handle different data formats
  let tableData;
  
  if (!data) {
    tableData = defaultData[0];
    console.log("Using default data");
  } else if (Array.isArray(data)) {
    tableData = data[0];
    console.log("Data is array, using first element:", tableData);
  } else {
    tableData = data;
    console.log("Data is object, using directly:", tableData);
  }
  
  console.log("Final tableData:", tableData);
  console.log("karigarstonereceive_set:", tableData?.karigarstonereceive_set);

  // Calculate totals
  const calculateTotals = (items) => {
    if (!items || items.length === 0) return {
      returnPcs: 0,
      returnGw: 0,
      brokenPcs: 0,
      brokenGw: 0,
      lossPcs: 0,
      lossGw: 0,
    };

    return items.reduce((acc, item) => ({
      returnPcs: acc.returnPcs + (item.return_pcs || 0),
      returnGw: acc.returnGw + (item.return_gw || 0),
      brokenPcs: acc.brokenPcs + (item.broken_pcs || 0),
      brokenGw: acc.brokenGw + (item.broken_gw || 0),
      lossPcs: acc.lossPcs + (item.loss_pcs || 0),
      lossGw: acc.lossGw + (item.loss_gw || 0),
    }), {
      returnPcs: 0,
      returnGw: 0,
      brokenPcs: 0,
      brokenGw: 0,
      lossPcs: 0,
      lossGw: 0,
    });
  };

  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-GB');
  };

  const formatNumber = (num, decimals = 3) => {
    return Number(num || 0).toFixed(decimals);
  };

  const totals = calculateTotals(tableData?.karigarstonereceive_set);

  return (
    <div className="w-full bg-white p-4 font-sans" style={{ fontSize: '12px', lineHeight: '1.4', maxWidth: '210mm', margin: '0 auto' }}>
      {/* Document Header */}
      <div className="text-center text-xl font-bold mb-6 underline">
       <u> RECEIVE FROM KARIGAR (STONE)</u>
      </div>

      {/* Information Section as Table */}
      <div className="flex justify-between gap-4 mb-4">
        {/* Left Table: Name + Voucher Date */}
        <table className="w-1/2 border-collapse border-2 border-black">
          <tbody>
            <tr>
              <td className="p-2 font-bold bg-gray-50 text-sm w-1/3">Name:</td>
              <td className="p-2 text-sm">{tableData?.karigar_ldgr_name || ''}</td>
            </tr>
            <tr>
              <td className="p-2 font-bold bg-gray-50 text-sm">Voucher Date:</td>
              <td className="p-2 text-sm">{formatDate(tableData?.date1)}</td>
            </tr>
          </tbody>
        </table>

        {/* Right Table: Job No. + Address */}
        <table className="w-1/2 border-collapse border-2 border-black">
          <tbody>
            <tr>
              <td className="p-2 font-bold bg-gray-50 text-sm w-1/3">Job No:</td>
              <td className="p-2 text-sm">{tableData?.billno || ''}</td>
            </tr>
            <tr>
              <td className="p-2 font-bold bg-gray-50 text-sm">Address:</td>
              <td className="p-2 text-sm">{tableData?.address || ''}</td>
            </tr>
          </tbody>
        </table>
      </div>


      {/* Main Table */}
      <div className="w-full mb-4">
        <table className="w-full border-collapse border-2 border-black" style={{ tableLayout: 'fixed' }}>
          <thead>
            <tr>
              <th className="border border-black p-2 font-bold text-center text-xs" rowSpan="2" style={{ width: '5%' }}>
                Sl.<br/>No.
              </th>
              <th className="border border-black p-2 font-bold text-center text-xs" rowSpan="2" style={{ width: '8%' }}>
                Code
              </th>
              <th className="border border-black p-2 font-bold text-center text-xs" rowSpan="2" style={{ width: '20%' }}>
                Item Description
              </th>
              <th className="border border-black p-2 font-bold text-center text-xs" rowSpan="2" style={{ width: '12%' }}>
                Item
              </th>
              <th className="border border-black p-2 font-bold text-center text-xs" rowSpan="2" style={{ width: '15%' }}>
                Design
              </th>
              <th className="border border-black p-2 font-bold text-center bg-gray-100 text-xs" colSpan="2" style={{ width: '15%' }}>
                Return
              </th>
              <th className="border border-black p-2 font-bold text-center bg-gray-100 text-xs" colSpan="2" style={{ width: '15%' }}>
                Broken
              </th>
              <th className="border border-black p-2 font-bold text-center bg-gray-100 text-xs" colSpan="2" style={{ width: '15%' }}>
                Loss
              </th>
            </tr>
            <tr>
              {/* Return columns */}
              <th className="border border-black p-1 font-bold text-center bg-gray-100 text-xs" style={{ width: '7.5%' }}>
                Pcs
              </th>
              <th className="border border-black p-1 font-bold text-center bg-gray-100 text-xs" style={{ width: '7.5%' }}>
                Wt
              </th>
              {/* Broken columns */}
              <th className="border border-black p-1 font-bold text-center bg-gray-100 text-xs" style={{ width: '7.5%' }}>
                Pcs
              </th>
              <th className="border border-black p-1 font-bold text-center bg-gray-100 text-xs" style={{ width: '7.5%' }}>
                Wt
              </th>
              {/* Loss columns */}
              <th className="border border-black p-1 font-bold text-center bg-gray-100 text-xs" style={{ width: '7.5%' }}>
                Pcs
              </th>
              <th className="border border-black p-1 font-bold text-center bg-gray-100 text-xs" style={{ width: '7.5%' }}>
                Wt
              </th>
            </tr>
          </thead>
          <tbody>
            {tableData?.karigarstonereceive_set && tableData.karigarstonereceive_set.length > 0 ? (
              tableData.karigarstonereceive_set.map((item, index) => (
                <tr key={item.id || index} style={{ height: '40px' }}>
                  <td className="border border-black p-1 text-center text-xs">
                    {item.sl_no || index + 1}.
                  </td>
                  <td className="border border-black p-1 text-center text-xs">
                    {item.item || ''}
                  </td>
                  <td className="border border-black p-1 text-left text-xs">
                    {item.item_name || ''}
                  </td>
                  <td className="border border-black p-1 text-center text-xs">
                    {item.item || ''}
                  </td>
                  <td className="border border-black p-1 text-center text-xs">
                    {item.packet || ''}
                  </td>
                  {/* Return columns */}
                  <td className="border border-black p-1 text-center text-xs">
                    {item.return_pcs || ''}
                  </td>
                  <td className="border border-black p-1 text-center text-xs">
                    {item.return_gw ? formatNumber(item.return_gw, 3) : ''}
                  </td>
                  {/* Broken columns */}
                  <td className="border border-black p-1 text-center text-xs">
                    {item.broken_pcs || ''}
                  </td>
                  <td className="border border-black p-1 text-center text-xs">
                    {item.broken_gw ? formatNumber(item.broken_gw, 3) : ''}
                  </td>
                  {/* Loss columns */}
                  <td className="border border-black p-1 text-center text-xs">
                    {item.loss_pcs || ''}
                  </td>
                  <td className="border border-black p-1 text-center text-xs">
                    {item.loss_gw ? formatNumber(item.loss_gw, 3) : ''}
                  </td>
                </tr>
              ))
            ) : (
              <tr style={{ height: '40px' }}>
                <td colSpan={11} className="border border-black p-4 text-center text-xs">
                  No data available
                </td>
              </tr>
            )}
            
            {/* Add empty rows to maintain table height - reduced to 3 rows */}
            {Array.from({ length: Math.max(0, 3 - (tableData?.karigarstonereceive_set?.length || 0)) }).map((_, index) => (
              <tr key={`empty-${index}`} style={{ height: '40px' }}>
                {Array.from({ length: 11 }).map((_, cellIndex) => (
                  <td key={cellIndex} className="border border-black p-1 text-center"></td>
                ))}
              </tr>
            ))}
          </tbody>
          
          {/* Total Row */}
          <tfoot>
            <tr className="bg-gray-50" style={{ height: '40px' }}>
              <td colSpan={5} className="border border-black p-2 text-left font-bold text-xs">
                Total :
              </td>
              {/* Return totals */}
              <td className="border border-black p-1 text-center font-bold text-xs">
                {totals.returnPcs || ''}
              </td>
              <td className="border border-black p-1 text-center font-bold text-xs">
                {totals.returnGw ? formatNumber(totals.returnGw, 3) : ''}
              </td>
              {/* Broken totals */}
              <td className="border border-black p-1 text-center font-bold text-xs">
                {totals.brokenPcs || ''}
              </td>
              <td className="border border-black p-1 text-center font-bold text-xs">
                {totals.brokenGw ? formatNumber(totals.brokenGw, 3) : ''}
              </td>
              {/* Loss totals */}
              <td className="border border-black p-1 text-center font-bold text-xs">
                {totals.lossPcs || ''}
              </td>
              <td className="border border-black p-1 text-center font-bold text-xs">
                {totals.lossGw ? formatNumber(totals.lossGw, 3) : ''}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* E. & O.E. */}
      <div className="mb-4">
        <div className="font-bold text-sm">E. & O.E.</div>
      </div>

      {/* Footer Information */}
      <div className="mb-6">
        <div className="flex justify-between items-center mb-3">
          <div className="flex items-center">
            <span className="font-bold mr-2 text-sm">VAT No.</span>
            <span className="border-b border-black pb-1" style={{ minWidth: '120px' }}></span>
          </div>
          <div className="flex items-center">
            <span className="font-bold mr-2 text-sm">WBST No.</span>
            <span className="border-b border-black pb-1" style={{ minWidth: '120px' }}></span>
          </div>
          <div className="flex items-center">
            <span className="font-bold mr-2 text-sm">CST No.</span>
            <span className="border-b border-black pb-1" style={{ minWidth: '120px' }}></span>
          </div>
        </div>
      </div>

      {/* Signature Section */}
      <div className="flex justify-between items-end mb-6">
        <div className="text-center">
          <div className="mb-12 font-medium text-sm">Karigar Signature</div>
          <div className="border-t border-black w-32"></div>
        </div>
        <div className="text-center">
          <div className="mb-12 font-medium text-sm">For .</div>
          <div className="border-t border-black w-32"></div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-black p-3 bg-gray-50">
        <div className="flex justify-between items-center text-xs text-gray-600">
        </div>
      </div>
    </div>
  );
};

export default StoneReceive;




