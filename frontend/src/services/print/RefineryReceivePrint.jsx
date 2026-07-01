import React from "react";

const formatDate = (dateString) => {
  if (!dateString) return "";
  return new Date(dateString).toLocaleDateString("en-GB", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
};

const fmt3 = (val) => parseFloat(val || 0).toFixed(3);

const RefineryReceivePrint = ({ data = {} }) => {
  const d = Array.isArray(data) ? data[0] : data;
  const items = d?.refinaryreceivedetail_set || [];

  const totals = items.reduce(
    (acc, item) => {
      acc.gw     += parseFloat(item.gw || 0);
      acc.convNw += parseFloat(item.conv_nw || 0);
      acc.lossWt += parseFloat(item.loss_wt || 0);
      return acc;
    },
    { gw: 0, convNw: 0, lossWt: 0 }
  );

  return (
    <div className="gi-alt">

      {/* Company header */}
      <div className="gi-company">
        <div className="gi-company-name">{d?.company_name || "JEWEL INDIA"}</div>
        {d?.company_address && <div className="gi-company-line">{d.company_address}</div>}
        {(d?.company_phone || d?.company_email) && (
          <div className="gi-company-line">
            {d.company_phone && <>Ph: {d.company_phone}</>}
            {d.company_phone && d.company_email && <>&nbsp;&nbsp;&middot;&nbsp;&nbsp;</>}
            {d.company_email && <>Email: {d.company_email}</>}
          </div>
        )}
        {(d?.company_gstin || d?.company_pan) && (
          <div className="gi-company-ids">
            {d.company_gstin && <span><strong>GSTIN:</strong> {d.company_gstin}</span>}
            {d.company_pan   && <span><strong>PAN:</strong> {d.company_pan}</span>}
          </div>
        )}
      </div>

      {/* Voucher title */}
      <div className="gi-title">Refinery Receive</div>

      {/* Meta strip */}
      <div className="gi-meta-row">
        <div className="gi-meta-block">
          <span className="gi-label">Voucher No.</span>
          <span>{d?.billno || "-"}</span>
        </div>
        <div className="gi-meta-block">
          <span className="gi-label">Date</span>
          <span>{formatDate(d?.date1)}</span>
        </div>
        <div className="gi-meta-block">
          <span className="gi-label">Refinery</span>
          <span>{d?.ldgr_name || "-"}</span>
        </div>
      </div>

      {/* Items table */}
      <table className="gi-table">
        <thead>
          <tr>
            <th className="gi-col-sl">Sl.<br/>No.</th>
            <th className="gi-col-num">Issue No</th>
            <th className="gi-col-item">Item</th>
            <th className="gi-col-num">Purity</th>
            <th className="gi-col-num">Gross Wt<br/>(gm)</th>
            <th className="gi-col-num">Conv<br/>Purity</th>
            <th className="gi-col-num">Conv Wt<br/>(gm)</th>
            <th className="gi-col-num">Loss %</th>
            <th className="gi-col-num">Loss Wt<br/>(gm)</th>
            <th className="gi-col-item">Remarks</th>
          </tr>
        </thead>
        <tbody>
          {items.length > 0 ? items.map((item, idx) => (
            <tr key={item.id || idx}>
              <td className="gi-ctr">{idx + 1}</td>
              <td className="gi-ctr">{item.issue_no || "-"}</td>
              <td>{item.item || "-"}</td>
              <td className="gi-ctr">{item.metal_purity || "-"}</td>
              <td className="gi-right">{fmt3(item.gw)}</td>
              <td className="gi-ctr">{item.conv_purity || "-"}</td>
              <td className="gi-right">{fmt3(item.conv_nw)}</td>
              <td className="gi-right">{fmt3(item.loss_per)}</td>
              <td className="gi-right">{fmt3(item.loss_wt)}</td>
              <td>{item.remarks || ""}</td>
            </tr>
          )) : (
            <tr>
              <td colSpan="10" className="gi-empty">No items</td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr className="gi-totals">
            <td colSpan="4" className="gi-right" style={{ paddingRight: "8px" }}>Total</td>
            <td className="gi-right">{fmt3(totals.gw)}</td>
            <td></td>
            <td className="gi-right">{fmt3(totals.convNw)}</td>
            <td></td>
            <td className="gi-right">{fmt3(totals.lossWt)}</td>
            <td></td>
          </tr>
        </tfoot>
      </table>

      {/* Signatures */}
      <div className="gi-sigs">
        {["Refinery Signature", "Prepared By", "Authorised Signatory"].map((label) => (
          <div key={label} className="gi-sig-block">
            <div className="gi-sig-space" />
            <div className="gi-sig-line" />
            <div className="gi-sig-label">{label}</div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="gi-footer">This is a computer generated document.</div>

      <style>{`
        .gi-alt { font-family: Arial, sans-serif; font-size: 11px; color: #000; background: #fff; padding: 28px 32px 24px; max-width: 980px; margin: 0 auto; }
        .gi-company { text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; }
        .gi-company-name { font-size: 18px; font-weight: bold; letter-spacing: 0.03em; }
        .gi-company-line { font-size: 10px; color: #333; margin-top: 3px; line-height: 1.5; }
        .gi-company-ids { font-size: 9.5px; color: #333; margin-top: 3px; display: flex; justify-content: center; gap: 18px; }
        .gi-title { text-align: center; font-size: 12px; font-weight: bold; letter-spacing: 0.08em; text-transform: uppercase; padding: 7px 0; border-bottom: 1px solid #000; }
        .gi-meta-row { display: flex; border-bottom: 1px solid #000; }
        .gi-meta-block { flex: 1; padding: 6px 10px; display: flex; gap: 6px; align-items: baseline; }
        .gi-meta-block + .gi-meta-block { border-left: 1px solid #000; }
        .gi-label { font-weight: bold; font-size: 10.5px; width: 74px; flex-shrink: 0; }
        .gi-table { width: 100%; border-collapse: collapse; }
        .gi-table th, .gi-table td { border: 1px solid #000; padding: 5px 6px; font-size: 10px; }
        .gi-table thead th { background: #f2f2f2; font-weight: bold; text-align: center; }
        .gi-col-sl { width: 34px; }
        .gi-col-num { width: 60px; }
        .gi-ctr { text-align: center; }
        .gi-right { text-align: right; }
        .gi-empty { text-align: center; padding: 12px; color: #555; }
        .gi-totals td { font-weight: bold; background: #f2f2f2; }
        .gi-sigs { display: flex; justify-content: space-between; padding: 20px 8px 0; }
        .gi-sig-block { text-align: center; width: 160px; }
        .gi-sig-space { height: 40px; }
        .gi-sig-line { border-top: 1px solid #000; margin-bottom: 4px; }
        .gi-sig-label { font-size: 10px; }
        .gi-footer { text-align: center; font-size: 9px; color: #666; margin-top: 16px; padding-top: 6px; border-top: 1px solid #ccc; }
        @media print { .gi-alt { padding: 12px; max-width: none; } body { margin: 0; padding: 0; } }
      `}</style>
    </div>
  );
};

export default RefineryReceivePrint;
