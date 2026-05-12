import React from 'react';

// ── helpers ──────────────────────────────────────────────────────────────────

const fmtN = (v, d = 3) => {
  const n = parseFloat(v);
  return isNaN(n) || n === 0 ? '' : n.toFixed(d);
};

const fmtC = (v, d = 2) => {
  const n = parseFloat(v);
  if (isNaN(n) || n === 0) return '';
  return n.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
};

const fmtCForce = (v, d = 2) => {
  const n = parseFloat(v) || 0;
  return n.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });
};

const getItemTotals = (data) => {
  const stoneItems = (data.main_item_set || []).filter((i) => i.item !== 'Gold');
  const metalItem  = (data.main_item_set || []).find((i) => i.item === 'Gold');
  const totalStoneCt    = stoneItems.reduce((s, i) => s + (parseFloat(i.ct)  || 0), 0);
  const totalStoneValue = stoneItems.reduce((s, i) => s + (parseFloat(i.amt) || 0), 0);
  const totalMetalValue = metalItem ? parseFloat(metalItem.amt) || 0 : 0;
  const totalOtherValue = parseFloat(data.other_chg) || 0;
  const totalMakingValue = parseFloat(data.making)   || 0;
  const productValue = totalStoneValue + totalMetalValue + totalOtherValue + totalMakingValue;
  const gstAmt   = productValue * 0.03;
  const billValue = productValue + gstAmt;
  return { stoneItems, metalItem, totalStoneCt, totalStoneValue, totalMetalValue, totalOtherValue, totalMakingValue, productValue, gstAmt, billValue };
};

// ── style constants ───────────────────────────────────────────────────────────

const FONT = "'Arial', sans-serif";
const BASE = 10;

const cell = (extra = {}) => ({
  border: '1px solid #aaa',
  padding: '3px 5px',
  fontSize: BASE,
  fontFamily: FONT,
  verticalAlign: 'middle',
  ...extra,
});

const hdrCell = (extra = {}) => ({
  border: '1px solid #555',
  padding: '3px 5px',
  fontSize: BASE,
  fontWeight: 700,
  fontFamily: FONT,
  background: '#e8e8e8',
  textAlign: 'center',
  verticalAlign: 'middle',
  whiteSpace: 'nowrap',
  ...extra,
});

const itemHdr = (extra = {}) => ({
  border: '1px solid #888',
  padding: '4px 6px',
  fontSize: BASE + 1,
  fontWeight: 700,
  fontFamily: FONT,
  background: '#f0f0f0',
  verticalAlign: 'middle',
  ...extra,
});

// ── Column definitions ────────────────────────────────────────────────────────
// Total 13 cols; widths are relative hints — browser distributes rest.
const COLS = [
  { key: 'sl',       label: 'Sl',           w: 22,  align: 'center' },
  { key: 'desc',     label: 'Description',  w: null, align: 'left'   },
  { key: 'pcs',      label: 'Pcs',          w: 28,  align: 'center' },
  { key: 'gw',       label: 'GW (g)',       w: 44,  align: 'right'  },
  { key: 'nw',       label: 'NW (g)',       w: 44,  align: 'right'  },
  { key: 'ct',       label: 'Ct',           w: 38,  align: 'right'  },
  { key: 'rate',     label: 'Rate',         w: 54,  align: 'right'  },
  { key: 'metalval', label: 'Metal Val',    w: 60,  align: 'right'  },
  { key: 'stoneval', label: 'Stone Val',    w: 60,  align: 'right'  },
  { key: 'mkrate',   label: 'Mkng Rate',    w: 52,  align: 'right'  },
  { key: 'mkval',    label: 'Mkng Val',     w: 58,  align: 'right'  },
  { key: 'prodval',  label: 'Prod Val',     w: 62,  align: 'right'  },
];
const NCOLS = COLS.length;

// ── Blank sub-row cell ────────────────────────────────────────────────────────

const BC = ({ w, style }) => (
  <td style={{ ...cell({ width: w, ...style }), borderColor: '#ccc' }} />
);

// ── Per-barcode block ─────────────────────────────────────────────────────────

