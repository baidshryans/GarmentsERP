import React from "react";
import ReactDOM from "react-dom";
import AccountingVoucher from "./AccouuntingVoucher";
import CustomerOrder from "./CustomerOrder";
import IssueToHallmark from "./IssueToHallmark";
import PurchaseVoucher from "./PurchaseVoucherVendor";
import JobOrder from "./JobOrder";
import ReceiveFromHallmark from "./ReceiveFromHallmark";
import ReceiveFromKarigar from "./ReceiveFromKariger";
import SalesInvoice from "./SalesInvoice";
import StoneIssue from "./StoneissueToKarigar";
import StoneReceive from "./StoneReceive";

const TestComponentsDemo = () => {
  const components = {
    StoneReceive,
    SalesInvoice,
    StoneIssue,
    ReceiveFromKarigar,
    ReceiveFromHallmark,
    IssueToHallmark,
    CustomerOrder,
    AccountingVoucher,
    JobOrder,
    PurchaseVoucher,
  };

  const componentData = {
    StoneReceive: {
      name: "Mantu Das",
      jobNo: "194/3330",
      voucherDate: "06/01/2025",
      address: "123 Karigar Street, Kolkata, India",
      items: [
        {
          code: "DLR 194/3330",
          description: "Solitaire Diamond ROUND",
          design: "Classic Round",
          returnPcs: 1,
          returnWt: 1.010,
          brokenPcs: 0,
          brokenWt: 0,
          lossPcs: 0,
          lossWt: 0,
        },
      ],
      totalPcs: 1,
      totalWt: 1.010,
      vatNo: "VAT12345",
      wbstNo: "WBST67890",
      cstNo: "CST54321",
    },
    SalesInvoice: {
      companyName: "Jewel India Jewellers",
      companyAddress: "24, Camac Street, 1st Floor, Kolkata-700016",
      phone: "033 2287 0526 / 0527",
      email: "jewelindiajewellers@yahoo.co.in",
      buyer: {
        name: "Manju Sharma",
        address: "275, Rabindra Sarani, Kolkata - 700006",
      },
      invoiceNo: "GST/24-25/04035",
      invoiceDate: "07/12/2024",
      state: "West Bengal",
      gstin: "19AACFJ4832H1ZC",
      items: [
        {
          pcs: 1,
          description: "Gold Chain",
          purity: 22,
          gw: 5.850,
          nw: 5.850,
          rate: 7420,
          amount: 47828,
        },
      ],
      totalBeforeTax: 45146,
      sgstRate: 1.5,
      sgstAmount: 677,
      cgstRate: 1.5,
      cgstAmount: 677,
      totalAfterTax: 46500,
      netReceivable: 46500,
      paymentMode: "Cash",
      bank: "0/-",
      cash: "46500/-",
    },
    StoneIssue: {
      name: "Kashinath Ghosh",
      jobNo: "IV/CA25/2487-1",
      address: "Some Address Here",
      orderDesign: "CA25/01008",
      voucherDate: "06/01/2025",
      items: [
        {
          design: "DET",
          itemCode: "DRHI01",
          description: "Diamond ROUND",
          pcs: 35,
          stoneCt: 0.120,
          stoneWt: 0.000,
          remarks: "",
        },
      ],
      totalPcs: 35,
      totalStoneWt: 0.120,
    },
    ReceiveFromKarigar: {
      name: "Gopal Santra",
      voucherDate: "06/01/2025",
      address: "",
      items: [
        {
          pcs: 1,
          description: "Jadau Necklace Set",
          orderDesign: "[1161258021] /1762",
          issueNo: "IS/CA25/3439",
          purity: "22K",
          grossWt: 74.750,
          netWt: 0.000,
          otherWt: 0.000,
          totalWt: 74.750,
        },
      ],
      grandTotal: "96.960",
    },
    ReceiveFromHallmark: {
      name: "PRINCE HALLMARKING",
      voucherDate: "06/01/2025",
      address: "",
      items: [
        {
          pcs: 1,
          code: "CA25-01013",
          description: "Diamond S.Pendant (18K)",
          design: "",
          grossWt: 2.320,
          netWt: 2.200,
          stoneWt: 0.000,
          lossWt: 0.000,
        },
      ],
      totalGrossWt: 35.01,
      totalNetWt: 30.230,
    },
    IssueToHallmark: {
      name: "PRINCE HALLMARKING",
      voucherDate: "04/01/2025",
      address: "",
      purpose: "Hallmarking",
      items: [
        {
          pcs: 1,
          code: "",
          description: "Diamond S.Pendant (18K)",
          design: "",
          grossWt: 2.320,
          netWt: 2.200,
          stoneWt: 0.000,
        },
      ],
      totalGrossWt: 35.010,
      totalNetWt: 30.230,
      totalStoneWt: 0.000,
    },
    CustomerOrder: {
      name: "Isha Kapoor",
      orderNo: "CA25/01087",
      orderDate: "05/01/2025",
      deliveryDate: "01/02/2025",
      address: "116, Chakraberia Road, North",
      purity: "14K",
      goldRate: "",
      phone: "8017838449",
      items: [
        {
          pcs: 1,
          description: "Lab Diamond Ladies Ring",
          size: "7 no",
          netWt: 4.000,
          stoneWt: "",
          makingWt: "",
          rate: 8000.00,
        },
      ],
      designNotes: "Design as per Xerox RHC, HMC and 3% GST Extra",
      salesPerson: "Lovely Jhawar (C)",
    },
    AccountingVoucher: {
      date: "26-11-2024",
      entries: [
        { particulars: "Swastik Jewels", debit: "68.00", credit: "" },
        { particulars: "ORO Precious Metals Pvt Ltd.", debit: "619.00", credit: "" },
        { particulars: "Swarn Shilp Chains and Jewellers Pvt Ltd", debit: "184.00", credit: "" },
        { particulars: "T.D.S. 194Q (Purchase)", debit: "", credit: "871.00" },
      ],
      narration: "Being TDS @ 0.10% deducted",
      amountInWords: "eight hundred seventy one",
    },
    JobOrder: {
      name: "Anup Santra",
      orderNo: "dnk-1941n",
      voucherNo: "IV/2678",
      address: "",
      voucherDate: "06/01/2025",
      items: [
        {
          pcs: 1,
          description: "Diamond Necklace (18K)",
          orderNo: "dnk-1941n",
          orderSl: "st",
          deliveryDate: "25/01/2025",
          design: "dnk-1941n",
          size: "",
          netWt: 45.000,
        },
      ],
      totalNetWt: 55.000,
    },
    PurchaseVoucher: {
      name: "Sujata Gold",
      billNo: "C2425/00413",
      address: "1st floor, 107 & 108, Vaishali Industrial Estate, Mhatre Wadi Road, Vaishali Diamond, Dahisar West",
      date: "07/12/2024",
      panNo: "ARJPJ7359M",
      gstin: "27ARJPJ7359M1Z1",
      state: "Maharashtra (27)",
      items: [
        {
          particulars: "New Gold Ornament",
          pcs: 0,
          ct: "",
          wt: "11.660",
          fineWt: "0.00",
          rate: "7548.17",
          value: "88011.65",
          making: "0.00",
          amount: "88011.65",
        },
      ],
      subtotal: "88011.65",
      making: "0.00",
      igstRate: 3.00,
      igstAmount: "2640.35",
      roundOff: "0.00",
      total: "90652.00",
      narration: "",
      inWords: "Rupees Ninety Thousand Six Hundred Fifty Two Only",
    },
  };

  const handlePrint = (component) => {
    try {
      // Create a temporary container for the print content
      const printContainer = document.createElement('div');
      printContainer.style.display = 'none';
      document.body.appendChild(printContainer);

      // Add print styles
      const style = document.createElement('style');
      style.textContent = `
        @media print {
          body > *:not(#print-root) {
            display: none !important;
          }
          #print-root {
            display: block !important;
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            padding: 20px;
            height: auto;
          }
          @page {
            size: auto;
            margin: 0.5cm;
          }
          table {
            page-break-inside: avoid;
          }
          tr {
            page-break-inside: avoid;
            page-break-after: auto;
          }
        }
      `;
      document.head.appendChild(style);
      
      // Set up print container
      printContainer.id = 'print-root';

      // Render component
      const ComponentToRender = components[component];
      ReactDOM.render(
        <ComponentToRender data={componentData[component] || {}} />,
        printContainer,
        () => {
          // Wait for render to complete
          setTimeout(() => {
            printContainer.style.display = 'block';
            window.print();
            
            // Cleanup after printing
            const cleanup = () => {
              document.body.removeChild(printContainer);
              document.head.removeChild(style);
            };

            if (window.matchMedia) {
              window.matchMedia('print').addEventListener('change', (mql) => {
                if (!mql.matches) {
                  cleanup();
                }
              });
            } else {
              // Fallback for browsers that don't support matchMedia
              setTimeout(cleanup, 1000);
            }
          }, 500);
        }
      );
    } catch (error) {
      console.error('Printing failed:', error);
    }
  };

  return (
    <div className="p-6 text-center">
      <h1 className="text-2xl font-bold mb-6">Print Components</h1>
      <div className="grid grid-cols-2 gap-4 mb-6">
        {Object.keys(components).map((comp) => (
          <button
            key={comp}
            onClick={() => handlePrint(comp)}
            className="bg-primary hover:bg-primary text-white py-2 px-4 rounded transition-colors"
          >
            Print {comp}
          </button>
        ))}
      </div>
    </div>
  );
};

export default TestComponentsDemo;