import { describe, it, expect } from "vitest";
import {
  findB2bMakingRule,
  getB2bStoneRate,
  pureRateFromPurityRate,
  resolveB2bMaking,
} from "./b2bPricing";

/**
 * Parity suite — mirrors backend/mastersconfig/tests/test_b2b_pricing.py using
 * the same numbers. If the Python and JS implementations drift, one of these
 * suites fails instead of a customer being mis-billed.
 */

const BASE_22K = 91.6;
const PURE_RATE = 7000;

const rule = (making_type, making_value, min_making_grams = 0) => ({
  making_type,
  making_value,
  min_making_grams,
});

const resolve = (r, weight, base = BASE_22K, pure = PURE_RATE) =>
  resolveB2bMaking(r, { weight, basePurityPct: base, pureGoldRate: pure });

describe("resolveB2bMaking", () => {
  it("per_gram above the minimum uses the actual weight", () => {
    const res = resolve(rule("per_gram", 300, 5), 8);
    expect(res.makingValue).toBeCloseTo(2400, 2);
    expect(res.effWeight).toBeCloseTo(8, 6);
  });

  it("per_gram below the minimum is floored", () => {
    const res = resolve(rule("per_gram", 300, 5), 3);
    expect(res.makingValue).toBeCloseTo(1500, 2); // not 900
    expect(res.effWeight).toBeCloseTo(5, 6);
  });

  it("flat value ignores the minimum", () => {
    const res = resolve(rule("val", 2000, 5), 3);
    expect(res.makingValue).toBeCloseTo(2000, 2);
    expect(res.effWeight).toBeCloseTo(3, 6);
    expect(res.effTunchPct).toBeCloseTo(BASE_22K, 6);
  });

  it("tunch above the minimum", () => {
    const res = resolve(rule("tunch", 8, 5), 10);
    expect(res.effTunchPct).toBeCloseTo(99.6, 6);
    expect(res.fineWt).toBeCloseTo(9.96, 6);
    expect(res.makingValue).toBe(0);
  });

  it("tunch below the minimum floors only the markup portion", () => {
    // 2g × 91.6% + 5g × 8% = 1.832 + 0.4 = 2.232 fine grams
    const res = resolve(rule("tunch", 8, 5), 2);
    expect(res.fineWt).toBeCloseTo(2.232, 6);
    expect(res.effTunchPct).toBeCloseTo(111.6, 6);
    expect(res.makingValue).toBe(0);
  });

  it("tunch preserves goldValue === weight × goldRate", () => {
    for (const weight of [0.5, 2, 3, 10]) {
      const res = resolve(rule("tunch", 8, 5), weight);
      expect(res.goldValue).toBeCloseTo(weight * res.goldRate, 6);
    }
  });

  it("per_nw below the minimum uses the floored weight", () => {
    const res = resolve(rule("per_nw", 12, 5), 2);
    expect(res.makingValue).toBeCloseTo(0.12 * ((5 * BASE_22K) / 100) * PURE_RATE, 6);
    // the gold line itself is untouched — only the making basis is floored
    expect(res.effTunchPct).toBeCloseTo(BASE_22K, 6);
  });

  it("charges nothing on a zero-weight line except flat value", () => {
    for (const mtype of ["per_gram", "per_nw", "tunch"]) {
      expect(resolve(rule(mtype, 300, 5), 0).makingValue).toBe(0);
    }
    expect(resolve(rule("val", 2000), 0).makingValue).toBeCloseTo(2000, 2);
  });

  it("does not blow up on a zero base purity", () => {
    const res = resolve(rule("tunch", 8, 5), 3, 0);
    expect(Number.isFinite(res.goldValue)).toBe(true);
    expect(pureRateFromPurityRate(6400, 0)).toBe(0);
  });

  it("returns plain purity figures when no rule matched", () => {
    const res = resolve(null, 10);
    expect(res.makingValue).toBeNull();
    expect(res.effTunchPct).toBeCloseTo(BASE_22K, 6);
    expect(res.fineWt).toBeCloseTo(9.16, 6);
  });

  it("treats an unknown making type as no rule", () => {
    const res = resolve(rule("bogus", 300, 5), 3);
    expect(res.makingValue).toBeNull();
    expect(res.effTunchPct).toBeCloseTo(BASE_22K, 6);
  });

  it("converts a purity rate back to a pure rate", () => {
    expect(pureRateFromPurityRate(6412, BASE_22K)).toBeCloseTo(7000, 6);
  });
});

describe("findB2bMakingRule", () => {
  const both = { purity: "22K", item: "RING", making_type: "both" };
  const purityOnly = { purity: "22K", item: null, making_type: "purity_only" };
  const itemOnly = { purity: null, item: "RING", making_type: "item_only" };
  const dflt = { purity: null, item: null, making_type: "default" };
  const pl = (...making_entries) => ({ making_entries });

  it("returns null without a pricelist", () => {
    expect(findB2bMakingRule(null, "22K", "RING")).toBeNull();
    expect(findB2bMakingRule(pl(), "22K", "RING")).toBeNull();
  });

  it("most specific wins", () => {
    expect(findB2bMakingRule(pl(dflt, itemOnly, purityOnly, both), "22K", "RING")).toBe(both);
  });

  it("falls back to purity-only", () => {
    expect(findB2bMakingRule(pl(dflt, itemOnly, purityOnly), "22K", "RING")).toBe(purityOnly);
  });

  it("falls back to item-only", () => {
    expect(findB2bMakingRule(pl(dflt, itemOnly), "22K", "RING")).toBe(itemOnly);
  });

  it("falls back to the default rule", () => {
    expect(findB2bMakingRule(pl(dflt), "22K", "RING")).toBe(dflt);
  });

  it("an unmatched purity still reaches the default rule", () => {
    expect(findB2bMakingRule(pl(purityOnly, dflt), "18K", null)).toBe(dflt);
  });

  it("returns null when nothing matches", () => {
    expect(findB2bMakingRule(pl(purityOnly), "18K", null)).toBeNull();
  });
});

describe("getB2bStoneRate", () => {
  it("prefers a pricelist override", () => {
    const pricelist = {
      stone_overrides: [{ packet: "D1", rate: 9000 }],
      wholesale_packet_rates: { D1: 800 },
    };
    expect(getB2bStoneRate(pricelist, "D1")).toBe(9000);
  });

  it("falls back to the wholesale rate", () => {
    expect(getB2bStoneRate({ wholesale_packet_rates: { D1: 800 } }, "D1")).toBe(800);
  });

  it("returns null with no override and no wholesale rate", () => {
    expect(getB2bStoneRate({ stone_overrides: [] }, "D1")).toBeNull();
    expect(getB2bStoneRate(null, "D1")).toBeNull();
  });
});