const ItemBlock = ({ data, idx }) => {
  const t = getItemTotals(data);

  const makingLabel = [
    data.making_rate ? `₹${fmtCForce(data.making_rate)}` : null,
    data.making_type || null,
  ].filter(Boolean).join(' / ');

  return (
    <>
      {/* ── Barcode header row ─── */}
      <tr>
        <td style={itemHdr({ textAlign: 'center', width: COLS[0].w })}>{idx + 1}</td>
        <td colSpan={NCOLS - 1} style={itemHdr({ textAlign: 'left' })}>
          <span style={{ fontFamily: 'monospace', fontSize: BASE + 1 }}>
            {data.barcode || data.voucher_no || '—'}
          </span>
          {' '}
          <span style={{ fontWeight: 400, color: '#333' }}>
            {data.item}{data.purity_name ? ` · ${data.purity_name}` : data.purity ? ` · ${data.purity}K` : ''}
          </span>
          <span style={{ float: 'right', fontWeight: 400, fontSize: BASE, color: '#444' }}>
            {data.pcs ? `${data.pcs} Pcs` : ''}
            {data.gw  ? `  ·  GW: ${fmtN(data.gw)} g` : ''}
            {data.nw  ? `  ·  NW: ${fmtN(data.nw)} g` : ''}
          </span>
        </td>
      </tr>

      {/* ── Metal (Gold) row ─── */}
      {t.metalItem && (
        <tr>
          <BC w={COLS[0].w} />
          <td style={cell({ textAlign: 'left', color: '#333' })}>
            <span style={{ color: '#999', marginRight: 4 }}>↳</span>
            <strong>Gold</strong>
            {t.metalItem.purity ? ` (${t.metalItem.purity})` : ''}
            {t.metalItem.packet ? <span style={{ color: '#666', fontSize: BASE - 1 }}> · Pkt: {t.metalItem.packet}</span> : ''}
          </td>
          <td style={cell({ textAlign: 'center' })}>{t.metalItem.pcs || ''}</td>
          <td style={cell({ textAlign: 'right' })}>{fmtN(t.metalItem.gw)}</td>
          <td style={cell({ textAlign: 'right' })}></td>
          <td style={cell({ textAlign: 'right', fontStyle: 'italic', color: '#555' })}>
            {fmtN(t.metalItem.ct)}
          </td>
          <td style={cell({ textAlign: 'right' })}>{fmtC(t.metalItem.rate, 0)}</td>
          <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtC(t.metalItem.amt)}</td>
          <td style={cell({ textAlign: 'right' })}></td>
          <td style={cell({ textAlign: 'right' })}></td>
          <td style={cell({ textAlign: 'right' })}></td>
          <td style={cell({ textAlign: 'right' })}></td>
        </tr>
      )}

      {/* ── Stone / other sub-item rows ─── */}
      {t.stoneItems.map((si, i) => (
        <tr key={i}>
          <BC w={COLS[0].w} />
          <td style={cell({ textAlign: 'left', color: '#333' })}>
            <span style={{ color: '#999', marginRight: 4 }}>↳</span>
            <strong>{si.item_name || si.item}</strong>
            {si.purity ? ` (${si.purity})` : ''}
            {si.packet ? <span style={{ color: '#666', fontSize: BASE - 1 }}> · Pkt: {si.packet}</span> : ''}
          </td>
          <td style={cell({ textAlign: 'center' })}>{si.pcs || ''}</td>
          <td style={cell({ textAlign: 'right' })}>{fmtN(si.gw)}</td>
          <td style={cell({ textAlign: 'right' })}></td>
          <td style={cell({ textAlign: 'right' })}>{fmtN(si.ct)}</td>
          <td style={cell({ textAlign: 'right' })}>{fmtC(si.rate, 0)}</td>
          <td style={cell({ textAlign: 'right' })}></td>
          <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtC(si.amt)}</td>
          <td style={cell({ textAlign: 'right' })}></td>
          <td style={cell({ textAlign: 'right' })}></td>
          <td style={cell({ textAlign: 'right' })}></td>
        </tr>
      ))}

      {/* ── Making charges row ─── */}
      {t.totalMakingValue > 0 && (
        <tr>
          <BC w={COLS[0].w} />
          <td style={cell({ textAlign: 'left', color: '#555', fontStyle: 'italic' })}>
            <span style={{ color: '#999', marginRight: 4 }}>↳</span>
            Making Charges
          </td>
          <td style={cell()}></td>
          <td style={cell()}></td>
          <td style={cell()}></td>
          <td style={cell()}></td>
          <td style={cell()}></td>
          <td style={cell()}></td>
          <td style={cell()}></td>
          <td style={cell({ textAlign: 'right', fontSize: BASE - 1, color: '#555' })}>{makingLabel}</td>
          <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtC(t.totalMakingValue)}</td>
          <td style={cell()}></td>
        </tr>
      )}

      {/* ── Per-item subtotal row ─── */}
      <tr style={{ background: '#fafafa' }}>
        <BC w={COLS[0].w} style={{ borderColor: '#aaa' }} />
        <td style={cell({ textAlign: 'right', fontSize: BASE - 1, color: '#555', fontStyle: 'italic' })}>
          Sub-total
        </td>
        <td style={cell({ textAlign: 'center', fontWeight: 600 })}>{data.pcs || ''}</td>
        <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtN(data.gw)}</td>
        <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtN(data.nw)}</td>
        <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtN(t.totalStoneCt) || ''}</td>
        <td style={cell()}></td>
        <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtC(t.totalMetalValue)}</td>
        <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtC(t.totalStoneValue)}</td>
        <td style={cell()}></td>
        <td style={cell({ textAlign: 'right', fontWeight: 600 })}>{fmtC(t.totalMakingValue)}</td>
        <td style={cell({ textAlign: 'right', fontWeight: 700, fontSize: BASE + 1 })}>{fmtCForce(t.productValue)}</td>
      </tr>
    </>
  );
};

// ── Main export ───────────────────────────────────────────────────────────────

