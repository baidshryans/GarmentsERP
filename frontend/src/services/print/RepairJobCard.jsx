import React from "react";

const LOSS_LABELS = {
  POLISH:  "Polish Loss",
  FILING:  "Filing Loss",
  MELTING: "Melting Loss",
  STONE:   "Stone Setting Loss",
  OTHER:   "Other",
};

const STATUS_LABELS = {
  RCV:  "Received from Customer",
  ISS:  "Issued to Karigar",
  RECV: "Received from Karigar",
  RDY:  "Ready for Delivery",
  DLV:  "Delivered",
};

const fmt3 = (n) => (parseFloat(n) || 0).toFixed(3);
const fmt2 = (n) => (parseFloat(n) || 0).toFixed(2);

const fmtDate = (d) => {
  if (!d) return "�";
  return new Date(d).toLocaleDateString("en-GB", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
};

export default function RepairJobCardPrint({ data = {} }) {
  const d = data;
  const showRepairDetails = ["RECV", "RDY", "DLV"].includes(d.status);

  const losses      = Array.isArray(d.losses)      ? d.losses      : [];
  const stones      = Array.isArray(d.stones)       ? d.stones      : [];
  const karigarLinks = Array.isArray(d.karigar_links) ? d.karigar_links : [];

  const namedLoss = losses.reduce((s, l) => s + (parseFloat(l.loss_wt) || 0), 0);
  const balance   = (parseFloat(d.received_gw) || 0) - (parseFloat(d.returned_gw) || 0) - namedLoss;

  return (
    <div style={{ fontFamily: "Arial, sans-serif", fontSize: "12px", color: "#000", maxWidth: "750px", margin: "0 auto", padding: "16px" }}>

      {/* ── Shop Header ── */}
      <div style={{ textAlign: "center", borderBottom: "2px solid #000", paddingBottom: "8px", marginBottom: "12px" }}>
        <div style={{ fontSize: "18px", fontWeight: "bold", letterSpacing: "1px" }}>
          {d.retail_name || "JEWEL INDIA"}
        </div>
        <div style={{ fontSize: "13px", fontWeight: "bold", marginTop: "4px", textDecoration: "underline" }}>
          REPAIR JOB CARD
        </div>
      </div>

      {/* ── Top info grid ── */}
      <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "10px" }}>
        <tbody>
          <tr>
            <td style={{ width: "50%", verticalAlign: "top" }}>
              <Row label="RJC No"    value={d.rjc_no}          />
              <Row label="Date"      value={fmtDate(d.date1)}   />
              <Row label="Customer"  value={d.customer_name}    />
              <Row label="Mobile"    value={d.customer_mobile || "�"} />
            </td>
            <td style={{ width: "50%", verticalAlign: "top", paddingLeft: "16px" }}>
              <Row label="Item"      value={d.item_name || "�"}   />
              <Row label="Purity"    value={d.purity_name || "�"} />
              <Row label="Exp. Delivery" value={fmtDate(d.expected_delivery_date)} />
              <Row label="Status"    value={STATUS_LABELS[d.status] || d.status} />
            </td>
          </tr>
        </tbody>
      </table>

      {/* ── Description ── */}
      {d.description && (
        <div style={{ border: "1px solid #999", borderRadius: "4px", padding: "6px 10px", marginBottom: "10px" }}>
          <span style={{ fontWeight: "bold" }}>Repair Instructions: </span>
          {d.description}
        </div>
      )}

      {/* ── Gold Received ── */}
      <SectionTitle>Gold Received from Customer</SectionTitle>
      <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "10px" }}>
        <tbody>
          <tr>
            <Th>Gross Weight (g)</Th>
            <Th>Net Weight (g)</Th>
          </tr>
          <tr>
            <Td center>{fmt3(d.received_gw)}</Td>
            <Td center>{fmt3(d.received_nw)}</Td>
          </tr>
        </tbody>
      </table>

      {/* ── Stones ── */}
      {stones.length > 0 && (
        <>
          <SectionTitle>Customer-Owned Stones</SectionTitle>
          <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "10px" }}>
            <tbody>
              <tr>
                <Th>Description</Th>
                <Th>Pcs</Th>
                <Th>Carats</Th>
                <Th>Remarks</Th>
                <Th>Returned</Th>
              </tr>
              {stones.map((s, i) => (
                <tr key={s.id ?? i}>
                  <Td>{s.description}</Td>
                  <Td center>{s.pcs}</Td>
                  <Td center>{fmt3(s.ct)}</Td>
                  <Td>{s.remarks}</Td>
                  <Td center>{s.returned ? "✓" : "�"}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* ── Karigar Activity (only shown after repair) ── */}
      {showRepairDetails && karigarLinks.length > 0 && (
        <>
          <SectionTitle>Karigar Activity</SectionTitle>
          <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "10px" }}>
            <tbody>
              <tr>
                <Th>Issue No</Th>
                <Th>Karigar</Th>
                <Th>Receive No</Th>
                <Th>Returned GW (g)</Th>
              </tr>
              {karigarLinks.map((lk) => (
                <tr key={lk.id}>
                  <Td>{lk.karigar_issue_no || "�"}</Td>
                  <Td>{lk.karigar_name || "�"}</Td>
                  <Td>{lk.karigar_receive_no || "�"}</Td>
                  <Td center>{lk.returned_gw ? fmt3(lk.returned_gw) : "�"}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* ── Named Losses (only shown after repair) ── */}
      {showRepairDetails && losses.length > 0 && (
        <>
          <SectionTitle>Manufacturing Losses</SectionTitle>
          <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "10px" }}>
            <tbody>
              <tr>
                <Th>Loss Type</Th>
                <Th>Weight (g)</Th>
                <Th>Remarks</Th>
              </tr>
              {losses.map((l, i) => (
                <tr key={l.id ?? i}>
                  <Td>{LOSS_LABELS[l.loss_type] || l.loss_type}</Td>
                  <Td center>{fmt3(l.loss_wt)}</Td>
                  <Td>{l.remarks}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* ── Weight Reconciliation (only shown after repair) ── */}
      {showRepairDetails && (
        <>
          <SectionTitle>Weight Reconciliation</SectionTitle>
          <table style={{ width: "100%", borderCollapse: "collapse", marginBottom: "10px" }}>
            <tbody>
              <tr>
                <Th>Received (g)</Th>
                <Th>Returned (g)</Th>
                <Th>Named Losses (g)</Th>
                <Th>Balance (g)</Th>
              </tr>
              <tr>
                <Td center>{fmt3(d.received_gw)}</Td>
                <Td center>{fmt3(d.returned_gw)}</Td>
                <Td center>{fmt3(namedLoss)}</Td>
                <Td center style={{ fontWeight: "bold", color: Math.abs(balance) <= 0.005 ? "#166534" : balance > 0 ? "#92400e" : "#991b1b" }}>
                  {fmt3(balance)}
                </Td>
              </tr>
            </tbody>
          </table>
        </>
      )}

      {/* ── Charges ── */}
      {(parseFloat(d.estimated_making) > 0) && (
        <div style={{ marginBottom: "10px" }}>
          <Row label="Estimated Making Charges" value={`₹ ${fmt2(d.estimated_making)}`} />
        </div>
      )}

      {/* ── Remarks ── */}
      {d.remarks && (
        <div style={{ marginBottom: "10px" }}>
          <Row label="Remarks" value={d.remarks} />
        </div>
      )}

      {/* ── Signature strip ── */}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: "32px", borderTop: "1px solid #000", paddingTop: "16px" }}>
        <div style={{ textAlign: "center", width: "200px" }}>
          <div style={{ borderTop: "1px solid #000", marginTop: "40px", paddingTop: "4px" }}>Customer Signature</div>
        </div>
        <div style={{ textAlign: "center", width: "200px" }}>
          <div style={{ borderTop: "1px solid #000", marginTop: "40px", paddingTop: "4px" }}>Authorised Signature</div>
        </div>
      </div>

      {/* ── Footer note ── */}
      <div style={{ textAlign: "center", fontSize: "10px", color: "#555", marginTop: "12px", borderTop: "1px dotted #ccc", paddingTop: "6px" }}>
        This is a computer-generated document. Please retain this slip for future reference.
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        @media print {
          body { margin: 0; padding: 0; font-size: 11px; }
          .no-print { display: none !important; }
        }
      `}} />
    </div>
  );
}

// ── Small helpers ────────────────────────────────────────────────────────────

function SectionTitle({ children }) {
  return (
    <div style={{ fontWeight: "bold", fontSize: "11px", background: "#f0f0f0", padding: "3px 8px", border: "1px solid #999", marginBottom: "4px" }}>
      {children}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: "flex", marginBottom: "3px" }}>
      <span style={{ fontWeight: "bold", width: "150px", flexShrink: 0 }}>{label}:</span>
      <span>{value || "�"}</span>
    </div>
  );
}

function Th({ children }) {
  return (
    <th style={{ border: "1px solid #999", padding: "4px 8px", background: "#f0f0f0", textAlign: "center", fontSize: "11px" }}>
      {children}
    </th>
  );
}

function Td({ children, center, style: s }) {
  return (
    <td style={{ border: "1px solid #ccc", padding: "4px 8px", textAlign: center ? "center" : "left", fontSize: "11px", ...s }}>
      {children ?? "�"}
    </td>
  );
}
