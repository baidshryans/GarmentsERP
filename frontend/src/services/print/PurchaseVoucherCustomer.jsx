import React from "react";

/* ────────────────────────────────────────────────────────────────────────────
   PurchaseVoucherCustomer
   ------------------------------------------------------------------
   A5-landscape, monochrome receipt format for purchases booked AGAINST a
   customer (old-gold / buyback vouchers). Designed to print on half-A4
   sheets with comfortable spacing.

   Layout (top → bottom):
     • Copy indicator     ─ ORIGINAL / DUPLICATE, plain caps, top-right
     • Header             ─ BIS placeholder · centered company block · logo
     • Title              ─ PURCHASE VOUCHER (CUSTOMER), centered
     • Meta cards         ─ Voucher No · Voucher Date · Place of Supply
     • Customer card      ─ name · address · Phone/PAN/GSTIN/State row
     • Items table        ─ SL · Particulars · Pcs · Ct · Wt · Fine Wt
                            · Rate · Value · Amount
     • Totals (in-table)  ─ Subtotal · Round Off · Total Payable
     • Narration / In Words (single lines, conditional)
     • Sign-off           ─ Issued-by GST grid · Authorised Signatory
     • Footer             ─ centered "computer-generated" line

   Data prop (merged row + companyInfo from PurchaseVoucherList):
     d.billno, d.date1, d.narration, d.bill_value, d.round_off,
     d.total_incl_gst, d.ldgr_name, d.party_address, d.party_phone,
     d.party_pan, d.party_gstin, d.party_state, d.vendor_state_code,
     d.purchasevoucheritems_set[], d.purchasevoucherdetails_set[],
     d.company_name, d.company_address, d.company_phone, d.company_email,
     d.company_cin, d.company_pan, d.company_gstin, d.company_logo_url,
     d.bis_logo_url
   ──────────────────────────────────────────────────────────────────────────── */

/* ─── Helpers ─────────────────────────────────────────────────────────── */

const fmt = (n, dec = 2) => {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num)) return "";
  return num.toLocaleString("en-IN", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
};
const fmt3 = (n) => fmt(n, 3);

