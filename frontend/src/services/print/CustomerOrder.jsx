import React from "react";
import { formatMoney, formatNumber, formatDate } from "@/lib/format";

// ── helpers ───────────────────────────────────────────────────────────────────

const FONT = '"Inter", Arial, Helvetica, sans-serif';

const FONTS_HREF =
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap';

const fmtDate = (val) => {
  if (!val) return '—';
  const d = new Date(val);
  if (isNaN(d)) return val;
  return formatDate(val, 'numeric');
};

const fmtWt = (v) => {
  const n = parseFloat(v);
  return isNaN(n) || n === 0 ? '—' : n.toFixed(3);
};

const fmtAmt = (v) => {
  const n = parseFloat(v);
  if (isNaN(n) || n === 0) return '—';
  return formatMoney(n, { decimals: 0 });
};

const MAKING_LABELS = {
  per_nw:    '% of NW',
  per_gram:  'Per Gram',
  fixed:     'Fixed',
  flat:      'Flat',
};

// ── CSS ───────────────────────────────────────────────────────────────────────

const CO_CSS = `
  .co-hdr {
    display: grid; grid-template-columns: auto 1fr auto;
    align-items: center; gap: 16px;
    padding-bottom: 14px; border-bottom: 2px solid #0f172a; margin-bottom: 0;
  }
  .co-bis {
    width: 64px; height: 64px; border-radius: 50%;
    display: grid; place-items: center;
    font-size: 7.5px; color: #64748b; text-align: center; line-height: 1.15;
    letter-spacing: 0.5px; font-family: "Inter", Arial, sans-serif;
  }
  .co-bis img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .co-logo {
    width: 90px; height: 64px;
    display: grid; place-items: center;
    font-size: 7.5px; color: #64748b; text-align: center; line-height: 1.15;
    letter-spacing: 0.5px; font-family: "Inter", Arial, sans-serif;
  }
  .co-logo img { max-width: 100%; max-height: 100%; object-fit: contain; }
  .co-brand-block { display: flex; flex-direction: column; align-items: center; gap: 4px; text-align: center; }
  .co-brand { font-family: "Fraunces", Georgia, serif; font-size: 14px; font-weight: 700; color: #0f172a; }
  .co-brand-sub { font-size: 9px; color: #64748b; letter-spacing: 0.2px; font-family: "Inter", Arial, sans-serif; }
  .co-brand-sub strong { color: #0f172a; font-weight: 600; }
  .co-brand-ids { display: flex; gap: 18px; font-size: 8.5px; color: #64748b; margin-top: 2px; font-family: "Inter", Arial, sans-serif; }
  .co-brand-ids span b { color: #0f172a; font-weight: 600; margin-left: 4px; font-variant-numeric: tabular-nums; }
`;

// ── Style tokens ──────────────────────────────────────────────────────────────

const BASE = 10;

