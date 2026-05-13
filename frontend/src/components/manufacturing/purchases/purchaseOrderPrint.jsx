import React from 'react';

// ── helpers ───────────────────────────────────────────────────────────────────

const FONT = '"Inter", Arial, Helvetica, sans-serif';

const FONTS_HREF =
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap';

const PO_HDR_CSS = `
  .po-hdr {
    display: grid; grid-template-columns: auto 1fr auto;
    align-items: center; gap: 16px;
    padding-bottom: 14px; border-bottom: 2px solid #0f172a; margin-bottom: 8px;
  }
  .po-bis {
    width: 64px; height: 64px;
    display: grid; place-items: center;
    font-size: 7.5px; color: #64748b; text-align: center; line-height: 1.15;
    letter-spacing: 0.5px; font-family: "Inter", Arial, sans-serif;
  }
  .po-bis.placeholder { border: 1px dashed #94a3b8; border-radius: 50%; }
  .po-bis img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .po-logo {
    width: 90px; height: 64px;
    display: grid; place-items: center;
    font-size: 7.5px; color: #64748b; text-align: center; line-height: 1.15;
    letter-spacing: 0.5px; font-family: "Inter", Arial, sans-serif;
  }
  .po-logo.placeholder { border: 1px dashed #94a3b8; }
  .po-logo img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .po-brand-block { display: flex; flex-direction: column; align-items: center; gap: 4px; text-align: center; }
  .po-brand { font-family: "Fraunces", Georgia, serif; font-size: 14px; font-weight: 700; color: #0f172a; }
  .po-brand-sub { font-size: 9px; color: #64748b; letter-spacing: 0.2px; font-family: "Inter", Arial, sans-serif; }
  .po-brand-sub strong { color: #0f172a; font-weight: 600; }
  .po-brand-ids { display: flex; gap: 18px; font-size: 8.5px; color: #64748b; margin-top: 2px; font-family: "Inter", Arial, sans-serif; }
  .po-brand-ids span b { color: #0f172a; font-weight: 600; margin-left: 4px; font-variant-numeric: tabular-nums; }
`;

const fmtDate = (val) => {
  if (!val) return '—';
  const d = new Date(val);
  if (isNaN(d)) return val;
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: '2-digit', year: 'numeric' });
};

const fmtWt = (v) => {
  const n = parseFloat(v);
  return isNaN(n) || n === 0 ? '—' : n.toFixed(3);
};

// ── Shared style tokens ───────────────────────────────────────────────────────

const BASE = 10;

const th = (extra = {}) => ({
  fontFamily: FONT,
  borderLeft: '1px solid #bbb', borderTop: '1px solid #aaa', borderBottom: '1px solid #aaa', borderRight: 'none',
  padding: '4px 5px', fontSize: 9, fontWeight: 700,
  background: '#fff', textAlign: 'center', whiteSpace: 'nowrap', lineHeight: 1.3,
  ...extra,
});
const th0 = (extra = {}) => th({ borderLeft: 'none', ...extra });

const td = (extra = {}) => ({
  fontFamily: FONT,
  borderLeft: '1px solid #e0e0e0', borderTop: 'none', borderBottom: 'none', borderRight: 'none',
  padding: '4px 5px', fontSize: BASE, verticalAlign: 'middle', lineHeight: 1.35,
  ...extra,
});
const td0 = (extra = {}) => td({ borderLeft: 'none', ...extra });

const totCell = (extra = {}) => ({
  ...td(extra),
  fontWeight: 700, background: '#f5f5f5',
  borderTop: '1px solid #aaa', borderBottom: '1px solid #aaa',
});
const totCell0 = (extra = {}) => totCell({ borderLeft: 'none', ...extra });

// ── Main component ────────────────────────────────────────────────────────────

