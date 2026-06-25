import React from 'react';
import { formatNumber } from '@/lib/format';

// ── helpers ───────────────────────────────────────────────────────────────────

const fmtN = (v, d = 3) => {
  const n = parseFloat(v);
  return isNaN(n) || n === 0 ? '' : n.toFixed(d);
};

const fmtC = (v, d = 0) => {
  const n = parseFloat(v);
  if (isNaN(n) || n === 0) return '';
  return formatNumber(n, { decimals: d });
};

const fmtCForce = (v, d = 0) => {
  const n = parseFloat(v) || 0;
  return formatNumber(n, { decimals: d });
};

const getItemTotals = (data) => {
  const stoneItems      = (data.main_item_set || []).filter((i) => i.item !== 'Gold');
  const metalItem       = (data.main_item_set || []).find((i) => i.item === 'Gold');
  const totalStoneCt    = stoneItems.reduce((s, i) => s + (parseFloat(i.ct)  || 0), 0);
  const totalStoneValue = stoneItems.reduce((s, i) => s + (parseFloat(i.amt) || 0), 0);
  const totalMetalValue = metalItem ? parseFloat(metalItem.amt) || 0 : 0;
  const totalOtherValue = parseFloat(data.other_chg) || 0;
  const totalMakingValue = parseFloat(data.making)   || 0;
  const productValue    = totalStoneValue + totalMetalValue + totalOtherValue + totalMakingValue;
  const gstAmt          = productValue * 0.03;
  const billValue       = productValue + gstAmt;
  return { stoneItems, metalItem, totalStoneCt, totalStoneValue, totalMetalValue,
           totalOtherValue, totalMakingValue, productValue, gstAmt, billValue };
};

// ── Design tokens ─────────────────────────────────────────────────────────────

const FONT  = 'Arial, Helvetica, sans-serif';
const BASE  = 10;
// Columns: Sl | Description | Pkt | Pcs | GW | NW | Ct | Rate | Metal Val | Stone Val | Making | Prod Val
const NCOLS = 12;

const cell = (extra = {}) => ({
  borderLeft: '1px solid #ddd', borderTop: 'none', borderBottom: 'none', borderRight: 'none',
  padding: '3px 5px', fontSize: BASE, fontFamily: FONT, verticalAlign: 'middle', lineHeight: 1.35,
  ...extra,
});
const cell0 = (extra = {}) => cell({ borderLeft: 'none', ...extra });

const th = (extra = {}) => ({
  borderLeft: '1px solid #bbb', borderTop: '1px solid #aaa', borderBottom: '1px solid #aaa', borderRight: 'none',
  padding: '4px 5px', fontSize: 9.5, fontWeight: 700, fontFamily: FONT,
  background: '#fff', textAlign: 'center', whiteSpace: 'nowrap', lineHeight: 1.3,
  ...extra,
});
const th0 = (extra = {}) => th({ borderLeft: 'none', ...extra });

const hdrCell = (extra = {}) => ({
  ...cell(extra),
  background: '#f2f2f2', fontWeight: 700, fontSize: BASE + 0.5,
  borderTop: '1px solid #bbb', borderBottom: '1px solid #bbb',
});
const hdrCell0 = (extra = {}) => hdrCell({ borderLeft: 'none', ...extra });

const subTotCell = (extra = {}) => ({
  ...cell(extra),
  background: '#f8f8f8', fontSize: 9, borderTop: '1px solid #ccc',
});
const subTotCell0 = (extra = {}) => subTotCell({ borderLeft: 'none', ...extra });

const gtCell = (extra = {}) => ({
  ...cell(extra),
  background: '#f2f2f2', fontWeight: 700, fontSize: BASE,
  borderTop: '1px solid #aaa', borderBottom: '1px solid #bbb',
});
const gtCell0 = (extra = {}) => gtCell({ borderLeft: 'none', ...extra });

const gstCell  = (extra = {}) => ({ ...cell(extra),  background: '#fff', fontSize: 9.5 });
const gstCell0 = (extra = {}) => gstCell({ borderLeft: 'none', ...extra });

const billCell  = (extra = {}) => ({
  ...cell(extra), background: '#fff', fontWeight: 700, fontSize: BASE,
  borderTop: '1px solid #aaa', borderBottom: '1px solid #aaa',
});
const billCell0 = (extra = {}) => billCell({ borderLeft: 'none', ...extra });

// ── Per-barcode block ─────────────────────────────────────────────────────────

