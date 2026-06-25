import React from "react";
import { formatNumber } from "@/lib/format";

const fmt = (n, dec = 2) => {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num)) return "";
  return formatNumber(num, { decimals: dec });
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
  const tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];
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
  const lakh = Math.floor((whole % 10000000) / 100000);
  const thou = Math.floor((whole % 100000) / 1000);
  const rest = whole % 1000;
  let res = "";
  if (crore) res += group(crore) + " Crore ";
  if (lakh) res += group(lakh) + " Lakh ";
  if (thou) res += group(thou) + " Thousand ";
  if (rest) res += group(rest);
  return "Rupees " + res.trim() + " Only";
}

const S = {
  page: {
    fontFamily: "Arial, sans-serif",
    fontSize: "12px",
    color: "#111",
    padding: "20mm 15mm",
    maxWidth: "210mm",
    margin: "0 auto",
  },
  title: {
    textAlign: "center",
    fontSize: "18px",
    fontWeight: "bold",
    margin: "0 0 4px",
    textTransform: "uppercase",
  },
  subtitle: {
    textAlign: "center",
    fontSize: "10px",
    color: "#555",
    margin: "0 0 16px",
  },
  hr: { borderTop: "1px solid #999", margin: "12px 0" },
  grid: { display: "flex", justifyContent: "space-between", gap: "20px" },
  col: { flex: 1 },
  label: { fontSize: "9px", color: "#888", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "2px" },
  value: { fontSize: "12px", fontWeight: "500", marginBottom: "8px" },
  table: { width: "100%", borderCollapse: "collapse", marginTop: "16px" },
  th: {
    border: "1px solid #bbb",
    padding: "6px 10px",
    fontSize: "10px",
    fontWeight: "600",
    textTransform: "uppercase",
    backgroundColor: "#f5f5f5",
    textAlign: "left",
  },
  td: {
    border: "1px solid #bbb",
    padding: "6px 10px",
    fontSize: "11px",
  },
  tdRight: {
    border: "1px solid #bbb",
    padding: "6px 10px",
    fontSize: "11px",
    textAlign: "right",
  },
  totalRow: { fontWeight: "bold", fontSize: "13px" },
  amountWords: {
    marginTop: "12px",
    padding: "8px 12px",
    border: "1px solid #bbb",
    backgroundColor: "#fafafa",
    fontSize: "11px",
    fontStyle: "italic",
  },
  sigBlock: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: "50px",
    paddingTop: "8px",
  },
  sigLabel: { fontSize: "10px", color: "#555", borderTop: "1px solid #999", paddingTop: "4px", width: "160px", textAlign: "center" },
  footer: { textAlign: "center", fontSize: "9px", color: "#999", marginTop: "24px" },
};

export default function CreditDebitNotePrint({ data }) {
  if (!data) return null;

  const isCN = data.note_type === "CN";
  const titleText = isCN ? "CREDIT NOTE" : "DEBIT NOTE";

  const hasCGST = (data.cgst_amt || 0) > 0;
  const hasSGST = (data.sgst_amt || 0) > 0;
  const hasIGST = (data.igst_amt || 0) > 0;

  return (
    <div style={S.page}>
      {/* Header */}
      <p style={S.title}>{data.company_name}</p>
      <p style={S.subtitle}>{data.company_address}</p>
      <div style={{ ...S.hr, borderTop: "2px solid #333" }} />

      <p style={{ ...S.title, fontSize: "15px", margin: "8px 0 12px" }}>{titleText}</p>

      {/* Note details + Party */}
      <div style={S.grid}>
        <div style={S.col}>
          <div style={S.label}>Note No</div>
          <div style={S.value}>{data.note_no}</div>
          <div style={S.label}>Date</div>
          <div style={S.value}>{fmtDate(data.date)}</div>
          {data.ref_invoice_no && (
            <>
              <div style={S.label}>Against Invoice</div>
              <div style={S.value}>{data.ref_invoice_no} {data.ref_invoice_date ? `(${fmtDate(data.ref_invoice_date)})` : ""}</div>
            </>
          )}
        </div>
        <div style={S.col}>
          <div style={S.label}>{isCN ? "Customer" : "Vendor"}</div>
          <div style={{ ...S.value, fontWeight: "bold" }}>{data.party_name}</div>
          {data.party_address && (
            <div style={{ ...S.value, fontSize: "10px", color: "#555" }}>{data.party_address}</div>
          )}
          {data.party_gstin && (
            <>
              <div style={S.label}>GSTIN</div>
              <div style={S.value}>{data.party_gstin}</div>
            </>
          )}
          {data.party_state && (
            <>
              <div style={S.label}>State</div>
              <div style={S.value}>{data.party_state}</div>
            </>
          )}
        </div>
      </div>

      {data.company_gstin && (
        <div style={{ fontSize: "10px", color: "#555", marginBottom: "8px" }}>
          <strong>GSTIN:</strong> {data.company_gstin}
          {data.company_state ? ` | State: ${data.company_state}` : ""}
        </div>
      )}

      {/* Reason */}
      <div style={S.hr} />
      <div style={S.label}>Reason for Issue</div>
      <div style={{ ...S.value, marginBottom: "12px" }}>{data.reason}</div>

      {/* Tax Table */}
      <table style={S.table}>
        <thead>
          <tr>
            <th style={S.th}>Particulars</th>
            <th style={{ ...S.th, textAlign: "right" }}>Amount (₹)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style={S.td}>Taxable Value</td>
            <td style={S.tdRight}>{fmt(data.taxable_value)}</td>
          </tr>
          {hasCGST && (
            <tr>
              <td style={S.td}>CGST @ {fmt(data.cgst_per)}%</td>
              <td style={S.tdRight}>{fmt(data.cgst_amt)}</td>
            </tr>
          )}
          {hasSGST && (
            <tr>
              <td style={S.td}>SGST @ {fmt(data.sgst_per)}%</td>
              <td style={S.tdRight}>{fmt(data.sgst_amt)}</td>
            </tr>
          )}
          {hasIGST && (
            <tr>
              <td style={S.td}>IGST @ {fmt(data.igst_per)}%</td>
              <td style={S.tdRight}>{fmt(data.igst_amt)}</td>
            </tr>
          )}
          <tr style={S.totalRow}>
            <td style={{ ...S.td, fontWeight: "bold" }}>Total</td>
            <td style={{ ...S.tdRight, fontWeight: "bold", fontSize: "13px" }}>₹{fmt(data.amount)}</td>
          </tr>
        </tbody>
      </table>

      {/* Amount in words */}
      <div style={S.amountWords}>
        <strong>Amount in words:</strong> {numberToWords(data.amount)}
      </div>

      {/* Adjustment ledger */}
      <div style={{ marginTop: "12px", fontSize: "10px", color: "#555" }}>
        <strong>Adjusted to:</strong> {data.adjustment_ledger}
      </div>

      {/* Signature */}
      <div style={S.sigBlock}>
        <div style={S.sigLabel}>Authorised Signatory</div>
        <div style={S.sigLabel}>{isCN ? "Customer" : "Vendor"} Acknowledgement</div>
      </div>

      <div style={S.footer}>This is a computer-generated document</div>
    </div>
  );
}
