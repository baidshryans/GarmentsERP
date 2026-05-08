// frontend/src/services/print/printHelpers.js

/* ─── number / date formatters ─────────────────────────────────── */

export const fmt = (n) => {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num) || num === 0) return "";
  return num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export const fmtDate = (s) => {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d)) return s;
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return String(d.getDate()).padStart(2, "0") + " " + months[d.getMonth()] + " " + d.getFullYear();
};

export function numberToWords(num) {
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

/* ─── voucher type helpers ──────────────────────────────────────── */

const GST_RE  = /cgst|sgst|igst|tcs|tds|gst/i;
const CASH_RE = /cash/i;
const BANK_RE = /bank|hdfc|sbi|icici|axis|kotak|yes\s*bank/i;

export const isGst  = (l) => GST_RE.test(l.account || "");
export const isRcpt = (t) => t === "RCPT-SALE" || t === "RCPT";
export const isPmnt = (t) => t === "PMNT"       || t === "PMNT-PURC";

export function detectParty(lines, type) {
  if (isRcpt(type)) return lines.find((l) => (l.credit || 0) > 0 && !isGst(l)) || null;
  if (isPmnt(type)) return lines.find((l) => (l.debit  || 0) > 0 && !isGst(l)) || null;
  return null;
}

export function detectMode(lines, type) {
  let cashBankLine = null;
  if (isRcpt(type)) cashBankLine = lines.find((l) => (l.debit  || 0) > 0 && !isGst(l));
  if (isPmnt(type)) cashBankLine = lines.find((l) => (l.credit || 0) > 0 && !isGst(l));
  if (!cashBankLine) return null;
  const name = cashBankLine.account || "";
  if (CASH_RE.test(name)) return { label: "Cash",    account: name };
  if (BANK_RE.test(name)) return { label: "Bank",    account: name };
  return                         { label: "Account", account: name };
}
