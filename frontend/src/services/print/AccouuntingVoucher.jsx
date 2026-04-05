import React from "react";

// Voucher type → display title mapping
const VOUCHER_TITLES = {
  "RCPT-SALE": "RECEIPT VOUCHER",
  "RCPT":      "RECEIPT VOUCHER",
  "PMNT":      "PAYMENT VOUCHER",
  "PMNT-PURC": "PAYMENT VOUCHER",
  "CONTRA":    "CONTRA VOUCHER",
  "JRNL":      "JOURNAL VOUCHER",
};

// GST/TDS account name patterns – used to exclude these from party detection
const GST_PATTERNS = /cgst|sgst|igst|tcs|tds|gst/i;

const isGstLine   = (line) => GST_PATTERNS.test(line.account || "");
const isRcptType  = (t)    => t === "RCPT-SALE" || t === "RCPT";
const isPmntType  = (t)    => t === "PMNT"      || t === "PMNT-PURC";
const hasPartyRow = (t)    => isRcptType(t) || isPmntType(t);

// Identify the "party" line for RCPT (credit side) and PMNT (debit side)
function detectParty(lines, voucherType) {
  if (isRcptType(voucherType)) {
    return lines.find((l) => (l.credit || 0) > 0 && !isGstLine(l)) || null;
  }
  if (isPmntType(voucherType)) {
    return lines.find((l) => (l.debit || 0) > 0 && !isGstLine(l)) || null;
  }
  return null;
}

// Collect GST-labelled lines that carry amounts
function getGstLines(lines) {
  return lines.filter((l) => isGstLine(l) && ((l.debit || 0) > 0 || (l.credit || 0) > 0));
}

const fmt = (v) =>
  v ? new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v) : "";

const fmtDate = (d) => {
  if (!d) return "";
  const dt = new Date(d);
  return `${String(dt.getDate()).padStart(2, "0")}/${String(dt.getMonth() + 1).padStart(2, "0")}/${dt.getFullYear()}`;
};

