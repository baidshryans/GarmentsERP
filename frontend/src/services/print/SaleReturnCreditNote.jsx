import React from "react";
import { fmt, fmtDate, numberToWords } from "./printHelpers";

// â”€â”€ CSS (self-contained â€” injected into the print popup) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const CN_CSS = `
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap");

:root {
  --ink:  #0f172a;
  --body: #1e293b;
  --muted:#64748b;
  --faint:#94a3b8;
  --rule: #e2e8f0;
  --band: #f8fafc;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

.cn-root {
  width: 210mm;
  min-height: 297mm;
  margin: 0 auto;
  background: #fff;
  padding: 12mm 13mm 10mm;
  font-family: "Inter", "Helvetica Neue", Arial, sans-serif;
  font-size: 9px;
  color: var(--body);
  font-feature-settings: "tnum" 1, "lnum" 1;
  -webkit-font-smoothing: antialiased;
}

/* â”€â”€ Header â”€â”€ */
.cn-header {
  display: grid;
  grid-template-columns: 72px 1fr 80px;
  align-items: center;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--ink);
}
.cn-logo-box {
  width: 60px; height: 60px;
  border: 1px dashed var(--faint); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 7px; color: var(--muted); text-align: center; line-height: 1.3;
}
.cn-logo-rect {
  width: 80px; height: 56px;
  border: 1px dashed var(--faint); border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  font-size: 7px; color: var(--muted); text-align: center; line-height: 1.3;
  justify-self: end;
}
.cn-brand-block { display: flex; flex-direction: column; align-items: center; gap: 3px; }
.cn-brand {
  font-family: "Fraunces", Georgia, serif;
  font-size: 28px; font-weight: 700; color: var(--ink);
  letter-spacing: -0.5px; line-height: 1;
}
.cn-brand-sub { font-size: 8.5px; color: var(--muted); letter-spacing: 0.2px; text-align: center; }
.cn-brand-sub strong, .cn-brand-sub b { color: var(--ink); font-weight: 600; }
.cn-dot { color: var(--faint); margin: 0 4px; }
.cn-brand-ids { display: flex; gap: 18px; font-size: 8.5px; color: var(--muted); margin-top: 2px; justify-content: center; }
.cn-brand-ids span b { color: var(--ink); font-weight: 600; margin-left: 3px; font-variant-numeric: tabular-nums; }

/* â”€â”€ Invoice head â”€â”€ */
.cn-invoice-head {
  text-align: center;
  padding: 9px 0 8px;
  border-bottom: 1px solid var(--rule);
}
.cn-invoice-head .cn-title {
  font-size: 11px; letter-spacing: 4px; text-transform: uppercase;
  color: var(--ink); font-weight: 700;
}
.cn-invoice-head .cn-subtitle {
  font-size: 8px; color: var(--muted); letter-spacing: 0.3px; margin-top: 1px;
}

/* â”€â”€ Party section â”€â”€ */
.cn-parties {
  display: grid; grid-template-columns: 1fr 1fr;
  border: 1px solid var(--rule); border-radius: 4px;
  margin: 8px 0;
}
.cn-party { padding: 10px 12px; }
.cn-party + .cn-party { border-left: 1px solid var(--rule); }
.cn-pe {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 6px;
  font-size: 7px; letter-spacing: 1.8px; text-transform: uppercase;
  color: var(--muted); font-weight: 700;
}
.cn-pe::after { content: ""; flex: 1; height: 1px; background: var(--rule); }
.cn-party .cn-name { font-size: 13px; font-weight: 700; color: var(--ink); letter-spacing: -0.1px; }
.cn-party .cn-addr { font-size: 9px; color: var(--body); margin-top: 4px; line-height: 1.55; }
.cn-party .cn-ids {
  display: flex; flex-direction: column; gap: 3px;
  margin-top: 8px; padding-top: 6px;
  border-top: 1px dashed var(--rule);
}
.cn-id { display: flex; flex-direction: column; }
.cn-id .cn-k {
  font-size: 7px; letter-spacing: 1.4px; text-transform: uppercase;
  color: var(--muted); font-weight: 700;
}
.cn-id .cn-v {
  font-size: 9px; color: var(--ink); font-weight: 600;
  font-variant-numeric: tabular-nums; margin-top: 1px;
}
.cn-id .cn-v.empty { color: var(--faint); font-weight: 400; }
.cn-reason-pill {
  display: inline-flex; align-items: center;
  background: var(--band); border: 1px solid var(--rule); border-radius: 20px;
  padding: 2px 8px; font-size: 7.5px; color: var(--body); font-weight: 600;
}

