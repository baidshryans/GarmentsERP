import React from "react";

const formatDate = (dateString) => {
  if (!dateString) return "";
  return new Date(dateString).toLocaleDateString("en-GB", {
    day: "2-digit", month: "2-digit", year: "numeric",
  });
};

const fmt3 = (val) => parseFloat(val || 0).toFixed(3);

const GoldIssueToKarigarAlt = ({ data = {} }) => {
  const d = Array.isArray(data) ? data[0] : data;
  const items = d?.karigargoldissue_set || [];

  const totals = items.reduce(
    (acc, item) => {
      acc.gw    += parseFloat(item.item_gw  || 0);
      acc.netWt += parseFloat(item.item_gw  || 0);
      acc.alloy += parseFloat(item.alloy_wt || 0);
      acc.convWt += parseFloat(item.conv_wt  || 0);
      return acc;
    },
    { gw: 0, netWt: 0, alloy: 0, convWt: 0 }
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
            {d.company_phone && d.company_email && <>&nbsp;&nbsp;�&nbsp;&nbsp;</>}
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
      <div className="gi-title">Karigar Gold Issue</div>

      {/* Meta strip */}
      <div className="gi-meta-row">
        <div className="gi-meta-block">
          <span className="gi-label">Voucher No.</span>
          <span>{d?.billno || "�"}</span>
        </div>
        <div className="gi-meta-block">
          <span className="gi-label">Date</span>
          <span>{formatDate(d?.date1)}</span>
        </div>
        <div className="gi-meta-block">
          <span className="gi-label">Slip Type</span>
          <span>{d?.slip_type || "�"}</span>
        </div>
      </div>

      {/* Karigar strip */}
      <div className="gi-karigar-row">
        <div className="gi-karigar-cell">
          <div className="gi-field">
            <span className="gi-label">Karigar</span>
            <span>{d?.karigar_ldgr_name || "�"}</span>
          </div>
          <div className="gi-field">
            <span className="gi-label">Address</span>
            <span>{d?.karigar_address || "�"}</span>
          </div>
        </div>
        <div className="gi-karigar-cell gi-karigar-right">
          <div className="gi-field">
            <span className="gi-label">Ref. Job No.</span>
            <span>{d?.karigargoldissue_set?.[0]?.ref_job_no?.issue_slip_no || d?.karigargoldissue_set?.[0]?.ref_job_no?.po_no || "�"}</span>
          </div>
        </div>
      </div>

      {/* Items table */}
      <table className="gi-table">
        <thead>
          <tr>
            <th className="gi-col-sl">Sl.<br/>No.</th>
            <th className="gi-col-item">Item Description</th>
            <th className="gi-col-num">Purity</th>
            <th className="gi-col-num">GW<br/>(gm)</th>
            <th className="gi-col-num">Net Wt<br/>(gm)</th>
            <th className="gi-col-num">Alloy<br/>(gm)</th>
            <th className="gi-col-num">Conv<br/>Purity</th>
            <th className="gi-col-num">Conv Wt<br/>(gm)</th>
          </tr>
        </thead>
        <tbody>
          {items.length > 0 ? items.map((item, idx) => (
            <tr key={item.id || idx}>
              <td className="gi-ctr">{item.sl_no || idx + 1}</td>
              <td>{item.item || "�"}</td>
              <td className="gi-ctr">{item.metal_purity || "�"}</td>
              <td className="gi-right">{fmt3(item.item_gw)}</td>
              <td className="gi-right">{fmt3(item.item_gw)}</td>
              <td className="gi-right">{fmt3(item.alloy_wt)}</td>
              <td className="gi-ctr">{item.conv_purity || "�"}</td>
              <td className="gi-right">{fmt3(item.conv_wt)}</td>
            </tr>
          )) : (
            <tr>
              <td colSpan="8" className="gi-empty">No items</td>
            </tr>
          )}
        </tbody>
        <tfoot>
          <tr className="gi-totals">
            <td colSpan="3" className="gi-right" style={{ paddingRight: "8px" }}>Total</td>
            <td className="gi-right">{fmt3(totals.gw)}</td>
            <td className="gi-right">{fmt3(totals.netWt)}</td>
            <td className="gi-right">{fmt3(totals.alloy)}</td>
            <td></td>
            <td className="gi-right">{fmt3(totals.convWt)}</td>
          </tr>
        </tfoot>
      </table>

      {/* Signatures */}
      <div className="gi-sigs">
        {["Karigar Signature", "Prepared By", "Authorised Signatory"].map((label) => (
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
        .gi-alt {
          font-family: Arial, sans-serif;
          font-size: 11px;
          color: #000;
          background: #fff;
          padding: 28px 32px 24px;
          max-width: 860px;
          margin: 0 auto;
        }

        /* Company */
        .gi-company {
          text-align: center;
          border-bottom: 2px solid #000;
          padding-bottom: 12px;
        }
        .gi-company-name {
          font-size: 18px;
          font-weight: bold;
          letter-spacing: 0.03em;
        }
        .gi-company-line {
          font-size: 10px;
          color: #333;
          margin-top: 3px;
          line-height: 1.5;
        }
        .gi-company-ids {
          font-size: 9.5px;
          color: #333;
          margin-top: 3px;
          display: flex;
          justify-content: center;
          gap: 18px;
        }

        /* Title */
        .gi-title {
          text-align: center;
          font-size: 12px;
          font-weight: bold;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          padding: 7px 0;
          border-bottom: 1px solid #000;
        }

        /* Meta strip */
        .gi-meta-row {
          display: flex;
          border-bottom: 1px solid #000;
        }
        .gi-meta-block {
          flex: 1;
          padding: 6px 10px;
          display: flex;
          gap: 6px;
          align-items: baseline;
        }
        .gi-meta-block + .gi-meta-block { border-left: 1px solid #000; }

        /* Karigar strip */
        .gi-karigar-row {
          display: flex;
          border-bottom: 1px solid #000;
        }
        .gi-karigar-cell { flex: 1; padding: 6px 10px; }
        .gi-karigar-right { flex: 0 0 220px; border-left: 1px solid #000; }
        .gi-field { display: flex; gap: 6px; margin-bottom: 4px; align-items: baseline; }
        .gi-field:last-child { margin-bottom: 0; }

        /* Shared label */
        .gi-label { font-weight: bold; font-size: 10.5px; width: 74px; flex-shrink: 0; }

        /* Items table */
        .gi-table { width: 100%; border-collapse: collapse; }
        .gi-table th, .gi-table td {
          border: 1px solid #000;
          padding: 5px 7px;
          font-size: 10.5px;
        }
        .gi-table thead th {
          background: #f2f2f2;
          font-weight: bold;
          text-align: center;
        }
        .gi-col-sl   { width: 38px; }
        .gi-col-item { }
        .gi-col-num  { width: 68px; }
        .gi-ctr  { text-align: center; }
        .gi-right { text-align: right; }
        .gi-empty { text-align: center; padding: 12px; color: #555; }

        /* Totals */
        .gi-totals td { font-weight: bold; background: #f2f2f2; }

        /* Signatures */
        .gi-sigs {
          display: flex;
          justify-content: space-between;
          padding: 20px 8px 0;
        }
        .gi-sig-block { text-align: center; width: 160px; }
        .gi-sig-space { height: 40px; }
        .gi-sig-line  { border-top: 1px solid #000; margin-bottom: 4px; }
        .gi-sig-label { font-size: 10px; }

        /* Footer */
        .gi-footer {
          text-align: center;
          font-size: 9px;
          color: #666;
          margin-top: 16px;
          padding-top: 6px;
          border-top: 1px solid #ccc;
        }

        @media print {
          .gi-alt { padding: 12px; max-width: none; }
          body { margin: 0; padding: 0; }
        }
      `}</style>
    </div>
  );
};

export default GoldIssueToKarigarAlt;
