import React from "react";

/* ────────────────────────────────────────────────────────────────────────────
   SalesInvoice — minimal modern Tax Invoice print format.
   Renders a one-page A4 invoice using the same `data` prop produced by
   SalesVoucherList. Designed to be opened in a fresh window for printing
   (browser native print, no PDF library).
   ──────────────────────────────────────────────────────────────────────────── */

/* ─── Number / date helpers ──────────────────────────────────────────────── */

const fmt = (n, dec = 2) => {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num)) return "";
  return num.toLocaleString("en-IN", {
    minimumFractionDigits: dec,
    maximumFractionDigits: dec,
  });
};

const fmtInt = (n) => {
  if (n === null || n === undefined || n === "") return "";
  const num = parseFloat(n);
  if (isNaN(num)) return "";
  return Math.round(num).toLocaleString("en-IN");
};

const fmtDate = (s) => {
  if (!s) return "";
  const d = new Date(s);
  if (isNaN(d)) return s;
  const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return `${String(d.getDate()).padStart(2, "0")} ${months[d.getMonth()]} ${d.getFullYear()}`;
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
    else {
      if (Math.floor(rem / 10)) r += tens[Math.floor(rem / 10)] + (rem % 10 ? " " : "");
      if (rem % 10) r += units[rem % 10];
    }
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

/* ─── Indian state lookup (abbrev or full name → { name, code }) ─────────── */

const STATE_MAP = (() => {
  const rows = [
    ["AN", "Andaman and Nicobar Islands", "35"],
    ["AP", "Andhra Pradesh", "37"],
    ["AR", "Arunachal Pradesh", "12"],
    ["AS", "Assam", "18"],
    ["BR", "Bihar", "10"],
    ["CG", "Chhattisgarh", "22"], ["CT", "Chhattisgarh", "22"],
    ["CH", "Chandigarh", "04"],
    ["DD", "Daman and Diu", "25"],
    ["DL", "Delhi", "07"],
    ["DN", "Dadra and Nagar Haveli", "26"],
    ["GA", "Goa", "30"],
    ["GJ", "Gujarat", "24"],
    ["HP", "Himachal Pradesh", "02"],
    ["HR", "Haryana", "06"],
    ["JH", "Jharkhand", "20"],
    ["JK", "Jammu and Kashmir", "01"],
    ["KA", "Karnataka", "29"],
    ["KL", "Kerala", "32"],
    ["LA", "Ladakh", "38"],
    ["LD", "Lakshadweep", "31"],
    ["MH", "Maharashtra", "27"],
    ["ML", "Meghalaya", "17"],
    ["MN", "Manipur", "14"],
    ["MP", "Madhya Pradesh", "23"],
    ["MZ", "Mizoram", "15"],
    ["NL", "Nagaland", "13"],
    ["OD", "Odisha", "21"], ["OR", "Odisha", "21"],
    ["PB", "Punjab", "03"],
    ["PY", "Puducherry", "34"],
    ["RJ", "Rajasthan", "08"],
    ["SK", "Sikkim", "11"],
    ["TG", "Telangana", "36"], ["TS", "Telangana", "36"],
    ["TN", "Tamil Nadu", "33"],
    ["TR", "Tripura", "16"],
    ["UK", "Uttarakhand", "05"], ["UT", "Uttarakhand", "05"],
    ["UP", "Uttar Pradesh", "09"],
    ["WB", "West Bengal", "19"],
  ];
  const m = {};
  rows.forEach(([abbr, name, code]) => {
    m[abbr.toUpperCase()] = { name, code };
    m[name.toUpperCase()] = { name, code };
  });
  return m;
})();

const resolveState = (value, fallbackCode) => {
  const raw = (value || "").toString().trim();
  const hit = STATE_MAP[raw.toUpperCase()];
  if (hit) {
    return { name: hit.name, code: hit.code, label: `${hit.name} (${hit.code})` };
  }
  const code = (fallbackCode || "").toString().trim();
  return { name: raw, code, label: raw + (code ? ` (${code})` : "") };
};

/* ─── Stylesheet ──────────────────────────────────────────────────────────── */

const FONTS_HREF =
  "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap";

const INVOICE_CSS = `
:root {
  --ink: #0f172a;
  --body: #1e293b;
  --muted: #64748b;
  --faint: #94a3b8;
  --rule: #e2e8f0;
  --band: #f8fafc;
}
.si-root, .si-root * { box-sizing: border-box; margin: 0; padding: 0; }
.si-root {
  background: #eef2f6;
  font-family: "Inter", "Helvetica Neue", Arial, sans-serif;
  color: var(--body);
  font-feature-settings: "tnum" 1, "lnum" 1;
  -webkit-font-smoothing: antialiased;
  width: 100%;
  min-height: 100vh;
  display: block;
}
.si-page {
  width: 210mm;
  height: 297mm;
  margin: 24px auto;
  background: #fff;
  padding: 10mm 11mm;
  box-shadow: 0 4px 24px rgba(15, 23, 42, 0.08);
  color: var(--body);
  font-size: 9px;
  line-height: 1.45;
  display: flex; flex-direction: column;
  overflow: hidden;
  break-after: page;
  page-break-after: always;
}
.si-page:last-of-type {
  break-after: auto;
  page-break-after: auto;
}

/* Header */
.si-hdr {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--ink);
  text-align: center;
}
.si-bis {
  width: 64px; height: 64px;
  border: 1px dashed var(--faint);
  border-radius: 50%;
  display: grid; place-items: center;
  font-size: 7.5px; color: var(--muted); text-align: center; line-height: 1.15;
  letter-spacing: 0.5px;
}
.si-logo {
  width: 90px; height: 64px;
  border: 1px dashed var(--faint);
  display: grid; place-items: center;
  font-size: 7.5px; color: var(--muted); text-align: center; line-height: 1.15;
  letter-spacing: 0.5px;
}
.si-bis img, .si-logo img { max-width: 100%; max-height: 100%; object-fit: contain; }
.si-brand-block { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.si-brand {
  font-family: "Fraunces", Georgia, serif;
  font-size: 34px; font-weight: 700; color: var(--ink);
  letter-spacing: -0.5px; line-height: 1;
}
.si-brand-sub { font-size: 9px; color: var(--muted); letter-spacing: 0.2px; }
.si-brand-sub strong { color: var(--ink); font-weight: 600; }
.si-brand-ids { display: flex; gap: 18px; font-size: 8.5px; color: var(--muted); margin-top: 2px; }
.si-brand-ids span b { color: var(--ink); font-weight: 600; margin-left: 4px; font-variant-numeric: tabular-nums; }

/* Invoice header */
.si-invoice-head {
  text-align: center;
  margin: 12px 0 10px;
}
.si-invoice-head .si-title {
  font-size: 11px; letter-spacing: 4px; text-transform: uppercase;
  color: var(--ink); font-weight: 700;
}
.si-invoice-head .si-meta {
  font-size: 10px; color: var(--muted);
  font-variant-numeric: tabular-nums;
  margin-top: 4px;
}
.si-invoice-head .si-meta .si-num {
  color: var(--ink); font-weight: 700; letter-spacing: 0.2px;
}
.si-invoice-head .si-meta .si-sep { color: var(--faint); margin: 0 8px; }
.si-invoice-head .si-meta .si-date { color: var(--ink); font-weight: 600; }

/* Parties */
.si-parties {
  display: grid; grid-template-columns: 1fr 1fr;
  margin-bottom: 12px;
  border: 1px solid var(--rule);
  border-radius: 4px;
  overflow: hidden;
}
.si-party { padding: 10px 12px; position: relative; }
.si-party + .si-party { border-left: 1px solid var(--rule); }
.si-party .si-pe {
  font-size: 7px; letter-spacing: 1.8px; text-transform: uppercase;
  color: var(--muted); font-weight: 700; margin-bottom: 6px;
  display: flex; align-items: center; gap: 8px;
}
.si-party .si-pe::after { content: ""; flex: 1; height: 1px; background: var(--rule); }
.si-party .si-name { font-size: 13px; font-weight: 700; color: var(--ink); letter-spacing: -0.1px; }
.si-party .si-addr { font-size: 9px; color: var(--body); margin-top: 4px; line-height: 1.55; }
.si-party .si-ids {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 8px 14px; margin-top: 10px; padding-top: 10px;
  border-top: 1px dashed var(--rule);
}
.si-id .si-l {
  font-size: 7px; letter-spacing: 1.4px; text-transform: uppercase;
  color: var(--muted); font-weight: 700;
}
.si-id .si-v {
  font-size: 9px; color: var(--ink); font-weight: 600;
  font-variant-numeric: tabular-nums; margin-top: 1px;
  word-break: break-all;
}
.si-id .si-v.empty { color: var(--faint); font-weight: 400; }

/* Metal rate */
.si-rate {
  display: flex; align-items: baseline; gap: 18px;
  padding: 7px 0;
  border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  margin-bottom: 14px;
  font-variant-numeric: tabular-nums;
}
.si-rate .si-l {
  font-size: 7.5px; letter-spacing: 1.6px; text-transform: uppercase;
  color: var(--muted); font-weight: 700;
}
.si-rate .si-r {
  font-size: 10px; color: var(--ink); font-weight: 500;
}

/* Items table */
table.si-items {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 8.5px;
}
table.si-items thead th {
  text-align: right;
  padding: 7px 5px;
  font-size: 7px; letter-spacing: 1.2px; text-transform: uppercase;
  color: var(--muted); font-weight: 700;
  border-bottom: 1px solid var(--ink);
}
table.si-items thead th.l { text-align: left; }
table.si-items thead th.c { text-align: center; }
table.si-items tbody td {
  padding: 6px 5px;
  border-bottom: 1px solid var(--rule);
  vertical-align: top;
  text-align: right;
  font-variant-numeric: tabular-nums;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
table.si-items tbody td.l { text-align: left; }
table.si-items tbody td.c { text-align: center; }
table.si-items tbody td.product {
  text-align: left;
  color: var(--ink); font-weight: 600; font-size: 9px;
}
table.si-items tbody tr.parent td { font-weight: 600; color: var(--ink); padding: 6px 5px; }
table.si-items tbody tr.parent td.amt { font-weight: 700; }
table.si-items tbody tr.parent td.sn { font-weight: 700; color: var(--ink); }
table.si-items tbody tr.sub td {
  color: var(--muted);
  border-bottom: 1px dashed var(--rule);
  font-size: 8px;
  padding: 4px 5px;
  background: #fcfcfd;
}
table.si-items tbody tr.sub td.l {
  padding-left: 12px;
  font-style: italic;
}

/* Bottom split */
.si-bottom {
  display: grid; grid-template-columns: 1.4fr 1fr;
  gap: 18px; margin-top: 14px;
}
.si-left h4 {
  font-size: 7.5px; letter-spacing: 1.6px; text-transform: uppercase;
  color: var(--muted); font-weight: 700; margin-bottom: 6px;
}
.si-left .si-block { margin-bottom: 14px; }
.si-purchase-total {
  border: 1px solid var(--rule);
  border-radius: 4px;
  padding: 8px 12px;
  background: var(--band);
}
.si-purchase-total .si-row { display: flex; justify-content: space-between; align-items: baseline; }
.si-purchase-total .si-row .si-l {
  font-size: 8px; letter-spacing: 1.4px; text-transform: uppercase;
  color: var(--muted); font-weight: 700;
}
.si-purchase-total .si-row .si-v {
  font-size: 11px; color: var(--ink); font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.si-purchase-total .si-src {
  margin-top: 4px; font-size: 7.5px; color: var(--faint);
  font-style: italic; letter-spacing: 0.3px;
}
.si-buyback {
  display: grid; grid-template-columns: 1.4fr 1fr 0.7fr;
  gap: 16px; padding: 4px 0 0;
}
.si-buyback .si-col .si-t {
  font-size: 7px; letter-spacing: 1.4px; text-transform: uppercase;
  color: var(--muted); font-weight: 700; margin-bottom: 3px;
}
.si-buyback .si-col .si-v { font-size: 9px; color: var(--body); font-weight: 400; line-height: 1.5; }

.si-pay-row { display: flex; gap: 22px; align-items: baseline; margin-bottom: 8px; }
.si-pay-row .si-pay { display: flex; align-items: baseline; gap: 6px; }
.si-pay-row .si-pay .si-pl {
  font-size: 7.5px; letter-spacing: 1.4px; text-transform: uppercase;
  color: var(--muted); font-weight: 700;
}
.si-pay-row .si-pay .si-pv {
  font-size: 11px; color: var(--ink); font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.si-words {
  font-size: 8.5px; color: var(--muted); font-style: italic;
  border-top: 1px dashed var(--rule); padding-top: 6px;
}
.si-words b { color: var(--ink); font-style: normal; font-weight: 600; }

/* Totals ladder */
.si-totals { font-size: 9.5px; }
.si-totals .si-row {
  display: flex; justify-content: space-between; align-items: baseline;
  padding: 5px 0; color: var(--body);
}
.si-totals .si-row .si-l {
  font-size: 8px; letter-spacing: 1.2px; text-transform: uppercase;
  color: var(--muted); font-weight: 600;
}
.si-totals .si-row .si-v {
  font-variant-numeric: tabular-nums; font-weight: 600; color: var(--ink);
}
.si-totals .si-row.bold {
  border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  padding: 7px 0;
}
.si-totals .si-row.bold .si-l { color: var(--ink); font-weight: 700; }
.si-totals .si-row.bold .si-v { font-weight: 700; }
.si-totals .si-row.net {
  margin-top: 4px; border-top: 2px solid var(--ink); padding: 8px 0;
}
.si-totals .si-row.net .si-l { color: var(--ink); font-weight: 700; font-size: 9px; }
.si-totals .si-row.net .si-v { font-weight: 700; }

/* Footer */
.si-footer {
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--rule);
}
.si-footer .si-terms {
  font-size: 8px; color: var(--muted); line-height: 1.6;
  margin-bottom: 16px;
}
.si-footer .si-terms div + div { margin-top: 2px; }
.si-footer .si-terms b { color: var(--ink); font-weight: 600; }
.si-sig-row { display: grid; grid-template-columns: 1fr 1fr; gap: 32px; align-items: end; }
.si-sig {
  text-align: center;
  display: flex; flex-direction: column; align-items: stretch;
  min-height: 78px;
}
.si-sig .si-for {
  font-size: 7.5px; letter-spacing: 1px; text-transform: uppercase;
  color: var(--muted); font-weight: 600; margin-bottom: 4px;
}
.si-sig .si-space {
  flex: 1; min-height: 56px;
  border-bottom: 1px solid var(--ink); margin-bottom: 5px;
}
.si-sig .si-l {
  font-size: 7.5px; letter-spacing: 1.6px; text-transform: uppercase;
  color: var(--ink); font-weight: 700;
}
.si-stamp {
  margin-top: 10px;
  display: flex; align-items: center; justify-content: space-between;
  font-size: 7.5px; color: var(--faint);
  letter-spacing: 0.4px; font-style: italic;
}
.si-stamp .si-pg { font-style: normal; font-weight: 700; color: var(--muted); letter-spacing: 1px; }

@media print {
  @page { size: A4 portrait; margin: 0; }
  html, body { background: #fff; margin: 0; padding: 0; }
  .si-root { background: #fff; }
  .si-page { box-shadow: none; margin: 0; }
  .no-print { display: none !important; }
}
`;

/* ─── Component ───────────────────────────────────────────────────────────── */

/* Row-budget paginator. Splits blocks across pages such that:
     • the LAST page reserves room for the bottom block (purchase / buy-back /
       payment / totals / signatures), so it gets at most `lastBudget` rows
     • all other pages can take up to `normalBudget` rows
   Each "block" is a parent item + its (already filtered) sub-rows kept
   together; `block.rows` is `1 + subs.length`. */
function paginateBlocks(blocks, lastBudget = 8, normalBudget = 28) {
  if (!blocks.length) return [[]];

  // Greedy: pack the LAST page from the tail (bounded by lastBudget),
  // then pack the remaining items forward into normal pages.
  let lastPage = [];
  let lastUsed = 0;
  let i = blocks.length - 1;
  while (i >= 0 && lastUsed + blocks[i].rows <= lastBudget) {
    lastPage.unshift(blocks[i]);
    lastUsed += blocks[i].rows;
    i--;
  }
  // If even the final block exceeds lastBudget, take it anyway (overflow case).
  if (lastPage.length === 0) {
    lastPage.push(blocks[blocks.length - 1]);
    i = blocks.length - 2;
  }

  const remaining = blocks.slice(0, i + 1);
  const earlier = [];
  let j = 0;
  while (j < remaining.length) {
    const page = [];
    let used = 0;
    while (j < remaining.length) {
      const next = remaining[j];
      if (used + next.rows > normalBudget && page.length > 0) break;
      page.push(next);
      used += next.rows;
      j++;
    }
    earlier.push(page);
  }
  return [...earlier, lastPage];
}

const SalesInvoice = ({ data = {} }) => {
  const d = data;

  const buyer = resolveState(d.customer_state, d.customer_state_code);
  const ship  = resolveState(
    d.shipping_state || d.customer_state,
    d.shipping_state_code || d.customer_state_code
  );

  /* Normalise metal-rate input. Accepts:
       • d.metal_rates as an array of { label, rate }
       • d.metal_rate_str as a single string ("14K @ 9200" / "14K : 9,200")
       • d.metal_rate_str as a comma- or pipe-separated list of such strings
     For each item, if `rate` is missing but `label` contains a number,
     split the label into purity + rate so the renderer can emit
     "<purity> : ₹ <rate> / gm" consistently. */
  const parseRateString = (s) => {
    if (!s) return null;
    const m = String(s).match(/^\s*(.+?)\s*[@:]\s*([\d.,]+)\s*$/);
    if (m) return { label: m[1].trim(), rate: m[2].replace(/,/g, "") };
    return { label: String(s).trim(), rate: "" };
  };
  const metalRates = (() => {
    if (Array.isArray(d.metal_rates)) {
      return d.metal_rates.map((r) =>
        r.rate || r.rate === 0
          ? { label: r.label, rate: r.rate }
          : parseRateString(r.label) || { label: r.label, rate: "" }
      );
    }
    if (d.metal_rate_str) {
      return String(d.metal_rate_str)
        .split(/[,|]+/)
        .map((s) => parseRateString(s))
        .filter(Boolean);
    }
    return [];
  })();

  const items = d.items || [];

  // Each block = parent item + already-filtered sub-rows (gold "R" stripped).
  // `rows` is the visual row count (parent + visible sub-rows) used by the
  // paginator to decide when to break.
  const blocks = items.map((item, idx) => {
    const subs = (item.sub_rows || []).filter(
      (s) => (s.item_type || "").toUpperCase() !== "R"
    );
    return { item, idx, subs, rows: 1 + subs.length };
  });
  const pages = paginateBlocks(blocks);

  const idCell = (label, value, mono = false) => (
    <div className="si-id">
      <div className="si-l">{label}</div>
      <div className={`si-v${value ? "" : " empty"}`} style={mono ? { fontVariantNumeric: "tabular-nums" } : undefined}>
        {value || "—"}
      </div>
    </div>
  );

  /* ── Repeated section renderers ─────────────────────────────────────── */

  const renderHeader = () => (
    <div className="si-hdr">
      <div className="si-bis">
        {d.bis_logo_url
          ? <img src={d.bis_logo_url} alt="BIS Hallmark" />
          : <span>BIS<br/>HALLMARK</span>}
      </div>
      <div className="si-brand-block">
        <div className="si-brand">{d.company_legal_name || d.legal_name || d.company_name || ""}</div>
        {d.company_address && (
          <div className="si-brand-sub">{d.company_address}</div>
        )}
        {(d.company_phone || d.company_email) && (
          <div className="si-brand-sub">
            {d.company_phone && <>Phone <strong>{d.company_phone}</strong></>}
            {d.company_phone && d.company_email && <>&nbsp; ·&nbsp; </>}
            {d.company_email && <>Email <strong>{d.company_email}</strong></>}
          </div>
        )}
        {(d.company_gstin || d.company_pan || d.company_cin) && (
          <div className="si-brand-ids">
            {d.company_gstin && <span>GSTIN<b>{d.company_gstin}</b></span>}
            {d.company_pan   && <span>PAN<b>{d.company_pan}</b></span>}
            {d.company_cin   && <span>CIN<b>{d.company_cin}</b></span>}
          </div>
        )}
      </div>
      <div className="si-logo">
        {d.company_logo_url
          ? <img src={d.company_logo_url} alt="Logo" />
          : <span>COMPANY<br/>LOGO</span>}
      </div>
    </div>
  );

  const renderInvoiceStrip = () => (
    <div className="si-invoice-head">
      <div className="si-title">Tax Invoice</div>
      <div className="si-meta">
        <span className="si-num">{d.gst_billno || d.billno || ""}</span>
        <span className="si-sep">·</span>
        <span className="si-date">{fmtDate(d.date1)}</span>
      </div>
    </div>
  );

  const renderParties = () => (
    <div className="si-parties">
      <div className="si-party">
        <div className="si-pe">Billed to</div>
        <div className="si-name">{d.customer_name || ""}</div>
        <div className="si-addr">{d.customer_address || ""}</div>
        <div className="si-ids">
          {idCell("State",  buyer.label)}
          {idCell("PAN",    d.customer_pan,    true)}
          {idCell("GSTIN",  d.customer_gstin,  true)}
          {idCell("Aadhar", d.customer_aadhar, true)}
          {idCell("DL No",  d.customer_dl,     true)}
          {idCell("Phone",  d.customer_phone,  true)}
        </div>
      </div>
      <div className="si-party">
        <div className="si-pe">Shipped to</div>
        <div className="si-name">{d.shipping_name || d.customer_name || ""}</div>
        <div className="si-addr">{d.shipping_address || d.customer_address || ""}</div>
        <div className="si-ids">
          {idCell("Place of Supply", ship.label)}
          {idCell("PAN",       d.shipping_pan   || d.customer_pan,   true)}
          {idCell("GSTIN",     d.shipping_gstin || d.customer_gstin, true)}
          {idCell("Mode",      d.mode_of_transport)}
          {idCell("Vehicle",   d.vehicle_no, true)}
          {idCell("E-way Ref", d.eway_ref_no, true)}
        </div>
      </div>
    </div>
  );

  const renderMetalRate = () => (
    <div className="si-rate">
      <span className="si-l">Metal Rate</span>
      {metalRates.length > 0
        ? metalRates.map((r, i) => (
            <span key={i} className="si-r">
              {r.label}
              {r.rate !== "" && r.rate !== undefined && r.rate !== null && (
                <> : ₹ {fmtInt(r.rate)} / gm</>
              )}
            </span>
          ))
        : <span className="si-r" style={{ color: "var(--faint)" }}>—</span>}
    </div>
  );

  const renderItemsTable = (pageBlocks) => (
    <table className="si-items">
      <colgroup>
        <col style={{ width: "4%"  }} />{/* S.No */}
        <col style={{ width: "17%" }} />{/* Item */}
        <col style={{ width: "7%"  }} />{/* HSN */}
        <col style={{ width: "6%"  }} />{/* Purity */}
        <col style={{ width: "4%"  }} />{/* Pcs */}
        <col style={{ width: "6%"  }} />{/* GW */}
        <col style={{ width: "6%"  }} />{/* NW */}
        <col style={{ width: "7%"  }} />{/* Rate */}
        <col style={{ width: "9%"  }} />{/* Metal Value */}
        <col style={{ width: "9%"  }} />{/* Stone Value */}
        <col style={{ width: "8%"  }} />{/* Making */}
        <col style={{ width: "7%"  }} />{/* Other */}
        <col style={{ width: "10%" }} />{/* Amount */}
      </colgroup>
      <thead>
        <tr>
          <th className="c">S.No</th>
          <th className="l">Item</th>
          <th className="c">HSN</th>
          <th className="c">Purity</th>
          <th>Pcs</th>
          <th>GW</th>
          <th>NW</th>
          <th>Rate</th>
          <th>Metal Value</th>
          <th>Stone Value</th>
          <th>Making</th>
          <th>Other</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        {pageBlocks.map((b) => {
          const item = b.item;
          return (
            <React.Fragment key={b.idx}>
              <tr className="parent">
                <td className="c sn">{item.sn ?? b.idx + 1}</td>
                <td className="product">{item.item_name}</td>
                <td className="c">{item.hsn}</td>
                <td className="c">{item.purity}</td>
                <td>{item.pcs}</td>
                <td>{fmt(item.gw, 3)}</td>
                <td>{fmt(item.nw, 3)}</td>
                <td>{item.rate ? fmtInt(item.rate) : ""}</td>
                <td>{item.metal_value ? fmtInt(item.metal_value) : ""}</td>
                <td>{item.stone_value ? fmtInt(item.stone_value) : ""}</td>
                <td>{item.making ? fmtInt(item.making) : ""}</td>
                <td>{item.other_value ? fmtInt(item.other_value) : "0"}</td>
                <td className="amt">{item.amount ? fmtInt(item.amount) : ""}</td>
              </tr>
              {b.subs.map((sub, si) => (
                <tr className="sub" key={si}>
                  <td className="c"></td>
                  <td className="l" colSpan={4}>↳ {sub.text}</td>
                  <td>{sub.gw ? fmt(sub.gw, 3) : ""}</td>
                  <td></td>
                  <td>{sub.rate ? fmtInt(sub.rate) : ""}</td>
                  <td></td>
                  <td>{(sub.item_type || "").toUpperCase() === "S" && sub.amount ? fmtInt(sub.amount) : ""}</td>
                  <td>{(sub.item_type || "").toUpperCase() === "M" && sub.amount ? fmtInt(sub.amount) : ""}</td>
                  <td>
                    {(["O","H"].includes((sub.item_type || "").toUpperCase()) && sub.amount)
                      ? fmtInt(sub.amount) : ""}
                  </td>
                  <td></td>
                </tr>
              ))}
            </React.Fragment>
          );
        })}
      </tbody>
    </table>
  );

  const renderBottomSplit = () => (
    <div className="si-bottom">
      <div className="si-left">
        {/* Purchase Total */}
        <div className="si-block">
          <h4>Purchase Details</h4>
          <div className="si-purchase-total">
            <div className="si-row">
              <span className="si-l">Total Purchase Amount</span>
              <span className="si-v">
                {d.purchase_total != null && d.purchase_total !== ""
                  ? <>₹ {fmtInt(d.purchase_total)}</>
                  : "—"}
              </span>
            </div>
            {d.purchase_voucher_ref && (
              <div className="si-src">
                From Purchase Voucher · {d.purchase_voucher_ref}
                {d.purchase_voucher_date && <> · {fmtDate(d.purchase_voucher_date)}</>}
              </div>
            )}
          </div>
        </div>

        {/* Buy-back Policy */}
        <div className="si-block">
          <h4>Buy-back Policy &amp; Deductions</h4>
          <div className="si-buyback">
            <div className="si-col">
              <div className="si-t">Stones</div>
              <div className="si-v">
                {d.buyback_stones_l1 || "Lab Grown Diamonds — 30%"}<br/>
                {d.buyback_stones_l2 || "Precious Col. Stone — 25%, Imitation — 100%"}
              </div>
            </div>
            <div className="si-col">
              <div className="si-t">Gold</div>
              <div className="si-v">
                {(d.buyback_gold || "Prevailing\nBuying Rate").split("\n").map((l, i) => (
                  <React.Fragment key={i}>{l}{i === 0 && <br/>}</React.Fragment>
                ))}
              </div>
            </div>
            <div className="si-col">
              <div className="si-t">Making</div>
              <div className="si-v">{d.buyback_making || "100%"}</div>
            </div>
          </div>
        </div>

        {/* Mode of Payment */}
        <div className="si-block">
          <h4>Mode of Payment</h4>
          <div className="si-pay-row">
            <div className="si-pay">
              <span className="si-pl">Bank</span>
              <span className="si-pv">₹ {fmtInt(d.bank_total || 0)}</span>
            </div>
            <div className="si-pay">
              <span className="si-pl">Cash</span>
              <span className="si-pv">₹ {fmtInt(d.cash || 0)}</span>
            </div>
          </div>
          <div className="si-words">
            <b>In words:</b> {numberToWords(d.total_bill_value)}
          </div>
        </div>
      </div>

      {/* Totals ladder */}
      <div className="si-totals">
        <div className="si-row"><span className="si-l">Freight Charges</span><span className="si-v">{fmtInt(d.freight_charge || 0)}</span></div>
        <div className="si-row"><span className="si-l">Less: Discount</span><span className="si-v">{fmtInt(d.discount || 0)}</span></div>
        <div className="si-row bold"><span className="si-l">Total Before Tax</span><span className="si-v">{fmtInt(d.taxable_value)}</span></div>
        <div className="si-row"><span className="si-l">{`SGST ${fmt(d.sgst_per || 0, 3)}%`}</span><span className="si-v">{fmtInt(d.sgst_amt || 0)}</span></div>
        <div className="si-row"><span className="si-l">{`CGST ${fmt(d.cgst_per || 0, 3)}%`}</span><span className="si-v">{fmtInt(d.cgst_amt || 0)}</span></div>
        <div className="si-row"><span className="si-l">{`IGST ${fmt(d.igst_per || 0, 3)}%`}</span><span className="si-v">{fmtInt(d.igst_amt || 0)}</span></div>
        {d.tcs_per > 0 && (
          <div className="si-row"><span className="si-l">{`TCS ${fmt(d.tcs_per, 3)}%`}</span><span className="si-v">{fmtInt(d.tcs_amt || 0)}</span></div>
        )}
        <div className="si-row bold"><span className="si-l">Total After Tax</span><span className="si-v">{fmtInt(d.total_bill_value)}</span></div>
        <div className="si-row"><span className="si-l">Less: Advance Amount</span><span className="si-v">{fmtInt(d.advance_deducted || 0)}</span></div>
        <div className="si-row net"><span className="si-l">Net Receivable</span><span className="si-v">₹ {fmtInt(d.net_receivable)}</span></div>
      </div>
    </div>
  );

  const renderSignaturesAndTerms = () => (
    <div className="si-footer">
      <div className="si-terms">
        <div>•&nbsp; Goods sold and delivered from <b>{(d.delivered_from || "Kolkata").toUpperCase()}</b> showroom.</div>
        <div>•&nbsp; Subject to <b>{(d.jurisdiction || "Kolkata").toUpperCase()}</b> jurisdiction only.</div>
        <div>•&nbsp; All disputes are to be settled in writing within 7 days of delivery.</div>
      </div>
      <div className="si-sig-row">
        <div className="si-sig">
          <div className="si-for">&nbsp;</div>
          <div className="si-space"></div>
          <div className="si-l">Customer Signature</div>
        </div>
        <div className="si-sig">
          <div className="si-for">For {(d.company_name || "").toUpperCase()}</div>
          <div className="si-space"></div>
          <div className="si-l">Authorised Signatory</div>
        </div>
      </div>
    </div>
  );

  const renderPageStamp = (pageNum, totalPages) => (
    <div className="si-stamp">
      <span>This is a computer-generated invoice and does not require a signature</span>
      <span className="si-pg">PAGE {pageNum} OF {totalPages}</span>
    </div>
  );

  const totalPages = pages.length;

  return (
    <div className="si-root">
      <link rel="stylesheet" href={FONTS_HREF} />
      <style>{INVOICE_CSS}</style>

      {pages.map((pageBlocks, pageIdx) => {
        const isLast    = pageIdx === totalPages - 1;
        const isFirst   = pageIdx === 0;
        return (
          <div key={pageIdx} className="si-page">
            {renderHeader()}
            {renderInvoiceStrip()}
            {renderParties()}
            {isFirst && renderMetalRate()}
            {renderItemsTable(pageBlocks)}
            {isLast && renderBottomSplit()}
            {isLast && renderSignaturesAndTerms()}
            {renderPageStamp(pageIdx + 1, totalPages)}
          </div>
        );
      })}
    </div>
  );
};
export default SalesInvoice;
