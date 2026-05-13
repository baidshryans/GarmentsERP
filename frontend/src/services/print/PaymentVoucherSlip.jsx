// frontend/src/services/print/PaymentVoucherSlip.jsx
/* eslint-disable react/prop-types */
import { fmt, fmtDate, numberToWords, detectParty, detectMode } from "./printHelpers";

const FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap";

const PV_CSS = [
  "@import url('" + FONTS + "');",
  "*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}",
  "body{background:#fff}",

  /* page � A5 landscape */
  ".pv-page{font-family:Inter,Arial,sans-serif;font-size:10px;line-height:1.4;color:#111;width:210mm;min-height:148mm;margin:0 auto;padding:8mm 10mm;background:#fff;display:flex;flex-direction:column}",

  /* company header */
  ".pv-header{text-align:center;padding-bottom:6px;border-bottom:2px solid #111}",
  ".pv-co-name{font-size:14px;font-weight:700;letter-spacing:.3px}",
  ".pv-co-sub{font-size:8.5px;color:#444;margin-top:1px}",

  /* title strip */
  ".pv-title{display:flex;align-items:center;justify-content:space-between;padding:4px 0;background:#f7f7f7;border-top:1px solid #111;border-bottom:1px solid #111}",
  ".pv-title-meta{font-size:8.5px;color:#555;min-width:90px}",
  ".pv-title-meta strong{color:#111;font-weight:700}",
  ".pv-title-center{font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;text-align:center;flex:1}",
  ".pv-title-right{text-align:right}",

  /* paid-to + amount row */
  ".pv-party-row{display:flex;align-items:stretch;border-bottom:1px solid #111}",
  ".pv-party{flex:1;padding:7px 10px 7px 0;border-right:1px solid #111}",
  ".pv-lbl{font-size:7.5px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;color:#666;margin-bottom:2px}",
  ".pv-party-name{font-size:13px;font-weight:700;word-break:break-word}",
  ".pv-party-ref{font-size:8px;color:#666;margin-top:2px}",
  ".pv-amount-block{min-width:130px;padding:7px 0 7px 10px;display:flex;flex-direction:column;align-items:flex-end;justify-content:center}",
  ".pv-amount-fig{font-size:20px;font-weight:800;letter-spacing:-.5px;font-variant-numeric:tabular-nums;line-height:1}",
  ".pv-amount-words{font-size:7px;color:#555;margin-top:3px;text-align:right;max-width:130px;line-height:1.3}",

  /* payment details strip */
  ".pv-details{display:flex;border-bottom:1px solid #111}",
  ".pv-det-cell{flex:1;padding:5px 8px 5px 0;border-right:1px solid #ddd}",
  ".pv-det-cell:last-child{border-right:none;padding-right:0}",
  ".pv-det-val{font-size:10px;font-weight:600;color:#111;margin-top:2px}",
  ".pv-mode-badge{display:inline-flex;align-items:center;padding:1px 8px;border:1px solid #999;border-radius:2px;font-size:9px;font-weight:700;letter-spacing:.3px;margin-top:2px}",

  /* narration */
  ".pv-narr{padding:5px 0;border-bottom:1px solid #111;font-size:9px;color:#444}",
  ".pv-narr strong{color:#111;font-weight:700}",

  /* footer */
  ".pv-footer{display:flex;align-items:flex-end;justify-content:space-between;padding-top:6px;flex:1}",
  ".pv-footer-left{font-size:8px;color:#555;line-height:1.7}",
  ".pv-footer-left strong{color:#111}",
  ".pv-sigs{display:flex;gap:32px;align-items:flex-end}",
  ".pv-sig-block{text-align:center;font-size:8.5px}",
  ".pv-sig-line{border-top:1px solid #111;margin-top:32px;padding-top:3px;font-weight:600;min-width:110px}",
  ".pv-eooe{font-size:7.5px;color:#999;margin-top:4px}",

  "@media print{@page{size:A5 landscape;margin:0}body{margin:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}.pv-page{padding:8mm 10mm}}",
].join("\n");

