import React from "react";

// ─── Formatters ───────────────────────────────────────────────────────────────

const fmtDate = (d) => {
  if (!d) return "—";
  const dt = new Date(d);
  if (isNaN(dt)) return d;
  return dt.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
};

const fmtN = (v, decimals = 3) => {
  const n = parseFloat(v);
  return isNaN(n) || n === 0 ? "" : n.toFixed(decimals);
};

const fmtAmt = (v) => {
  const n = parseFloat(v);
  if (isNaN(n)) return "";
  return "₹ " + n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const NATURE_LABELS = {
  new_booking: "New Booking",
  repair: "Repair",
  sample: "Sample",
  to_be_altered: "To Be Altered",
  valuation: "Valuation",
  melting: "Melting",
};

// ─── Style constants ──────────────────────────────────────────────────────────

const FONT = "'Arial', 'Helvetica', sans-serif";
const BORDER = "1px solid #222";
const BORDER_LIGHT = "1px solid #aaa";
const BORDER_DASHED = "1px dashed #bbb";

const S = {
  page: {
    fontFamily: FONT,
    fontSize: 11,
    color: "#111",
    background: "#fff",
    width: "210mm",
    minHeight: "297mm",
    margin: "0 auto",
    padding: "10mm 12mm",
    boxSizing: "border-box",
  },

  // Header
  shopName: {
    fontSize: 20,
    fontWeight: 700,
    letterSpacing: 2,
    textAlign: "center",
    textTransform: "uppercase",
  },
  shopSub: {
    fontSize: 10,
    textAlign: "center",
    color: "#555",
    marginTop: 2,
  },
  dividerThick: {
    borderTop: "2.5px solid #111",
    margin: "6px 0 2px",
  },
  dividerThin: {
    borderTop: BORDER_LIGHT,
    margin: "2px 0 6px",
  },
  title: {
    fontSize: 13,
    fontWeight: 700,
    textAlign: "center",
    letterSpacing: 4,
    textTransform: "uppercase",
    padding: "4px 0",
    borderTop: BORDER,
    borderBottom: BORDER,
    background: "#f4f4f4",
    margin: "6px 0",
  },

  // Info grid
  infoTable: {
    width: "100%",
    borderCollapse: "collapse",
    border: BORDER,
    marginBottom: 8,
  },
  infoCell: {
    padding: "4px 8px",
    verticalAlign: "top",
    fontSize: 11,
    border: BORDER_LIGHT,
  },
  infoLabel: {
    fontWeight: 700,
    fontSize: 10,
    color: "#444",
    whiteSpace: "nowrap",
    paddingRight: 4,
    display: "inline-block",
    minWidth: 70,
  },
  infoValue: {
    fontSize: 11,
  },

  // Items table
  itemTable: {
    width: "100%",
    borderCollapse: "collapse",
    border: BORDER,
    marginBottom: 8,
  },
  th: {
    background: "#eee",
    fontWeight: 700,
    fontSize: 10,
    textAlign: "center",
    padding: "4px 5px",
    border: BORDER,
    whiteSpace: "nowrap",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  td: {
    fontSize: 10.5,
    padding: "5px 5px",
    border: BORDER_LIGHT,
    verticalAlign: "top",
  },
  tdRight: {
    fontSize: 10.5,
    padding: "5px 5px",
    border: BORDER_LIGHT,
    verticalAlign: "top",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
  emptyRow: {
    height: 22,
    border: BORDER_LIGHT,
  },

  // Footer rows
  footerTable: {
    width: "100%",
    borderCollapse: "collapse",
    border: BORDER,
    marginTop: 6,
  },
  footerCell: {
    padding: "6px 10px",
    border: BORDER_LIGHT,
    fontSize: 10.5,
    verticalAlign: "top",
  },
  signCell: {
    padding: "28px 10px 6px",
    border: BORDER_LIGHT,
    fontSize: 10,
    verticalAlign: "bottom",
    textAlign: "center",
    color: "#444",
  },

  note: {
    fontSize: 9,
    color: "#666",
    textAlign: "center",
    marginTop: 6,
    fontStyle: "italic",
  },
};

// ─── InfoRow helper ───────────────────────────────────────────────────────────

const InfoRow = ({ label, value }) => (
  <div style={{ marginBottom: 3 }}>
    <span style={S.infoLabel}>{label}</span>
    <span style={S.infoValue}>{value || "—"}</span>
  </div>
);

// ─── Print Component ──────────────────────────────────────────────────────────

const CustomerOrderPrint = ({ data }) => {
  // Guarantee items is an array
  const items = Array.isArray(data.items) ? data.items : [];

  // Empty filler rows so the table always has at least 8 lines
  const MIN_ROWS = 8;
  const fillerCount = Math.max(0, MIN_ROWS - items.length);

  const goldRateFixed = data.fix_gold_rate && (data.rate_14kt || data.rate_18kt || data.rate_22kt);

  return (
    <div style={S.page}>

      {/* ── Shop letterhead ────────────────────────────────────────────── */}
      <div style={S.shopName}>{data.retail_name || "JEWEL INDIA"}</div>
      {(data.retail_city || data.retail_phone) && (
        <div style={S.shopSub}>
          {[data.retail_city, data.retail_phone ? `Ph: ${data.retail_phone}` : ""]
            .filter(Boolean).join("  |  ")}
        </div>
      )}
      <div style={S.dividerThick} />
      <div style={S.dividerThin} />

      {/* ── Document title ─────────────────────────────────────────────── */}
      <div style={S.title}>ORDER MEMO</div>

      {/* ── Customer & Order info ──────────────────────────────────────── */}
      <table style={S.infoTable}>
        <tbody>
          <tr>
            {/* Left: customer */}
            <td style={{ ...S.infoCell, width: "52%" }}>
              <InfoRow label="Customer"   value={data.ldgr_code_name} />
              <InfoRow label="Phone"      value={data.ldgr_mobile} />
            </td>
            {/* Right: order meta */}
            <td style={S.infoCell}>
              <InfoRow label="Order No."  value={data.order_no} />
              <InfoRow label="Date"       value={fmtDate(data.date1)} />
              <InfoRow label="Del. Date"  value={fmtDate(data.delivery_date)} />
              <InfoRow label="Nature"     value={NATURE_LABELS[data.nature] || data.nature} />
            </td>
          </tr>
        </tbody>
      </table>

      {/* ── Items table ────────────────────────────────────────────────── */}
      <table style={S.itemTable}>
        <thead>
          <tr>
            <th style={{ ...S.th, width: 28 }}>Sl.</th>
            <th style={{ ...S.th, width: 60 }}>Item Code</th>
            <th style={{ ...S.th }}>Description</th>
            <th style={{ ...S.th, width: 44 }}>Purity</th>
            <th style={{ ...S.th, width: 34 }}>Pcs</th>
            <th style={{ ...S.th, width: 50 }}>GW (g)</th>
            <th style={{ ...S.th, width: 56 }}>Making</th>
            <th style={{ ...S.th, width: 42 }}>Size</th>
            <th style={{ ...S.th }}>Remarks</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row, i) => (
            <tr key={i}>
              <td style={{ ...S.td, textAlign: "center" }}>{i + 1}</td>
              <td style={{ ...S.td, fontWeight: 600 }}>{row.item_id}</td>
              <td style={S.td}>{row.item_name || ""}</td>
              <td style={{ ...S.td, textAlign: "center" }}>{row.purity || ""}</td>
              <td style={{ ...S.tdRight }}>{row.pcs || ""}</td>
              <td style={{ ...S.tdRight }}>{fmtN(row.gw)}</td>
              <td style={{ ...S.tdRight }}>
                {row.making_amt
                  ? `${fmtN(row.making_amt, 2)}${row.making_type === "per_nw" ? "%" : ""}`
                  : ""}
              </td>
              <td style={{ ...S.td, textAlign: "center" }}>{row.size || ""}</td>
              <td style={S.td}>{row.remarks || ""}</td>
            </tr>
          ))}

          {/* Filler blank rows */}
          {Array.from({ length: fillerCount }).map((_, i) => (
            <tr key={`filler-${i}`}>
              <td style={S.emptyRow} colSpan={9}>&nbsp;</td>
            </tr>
          ))}

          {/* Totals row */}
          {items.length > 0 && (
            <tr style={{ background: "#f7f7f7" }}>
              <td colSpan={4} style={{ ...S.td, fontWeight: 700, textAlign: "right",
                fontSize: 10, color: "#444", letterSpacing: 0.5 }}>
                TOTAL
              </td>
              <td style={{ ...S.tdRight, fontWeight: 700 }}>
                {items.reduce((s, r) => s + (parseInt(r.pcs) || 0), 0) || ""}
              </td>
              <td style={{ ...S.tdRight, fontWeight: 700 }}>
                {fmtN(items.reduce((s, r) => s + (parseFloat(r.gw) || 0), 0))}
              </td>
              <td colSpan={3} style={S.td} />
            </tr>
          )}
        </tbody>
      </table>

      {/* ── Gold rate block (only when fixed) ─────────────────────────── */}
      {goldRateFixed && (
        <table style={{ ...S.itemTable, marginBottom: 8 }}>
          <tbody>
            <tr>
              <td style={{ ...S.infoCell, fontWeight: 700, fontSize: 10,
                letterSpacing: 0.5, textTransform: "uppercase", width: 130 }}>
                Fixed Gold Rate
              </td>
              {data.rate_14kt ? (
                <td style={S.infoCell}>
                  <span style={S.infoLabel}>14K</span>
                  <span>₹ {Number(data.rate_14kt).toLocaleString("en-IN")}/g</span>
                </td>
              ) : null}
              {data.rate_18kt ? (
                <td style={S.infoCell}>
                  <span style={S.infoLabel}>18K</span>
                  <span>₹ {Number(data.rate_18kt).toLocaleString("en-IN")}/g</span>
                </td>
              ) : null}
              {data.rate_22kt ? (
                <td style={S.infoCell}>
                  <span style={S.infoLabel}>22K</span>
                  <span>₹ {Number(data.rate_22kt).toLocaleString("en-IN")}/g</span>
                </td>
              ) : null}
              {data.gold_rate_date && (
                <td style={S.infoCell}>
                  <span style={S.infoLabel}>Rate Date</span>
                  <span>{fmtDate(data.gold_rate_date)}</span>
                </td>
              )}
            </tr>
          </tbody>
        </table>
      )}

      {/* ── Remarks ────────────────────────────────────────────────────── */}
      {data.remarks && (
        <table style={{ ...S.itemTable, marginBottom: 8 }}>
          <tbody>
            <tr>
              <td style={{ ...S.infoCell, fontWeight: 700, fontSize: 10,
                letterSpacing: 0.5, textTransform: "uppercase", width: 80 }}>
                Remarks
              </td>
              <td style={S.infoCell}>{data.remarks}</td>
            </tr>
          </tbody>
        </table>
      )}

      {/* ── Salesperson & estimated amount ─────────────────────────────── */}
      <table style={S.footerTable}>
        <tbody>
          <tr>
            <td style={{ ...S.footerCell, width: "60%" }}>
              <span style={{ fontWeight: 700, fontSize: 10, textTransform: "uppercase",
                letterSpacing: 0.5 }}>Salesperson: </span>
              {[data.salesman_1_name, data.salesman_2_name].filter(Boolean).join(" / ") || "—"}
            </td>
            <td style={S.footerCell}>
              <span style={{ fontWeight: 700, fontSize: 10, textTransform: "uppercase",
                letterSpacing: 0.5 }}>Est. Amount: </span>
              {fmtAmt(data.est_amount) || "—"}
            </td>
          </tr>
        </tbody>
      </table>

      {/* ── Signature row ──────────────────────────────────────────────── */}
      <table style={{ ...S.footerTable, marginTop: 10 }}>
        <tbody>
          <tr>
            <td style={{ ...S.footerCell, fontSize: 10, color: "#555" }}>
              E. &amp; O.E.
            </td>
            <td style={{ ...S.signCell, width: "34%" }}>
              ___________________________
              <div style={{ marginTop: 4, fontWeight: 600 }}>Customer Signature</div>
            </td>
            <td style={{ ...S.signCell, width: "34%" }}>
              ___________________________
              <div style={{ marginTop: 4, fontWeight: 600 }}>
                For {data.retail_name || "___________"}
              </div>
            </td>
          </tr>
        </tbody>
      </table>

      {/* ── Footer note ────────────────────────────────────────────────── */}
      <div style={S.note}>
        * GST and other taxes as applicable. This is a computer-generated order memo.
      </div>

      {/* ── Print-only CSS injected via style tag ──────────────────────── */}
      <style>{`
        @page { size: A4 portrait; margin: 0; }
        @media print {
          body { margin: 0; }
          * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
        }
      `}</style>
    </div>
  );
};

export default CustomerOrderPrint;
