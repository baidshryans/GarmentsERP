/**
 * B2B pricelist making/tunch math — the single source of truth on the frontend.
 *
 * Mirror of `backend/mastersconfig/b2b_pricing.py`. The two files must stay in
 * lockstep: identical branch order, identical formulas, no rounding inside the
 * helpers (each caller rounds at its own boundary). Both sides have a parity
 * test suite driven by the same numbers — change one, change the other.
 *
 * Given a matched rule, actual gold weight `w`, purity base % `base`
 * (PurityMaster.gw_per) and `pureGoldRate` (₹ per gram of 100% pure gold):
 *
 *   effW = w                  if makingType === 'val' or w <= 0
 *        = max(w, minGrams)   otherwise
 *
 *   per_gram : making = value * effW                             ; effPct = base
 *   val      : making = value                                    ; effPct = base
 *   per_nw   : making = value/100 * (effW*base/100*pureRate)     ; effPct = base
 *   tunch    : making = 0 ; effPct = base + value * effW / w      (w > 0, else base)
 *
 *   fineWt    = w * effPct / 100
 *   goldRate  = pureRate * effPct / 100
 *   goldValue = fineWt * pureRate         // invariant: === w * goldRate
 *
 * Folding the tunch minimum into an *effective percentage over the actual
 * weight* is what preserves `goldValue === w * goldRate`. That invariant lets
 * the sale voucher express a tunch rule as a plain ₹/g on the gold sub-item row
 * without needing any new row fields.
 */

export const MAKING_TYPES = ["per_gram", "val", "tunch", "per_nw"];

export const MAKING_TYPE_LABELS = {
  per_gram: "Per Gram",
  val: "Flat Value",
  tunch: "Tunch % Markup",
  per_nw: "% of Gold Value",
};

/** Unit shown next to the value input for each making type. */
export const MAKING_TYPE_UNITS = {
  per_gram: "/g",
  val: "flat",
  tunch: "%",
  per_nw: "%",
};

const num = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
};

/**
 * Resolve the most specific making rule for a (purity, item) pair.
 * Priority: (purity, item) > (purity, ·) > (·, item) > (·, ·).
 *
 * Serialized rules carry the purity NAME (e.g. "22K") and the item SHORT_CODE,
 * not database ids.
 */
export function findB2bMakingRule(pricelist, purityName, itemCode) {
  const entries = pricelist?.making_entries;
  if (!entries?.length) return null;

  const sameP = (e) => purityName != null && String(e.purity) === String(purityName);
  const sameI = (e) => itemCode != null && String(e.item) === String(itemCode);
  const noP = (e) => !e.purity;
  const noI = (e) => !e.item;

  return (
    entries.find((e) => sameP(e) && sameI(e)) ||
    entries.find((e) => sameP(e) && noI(e)) ||
    entries.find((e) => noP(e) && sameI(e)) ||
    entries.find((e) => noP(e) && noI(e)) ||
    null
  );
}

/** Stone rate for a packet: pricelist override > wholesale fallback > null. */
export function getB2bStoneRate(pricelist, pcktNo) {
  if (!pricelist) return null;
  const override = pricelist.stone_overrides?.find((s) => s.packet === pcktNo);
  if (override) return override.rate;
  const wholesale = pricelist.wholesale_packet_rates?.[pcktNo];
  return wholesale != null ? wholesale : null;
}

/**
 * Convert a per-purity ₹/g rate (e.g. the 22K rate) into a 100%-pure ₹/g rate.
 * Several PurityMaster rows carry gw_per = 0 ("22", "18", "MIX"), so guard it.
 */
export function pureRateFromPurityRate(purityRate, gwPer) {
  const base = num(gwPer);
  if (base <= 0) return 0;
  return (num(purityRate) * 100) / base;
}

/**
 * Compute the gold and making figures implied by a B2B making rule.
 *
 * @param rule  a serialized making_entries row, or null
 * @param opts.weight         grams of gold on the line
 * @param opts.basePurityPct  PurityMaster.gw_per, e.g. 91.6
 * @param opts.pureGoldRate   ₹ per gram of 100% pure gold
 * @returns {{makingType: string|null, effWeight: number, effTunchPct: number,
 *            fineWt: number, goldRate: number, goldValue: number,
 *            makingValue: number|null}}
 *          `makingValue === null` means no rule matched — the caller should
 *          fall back to its own default.
 */
export function resolveB2bMaking(rule, { weight, basePurityPct, pureGoldRate } = {}) {
  const w = Math.max(num(weight), 0);
  const base = num(basePurityPct);
  const pureRate = num(pureGoldRate);

  const result = (makingType, effWeight, effPct, making) => {
    const fineWt = (w * effPct) / 100;
    return {
      makingType,
      effWeight,
      effTunchPct: effPct,
      fineWt,
      goldRate: (pureRate * effPct) / 100,
      goldValue: fineWt * pureRate,
      makingValue: making,
    };
  };

  if (!rule) return result(null, w, base, null);

  const mtype = rule.making_type;
  const value = num(rule.making_value);
  const minG = num(rule.min_making_grams);

  // Flat Value overrides everything: it is a flat amount, the minimum never applies.
  const effW = mtype === "val" || w <= 0 ? w : Math.max(w, minG);

  if (mtype === "per_gram") return result(mtype, effW, base, value * effW);
  if (mtype === "val") return result(mtype, effW, base, value);
  if (mtype === "per_nw") {
    const goldValueAtEff = ((effW * base) / 100) * pureRate;
    return result(mtype, effW, base, (value / 100) * goldValueAtEff);
  }
  if (mtype === "tunch") {
    const effPct = w > 0 ? base + (value * effW) / w : base;
    return result(mtype, effW, effPct, 0);
  }

  // Unknown type — behave as if no rule matched rather than mis-charging.
  return result(null, w, base, null);
}
