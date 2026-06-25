// Central formatter (Multi-Country Phase 1).
// All money/date/number/amount-in-words presentation routes through this module
// so currency/locale becomes a single config lever. Plain functions (no hooks)
// so non-React print templates can call them too.

export const INR_CONFIG = {
  currency: 'INR',
  symbol: '₹',
  symbolPosition: 'prefix', // 'prefix' | 'suffix'
  symbolSpace: true,        // space between symbol and number
  locale: 'en-IN',          // drives digit grouping (Indian vs western)
  dateLocale: 'en-IN',
  wordsStyle: 'indian-rupee',
};

let _config = INR_CONFIG;

export function setFormatConfig(cfg) { _config = cfg; }
export function getFormatConfig() { return _config; }

function isEmpty(v) {
  return v === null || v === undefined || v === '';
}

export function formatNumber(value, opts = {}) {
  const { decimals, minDecimals, maxDecimals, abs = false, blankOnZero = false } = opts;
  if (blankOnZero && (isEmpty(value) || Number(value) === 0)) return '';
  let num = parseFloat(isEmpty(value) ? 0 : value);
  if (isNaN(num)) return '';
  if (abs) num = Math.abs(num);
  const o = {};
  if (decimals != null) {
    o.minimumFractionDigits = decimals;
    o.maximumFractionDigits = decimals;
  } else {
    if (minDecimals != null) o.minimumFractionDigits = minDecimals;
    if (maxDecimals != null) o.maximumFractionDigits = maxDecimals;
  }
  return num.toLocaleString(_config.locale, o);
}

const _MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export function formatDate(value, style = 'short') {
  if (isEmpty(value)) return '';
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  if (style === 'numeric') {
    const dd = String(d.getDate()).padStart(2, '0');
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    return `${dd}/${mm}/${d.getFullYear()}`;
  }
  // 'short'
  return `${String(d.getDate()).padStart(2, '0')} ${_MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function formatMoney(value, opts = {}) {
  const { showSymbol = true, space = _config.symbolSpace, ...numOpts } = opts;
  const numStr = formatNumber(value, numOpts);
  if (numStr === '') return '';
  if (!showSymbol) return numStr;
  const gap = space ? ' ' : '';
  return _config.symbolPosition === 'suffix'
    ? `${numStr}${gap}${_config.symbol}`
    : `${_config.symbol}${gap}${numStr}`;
}
