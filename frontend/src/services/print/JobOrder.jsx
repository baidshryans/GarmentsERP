
import React from "react";

const JobOrder = ({ data = {} }) => {
  // Handle data structure - expecting an object
  const actualData = data && Object.keys(data).length > 0 ? data : {};
  
  const jobData = Object.keys(actualData).length > 0 ? actualData : sampleData;
  
  // Helper functions similar to ReceiveFromKarigar
  function getFlatRows(items = []) {
    const rows = [];
    items.forEach((item, itemIndex) => {
      rows.push({
        itemIndex: itemIndex + 1,
        slNo: item.issue_sl_no || (itemIndex + 1),
        pcs: item.pcs ?? "",
        description: item.item ?? "",
        orderNo: item.order_no || jobData.order_no || "",
        orderSl: item.issue_sl_no || (itemIndex + 1),
        dueDate: item.due_date || "",
        design: item.design_code ?? "",
        size: item.size ?? "",
        netWt: item.approx_wt ?? 0,
        purity: item.purity ?? "",
        remarks: item.remarks ?? "",
        id: item.id || itemIndex,
      });
    });
    return rows;
  }

  function getTotals(rows) {
    const sum = (key) =>
      rows.reduce((acc, row) => acc + (parseFloat(row[key]) || 0), 0);
    return {
      pcs: rows.reduce((acc, row) => acc + (parseInt(row.pcs) || 0), 0),
      netWt: sum("netWt"),
    };
  }

  const karigarName = jobData.karigar_ldgr_name || "N/A";
  const address = jobData.karigar_address || "N/A";
  const orderNo = jobData.order_no || "N/A";
  const voucherNo = jobData.issue_slip_no || "N/A";
  const voucherDate = jobData.date1 || "";

  const rows = getFlatRows(Array.isArray(jobData.items) ? jobData.items : []);
  const totals = getTotals(rows);

  const formatDate = (dateString) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    return date.toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  };

  // Columns matching the joborder requirements
  const columns = [
    { key: "slNo", label: "Sl.\nNo." },
    { key: "pcs", label: "Pcs" },
    { key: "description", label: "Item Description" },
    { key: "orderNo", label: "Ord. No." },
    { key: "orderSl", label: "Ord. Sl" },
    { key: "dueDate", label: "Dlv. Date" },
    { key: "design", label: "Design" },
    { key: "size", label: "Size" },
    { key: "netWt", label: "Net Wt" },
  ];

  return (
    <div className="w-full max-w-7xl mx-auto text-black bg-white p-6 print-container">
      {/* Header Section - Title moved outside */}
      <div className="text-center mb-6">
        <div className="text-3xl font-bold uppercase"><u>Work Order To Artisan</u></div>
      </div>

      <div className="flex justify-between gap-4 mb-4">
        {/* Left Table - Name, Address, Voucher Date */}
        <table className="border-2 border-black w-1/2">
          <tbody>
            <tr>
              <td className="p-3">
                <div className="flex mb-2">
                  <div className="w-20 font-bold">Name :</div>
                  <div className="flex-1 font-semibold">{karigarName}</div>
                </div>
                <div className="flex mb-2">
                  <div className="w-20 font-bold">Address :</div>
                  <div className="flex-1 font-semibold">{address}</div>
                </div>
                <div className="flex">
                  <div className="w-20 font-bold">Voucher Date :</div>
                  <div className="flex-1 font-semibold">{formatDate(voucherDate)}</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        {/* Right Table - Order No and Voucher No */}
        <table className="border-2 border-black w-1/2">
          <tbody>
            <tr>
              <td className="p-3">
                <div className="flex mb-2">
                  <div className="w-32 font-bold">Order No./Design :</div>
                  <div className="flex-1 font-semibold">{orderNo}</div>
                </div>
                <div className="flex">
                  <div className="w-32 font-bold">Voucher No :</div>
                  <div className="flex-1 font-semibold">{voucherNo}</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>



      {/* Items Table */}
      <div className="overflow-x-auto border-2 border-black">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-gray-100 border-b-2 border-black">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`border-r border-black p-2 text-center font-bold text-sm ${
                    col.key === "description" ? "min-w-[150px]" : ""
                  }`}
                >
                  {col.label.split("\n").map((line, idx) => (
                    <React.Fragment key={idx}>
                      {line}
                      <br />
                    </React.Fragment>
                  ))}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {rows.length > 0 ? (
              rows.map((row, idx) => (
                <tr
                  key={`${row.id}-${idx}`}
                  className="border-b border-black hover:bg-gray-50"
                >
                  {columns.map((col) => {
                    let cellValue = row[col.key];
                    
                    // Format numeric values
                    if (col.key === "netWt") {
                      cellValue = parseFloat(cellValue)
                        ? parseFloat(cellValue).toFixed(3)
                        : "0.000";
                    }
                    
                    // Format dates
                    if (col.key === "dueDate") {
                      cellValue = formatDate(cellValue);
                    }

                    // Add purity to description if available
                    if (col.key === "description" && row.purity) {
                      cellValue = `${cellValue} ${row.purity ? `(${row.purity}K)` : ''}`;
                    }

                    return (
                      <td
                        key={col.key}
                        className={`border-r border-black p-2 text-center align-top text-sm ${
                          col.key === "description" ? "text-left" : ""
                        }`}
                        title={typeof cellValue === "string" ? cellValue : undefined}
                      >
                        {cellValue}
                      </td>
                    );
                  })}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="p-6 text-center text-gray-500">
                  No items found.
                </td>
              </tr>
            )}

            {/* Add empty rows for better spacing */}
            {Array.from({ length: Math.max(0, 3 - rows.length) }).map((_, index) => (
              <tr key={`empty-${index}`} className="border-b border-black">
                {columns.map((col) => (
                  <td key={col.key} className="border-r border-black p-2 text-center align-top text-sm" style={{ height: '35px' }}>
                    &nbsp;
                  </td>
                ))}
              </tr>
            ))}

            {/* Total Row */}
            {rows.length > 0 && (
              <tr className="font-bold border-t-2 border-black bg-gray-200">
                <td className="border-r border-black p-2 text-center">TOTAL</td>
                <td className="border-r border-black p-2 text-center">
                  {totals.pcs}
                </td>
                <td colSpan={6} className="border-r border-black"></td>
                <td className="border-r border-black p-2 text-center">
                  {totals.netWt.toFixed(3)}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Signature Section */}
      <div className="border-t-2 border-black p-6 flex justify-between">
        <div className="text-left">
          <div className="font-semibold mb-16">Karigar Signature</div>
          <div className="border-t-2 border-black w-56 pt-2 text-center">
            <div className="text-sm">Signature & Date</div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-black p-3 bg-gray-50">
        <div className="flex justify-between items-center text-xs text-gray-600">
        </div>
      </div>

      {/* Print Styles */}
      <style
        dangerouslySetInnerHTML={{
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
              td, th {
                font-family: monospace, monospace;
              }
            }
          `,
        }}
      />
    </div>
  );
};

export default JobOrder;







