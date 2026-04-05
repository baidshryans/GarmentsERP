
import React from "react";

const StoneIssue = ({ data = [] }) => {
  // Handle data structure - expecting an array
  const actualData = Array.isArray(data) ? data[0] : data;
  
 

  const stoneData = (actualData && Object.keys(actualData).length > 0) ? actualData : sampleData;
  
  // Debug log
  console.log('StoneIssue received data:', data);
  console.log('Final data being used:', stoneData);

  // Function to format date
  const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric'
    });
  };

  // Get current date and time for footer
  const getCurrentDateTime = () => {
    const now = new Date();
    return now.toLocaleDateString('en-GB', {
      day: 'numeric',
      month: 'numeric',
      year: '2-digit'
    }) + ', ' + now.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  // Calculate totals (removed cgst, sgst, igst)
  const calculateTotals = () => {
    let totalPcs = 0;
    let totalCt = 0;
    let totalGw = 0;
    let totalTaxableValue = 0;
    let totalValue = 0;

    stoneData?.karigarstoneissue_set?.forEach(item => {
      totalPcs += parseInt(item.pcs || 0);
      totalCt += parseFloat(item.ct || 0);
      totalGw += parseFloat(item.gw || 0);
      totalTaxableValue += parseFloat(item.taxable_value || 0);
      totalValue += parseFloat(item.tot_val || 0);
    });

    return {
      totalPcs,
      totalCt: totalCt.toFixed(3),
      totalGw: totalGw.toFixed(3),
      totalTaxableValue: totalTaxableValue.toFixed(2),
      totalValue: totalValue.toFixed(2)
    };
  };

  const totals = calculateTotals();

  return (
    <div className="w-full max-w-6xl mx-auto text-black bg-white p-6 print-container">
      {/* Title Section - Centered Outside (No Border) */}
      <div className="p-6 text-center mb-4">
        <div className="text-3xl font-bold"><u>ISSUE TO KARIGAR (STONE)</u></div>
      </div>

      {/* Header Table */}
     <div className="flex justify-between gap-4 mb-6">
  {/* Left Table */}
  <table className="border-2 border-black w-1/2">
    <tbody>
      <tr>
        <td className="p-3">
          <div className="flex mb-2">
            <div className="w-20 font-bold">Name:</div>
            <div className="flex-1 font-semibold">{stoneData?.karigar_ldgr_name || 'N/A'}</div>
          </div>
          <div className="flex">
            <div className="w-20 font-bold">Address:</div>
            <div className="flex-1 font-semibold">{stoneData?.karigar_address || ''}</div>
          </div>
        </td>
      </tr>
    </tbody>
  </table>

  {/* Right Table */}
  <table className="border-2 border-black w-1/2">
    <tbody>
      <tr>
        <td className="p-3">
          <div className="flex mb-2">
            <div className="w-24 font-bold">Date:</div>
            <div className="flex-1 font-semibold">{formatDate(stoneData?.date1)}</div>
          </div>
          <div className="flex">
            <div className="w-24 font-bold">Bill No:</div>
            <div className="flex-1 font-semibold">{stoneData?.billno || 'N/A'}</div>
          </div>
        </td>
      </tr>
    </tbody>
  </table>
</div>


      {/* Details Table */}
      <div className="border-2 border-black">
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            
            {/* Table Headers */}
            <thead>
              <tr className="bg-gray-100 border-b-2 border-black">
                <th className="border-r border-black p-3 text-center font-bold text-sm w-16">
                  Sl.<br/>No.
                </th>
                <th className="border-r border-black p-3 text-center font-bold text-sm w-28">
                  Packet
                </th>
                <th className="border-r border-black p-3 text-center font-bold text-sm">
                  Item Description
                </th>
                <th className="border-r border-black p-3 text-center font-bold text-sm w-20">
                  Pcs
                </th>
                <th className="border-r border-black p-3 text-center font-bold text-sm w-24">
                  Ct<br/>(Weight)
                </th>
                <th className="border-r border-black p-3 text-center font-bold text-sm w-24">
                  Gross Wt<br/>(gms)
                </th>
                <th className="border-r border-black p-3 text-center font-bold text-sm w-24">
                  Rate
                </th>
                <th className="border-r border-black p-3 text-center font-bold text-sm w-28">
                  Taxable<br/>Value
                </th>
                <th className="border-r border-black p-3 text-center font-bold text-sm w-28">
                  Total<br/>Value
                </th>
                <th className="p-3 text-center font-bold text-sm w-32">
                  Remarks
                </th>
              </tr>
            </thead>

            {/* Table Body */}
            <tbody>
              {stoneData?.karigarstoneissue_set?.length > 0 ? (
                stoneData.karigarstoneissue_set.map((item, index) => (
                  <tr key={item.id || index} className="border-b border-black hover:bg-gray-50">
                    <td className="border-r border-black p-3 text-center align-top">
                      {item.sl_no || (index + 1)}
                    </td>
                    <td className="border-r border-black p-3 text-center align-top">
                      {item.packet || '-'}
                    </td>
                    <td className="border-r border-black p-3 align-top">
                      <div>
                        <div className=" text-lg">{item.item || 'N/A'}</div>
                        <div className="text-sm text-gray-600 mt-1">
                          Job ID: {item.job_sl_object_id || '-'}
                        </div>
                      </div>
                    </td>
                    <td className="border-r border-black p-3 text-center align-top">
                      {item.pcs || 0}
                    </td>
                    <td className="border-r border-black p-3 text-center align-top ">
                      {parseFloat(item.ct || 0).toFixed(3)}
                    </td>
                    <td className="border-r border-black p-3 text-center align-top">
                      {parseFloat(item.gw || 0).toFixed(3)}
                    </td>
                    <td className="border-r border-black p-3 text-center align-top">
                      {parseFloat(item.rate || 0).toFixed(2)}
                    </td>
                    <td className="border-r border-black p-3 text-center align-top">
                      {parseFloat(item.taxable_value || 0).toFixed(2)}
                    </td>
                    <td className="border-r border-black p-3 text-center align-top">
                      {parseFloat(item.tot_val || 0).toFixed(2)}
                    </td>
                    <td className="p-3 align-top text-xs">
                      {item.remarks || '-'}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="10" className="p-6 text-center text-gray-500 border-b border-black">
                    No items found
                  </td>
                </tr>
              )}

              {/* Totals Row */}
              <tr className="font-bold border-t-2 border-black bg-gray-200">
                <td className="border-r border-black p-3 text-center font-bold">
                  Total
                </td>
                <td className="border-r border-black p-3"></td>
                <td className="border-r border-black p-3"></td>
                <td className="border-r border-black p-3 text-center">
                  {totals.totalPcs}
                </td>
                <td className="border-r border-black p-3 text-center">
                  {totals.totalCt}
                </td>
                <td className="border-r border-black p-3 text-center">
                  {totals.totalGw}
                </td>
                <td className="border-r border-black p-3"></td>
                <td className="border-r border-black p-3 text-center ">
                  {totals.totalTaxableValue}
                </td>
                <td className="border-r border-black p-3 text-center">
                  {totals.totalValue}
                </td>
                <td className="p-3"></td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Signature Section */}
        <div className="border-t-2 border-black p-6">
          <div className="flex justify-between items-end">
            <div className="text-left">
              <div className="font-semibold mb-16">Karigar Signature:</div>
              <div className="border-t-2 border-black w-56 pt-2 text-center">
                <div className="text-sm">Signature & Date</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Print Styles */}
      <style dangerouslySetInnerHTML={{
        __html: `
          @media print {
            .print-container { 
              width: 100% !important; 
              max-width: none !important; 
              margin: 0 !important; 
              padding: 10px !important; 
            }
            body { 
              margin: 0; 
              padding: 0; 
              font-size: 10px; 
              line-height: 1.2;
            }
            table { 
              page-break-inside: avoid; 
            }
            .no-print { 
              display: none !important; 
            }
            .hover\\:bg-gray-50:hover {
              background-color: transparent !important;
            }
          }
        `
      }} />
    </div>
  );
};

export default StoneIssue;

