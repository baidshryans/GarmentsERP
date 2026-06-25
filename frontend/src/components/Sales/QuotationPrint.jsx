import React from "react";
import { formatNumber, formatDate } from "@/lib/format";

const fmtN = (v, d = 3) => {
  const n = parseFloat(v);
  return isNaN(n) || n === 0 ? "" : n.toFixed(d);
};
const fmtI = (v) => {
  const n = parseInt(v);
  return isNaN(n) || n === 0 ? "" : formatNumber(n);
};

// ── Cell primitives ──────────────────────────────────────────────────────────

const TH = ({ children, colSpan, rowSpan, style, width }) => (
  <th
    colSpan={colSpan}
    rowSpan={rowSpan}
    style={{
      border: "1px solid #333",
      padding: "3px 5px",
      textAlign: "center",
      fontSize: 10,
      fontWeight: 700,
      background: "#f0f0f0",
      whiteSpace: "nowrap",
      width,
      ...style,
    }}
  >
    {children}
  </th>
);

const TD = ({ children, right, bold, colSpan, rowSpan, style }) => (
  <td
    colSpan={colSpan}
    rowSpan={rowSpan}
    style={{
      border: "1px solid #888",
      padding: "3px 5px",
      textAlign: right ? "right" : "center",
      fontSize: 10,
      fontWeight: bold ? 700 : 400,
      verticalAlign: "top",
      ...style,
    }}
  >
    {children}
  </td>
);

// ── Sub-row for stone/diamond detail ─────────────────────────────────────────

const DetailSubRow = ({ det }) => (
  <tr>
    {/* Empty cells for Sr, Design, Item No, Product */}
    <td style={subCell}></td>
    <td style={subCell}></td>
    <td style={subCell}></td>
    <td style={subCell}></td>
    {/* Gold columns empty */}
    <td style={subCell}></td>
    <td style={subCell}></td>
    <td style={subCell}></td>
    <td style={subCell}></td>
    <td style={subCell}></td>
    {/* Quality/Size — show packet name */}
    <td style={{ ...subCell, textAlign: "left", paddingLeft: 8, fontStyle: "italic" }}>
      {det.packet_name}
    </td>
    {/* Diamond columns — only if is_diamond */}
    <td style={subCell}>{det.is_diamond ? det.pcs || "" : ""}</td>
    <td style={subCell}>{det.is_diamond ? fmtN(det.wt) : ""}</td>
    <td style={subCell}>{det.is_diamond ? fmtI(det.rate) : ""}</td>
    <td style={subCell}>{det.is_diamond ? fmtI(det.amount) : ""}</td>
    {/* Stone columns — only if not diamond */}
    <td style={subCell}>{!det.is_diamond ? det.pcs || "" : ""}</td>
    <td style={subCell}>{!det.is_diamond ? fmtN(det.wt) : ""}</td>
    <td style={subCell}>{!det.is_diamond ? fmtI(det.rate) : ""}</td>
    <td style={subCell}>{!det.is_diamond ? fmtI(det.amount) : ""}</td>
    {/* Labour + Total empty */}
    <td style={subCell}></td>
    <td style={subCell}></td>
    <td style={subCell}></td>
  </tr>
);

const subCell = {
  border: "1px solid #ccc",
  padding: "1px 4px",
  fontSize: 9,
  color: "#555",
  textAlign: "right",
};

// ── Main item row ────────────────────────────────────────────────────────────

const ItemRow = ({ item, baseUrl }) => {
  const imgSrc = item.image_url
    ? item.image_url.startsWith("http")
      ? item.image_url
      : `${baseUrl}${item.image_url}`
    : null;

  // Count detail sub-rows for rowSpan
  const detailCount = (item.details || []).length;
  const rowSpan = detailCount > 0 ? 1 : 1; // We render sub-rows as separate <tr>, no rowSpan needed

  return (
    <>
      <tr>
        <TD rowSpan={detailCount + 1} style={{ verticalAlign: "middle" }}>{item.sl_no}</TD>
        <TD rowSpan={detailCount + 1} style={{ verticalAlign: "middle", padding: 2 }}>
          {imgSrc ? (
            <img src={imgSrc} alt="" style={{ width: 55, height: 55, objectFit: "cover", borderRadius: 3 }} />
          ) : (
            <div style={{ width: 55, height: 55, background: "#f5f5f5", borderRadius: 3, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 7, color: "#aaa" }}>
              {item.design_code || "—"}
            </div>
          )}
          <div style={{ fontSize: 8, fontWeight: 600, textAlign: "center", marginTop: 2 }}>{item.design_code}</div>
        </TD>
        <TD style={{ textAlign: "left" }}>{item.barcode_text}</TD>
        <TD style={{ textAlign: "left" }}>{item.item_name}</TD>
        {/* Gold */}
        <TD bold>{item.purity_text}</TD>
        <TD right>{fmtN(item.gw)}</TD>
        <TD right>{fmtN(item.nw)}</TD>
        <TD right>{fmtI(item.gold_rate)}</TD>
        <TD right bold>{fmtI(item.gold_amount)}</TD>
        {/* Quality/Size — aggregate on main row */}
        <TD></TD>
        {/* Diamond — aggregate */}
        <TD right bold>{item.total_diamond_pcs || ""}</TD>
        <TD right bold>{fmtN(item.total_diamond_wt)}</TD>
        <TD right></TD>
        <TD right bold>{fmtI(item.total_diamond_amt)}</TD>
        {/* Stone — aggregate */}
        <TD right>{item.total_stone_pcs || ""}</TD>
        <TD right>{fmtN(item.total_stone_wt)}</TD>
        <TD right></TD>
        <TD right>{fmtI(item.total_stone_amt)}</TD>
        {/* Labour */}
        <TD right>{fmtI(item.making_rate)}</TD>
        <TD right bold>{fmtI(item.making_amount)}</TD>
        {/* Total */}
        <TD right bold style={{ fontSize: 11 }}>{fmtI(item.total_amount)}</TD>
      </tr>
      {(item.details || []).map((det, di) => (
        <DetailSubRow key={di} det={det} />
      ))}
    </>
  );
};