const ItemBlock = ({ data, idx, totalItems }) => {
  const t = getItemTotals(data);

  const purityLabel = data.purity_name || (data.purity ? `${data.purity}K` : '');
  const itemLabel   = [data.item_name || data.item, purityLabel].filter(Boolean).join(' · ');

  // Gold rate from the metal sub-item, formatted for display
  const goldRate = t.metalItem?.rate
    ? formatNumber(t.metalItem.rate, { maxDecimals: 0 })
    : '';

  return (
    <>
      {/* ── Main item row — gold rate, metal val, making and product value ── */}
      <tr>
        <td style={hdrCell0({ textAlign: 'center', width: 24 })}>{idx + 1}</td>
        <td style={hdrCell({ textAlign: 'left' })}>{itemLabel}</td>
        <td style={hdrCell()} />
        <td style={hdrCell({ textAlign: 'center' })}>{data.pcs || ''}</td>
        <td style={hdrCell({ textAlign: 'right', fontFamily: FONT })}>{fmtN(data.gw)}</td>
        <td style={hdrCell({ textAlign: 'right', fontFamily: FONT })}>{fmtN(data.nw)}</td>
        <td style={hdrCell()} />
        <td style={hdrCell({ textAlign: 'right' })}>{goldRate}</td>
        <td style={hdrCell({ textAlign: 'right' })}>{fmtC(t.totalMetalValue)}</td>
        <td style={hdrCell()} />
        <td style={hdrCell({ textAlign: 'right' })}>{fmtC(t.totalMakingValue)}</td>
        <td style={hdrCell({ textAlign: 'right', fontSize: BASE + 1 })}>{fmtCForce(t.productValue)}</td>
      </tr>

      {/* ── Stone / other sub-item rows ── */}
      {t.stoneItems.map((si, i) => (
        <tr key={i}>
          <td style={cell0()} />
          <td style={cell({ textAlign: 'left' })}>
                        {si.item_name || si.item}
            {si.purity
              ? <span style={{ color: '#888', fontSize: 9 }}> ({si.purity})</span>
              : null}
          </td>
          <td style={cell({ textAlign: 'left', fontSize: 9, color: '#555' })}>{si.packet || ''}</td>
          <td style={cell({ textAlign: 'center' })}>{si.pcs || ''}</td>
          <td style={cell({ textAlign: 'right', fontFamily: FONT })}>{fmtN(si.gw)}</td>
          <td style={cell()} />
          <td style={cell({ textAlign: 'right' })}>{fmtN(si.ct)}</td>
          <td style={cell({ textAlign: 'right' })}>{fmtC(si.rate, 0)}</td>
          <td style={cell()} />
          <td style={cell({ textAlign: 'right' })}>{fmtC(si.amt)}</td>
          <td style={cell()} />
          <td style={cell()} />
        </tr>
      ))}

      {/* ── Per-item subtotal — hidden when only 1 item (same as grand total) ── */}
      {totalItems > 1 && (
        <tr>
          <td style={subTotCell0()} />
          <td style={subTotCell({ textAlign: 'right', color: '#777', fontStyle: 'italic' })}>Sub-total</td>
          <td style={subTotCell()} />
          <td style={subTotCell({ textAlign: 'center', fontWeight: 700 })}>{data.pcs || ''}</td>
          <td style={subTotCell({ textAlign: 'right', fontWeight: 700 })}>{fmtN(data.gw)}</td>
          <td style={subTotCell({ textAlign: 'right', fontWeight: 700 })}>{fmtN(data.nw)}</td>
          <td style={subTotCell({ textAlign: 'right', fontWeight: 700 })}>{fmtN(t.totalStoneCt)}</td>
          <td style={subTotCell()} />
          <td style={subTotCell({ textAlign: 'right', fontWeight: 700 })}>{fmtC(t.totalMetalValue)}</td>
          <td style={subTotCell({ textAlign: 'right', fontWeight: 700 })}>{fmtC(t.totalStoneValue)}</td>
          <td style={subTotCell({ textAlign: 'right', fontWeight: 700 })}>{fmtC(t.totalMakingValue)}</td>
          <td style={subTotCell({ textAlign: 'right', fontWeight: 700, fontSize: BASE + 1 })}>{fmtCForce(t.productValue)}</td>
        </tr>
      )}

      {/* Spacer between barcodes */}
      <tr>
        <td colSpan={NCOLS} style={{ height: 4, border: 'none', padding: 0 }} />
      </tr>
    </>
  );
};

// ── Main export ───────────────────────────────────────────────────────────────

