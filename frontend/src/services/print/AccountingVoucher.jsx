import React from "react";
import { fmt, fmtDate, numberToWords, isGst, isRcpt, isPmnt, detectParty, detectMode } from "./printHelpers";
import { formatMoney } from "@/lib/format";

/* ─── voucher type helpers ────────────────────────────────────────────────── */

const VOUCHER_TITLES = {
  "RCPT-SALE": "Receipt Voucher",
  "RCPT":      "Receipt Voucher",
  "PMNT":      "Payment Voucher",
  "PMNT-PURC": "Payment Voucher",
  "CONTRA":    "Contra Voucher",
  "JRNL":      "Journal Voucher",
};

/* ─── CSS ─────────────────────────────────────────────────────────────────── */

const FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap";

const AV_CSS = [
  "@import url('" + FONTS + "');",
  "*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}",
  "body{background:#fff}",

  /* page */
  ".av-page{font-family:Inter,Arial,sans-serif;font-size:10.5px;line-height:1.4;color:#111;width:210mm;min-height:297mm;margin:0 auto;padding:10mm 12mm;background:#fff}",

  /* company header */
  ".av-header{text-align:center;padding-bottom:6px;margin-bottom:0;border-bottom:2px solid #111}",
  ".av-co-name{font-size:14px;font-weight:700;letter-spacing:.3px}",
  ".av-co-sub{font-size:9.5px;color:#444;margin-top:2px}",
  ".av-co-gstin{font-size:9.5px;font-weight:600;margin-top:1px}",

  /* title strip */
  ".av-title{display:flex;align-items:center;justify-content:space-between;padding:5px 8px;background:#f7f7f7;border:1px solid #111;border-top:none;margin-bottom:0}",
  ".av-title-text{font-size:13px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;flex:1;text-align:center}",
  ".av-title-side{font-size:9px;color:#666;white-space:nowrap;min-width:110px}",
  ".av-title-right{text-align:right}",

  /* info strip */
  ".av-info{display:grid;grid-template-columns:1fr 1fr;border:1px solid #111;border-top:none;margin-bottom:0}",
  ".av-info-cell{padding:5px 8px;border-right:1px solid #ddd}",
  ".av-info-cell:last-child{border-right:none}",
  ".av-info-cell:nth-child(2n-1){border-right:1px solid #ddd}",
  ".av-info-lbl{font-size:8.5px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:#666;margin-bottom:1px}",
  ".av-info-val{font-size:11px;font-weight:600;color:#111}",

  /* party strip (RCPT/PMNT only) */
  ".av-party-strip{display:grid;grid-template-columns:1fr auto;border:1px solid #111;border-top:none;padding:5px 8px;gap:8px}",
  ".av-party-lbl{font-size:8.5px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;color:#666;margin-bottom:1px}",
  ".av-party-val{font-size:11px;font-weight:600}",
  ".av-mode-badge{display:inline-flex;align-items:center;padding:2px 10px;border:1px solid #bbb;border-radius:3px;font-size:9.5px;font-weight:600;color:#333;white-space:nowrap;align-self:center}",

  /* cheque strip */
  ".av-chq-strip{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #111;border-top:none}",
  ".av-chq-cell{padding:4px 8px;border-right:1px solid #ddd}",
  ".av-chq-cell:last-child{border-right:none}",
  ".av-chq-lbl{font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;color:#777;margin-bottom:1px}",
  ".av-chq-val{font-size:10px;font-weight:600}",

  /* entries table */
  ".av-tbl-wrap{border:1px solid #111;border-top:none;margin-bottom:0}",
  ".av-tbl{width:100%;border-collapse:collapse;table-layout:fixed}",
  ".av-tbl th{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.3px;padding:4px 6px;border-bottom:1.5px solid #111;border-right:1px solid #ccc;background:#fafafa}",
  ".av-tbl th:last-child{border-right:none}",
  ".av-tbl td{padding:3px 6px;border-bottom:1px solid #eee;border-right:1px solid #eee;vertical-align:middle}",
  ".av-tbl td:last-child{border-right:none}",
  ".av-tbl .av-pad-row td{padding:7px 6px;border-bottom:1px solid #eee}",
  ".av-num{text-align:right;font-variant-numeric:tabular-nums;font-size:10.5px}",
  ".av-ctr{text-align:center;color:#777;font-size:10px}",
  ".av-dr td{font-weight:500;font-size:10.5px}",
  ".av-cr td{font-size:10.5px;color:#222}",
  ".av-gst td{font-size:9.5px;color:#555}",

  /* total row */
  ".av-total-row{border:1px solid #111;border-top:none}",
  ".av-total-row td{padding:5px 6px;font-size:11px;font-weight:700;font-variant-numeric:tabular-nums;border-right:1px solid #ddd}",
  ".av-total-row td:last-child{border-right:none}",
  ".av-total-lbl{text-align:right}",
  ".av-total-num{text-align:right;width:20%}",

  /* words / narration */
  ".av-words{border:1px solid #111;border-top:none;padding:5px 8px;font-size:10px;line-height:1.5}",
  ".av-narr{border:1px solid #111;border-top:none;padding:5px 8px;font-size:10px;line-height:1.5}",

  /* footer */
  ".av-footer{border:1px solid #111;border-top:none;padding:8px 10px;display:flex;justify-content:space-between;align-items:flex-end;margin-top:0}",
  ".av-footer-left{font-size:9.5px;line-height:1.7;color:#444}",
  ".av-sigs{display:flex;gap:40px;align-items:flex-end}",
  ".av-sig-block{text-align:center;font-size:9.5px}",
  ".av-sig-line{border-top:1px solid #111;margin-top:40px;padding-top:3px;font-weight:600;min-width:130px}",

  "@media print{@page{size:A4;margin:0}body{margin:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}.av-page{padding:10mm 12mm}}"
].join("\n");