// ─────────────────────────────────────────────────────────────
const AccountingVoucher = ({ data = {} }) => {
  const lines        = data.voucher_details || [];
  const voucherType  = (data.voucher_type || "JRNL").trim().toUpperCase();
  const title        = VOUCHER_TITLES[voucherType] || "JOURNAL VOUCHER";
  const party        = detectParty(lines, voucherType);
  const gstLines     = getGstLines(lines);
  const showParty    = hasPartyRow(voucherType);

  // Non-GST lines only go into the main table
  const mainLines = lines.filter((l) => !isGstLine(l));

  // Totals (excluding GST lines from the running total, matching PHP behaviour)
  const rawDr  = mainLines.reduce((s, l) => s + (parseFloat(l.debit)  || 0), 0);
  const rawCr  = mainLines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);
  const gstDr  = gstLines.reduce((s, l) => s + (parseFloat(l.debit)  || 0), 0);
  const gstCr  = gstLines.reduce((s, l) => s + (parseFloat(l.credit) || 0), 0);

  const totalDr = isRcptType(voucherType) ? rawDr          : rawDr  + gstDr;
  const totalCr = isRcptType(voucherType) ? rawCr + gstCr  : rawCr;

  // Bank/cheque rows
  const bankLines = lines.filter((l) => l.chq_no);

  // Inline styles – A5 landscape ─────────────────────────────
  const page = {
    fontFamily:  "Arial, sans-serif",
    fontSize:    "8pt",
    color:       "#000",
    width:       "210mm",
    minHeight:   "148mm",
    margin:      "0 auto",
    padding:     "6mm 6mm 4mm 6mm",
    boxSizing:   "border-box",
    lineHeight:  1.25,
  };
  const bold   = { fontWeight: "bold" };
  const center = { textAlign: "center" };
  const right  = { textAlign: "right" };

  const tbl = { width: "100%", borderCollapse: "collapse" };
  const cell = (extra = {}) => ({
    border:  "1px solid #000",
    padding: "2px 4px",
    verticalAlign: "top",
    ...extra,
  });
  const hdr = (extra = {}) => ({
    ...cell(extra),
    fontWeight: "bold",
    backgroundColor: "#fff",
  });

  return (
    <div style={page}>

      {/* ── COMPANY HEADER ──────────────────────────────────── */}
      <div style={{ ...center, marginBottom: "4px" }}>
        <div style={{ ...bold, fontSize: "13pt" }}>ZORII DIAMONDS PVT. LTD.</div>
        <div>24, Camac Street, 1st Floor, Kolkata-700016</div>
        <div>Phone:-8981584400</div>
      </div>

      {/* ── VOUCHER TITLE ───────────────────────────────────── */}
      <div style={{ ...center, ...bold, fontSize: "9pt", textDecoration: "underline", margin: "4px 0" }}>
        {title}
      </div>

      {/* ── PARTY / VOUCHER-NO BLOCK ────────────────────────── */}
      {showParty ? (
        <table style={{ ...tbl, border: "1px solid #000", marginBottom: "4px" }}>
          <tbody>
            <tr>
              <td style={{ ...cell(), width: "10%" }}><b>Name :</b></td>
              <td style={{ ...cell(), width: "55%" }}>{party?.account || ""}</td>
              <td style={{ ...cell(), width: "15%", ...bold }}>Voucher No. :</td>
              <td style={{ ...cell(), width: "20%" }}>{data.voucher_no || ""}</td>
            </tr>
            <tr>
              <td style={cell()}><b>Address :</b></td>
              <td style={cell()}>{/* address not in API yet */}</td>
              <td style={{ ...cell(), ...bold }}>Voucher Date :</td>
              <td style={cell()}>{fmtDate(data.date)}</td>
            </tr>
            <tr>
              <td style={cell()}><b>GSTIN :</b></td>
              <td style={cell()} colSpan="3">{/* gstin not in API yet */}</td>
            </tr>
          </tbody>
        </table>
      ) : (
        <table style={{ ...tbl, marginBottom: "4px" }}>
          <tbody>
            <tr>
              <td style={{ padding: "1px 0", width: "20%" }}><b>Voucher No :</b></td>
              <td style={{ padding: "1px 0", width: "50%" }}>{data.voucher_no || ""}</td>
              <td style={{ padding: "1px 0", width: "15%", ...bold }}>Voucher Date :</td>
              <td style={{ padding: "1px 0", width: "15%", ...right }}>{fmtDate(data.date)}</td>
            </tr>
          </tbody>
        </table>
      )}

      {/* ── MAIN TABLE ──────────────────────────────────────── */}
      <table style={tbl}>
        <thead>
          <tr>
            <th style={hdr({ width: "6%",  ...center })}>Sl. No.</th>
            <th style={hdr({ width: "64%" })}>Description</th>
            <th style={hdr({ width: "15%", ...right })}>Amount (Dr)</th>
            <th style={hdr({ width: "15%", ...right })}>Amount (Cr)</th>
          </tr>
        </thead>
        <tbody>
          {mainLines.map((line, i) => (
            <tr key={i}>
              <td style={cell({ ...center })}>{i + 1}.</td>
              <td style={cell()}>
                {(line.debit || 0) > 0 ? "By" : "\u00a0\u00a0\u00a0\u00a0To"}&nbsp;&nbsp;
                {line.account || ""}
              </td>
              <td style={cell({ ...right })}>{(line.debit  || 0) > 0 ? fmt(line.debit)  : ""}</td>
              <td style={cell({ ...right })}>{(line.credit || 0) > 0 ? fmt(line.credit) : ""}</td>
            </tr>
          ))}

          {/* Empty filler rows (minimum 2) */}
          {Array.from({ length: Math.max(0, 3 - mainLines.length) }).map((_, i) => (
            <tr key={`empty-${i}`}>
              <td style={cell({ padding: "6px 4px" })}>&nbsp;</td>
              <td style={cell()}></td>
              <td style={cell()}></td>
              <td style={cell()}></td>
            </tr>
          ))}

          {/* ── GST ROWS (RCPT / PMNT only) ─────────────────── */}
          {gstLines.map((g, i) => {
            const amt = isRcptType(voucherType) ? (g.credit || g.debit || 0) : (g.debit || g.credit || 0);
            const base = isRcptType(voucherType) ? rawCr : rawDr;
            const pct  = base > 0 ? Math.round((amt / base) * 1000) / 10 : 0;
            const label = `ADD : ${(g.account || "").toUpperCase().replace("INPUT ", "")} ${pct > 0 ? pct + " %" : ""}`;
            return (
              <tr key={`gst-${i}`}>
                <td style={cell()}></td>
                <td style={cell({ ...right })}>{label}</td>
                <td style={cell({ ...right })}>{!isRcptType(voucherType) && amt > 0 ? fmt(amt) : ""}</td>
                <td style={cell({ ...right })}>{isRcptType(voucherType)  && amt > 0 ? fmt(amt) : ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* ── TOTAL ROW ───────────────────────────────────────── */}
      <table style={{ ...tbl, marginTop: "1px" }}>
        <tbody>
          <tr>
            <td style={{ ...cell({ width: "70%", ...bold, ...right, fontSize: "9pt" })}} colSpan={2}>
              Total :
            </td>
            <td style={cell({ width: "15%", ...right, ...bold, fontSize: "9pt" })}>{totalDr > 0 ? fmt(totalDr) : ""}</td>
            <td style={cell({ width: "15%", ...right, ...bold, fontSize: "9pt" })}>{totalCr > 0 ? fmt(totalCr) : ""}</td>
          </tr>
        </tbody>
      </table>

      {/* ── BANK / CHEQUE DETAILS ───────────────────────────── */}
      {bankLines.length > 0 && (
        <table style={{ ...tbl, marginTop: "3px", border: "1px solid #000" }}>
          <tbody>
            {bankLines.map((b, i) => (
              <tr key={i}>
                <td style={cell({ width: "15%" })}><b>Drawn On :</b></td>
                <td style={cell({ width: "40%" })}>{b.party_bank_name || ""}</td>
                <td style={cell({ width: "20%" })}><b>Chq / Card No.</b> {b.chq_no || ""}</td>
                <td style={cell({ width: "25%" })}><b>Chq. Date :</b> {fmtDate(b.chq_date)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ── NARRATION ───────────────────────────────────────── */}
      {data.narration && (
        <table style={{ ...tbl, marginTop: "3px", border: "1px solid #000" }}>
          <tbody>
            <tr>
              <td style={{ ...cell({ width: "15%" }), ...bold }}>Narration</td>
              <td style={cell({ width: "85%" })}>{data.narration}</td>
            </tr>
          </tbody>
        </table>
      )}

      {/* ── FOOTER ──────────────────────────────────────────── */}
      <div style={{ marginTop: "8px" }}>
        {/* E. & O.E. */}
        <div style={{ ...right, marginBottom: "4px", fontSize: "7pt" }}>E. &amp; O.E.</div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
          {/* Left: PAN / GSTIN / State */}
          <div style={{ fontSize: "7.5pt" }}>
            <div><b>PAN</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;19AACCZ5519L1ZR</div>
            <div><b>GSTIN No.</b>&nbsp;&nbsp;&nbsp;19AACCZ5519L1ZR</div>
            <div><b>STATE</b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;West Bengal</div>
            <div><b>STATE CODE</b>&nbsp;&nbsp;19</div>
          </div>

          {/* Signature blocks */}
          <div style={{ display: "flex", gap: "24px", fontSize: "7.5pt" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ borderTop: "1px solid #000", paddingTop: "2px", marginTop: "24px", minWidth: "80px" }}>
                Party Signature
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ marginBottom: "2px" }}>For</div>
              <div style={{ ...bold, fontSize: "8pt" }}>ZORII DIAMONDS PVT. LTD.</div>
              <div style={{ borderTop: "1px solid #000", paddingTop: "2px", marginTop: "20px", minWidth: "100px" }}>
                Authorised Signatory
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── PRINT STYLES ────────────────────────────────────── */}
      <style>{`
        @media print {
          @page {
            size: A5 landscape;
            margin: 0;
          }
          body { margin: 0; padding: 0; }
        }
      `}</style>
    </div>
  );
};

export default AccountingVoucher;