export const PurchaseOrderPrint = ({ po, rows = [], company = {} }) => {
  const totalPcs = rows.reduce((s, r) => s + (parseInt(r.pcs) || 0), 0);
  const totalWt  = rows.reduce((s, r) => s + (parseFloat(r.approx_wt) || 0), 0);

  const { name = '', address = '', phone = '', email = '', pan = '', cin = '', gstin = '',
          bis_logo_url = '', company_logo_url = '' } = company;

  return (
    <div style={{ padding: '14mm', maxWidth: 700, margin: '0 auto', fontFamily: FONT }}>

      {/* ── Font + header CSS ── */}
      <link rel="stylesheet" href={FONTS_HREF} />
      <style>{PO_HDR_CSS}</style>

      {/* ── Company header (matches Sales Invoice layout) ── */}
      <div className="po-hdr">
        <div className={bis_logo_url ? 'po-bis' : 'po-bis placeholder'}>
          {bis_logo_url
            ? <img src={bis_logo_url} alt="BIS Hallmark" />
            : <span>BIS<br />HALLMARK</span>}
        </div>
        <div className="po-brand-block">
          {name && <div className="po-brand">{name}</div>}
          {address && <div className="po-brand-sub">{address}</div>}
          {(phone || email) && (
            <div className="po-brand-sub">
              {phone && <>Phone <strong>{phone}</strong></>}
              {phone && email && <> &nbsp;·&nbsp; </>}
              {email && <>Email <strong>{email}</strong></>}
            </div>
          )}
          {(gstin || pan || cin) && (
            <div className="po-brand-ids">
              {gstin && <span>GSTIN<b>{gstin}</b></span>}
              {pan   && <span>PAN<b>{pan}</b></span>}
              {cin   && <span>CIN<b>{cin}</b></span>}
            </div>
          )}
        </div>
        <div className={company_logo_url ? 'po-logo' : 'po-logo placeholder'}>
          {company_logo_url
            ? <img src={company_logo_url} alt="Logo" />
            : <span>COMPANY<br />LOGO</span>}
        </div>
      </div>

      {/* ── PO title + type badge ── */}
      <div style={{ textAlign: 'center', marginTop: 10, marginBottom: 8 }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 4, textTransform: 'uppercase', color: '#0f172a', fontFamily: FONT }}>
          PURCHASE ORDER
        </div>
      </div>

      {/* ── Order details + Supplier ── */}
      <div style={{ display: 'flex', marginBottom: 10 }}>
        <div style={{
          flex: 1, padding: '6px 8px', border: '1px solid #ccc',
          borderRight: 'none', fontSize: 9, lineHeight: 1.9, fontFamily: FONT,
        }}>
          <div style={{ fontSize: 7.5, fontWeight: 700, letterSpacing: 1, color: '#888', textTransform: 'uppercase', marginBottom: 2 }}>
            Order Details
          </div>
          <div>
            <span style={{ color: '#777', width: 50, display: 'inline-block' }}>PO No</span>
            <span style={{ fontWeight: 700 }}>{po?.po_no || '—'}</span>
          </div>
          <div>
            <span style={{ color: '#777', width: 50, display: 'inline-block' }}>Date</span>
            <span style={{ fontWeight: 700 }}>{fmtDate(po?.date1)}</span>
          </div>
        </div>
        <div style={{
          flex: 1, padding: '6px 8px', border: '1px solid #ccc',
          fontSize: 9, lineHeight: 1.9, fontFamily: FONT,
        }}>
          <div style={{ fontSize: 7.5, fontWeight: 700, letterSpacing: 1, color: '#888', textTransform: 'uppercase', marginBottom: 2 }}>
            Supplier / Karigar
          </div>
          <div style={{ fontSize: 11, fontWeight: 700, fontFamily: FONT }}>{po?.ldgr_name || '—'}</div>
        </div>
      </div>

      {/* ── Items table (9 columns — Status removed) ── */}
      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'auto', fontFamily: FONT }}>
        <colgroup>
          <col style={{ width: 20  }} />{/* Sl */}
          <col                       />{/* Item */}
          <col style={{ width: 32  }} />{/* Purity */}
          <col style={{ width: 28  }} />{/* Pcs */}
          <col style={{ width: 52  }} />{/* Approx Wt */}
          <col style={{ width: 54  }} />{/* Design Code */}
          <col style={{ width: 28  }} />{/* Size */}
          <col style={{ width: 54  }} />{/* Due Date */}
          <col                       />{/* Remarks */}
        </colgroup>
        <thead>
          <tr>
            <th style={th0({ textAlign: 'center' })}>Sl</th>
            <th style={th0({ textAlign: 'left'   })}>Item</th>
            <th style={th({  textAlign: 'center' })}>Purity</th>
            <th style={th({  textAlign: 'center' })}>Pcs</th>
            <th style={th({  textAlign: 'right'  })}>Approx Wt (g)</th>
            <th style={th({  textAlign: 'center' })}>Design Code</th>
            <th style={th({  textAlign: 'center' })}>Size</th>
            <th style={th({  textAlign: 'center' })}>Due Date</th>
            <th style={th({  textAlign: 'left'   })}>Remarks</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => {
            const itemName = row._co_display?.item_name || row.item_name || row.item || '—';
            return (
              <tr key={idx} style={{ borderBottom: '1px solid #efefef' }}>
                <td style={td0({ textAlign: 'center' })}>{row.po_sl_no ?? idx + 1}</td>
                <td style={td0({ textAlign: 'left'   })}>{itemName}</td>
                <td style={td({  textAlign: 'center' })}>{row.purity || '—'}</td>
                <td style={td({  textAlign: 'center' })}>{row.pcs || '—'}</td>
                <td style={td({  textAlign: 'right'  })}>{fmtWt(row.approx_wt)}</td>
                <td style={td({  textAlign: 'center' })}>{row.design_code || '—'}</td>
                <td style={td({  textAlign: 'center' })}>{row.size || '—'}</td>
                <td style={td({  textAlign: 'center' })}>{fmtDate(row.due_date)}</td>
                <td style={td({  textAlign: 'left', fontSize: 9, color: '#555' })}>{row.remarks || ''}</td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={3} style={totCell0({ textAlign: 'right' })}>Total</td>
            <td style={totCell({ textAlign: 'center' })}>{totalPcs}</td>
            <td style={totCell({ textAlign: 'right'  })}>{fmtWt(totalWt)}</td>
            <td colSpan={4} style={totCell()} />
          </tr>
        </tfoot>
      </table>

      {/* ── Footer ── */}
      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', fontFamily: FONT }}>
        <div style={{ fontSize: 8, color: '#888', fontStyle: 'italic', maxWidth: '60%', lineHeight: 1.7 }}>
          Please ensure all items are hallmarked as per BIS standards.<br />
          Delivery must be accompanied by a delivery challan.<br />
          This is a computer-generated document.
        </div>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 110, borderTop: '1px solid #999', margin: '28px auto 0' }} />
          <div style={{ fontSize: 8.5, color: '#555', marginTop: 3 }}>Authorised Signatory</div>
        </div>
      </div>

    </div>
  );
};

export default PurchaseOrderPrint;

