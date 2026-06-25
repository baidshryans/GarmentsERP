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

function _numberToWordsIndian(num) {
  if (!num && num !== 0) return '';
  const units = ['','One','Two','Three','Four','Five','Six','Seven','Eight','Nine'];
  const teens = ['Ten','Eleven','Twelve','Thirteen','Fourteen','Fifteen','Sixteen','Seventeen','Eighteen','Nineteen'];
  const tens  = ['','','Twenty','Thirty','Forty','Fifty','Sixty','Seventy','Eighty','Ninety'];
  const group = (n) => {
    if (n === 0) return '';
    let r = '';
    const h = Math.floor(n / 100), rem = n % 100;
    if (h) r += units[h] + ' Hundred' + (rem ? ' ' : '');
    if (rem >= 10 && rem < 20) r += teens[rem - 10];
    else {
      if (Math.floor(rem / 10)) r += tens[Math.floor(rem / 10)] + (rem % 10 ? ' ' : '');
      if (rem % 10) r += units[rem % 10];
    }
    return r;
  };
  const whole = Math.floor(Math.abs(num));
  if (whole === 0) return 'Rupees Zero Only';
  const crore = Math.floor(whole / 10000000);
  const lakh  = Math.floor((whole % 10000000) / 100000);
  const thou  = Math.floor((whole % 100000) / 1000);
  const rest  = whole % 1000;
  let res = '';
  if (crore) res += group(crore) + ' Crore ';
  if (lakh)  res += group(lakh)  + ' Lakh ';
  if (thou)  res += group(thou)  + ' Thousand ';
  if (rest)  res += group(rest);
  return 'Rupees ' + res.trim() + ' Only';
}

export function formatWords(value) {
  // wordsStyle currently only 'indian-rupee'; future styles dispatch here
  return _numberToWordsIndian(value);
}

const _MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export function formatDate(value, style = 'short') {
  if (isEmpty(value)) return '';
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  // An options object is forwarded to toLocaleDateString with the config locale
  // (used for custom shapes like weekday-long headers).
  if (style && typeof style === 'object') {
    return d.toLocaleDateString(_config.dateLocale, style);
  }
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