// ── Main Print Component ─────────────────────────────────────────────────────

export default function QuotationPrint({ data }) {
  if (!data) return null;

  const items = data.items || [];
  const baseUrl = window.location.origin.replace(":5173", ":8000");

  const currentDate = data.date1
    ? formatDate(data.date1, "numeric")
    : formatDate(new Date(), "numeric");

  const partyName = data.ldgr_name || data.party_name || "—";

  // Grand totals
  const grand = items.reduce(
    (acc, item) => ({
      gw: acc.gw + parseFloat(item.gw || 0),
      nw: acc.nw + parseFloat(item.nw || 0),
      goldAmt: acc.goldAmt + parseFloat(item.gold_amount || 0),
      diamondPcs: acc.diamondPcs + parseInt(item.total_diamond_pcs || 0),
      diamondWt: acc.diamondWt + parseFloat(item.total_diamond_wt || 0),
      diamondAmt: acc.diamondAmt + parseFloat(item.total_diamond_amt || 0),
      stonePcs: acc.stonePcs + parseInt(item.total_stone_pcs || 0),
      stoneWt: acc.stoneWt + parseFloat(item.total_stone_wt || 0),
      stoneAmt: acc.stoneAmt + parseFloat(item.total_stone_amt || 0),
      makingAmt: acc.makingAmt + parseFloat(item.making_amount || 0),
      totalAmt: acc.totalAmt + parseFloat(item.total_amount || 0),
    }),
    { gw: 0, nw: 0, goldAmt: 0, diamondPcs: 0, diamondWt: 0, diamondAmt: 0, stonePcs: 0, stoneWt: 0, stoneAmt: 0, makingAmt: 0, totalAmt: 0 }
  );

  // Pure gold calculation
  const pureGold = items.reduce((sum, item) => {
    const nw = parseFloat(item.nw || 0);
    const purityStr = (item.purity_text || "").replace(/[^0-9.]/g, "");
    const purity = parseFloat(purityStr) || 0;
    // If purity is like 22, convert: 22K → 91.6%
    const purityPct = purity > 100 ? purity / 10 : purity < 25 ? (purity / 24) * 100 : purity;
    return sum + (nw * purityPct) / 100;
  }, 0);

  const taxPercent = parseFloat(data.tax_percent || 3);
  const taxAmount = parseFloat(data.tax_amount) || Math.round(grand.totalAmt * (taxPercent / 100));
  const netTotal = parseFloat(data.net_total) || grand.totalAmt + taxAmount;

  return (
    <div
      style={{
        padding: "12px 16px",
        maxWidth: 1200,
        margin: "0 auto",
        fontFamily: "'Segoe UI', Arial, sans-serif",
        color: "#111",
      }}
    >
      <style>{`
        @media print {
          @page { size: A4 landscape; margin: 8mm; }
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        }
      `}</style>

      {/* ── Title ──────────────────────────────────────────────────────── */}
      <h1
        style={{
          textAlign: "center",
          fontSize: 20,
          fontWeight: 800,
          letterSpacing: 4,
          marginBottom: 8,
          textTransform: "uppercase",
        }}
      >
        Quotation
      </h1>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10 }}>
        <div>
          <span style={{ fontSize: 12 }}>
            <strong>Party :.</strong> {partyName}
          </span>
        </div>
        <div style={{ textAlign: "right", fontSize: 12 }}>
          <div>
            <strong>NO :</strong>&nbsp;&nbsp; {data.quotation_no || "—"}
          </div>
          <div>
            <strong>Date :</strong>&nbsp;&nbsp; {currentDate}
          </div>
        </div>
      </div>

      {/* ── Main Table ─────────────────────────────────────────────────── */}
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          {/* Row 1: Group headers */}
          <tr>
            <TH rowSpan={2} width={28}>Sr.</TH>
            <TH rowSpan={2} width={65}>Design</TH>
            <TH rowSpan={2} width={65}>Item No.</TH>
            <TH rowSpan={2} width={90}>Product</TH>
            <TH colSpan={5} style={{ background: "#e8e8e8" }}>Gold</TH>
            <TH rowSpan={2} width={55}>Quality<br/>Size</TH>
            <TH colSpan={4} style={{ background: "#e0e8f0" }}>Diamond</TH>
            <TH colSpan={4} style={{ background: "#e0f0e8" }}>Stone</TH>
            <TH colSpan={2}>Labour</TH>
            <TH rowSpan={2} width={65}>Total<br/>(Rs.)</TH>
          </tr>
          {/* Row 2: Sub headers */}
          <tr>
            {/* Gold */}
            <TH width={35}>Qly</TH>
            <TH width={45}>Gwt</TH>
            <TH width={45}>Nwt</TH>
            <TH width={40}>Rate</TH>
            <TH width={55}>Amt</TH>
            {/* Diamond */}
            <TH width={30}>Pcs</TH>
            <TH width={42}>Wt</TH>
            <TH width={40}>Rate</TH>
            <TH width={50}>Amt</TH>
            {/* Stone */}
            <TH width={30}>Pcs</TH>
            <TH width={42}>Wt</TH>
            <TH width={40}>Rate</TH>
            <TH width={50}>Amt</TH>
            {/* Labour */}
            <TH width={40}>Rate</TH>
            <TH width={50}>Amt</TH>
          </tr>
        </thead>

        <tbody>
          {items.map((item) => (
            <ItemRow key={item.sl_no} item={item} baseUrl={baseUrl} />
          ))}
        </tbody>

        <tfoot>
          {/* ── TOTAL row ──────────────────────────────────────────────── */}
          <tr style={{ background: "#e5e7eb", fontWeight: 700 }}>
            <TD colSpan={4} bold style={{ textAlign: "left", fontSize: 11 }}>TOTAL</TD>
            <TD></TD>
            <TD right bold>{fmtN(grand.gw)}</TD>
            <TD right bold>{fmtN(grand.nw)}</TD>
            <TD right></TD>
            <TD right bold>{fmtI(grand.goldAmt)}</TD>
            <TD></TD>
            <TD right bold>{grand.diamondPcs || ""}</TD>
            <TD right bold>{fmtN(grand.diamondWt)}</TD>
            <TD right></TD>
            <TD right bold>{fmtI(grand.diamondAmt)}</TD>
            <TD right bold>{grand.stonePcs || ""}</TD>
            <TD right bold>{fmtN(grand.stoneWt)}</TD>
            <TD right></TD>
            <TD right bold>{fmtI(grand.stoneAmt)}</TD>
            <TD right></TD>
            <TD right bold>{fmtI(grand.makingAmt)}</TD>
            <TD right bold style={{ fontSize: 11 }}>{fmtI(grand.totalAmt)}</TD>
          </tr>
        </tfoot>
      </table>

      {/* ── Pure Gold / Seller Info / Tax ─────────────────────────────── */}
      <div style={{ marginTop: 10, display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 11 }}>
            <strong>Pure Gold :.</strong>&nbsp;&nbsp;&nbsp; <strong>{pureGold.toFixed(3)}</strong>
          </div>
          {data.seller_info && (
            <div style={{ fontSize: 11, marginTop: 4, color: "#444" }}>
              {data.seller_info}
            </div>
          )}
        </div>
        <table style={{ borderCollapse: "collapse", minWidth: 250 }}>
          {taxAmount > 0 && (
            <tr>
              <td style={{ border: "1px solid #888", padding: "4px 10px", fontSize: 11, textAlign: "right", fontWeight: 600 }}>
                GST @ {taxPercent}%
              </td>
              <td style={{ border: "1px solid #888", padding: "4px 10px", fontSize: 11, textAlign: "right", fontWeight: 700 }}>
                {fmtI(taxAmount)}
              </td>
            </tr>
          )}
          <tr>
            <td style={{ border: "1px solid #888", padding: "4px 10px", fontSize: 12, textAlign: "right", fontWeight: 700 }}>
              Net Total :
            </td>
            <td style={{ border: "1px solid #888", padding: "4px 10px", fontSize: 13, textAlign: "right", fontWeight: 800 }}>
              {formatNumber(netTotal)}
            </td>
          </tr>
        </table>
      </div>

      {/* ── Valid Until ────────────────────────────────────────────────── */}
      {data.valid_until && (
        <div style={{ fontSize: 9, color: "#888", marginTop: 10 }}>
          Valid until: {formatDate(data.valid_until, "short")}
        </div>
      )}
    </div>
  );
}
