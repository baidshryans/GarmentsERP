import React from "react";

// ─── Helpers ────────────────────────────────────────────────────────────────
const fmt = (n, dec = 2) => {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num)) return "";
  return num.toLocaleString("en-IN", { minimumFractionDigits: dec, maximumFractionDigits: dec });
};

const fmtDate = (s) => {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d)) return s;
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;
};

function numberToWords(num) {
  if (!num && num !== 0) return "";
  const units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine"];
  const teens = ["Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"];
  const tens  = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];
  const group = (n) => {
    if (n === 0) return "";
    let r = "";
    const h = Math.floor(n / 100), rem = n % 100;
    if (h) r += units[h] + " Hundred" + (rem ? " " : "");
    if (rem >= 10 && rem < 20) r += teens[rem - 10];
    else { if (Math.floor(rem / 10)) r += tens[Math.floor(rem / 10)] + (rem % 10 ? " " : ""); if (rem % 10) r += units[rem % 10]; }
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
  if (lakh)  res += group(lakh) + " Lakh ";
  if (thou)  res += group(thou) + " Thousand ";
  if (rest)  res += group(rest);
  return "Rupees " + res.trim() + " Only";
}

// ─── Styles ──────────────────────────────────────────────────────────────────
const PAGE = {
  fontFamily: "Arial, sans-serif",
  fontSize: "8px",
  lineHeight: "1.25",
  color: "#000",
  backgroundColor: "#fff",
  padding: "10mm 8mm",
  width: "210mm",
  boxSizing: "border-box",
};

const OUTER_TABLE = { width: "100%", borderCollapse: "collapse", border: "1.5px solid #000" };
const TD  = (extra = {}) => ({ border: "1px solid #000", padding: "4px 5px", verticalAlign: "top", ...extra });
const BOLD = { fontWeight: "bold" };

const TH_CELL = (extra = {}) => ({
  border: "1px solid #000", padding: "3px 4px", fontWeight: "bold",
  textAlign: "center", backgroundColor: "#f0f0f0", fontSize: "7.5px", ...extra,
});
const NUM_CELL = { border: "1px solid #000", padding: "3px 4px", textAlign: "right", fontSize: "7.5px" };
const STR_CELL = { border: "1px solid #000", padding: "3px 4px", textAlign: "left",  fontSize: "7.5px" };
const CTR_CELL = { border: "1px solid #000", padding: "3px 4px", textAlign: "center",fontSize: "7.5px" };

// ─── Sub-components ───────────────────────────────────────────────────────────
const B = ({ children }) => <span style={BOLD}>{children}</span>;

const Row = ({ label, value }) => (
  <div style={{ fontSize: "7.5px", marginBottom: "2px" }}>
    <B>{label}: </B>{value || ""}
  </div>
);

const SumRow = ({ label, value, bold, highlight }) => (
  <tr style={highlight ? { backgroundColor: "#e8e8e8" } : {}}>
    <td style={{ border: "1px solid #000", padding: "2px 4px", fontWeight: bold ? "bold" : "normal", backgroundColor: highlight ? "#e8e8e8" : bold ? "#f5f5f5" : "transparent" }}>
      {label}
    </td>
    <td style={{ border: "1px solid #000", padding: "2px 4px", textAlign: "right", fontWeight: bold ? "bold" : "normal", backgroundColor: highlight ? "#e8e8e8" : bold ? "#f5f5f5" : "transparent" }}>
      {value}
    </td>
  </tr>
);