const fmtDate = (s) => {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d)) return s;
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${String(d.getDate()).padStart(2, "0")} ${months[d.getMonth()]} ${d.getFullYear()}`;
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
    else {
      if (Math.floor(rem / 10)) r += tens[Math.floor(rem / 10)] + (rem % 10 ? " " : "");
      if (rem % 10) r += units[rem % 10];
    }
    return r;
  };
  const whole = Math.floor(Math.abs(num));
  if (whole === 0) return "Rupees Zero Only";
  const crore = Math.floor(whole / 10000000);
  const lakh  = Math.floor((whole % 10000000) / 100000);
  const thou  = Math.floor((whole % 100000) / 1000);
  const rest  = whole % 1000;
  let res = "";
  if (crore) res += group(crore) + " Crore ";
  if (lakh)  res += group(lakh)  + " Lakh ";
  if (thou)  res += group(thou)  + " Thousand ";
  if (rest)  res += group(rest);
  return "Rupees " + res.trim() + " Only";
}

/* ─── Stylesheet (scoped via .pvc- prefix) ────────────────────────────── */

const PVC_CSS = `
*,*::before,*::after { box-sizing: border-box; margin: 0; padding: 0; }
body { background: #fff; }

.pvc-page {
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 9px;
  line-height: 1.4;
  color: #000;
  width: 210mm;
  min-height: 148mm;
  margin: 0 auto;
  padding: 5mm 7mm;
  background: #fff;
  position: relative;
  break-after: page;
  page-break-after: always;
  -webkit-font-smoothing: antialiased;
}
.pvc-page:last-of-type { break-after: auto; page-break-after: auto; }
.pvc-page::before {
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: #000;
}

/* Copy indicator */
.pvc-copy-line {
  display: flex; justify-content: flex-end; align-items: center;
  margin-bottom: 2px;
}
.pvc-copy-tag {
  color: #000; font-size: 8px; font-weight: 700;
  letter-spacing: 1.6px; text-transform: uppercase;
}

/* Header */
.pvc-header {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  align-items: center;
  margin-bottom: 5px;
}
.pvc-header .left  { justify-self: start; }
.pvc-header .right { justify-self: end; }
.pvc-logo-slot {
  width: 40px; height: 40px;
  border: 1px dashed #9a9a9a; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  color: #6e6e6e;
  font-size: 6.5px; font-weight: 600; letter-spacing: 1px;
  text-align: center; line-height: 1.1;
}
.pvc-logo-slot.square { border-radius: 4px; width: 60px; height: 38px; }
.pvc-logo-img        { max-height: 44px; max-width: 80px; object-fit: contain; }
.pvc-logo-img.square { max-height: 38px; max-width: 90px; }

.pvc-brand   { text-align: center; }
.pvc-h-name  { font-size: 14px; font-weight: 800; letter-spacing: 0.4px; line-height: 1.1; }
.pvc-h-meta  { color: #2b2b2b; font-size: 8.5px; margin-top: 2px; line-height: 1.35; }
.pvc-h-meta div + div { margin-top: 0; }

/* Title */
.pvc-title {
  text-align: center;
  padding: 0 0 3px;
  margin-bottom: 6px;
}
.pvc-title-text {
  font-size: 11px; font-weight: 700; color: #000;
  letter-spacing: 2.5px; text-transform: uppercase;
}

/* Meta cards (Voucher No · Date · Place of Supply) */
.pvc-meta-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  column-gap: 6px;
  margin-bottom: 6px;
}
.pvc-meta-card {
  border: 1px solid #d0d0d0; border-radius: 3px;
  padding: 4px 8px; background: #fff;
}
.pvc-label {
  text-transform: uppercase; letter-spacing: 1.4px;
  font-size: 7px; font-weight: 600; color: #6e6e6e;
}
.pvc-meta-card .pvc-label { margin-bottom: 1px; }
.pvc-meta-card .pvc-value {
  font-size: 9.5px; font-weight: 700; color: #000;
  font-variant-numeric: tabular-nums;
}

/* Customer / vendor card */
.pvc-vendor-card {
  background: #f6f6f6;
  padding: 6px 10px;
  border-left: 3px solid #000;
  border-radius: 2px;
  margin-bottom: 6px;
  font-size: 9px;
}
.pvc-vendor-card .pvc-name {
  font-size: 10.5px; font-weight: 700; color: #000;
  margin-bottom: 2px;
}
.pvc-vendor-card .pvc-addr { color: #2b2b2b; font-size: 9px; margin-bottom: 3px; line-height: 1.4; }
.pvc-vendor-card .pvc-ids-row {
  display: flex; flex-wrap: wrap;
  column-gap: 14px; row-gap: 2px;
  padding-top: 3px; border-top: 1px dashed #d0d0d0;
}
.pvc-kv { display: inline-flex; align-items: baseline; gap: 6px; }
.pvc-kv .k {
  color: #6e6e6e; text-transform: uppercase; letter-spacing: 1px;
  font-size: 7.2px; font-weight: 600;
}
.pvc-kv .v { color: #000; font-weight: 600; font-size: 9px; }
.pvc-kv .v.muted { color: #2b2b2b; font-weight: 500; }

/* Items table */
.pvc-items { width: 100%; border-collapse: collapse; margin-top: 2px; }
.pvc-items thead th {
  text-transform: uppercase; letter-spacing: 1.2px;
  font-size: 7.5px; font-weight: 700; color: #000;
  text-align: right; padding: 4px 5px;
  border-bottom: 1.5px solid #000;
  background: #fff;
}
.pvc-items thead th.t-left   { text-align: left; }
.pvc-items thead th.t-center { text-align: center; }
.pvc-items tbody td {
  padding: 5px 5px;
  border-bottom: 1px solid #d0d0d0;
  font-size: 8.5px;
  color: #000;
  vertical-align: top;
}
.pvc-items tbody td.t-num    { text-align: right; font-variant-numeric: tabular-nums; }
.pvc-items tbody td.t-center { text-align: center; }
.pvc-items tbody td.sl       { color: #000; font-weight: 700; }
.pvc-item-name { font-weight: 700; }
.pvc-item-sub  { color: #2b2b2b; font-size: 7.5px; margin-top: 1px; }
.pvc-items tbody tr.filler td { border-bottom: 1px dotted #d0d0d0; padding: 3px 5px; }

/* Sub-rows under a parent item */
.pvc-items tbody tr.subrow td { color: #2b2b2b; font-size: 8.2px; }
.pvc-items tbody tr.subrow td.particulars { padding-left: 14px; }

/* Integrated totals (rows of the items table) */
.pvc-items tr.tot td {
  border-bottom: none;
  padding: 4px 5px;
  font-size: 9px;
  color: #000;
}
.pvc-items tr.tot td.tot-label {
  text-align: right; padding-right: 10px;
  font-weight: 500; color: #2b2b2b;
  white-space: nowrap;
}
.pvc-items tr.tot td.tot-value {
  text-align: right; font-variant-numeric: tabular-nums;
  font-weight: 600; white-space: nowrap;
}
.pvc-items tr.tot.first td  { border-top: 1px solid #9a9a9a; padding-top: 5px; }
.pvc-items tr.tot.subtotal td.tot-label { color: #000; font-weight: 600; }
.pvc-items tr.tot.subtotal td.tot-value { font-weight: 700; }
.pvc-items tr.tot.grand td {
  border-top: 1px solid #9a9a9a;
  padding-top: 5px; padding-bottom: 5px;
  font-size: 10.5px; font-weight: 700; color: #000;
}

/* Narration / In Words */
.pvc-meta-line {
  margin-top: 6px; font-size: 9px; color: #000;
}
.pvc-meta-line + .pvc-meta-line { margin-top: 3px; }
.pvc-meta-line .pvc-label-inline {
  display: inline-block; margin-right: 8px;
  text-transform: uppercase; letter-spacing: 1.4px;
  font-size: 7.5px; font-weight: 600; color: #6e6e6e;
}
.pvc-meta-line .strong { font-weight: 700; color: #000; }

/* Sign-off */
.pvc-signoff {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 14px; margin-top: 8px;
  padding-top: 6px; border-top: 1px solid #000;
}
.pvc-gst-grid {
  display: grid; grid-template-columns: auto 1fr;
  column-gap: 10px; row-gap: 2px; font-size: 8.5px;
}
.pvc-gst-grid .k {
  color: #6e6e6e; text-transform: uppercase; letter-spacing: 1.3px;
  font-size: 7.2px; font-weight: 600; align-self: center;
}
.pvc-gst-grid .v { color: #000; font-weight: 600; }

.pvc-sign      { text-align: right; }
.pvc-sign .for { font-size: 9px; color: #2b2b2b; }
.pvc-sign .for .strong { color: #000; font-weight: 700; }
.pvc-sig-box {
  display: inline-block; margin-top: 18px;
  padding: 4px 18px 0;
  border-top: 1.5px solid #000;
  font-size: 8px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 1.6px; color: #000;
}

/* Footer */
.pvc-footer {
  margin-top: 8px; text-align: center;
  padding-top: 5px; border-top: 1px solid #d0d0d0;
  font-size: 7px; color: #6e6e6e;
  text-transform: uppercase; letter-spacing: 1.2px;
}

@media print {
  @page { size: A5 landscape; margin: 0; }
  body  { margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .pvc-page { padding: 5mm 7mm; }
}
`;

/* ─── Component ───────────────────────────────────────────────────────── */

const PurchaseVoucherCustomer = ({ data = {} }) => {
  const d = data;

  /* item rows ------------------------------------------------------- */
  const items      = d.purchasevoucheritems_set || [];
  const directSubs = (d.purchasevoucherdetails_set || []).filter((x) => !x.main_item);

  /* totals ---------------------------------------------------------- */
  const subtotal   = parseFloat(d.bill_value) || parseFloat(d.item_total) || 0;
  const roundOff   = parseFloat(d.round_off) || 0;
  const grandTotal = parseFloat(d.total_incl_gst) || (subtotal + roundOff);

  /* place of supply (state · code) --------------------------------- */
  const placeOfSupply = (() => {
    const state = d.party_state || "";
    const code = d.vendor_state_code || "";
    if (state && code) return `${state} · ${code}`;
    return state || code || "";
  })();

  return (
    <div className="pvc-page">
      <style>{PVC_CSS}</style>

      {/* Copy indicator */}
      <div className="pvc-copy-line">
        <span className="pvc-copy-tag">Original / Duplicate</span>
      </div>

      {/* Header — BIS · Company (centered) · Brand logo */}
      <div className="pvc-header">
        <div className="left">
          {d.bis_logo_url
            ? <img src={d.bis_logo_url} alt="BIS Hallmark" className="pvc-logo-img" />
            : <div className="pvc-logo-slot">BIS<br/>HALLMARK</div>}
        </div>
        <div className="pvc-brand">
          <div className="pvc-h-name">{d.company_name || "JEWEL INDIA"}</div>
          <div className="pvc-h-meta">
            {d.company_address && <div>{d.company_address}</div>}
            {(d.company_phone || d.company_email) && (
              <div>
                {d.company_phone && <>Phone : {d.company_phone}</>}
                {d.company_phone && d.company_email && <>&nbsp;&nbsp;·&nbsp;&nbsp;</>}
                {d.company_email && <>Email : {d.company_email}</>}
              </div>
            )}
            {d.company_cin && <div>CIN : {d.company_cin}</div>}
          </div>
        </div>
        <div className="right">
          {d.company_logo_url
            ? <img src={d.company_logo_url} alt="logo" className="pvc-logo-img square" />
            : <div className="pvc-logo-slot square">COMPANY<br/>LOGO</div>}
        </div>
      </div>

      {/* Title */}
      <div className="pvc-title">
        <span className="pvc-title-text">Purchase Voucher (Customer)</span>
      </div>

      {/* Meta cards */}
      <div className="pvc-meta-strip">
        <div className="pvc-meta-card">
          <div className="pvc-label">Voucher No.</div>
          <div className="pvc-value">{d.billno || ""}</div>
        </div>
        <div className="pvc-meta-card">
          <div className="pvc-label">Voucher Date</div>
          <div className="pvc-value">{fmtDate(d.date1)}</div>
        </div>
        <div className="pvc-meta-card">
          <div className="pvc-label">Place of Supply</div>
          <div className="pvc-value">{placeOfSupply || "—"}</div>
        </div>
      </div>

      {/* Customer card */}
      <div className="pvc-vendor-card">
        <div className="pvc-name">{d.ldgr_name || ""}</div>
        {d.party_address && <div className="pvc-addr">{d.party_address}</div>}
        <div className="pvc-ids-row">
          {d.party_phone && (
            <span className="pvc-kv"><span className="k">Phone</span><span className="v">{d.party_phone}</span></span>
          )}
          {d.party_pan && (
            <span className="pvc-kv"><span className="k">PAN</span><span className="v">{d.party_pan}</span></span>
          )}
          <span className="pvc-kv">
            <span className="k">GSTIN</span>
            <span className={"v" + (d.party_gstin ? "" : " muted")}>
              {d.party_gstin || "Unregistered"}
            </span>
          </span>
          {placeOfSupply && (
            <span className="pvc-kv"><span className="k">State</span><span className="v">{placeOfSupply}</span></span>
          )}
        </div>
      </div>

      {/* Items table */}
      <table className="pvc-items">
        <colgroup>
          <col style={{ width: "5%"  }} />
          <col style={{ width: "31%" }} />
          <col style={{ width: "6%"  }} />
          <col style={{ width: "7%"  }} />
          <col style={{ width: "9%"  }} />
          <col style={{ width: "9%"  }} />
          <col style={{ width: "10%" }} />
          <col style={{ width: "11%" }} />
          <col style={{ width: "12%" }} />
        </colgroup>
        <thead>
          <tr>
            <th className="t-center">SL</th>
            <th className="t-left">Particulars</th>
            <th>Pcs</th>
            <th>Ct</th>
            <th>Wt</th>
            <th>Fine Wt</th>
            <th>Rate</th>
            <th>Value</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {/* Direct sub-items (no parent) — each is its own SL row */}
          {directSubs.map((sub, i) => (
            <tr key={"d-" + i}>
              <td className="sl t-center">{String(i + 1).padStart(2, "0")}</td>
              <td>
                <div className="pvc-item-name">{sub.sub_item || ""}</div>
                {(sub.metal_purity || sub.packet) && (
                  <div className="pvc-item-sub">
                    {sub.metal_purity && <>Purity: {sub.metal_purity}</>}
                    {sub.metal_purity && sub.packet && <> · </>}
                    {sub.packet && <>{sub.packet}</>}
                  </div>
                )}
              </td>
              <td className="t-center">{sub.sub_pcs || "—"}</td>
              <td className="t-num">{sub.sub_ct ? fmt3(sub.sub_ct) : "—"}</td>
              <td className="t-num strong">{sub.sub_gw ? fmt3(sub.sub_gw) : "—"}</td>
              <td className="t-num">{sub.fine_wt ? fmt3(sub.fine_wt) : "—"}</td>
              <td className="t-num">{sub.rate ? fmt(sub.rate) : "—"}</td>
              <td className="t-num">{sub.value ? fmt(sub.value) : "—"}</td>
              <td className="t-num strong">{sub.value ? fmt(sub.value) : "—"}</td>
            </tr>
          ))}

          {/* Items with their own sub-rows */}
          {items.map((item, idx) => {
            const subs   = item.purchasevoucherdetails_set || [];
            const slNo   = String(directSubs.length + idx + 1).padStart(2, "0");
            const amount = parseFloat(item.item_value) || 0;
            return (
              <React.Fragment key={"i-" + idx}>
                <tr>
                  <td className="sl t-center">{slNo}</td>
                  <td>
                    <div className="pvc-item-name">{item.item_name || item.item || ""}</div>
                    {(item.purity || item.barcode_txt || item.size) && (
                      <div className="pvc-item-sub">
                        {item.purity && <>Purity: {item.purity}</>}
                        {item.purity && item.barcode_txt && <> · </>}
                        {item.barcode_txt && <>{item.barcode_txt}</>}
                        {(item.purity || item.barcode_txt) && item.size && <> · </>}
                        {item.size && <>Size {item.size}</>}
                      </div>
                    )}
                  </td>
                  <td className="t-center">{item.pcs ?? "—"}</td>
                  <td className="t-num">—</td>
                  <td className="t-num strong">{item.gw ? fmt3(item.gw) : "—"}</td>
                  <td className="t-num">—</td>
                  <td className="t-num">—</td>
                  <td className="t-num">—</td>
                  <td className="t-num strong">{amount ? fmt(amount) : "—"}</td>
                </tr>
                {subs.map((sub, si) => (
                  <tr key={"i-" + idx + "-s-" + si} className="subrow">
                    <td></td>
                    <td className="particulars">↳ {sub.sub_item || ""}</td>
                    <td className="t-center">{sub.sub_pcs || ""}</td>
                    <td className="t-num">{sub.sub_ct ? fmt3(sub.sub_ct) : ""}</td>
                    <td className="t-num">{sub.sub_gw ? fmt3(sub.sub_gw) : ""}</td>
                    <td className="t-num">{sub.fine_wt ? fmt3(sub.fine_wt) : ""}</td>
                    <td className="t-num">{sub.rate ? fmt(sub.rate) : ""}</td>
                    <td className="t-num">{sub.value ? fmt(sub.value) : ""}</td>
                    <td className="t-num">{sub.value ? fmt(sub.value) : ""}</td>
                  </tr>
                ))}
              </React.Fragment>
            );
          })}

          {/* Filler rows when bill is short, for visual balance */}
          {(directSubs.length + items.length) > 0 &&
           (directSubs.length + items.length) < 3 &&
           Array.from({ length: 3 - (directSubs.length + items.length) }).map((_, i) => (
            <tr key={"f-" + i} className="filler">
              <td colSpan={9}>&nbsp;</td>
            </tr>
          ))}

          {/* Totals — integrated as bottom rows */}
          <tr className="tot subtotal first">
            <td colSpan={7}></td>
            <td className="tot-label">Subtotal</td>
            <td className="tot-value">{fmt(subtotal)}</td>
          </tr>
          {roundOff !== 0 && (
            <tr className="tot">
              <td colSpan={7}></td>
              <td className="tot-label">Round Off</td>
              <td className="tot-value">{fmt(roundOff)}</td>
            </tr>
          )}
          <tr className="tot grand">
            <td colSpan={7}></td>
            <td className="tot-label">Total Payable</td>
            <td className="tot-value">{fmt(grandTotal)}</td>
          </tr>
        </tbody>
      </table>

      {/* Narration (rendered only when not blank) */}
      {d.narration && (
        <div className="pvc-meta-line">
          <span className="pvc-label-inline">Narration</span>
          <span>{d.narration}</span>
        </div>
      )}

      {/* In Words */}
      <div className="pvc-meta-line">
        <span className="pvc-label-inline">In Words</span>
        <span className="strong">{numberToWords(grandTotal)}</span>
      </div>

      {/* Sign-off */}
      <div className="pvc-signoff">
        <div>
          <div className="pvc-label" style={{ marginBottom: 4 }}>Issued By</div>
          <div className="pvc-gst-grid">
            {d.company_pan && (<>
              <div className="k">Pan</div>   <div className="v">{d.company_pan}</div>
            </>)}
            {d.company_gstin && (<>
              <div className="k">Gstin</div> <div className="v">{d.company_gstin}</div>
            </>)}
            {(d.company_state || d.company_state_code) && (<>
              <div className="k">State</div>
              <div className="v">
                {d.company_state || ""}
                {d.company_state && d.company_state_code && " · "}
                {d.company_state_code || ""}
              </div>
            </>)}
          </div>
        </div>
        <div className="pvc-sign">
          <div className="for">for <span className="strong">{d.company_name || "JEWEL INDIA"}</span></div>
          <div className="pvc-sig-box">Authorised Signatory</div>
        </div>
      </div>

      {/* Footer */}
      <div className="pvc-footer">
        Computer-generated voucher · No physical signature required
      </div>
    </div>
  );
};

export default PurchaseVoucherCustomer;
