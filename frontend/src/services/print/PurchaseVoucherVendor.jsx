import React from "react";

const fmt = (n, dec = 2) => {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num)) return "";
  return num.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec });
};
const fmt3 = (n) => fmt(n, 3);
const fmtDate = (s) => {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d)) return s;
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return String(d.getDate()).padStart(2,"0") + " " + months[d.getMonth()] + " " + d.getFullYear();
};
function numberToWords(num) {
  if (!num && num !== 0) return "";
  const units = ["","One","Two","Three","Four","Five","Six","Seven","Eight","Nine"];
  const teens = ["Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen","Seventeen","Eighteen","Nineteen"];
  const tens  = ["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"];
  const group = (n) => {
    if (n === 0) return "";
    let r = "";
    const h = Math.floor(n / 100), rem = n % 100;
    if (h) r += units[h] + " Hundred" + (rem ? " " : "");
    if (rem >= 10 && rem < 20) r += teens[rem - 10];
    else { if (Math.floor(rem/10)) r += tens[Math.floor(rem/10)] + (rem%10?" ":""); if (rem%10) r += units[rem%10]; }
    return r;
  };
  const whole = Math.floor(Math.abs(num));
  if (whole === 0) return "Rupees Zero Only";
  const crore = Math.floor(whole/10000000), lakh = Math.floor((whole%10000000)/100000),
        thou  = Math.floor((whole%100000)/1000), rest = whole%1000;
  let res = "";
  if (crore) res += group(crore) + " Crore ";
  if (lakh)  res += group(lakh)  + " Lakh ";
  if (thou)  res += group(thou)  + " Thousand ";
  if (rest)  res += group(rest);
  return "Rupees " + res.trim() + " Only";
}

const FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap";

/* eslint-disable no-template-curly-in-string */
const PV_CSS = [
  "@import url('" + FONTS + "');",
  "*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}",
  "body{background:#fff}",
  ".pv-page{font-family:Inter,Arial,sans-serif;font-size:10.5px;line-height:1.35;color:#111;width:210mm;min-height:297mm;margin:0 auto;padding:8mm 10mm;background:#fff;break-after:page;page-break-after:always}",
  ".pv-page:last-of-type{break-after:auto;page-break-after:auto}",
  ".pv-header{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:4px;padding-bottom:4px;border-bottom:1.5px solid #111}",
  ".pv-logo{height:44px;width:auto;object-fit:contain}",
  ".pv-company-name{font-size:14px;font-weight:700;letter-spacing:.3px;line-height:1.2;text-align:center}",
  ".pv-company-sub{font-size:9.5px;color:#333;margin-top:2px;text-align:center}",
  ".pv-company-gstin{font-size:9.5px;font-weight:600;margin-top:1px;text-align:center}",
  ".pv-title-strip{display:flex;align-items:center;justify-content:space-between;padding:3px 6px;border:1px solid #111;margin-top:4px}",
  ".pv-title-center{font-size:12px;font-weight:700;letter-spacing:.5px;text-transform:uppercase;flex:1;text-align:center}",
  ".pv-title-side{font-size:9.5px;color:#444;white-space:nowrap;min-width:100px}",
  ".pv-title-right{text-align:right}",
  ".pv-meta-table{width:100%;border-collapse:collapse;border:1px solid #111;border-top:none;margin-top:-1px}",
  ".pv-meta-table td{border:1px solid #ccc;padding:3px 6px;vertical-align:top}",
  ".pv-section-head{font-size:8.5px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:#555;padding:2px 0 1px}",
  ".pv-label{font-weight:600;color:#333;white-space:nowrap}",
  ".pv-items-wrap{border:1px solid #111;border-top:none;margin-top:-1px}",
  ".pv-items-table{width:100%;border-collapse:collapse;table-layout:fixed}",
  ".pv-items-table th{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;text-align:center;padding:3px 2px;border-bottom:1.5px solid #111;border-right:1px solid #ccc;background:#fff}",
  ".pv-items-table th:last-child{border-right:none}",
  ".pv-items-table td{padding:2px 4px;border-bottom:1px solid #eee;border-right:1px solid #eee;vertical-align:top;font-size:10px}",
  ".pv-items-table td:last-child{border-right:none}",
  ".pv-items-table tr:last-child td{border-bottom:none}",
  ".pv-main-row td{font-weight:500}",
  ".pv-sub-row td{font-size:9.5px;color:#333;border-bottom:1px solid #f4f4f4}",
  ".pv-num{text-align:right;font-variant-numeric:tabular-nums}",
  ".pv-ctr{text-align:center}",
  ".pv-totals-table{width:100%;border-collapse:collapse;border:1px solid #111;border-top:none;margin-top:-1px}",
  ".pv-totals-table td{padding:2px 6px;border-bottom:1px solid #eee;font-size:10px}",
  ".pv-totals-table tr:last-child td{border-bottom:none}",
  ".pv-total-label{font-weight:600;text-align:right;width:50%;color:#333}",
  ".pv-total-value{font-variant-numeric:tabular-nums;text-align:right;width:22%}",
  ".pv-total-spacer{width:28%}",
  ".pv-grand-row td{font-size:11px;font-weight:700;border-top:1.5px solid #111!important;padding-top:4px!important}",
  ".pv-words-row{border:1px solid #111;border-top:none;margin-top:-1px;padding:4px 6px;font-size:10px}",
  ".pv-narr-row{border:1px solid #111;border-top:none;margin-top:-1px;padding:4px 6px;font-size:10px}",
  ".pv-footer{border:1px solid #111;border-top:none;margin-top:-1px;padding:6px;display:flex;justify-content:space-between;align-items:flex-end;font-size:10px}",
  ".pv-footer-left{line-height:1.7}",
  ".pv-footer-right{text-align:center;min-width:160px}",
  ".pv-sig{border-top:1px solid #111;padding-top:2px;margin-top:36px;font-size:9.5px;font-weight:600}",
  "@media print{@page{size:A4;margin:0}body{margin:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}.pv-page{padding:8mm 10mm}}"
].join("\n");