const PaymentVoucherSlip = ({ data = {} }) => {
  const d        = data;
  const lines    = d.voucher_details || [];
  const party    = detectParty(lines, "PMNT");
  const mode     = detectMode(lines, "PMNT");
  const bankLine = lines.find((l) => l.chq_no);
  const totalAmt = lines.reduce((s, l) => s + (parseFloat(l.debit) || 0), 0);

  return (
    <div className="pv-page">
      <style>{PV_CSS}</style>

      {/* ── Company header ── */}
      <div className="pv-header">
        <div className="pv-co-name">{d.company_legal_name || d.company_name || "JEWEL INDIA"}</div>
        {d.company_address && (
          <div className="pv-co-sub">{d.company_address}</div>
        )}
        {(d.company_phone || d.company_email) && (
          <div className="pv-co-sub">
            {d.company_phone && "Tel: " + d.company_phone}
            {d.company_phone && d.company_email && "  �  "}
            {d.company_email}
          </div>
        )}
      </div>

      {/* ── Title strip ── */}
      <div className="pv-title">
        <div className="pv-title-meta">
          Vou. No.&nbsp;<strong>{d.voucher_no || "�"}</strong>
        </div>
        <div className="pv-title-center">Payment Voucher</div>
        <div className="pv-title-meta pv-title-right">
          <div>Date:&nbsp;<strong>{fmtDate(d.date)}</strong></div>
          <div style={{ fontSize: "7.5px", color: "#888", marginTop: "1px" }}>
            Original / Duplicate
          </div>
        </div>
      </div>

      {/* ── Paid To + Amount ── */}
      <div className="pv-party-row">
        <div className="pv-party">
          <div className="pv-lbl">Paid To</div>
          <div className="pv-party-name">{party?.account || "�"}</div>
          {party?.ref_bill_no && (
            <div className="pv-party-ref">Ref: {party.ref_bill_no}</div>
          )}
        </div>
        <div className="pv-amount-block">
          <div className="pv-lbl" style={{ textAlign: "right" }}>Amount</div>
          <div className="pv-amount-fig">₹&nbsp;{fmt(totalAmt) || "0.00"}</div>
          <div className="pv-amount-words">{numberToWords(totalAmt)}</div>
        </div>
      </div>

      {/* ── Payment details strip ── */}
      <div className="pv-details">
        <div className="pv-det-cell">
          <div className="pv-lbl">Mode</div>
          <div className="pv-mode-badge">{mode?.label || "�"}</div>
        </div>
        <div className="pv-det-cell">
          <div className="pv-lbl">Bank / Account</div>
          <div className="pv-det-val">{mode?.account || "�"}</div>
        </div>
        <div className="pv-det-cell">
          <div className="pv-lbl">Cheque / Ref. No.</div>
          <div className="pv-det-val">{bankLine?.chq_no || "�"}</div>
        </div>
        <div className="pv-det-cell">
          <div className="pv-lbl">Instrument Date</div>
          <div className="pv-det-val">{fmtDate(bankLine?.chq_date) || "�"}</div>
        </div>
      </div>

      {/* ── Narration (hidden when empty) ── */}
      {d.narration && (
        <div className="pv-narr">
          <strong>Narration:</strong>&nbsp;{d.narration}
        </div>
      )}

      {/* ── Footer ── */}
      <div className="pv-footer">
        <div className="pv-footer-left">
          {d.company_pan   && <div><strong>PAN:</strong>&nbsp;{d.company_pan}</div>}
          {d.company_gstin && <div><strong>GSTIN:</strong>&nbsp;{d.company_gstin}</div>}
          <div className="pv-eooe">E. &amp; O.E.</div>
        </div>
        <div className="pv-sigs">
          <div className="pv-sig-block">
            <div className="pv-sig-line">Authorised By (Party)</div>
          </div>
          <div className="pv-sig-block">
            <div style={{ fontSize: "8px", fontWeight: 600, marginBottom: 2 }}>
              for {d.company_legal_name || d.company_name || "JEWEL INDIA"}
            </div>
            <div className="pv-sig-line">Authorised Signatory</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PaymentVoucherSlip;