/* ─── component ───────────────────────────────────────────────────────────── */

const AccountingVoucher = ({ data = {} }) => {
  const d           = data;
  const lines       = d.voucher_details || [];
  const vType       = (d.voucher_type || "JRNL").trim().toUpperCase();
  const title       = VOUCHER_TITLES[vType] || "Journal Voucher";
  const showParty   = isRcpt(vType) || isPmnt(vType);
  const partyLabel  = isRcpt(vType) ? "Received From" : "Paid To";

  const party     = detectParty(lines, vType);
  const mode      = showParty ? detectMode(lines, vType) : null;
  const gstLines  = lines.filter((l) => isGst(l) && ((l.debit || 0) > 0 || (l.credit || 0) > 0));
  const mainLines = lines.filter((l) => !isGst(l));

  const rawDr = mainLines.reduce((s, l) => s + (parseFloat(l.debit)  || 0), 0);
  const rawCr = mainLines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
  const gstDr = gstLines.reduce ((s, l) => s + (parseFloat(l.debit)  || 0), 0);
  const gstCr = gstLines.reduce ((s, l) => s + (parseFloat(l.credit) || 0), 0);
  const totalDr = isRcpt(vType) ? rawDr          : rawDr + gstDr;
  const totalCr = isRcpt(vType) ? rawCr + gstCr  : rawCr;
  const netAmt  = Math.max(totalDr, totalCr);

  const bankLines = lines.filter((l) => l.chq_no);
  const padCount  = Math.max(0, 5 - mainLines.length - gstLines.length);

  return (
    <div className="av-page">
      <style>{AV_CSS}</style>

      {/* ── Company header ── */}
      <div className="av-header">
        {d.company_logo_url && (
          <img src={d.company_logo_url} alt="" style={{height:40,marginBottom:4,objectFit:"contain"}} />
        )}
        <div className="av-co-name">{d.company_legal_name || d.company_name || "JEWEL INDIA"}</div>
        {d.company_address && <div className="av-co-sub">{d.company_address}</div>}
        {(d.company_phone || d.company_email) && (
          <div className="av-co-sub">
            {d.company_phone && "Tel: " + d.company_phone}
            {d.company_phone && d.company_email && "  ·  "}
            {d.company_email}
          </div>
        )}
        {d.company_gstin && <div className="av-co-gstin">GSTIN: {d.company_gstin}</div>}
      </div>

      {/* ── Title strip ── */}
      <div className="av-title">
        <span className="av-title-side">&nbsp;</span>
        <span className="av-title-text">{title}</span>
        <span className="av-title-side av-title-right">Original / Duplicate</span>
      </div>

      {/* ── Voucher no + date ── */}
      <div className="av-info">
        <div className="av-info-cell">
          <div className="av-info-lbl">Voucher No.</div>
          <div className="av-info-val">{d.voucher_no || "—"}</div>
        </div>
        <div className="av-info-cell">
          <div className="av-info-lbl">Date</div>
          <div className="av-info-val">{fmtDate(d.date)}</div>
        </div>
      </div>

      {/* ── Party strip (PMNT / RCPT only) ── */}
      {showParty && party && (
        <div className="av-party-strip">
          <div>
            <div className="av-party-lbl">{partyLabel}</div>
            <div className="av-party-val">
              {party.account || ""}
              {party.ref_bill_no && (
                <span style={{fontWeight:400,fontSize:"9.5px",color:"#555",marginLeft:8}}>
                  Ref: {party.ref_bill_no}
                </span>
              )}
            </div>
          </div>
          {mode && (
            <div style={{textAlign:"right"}}>
              <div className="av-party-lbl">Mode</div>
              <span className="av-mode-badge">{mode.label}: {mode.account}</span>
            </div>
          )}
        </div>
      )}

      {/* ── Cheque details ── */}
      {bankLines.length > 0 && (
        <div className="av-chq-strip">
          {bankLines.map((b, i) => (
            <React.Fragment key={i}>
              <div className="av-chq-cell">
                <div className="av-chq-lbl">Drawn On</div>
                <div className="av-chq-val">{b.party_bank_name || "—"}</div>
              </div>
              <div className="av-chq-cell">
                <div className="av-chq-lbl">Cheque / Card No.</div>
                <div className="av-chq-val">{b.chq_no || "—"}</div>
              </div>
              <div className="av-chq-cell">
                <div className="av-chq-lbl">Cheque Date</div>
                <div className="av-chq-val">{fmtDate(b.chq_date) || "—"}</div>
              </div>
              <div className="av-chq-cell">
                <div className="av-chq-lbl">Account</div>
                <div className="av-chq-val">{b.account || "—"}</div>
              </div>
            </React.Fragment>
          ))}
        </div>
      )}

      {/* ── Entries table ── */}
      <div className="av-tbl-wrap">
        <table className="av-tbl">
          <colgroup>
            <col style={{width:"5%"}} />
            <col style={{width:"55%"}} />
            <col style={{width:"20%"}} />
            <col style={{width:"20%"}} />
          </colgroup>
          <thead>
            <tr>
              <th style={{textAlign:"center"}}>Sl.</th>
              <th style={{textAlign:"left"}}>Particulars</th>
              <th style={{textAlign:"right"}}>Debit (₹)</th>
              <th style={{textAlign:"right"}}>Credit (₹)</th>
            </tr>
          </thead>
          <tbody>

            {mainLines.map((line, i) => {
              const isDr = (parseFloat(line.debit) || 0) > 0;
              return (
                <tr key={i} className={isDr ? "av-dr" : "av-cr"}>
                  <td className="av-ctr">{i + 1}</td>
                  <td>
                    {isDr
                      ? <><span style={{fontWeight:700,letterSpacing:".2px"}}>Dr&nbsp;</span>{line.account || ""}</>
                      : <span style={{paddingLeft:20}}><span style={{fontWeight:700,letterSpacing:".2px"}}>Cr&nbsp;</span>{line.account || ""}</span>
                    }
                  </td>
                  <td className="av-num">{isDr ? fmt(line.debit) : ""}</td>
                  <td className="av-num">{!isDr ? fmt(line.credit) : ""}</td>
                </tr>
              );
            })}

            {gstLines.map((g, i) => {
              const amt  = isRcpt(vType) ? (g.credit || g.debit || 0) : (g.debit || g.credit || 0);
              const base = isRcpt(vType) ? rawCr : rawDr;
              const pct  = base > 0 ? Math.round((amt / base) * 1000) / 10 : 0;
              const label = (g.account || "").replace(/^input\s*/i, "") + (pct > 0 ? " @ " + pct + "%" : "");
              return (
                <tr key={"g" + i} className="av-gst">
                  <td></td>
                  <td style={{paddingLeft:28,fontStyle:"italic"}}>{label}</td>
                  <td className="av-num">{!isRcpt(vType) && amt > 0 ? fmt(amt) : ""}</td>
                  <td className="av-num">{ isRcpt(vType) && amt > 0 ? fmt(amt) : ""}</td>
                </tr>
              );
            })}

            {Array.from({length: padCount}).map((_, i) => (
              <tr key={"p"+i} className="av-pad-row">
                <td></td><td></td><td></td><td></td>
              </tr>
            ))}

          </tbody>
        </table>
      </div>

      {/* ── Total row ── */}
      <div className="av-total-row" style={{display:"grid",gridTemplateColumns:"60% 20% 20%"}}>
        <div className="av-total-lbl" style={{padding:"5px 8px",fontWeight:700,textAlign:"right",borderRight:"1px solid #ddd",fontSize:11}}>
          Total
        </div>
        <div className="av-total-num" style={{padding:"5px 8px",borderRight:"1px solid #ddd",textAlign:"right",fontWeight:700,fontSize:11,fontVariantNumeric:"tabular-nums"}}>
          {totalDr > 0 ? formatMoney(totalDr, { decimals: 2 }) : ""}
        </div>
        <div className="av-total-num" style={{padding:"5px 8px",textAlign:"right",fontWeight:700,fontSize:11,fontVariantNumeric:"tabular-nums"}}>
          {totalCr > 0 ? formatMoney(totalCr, { decimals: 2 }) : ""}
        </div>
      </div>

      {/* ── Amount in words ── */}
      {netAmt > 0 && (
        <div className="av-words">
          <span style={{fontWeight:700}}>Amount in Words:&nbsp;</span>
          {numberToWords(netAmt)}
        </div>
      )}

      {/* ── Narration ── */}
      {d.narration && (
        <div className="av-narr">
          <span style={{fontWeight:700}}>Narration:&nbsp;</span>{d.narration}
        </div>
      )}

      {/* ── Footer ── */}
      <div className="av-footer">
        <div className="av-footer-left">
          {d.company_pan   && <div><strong>PAN:</strong>&nbsp;{d.company_pan}</div>}
          {d.company_gstin && <div><strong>GSTIN:</strong>&nbsp;{d.company_gstin}</div>}
          {d.company_tan   && <div><strong>TAN:</strong>&nbsp;{d.company_tan}</div>}
          <div style={{marginTop:3,color:"#888",fontSize:"9px"}}>E. &amp; O.E.</div>
        </div>

        <div className="av-sigs">
          {showParty && (
            <div className="av-sig-block">
              <div className="av-sig-line">
                {isRcpt(vType) ? "Received By" : "Authorised By"} (Party)
              </div>
            </div>
          )}
          <div className="av-sig-block">
            <div style={{fontSize:"9.5px",fontWeight:600,marginBottom:2}}>
              for {d.company_legal_name || d.company_name || "JEWEL INDIA"}
            </div>
            <div className="av-sig-line">Authorised Signatory</div>
          </div>
        </div>
      </div>

    </div>
  );
};

export default AccountingVoucher;

