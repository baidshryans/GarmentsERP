// const exampleData = {
//     name: "Isha Kapoor",
//     orderNo: "CA25/01087",
//     orderDate: "05/01/2025",
//     deliveryDate: "01/02/2025",
//     address: "116, Chakraberia Road, North",
//     purity: "14K",
//     goldRate: "",
//     phone: "8017838449",
//     items: [
//       {
//         pcs: 1,
//         description: "Lab Diamond Ladies Ring",
//         size: "7 no",
//         netWt: 4.000,
//         stoneWt: "",
//         makingWt: "",
//         rate: 8000.00,
//       },
//     ],
//     designNotes: "Design as per Xerox RHC, HMC and 3% GST Extra",
//     salesPerson: "Lovely Jhawar (C)",
//   };
  
//   // Usage in a React component
//   <CustomerOrder data={exampleData} />;
  
import React, { useEffect } from "react";

const CustomerOrder = ({ data }) => {


  return (
    <div className="w-full max-w-4xl mx-auto bg-white text-black text-sm font-sans">
      <table className="w-full border border-black border-collapse">
        <tbody>
          {/* 1) Title Row */}
          <tr className="border-b border-black">
            <td className="text-center p-2 font-bold text-base align-middle">
              ORDER MEMO
            </td>
          </tr>

          {/* 2) Header Info Row */}
          <tr className="border-b border-black align-top">
            <td>
              <table className="w-full border-collapse">
                <tbody>
                  <tr>
                    {/* Left side: Name, Address, Phone */}
                    <td className="align-top border-r border-black p-2 w-1/2">
                      <table className="w-full text-sm">
                        <tbody>
                          <tr>
                            <td className="w-20 font-semibold align-top">Name</td>
                            <td>{data.name}</td>
                          </tr>
                          <tr>
                            <td className="w-20 font-semibold align-top">Address</td>
                            <td>{data.address}</td>
                          </tr>
                          <tr>
                            <td className="w-20 font-semibold align-top">Ph No.</td>
                            <td>{data.phone}</td>
                          </tr>
                        </tbody>
                      </table>
                    </td>

                    {/* Right side: Order No, Date, Purity, Gold Rate, Del. Date */}
                    <td className="align-top p-2 w-1/2">
                      <table className="w-full text-sm">
                        <tbody>
                          <tr>
                            <td className="w-20 font-semibold align-top">Order No.</td>
                            <td>{data.orderNo}</td>
                            <td className="w-12 font-semibold align-top">Date</td>
                            <td>{data.orderDate}</td>
                          </tr>
                          <tr>
                            <td className="w-20 font-semibold align-top">Purity</td>
                            <td>{data.purity}</td>
                            <td className="w-12 font-semibold align-top">Gold Rate</td>
                            <td>{data.goldRate}</td>
                          </tr>
                          <tr>
                            <td className="w-20 font-semibold align-top">Del. Date</td>
                            <td colSpan={3}>{data.deliveryDate}</td>
                          </tr>
                        </tbody>
                      </table>
                    </td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>

          {/* 3) Items Table Row */}
          <tr className="border-b border-black align-top">
            <td className="p-0">
              <table className="w-full border-collapse">
                <thead className="text-sm">
                  {/* First header row */}
                  <tr className="border-b border-black">
                    <th className="border-r border-black w-16 py-1 px-2 text-left">
                      Sl.<br />No.
                    </th>
                    <th className="border-r border-black w-16 py-1 px-2 text-left">
                      Pcs
                    </th>
                    <th className="border-r border-black py-1 px-2 text-left w-[40%]">
                      Description
                    </th>
                    <th className="border-r border-black w-16 py-1 px-2 text-left">
                      Size
                    </th>
                    <th className="border-r border-black w-16 py-1 px-2 text-left">
                      Net Wt
                    </th>
                    {/* “Stone” spans 2 columns; second row below for “Wt” & “Rate” */}
                    <th colSpan={2} className="border-r border-black py-1 px-2 text-center">
                      Stone
                    </th>
                    <th className="py-1 px-2 text-left w-20">
                      Making
                    </th>
                  </tr>
                  {/* Second header row for Stone Wt & Rate */}
                  <tr className="border-b border-black">
                    <th className="border-r border-black h-7"></th>
                    <th className="border-r border-black"></th>
                    <th className="border-r border-black"></th>
                    <th className="border-r border-black"></th>
                    <th className="border-r border-black"></th>
                    <th className="border-r border-black py-1 px-2 text-left w-16">
                      Wt
                    </th>
                    <th className="border-r border-black py-1 px-2 text-left w-16">
                      Rate
                    </th>
                    <th></th>
                  </tr>
                </thead>
                <tbody className="text-sm">
                  {data.items.map((item, index) => (
                    <tr key={index} className="border-b border-black align-top">
                      <td className="border-r border-black py-1 px-2">{index + 1}</td>
                      <td className="border-r border-black py-1 px-2">{item.pcs}</td>
                      <td className="border-r border-black py-1 px-2">
                        {item.description}
                        {item.designNotes && (
                          <div className="text-xs mt-1">{item.designNotes}</div>
                        )}
                      </td>
                      <td className="border-r border-black py-1 px-2">{item.size}</td>
                      <td className="border-r border-black py-1 px-2">{item.netWt}</td>
                      <td className="border-r border-black py-1 px-2">{item.stoneWt}</td>
                      <td className="border-r border-black py-1 px-2">{item.stoneRate}</td>
                      <td className="py-1 px-2 text-right">{item.making}</td>
                    </tr>
                  ))}
                  {/* Empty rows for spacing (adjust count as needed) */}
                  {[...Array(10)].map((_, i) => (
                    <tr key={`empty-${i}`} className="border-b border-black h-6">
                      <td className="border-r border-black"></td>
                      <td className="border-r border-black"></td>
                      <td className="border-r border-black"></td>
                      <td className="border-r border-black"></td>
                      <td className="border-r border-black"></td>
                      <td className="border-r border-black"></td>
                      <td className="border-r border-black"></td>
                      <td></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </td>
          </tr>

          {/* 4) Sales Person */}
          <tr className="border-b border-black">
            <td className="p-2">
              <span className="font-semibold">Sales Person :</span> {data.salesPerson}
            </td>
          </tr>

          {/* 5) E. & O.E. + For */}
          <tr className="border-b border-black">
            <td className="p-2 flex justify-between">
              <div className="font-semibold">E. &amp; O.E.</div>
              <div>For __________________</div>
            </td>
          </tr>

          {/* 6) Customer Signature + VAT/WBST/CST */}
          <tr className="border-b border-black">
            <td className="p-2 flex justify-between items-start">
              <div className="space-y-1 leading-tight">
                <div>VAT No.</div>
                <div>WBST No.</div>
                <div>CST No.</div>
              </div>
              <div className="font-semibold">Customer Signature</div>
            </td>
          </tr>

          {/* 7) TAX EXTRA */}
          <tr>
            <td className="p-2 text-center font-bold">
              TAX EXTRA
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
};

export default CustomerOrder;