export const MultiEstimatePrint = ({ items = [] }) => {
  const currentDate = new Date().toLocaleDateString('en-IN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  });

  const grand = items.reduce(
    (acc, item) => {
      const t = getItemTotals(item);
      return {
        pcs:        acc.pcs        + (parseInt(item.pcs)   || 0),
        gw:         acc.gw         + (parseFloat(item.gw)  || 0),
        nw:         acc.nw         + (parseFloat(item.nw)  || 0),
        stoneCt:    acc.stoneCt    + t.totalStoneCt,
        stoneVal:   acc.stoneVal   + t.totalStoneValue,
        metalVal:   acc.metalVal   + t.totalMetalValue,
        making:     acc.making     + t.totalMakingValue,
        productVal: acc.productVal + t.productValue,
        gstAmt:     acc.gstAmt     + t.gstAmt,
        billVal:    acc.billVal    + t.billValue,
      };
    },
    { pcs: 0, gw: 0, nw: 0, stoneCt: 0, stoneVal: 0, metalVal: 0, making: 0, productVal: 0, gstAmt: 0, billVal: 0 }
  );

  const footerCell = (extra = {}) => ({
    border: '1px solid #555',
    padding: '4px 6px',
    fontSize: BASE,
    fontFamily: FONT,
    fontWeight: 700,
    background: '#e8e8e8',
    verticalAlign: 'middle',
    ...extra,
  });

  return (
    <div style={{ padding: '16px 20px', maxWidth: 900, margin: '0 auto', fontFamily: FONT }}>

      {/* Date line */}
      <div style={{ textAlign: 'right', fontSize: BASE, marginBottom: 10, color: '#555' }}>
        Date: {currentDate}&nbsp;&nbsp;·&nbsp;&nbsp;Items: {items.length}
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'auto' }}>
        {/* Column width hints */}
        <colgroup>
          {COLS.map((c) => (
            <col key={c.key} style={c.w ? { width: c.w } : {}} />
          ))}
        </colgroup>

        {/* ── Table header ── */}
        <thead>
          <tr>
            {COLS.map((c) => (
              <th key={c.key} style={hdrCell({ textAlign: c.align, width: c.w || undefined })}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>

        {/* ── Item blocks ── */}
        <tbody>
          {items.map((item, idx) => (
            <ItemBlock key={item._key || idx} data={item} idx={idx} />
          ))}
        </tbody>

        {/* ── Grand totals footer ── */}
        <tfoot>
          {/* Grand total row */}
          <tr>
            <td colSpan={2} style={footerCell({ textAlign: 'center' })}>
              Grand Total · {items.length} item{items.length !== 1 ? 's' : ''}
            </td>
            <td style={footerCell({ textAlign: 'center' })}>{grand.pcs}</td>
            <td style={footerCell({ textAlign: 'right' })}>{fmtN(grand.gw)}</td>
            <td style={footerCell({ textAlign: 'right' })}>{fmtN(grand.nw)}</td>
            <td style={footerCell({ textAlign: 'right' })}>{fmtN(grand.stoneCt) || ''}</td>
            <td style={footerCell({ textAlign: 'right' })}></td>
            <td style={footerCell({ textAlign: 'right' })}>{fmtCForce(grand.metalVal)}</td>
            <td style={footerCell({ textAlign: 'right' })}>{fmtCForce(grand.stoneVal)}</td>
            <td style={footerCell({ textAlign: 'right' })}></td>
            <td style={footerCell({ textAlign: 'right' })}>{fmtCForce(grand.making)}</td>
            <td style={footerCell({ textAlign: 'right', fontSize: BASE + 1 })}>{fmtCForce(grand.productVal)}</td>
          </tr>

          {/* GST 3% */}
          <tr>
            <td colSpan={NCOLS - 1} style={{ ...footerCell({ textAlign: 'right', fontWeight: 400, background: '#fff' }), borderColor: '#aaa' }}>
              GST @ 3%
            </td>
            <td style={footerCell({ textAlign: 'right', background: '#fff', borderColor: '#aaa' })}>
              {fmtCForce(grand.gstAmt)}
            </td>
          </tr>

          {/* Bill Value */}
          <tr>
            <td colSpan={NCOLS - 1} style={footerCell({ textAlign: 'right', fontSize: BASE + 2, background: '#d4edda' })}>
              Total Estimate Value (incl. GST)
            </td>
            <td style={footerCell({ textAlign: 'right', fontSize: BASE + 3, background: '#d4edda', color: '#155724' })}>
              ₹&nbsp;{fmtCForce(grand.billVal, 0)}
            </td>
          </tr>
        </tfoot>
      </table>

      {/* Disclaimer */}
      <div style={{ marginTop: 14, fontSize: BASE - 1, color: '#888', textAlign: 'center', fontStyle: 'italic' }}>
        This is an estimate only. Gold rate used is the latest available market rate and may vary at time of billing.
      </div>
    </div>
  );
};

// Legacy single-item shim
export const JewelryEstimateTable = ({ data }) => (
  <MultiEstimatePrint items={[{ ...data, _key: 1 }]} />
);

export default JewelryEstimateTable;