const PurchaseVoucherVendor = ({ data = {} }) => {
  const d = data;
  const items      = d.purchasevoucheritems_set  || [];
  const directSubs = (d.purchasevoucherdetails_set || []).filter(x => !x.main_item);
  const makingTotal = items.reduce((s, it) => s + (parseFloat(it.making_value) || 0), 0);
  const grandTotal  = parseFloat(d.total_incl_gst) || 0;

  return (
    <div className="pv-page">
      <style>{PV_CSS}</style>

      {/* ── Header ── */}
      <div className="pv-header">
        {d.company_logo_url && <img src={d.company_logo_url} alt="logo" className="pv-logo" />}
        <div>
          <div className="pv-company-name">{d.company_legal_name || d.company_name || "JEWEL INDIA"}</div>
          {d.company_address && <div className="pv-company-sub">{d.company_address}</div>}
          {(d.company_phone || d.company_email) && (
            <div className="pv-company-sub">
              {d.company_phone && "Ph: " + d.company_phone}
              {d.company_phone && d.company_email && "  �  "}
              {d.company_email}
            </div>
          )}
          {d.company_gstin && <div className="pv-company-gstin">GSTIN: {d.company_gstin}</div>}
        </div>
        {d.bis_logo_url && <img src={d.bis_logo_url} alt="BIS" className="pv-logo" />}
      </div>

      {/* ── Title ── */}
      <div className="pv-title-strip">
        <div className="pv-title-side">
          {d.is_rcm ? <span style={{color:"#c00",fontWeight:700}}>RCM</span> : ""}
        </div>
        <div className="pv-title-center">Purchase Voucher � Vendor</div>
        <div className="pv-title-side pv-title-right">Original / Duplicate</div>
      </div>

      {/* ── Vendor + bill info ── */}
      <table className="pv-meta-table">
        <tbody>
          <tr>
            <td style={{width:"60%"}}>
              <div className="pv-section-head">Vendor Details</div>
              <table style={{width:"100%",borderCollapse:"collapse"}}>
                <tbody>
                  <tr>
                    <td style={{width:65,paddingBottom:2}} className="pv-label">Name</td>
                    <td style={{fontWeight:600}}>{d.ldgr_name || ""}</td>
                  </tr>
                  {d.party_address ? (
                    <tr>
                      <td className="pv-label" style={{verticalAlign:"top"}}>Address</td>
                      <td>{d.party_address}</td>
                    </tr>
                  ) : null}
                  <tr>
                    <td colSpan={2} style={{paddingTop:3,fontSize:"9.5px"}}>
                      {d.party_pan   ? <><span className="pv-label">PAN:</span> {d.party_pan}&nbsp;&nbsp;&nbsp;</> : null}
                      {d.party_gstin ? <><span className="pv-label">GSTIN:</span> {d.party_gstin}&nbsp;&nbsp;&nbsp;</> : null}
                      {d.party_state ? <><span className="pv-label">State:</span> {d.party_state}</> : null}
                    </td>
                  </tr>
                </tbody>
              </table>
            </td>
            <td style={{width:"40%"}}>
              <div className="pv-section-head">Voucher Details</div>
              <table style={{width:"100%",borderCollapse:"collapse"}}>
                <tbody>
                  <tr>
                    <td style={{width:68}} className="pv-label">Bill No.</td>
                    <td style={{fontWeight:600}}>{d.billno || ""}</td>
                  </tr>
                  <tr>
                    <td className="pv-label">Date</td>
                    <td>{fmtDate(d.date1)}</td>
                  </tr>
                  {d.ref_no ? (
                    <tr>
                      <td className="pv-label">Ref No.</td>
                      <td>{d.ref_no}{d.ref_date ? " / " + fmtDate(d.ref_date) : ""}</td>
                    </tr>
                  ) : null}
                  {d.hsn ? (
                    <tr>
                      <td className="pv-label">HSN</td>
                      <td>{d.hsn}</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </td>
          </tr>
        </tbody>
      </table>

      {/* ── Items ── */}
      <div className="pv-items-wrap">
        <table className="pv-items-table">
          <colgroup>
            <col style={{width:"4%"}} /><col style={{width:"28%"}} /><col style={{width:"5%"}} />
            <col style={{width:"7%"}} /><col style={{width:"7%"}} /><col style={{width:"6%"}} />
            <col style={{width:"9%"}} /><col style={{width:"9%"}} /><col style={{width:"10%"}} />
            <col style={{width:"15%"}} />
          </colgroup>
          <thead>
            <tr>
              <th>SL</th>
              <th style={{textAlign:"left"}}>Particulars</th>
              <th>Pcs</th>
              <th>GW (g)</th>
              <th>WT / CT</th>
              <th>Tunch%</th>
              <th>Fine WT</th>
              <th>Rate (₹/g)</th>
              <th>Making (₹)</th>
              <th>Amount (₹)</th>
            </tr>
          </thead>
          <tbody>
            {directSubs.map((sub, i) => (
              <tr key={"ds-"+i} className="pv-main-row">
                <td className="pv-ctr">{i+1}</td>
                <td>{sub.sub_item||""}{sub.packet?" ["+sub.packet+"]":""}</td>
                <td className="pv-ctr">{sub.sub_pcs||""}</td>
                <td className="pv-num">{fmt3(sub.sub_gw)}</td>
                <td className="pv-num">{sub.sub_ct ? fmt3(sub.sub_ct)+" ct" : fmt3(sub.sub_gw)}</td>
                <td className="pv-num">{sub.tunch ? fmt(sub.tunch) : ""}</td>
                <td className="pv-num">{fmt3(sub.fine_wt)}</td>
                <td className="pv-num">{fmt(sub.rate)}</td>
                <td></td>
                <td className="pv-num">{fmt(sub.value)}</td>
              </tr>
            ))}
            {items.map((item, idx) => {
              const subs   = item.purchasevoucherdetails_set || [];
              const amount = parseFloat(item.item_value) || 0;
              const slNo   = directSubs.length + idx + 1;
              return (
                <React.Fragment key={idx}>
                  <tr className="pv-main-row">
                    <td className="pv-ctr">{slNo}</td>
                    <td>
                      {item.item_name || item.item || ""}
                      {item.barcode_txt ? <span style={{color:"#555",fontSize:"9px"}}>{" ["+item.barcode_txt+"]"}</span> : null}
                      {item.size       ? <span style={{color:"#555",fontSize:"9px"}}>{" � Sz "+item.size}</span> : null}
                      {item.purity     ? <span style={{color:"#555",fontSize:"9px"}}>{" � "+item.purity}</span> : null}
                    </td>
                    <td className="pv-ctr">{item.pcs ?? ""}</td>
                    <td className="pv-num">{fmt3(item.gw)}</td>
                    <td></td><td></td><td></td><td></td>
                    <td className="pv-num">{item.making_value ? fmt(item.making_value) : ""}</td>
                    <td className="pv-num">{fmt(amount)}</td>
                  </tr>
                  {subs.map((sub, si) => (
                    <tr key={"s-"+idx+"-"+si} className="pv-sub-row">
                      <td></td>
                      <td style={{paddingLeft:14}}>
                        {"↳ "}{sub.sub_item||""}
                        {sub.packet ? <span style={{fontSize:"9px",color:"#666"}}>{" ["+sub.packet+"]"}</span> : null}
                      </td>
                      <td className="pv-ctr">{sub.sub_pcs||""}</td>
                      <td className="pv-num">{fmt3(sub.sub_gw)}</td>
                      <td className="pv-num">{sub.sub_ct ? fmt3(sub.sub_ct)+" ct" : fmt3(sub.sub_gw)}</td>
                      <td className="pv-num">{sub.tunch ? fmt(sub.tunch) : ""}</td>
                      <td className="pv-num">{sub.fine_wt ? fmt3(sub.fine_wt) : ""}</td>
                      <td className="pv-num">{sub.rate ? fmt(sub.rate) : ""}</td>
                      <td></td>
                      <td className="pv-num">{sub.value ? fmt(sub.value) : ""}</td>
                    </tr>
                  ))}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ── Totals ── */}
      <table className="pv-totals-table">
        <tbody>
          {parseFloat(d.bill_value) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">Item Total</td><td className="pv-total-value">₹ {fmt(d.bill_value)}</td></tr> : null}
          {makingTotal ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">Making Charges</td><td className="pv-total-value">₹ {fmt(makingTotal)}</td></tr> : null}
          {parseFloat(d.discount_amt) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">Discount</td><td className="pv-total-value" style={{color:"#c00"}}>({fmt(Math.abs(d.discount_amt))})</td></tr> : null}
          {parseFloat(d.hallmark_charge) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">Hallmark Charges</td><td className="pv-total-value">₹ {fmt(d.hallmark_charge)}</td></tr> : null}
          {parseFloat(d.freight_amt) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">Freight / Carriage</td><td className="pv-total-value">₹ {fmt(d.freight_amt)}</td></tr> : null}
          {parseFloat(d.add_chrg_amt1) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">{d.add_chrg_cap1||"Add. Charge 1"}</td><td className="pv-total-value">₹ {fmt(d.add_chrg_amt1)}</td></tr> : null}
          {parseFloat(d.add_chrg_amt2) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">{d.add_chrg_cap2||"Add. Charge 2"}</td><td className="pv-total-value">₹ {fmt(d.add_chrg_amt2)}</td></tr> : null}
          {parseFloat(d.cgst) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">CGST @ 1.5%</td><td className="pv-total-value">₹ {fmt(d.cgst)}</td></tr> : null}
          {parseFloat(d.sgst) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">SGST @ 1.5%</td><td className="pv-total-value">₹ {fmt(d.sgst)}</td></tr> : null}
          {parseFloat(d.igst) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">IGST @ 3.0%</td><td className="pv-total-value">₹ {fmt(d.igst)}</td></tr> : null}
          {parseFloat(d.tcs_amt) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">TCS</td><td className="pv-total-value">₹ {fmt(d.tcs_amt)}</td></tr> : null}
          {parseFloat(d.tds_amt) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">{"TDS"+(d.tds_section?" ("+d.tds_section+")":"")}</td><td className="pv-total-value" style={{color:"#c00"}}>({fmt(d.tds_amt)})</td></tr> : null}
          {parseFloat(d.round_off) ? <tr><td className="pv-total-spacer"></td><td className="pv-total-label">Round Off</td><td className="pv-total-value">₹ {fmt(d.round_off)}</td></tr> : null}
          <tr className="pv-grand-row">
            <td className="pv-total-spacer"></td>
            <td className="pv-total-label">Net Payable</td>
            <td className="pv-total-value">₹ {fmt(grandTotal)}</td>
          </tr>
        </tbody>
      </table>

      {/* ── Amount in words ── */}
      <div className="pv-words-row">
        <span style={{fontWeight:700}}>Amount in Words: </span>
        {numberToWords(grandTotal)}
      </div>

      {/* ── Narration ── */}
      {d.narration ? (
        <div className="pv-narr-row">
          <span style={{fontWeight:700}}>Narration: </span>{d.narration}
        </div>
      ) : null}

      {/* ── Footer ── */}
      <div className="pv-footer">
        <div className="pv-footer-left">
          {d.company_pan   ? <div><span className="pv-label">PAN:</span> {d.company_pan}</div>   : null}
          {d.company_gstin ? <div><span className="pv-label">GSTIN:</span> {d.company_gstin}</div> : null}
          {d.company_tan   ? <div><span className="pv-label">TAN:</span> {d.company_tan}</div>   : null}
          <div style={{marginTop:2,fontSize:"9.5px",color:"#555"}}>E. &amp; O.E.</div>
        </div>
        <div className="pv-footer-right">
          <div style={{fontSize:"9.5px",fontWeight:600,marginBottom:2}}>for {d.company_legal_name || d.company_name || "JEWEL INDIA"}</div>
          <div className="pv-sig">Authorised Signatory</div>
        </div>
      </div>
    </div>
  );
};

export default PurchaseVoucherVendor;

