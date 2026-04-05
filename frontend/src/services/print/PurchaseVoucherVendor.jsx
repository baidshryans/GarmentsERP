
import React from 'react';

const PurchaseVoucher = ({ data = {} }) => {
  const voucherData = data;

  const formatDate = (dateString) => {
    if (!dateString) return "";
    const date = new Date(dateString);
    return `${date.getDate().toString().padStart(2, '0')}/${(date.getMonth() + 1).toString().padStart(2, '0')}/${date.getFullYear()}`;
  };

  const formatCurrency = (amount) => {
    if (!amount && amount !== 0) return "";
    return new Intl.NumberFormat('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(amount);
  };

  const numberToWords = (num) => {
    if (!num && num !== 0) return "";
    const units = ['', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine'];
    const teens = ['Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen'];
    const tens = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];

    if (num === 0) return 'Zero';

    const wholePart = Math.floor(Math.abs(num));
    if (wholePart === 0) return 'Rupees Zero Only';

    // Indian numbering: ones, tens, hundreds, then groups of 2 (thousands, lakhs, crores)
    const crore = Math.floor(wholePart / 10000000);
    const lakh = Math.floor((wholePart % 10000000) / 100000);
    const thousand = Math.floor((wholePart % 100000) / 1000);
    const hundred = Math.floor((wholePart % 1000) / 100);
    const remainder = wholePart % 100;

    const convertTwoDigit = (n) => {
      if (n === 0) return '';
      if (n < 10) return units[n];
      if (n < 20) return teens[n - 10];
      return tens[Math.floor(n / 10)] + (n % 10 ? ' ' + units[n % 10] : '');
    };

    let result = '';
    if (crore > 0) result += convertTwoDigit(crore) + ' Crore ';
    if (lakh > 0) result += convertTwoDigit(lakh) + ' Lakh ';
    if (thousand > 0) result += convertTwoDigit(thousand) + ' Thousand ';
    if (hundred > 0) result += units[hundred] + ' Hundred ';
    if (remainder > 0) {
      if (result) result += 'and ';
      result += convertTwoDigit(remainder);
    }

    return 'Rupees ' + result.trim() + ' Only';
  };

  // Calculate making total from all items
  const calculateMakingTotal = () => {
    if (!voucherData.purchasevoucheritems_set) return 0;
    return voucherData.purchasevoucheritems_set.reduce((sum, item) => sum + (item.making_value || 0), 0);
  };

  // Styles
  const s = {
    page: {
      fontFamily: 'Arial, sans-serif',
      fontSize: '11px',
      lineHeight: '1.3',
      color: '#000',
      maxWidth: '210mm',
      margin: '0 auto',
      padding: '10px',
    },
    headerWrap: {
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      marginBottom: '6px',
      position: 'relative',
    },
    companyName: {
      fontSize: '20px',
      fontWeight: 'bold',
      textAlign: 'center',
    },
    companyDetail: {
      fontSize: '11px',
      textAlign: 'center',
      margin: '1px 0',
    },
    titleRow: {
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      margin: '10px 0 6px 0',
    },
    titleCenter: {
      fontSize: '13px',
      fontWeight: 'bold',
      textDecoration: 'underline',
      textAlign: 'center',
      flex: 1,
    },
    titleRight: {
      fontSize: '11px',
      textAlign: 'right',
      whiteSpace: 'nowrap',
    },
    outerTable: {
      width: '100%',
      border: '2px solid #000',
      borderCollapse: 'collapse',
    },
    cell: {
      border: '1px solid #000',
      padding: '4px 6px',
      verticalAlign: 'top',
    },
    thCell: {
      border: '1px solid #000',
      padding: '3px 4px',
      fontWeight: 'bold',
      fontSize: '10px',
      textAlign: 'center',
      backgroundColor: '#fff',
    },
    itemCell: {
      border: '1px solid #000',
      padding: '2px 4px',
      fontSize: '10px',
      verticalAlign: 'top',
    },
    subItemCell: {
      borderLeft: '1px solid #000',
      borderRight: '1px solid #000',
      borderTop: 'none',
      borderBottom: 'none',
      padding: '1px 4px',
      fontSize: '10px',
      verticalAlign: 'top',
    },
    totalLabel: {
      padding: '2px 8px',
      textAlign: 'right',
      fontWeight: 'bold',
      fontSize: '10px',
      border: '1px solid #000',
    },
    totalValue: {
      padding: '2px 8px',
      textAlign: 'right',
      fontSize: '10px',
      border: '1px solid #000',
    },
  };

  const items = voucherData.purchasevoucheritems_set || [];

  return (
    <div style={s.page}>
      {/* ========== COMPANY HEADER ========== */}
      <div style={s.headerWrap}>
        <div style={{ textAlign: 'center' }}>
          <div style={s.companyName}>{voucherData.company_name || 'JEWEL INDIA'}</div>
          {voucherData.company_address && (
            <div style={s.companyDetail}>{voucherData.company_address}</div>
          )}
          {voucherData.company_phone && (
            <div style={s.companyDetail}>Ph: {voucherData.company_phone}</div>
          )}
          {voucherData.company_email && (
            <div style={s.companyDetail}>Email: {voucherData.company_email}</div>
          )}
          {(voucherData.company_pan || voucherData.company_tan) && (
            <div style={s.companyDetail}>
              {voucherData.company_pan && `PAN: ${voucherData.company_pan}`}
              {voucherData.company_pan && voucherData.company_tan && '  |  '}
              {voucherData.company_tan && `TAN: ${voucherData.company_tan}`}
            </div>
          )}
          {voucherData.company_cin && (
            <div style={s.companyDetail}>CIN: {voucherData.company_cin}</div>
          )}
        </div>
      </div>

      {/* ========== TITLE ROW ========== */}
      <div style={s.titleRow}>
        <div style={{ flex: 1 }}></div>
        <div style={s.titleCenter}>
          PURCHASE VOUCHER ({(voucherData.voucher_type || 'DEALER').toUpperCase()})
        </div>
        <div style={{ ...s.titleRight, flex: 1 }}>Original / Duplicate</div>
      </div>

      {/* ========== MAIN OUTER TABLE ========== */}
      <table style={s.outerTable}>
        <tbody>
          {/* ---- Vendor / Bill Info Row ---- */}
          <tr>
            <td style={{ ...s.cell, width: '65%' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <tbody>
                  <tr>
                    <td style={{ padding: '2px 0', fontWeight: 'bold', width: '70px' }}>Name :</td>
                    <td style={{ padding: '2px 0' }}>{voucherData.ldgr_name || ''}</td>
                  </tr>
                  <tr>
                    <td style={{ padding: '2px 0', fontWeight: 'bold', verticalAlign: 'top' }}>Address :</td>
                    <td style={{ padding: '2px 0' }}>{voucherData.vendor_address || ''}</td>
                  </tr>
                  <tr>
                    <td colSpan="2" style={{ padding: '4px 0 2px 0' }}>
                      <span style={{ fontWeight: 'bold' }}>PAN No.</span> {voucherData.vendor_pan || ''}
                      &nbsp;&nbsp;&nbsp;&nbsp;
                      <span style={{ fontWeight: 'bold' }}>GSTIN</span> {voucherData.vendor_gstin || ''}
                      &nbsp;&nbsp;&nbsp;&nbsp;
                      <span style={{ fontWeight: 'bold' }}>State :</span> {voucherData.pos_name || ''}{voucherData.place_of_supply ? ` (${voucherData.place_of_supply})` : ''}
                    </td>
                  </tr>
                </tbody>
              </table>
            </td>
            <td style={{ ...s.cell, width: '35%' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <tbody>
                  <tr>
                    <td style={{ padding: '2px 0', fontWeight: 'bold', width: '60px' }}>Bill No.</td>
                    <td style={{ padding: '2px 0' }}>{voucherData.billno || ''}</td>
                  </tr>
                  <tr>
                    <td style={{ padding: '2px 0', fontWeight: 'bold' }}>Date</td>
                    <td style={{ padding: '2px 0' }}>{formatDate(voucherData.date1)}</td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>

          {/* ---- Items Table ---- */}
          <tr>
            <td colSpan="2" style={{ border: '1px solid #000', padding: 0 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={{ ...s.thCell, width: '3%' }}>SL</th>
                    <th style={{ ...s.thCell, width: '24%', textAlign: 'left' }}>PARTICULARS</th>
                    <th style={{ ...s.thCell, width: '5%' }}>PCS</th>
                    <th style={{ ...s.thCell, width: '7%' }}>CT</th>
                    <th style={{ ...s.thCell, width: '8%' }}>WT</th>
                    <th style={{ ...s.thCell, width: '8%' }}>FINE WT</th>
                    <th style={{ ...s.thCell, width: '9%' }}>RATE</th>
                    <th style={{ ...s.thCell, width: '10%' }}>VALUE</th>
                    <th style={{ ...s.thCell, width: '8%' }}>MAKING</th>
                    <th style={{ ...s.thCell, width: '10%' }}>AMOUNT</th>
                  </tr>
                </thead>
                <tbody>
                  {items.length > 0 ? (
                    items.map((item, idx) => {
                      const subItems = item.purchasevoucherdetails_set || [];
                      const amount = (item.item_value || 0) + (item.making_value || 0);
                      return (
                        <React.Fragment key={idx}>
                          {/* Main Item Row */}
                          <tr>
                            <td style={{ ...s.itemCell, textAlign: 'center', fontWeight: 'bold' }}>
                              {item.sl_no || (idx + 1)}.
                            </td>
                            <td style={{ ...s.itemCell, fontWeight: 'bold' }}>
                              {item.item || ''}
                            </td>
                            <td style={{ ...s.itemCell, textAlign: 'center' }}>
                              {item.pcs != null ? item.pcs : ''}
                            </td>
                            <td style={{ ...s.itemCell, textAlign: 'center' }}></td>
                            <td style={{ ...s.itemCell, textAlign: 'right' }}>
                              {item.gw || ''}
                            </td>
                            <td style={{ ...s.itemCell, textAlign: 'right' }}></td>
                            <td style={{ ...s.itemCell, textAlign: 'right' }}></td>
                            <td style={{ ...s.itemCell, textAlign: 'right' }}></td>
                            <td style={{ ...s.itemCell, textAlign: 'right' }}>
                              {formatCurrency(item.making_value)}
                            </td>
                            <td style={{ ...s.itemCell, textAlign: 'right' }}>
                              {formatCurrency(amount)}
                            </td>
                          </tr>

                          {/* Sub-Item Rows */}
                          {subItems.map((sub, sIdx) => (
                            <tr key={`sub-${idx}-${sIdx}`}>
                              <td style={{ ...s.subItemCell, textAlign: 'center' }}></td>
                              <td style={{ ...s.subItemCell, paddingLeft: '20px' }}>
                                {sub.sub_item || ''}
                              </td>
                              <td style={{ ...s.subItemCell, textAlign: 'center' }}></td>
                              <td style={{ ...s.subItemCell, textAlign: 'center' }}>
                                {sub.sub_ct || ''}
                              </td>
                              <td style={{ ...s.subItemCell, textAlign: 'right' }}>
                                {sub.sub_gw || ''}
                              </td>
                              <td style={{ ...s.subItemCell, textAlign: 'right' }}>
                                {sub.fine_wt || ''}
                              </td>
                              <td style={{ ...s.subItemCell, textAlign: 'right' }}>
                                {formatCurrency(sub.rate)}
                              </td>
                              <td style={{ ...s.subItemCell, textAlign: 'right' }}>
                                {formatCurrency(sub.value)}
                              </td>
                              <td style={{ ...s.subItemCell, textAlign: 'right' }}></td>
                              <td style={{ ...s.subItemCell, textAlign: 'right' }}></td>
                            </tr>
                          ))}
                        </React.Fragment>
                      );
                    })
                  ) : (
                    <>
                      <tr><td colSpan="10" style={{ ...s.itemCell, padding: '20px' }}>&nbsp;</td></tr>
                      <tr><td colSpan="10" style={{ ...s.itemCell, padding: '20px' }}>&nbsp;</td></tr>
                    </>
                  )}

                  {/* ---- Totals rows (right-aligned in last 2 columns) ---- */}
                  <tr>
                    <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                    <td style={s.totalLabel}>SUBTOTAL</td>
                    <td style={s.totalValue}>{formatCurrency(voucherData.bill_value)}</td>
                  </tr>
                  <tr>
                    <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                    <td style={s.totalLabel}>MAKING</td>
                    <td style={s.totalValue}>{formatCurrency(calculateMakingTotal())}</td>
                  </tr>
                  {voucherData.discount_amt > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>DISCOUNT</td>
                      <td style={s.totalValue}>-{formatCurrency(voucherData.discount_amt)}</td>
                    </tr>
                  )}
                  {voucherData.hallmark_charge > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>HALLMARK</td>
                      <td style={s.totalValue}>{formatCurrency(voucherData.hallmark_charge)}</td>
                    </tr>
                  )}
                  {voucherData.freight_amt > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>FREIGHT</td>
                      <td style={s.totalValue}>{formatCurrency(voucherData.freight_amt)}</td>
                    </tr>
                  )}
                  {voucherData.add_chrg_amt1 > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>{voucherData.add_chrg_cap1 || 'ADD CHG1'}</td>
                      <td style={s.totalValue}>{formatCurrency(voucherData.add_chrg_amt1)}</td>
                    </tr>
                  )}
                  {voucherData.add_chrg_amt2 > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>{voucherData.add_chrg_cap2 || 'ADD CHG2'}</td>
                      <td style={s.totalValue}>{formatCurrency(voucherData.add_chrg_amt2)}</td>
                    </tr>
                  )}
                  {voucherData.sgst > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>SGST@ 1.50%</td>
                      <td style={s.totalValue}>{formatCurrency(voucherData.sgst)}</td>
                    </tr>
                  )}
                  {voucherData.cgst > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>CGST@ 1.50%</td>
                      <td style={s.totalValue}>{formatCurrency(voucherData.cgst)}</td>
                    </tr>
                  )}
                  {voucherData.igst > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>IGST@ 3.00%</td>
                      <td style={s.totalValue}>{formatCurrency(voucherData.igst)}</td>
                    </tr>
                  )}
                  {voucherData.tcs_amt > 0 && (
                    <tr>
                      <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                      <td style={s.totalLabel}>TCS</td>
                      <td style={s.totalValue}>{formatCurrency(voucherData.tcs_amt)}</td>
                    </tr>
                  )}
                  <tr>
                    <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                    <td style={s.totalLabel}>ROUND OFF</td>
                    <td style={s.totalValue}>{formatCurrency(voucherData.round_off)}</td>
                  </tr>
                  <tr>
                    <td colSpan="8" style={{ border: '1px solid #000', padding: 0 }}></td>
                    <td style={{ ...s.totalLabel, fontSize: '12px', borderTop: '2px solid #000' }}>TOTAL</td>
                    <td style={{ ...s.totalValue, fontSize: '12px', fontWeight: 'bold', borderTop: '2px solid #000' }}>{formatCurrency(voucherData.total_incl_gst)}</td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>

          {/* ---- Narration ---- */}
          <tr>
            <td colSpan="2" style={{ ...s.cell, borderBottom: 'none' }}>
              <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>NARRATION:</div>
              <div style={{ minHeight: '16px', paddingLeft: '4px' }}>{voucherData.narration || ''}</div>
            </td>
          </tr>

          {/* ---- Amount in Words ---- */}
          <tr>
            <td colSpan="2" style={{ ...s.cell, borderTop: 'none', borderBottom: 'none' }}>
              <span>In Words: </span>
              <span style={{ fontWeight: 'bold' }}>{numberToWords(voucherData.total_incl_gst)}</span>
            </td>
          </tr>

          {/* ---- Footer: PAN / GSTIN / Signature ---- */}
          <tr>
            <td colSpan="2" style={{ ...s.cell, borderTop: 'none' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: '10px' }}>
                {/* Left: Company PAN / GSTIN */}
                <div>
                  <table style={{ borderCollapse: 'collapse', fontSize: '11px' }}>
                    <tbody>
                      <tr>
                        <td style={{ padding: '1px 0', fontWeight: 'bold' }}>PAN No. :</td>
                        <td style={{ padding: '1px 10px', fontWeight: 'bold' }}>{voucherData.company_pan || ''}</td>
                        <td style={{ padding: '1px 20px' }}>State :<span style={{ fontWeight: 'bold' }}>{voucherData.pos_name || ''}</span></td>
                        <td style={{ padding: '1px 20px' }}>E.&amp;.O.E</td>
                      </tr>
                      <tr>
                        <td style={{ padding: '1px 0', fontWeight: 'bold' }}>GSTIN :</td>
                        <td style={{ padding: '1px 10px', fontWeight: 'bold' }}>{voucherData.company_gstin || ''}</td>
                        <td style={{ padding: '1px 20px' }}>State Code :<span style={{ fontWeight: 'bold' }}>{voucherData.pos_name || ''}</span></td>
                        <td></td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Right: Signature Block */}
                <div style={{ textAlign: 'center', minWidth: '180px' }}>
                  <div style={{ fontSize: '11px', fontWeight: 'bold', marginBottom: '2px' }}>for {voucherData.company_name || 'JEWEL INDIA'}</div>
                  <div style={{ height: '50px' }}></div>
                  <div style={{ borderTop: '1px solid #000', paddingTop: '2px', fontSize: '10px' }}>Signature</div>
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      {/* ========== BOTTOM COMPANY FOOTER ========== */}
      <div style={{ textAlign: 'center', marginTop: '12px', fontSize: '11px', lineHeight: '1.4' }}>
        <div style={{ fontWeight: 'bold', fontSize: '12px' }}>{voucherData.company_name || 'JEWEL INDIA'}</div>
        {voucherData.company_address && <div>{voucherData.company_address}</div>}
        {voucherData.company_phone   && <div>Ph: {voucherData.company_phone}</div>}
      </div>

      {/* Print Styles */}
      <style>{`
        @media print {
          @page {
            size: A4;
            margin: 0.3in;
          }
          body {
            margin: 0;
            padding: 0;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
        }
      `}</style>
    </div>
  );
};

export default PurchaseVoucher;
