"""B2B pricelist making/tunch math — the single source of truth.

Mirrored in JavaScript at ``frontend/src/lib/b2bPricing.js``.  The two files must
stay in lockstep: identical branch order, identical formulas, no rounding inside
the helper (each caller rounds at its own boundary).  There is a parity test
suite on both sides using the same numbers — if you change one, change the other
and both test tables.

Given a matched rule, actual gold weight ``w``, purity base % ``base``
(``PurityMaster.gw_per``) and the pure-gold rate ``pure_rate`` (₹ per gram of
100% pure gold):

    eff_w = w                    if making_type == 'val' or w <= 0
          = max(w, min_grams)    otherwise

    per_gram : making = making_value * eff_w                              ; eff_pct = base
    val      : making = making_value                                      ; eff_pct = base
    per_nw   : making = making_value/100 * (eff_w*base/100*pure_rate)     ; eff_pct = base
    tunch    : making = 0 ; eff_pct = base + making_value * eff_w / w      (w > 0, else base)

    fine_wt    = w * eff_pct / 100
    gold_rate  = pure_rate * eff_pct / 100
    gold_value = fine_wt * pure_rate          # invariant: == w * gold_rate

Folding the tunch minimum back into an *effective percentage over the actual
weight* is what preserves ``gold_value == w * gold_rate``.  That invariant lets
the sale voucher express a tunch rule as a plain ₹/g on the gold sub-item row
without needing any new row fields.
"""

from decimal import Decimal

MAKING_TYPES = ('per_gram', 'val', 'tunch', 'per_nw')

_HUNDRED = Decimal('100')


def _D(value):
    if value is None or value == '':
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def find_b2b_making_rule(pricelist, purity=None, item=None):
    """Resolve the most specific making rule for a (purity, item) pair.

    Priority: (purity, item) > (purity, ·) > (·, item) > (·, ·).  Returns None
    when the pricelist is None or nothing matches.

    Iterates ``making_entries.all()`` rather than issuing filtered queries so a
    ``prefetch_related('making_entries')`` on the caller costs zero extra
    queries per design.
    """
    if pricelist is None:
        return None

    purity_id = getattr(purity, 'id', purity)
    item_id = getattr(item, 'id', item)
    entries = list(pricelist.making_entries.all())

    def matches(entry_fk, wanted_id, specific):
        if specific:
            return wanted_id is not None and entry_fk == wanted_id
        return entry_fk is None

    def pick(specific_purity, specific_item):
        for entry in entries:
            if (matches(entry.purity_id, purity_id, specific_purity)
                    and matches(entry.item_id, item_id, specific_item)):
                return entry
        return None

    return (pick(True, True) or pick(True, False)
            or pick(False, True) or pick(False, False))


def resolve_b2b_making(rule, *, weight, base_purity_pct, pure_gold_rate):
    """Compute the gold and making figures implied by a B2B making rule.

    ``rule``            a B2BPricelistMaking instance, or None
    ``weight``          grams of gold on the line
    ``base_purity_pct`` PurityMaster.gw_per, e.g. Decimal('91.60')
    ``pure_gold_rate``  ₹ per gram of 100% pure gold

    Returns a dict:
        making_type    str | None    the rule's type (None when no rule matched)
        eff_weight     Decimal       max(weight, min_making_grams); weight for 'val'; 0 if weight <= 0
        eff_tunch_pct  Decimal       % of pure gold charged, expressed over the ACTUAL weight
        fine_wt        Decimal       weight * eff_tunch_pct / 100
        gold_rate      Decimal       ₹/gram for the gold line
        gold_value     Decimal       fine_wt * pure_gold_rate  (== weight * gold_rate)
        making_value   Decimal|None  ₹ making; None means "no rule matched" so the
                                     caller should fall back to its own default
    """
    w = _D(weight)
    if w < 0:
        w = Decimal('0')
    base = _D(base_purity_pct)
    pure_rate = _D(pure_gold_rate)

    def result(making_type, eff_weight, eff_pct, making):
        fine_wt = w * eff_pct / _HUNDRED
        return {
            'making_type': making_type,
            'eff_weight': eff_weight,
            'eff_tunch_pct': eff_pct,
            'fine_wt': fine_wt,
            'gold_rate': pure_rate * eff_pct / _HUNDRED,
            'gold_value': fine_wt * pure_rate,
            'making_value': making,
        }

    if rule is None:
        return result(None, w, base, None)

    mtype = rule.making_type
    value = _D(rule.making_value)
    min_g = _D(getattr(rule, 'min_making_grams', 0))

    # Flat Value overrides everything: it is a flat amount, the minimum never applies.
    if mtype == 'val' or w <= 0:
        eff_w = w
    else:
        eff_w = max(w, min_g)

    if mtype == 'per_gram':
        return result(mtype, eff_w, base, value * eff_w)

    if mtype == 'val':
        return result(mtype, eff_w, base, value)

    if mtype == 'per_nw':
        gold_value_at_eff = eff_w * base / _HUNDRED * pure_rate
        return result(mtype, eff_w, base, value / _HUNDRED * gold_value_at_eff)

    if mtype == 'tunch':
        eff_pct = base + (value * eff_w / w) if w > 0 else base
        return result(mtype, eff_w, eff_pct, Decimal('0'))

    # Unknown type — behave as if no rule matched rather than mis-charging.
    return result(None, w, base, None)


def pure_rate_from_purity_rate(purity_rate, gw_per):
    """Convert a per-purity ₹/g rate (e.g. the 22K rate) into a 100%-pure ₹/g rate.

    Several PurityMaster rows in production carry ``gw_per = 0`` ("22", "18",
    "MIX"), so guard the division.
    """
    base = _D(gw_per)
    if base <= 0:
        return Decimal('0')
    return _D(purity_rate) * _HUNDRED / base
