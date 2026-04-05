
import React from "react";

const IssueToHallmark = ({ data = {} }) => {
  // Sample data for fallback (matching your structure)
  

  // If data is an array, get the first item, otherwise use data or sample
  const actualData = Array.isArray(data) ? data[0] : data;
  const issueData = (actualData && Object.keys(actualData).length > 0) ? actualData : sampleData;
  
  // Debug: Log the data to console
  console.log('IssueToHallmark received data:', data);
  console.log('Final data being used:', issueData);

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

  // Flatten items with their packet details for table rows
  const getTableRows = () => {
    const rows = [];
    
    issueData?.hallmarkissueitem_set?.forEach((item, itemIndex) => {
      if (item.hallmarkissuedetails_set && item.hallmarkissuedetails_set.length > 0) {
        // Add rows for each packet detail
        item.hallmarkissuedetails_set.forEach((detail, detailIndex) => {
          rows.push({
            ...item,
            ...detail,
            isFirstRow: detailIndex === 0,
            itemIndex: itemIndex + 1,
            detailIndex: detailIndex
          });
        });
      } else {
        // Add single row if no packet details
        rows.push({
          ...item,
          isFirstRow: true,
          itemIndex: itemIndex + 1,
          detailIndex: 0,
          packet: '',
          ct: 0
        });
      }
    });
    
    return rows;
  };

  // Calculate totals
  const calculateTotals = () => {
    let totalPcs = 0;
    let totalGw = 0;
    let totalNw = 0;
    let totalStoneWt = 0;
    let totalCt = 0;

    const rows = getTableRows();
    
    rows.forEach(row => {
      if (row.isFirstRow) {
        totalPcs += row.pcs || 0;
        const itemGw = parseFloat(row.gw || 0);
        const itemNw = parseFloat(row.nw || 0);
        totalGw += itemGw;
        totalNw += itemNw;
        totalStoneWt += itemGw - itemNw > 0 ? itemGw - itemNw : 0;
      }
      totalCt += parseFloat(row.ct || 0);
    });

    return {
      totalPcs,
      totalGw: totalGw.toFixed(3),
      totalNw: totalNw.toFixed(3),
      totalStoneWt: totalStoneWt.toFixed(3),
      totalCt: totalCt.toFixed(3)
    };
  };

  const tableRows = getTableRows();
  const totals = calculateTotals();

  return (
    <div className="w-full max-w-7xl mx-auto text-black bg-white p-6 print-container">
      {/* Title Section - Centered Outside (No Border) */}
      <div className="p-6 text-center mb-4">
        <div className="text-3xl font-bold"><u>ISSUE TO HALLMARK</u></div>
      </div>

      {/* Header Information Table - Separate Table with Lighter Borders */}
      <div className="flex justify-between gap-4 mb-4">
        {/* Left Table: Name, Date */}
        <table className="w-1/2 border-collapse" style={{ border: '1px solid #666' }}>
          <tbody>
            <tr>
              <td className="p-2 font-bold bg-gray-50 text-sm" style={{ width: '20%' }}>
                Name :
              </td>
              <td className="p-2 text-sm font-semibold" style={{ width: '100%' }}>
                {issueData?.hallmark_center_name || 'N/A'}
              </td>
            </tr>
            <tr>
              <td className="p-2 font-bold bg-gray-50 text-sm">Date :</td>
              <td className="p-2 text-sm">{formatDate(issueData?.date1)}</td>
            </tr>
          </tbody>
        </table>

        {/* Right Table: Issue Slip No, Address */}
        <table className="w-1/2 border-collapse" style={{ border: '1px solid #666' }}>
          <tbody>
            <tr>
              <td className="p-2 font-bold bg-gray-50 text-sm" style={{ width: '20%' }}>
                Issue Slip No :
              </td>
              <td className="p-2 text-sm" style={{ width: '100%' }}>
                {issueData?.issue_slip_no || 'N/A'}
              </td>
            </tr>
            <tr>
              <td className="p-2 font-bold bg-gray-50 text-sm">Address :</td>
              <td className="p-2 text-sm">{issueData?.hallmark_center_address || ''}</td>
            </tr>
          </tbody>
        </table>
      </div>


      {/* Items Details Table - Separate Table with Matching Lighter Borders */}
      <div style={{ border: '1px solid #666' }}>
        {/* Table Section */}
        <div className="overflow-x-auto">
          <table className="w-full border-collapse" style={{ border: '1px solid #666' }}>
            {/* Table Headers */}
            <thead>
              <tr className="bg-gray-100">
                <th className="p-2 text-center font-bold text-sm w-12" style={{ border: '1px solid #666' }}>
                  Sl.<br/>No.
                </th>
                <th className="p-2 text-center font-bold text-sm w-16" style={{ border: '1px solid #666' }}>
                  Pcs
                </th>
                <th className="p-2 text-center font-bold text-sm w-20" style={{ border: '1px solid #666' }}>
                  Code
                </th>
                <th className="p-2 text-center font-bold text-sm" style={{ border: '1px solid #666' }}>
                  Item Description
                </th>
                <th className="p-2 text-center font-bold text-sm w-20" style={{ border: '1px solid #666' }}>
                  Design
                </th>
                <th className="p-2 text-center font-bold text-sm w-20" style={{ border: '1px solid #666' }}>
                  Purity<br/>(K)
                </th>
                <th className="p-2 text-center font-bold text-sm w-24" style={{ border: '1px solid #666' }}>
                  Packet<br/>No.
                </th>
                <th className="p-2 text-center font-bold text-sm w-16" style={{ border: '1px solid #666' }}>
                  Ct<br/>(Weight)
                </th>
                <th className="p-2 text-center font-bold text-sm w-20" style={{ border: '1px solid #666' }}>
                  Gross Wt<br/>(gms)
                </th>
                <th className="p-2 text-center font-bold text-sm w-20" style={{ border: '1px solid #666' }}>
                  Net Wt<br/>(gms)
                </th>
                <th className="p-2 text-center font-bold text-sm w-20" style={{ border: '1px solid #666' }}>
                  Stone Wt<br/>(gms)
                </th>
              </tr>
            </thead>

            {/* Table Body */}
            <tbody>
              {tableRows.length > 0 ? (
                tableRows.map((row, index) => {
                  const stoneWt = row.isFirstRow ? 
                    ((parseFloat(row.gw || 0)) - (parseFloat(row.nw || 0))) : 0;
                  
                  return (
                    <tr key={`${row.id}-${row.detailIndex}`} className="hover:bg-gray-50">
                      <td className="p-2 text-center align-top" style={{ border: '1px solid #666' }}>
                        {row.isFirstRow ? row.itemIndex : ''}
                      </td>
                      <td className="p-2 text-center align-top" style={{ border: '1px solid #666' }}>
                        {row.isFirstRow ? (row.pcs || 0) : ''}
                      </td>
                      <td className="p-2 text-center align-top" style={{ border: '1px solid #666' }}>
                        {row.isFirstRow ? (row.code || '-') : ''}
                      </td>
                      <td className="p-2 align-top" style={{ border: '1px solid #666' }}>
                        {row.isFirstRow && (
                          <div>
                            <div className="font-semibold text-sm">{row.item || 'N/A'}</div>
                            {row.remarks && (
                              <div className="text-xs text-gray-600 mt-1">
                                <span className="font-medium">Remarks:</span> {row.remarks}
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="p-2 text-center align-top" style={{ border: '1px solid #666' }}>
                        {row.isFirstRow ? (row.design || '-') : ''}
                      </td>
                      <td className="p-2 text-center align-top " style={{ border: '1px solid #666' }}>
                        {row.metal_purity || row.purity || '-'}
                      </td>
                      <td className="p-2 text-center align-top " style={{ border: '1px solid #666' }}>
                        {row.packet || '-'}
                      </td>
                      <td className="p-2 text-center align-top " style={{ border: '1px solid #666' }}>
                        {row.ct ? parseFloat(row.ct).toFixed(3) : '0.000'}
                      </td>
                      <td className="p-2 text-center align-top " style={{ border: '1px solid #666' }}>
                        {row.isFirstRow ? parseFloat(row.gw || 0).toFixed(3) : ''}
                      </td>
                      <td className="p-2 text-center align-top " style={{ border: '1px solid #666' }}>
                        {row.isFirstRow ? parseFloat(row.nw || 0).toFixed(3) : ''}
                      </td>
                      <td className="p-2 text-center align-top " style={{ border: '1px solid #666' }}>
                        {row.isFirstRow ? (stoneWt > 0 ? stoneWt.toFixed(3) : '0.000') : ''}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan="11" className="p-6 text-center text-gray-500" style={{ border: '1px solid #666' }}>
                    No items found
                  </td>
                </tr>
              )}

              {/* Totals Row */}
              <tr className="font-bold bg-gray-200">
                <td className="p-2 text-center font-bold" style={{ border: '1px solid #666' }}>
                  TOTAL
                </td>
                <td className="p-2 text-center" style={{ border: '1px solid #666' }}>
                  {totals.totalPcs}
                </td>
                <td className="p-2" style={{ border: '1px solid #666' }}></td>
                <td className="p-2" style={{ border: '1px solid #666' }}></td>
                <td className="p-2" style={{ border: '1px solid #666' }}></td>
                <td className="p-2" style={{ border: '1px solid #666' }}></td>
                <td className="p-2" style={{ border: '1px solid #666' }}></td>
                <td className="p-2 text-center" style={{ border: '1px solid #666' }}>
                  {totals.totalCt}
                </td>
                <td className="p-2 text-center" style={{ border: '1px solid #666' }}>
                  {totals.totalGw}
                </td>
                <td className="p-2 text-center" style={{ border: '1px solid #666' }}>
                  {totals.totalNw}
                </td>
                <td className="p-2 text-center" style={{ border: '1px solid #666' }}>
                  {totals.totalStoneWt}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Signature Section */}
        <div className="p-6" style={{ borderTop: '1px solid #666' }}>
          <div className="flex justify-between items-end">
            <div className="text-balance">
              <div className="font-semibold mb-16">Received By:</div>
              <div className="w-56 pt-2 text-center" style={{ borderTop: '1px solid #666' }}>
                <div className="text-sm">Authorized Signature & Date</div>
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

export default IssueToHallmark;


