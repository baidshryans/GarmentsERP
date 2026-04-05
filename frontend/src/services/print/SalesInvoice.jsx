import React from "react";

// ─── Helpers ────────────────────────────────────────────────────────────────

const fmt = (n, dec = 2) => {
  if (n === null || n === undefined || n === '') return '';
  const num = parseFloat(n);
  if (isNaN(num)) return '';
  return num.toLocaleString('en-IN', { minimumFractionDigits: dec, maximumFractionDigits: dec });
};

const fmtDate = (s) => {
  if (!s) return '';
  const d = new Date(s);
  if (isNaN(d)) return s;
  return `${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`;
};

function numberToWords(num) {
  if (!num && num !== 0) return '';
  const units = ['','One','Two','Three','Four','Five','Six','Seven','Eight','Nine'];
  const teens = ['Ten','Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen','Seventeen','Eighteen','Nineteen'];
  const tens  = ['','','Twenty','Thirty','Forty','Fifty','Sixty','Seventy','Eighty','Ninety'];
  const group = (n) => {
    if (n === 0) return '';
    let r = '';
    const h = Math.floor(n/100), rem = n%100;
    if (h) r += units[h]+' Hundred'+(rem?' ':'');
    if (rem>=10&&rem<20) r += teens[rem-10];
    else { if (Math.floor(rem/10)) r += tens[Math.floor(rem/10)]+(rem%10?' ':''); if (rem%10) r += units[rem%10]; }
    return r;
  };
  const whole = Math.floor(Math.abs(num));
  if (whole === 0) return 'Rupees Zero Only';
  const crore = Math.floor(whole/10000000);
  const lakh  = Math.floor((whole%10000000)/100000);
  const thou  = Math.floor((whole%100000)/1000);
  const rest  = whole%1000;
  let res = '';
  if (crore) res += group(crore)+' Crore ';
  if (lakh)  res += group(lakh)+' Lakh ';
  if (thou)  res += group(thou)+' Thousand ';
  if (rest)  res += group(rest);
  return 'Rupees '+res.trim()+' Only';
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const PAGE = {
  fontFamily: 'Arial, sans-serif',
  fontSize: '8px',
  lineHeight: '1.25',
  color: '#000',
  backgroundColor: '#fff',
  padding: '10mm 8mm',
  width: '210mm',
  boxSizing: 'border-box',
};

const OUTER_TABLE = {
  width: '100%',
  borderCollapse: 'collapse',
  border: '1.5px solid #000',
};

const TD = (extra = {}) => ({
  border: '1px solid #000',
  padding: '4px 5px',
  verticalAlign: 'top',
  ...extra,
});

const BOLD = { fontWeight: 'bold' };

const TH_CELL = (extra = {}) => ({
  border: '1px solid #000',
  padding: '3px 4px',
  fontWeight: 'bold',
  textAlign: 'center',
  backgroundColor: '#f0f0f0',
  fontSize: '7.5px',
  ...extra,
});

const NUM_CELL = {
  border: '1px solid #000',
  padding: '3px 4px',
  textAlign: 'right',
  fontSize: '7.5px',
};

const STR_CELL = {
  border: '1px solid #000',
  padding: '3px 4px',
  textAlign: 'left',
  fontSize: '7.5px',
};

const CTR_CELL = {
  border: '1px solid #000',
  padding: '3px 4px',
  textAlign: 'center',
  fontSize: '7.5px',
};

// ─── Component ───────────────────────────────────────────────────────────────

const SalesInvoice = ({ data = {} }) => {
  const d = data;

  const printStyle = `
    @media print {
      @page { size: A4 portrait; margin: 8mm; }
      body  { margin: 0; padding: 0; }
      .no-print { display: none !important; }
    }
    * { box-sizing: border-box; }
  `;

  return (
    <div style={PAGE}>
      <style>{printStyle}</style>

      {/* ── SECTION 1: Header ─────────────────────────────────────────────── */}
      <div style={{ textAlign: 'center', marginBottom: '4px' }}>
        <div style={{ fontSize: '14px', fontWeight: 'bold', letterSpacing: '1px' }}>
          {d.company_name || 'JEWEL INDIA JEWELLERS'}
        </div>
        <div style={{ fontSize: '8px', marginTop: '2px' }}>{d.company_address}</div>
        <div style={{ fontSize: '8px' }}>
          {d.company_phone && `Ph: ${d.company_phone}`}
          {d.company_phone && d.company_email && '  |  '}
          {d.company_email && `Email: ${d.company_email}`}
        </div>
        <div style={{ fontSize: '8px', marginTop: '1px' }}>
          {d.company_pan  && `PAN: ${d.company_pan}`}
          {d.company_pan  && d.company_tan && '  |  '}
          {d.company_tan  && `TAN: ${d.company_tan}`}
          {d.company_cin  && (d.company_pan || d.company_tan) && '  |  '}
          {d.company_cin  && `CIN: ${d.company_cin}`}
        </div>
        <div style={{ fontSize: '10px', fontWeight: 'bold', marginTop: '4px', letterSpacing: '2px' }}>
          TAX INVOICE
        </div>
        <div style={{ fontSize: '7px', color: '#444' }}>ORIGINAL / DUPLICATE / TRIPLICATE</div>
      </div>

      <table style={OUTER_TABLE}>
        <tbody>

          {/* ── SECTION 2: Billing Address ─────────────────────────────────── */}
          <tr>
            <td style={{ ...TD(), width: '50%' }}>
              <div style={{ ...BOLD, fontSize: '7.5px', marginBottom: '3px' }}>DETAILS OF BUYER (BILLING ADDRESS)</div>
              <Row label="NAME"    value={d.customer_name} />
              <Row label="ADDRESS" value={d.customer_address} />
              <RowInline
                left={<><B>STATE: </B>{d.customer_state}</>}
                right={<><B>CODE: </B>{d.customer_state_code}</>}
              />
              {d.customer_aadhar && <Row label="AADHAAR" value={d.customer_aadhar} />}
              {d.customer_dl     && <Row label="DRIVING LICENSE" value={d.customer_dl} />}
              {d.customer_pan    && <Row label="PAN NO" value={d.customer_pan} />}
              {d.customer_gstin  && <Row label="GSTIN NO" value={d.customer_gstin} />}
            </td>
            <td style={{ ...TD(), width: '50%' }}>
              <Row label="INVOICE NO"   value={d.gst_billno || d.billno} />
              <Row label="INVOICE DATE" value={fmtDate(d.date1)} />
              <Row label="GSTIN NO"     value={d.company_gstin} />
              <RowInline
                left={<><B>STATE: </B>{d.company_state}</>}
                right={<><B>CODE: </B>{d.company_state_code}</>}
              />
              <Row label="TAX PAYABLE ON REVERSE CHARGE" value="NO" />
            </td>
          </tr>

          {/* ── SECTION 3: Shipping / Transport ────────────────────────────── */}
          <tr>
            <td style={TD()}>
              <div style={{ ...BOLD, fontSize: '7.5px', marginBottom: '3px' }}>DETAILS OF CONSIGNEE (SHIPPING ADDRESS)</div>
              <Row label="NAME"    value={d.customer_name} />
              <Row label="ADDRESS" value={d.customer_address} />
              <RowInline
                left={<><B>STATE: </B>{d.customer_state}</>}
                right={<><B>CODE: </B>{d.customer_state_code}</>}
              />
              {d.customer_pan   && <Row label="PAN NO"   value={d.customer_pan} />}
              {d.customer_gstin && <Row label="GSTIN NO" value={d.customer_gstin} />}
            </td>
            <td style={TD()}>
              <Row label="MODE OF TRANSPORT"       value={d.mode_of_transport} />
              <Row label="VEHICLE NUMBER"          value="" />
              <Row label="SUPPLY DATE"             value={fmtDate(d.date1)} />
              <Row label="PLACE OF SUPPLY"         value={d.place_of_supply} />
              <Row label="ELECTRONIC REF. NUMBER"  value="" />
              <Row label="METAL RATE"              value={d.metal_rate_str} />
            </td>
          </tr>

          {/* ── SECTION 4: Items Table ──────────────────────────────────────── */}
          <tr>
            <td colSpan={2} style={{ padding: 0, border: '1px solid #000' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr>
                    <th style={TH_CELL({ width: '28px' })}>S.N<br/>PCS</th>
                    <th style={TH_CELL({ textAlign: 'left', minWidth: '90px' })}>ITEM DESCRIPTION</th>
                    <th style={TH_CELL({ width: '38px' })}>HSN</th>
                    <th style={TH_CELL({ width: '32px' })}>PURITY</th>
                    <th style={TH_CELL({ width: '32px' })}>GW</th>
                    <th style={TH_CELL({ width: '32px' })}>NW</th>
                    <th style={TH_CELL({ width: '44px' })}>RATE</th>
                    <th style={TH_CELL({ width: '52px' })}>METAL<br/>VALUE</th>
                    <th style={TH_CELL({ width: '48px' })}>STONE<br/>VALUE</th>
                    <th style={TH_CELL({ width: '48px' })}>MAKING<br/>CHRG</th>
                    <th style={TH_CELL({ width: '44px' })}>OTHER<br/>CHRG</th>
                    <th style={TH_CELL({ width: '56px' })}>AMOUNT</th>
                  </tr>
                </thead>
                <tbody>
                  {(d.items || []).map((item, idx) => (
                    <React.Fragment key={idx}>
                      {/* Main barcode row — bold */}
                      <tr>
                        <td style={{ ...CTR_CELL, fontWeight: 'bold' }}>
                          {item.sn}<br/>{item.pcs}
                        </td>
                        <td style={{ ...STR_CELL, fontWeight: 'bold' }}>
                          {item.item_name}
                        </td>
                        <td style={{ ...CTR_CELL, fontWeight: 'bold' }}>{item.hsn}</td>
                        <td style={{ ...CTR_CELL, fontWeight: 'bold' }}>{item.purity}</td>
                        <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{fmt(item.gw, 3)}</td>
                        <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{fmt(item.nw, 3)}</td>
                        <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{item.rate ? fmt(item.rate, 0) : '-'}</td>
                        <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{item.metal_value ? fmt(item.metal_value) : '-'}</td>
                        <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{item.stone_value ? fmt(item.stone_value) : '-'}</td>
                        <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{item.making ? fmt(item.making) : '-'}</td>
                        <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{item.other_value ? fmt(item.other_value) : '-'}</td>
                        <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{fmt(item.amount)}</td>
                      </tr>
                      {/* Sub-item detail rows */}
                      {(item.sub_rows || []).map((sub, si) => (
                        <tr key={si} style={{ backgroundColor: '#fafafa' }}>
                          <td style={CTR_CELL}>{sub.pcs || ''}</td>
                          <td style={{ ...STR_CELL, paddingLeft: '12px', color: '#333' }}>
                            {sub.text}
                          </td>
                          <td style={CTR_CELL}></td>
                          <td style={CTR_CELL}>{sub.metal_purity || ''}</td>
                          <td style={NUM_CELL}>{sub.gw ? fmt(sub.gw, 3) : ''}</td>
                          <td style={NUM_CELL}></td>
                          <td style={NUM_CELL}>{sub.rate ? fmt(sub.rate, 0) : ''}</td>
                          <td style={NUM_CELL}>
                            {sub.item_type === 'R' ? fmt(sub.amount) : ''}
                          </td>
                          <td style={NUM_CELL}>
                            {sub.item_type === 'S' ? fmt(sub.amount) : ''}
                          </td>
                          <td style={NUM_CELL}></td>
                          <td style={NUM_CELL}>
                            {!['R','S','M'].includes(sub.item_type) ? fmt(sub.amount) : ''}
                          </td>
                          <td style={NUM_CELL}></td>
                        </tr>
                      ))}
                    </React.Fragment>
                  ))}
                  {/* Column totals row */}
                  {(d.items || []).length > 0 && (
                    <tr style={{ backgroundColor: '#f0f0f0' }}>
                      <td style={{ ...CTR_CELL, fontWeight: 'bold' }}>
                        {(d.items||[]).reduce((s,i)=>s+(i.pcs||0),0)}
                      </td>
                      <td style={{ ...STR_CELL, fontWeight: 'bold' }}>TOTAL</td>
                      <td style={CTR_CELL}></td>
                      <td style={CTR_CELL}></td>
                      <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>
                        {fmt((d.items||[]).reduce((s,i)=>s+i.gw,0), 3)}
                      </td>
                      <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>
                        {fmt((d.items||[]).reduce((s,i)=>s+i.nw,0), 3)}
                      </td>
                      <td style={NUM_CELL}></td>
                      <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>
                        {fmt((d.items||[]).reduce((s,i)=>s+i.metal_value,0))}
                      </td>
                      <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>
                        {fmt((d.items||[]).reduce((s,i)=>s+i.stone_value,0))}
                      </td>
                      <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>
                        {fmt((d.items||[]).reduce((s,i)=>s+i.making,0))}
                      </td>
                      <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>
                        {fmt((d.items||[]).reduce((s,i)=>s+i.other_value,0))}
                      </td>
                      <td style={{ ...NUM_CELL, fontWeight: 'bold' }}>{fmt(d.items_total)}</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </td>
          </tr>

          {/* ── SECTION 5: Summary ──────────────────────────────────────────── */}
          <tr>
            {/* Left: Purchase / Payment details */}
            <td style={TD()}>
              <div style={{ ...BOLD, marginBottom: '3px' }}>PURCHASE DETAILS</div>
              <div style={{ fontSize: '7px', marginBottom: '4px' }}>
                <div style={BOLD}>BUY BACK POLICY / DEDUCTIONS</div>
                <div>STONES</div>
                <div>GOLD UPTO 6 MCT = 10%, ABOVE 6MCT TO 24MCT = 5%, ABOVE = 5%</div>
                <div>PRECIOUS COL STONE = 5%, IMITATION = 10%</div>
              </div>

              <div style={{ ...BOLD, marginBottom: '2px' }}>MODE OF PAYMENT</div>
              {d.cash > 0 && (
                <div style={{ fontSize: '7px' }}>CASH: ₹{fmt(d.cash)}</div>
              )}
              {(d.bank_lines || []).map((line, i) => (
                <div key={i} style={{ fontSize: '7px' }}>BANK: {line}</div>
              ))}

              <div style={{ fontSize: '7px', fontStyle: 'italic', marginTop: '6px' }}>
                <div>~ GOODS SOLD ARE DELIVERED FROM KOLKATA SHOWROOM</div>
                <div>~ SUBJECT TO KOLKATA JURISDICTION ONLY</div>
              </div>
            </td>

            {/* Right: Tax summary */}
            <td style={TD()}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '7.5px' }}>
                <tbody>
                  <SumRow label="TOTAL ITEMS VALUE"     value={fmt(d.items_total)} />
                  {d.discount > 0 && <SumRow label="LESS DISCOUNT"       value={`- ${fmt(d.discount)}`} />}
                  {d.freight_charge > 0 && <SumRow label="FREIGHT CHARGES" value={fmt(d.freight_charge)} />}
                  <SumRow label="TOTAL AMT BEFORE TAX"  value={fmt(d.taxable_value)} bold />
                  {d.sgst_per > 0 && <SumRow label={`ADD: SGST @ ${d.sgst_per}%`} value={fmt(d.sgst_amt)} />}
                  {d.cgst_per > 0 && <SumRow label={`ADD: CGST @ ${d.cgst_per}%`} value={fmt(d.cgst_amt)} />}
                  {d.igst_per > 0 && <SumRow label={`ADD: IGST @ ${d.igst_per}%`} value={fmt(d.igst_amt)} />}
                  {d.tcs_per  > 0 && <SumRow label={`ADD: TCS @ ${d.tcs_per}%`}   value={fmt(d.tcs_amt)}  />}
                  <SumRow label="TOTAL AMT AFTER TAX"   value={fmt(d.total_bill_value)} bold />
                  {d.cash > 0 && <SumRow label="LESS: CASH RECEIVED"  value={`- ${fmt(d.cash)}`} />}
                  <SumRow label="NET RECEIVABLE"         value={fmt(d.net_receivable)} bold highlight />
                </tbody>
              </table>
            </td>
          </tr>

          {/* ── SECTION 6: Amount in words + Signature ──────────────────────── */}
          <tr>
            <td style={TD()}>
              <div style={{ ...BOLD, fontSize: '7.5px', marginBottom: '2px' }}>Amount in Words:</div>
              <div style={{ fontStyle: 'italic', fontSize: '8px' }}>
                {numberToWords(d.total_bill_value)}
              </div>
              {d.mrp > 0 && (
                <div style={{ ...BOLD, marginTop: '6px', fontSize: '7.5px' }}>
                  MRP: ₹{fmt(d.mrp)}
                </div>
              )}
            </td>
            <td style={{ ...TD(), textAlign: 'center' }}>
              <div style={{ ...BOLD, fontSize: '8px', marginBottom: '30px' }}>
                FOR {d.company_name || 'JEWEL INDIA JEWELLERS'}
              </div>
              <div style={{ borderTop: '1px solid #000', paddingTop: '4px', ...BOLD, fontSize: '7.5px' }}>
                AUTHORISED SIGNATORY
              </div>
            </td>
          </tr>

        </tbody>
      </table>

      {/* Footer */}
      <div style={{ textAlign: 'center', fontSize: '6.5px', fontStyle: 'italic', marginTop: '4px', color: '#555' }}>
        THIS IS A COMPUTER GENERATED INVOICE AND DOES NOT REQUIRE A SIGNATURE. SUBJECT TO KOLKATA JURISDICTION.
      </div>
    </div>
  );
};

// ─── Small helper sub-components ─────────────────────────────────────────────

const B = ({ children }) => <span style={{ fontWeight: 'bold' }}>{children}</span>;

const Row = ({ label, value }) => (
  <div style={{ fontSize: '7.5px', marginBottom: '2px' }}>
    <B>{label}: </B>{value || ''}
  </div>
);

const RowInline = ({ left, right }) => (
  <div style={{ fontSize: '7.5px', marginBottom: '2px', display: 'flex', gap: '20px' }}>
    <span>{left}</span>
    <span>{right}</span>
  </div>
);

const SumRow = ({ label, value, bold, highlight }) => (
  <tr style={highlight ? { backgroundColor: '#e8e8e8' } : {}}>
    <td style={{
      border: '1px solid #000', padding: '2px 4px',
      fontWeight: bold ? 'bold' : 'normal',
      backgroundColor: highlight ? '#e8e8e8' : (bold ? '#f5f5f5' : 'transparent'),
    }}>
      {label}
    </td>
    <td style={{
      border: '1px solid #000', padding: '2px 4px', textAlign: 'right',
      fontWeight: bold ? 'bold' : 'normal',
      backgroundColor: highlight ? '#e8e8e8' : (bold ? '#f5f5f5' : 'transparent'),
    }}>
      {value}
    </td>
  </tr>
);

export default SalesInvoice;
