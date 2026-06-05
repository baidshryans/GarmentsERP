import React from "react";

/* ────────────────────────────────────────────────────────────────────────────
   PurchaseVoucherVendor — modern Vendor Purchase Voucher print format.
   Same visual language as SalesInvoice (Inter/Fraunces + slate palette),
   adapted for vendor purchase: vendor party, vendor invoice meta, HSN tax
   breakup, RCM badge, TCS/TDS in the totals ladder.
   Renders one or more A4 pages with row-budget pagination.
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
  return String(d.getDate()).padStart(2, "0") + " " + months[d.getMonth()] + " " + d.getFullYear();
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

/* ─── Indian state lookup ─────────────────────────────────────────────────── */

const STATE_MAP = (() => {
  const rows = [
    ["AN","Andaman and Nicobar Islands","35"],["AP","Andhra Pradesh","37"],
    ["AR","Arunachal Pradesh","12"],["AS","Assam","18"],["BR","Bihar","10"],
    ["CG","Chhattisgarh","22"],["CT","Chhattisgarh","22"],["CH","Chandigarh","04"],
    ["DD","Daman and Diu","25"],["DL","Delhi","07"],["DN","Dadra and Nagar Haveli","26"],
    ["GA","Goa","30"],["GJ","Gujarat","24"],["HP","Himachal Pradesh","02"],
    ["HR","Haryana","06"],["JH","Jharkhand","20"],["JK","Jammu and Kashmir","01"],
    ["KA","Karnataka","29"],["KL","Kerala","32"],["LA","Ladakh","38"],
    ["LD","Lakshadweep","31"],["MH","Maharashtra","27"],["ML","Meghalaya","17"],
    ["MN","Manipur","14"],["MP","Madhya Pradesh","23"],["MZ","Mizoram","15"],
    ["NL","Nagaland","13"],["OD","Odisha","21"],["OR","Odisha","21"],
    ["PB","Punjab","03"],["PY","Puducherry","34"],["RJ","Rajasthan","08"],
    ["SK","Sikkim","11"],["TG","Telangana","36"],["TS","Telangana","36"],
    ["TN","Tamil Nadu","33"],["TR","Tripura","16"],["UK","Uttarakhand","05"],
    ["UT","Uttarakhand","05"],["UP","Uttar Pradesh","09"],["WB","West Bengal","19"],
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
  if (hit) return { name: hit.name, code: hit.code, label: hit.name + " (" + hit.code + ")" };
  const code = (fallbackCode || "").toString().trim();
  return { name: raw, code, label: raw + (code ? " (" + code + ")" : "") };
};

const num = (v) => {
  const n = parseFloat(v);
  return isNaN(n) ? 0 : n;
};

/* ─── Stylesheet ──────────────────────────────────────────────────────────── */

const FONTS_HREF =
  "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap";

const PV_CSS = `
:root{--ink:#0f172a;--body:#1e293b;--muted:#64748b;--faint:#94a3b8;--rule:#e2e8f0;--band:#f8fafc;--neg:#b91c1c;}
.pv-root,.pv-root *{box-sizing:border-box;margin:0;padding:0;}
.pv-root{background:#eef2f6;font-family:"Inter","Helvetica Neue",Arial,sans-serif;color:var(--body);font-feature-settings:"tnum" 1,"lnum" 1;-webkit-font-smoothing:antialiased;width:100%;min-height:100vh;display:block;}
.pv-page{width:210mm;height:297mm;margin:24px auto;background:#fff;padding:10mm 11mm;box-shadow:0 4px 24px rgba(15,23,42,.08);color:var(--body);font-size:9px;line-height:1.45;display:flex;flex-direction:column;overflow:hidden;break-after:page;page-break-after:always;}
.pv-page:last-of-type{break-after:auto;page-break-after:auto;}

/* Header */
.pv-hdr{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:16px;padding-bottom:14px;border-bottom:2px solid var(--ink);text-align:center;}
.pv-bis{width:64px;height:64px;border-radius:50%;display:grid;place-items:center;font-size:7.5px;color:var(--muted);text-align:center;line-height:1.15;letter-spacing:.5px;}
.pv-bis.placeholder{border:1px dashed var(--faint);}
.pv-logo{width:90px;height:64px;display:grid;place-items:center;font-size:7.5px;color:var(--muted);text-align:center;line-height:1.15;letter-spacing:.5px;}
.pv-logo.placeholder{border:1px dashed var(--faint);}
.pv-bis img,.pv-logo img{max-width:100%;max-height:100%;object-fit:contain;}
.pv-brand-block{display:flex;flex-direction:column;align-items:center;gap:4px;}
.pv-brand{font-family:"Fraunces",Georgia,serif;font-size:14px;font-weight:700;color:var(--ink);}
.pv-brand-legal{font-size:11px;font-weight:600;color:var(--ink);}
.pv-brand-sub{font-size:9px;color:var(--muted);letter-spacing:.2px;}
.pv-brand-sub strong{color:var(--ink);font-weight:600;}
.pv-brand-ids{display:flex;gap:18px;font-size:8.5px;color:var(--muted);margin-top:2px;flex-wrap:wrap;justify-content:center;}
.pv-brand-ids span b{color:var(--ink);font-weight:600;margin-left:4px;font-variant-numeric:tabular-nums;}

/* Title strip */
.pv-title{text-align:center;margin:12px 0 10px;position:relative;}
.pv-title .pv-t{font-size:11px;letter-spacing:4px;text-transform:uppercase;color:var(--ink);font-weight:700;}
.pv-title .pv-m{font-size:10px;color:var(--muted);font-variant-numeric:tabular-nums;margin-top:4px;}
.pv-title .pv-m .pv-num{color:var(--ink);font-weight:700;letter-spacing:.2px;}
.pv-title .pv-m .pv-sep{color:var(--faint);margin:0 8px;}
.pv-title .pv-m .pv-date{color:var(--ink);font-weight:600;}
.pv-rcm{position:absolute;left:0;top:0;font-size:8px;letter-spacing:1.6px;font-weight:700;color:var(--neg);border:1px solid var(--neg);padding:2px 6px;border-radius:3px;}
.pv-copy{position:absolute;right:0;top:2px;font-size:8px;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted);font-weight:600;}

/* Parties */
.pv-parties{display:grid;grid-template-columns:1.4fr 1fr;margin-bottom:12px;border:1px solid var(--rule);border-radius:4px;overflow:hidden;}
.pv-party{padding:10px 12px;}
.pv-party + .pv-party{border-left:1px solid var(--rule);}
.pv-pe{font-size:7px;letter-spacing:1.8px;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:6px;display:flex;align-items:center;gap:8px;}
.pv-pe::after{content:"";flex:1;height:1px;background:var(--rule);}
.pv-name{font-size:13px;font-weight:700;color:var(--ink);letter-spacing:-.1px;}
.pv-addr{font-size:9px;color:var(--body);margin-top:4px;line-height:1.55;}
.pv-ids{display:grid;grid-template-columns:repeat(3,1fr);gap:8px 14px;margin-top:10px;padding-top:10px;border-top:1px dashed var(--rule);}
.pv-ids.cols2{grid-template-columns:repeat(2,1fr);}
.pv-id .pv-l{font-size:7px;letter-spacing:1.4px;text-transform:uppercase;color:var(--muted);font-weight:700;}
.pv-id .pv-v{font-size:9px;color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums;margin-top:1px;word-break:break-all;}
.pv-id .pv-v.empty{color:var(--faint);font-weight:400;}

/* Metal rate */
.pv-rate{display:flex;align-items:baseline;gap:18px;padding:7px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin-bottom:14px;font-variant-numeric:tabular-nums;flex-wrap:wrap;}
.pv-rate .pv-l{font-size:7.5px;letter-spacing:1.6px;text-transform:uppercase;color:var(--muted);font-weight:700;}
.pv-rate .pv-r{font-size:10px;color:var(--ink);font-weight:500;}

/* Items table */
table.pv-items{width:100%;border-collapse:collapse;table-layout:fixed;font-size:8.5px;}
table.pv-items thead th{text-align:right;padding:7px 5px;font-size:7px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);font-weight:700;border-bottom:1px solid var(--ink);}
table.pv-items thead th.l{text-align:left;}
table.pv-items thead th.c{text-align:center;}
table.pv-items tbody td{padding:6px 5px;border-bottom:1px solid var(--rule);vertical-align:top;text-align:right;font-variant-numeric:tabular-nums;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
table.pv-items tbody td.l{text-align:left;}
table.pv-items tbody td.c{text-align:center;}
table.pv-items tbody td.product{text-align:left;color:var(--ink);font-weight:600;font-size:9px;}
table.pv-items tbody tr.parent td{font-weight:600;color:var(--ink);padding:6px 5px;}
table.pv-items tbody tr.parent td.amt{font-weight:700;}
table.pv-items tbody tr.parent td.sn{font-weight:700;color:var(--ink);}
table.pv-items tbody tr.sub td{color:var(--muted);border-bottom:1px dashed var(--rule);font-size:8px;padding:4px 5px;background:#fcfcfd;}
table.pv-items tbody tr.sub td.l{padding-left:12px;font-style:italic;}

/* Bottom split */
.pv-bottom{display:grid;grid-template-columns:1.4fr 1fr;gap:18px;margin-top:14px;}
.pv-left h4{font-size:7.5px;letter-spacing:1.6px;text-transform:uppercase;color:var(--muted);font-weight:700;margin-bottom:6px;}
.pv-block{margin-bottom:14px;}
.pv-narr,.pv-words{border:1px solid var(--rule);border-radius:4px;padding:8px 12px;background:var(--band);font-size:9px;color:var(--body);}
.pv-narr b,.pv-words b{color:var(--ink);font-weight:600;}
.pv-words{font-style:italic;margin-top:6px;}
.pv-words b{font-style:normal;}

/* Totals ladder */
.pv-totals{font-size:9.5px;}
.pv-totals .pv-row{display:flex;justify-content:space-between;align-items:baseline;padding:5px 0;color:var(--body);}
.pv-totals .pv-row .pv-l{font-size:8px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);font-weight:600;}
.pv-totals .pv-row .pv-v{font-variant-numeric:tabular-nums;font-weight:600;color:var(--ink);}
.pv-totals .pv-row.bold{border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:7px 0;}
.pv-totals .pv-row.bold .pv-l{color:var(--ink);font-weight:700;}
.pv-totals .pv-row.bold .pv-v{font-weight:700;}
.pv-totals .pv-row.net{margin-top:4px;border-top:2px solid var(--ink);padding:8px 0;}
.pv-totals .pv-row.net .pv-l{color:var(--ink);font-weight:700;font-size:9px;}
.pv-totals .pv-row.net .pv-v{font-weight:700;}
.pv-totals .pv-row.neg .pv-v{color:var(--neg);}

/* Footer */
.pv-footer{margin-top:auto;padding-top:12px;border-top:1px solid var(--rule);}
.pv-terms{font-size:8px;color:var(--muted);line-height:1.6;margin-bottom:16px;}
.pv-terms div + div{margin-top:2px;}
.pv-terms b{color:var(--ink);font-weight:600;}
.pv-sig-row{display:grid;grid-template-columns:1fr 1fr;gap:32px;align-items:end;}
.pv-sig{text-align:center;display:flex;flex-direction:column;align-items:stretch;min-height:78px;}
.pv-sig .pv-for{font-size:7.5px;letter-spacing:1px;text-transform:uppercase;color:var(--muted);font-weight:600;margin-bottom:4px;}
.pv-sig .pv-space{flex:1;min-height:56px;border-bottom:1px solid var(--ink);margin-bottom:5px;}
.pv-sig .pv-l{font-size:7.5px;letter-spacing:1.6px;text-transform:uppercase;color:var(--ink);font-weight:700;}
.pv-stamp{margin-top:10px;display:flex;align-items:center;justify-content:space-between;font-size:7.5px;color:var(--faint);letter-spacing:.4px;font-style:italic;}
.pv-stamp .pv-pg{font-style:normal;font-weight:700;color:var(--muted);letter-spacing:1px;}

@media print{
  @page{size:A4 portrait;margin:0;}
  html,body{background:#fff;margin:0;padding:0;}
  .pv-root{background:#fff;}
  .pv-page{box-shadow:none;margin:0;}
  .no-print{display:none !important;}
}
`;

/* Row-budget paginator. Mirrors SalesInvoice: pack the LAST page from the
   tail (bounded by lastBudget so the bottom split fits), then forward-pack
   the rest into normal pages. */
function paginateBlocks(blocks, lastBudget = 8, normalBudget = 28) {
  if (!blocks.length) return [[]];
  let lastPage = [];
  let lastUsed = 0;
  let i = blocks.length - 1;
  while (i >= 0 && lastUsed + blocks[i].rows <= lastBudget) {
    lastPage.unshift(blocks[i]);
    lastUsed += blocks[i].rows;
    i--;
  }
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

/* ─── Component ───────────────────────────────────────────────────────────── */

const PurchaseVoucherVendor = ({ data = {} }) => {
  const d = data;

  const vendorState = resolveState(d.party_state, d.party_state_code);
  const placeOfSup  = resolveState(d.place_of_supply || d.party_state, d.place_of_supply_code || d.party_state_code);

  const items      = d.purchasevoucheritems_set  || [];
  const directSubs = (d.purchasevoucherdetails_set || []).filter(x => !x.main_item);

  /* Build blocks for pagination: each main item + its subs is one block;
     direct (orphan) subs become their own single-row blocks. */
  const blocks = [];
  directSubs.forEach((sub, idx) => {
    blocks.push({ kind: "direct", sub, idx, rows: 1 });
  });
  items.forEach((item, idx) => {
    const subs = item.purchasevoucherdetails_set || [];
    blocks.push({ kind: "main", item, subs, idx, rows: 1 + subs.length });
  });
  const pages = paginateBlocks(blocks);
  const totalPages = pages.length;

  /* Totals derivations. Subtotal is the taxable-value persisted on the
     voucher (d.tds_taxable_value) — i.e. value exclusive of GST/TCS/TDS. */
  const subtotal    = num(d.tds_taxable_value);
  const hallmark    = num(d.hallmark_charge);
  const freight     = num(d.freight_amt);
  const addChrg1    = num(d.add_chrg_amt1);
  const addChrg2    = num(d.add_chrg_amt2);
  const discount    = num(d.discount_amt);
  const taxable     = subtotal + hallmark + freight + addChrg1 + addChrg2 - discount;
  const cgst        = num(d.cgst);
  const sgst        = num(d.sgst);
  const igst        = num(d.igst);
  const totalTax    = cgst + sgst + igst;
  const totalAfter  = taxable + totalTax;
  const tcs         = num(d.tcs_amt);
  const tds         = num(d.tds_amt);
  const roundOff    = num(d.round_off);
  const netPayable  = num(d.total_incl_gst) || (totalAfter + tcs - tds + roundOff);

  /* Metal rates from items (if rates differ across items, list them). */
  const rateMap = {};
  items.forEach((it) => {
    const rate = num(it.rate);
    const label = it.purity || it.metal_purity || "";
    if (rate > 0 && label) rateMap[label] = rate;
  });
  const metalRates = Object.entries(rateMap).map(([label, rate]) => ({ label, rate }));

  /* GST percentages come from the HSN master (backend-resolved), not from
     amount/taxable ratios — the ratio drifts with rounding. */
  const cgstPer = num(d.hsn_cgst_per);
  const sgstPer = num(d.hsn_sgst_per);
  const igstPer = num(d.hsn_igst_per);
  const tcsPer  = taxable > 0 ? (tcs / taxable) * 100 : 0;

  /* ── Section renderers ─────────────────────────────────────────────────── */

  const idCell = (label, value) => (
    <div className="pv-id">
      <div className="pv-l">{label}</div>
      <div className={"pv-v" + (value ? "" : " empty")}>{value || "—"}</div>
    </div>
  );

  const renderHeader = () => (
    <div className="pv-hdr">
      <div className={d.bis_logo_url ? "pv-bis" : "pv-bis placeholder"}>
        {d.bis_logo_url
          ? <img src={d.bis_logo_url} alt="BIS Hallmark" />
          : <span>BIS<br/>HALLMARK</span>}
      </div>
      <div className="pv-brand-block">
        <div className="pv-brand">{d.company_name || "JEWEL INDIA"}</div>
        {(d.company_legal_name && d.company_legal_name !== d.company_name) && (
          <div className="pv-brand-legal">{d.company_legal_name}</div>
        )}
        {d.company_address && <div className="pv-brand-sub">{d.company_address}</div>}
        {(d.company_phone || d.company_email) && (
          <div className="pv-brand-sub">
            {d.company_phone && <>Phone <strong>{d.company_phone}</strong></>}
            {d.company_phone && d.company_email && <>&nbsp;·&nbsp;</>}
            {d.company_email && <>Email <strong>{d.company_email}</strong></>}
          </div>
        )}
        {(d.company_gstin || d.company_pan || d.company_tan || d.company_cin) && (
          <div className="pv-brand-ids">
            {d.company_gstin && <span>GSTIN<b>{d.company_gstin}</b></span>}
            {d.company_pan   && <span>PAN<b>{d.company_pan}</b></span>}
            {d.company_tan   && <span>TAN<b>{d.company_tan}</b></span>}
            {d.company_cin   && <span>CIN<b>{d.company_cin}</b></span>}
          </div>
        )}
      </div>
      <div className={d.company_logo_url ? "pv-logo" : "pv-logo placeholder"}>
        {d.company_logo_url
          ? <img src={d.company_logo_url} alt="Logo" />
          : <span>COMPANY<br/>LOGO</span>}
      </div>
    </div>
  );

  const renderTitleStrip = () => (
    <div className="pv-title">
      {d.is_rcm ? <span className="pv-rcm">RCM</span> : null}
      <div className="pv-t">Purchase Voucher · Vendor</div>
      <div className="pv-m">
        <span className="pv-num">{d.billno || ""}</span>
        <span className="pv-sep">·</span>
        <span className="pv-date">{fmtDate(d.date1)}</span>
      </div>
      <span className="pv-copy">Original / Duplicate</span>
    </div>
  );

  const renderParties = () => (
    <div className="pv-parties">
      <div className="pv-party">
        <div className="pv-pe">Vendor</div>
        <div className="pv-name">{d.ldgr_name || ""}</div>
        {d.party_address && <div className="pv-addr">{d.party_address}</div>}
        <div className="pv-ids">
          {idCell("State", vendorState.label)}
          {idCell("GSTIN", d.party_gstin)}
          {idCell("PAN",   d.party_pan)}
          {idCell("Phone", d.party_phone)}
          {idCell("Email", d.party_email)}
          {idCell("MSME",  d.party_msme)}
        </div>
      </div>
      <div className="pv-party">
        <div className="pv-pe">Voucher Details</div>
        <div className="pv-ids cols2" style={{ borderTop: "none", paddingTop: 0, marginTop: 0 }}>
          {idCell("Vendor Invoice", d.ref_no)}
          {idCell("Invoice Date",   d.ref_date ? fmtDate(d.ref_date) : "")}
          {idCell("HSN",            d.hsn)}
          {idCell("E-Way Bill",     d.eway_bill_no)}
          {idCell("Place of Supply", placeOfSup.label)}
          {idCell("Supply Type",     d.supply_type || (vendorState.code && placeOfSup.code && vendorState.code !== placeOfSup.code ? "Inter-State" : "Intra-State"))}
          {idCell("Mode",            d.mode_of_transport)}
          {idCell("Vehicle",         d.vehicle_no)}
        </div>
      </div>
    </div>
  );

  const renderMetalRate = () => (
    <div className="pv-rate">
      <span className="pv-l">Metal Rate</span>
      {metalRates.length > 0
        ? metalRates.map((r, i) => (
            <span key={i} className="pv-r">{r.label} : ₹ {fmtInt(r.rate)} / gm</span>
          ))
        : <span className="pv-r" style={{ color: "var(--faint)" }}>—</span>}
    </div>
  );

  const renderItemsTable = (pageBlocks) => (
    <table className="pv-items">
      <colgroup>
        <col style={{ width: "4%"  }} />
        <col style={{ width: "20%" }} />
        <col style={{ width: "6%"  }} />
        <col style={{ width: "6%"  }} />
        <col style={{ width: "4%"  }} />
        <col style={{ width: "7%"  }} />
        <col style={{ width: "7%"  }} />
        <col style={{ width: "7%"  }} />
        <col style={{ width: "9%"  }} />
        <col style={{ width: "8%"  }} />
        <col style={{ width: "8%"  }} />
        <col style={{ width: "5%"  }} />
        <col style={{ width: "9%"  }} />
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
          if (b.kind === "direct") {
            const s = b.sub;
            return (
              <tr className="sub" key={"d-" + b.idx}>
                <td className="c"></td>
                <td className="l" colSpan={4}>↳ {s.sub_item || ""}{s.packet ? " [" + s.packet + "]" : ""}</td>
                <td>{s.sub_gw ? fmt(s.sub_gw, 3) : ""}</td>
                <td>{s.sub_ct ? fmt(s.sub_ct, 3) + " ct" : ""}</td>
                <td>{s.rate ? fmtInt(s.rate) : ""}</td>
                <td>{!s.sub_ct && s.value ? fmtInt(s.value) : ""}</td>
                <td>{s.sub_ct && s.value ? fmtInt(s.value) : ""}</td>
                <td></td>
                <td></td>
                <td>{s.value ? fmtInt(s.value) : ""}</td>
              </tr>
            );
          }
          const item = b.item;
          const amount = num(item.item_value);
          const metalValue = amount - num(item.making_value);
          return (
            <React.Fragment key={"m-" + b.idx}>
              <tr className="parent">
                <td className="c sn">{b.idx + 1}</td>
                <td className="product">
                  {item.item_name || item.item || ""}
                  {item.barcode_txt ? <span style={{ color: "var(--muted)", fontSize: "8px", fontWeight: 500 }}>{" · " + item.barcode_txt}</span> : null}
                  {item.size       ? <span style={{ color: "var(--muted)", fontSize: "8px", fontWeight: 500 }}>{" · Sz " + item.size}</span> : null}
                </td>
                <td className="c">{item.hsn || d.hsn || ""}</td>
                <td className="c">{item.purity || ""}</td>
                <td>{item.pcs ?? ""}</td>
                <td>{fmt(item.gw, 3)}</td>
                <td>{item.nw ? fmt(item.nw, 3) : fmt(item.gw, 3)}</td>
                <td>{item.rate ? fmtInt(item.rate) : ""}</td>
                <td>{metalValue > 0 ? fmtInt(metalValue) : ""}</td>
                <td></td>
                <td>{item.making_value ? fmtInt(item.making_value) : ""}</td>
                <td>0</td>
                <td className="amt">{amount ? fmtInt(amount) : ""}</td>
              </tr>
              {b.subs.map((s, si) => (
                <tr className="sub" key={"s-" + b.idx + "-" + si}>
                  <td className="c"></td>
                  <td className="l" colSpan={4}>↳ {s.sub_item || ""}{s.packet ? " [" + s.packet + "]" : ""}</td>
                  <td>{s.sub_gw ? fmt(s.sub_gw, 3) : ""}</td>
                  <td>{s.sub_ct ? fmt(s.sub_ct, 3) + " ct" : ""}</td>
                  <td>{s.rate ? fmtInt(s.rate) : ""}</td>
                  <td>{!s.sub_ct && s.value ? fmtInt(s.value) : ""}</td>
                  <td>{s.sub_ct && s.value ? fmtInt(s.value) : ""}</td>
                  <td></td>
                  <td></td>
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
    <div className="pv-bottom">
      <div className="pv-left">
        <div className="pv-block">
          <h4>Narration</h4>
          <div className="pv-narr">
            {d.narration || "—"}
          </div>
          <div className="pv-words">
            <b>In words:</b> {numberToWords(netPayable)}
          </div>
        </div>
        {(d.payment_mode || d.due_date) && (
          <div className="pv-block">
            <h4>Payment Details</h4>
            <div className="pv-narr" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span><b>Mode:</b> {d.payment_mode || "—"}</span>
              {d.due_date && (
                <span style={{ fontVariantNumeric: "tabular-nums", color: "var(--ink)", fontWeight: 700 }}>
                  Due {fmtDate(d.due_date)}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="pv-totals">
        <div className="pv-row"><span className="pv-l">Subtotal</span><span className="pv-v">{fmtInt(subtotal)}</span></div>
        {hallmark    ? <div className="pv-row"><span className="pv-l">Hallmark Charges</span><span className="pv-v">{fmtInt(hallmark)}</span></div> : null}
        {freight     ? <div className="pv-row"><span className="pv-l">Freight Charges</span><span className="pv-v">{fmtInt(freight)}</span></div> : null}
        {addChrg1    ? <div className="pv-row"><span className="pv-l">{d.add_chrg_cap1 || "Add. Charge 1"}</span><span className="pv-v">{fmtInt(addChrg1)}</span></div> : null}
        {addChrg2    ? <div className="pv-row"><span className="pv-l">{d.add_chrg_cap2 || "Add. Charge 2"}</span><span className="pv-v">{fmtInt(addChrg2)}</span></div> : null}
        {discount    ? <div className="pv-row neg"><span className="pv-l">Less: Discount</span><span className="pv-v">{fmtInt(discount)}</span></div> : null}
        <div className="pv-row bold"><span className="pv-l">Total Before Tax</span><span className="pv-v">{fmtInt(taxable)}</span></div>
        {cgst ? <div className="pv-row"><span className="pv-l">{"CGST " + fmt(cgstPer, 3) + "%"}</span><span className="pv-v">{fmtInt(cgst)}</span></div> : null}
        {sgst ? <div className="pv-row"><span className="pv-l">{"SGST " + fmt(sgstPer, 3) + "%"}</span><span className="pv-v">{fmtInt(sgst)}</span></div> : null}
        {igst ? <div className="pv-row"><span className="pv-l">{"IGST " + fmt(igstPer, 3) + "%"}</span><span className="pv-v">{fmtInt(igst)}</span></div> : null}
        <div className="pv-row bold"><span className="pv-l">Total After Tax</span><span className="pv-v">{fmtInt(totalAfter)}</span></div>
        {tcs ? <div className="pv-row"><span className="pv-l">{"TCS " + fmt(tcsPer, 3) + "%"}</span><span className="pv-v">{fmtInt(tcs)}</span></div> : null}
        {tds ? <div className="pv-row neg"><span className="pv-l">{"Less: TDS" + (d.tds_section ? " (" + d.tds_section + ")" : "")}</span><span className="pv-v">{fmtInt(tds)}</span></div> : null}
        {roundOff ? <div className="pv-row"><span className="pv-l">Round Off</span><span className="pv-v">{fmtInt(roundOff)}</span></div> : null}
        <div className="pv-row net"><span className="pv-l">Net Payable</span><span className="pv-v">₹ {fmtInt(netPayable)}</span></div>
      </div>
    </div>
  );

  const renderFooter = () => (
    <div className="pv-footer">
      <div className="pv-terms">
        <div>•&nbsp; Goods received in good order &amp; condition. Hallmark verified at receipt.</div>
        <div>•&nbsp; Payment due as per agreed credit terms, subject to vendor's bank realisation.</div>
        <div>•&nbsp; Disputes, if any, to be raised within 48 hours of receipt. Subject to <b>{(d.jurisdiction || "Kolkata").toUpperCase()}</b> jurisdiction only.</div>
      </div>
      <div className="pv-sig-row">
        <div className="pv-sig">
          <div className="pv-for">&nbsp;</div>
          <div className="pv-space"></div>
          <div className="pv-l">Received By / Stores</div>
        </div>
        <div className="pv-sig">
          <div className="pv-for">For {(d.company_legal_name || d.company_name || "").toUpperCase()}</div>
          <div className="pv-space"></div>
          <div className="pv-l">Authorised Signatory</div>
        </div>
      </div>
    </div>
  );

  const renderPageStamp = (pageNum, total) => (
    <div className="pv-stamp">
      <span>This is a computer-generated voucher and does not require a signature</span>
      <span className="pv-pg">PAGE {pageNum} OF {total}</span>
    </div>
  );

  return (
    <div className="pv-root">
      <link rel="stylesheet" href={FONTS_HREF} />
      <style>{PV_CSS}</style>

      {pages.map((pageBlocks, pageIdx) => {
        const isFirst = pageIdx === 0;
        const isLast  = pageIdx === totalPages - 1;
        return (
          <div key={pageIdx} className="pv-page">
            {renderHeader()}
            {renderTitleStrip()}
            {renderParties()}
            {isFirst && metalRates.length > 0 && renderMetalRate()}
            {renderItemsTable(pageBlocks)}
            {isLast && renderBottomSplit()}
            {isLast && renderFooter()}
            {renderPageStamp(pageIdx + 1, totalPages)}
          </div>
        );
      })}
    </div>
  );
};

export default PurchaseVoucherVendor;