export const MultiEstimatePrint = ({ items = [] }) => {
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

  return (
    <div style={{ padding: '16px 20px', maxWidth: 960, margin: '0 auto', fontFamily: FONT }}>

      {/* ESTIMATE heading */}
      <h1 style={{
        textAlign: 'center', fontSize: 18, fontWeight: 700,
        fontFamily: FONT, letterSpacing: 3, marginBottom: 10,
      }}>
        ESTIMATE
      </h1>


      {/* Main table */}
      <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'auto', fontFamily: FONT }}>
        <colgroup>
          <col style={{ width: 24  }} />{/* Sl */}
          <col                       />{/* Description — flexible */}
          <col style={{ width: 62  }} />{/* Packet No */}
          <col style={{ width: 30  }} />{/* Pcs */}
          <col style={{ width: 46  }} />{/* GW */}
          <col style={{ width: 46  }} />{/* NW */}
          <col style={{ width: 40  }} />{/* Ct */}
          <col style={{ width: 56  }} />{/* Rate */}
          <col style={{ width: 64  }} />{/* Metal Val */}
          <col style={{ width: 64  }} />{/* Stone Val */}
          <col style={{ width: 60  }} />{/* Making */}
          <col style={{ width: 68  }} />{/* Prod Val */}
        </colgroup>

        <thead>
          {/* Row 1 — group headers */}
          <tr>
            <th rowSpan={2} style={th0({ textAlign: 'center', verticalAlign: 'middle' })}>Sl</th>
            <th rowSpan={2} style={th0({ textAlign: 'left',   verticalAlign: 'middle' })}>Description</th>
            <th rowSpan={2} style={th({  textAlign: 'left',   verticalAlign: 'middle' })}>Packet No</th>
            <th rowSpan={2} style={th({  textAlign: 'center', verticalAlign: 'middle' })}>Pcs</th>
            {/* GW + NW grouped under "Metal (Gm)" */}
            <th colSpan={2} style={th({ textAlign: 'center', borderBottom: '1px solid #bbb' })}>Metal (Gm)</th>
            <th rowSpan={2} style={th({  textAlign: 'right',  verticalAlign: 'middle' })}>Ct</th>
            <th rowSpan={2} style={th({  textAlign: 'right',  verticalAlign: 'middle' })}>Rate</th>
            <th rowSpan={2} style={th({  textAlign: 'right',  verticalAlign: 'middle' })}>Metal Val</th>
            <th rowSpan={2} style={th({  textAlign: 'right',  verticalAlign: 'middle' })}>Stone Val</th>
            <th rowSpan={2} style={th({  textAlign: 'right',  verticalAlign: 'middle' })}>Making</th>
            <th rowSpan={2} style={th({  textAlign: 'right',  verticalAlign: 'middle', fontSize: 9 })}>Prod Val</th>
          </tr>
          {/* Row 2 — sub-headers for Metal (Gm) group */}
          <tr>
            <th style={th({ textAlign: 'center' })}>Gr. Wt.</th>
            <th style={th({ textAlign: 'center' })}>Net Wt.</th>
          </tr>
        </thead>

        <tbody>
          {items.map((item, idx) => (
            <ItemBlock key={item._key || idx} data={item} idx={idx} totalItems={items.length} />
          ))}
        </tbody>

        <tfoot>
          {/* Grand total */}
          <tr>
            <td colSpan={2} style={gtCell0({ textAlign: 'center' })}>
              Grand Total · {items.length} item{items.length !== 1 ? 's' : ''}
            </td>
            <td style={gtCell()} />
            <td style={gtCell({ textAlign: 'center' })}>{grand.pcs}</td>
            <td style={gtCell({ textAlign: 'right'  })}>{fmtN(grand.gw)}</td>
            <td style={gtCell({ textAlign: 'right'  })}>{fmtN(grand.nw)}</td>
            <td style={gtCell({ textAlign: 'right'  })}>{fmtN(grand.stoneCt)}</td>
            <td style={gtCell()} />
            <td style={gtCell({ textAlign: 'right'  })}>{fmtCForce(grand.metalVal)}</td>
            <td style={gtCell({ textAlign: 'right'  })}>{fmtCForce(grand.stoneVal)}</td>
            <td style={gtCell({ textAlign: 'right'  })}>{fmtCForce(grand.making)}</td>
            <td style={gtCell({ textAlign: 'right', fontSize: BASE + 1 })}>{fmtCForce(grand.productVal)}</td>
          </tr>

          {/* GST @ 3% */}
          <tr>
            <td colSpan={NCOLS - 1} style={gstCell0({ textAlign: 'right', color: '#555' })}>
              GST @ 3%
            </td>
            <td style={gstCell({ textAlign: 'right' })}>{fmtCForce(grand.gstAmt)}</td>
          </tr>

          {/* Total estimate value */}
          <tr>
            <td colSpan={NCOLS - 1} style={billCell0({ textAlign: 'right', fontSize: BASE + 1 })}>
              Total Estimate Value (incl. GST)
            </td>
            <td style={billCell({ textAlign: 'right', fontSize: BASE + 3 })}>
              ₹&nbsp;{fmtCForce(grand.billVal, 0)}
            </td>
          </tr>
        </tfoot>
      </table>

      {/* Disclaimer */}
      <div style={{
        marginTop: 14, fontSize: 8.5, color: '#888',
        textAlign: 'center', fontStyle: 'italic', fontFamily: FONT,
      }}>
        This is an estimate only. Gold rates used are the latest available market rates and may vary at the time of actual billing.
      </div>
    </div>
  );
};

// Legacy single-item shim
export const JewelryEstimateTable = ({ data }) => (
  <MultiEstimatePrint items={[{ ...data, _key: 1 }]} />
);

export default JewelryEstimateTable;