/* â”€â”€ Items table â”€â”€ */
table.cn-items {
  width: 100%; border-collapse: collapse;
  font-size: 8.5px; font-variant-numeric: tabular-nums;
  margin-bottom: 8px;
}
table.cn-items thead th {
  font-size: 7px; letter-spacing: 1.2px; text-transform: uppercase;
  color: var(--muted); font-weight: 700;
  border-bottom: 1px solid var(--ink);
  padding: 5px 5px 4px;
}
table.cn-items thead th.l { text-align: left; }
table.cn-items thead th.c { text-align: center; }
table.cn-items thead th.r { text-align: right; }
table.cn-items tbody td {
  padding: 5px 5px;
  border-bottom: 1px solid var(--rule);
  font-variant-numeric: tabular-nums;
}
table.cn-items tbody td.l { text-align: left; }
table.cn-items tbody td.c { text-align: center; }
table.cn-items tbody td.r { text-align: right; }
table.cn-items tbody tr.parent td { font-weight: 600; color: var(--ink); padding: 6px 5px; }
table.cn-items tbody tr.parent td.sn { font-weight: 700; }
table.cn-items tbody tr.sub td {
  color: var(--muted); border-bottom: 1px dashed var(--rule);
  font-size: 8px; background: #fcfcfd; font-style: italic;
}
table.cn-items tbody tr.sub td.l { padding-left: 14px; }

/* â”€â”€ Bottom layout â”€â”€ */
.cn-bottom {
  display: grid; grid-template-columns: 1.4fr 1fr;
  gap: 12px; margin-top: 6px;
}
.cn-words {
  font-size: 8.5px; color: var(--muted); font-style: italic;
  border-top: 1px dashed var(--rule); padding-top: 6px;
}
.cn-words b { color: var(--ink); font-style: normal; font-weight: 600; }
.cn-declaration {
  margin-top: 10px; padding-top: 8px;
  border-top: 1px dashed var(--rule);
  font-size: 7.5px; color: var(--muted); line-height: 1.65;
}
.cn-declaration b { color: var(--ink); }