const th = (extra = {}) => ({
  fontFamily: FONT,
  borderLeft: '1px solid #bbb', borderTop: '1px solid #aaa', borderBottom: '1px solid #aaa', borderRight: 'none',
  padding: '4px 5px', fontSize: 8.5, fontWeight: 700,
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

const CustomerOrderPrint = ({ data = {}, company = {} }) => {
  const items = Array.isArray(data.items) ? data.items : [];

  const totalPcs = items.reduce((s, r) => s + (parseInt(r.pcs)  || 0), 0);
  const totalWt  = items.reduce((s, r) => s + (parseFloat(r.gw) || 0), 0);

  const { name = '', legal_name = '', address = '', phone = '', email = '', pan = '', cin = '', gstin = '',
          bis_logo_url = '', company_logo_url = '' } = company;

  const showGoldRates = Boolean(data.fix_gold_rate && (data.rate_14kt || data.rate_18kt || data.rate_22kt));
  const showAdvance   = Boolean(data.advance_amt || data.est_amount);

  return (
    <div style={{ padding: '14mm', maxWidth: 700, margin: '0 auto', fontFamily: FONT }}>

      {/* ── Font + CSS ── */}
      <link rel="stylesheet" href={FONTS_HREF} />
      <style>{CO_CSS}</style>

      {/* ── Company header ── */}
      <div className="co-hdr">
        <div className={bis_logo_url ? 'co-bis' : 'co-bis placeholder'}>
          {bis_logo_url
            ? <img src={bis_logo_url} alt="BIS Hallmark" />
            : <span>BIS<br />HALLMARK</span>}
        </div>
        <div className="co-brand-block">
          {name && <div className="co-brand">{name}</div>}
          {legal_name && <div className="co-brand-sub" style={{ fontSize: 11, fontWeight: 600, color: '#0f172a' }}>{legal_name}</div>}
          {address && <div className="co-brand-sub">{address}</div>}
          {(phone || email) && (
            <div className="co-brand-sub">
              {phone && <>Phone <strong>{phone}</strong></>}
              {phone && email && <> &nbsp;·&nbsp; </>}
              {email && <>Email <strong>{email}</strong></>}
            </div>
          )}
          {(gstin || pan || cin) && (
            <div className="co-brand-ids">
              {gstin && <span>GSTIN<b>{gstin}</b></span>}
              {pan   && <span>PAN<b>{pan}</b></span>}
              {cin   && <span>CIN<b>{cin}</b></span>}
            </div>
          )}
        </div>
        <div className={company_logo_url ? 'co-logo' : 'co-logo placeholder'}>
          {company_logo_url
            ? <img src={company_logo_url} alt="Logo" />
            : <span>COMPANY<br />LOGO</span>}
        </div>
      </div>

      {/* ── Document title ── */}
      <div style={{ textAlign: 'center', padding: '9px 0 7px', borderBottom: '1px solid #e2e8f0', marginBottom: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 4, textTransform: 'uppercase', color: '#0f172a', fontFamily: FONT }}>
          Customer Order
        </div>
      </div>

      {/* ── Order details + Customer ── */}
      <div style={{ display: 'flex', marginBottom: 10 }}>
        <div style={{ flex: 1, padding: '7px 9px', border: '1px solid #ccc', borderRight: 'none', fontSize: 9, lineHeight: 1.9, fontFamily: FONT }}>
          <div style={{ fontSize: 7.5, fontWeight: 700, letterSpacing: 1, color: '#888', textTransform: 'uppercase', marginBottom: 3 }}>Customer</div>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a', marginBottom: 1 }}>{data.ldgr_code_name || '—'}</div>
          {data.ldgr_mobile && (
            <div>
              <span style={{ color: '#777', display: 'inline-block', minWidth: 60 }}>Mobile</span>
              <span style={{ fontWeight: 600, color: '#0f172a' }}>{data.ldgr_mobile}</span>
            </div>
          )}
          {(data.salesman_1_name || data.salesman_2_name) && (
            <div>
              <span style={{ color: '#777', display: 'inline-block', minWidth: 60 }}>Salesman</span>
              <span style={{ fontWeight: 600, color: '#0f172a' }}>
                {[data.salesman_1_name, data.salesman_2_name].filter(Boolean).join(' / ')}
              </span>
            </div>
          )}
        </div>
        <div style={{ flex: 1, padding: '7px 9px', border: '1px solid #ccc', fontSize: 9, lineHeight: 1.9, fontFamily: FONT }}>
          <div style={{ fontSize: 7.5, fontWeight: 700, letterSpacing: 1, color: '#888', textTransform: 'uppercase', marginBottom: 3 }}>Order Details</div>
          {[
            ['Order No',      data.order_no],
            ['Order Date',    fmtDate(data.date1)],
            ['Delivery Date', fmtDate(data.delivery_date)],
          ].map(([lbl, val]) => (
            <div key={lbl}>
              <span style={{ color: '#777', display: 'inline-block', minWidth: 76 }}>{lbl}</span>
              <span style={{ fontWeight: 600, color: '#0f172a' }}>{val || '—'}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ── Fixed gold rates (only when fix_gold_rate = true) ── */}
      {showGoldRates && (
        <div style={{
          display: 'flex', alignItems: 'baseline', gap: 18,
          padding: '6px 0', borderTop: '1px solid #e2e8f0', borderBottom: '1px solid #e2e8f0',
          marginBottom: 10, fontVariantNumeric: 'tabular-nums', fontFamily: FONT,
        }}>
          <span style={{ fontSize: 7.5, letterSpacing: '1.4px', textTransform: 'uppercase', color: '#64748b', fontWeight: 700 }}>Fixed Gold Rates</span>
          {data.rate_14kt ? <span style={{ fontSize: 10, color: '#0f172a', fontWeight: 500 }}>14K &nbsp;₹ {formatNumber(data.rate_14kt)} / gm</span> : null}
          {data.rate_14kt && data.rate_18kt ? <span style={{ color: '#cbd5e1' }}>·</span> : null}
          {data.rate_18kt ? <span style={{ fontSize: 10, color: '#0f172a', fontWeight: 500 }}>18K &nbsp;₹ {formatNumber(data.rate_18kt)} / gm</span> : null}
          {data.rate_18kt && data.rate_22kt ? <span style={{ color: '#cbd5e1' }}>·</span> : null}
          {data.rate_22kt ? <span style={{ fontSize: 10, color: '#0f172a', fontWeight: 500 }}>22K &nbsp;₹ {formatNumber(data.rate_22kt)} / gm</span> : null}
        </div>
      )}

      {/* ── Advance / value summary ── */}
      {showAdvance && (
        <div style={{ display: 'flex', border: '1px solid #e2e8f0', borderRadius: 4, marginBottom: 10, overflow: 'hidden', background: '#f8fafc' }}>
          {[
            { lbl: 'Estimated Value',   val: fmtAmt(data.est_amount),        color: '#0f172a' },
            { lbl: 'Advance Received',  val: fmtAmt(data.advance_amt),       color: '#0f172a' },
            { lbl: 'Advance Available', val: fmtAmt(data.advance_available), color: '#166534' },
          ].map(({ lbl, val }, i) => (
            <div key={i} style={{
              flex: 1, padding: '7px 10px', textAlign: 'center',
              borderRight: i < 2 ? '1px solid #e2e8f0' : 'none',
            }}>
              <div style={{ fontSize: 7, letterSpacing: '1.4px', textTransform: 'uppercase', color: '#64748b', fontWeight: 700, fontFamily: FONT }}>{lbl}</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#0f172a', marginTop: 2, fontVariantNumeric: 'tabular-nums', fontFamily: FONT, color: i === 2 ? '#166534' : '#0f172a' }}>{val}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Items table ── */}
      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'auto', fontFamily: FONT }}>
        <colgroup>
          <col style={{ width: 20  }} />{/* Sl */}
          <col                       />{/* Item */}
          <col style={{ width: 32  }} />{/* Purity */}
          <col style={{ width: 26  }} />{/* Pcs */}
          <col style={{ width: 52  }} />{/* Wt */}
          <col style={{ width: 28  }} />{/* Size */}
          <col style={{ width: 54  }} />{/* Making Type */}
          <col style={{ width: 52  }} />{/* Making ₹ */}
          <col                       />{/* Remarks */}
        </colgroup>
        <thead>
          <tr>
            <th style={th0({ textAlign: 'center' })}>Sl</th>
            <th style={th0({ textAlign: 'left'   })}>Item</th>
            <th style={th({  textAlign: 'center' })}>Purity</th>
            <th style={th({  textAlign: 'center' })}>Pcs</th>
            <th style={th({  textAlign: 'right'  })}>Wt (g)</th>
            <th style={th({  textAlign: 'center' })}>Size</th>
            <th style={th({  textAlign: 'center' })}>Making Type</th>
            <th style={th({  textAlign: 'right'  })}>Making (₹)</th>
            <th style={th({  textAlign: 'left'   })}>Remarks</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row, idx) => (
            <tr key={idx} style={{ borderBottom: '1px solid #efefef' }}>
              <td style={td0({ textAlign: 'center' })}>{row.sl_no ?? idx + 1}</td>
              <td style={td0({ textAlign: 'left'   })}>{row.item_name || row.item_id || '—'}</td>
              <td style={td({  textAlign: 'center' })}>{row.purity || '—'}</td>
              <td style={td({  textAlign: 'center' })}>{row.pcs || '—'}</td>
              <td style={td({  textAlign: 'right'  })}>{fmtWt(row.gw)}</td>
              <td style={td({  textAlign: 'center' })}>{row.size || '—'}</td>
              <td style={td({  textAlign: 'center', fontSize: 9 })}>{MAKING_LABELS[row.making_type] || row.making_type || '—'}</td>
              <td style={td({  textAlign: 'right'  })}>
                {row.making_amt ? formatNumber(row.making_amt) : '—'}
              </td>
              <td style={td({  textAlign: 'left', fontSize: 9, color: '#555' })}>{row.remarks || ''}</td>
            </tr>
          ))}
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
          This is a preliminary order acknowledgement, not a tax invoice.<br />
          Final billing will be done at the time of delivery.<br />
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

export default CustomerOrderPrint;

