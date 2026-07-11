// frontend/src/services/print/printHelpers.js
import { formatWords, formatNumber } from '@/lib/format';

/* ─── number / date formatters ─────────────────────────────────── */

export const fmt = (n) => {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num) || num === 0) return "";
  return formatNumber(num, { decimals: 2 });
};

export const fmtDate = (s) => {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d)) return s;
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return String(d.getDate()).padStart(2, "0") + " " + months[d.getMonth()] + " " + d.getFullYear();
};

// Relocated to the central formatter (Multi-Country Phase 1). Kept as a named
// re-export so existing print-template importers continue to work unchanged.
export const numberToWords = formatWords;

/* ─── voucher type helpers ──────────────────────────────────────── */

const GST_RE  = /cgst|sgst|igst|tcs|tds|gst/i;
const CASH_RE = /cash/i;
const BANK_RE = /bank|hdfc|sbi|icici|axis|kotak|yes\s*bank/i;

export const isGst  = (l) => GST_RE.test(l.account_name || "");
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
  const name = cashBankLine.account_name || "";
  if (CASH_RE.test(name)) return { label: "Cash",    account: name };
  if (BANK_RE.test(name)) return { label: "Bank",    account: name };
  return                         { label: "Account", account: name };
}
