

import React from "react";

// Helper functions to flatten rows & get totals (as per your original)
function getFlatRows(items = []) {
  const rows = [];
  items.forEach((item, itemIndex) => {
    if (Array.isArray(item.details) && item.details.length > 0) {
      item.details.forEach((detail, detailIndex) => {
        rows.push({
          itemIndex: itemIndex + 1,
          detailIndex,
          pcs: detail.issue_pcs ?? "",
          description: detail.item ?? "",
          packet: detail.packet ?? "",
          purity: detail.metal_purity ?? item.purity ?? "",
          grossWt: detail.issue_gw ?? item.gw ?? 0,
          netWt: detail.balance_gw ?? item.nw ?? 0,
          wastage: item.wastage ?? 0,
          addlRecd: item.add_gw ?? 0,
          tunch: item.tunch_per ?? 0,
          wt: item.main_total_wt ?? 0,
          stoneCt: detail.issue_ct ?? 0,
          stoneWt: detail.issue_gw ?? 0,
          remarks: item.remarks ?? "",
          isFirstRow: detailIndex === 0,
          id: item.id || itemIndex,
        });
      });
    } else {
      rows.push({
        itemIndex: itemIndex + 1,
        detailIndex: 0,
        pcs: item.pcs ?? "",
        description: item.item ?? "",
        packet: "",
        purity: item.purity ?? "",
        grossWt: item.gw ?? 0,
        netWt: item.nw ?? 0,
        wastage: item.wastage ?? 0,
        addlRecd: item.add_gw ?? 0,
        tunch: item.tunch_per ?? 0,
        wt: item.main_total_wt ?? 0,
        stoneCt: 0,
        stoneWt: 0,
        remarks: item.remarks ?? "",
        isFirstRow: true,
        id: item.id || itemIndex,
      });
    }
  });
  return rows;
}

function getTotals(rows) {
  const sum = (key) =>
    rows.reduce((acc, row) => acc + (parseFloat(row[key]) || 0), 0);
  return {
    grossWt: sum("grossWt"),
    netWt: sum("netWt"),
    wastage: sum("wastage"),
    addlRecd: sum("addlRecd"),
    tunch: sum("tunch"),
    wt: sum("wt"),
    stoneCt: sum("stoneCt"),
    stoneWt: sum("stoneWt"),
    pcs: rows.reduce(
      (acc, row) => acc + (row.isFirstRow ? parseInt(row.pcs) || 0 : 0),
      0
    ),
  };
}

const ReceiveFromKarigar = ({ data = {} }) => {
  const karigarName = data.karigar_ldgr_name || "N/A";
  const address = data.place_of_supply || "N/A";
  const receiveSlipNo = data.receive_slip_no || "N/A";
  const voucherDate = data.date1 || "";

  const rows = getFlatRows(Array.isArray(data.items) ? data.items : []);
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

  // Columns matching the hallmark style, adjusted for karigar fields
  const columns = [
    { key: "itemIndex", label: "Sl.\nNo." },
    { key: "pcs", label: "Pcs" },
    { key: "packet", label: "Packet No." },
    { key: "description", label: "Description" },
    { key: "purity", label: "Purity (K)" },
    { key: "grossWt", label: "Gross Wt (gms)" },
    { key: "netWt", label: "Net Wt (gms)" },
    { key: "wastage", label: "Wastage" },
    { key: "addlRecd", label: "Addl Recd" },
    { key: "tunch", label: "Tunch" },
    { key: "wt", label: "Wt" },
    { key: "stoneCt", label: "Stone Ct" },
    { key: "stoneWt", label: "Stone Wt" },
    { key: "remarks", label: "Remarks" },
  ];

  return (
    <div className="w-full max-w-7xl mx-auto text-black bg-white p-6 print-container">
      {/* Header Section - Title moved outside */}
      <div className="text-center mb-6">
        <div className="text-3xl font-bold uppercase"><u>Receive From Karigar</u></div>
      </div>

      {/* Information Section */}
      <div className="flex justify-between gap-4 mb-4">
        {/* Left Table: Name, Address */}
        <table className="w-1/2 border-2 border-black">
          <tbody>
            <tr>
              <td className="w-28 p-3 font-bold ">Name :</td>
              <td className="p-3 font-semibold">{karigarName}</td>
            </tr>
            <tr>
              <td className="w-28 p-3 font-bold ">Address :</td>
              <td className="p-3 font-semibold">{address}</td>
            </tr>
          </tbody>
        </table>

        {/* Right Table: Receive Slip No, Voucher Date */}
        <table className="w-1/2 border-2 border-black">
          <tbody>
            <tr>
              <td className="w-36 p-3 font-bold ">Receive SlipNo:</td>
              <td className="p-3 font-semibold">{receiveSlipNo}</td>
            </tr>
            <tr>
              <td className="w-36 p-3 font-bold ">Voucher Date :</td>
              <td className="p-3 font-semibold">{formatDate(voucherDate)}</td>
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
                  key={`${row.id}-${row.detailIndex}`}
                  className="border-b border-black hover:bg-gray-50"
                >
                  {columns.map((col) => {
                    let cellValue = row[col.key];
                    if (
                      [
                        "grossWt",
                        "netWt",
                        "wastage",
                        "addlRecd",
                        "tunch",
                        "wt",
                        "stoneCt",
                        "stoneWt",
                      ].includes(col.key)
                    ) {
                      cellValue =
                        parseFloat(cellValue)
                          ? parseFloat(cellValue).toFixed(3)
                          : "0.000";
                    }
                    if (col.key === "pcs") {
                      cellValue = row.isFirstRow ? cellValue : "";
                    }
                    if (col.key === "itemIndex") {
                      cellValue = row.isFirstRow ? cellValue : "";
                    }
                    if (col.key === "remarks") {
                      cellValue = row.isFirstRow ? cellValue : "";
                    }
                    return (
                      <td
                        key={col.key}
                        className={`border-r border-black p-2 text-center align-top text-sm ${
                          col.key === "description" ? "text-left" : "font-normal"
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
                  No records found.
                </td>
              </tr>
            )}

            {rows.length > 0 && (
              <tr className="font-bold border-t-2 border-black bg-gray-200">
                <td className="border-r border-black p-2 text-center">TOTAL</td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.pcs}
                </td>
                <td colSpan={1} className="border-r border-black"></td>
                <td colSpan={1} className="border-r border-black"></td>
                <td className="border-r border-black p-2"></td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.grossWt.toFixed(3)}
                </td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.netWt.toFixed(3)}
                </td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.wastage.toFixed(3)}
                </td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.addlRecd.toFixed(3)}
                </td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.tunch.toFixed(3)}
                </td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.wt.toFixed(3)}
                </td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.stoneCt.toFixed(3)}
                </td>
                <td className="border-r border-black p-2 text-center font-normal">
                  {totals.stoneWt.toFixed(3)}
                </td>
                <td className="border-r border-black p-2"></td>
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

export default ReceiveFromKarigar;
