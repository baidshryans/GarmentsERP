import React from 'react';

// ── helpers ──────────────────────────────────────────────────────────────────

const fmtN = (v, d = 3) => {
  const n = parseFloat(v);
  return isNaN(n) ? '—' : n.toFixed(d);
};

const getItemTotals = (data) => {
  const stoneItems = (data.main_item_set || []).filter((i) => i.item !== 'GOLD');
  const metalItem  = (data.main_item_set || []).find((i) => i.item === 'GOLD');
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

// ── Cell / Header primitives ──────────────────────────────────────────────────

const TH = ({ children, colSpan, rowSpan, style }) => (
  <th
    colSpan={colSpan}
    rowSpan={rowSpan}
    style={{
      border: '1px solid #000',
      padding: '4px 6px',
      textAlign: 'center',
      fontSize: 11,
      fontWeight: 600,
      background: '#f3f4f6',
      ...style,
    }}
  >
    {children}
  </th>
);

const TD = ({ children, right, bold, colSpan, style }) => (
  <td
    colSpan={colSpan}
    style={{
      border: '1px solid #000',
      padding: '4px 6px',
      textAlign: right ? 'right' : 'center',
      fontSize: 11,
      fontWeight: bold ? 700 : 400,
      ...style,
    }}
  >
    {children}
  </td>
);

// ── Single barcode row ────────────────────────────────────────────────────────

const ItemRow = ({ data, idx }) => {
  const t = getItemTotals(data);
  return (
    <tr>
      <TD>{idx + 1}</TD>
      <TD style={{ textAlign: 'left' }}>
        <div style={{ fontWeight: 600 }}>
          {data.barcode || data.voucher_no || '—'}
        </div>
        <div>
          {data.item} {data.purity ? `(${data.purity}K)` : ''}
        </div>
        {t.stoneItems.map((si, i) => (
          <div key={i} style={{ fontSize: 10, color: '#555' }}>
            {si.item} {si.ct > 0 ? `${fmtN(si.ct)}Ct` : ''} {si.packet ? `(${si.packet})` : ''}
          </div>
        ))}
        {data.item && <div style={{ fontSize: 10, color: '#555' }}>{data.item} Charges</div>}
      </TD>
      <TD>{data.pcs || 0}</TD>
      <TD>{fmtN(data.gw)}</TD>
      <TD>{fmtN(data.nw)}</TD>
      <TD>{fmtN(t.totalStoneCt)}</TD>
      <TD style={{ textAlign: 'left', fontSize: 10 }}>
        {t.metalItem && <div>{t.metalItem.rate}</div>}
        {t.stoneItems.map((si, i) => <div key={i}>{si.rate}</div>)}
      </TD>
      <TD right>{fmtN(t.totalStoneValue, 2)}</TD>
      <TD right>{fmtN(t.totalMetalValue, 2)}</TD>
      <TD right>{fmtN(t.totalOtherValue, 2)}</TD>
      <TD right>{fmtN(t.totalMakingValue, 2)}</TD>
      <TD right bold>{fmtN(t.productValue, 2)}</TD>
    </tr>
  );
};

// ── Main multi-item print component ──────────────────────────────────────────

export const MultiEstimatePrint = ({ items = [] }) => {
  const currentDate = new Date().toLocaleDateString('en-IN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
  });

  // Grand totals
  const grand = items.reduce(
    (acc, item) => {
      const t = getItemTotals(item);
      return {
        pcs:       acc.pcs       + (parseInt(item.pcs)  || 0),
        gw:        acc.gw        + (parseFloat(item.gw) || 0),
        nw:        acc.nw        + (parseFloat(item.nw) || 0),
        stoneCt:   acc.stoneCt   + t.totalStoneCt,
        stoneVal:  acc.stoneVal  + t.totalStoneValue,
        metalVal:  acc.metalVal  + t.totalMetalValue,
        otherVal:  acc.otherVal  + t.totalOtherValue,
        making:    acc.making    + t.totalMakingValue,
        productVal:acc.productVal+ t.productValue,
        gstAmt:    acc.gstAmt   + t.gstAmt,
        billVal:   acc.billVal   + t.billValue,
      };
    },
    { pcs: 0, gw: 0, nw: 0, stoneCt: 0, stoneVal: 0, metalVal: 0, otherVal: 0, making: 0, productVal: 0, gstAmt: 0, billVal: 0 }
  );

  return (
    <div style={{ padding: 24, maxWidth: 960, margin: '0 auto', fontFamily: 'Arial, sans-serif' }}>

      {/* Title */}
      <h1 style={{ textAlign: 'center', fontSize: 18, fontWeight: 700, marginBottom: 12, letterSpacing: 2 }}>
        ESTIMATE
      </h1>

      {/* Customer / Memo header */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <div style={{ flex: 2, border: '1px solid #000', borderRadius: 4, padding: '10px 14px' }}>
          <div><strong>Name:</strong></div>
          <div style={{ marginTop: 4 }}><strong>Address:</strong></div>
        </div>
        <div style={{ flex: 1, border: '1px solid #000', borderRadius: 4, padding: '10px 14px' }}>
          <div><strong>Date:</strong> {currentDate}</div>
          <div style={{ marginTop: 4 }}><strong>Items:</strong> {items.length}</div>
        </div>
      </div>

      {/* Main table */}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <TH rowSpan={2} style={{ width: 28 }}>Sl.</TH>
            <TH rowSpan={2}>Item Description</TH>
            <TH rowSpan={2} style={{ width: 32 }}>Pcs</TH>
            <TH rowSpan={2} style={{ width: 46 }}>Gr Wt</TH>
            <TH rowSpan={2} style={{ width: 46 }}>Net Wt</TH>
            <TH rowSpan={2} style={{ width: 50 }}>Stone Wt (Ct)</TH>
            <TH rowSpan={2} style={{ width: 56 }}>Rate</TH>
            <TH rowSpan={2} style={{ width: 58 }}>Stone Value</TH>
            <TH rowSpan={2} style={{ width: 58 }}>Metal Value</TH>
            <TH rowSpan={2} style={{ width: 54 }}>Other</TH>
            <TH rowSpan={2} style={{ width: 54 }}>Making</TH>
            <TH rowSpan={2} style={{ width: 70 }}>Product Value</TH>
          </tr>
          {/* spacer row for rowSpan=2 to render correctly — empty row */}
          <tr style={{ display: 'none' }}><td /></tr>
        </thead>

        <tbody>
          {items.map((item, idx) => (
            <ItemRow key={item._key || idx} data={item} idx={idx} />
          ))}
        </tbody>

        {/* Grand total row */}
        <tfoot>
          <tr style={{ background: '#e5e7eb' }}>
            <TD colSpan={2} bold>Total ({items.length} items)</TD>
            <TD bold>{grand.pcs}</TD>
            <TD bold>{fmtN(grand.gw)}</TD>
            <TD bold>{fmtN(grand.nw)}</TD>
            <TD bold>{fmtN(grand.stoneCt)}</TD>
            <TD />
            <TD right bold>{fmtN(grand.stoneVal, 2)}</TD>
            <TD right bold>{fmtN(grand.metalVal, 2)}</TD>
            <TD right bold>{fmtN(grand.otherVal, 2)}</TD>
            <TD right bold>{fmtN(grand.making, 2)}</TD>
            <TD right bold>{fmtN(grand.productVal, 2)}</TD>
          </tr>

          {/* GST row */}
          <tr>
            <td
              colSpan={11}
              style={{ border: '1px solid #000', padding: '4px 6px', textAlign: 'right', fontSize: 11, fontWeight: 600 }}
            >
              GST 3%
            </td>
            <TD right bold>{fmtN(grand.gstAmt, 2)}</TD>
          </tr>

          {/* Bill Value row */}
          <tr>
            <td
              colSpan={11}
              style={{ border: '1px solid #000', padding: '4px 6px', textAlign: 'right', fontSize: 13, fontWeight: 700 }}
            >
              Bill Value
            </td>
            <TD right bold style={{ fontSize: 13 }}>
              ₹ {fmtN(grand.billVal, 0)}
            </TD>
          </tr>
        </tfoot>
      </table>

      {/* Signature area */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 40, paddingTop: 16, borderTop: '1px solid #ccc' }}>
        <div style={{ fontSize: 11, color: '#555' }}>Customer Signature</div>
        <div style={{ fontSize: 11, color: '#555' }}>Authorised Signatory</div>
      </div>
    </div>
  );
};

// ── Legacy single-item component (kept for backward compatibility) ─────────────

export const JewelryEstimateTable = ({ data }) => (
  <MultiEstimatePrint items={[{ ...data, _key: 1 }]} />
);

export default JewelryEstimateTable;