// ─── Main Component ───────────────────────────────────────────────────────────
const SaleReturnCreditNote = ({ data = {} }) => {
  if (!data) return null;

  const hasCGST = (data.cgst_per || 0) > 0;
  const hasSGST = (data.sgst_per || 0) > 0;
  const hasIGST = (data.igst_per || 0) > 0;

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

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ textAlign: "center", marginBottom: "4px" }}>
        <div style={{ fontSize: "14px", fontWeight: "bold", letterSpacing: "1px" }}>
          {data.company_name || "JEWEL INDIA JEWELLERS"}
        </div>
        <div style={{ fontSize: "8px", marginTop: "2px" }}>{data.company_address}</div>
        {data.company_gstin && (
          <div style={{ fontSize: "8px" }}>GSTIN: {data.company_gstin}</div>
        )}
        <div style={{ fontSize: "11px", fontWeight: "bold", marginTop: "4px", letterSpacing: "2px" }}>
          CREDIT NOTE
        </div>
        <div style={{ fontSize: "7px", color: "#444" }}>
          (Sales Return)
        </div>
      </div>

      <table style={OUTER_TABLE}>
        <tbody>

          {/* ── Party & Note Details ────────────────────────────────────── */}
          <tr>
            <td style={{ ...TD(), width: "50%" }}>
              <div style={{ ...BOLD, fontSize: "7.5px", marginBottom: "3px" }}>CUSTOMER</div>
              <Row label="NAME"    value={data.party_name} />
              {data.party_address && <Row label="ADDRESS" value={data.party_address} />}
              {data.party_state   && <Row label="STATE"   value={data.party_state} />}
              {data.party_gstin   && <Row label="GSTIN"   value={data.party_gstin} />}
            </td>
            <td style={{ ...TD(), width: "50%" }}>
              <Row label="CREDIT NOTE NO"   value={data.note_no} />
              <Row label="DATE"             value={fmtDate(data.date)} />
              {data.company_state  && <Row label="OUR STATE"   value={data.company_state} />}
              {data.company_gstin  && <Row label="OUR GSTIN"   value={data.company_gstin} />}
              {data.ref_invoice_no && (
                <Row
                  label="AGAINST INVOICE"
                  value={`${data.ref_invoice_no}${data.ref_invoice_date ? " dt. " + fmtDate(data.ref_invoice_date) : ""}`}
                />
              )}
              <Row label="REASON" value={data.reason || "Customer Return"} />
            </td>
          </tr>

          {/* ── Items Table ──────────────────────────────────────────────── */}
          <tr>
            <td colSpan={2} style={{ padding: 0, border: "1px solid #000" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={TH_CELL({ width: "26px" })}>S.N<br/>PCS</th>
                    <th style={TH_CELL({ textAlign: "left", minWidth: "100px" })}>ITEM DESCRIPTION</th>
                    <th style={TH_CELL({ width: "60px" })}>BARCODE</th>
                    <th style={TH_CELL({ width: "36px" })}>GW</th>
                    <th style={TH_CELL({ width: "48px" })}>MAKING</th>
                    <th style={TH_CELL({ width: "60px" })}>AMOUNT</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.items || []).map((item, idx) => (
                    <React.Fragment key={idx}>
                      <tr>
                        <td style={{ ...CTR_CELL, fontWeight: "bold" }}>
                          {item.sn}<br />{item.pcs}
                        </td>
                        <td style={{ ...STR_CELL, fontWeight: "bold" }}>
                          {item.item_name}
                        </td>
                        <td style={CTR_CELL}>{item.barcode || "—"}</td>
                        <td style={{ ...NUM_CELL, fontWeight: "bold" }}>{fmt(item.gw, 3)}</td>
                        <td style={{ ...NUM_CELL, fontWeight: "bold" }}>{item.making ? fmt(item.making) : "—"}</td>
                        <td style={{ ...NUM_CELL, fontWeight: "bold" }}>{fmt(item.amount)}</td>
                      </tr>
                      {(item.sub_rows || []).map((sub, si) => (
                        <tr key={si} style={{ backgroundColor: "#fafafa" }}>
                          <td style={CTR_CELL}>{sub.pcs || ""}</td>
                          <td style={{ ...STR_CELL, paddingLeft: "12px", color: "#333" }}>{sub.text}</td>
                          <td style={CTR_CELL}>{sub.metal_purity || ""}</td>
                          <td style={NUM_CELL}>{sub.gw ? fmt(sub.gw, 3) : ""}</td>
                          <td style={NUM_CELL}>{sub.rate ? fmt(sub.rate, 0) : ""}</td>
                          <td style={NUM_CELL}>{sub.amount ? fmt(sub.amount) : ""}</td>
                        </tr>
                      ))}
                    </React.Fragment>
                  ))}

                  {/* Totals row */}
                  {(data.items || []).length > 0 && (
                    <tr style={{ backgroundColor: "#f0f0f0" }}>
                      <td style={{ ...CTR_CELL, fontWeight: "bold" }}>
                        {(data.items || []).reduce((s, i) => s + (i.pcs || 0), 0)}
                      </td>
                      <td style={{ ...STR_CELL, fontWeight: "bold" }}>TOTAL</td>
                      <td style={CTR_CELL}></td>
                      <td style={{ ...NUM_CELL, fontWeight: "bold" }}>
                        {fmt((data.items || []).reduce((s, i) => s + (i.gw || 0), 0), 3)}
                      </td>
                      <td style={{ ...NUM_CELL, fontWeight: "bold" }}>
                        {fmt((data.items || []).reduce((s, i) => s + (i.making || 0), 0))}
                      </td>
                      <td style={{ ...NUM_CELL, fontWeight: "bold" }}>
                        {fmt((data.items || []).reduce((s, i) => s + (i.amount || 0), 0))}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </td>
          </tr>

          {/* ── Tax Summary ──────────────────────────────────────────────── */}
          <tr>
            <td style={TD()}>
              <div style={{ ...BOLD, fontSize: "7.5px", marginBottom: "4px" }}>Amount in Words:</div>
              <div style={{ fontStyle: "italic", fontSize: "8px" }}>
                {numberToWords(data.amount)}
              </div>
            </td>
            <td style={TD()}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "7.5px" }}>
                <tbody>
                  <SumRow label="TOTAL ITEMS VALUE"    value={fmt(data.mrp)} />
                  {(data.discount || 0) > 0 && (
                    <SumRow label="LESS DISCOUNT"      value={`- ${fmt(data.discount)}`} />
                  )}
                  <SumRow label="TAXABLE VALUE"        value={fmt(data.taxable_value)} bold />
                  {hasCGST && <SumRow label={`CGST @ ${fmt(data.cgst_per)}%`} value={fmt(data.cgst_amt)} />}
                  {hasSGST && <SumRow label={`SGST @ ${fmt(data.sgst_per)}%`} value={fmt(data.sgst_amt)} />}
                  {hasIGST && <SumRow label={`IGST @ ${fmt(data.igst_per)}%`} value={fmt(data.igst_amt)} />}
                  <SumRow label="TOTAL CREDIT AMOUNT"  value={`₹${fmt(data.amount)}`} bold highlight />
                </tbody>
              </table>
            </td>
          </tr>

          {/* ── Signature ────────────────────────────────────────────────── */}
          <tr>
            <td style={TD()}>
              <div style={{ fontSize: "7px", fontStyle: "italic", marginTop: "4px" }}>
                This credit note is issued in accordance with GST regulations.
              </div>
            </td>
            <td style={{ ...TD(), textAlign: "center" }}>
              <div style={{ ...BOLD, fontSize: "8px", marginBottom: "30px" }}>
                FOR {data.company_name || "JEWEL INDIA JEWELLERS"}
              </div>
              <div style={{ borderTop: "1px solid #000", paddingTop: "4px", ...BOLD, fontSize: "7.5px" }}>
                AUTHORISED SIGNATORY
              </div>
            </td>
          </tr>

        </tbody>
      </table>

      <div style={{ textAlign: "center", fontSize: "6.5px", fontStyle: "italic", marginTop: "4px", color: "#555" }}>
        THIS IS A COMPUTER GENERATED CREDIT NOTE.
      </div>
    </div>
  );
};

export default SaleReturnCreditNote;