/* â”€â”€ Totals â”€â”€ */
.cn-totals { font-size: 9.5px; }
.cn-row { display: flex; justify-content: space-between; padding: 5px 0; color: var(--body); }
.cn-row .cn-l {
  font-size: 8px; letter-spacing: 1.2px; text-transform: uppercase;
  color: var(--muted); font-weight: 600;
}
.cn-row .cn-v { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--ink); }
.cn-row.bold { border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.cn-row.bold .cn-l { color: var(--ink); font-weight: 700; }
.cn-row.bold .cn-v { font-weight: 700; }
.cn-row.minus .cn-l::before { content: "âˆ’ "; }
.cn-row.net { margin-top: 4px; border-top: 2px solid var(--ink); padding: 8px 0; }
.cn-row.net .cn-l { color: var(--ink); font-weight: 700; font-size: 9px; }
.cn-row.net .cn-v { font-weight: 700; }

/* â”€â”€ Footer â”€â”€ */
.cn-footer {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 16px; border-top: 1px solid var(--rule);
  margin-top: 14px; padding-top: 8px;
}
.cn-terms { font-size: 8px; color: var(--muted); line-height: 1.6; }
.cn-terms b { color: var(--ink); font-weight: 600; }
.cn-terms div + div { margin-top: 2px; }
.cn-stamp { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.cn-stamp .cn-sig-label {
  font-size: 7.5px; letter-spacing: 1px; text-transform: uppercase;
  color: var(--muted); font-weight: 600;
}
.cn-stamp .cn-sig-space {
  width: 160px; height: 52px;
}
.cn-stamp .cn-sig-line {
  width: 160px; border-bottom: 1px solid var(--ink); margin-bottom: 5px;
}
.cn-stamp .cn-sig-name {
  font-size: 7.5px; letter-spacing: 1.6px; text-transform: uppercase;
  color: var(--ink); font-weight: 700;
}
.cn-stamp .cn-sig-sub {
  font-size: 7.5px; color: var(--faint); letter-spacing: 0.4px; font-style: italic;
}

@media print {
  html, body { background: #fff; margin: 0; padding: 0; }
  .cn-root { box-shadow: none; }
}
`;

// â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function fmtAmt(n) { return fmt(n); }
function fmt3(n) {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num) || num === 0) return "";
  return num.toLocaleString("en-IN", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

export default function SaleReturnCreditNote({ data: d }) {
  if (!d) return null;

  const hasCgst = Number(d.cgst_per || 0) > 0;
  const hasSgst = Number(d.sgst_per || 0) > 0;
  const hasIgst = Number(d.igst_per || 0) > 0;
  const hasDiscount = Number(d.discount || 0) > 0;

  return (
    <>
      <style>{CN_CSS}</style>
      <div className="cn-root">

        {/* â”€â”€ HEADER â”€â”€ */}
        <div className="cn-header">
          <div className="cn-logo-box">BIS<br />Hallmark</div>

          <div className="cn-brand-block">
            <div className="cn-brand">{d.company_name || ""}</div>
            {d.company_legal_name && (
              <div className="cn-brand-sub"><strong>{d.company_legal_name}</strong></div>
            )}
            {d.company_address && (
              <div className="cn-brand-sub">{d.company_address}</div>
            )}
            {(d.company_phone || d.company_email) && (
              <div className="cn-brand-sub">
                {[
                  d.company_phone && <span key="ph">Phone <b>{d.company_phone}</b></span>,
                  d.company_email && <span key="em">Email <b>{d.company_email}</b></span>,
                ].filter(Boolean).reduce((acc, el, i) => i === 0 ? [el] : [...acc, <span key={`s${i}`} className="cn-dot"> Â· </span>, el], [])}
              </div>
            )}
            <div className="cn-brand-ids">
              {d.company_gstin && <span>GSTIN <b>{d.company_gstin}</b></span>}
              {d.company_pan   && <span>PAN <b>{d.company_pan}</b></span>}
              {d.company_cin   && <span>CIN <b>{d.company_cin}</b></span>}
            </div>
          </div>

          <div className="cn-logo-rect">Company<br />Logo</div>
        </div>

        {/* â”€â”€ INVOICE HEAD â”€â”€ */}
        <div className="cn-invoice-head">
          <div className="cn-title">Credit Note</div>
          <div className="cn-subtitle">GST Credit Note &nbsp;/&nbsp; Sales Return</div>
        </div>

        {/* â”€â”€ PARTY SECTION â”€â”€ */}
        <div className="cn-parties">
          {/* Customer */}
          <div className="cn-party">
            <div className="cn-pe">Customer Details</div>
            <div className="cn-name">{d.party_name}</div>
            {d.party_address && <div className="cn-addr">{d.party_address}</div>}
            <div className="cn-ids">
              {d.party_gstin && (
                <div className="cn-id">
                  <span className="cn-k">GSTIN</span>
                  <span className="cn-v">{d.party_gstin}</span>
                </div>
              )}
              {d.party_state && (
                <div className="cn-id">
                  <span className="cn-k">State</span>
                  <span className="cn-v">{d.party_state}</span>
                </div>
              )}
              {d.party_mobile && (
                <div className="cn-id">
                  <span className="cn-k">Mobile</span>
                  <span className="cn-v">{d.party_mobile}</span>
                </div>
              )}
            </div>
          </div>

          {/* Credit Note Details */}
          <div className="cn-party">
            <div className="cn-pe">Credit Note Details</div>
            <div className="cn-ids" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>
              <div className="cn-id">
                <span className="cn-k">Credit Note No.</span>
                <span className="cn-v">{d.note_no}</span>
              </div>
              <div className="cn-id">
                <span className="cn-k">Date</span>
                <span className="cn-v">{fmtDate ? fmtDate(d.date) : d.date}</span>
              </div>
              {d.ref_invoice_no && (
                <div className="cn-id">
                  <span className="cn-k">Against Invoice</span>
                  <span className="cn-v">{d.ref_invoice_no}</span>
                </div>
              )}
              {d.ref_invoice_date && (
                <div className="cn-id">
                  <span className="cn-k">Invoice Date</span>
                  <span className="cn-v">{fmtDate ? fmtDate(d.ref_invoice_date) : d.ref_invoice_date}</span>
                </div>
              )}
              {d.reason && (
                <div className="cn-id">
                  <span className="cn-k">Reason</span>
                  <span className="cn-v"><span className="cn-reason-pill">{d.reason}</span></span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* â”€â”€ ITEMS TABLE â”€â”€ */}
        <table className="cn-items">
          <thead>
            <tr>
              <th className="c" style={{ width: "24px" }}>S.No</th>
              <th className="c" style={{ width: "24px" }}>Pcs</th>
              <th className="l">Item Description</th>
              <th className="c" style={{ width: "48px" }}>Purity</th>
              <th className="r" style={{ width: "48px" }}>Weight</th>
              <th className="r" style={{ width: "50px" }}>Rate (â‚¹)</th>
              <th className="r" style={{ width: "52px" }}>Making</th>
              <th className="r" style={{ width: "62px" }}>Amount</th>
            </tr>
          </thead>
          <tbody>
            {(d.items || []).map((item, idx) => (
              <React.Fragment key={idx}>
                <tr className="parent">
                  <td className="c">{idx + 1}</td>
                  <td className="c">{item.pcs || 1}</td>
                  <td className="l">{item.item_name}</td>
                  <td className="c">
                    {item.purity || <span style={{ color: "var(--faint)" }}>â€”</span>}
                  </td>
                  <td className="r">{fmt3(item.gw)}&nbsp;g</td>
                  <td className="r"><span style={{ color: "var(--faint)" }}>â€”</span></td>
                  <td className="r">{fmtAmt(item.making)}</td>
                  <td className="r">{fmtAmt(item.amount)}</td>
                </tr>
                {(item.sub_rows || []).map((sub, si) => {
                  const wt = sub.uom === 'Ct'
                    ? `${fmt3(sub.ct)} ct`
                    : sub.uom === 'Pcs'
                      ? `${sub.pcs} pcs`
                      : `${fmt3(sub.gw)} g`;
                  return (
                    <tr key={si} className="sub">
                      <td></td>
                      <td></td>
                      <td className="l">{sub.text}</td>
                      <td className="c">{sub.metal_purity || "â€”"}</td>
                      <td className="r">{wt}</td>
                      <td className="r">{fmtAmt(sub.rate)}</td>
                      <td className="r">â€”</td>
                      <td className="r">{fmtAmt(sub.amount)}</td>
                    </tr>
                  );
                })}
              </React.Fragment>
            ))}
          </tbody>
        </table>

        {/* â”€â”€ BOTTOM â”€â”€ */}
        <div className="cn-bottom">

          {/* Left: words + declaration */}
          <div>
            <div className="cn-words">
              <b>Credit Amount in Words:</b><br />
              {numberToWords ? numberToWords(d.amount) : ""}
            </div>
            <div className="cn-declaration">
              <b>Declaration:</b> We hereby declare that this credit note shows the
              actual credit amount and that all particulars are true and correct to
              the best of our knowledge and belief.
            </div>
          </div>

          {/* Right: totals */}
          <div className="cn-totals">
            {Number(d.mrp || 0) > 0 && (
              <div className="cn-row">
                <span className="cn-l">MRP (Gross)</span>
                <span className="cn-v">{fmtAmt(d.mrp)}</span>
              </div>
            )}
            {hasDiscount && (
              <div className="cn-row minus">
                <span className="cn-l">Discount</span>
                <span className="cn-v">{fmtAmt(d.discount)}</span>
              </div>
            )}
            <div className="cn-row bold">
              <span className="cn-l">Taxable Value</span>
              <span className="cn-v">{fmtAmt(d.taxable_value)}</span>
            </div>
            {hasCgst && (
              <div className="cn-row">
                <span className="cn-l">CGST @ {d.cgst_per}%</span>
                <span className="cn-v">{fmtAmt(d.cgst_amt)}</span>
              </div>
            )}
            {hasSgst && (
              <div className="cn-row">
                <span className="cn-l">SGST @ {d.sgst_per}%</span>
                <span className="cn-v">{fmtAmt(d.sgst_amt)}</span>
              </div>
            )}
            {hasIgst && (
              <div className="cn-row">
                <span className="cn-l">IGST @ {d.igst_per}%</span>
                <span className="cn-v">{fmtAmt(d.igst_amt)}</span>
              </div>
            )}
            <div className="cn-row net">
              <span className="cn-l">Total Credit Amount</span>
              <span className="cn-v">{fmtAmt(d.amount)}</span>
            </div>
          </div>
        </div>

        {/* â”€â”€ FOOTER â”€â”€ */}
        <div className="cn-footer">
          <div className="cn-terms">
            <b>Terms &amp; Conditions:</b>
            <div>1. This credit note is issued against the above referenced invoice only.</div>
            <div>2. Goods once returned cannot be re-exchanged without prior approval.</div>
            <div>3. This is a computer-generated document.</div>
          </div>
          <div className="cn-stamp">
            <div className="cn-sig-label">
              For {d.company_legal_name || d.company_name || ""}
            </div>
            <div className="cn-sig-space" />
            <div className="cn-sig-line" />
            <div className="cn-sig-name">Authorised Signatory</div>
            <div className="cn-sig-sub">System-generated credit note</div>
          </div>
        </div>

      </div>
    </>
  );
}

