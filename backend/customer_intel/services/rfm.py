"""
RFM scoring, buying cadence and lapse risk.

Explainable statistics only — no machine learning. Every number this module
produces must be reconstructible by hand from the inputs, because a salesperson
is going to act on it and will (rightly) ask why.

The confidence gate is the most important thing here. On a dataset where most
customers have bought exactly once, frequency and cadence are undefined. Rather
than emitting a confident-looking fabrication, `confidence_for()` marks those
customers 'low'/'none' and callers must suppress cadence and lapse output.
"""

import bisect
import statistics
from datetime import timedelta

# ── tuning constants ──────────────────────────────────────────────────────────

# Below this cohort size, quintiles are noise — use fixed bands instead.
MIN_COHORT_FOR_QUINTILES = 100
# Quintiles also need enough repeat buyers for frequency to have any spread.
MIN_REPEAT_SHARE_FOR_QUINTILES = 0.30

# Jewellery-specific sanity clamp on inter-purchase gaps. Two purchases in one
# week does not mean a 4-day buying cycle; one 6-year gap should not park a
# customer in 'healthy' forever.
MIN_GAP_DAYS = 45
MAX_GAP_DAYS = 1460

# Absolute recency bands, in days since last purchase.
R_BANDS = [(90, 5), (180, 4), (365, 3), (730, 2)]
# Absolute frequency bands, on lifetime purchase count.
F_BANDS = [(1, 1), (2, 2), (4, 3), (7, 4)]
# Absolute monetary bands, in INR of net spend.
M_BANDS = [(50_000, 1), (200_000, 2), (500_000, 3), (1_000_000, 4)]

LAPSE_BANDS = [(0.8, "healthy"), (1.3, "due"), (2.5, "at_risk")]


def _band_score(value, bands, top=5):
    """First matching (threshold, score) wins; falls through to `top`."""
    for threshold, score in bands:
        if value <= threshold:
            return score
    return top


def _recency_score_absolute(days_since_last):
    if days_since_last is None:
        return 1
    return _band_score(days_since_last, R_BANDS, top=1)


def _quintile_cuts(values):
    """
    Four cut points splitting a sorted population into five roughly equal parts.

    Returns None when the population is too small or too degenerate (e.g. every
    value identical) for quintiles to mean anything.
    """
    clean = sorted(v for v in values if v is not None)
    if len(clean) < 5 or clean[0] == clean[-1]:
        return None
    return [
        clean[int(len(clean) * q)] for q in (0.2, 0.4, 0.6, 0.8)
    ]


def _score_from_cuts(value, cuts, reverse=False):
    """
    Score 1-5 by position against quintile cut points.

    Uses bisect against the cut points rather than slicing a sorted list, so
    customers with identical values always receive identical scores.
    `reverse=True` for recency, where a smaller value is better.
    """
    if value is None:
        return 1
    idx = bisect.bisect_right(cuts, value)
    score = idx + 1
    if reverse:
        score = 6 - score
    return max(1, min(5, score))


# ── segment labelling ─────────────────────────────────────────────────────────
# Order matters — first matching predicate wins.
RFM_SEGMENT_MAP = [
    (lambda r, f, m: r >= 4 and f >= 4 and m >= 4, "champion"),
    (lambda r, f, m: r <= 2 and f >= 4 and m >= 4, "cant_lose"),
    (lambda r, f, m: r >= 3 and f >= 4, "loyal"),
    (lambda r, f, m: r <= 2 and f >= 3, "at_risk"),
    (lambda r, f, m: r == 1 and f == 1, "lost"),
    (lambda r, f, m: r <= 2 and f <= 2 and m <= 2, "hibernating"),
    (lambda r, f, m: r >= 4 and f == 1, "new"),
    (lambda r, f, m: r >= 4 and f == 2, "promising"),
    (lambda r, f, m: r >= 3 and f == 3, "potential_loyalist"),
    (lambda r, f, m: r == 3 and f <= 2, "needs_attention"),
]


def segment_for(r, f, m):
    for predicate, label in RFM_SEGMENT_MAP:
        if predicate(r, f, m):
            return label
    return "about_to_sleep"


# ── confidence ────────────────────────────────────────────────────────────────

def confidence_for(purchase_count_all, history_span_days):
    """
    How much the derived cadence/lapse numbers can be trusted.

    Returns (level, human_readable_reason). Callers MUST hide cadence and lapse
    output when the level is 'none' or 'low' — see
    CustomerProfileSnapshot.cadence_is_meaningful.
    """
    if not purchase_count_all:
        return "none", "No purchase history"

    span_months = round((history_span_days or 0) / 30.4)
    plural = "s" if purchase_count_all != 1 else ""
    detail = f"{purchase_count_all} purchase{plural}"
    if span_months >= 1:
        detail += f" over {span_months} month{'s' if span_months != 1 else ''}"

    if purchase_count_all == 1:
        return "low", f"{detail} — not enough to predict a pattern"
    if purchase_count_all <= 3:
        return "medium", detail
    return "high", detail


# ── cadence ───────────────────────────────────────────────────────────────────

def cadence_for(purchase_dates, cohort_median_gap=None):
    """
    Infer a buying rhythm from a customer's ordered purchase dates.

    Returns (median_gap_days, mean_gap_days, gap_basis). The basis says where
    the number came from so the UI can be honest:
        own     — enough of their own gaps to stand alone (>= 3)
        blended — 1-2 own gaps, averaged 50/50 with the cohort
        cohort  — no gaps of their own; borrowed from similar customers
        none    — nothing to go on
    """
    dates = sorted(d for d in purchase_dates if d)
    gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]

    if len(gaps) >= 3:
        median = statistics.median(gaps)
        mean = statistics.fmean(gaps)
        basis = "own"
    elif gaps and cohort_median_gap:
        own = statistics.median(gaps)
        median = (own + cohort_median_gap) / 2
        mean = statistics.fmean(gaps)
        basis = "blended"
    elif gaps:
        median = statistics.median(gaps)
        mean = statistics.fmean(gaps)
        basis = "own"
    elif cohort_median_gap:
        median = mean = cohort_median_gap
        basis = "cohort"
    else:
        return None, None, "none"

    median = max(MIN_GAP_DAYS, min(MAX_GAP_DAYS, int(round(median))))
    return median, int(round(mean)), basis


def lapse_for(days_since_last, median_gap_days):
    """Returns (lapse_ratio, lapse_band)."""
    if days_since_last is None:
        return None, "never"
    if not median_gap_days:
        return None, ""
    ratio = days_since_last / median_gap_days
    for threshold, band in LAPSE_BANDS:
        if ratio < threshold:
            return round(ratio, 3), band
    return round(ratio, 3), "lapsed"


def next_expected(last_purchase_date, median_gap_days):
    if not last_purchase_date or not median_gap_days:
        return None
    return last_purchase_date + timedelta(days=median_gap_days)


# ── engagement score ──────────────────────────────────────────────────────────

ENGAGEMENT_WEIGHTS = [
    ("catalog_opened", 30, "Opened a catalog link"),
    ("viewed_designs", 20, "Viewed 3+ designs"),
    ("replied", 20, "Replied to a message"),
    ("scheme_active", 15, "Active savings scheme"),
    ("pending_order", 15, "Has a pending order"),
]


def engagement_for(catalog_opens_90d=0, design_views_90d=0, inbound_replies_90d=0,
                   scheme_active=False, pending_order=False):
    """
    A 0-100 score that is additive and printable — the UI shows the components
    as chips so a user can see exactly why someone scored what they did. No
    opaque weighted composite.
    """
    flags = {
        "catalog_opened": catalog_opens_90d > 0,
        "viewed_designs": design_views_90d >= 3,
        "replied": inbound_replies_90d > 0,
        "scheme_active": bool(scheme_active),
        "pending_order": bool(pending_order),
    }
    components = [
        {"key": key, "points": points, "label": label}
        for key, points, label in ENGAGEMENT_WEIGHTS if flags[key]
    ]
    score = min(100, sum(c["points"] for c in components))
    return score, {"components": components}


# ── cohort scorer ─────────────────────────────────────────────────────────────

class CohortScorer:
    """
    Assigns R/F/M scores relative to a retail's active customer population.

    Built from the whole cohort first (pass A of the nightly rebuild), then used
    to score each customer (pass B). Picks quintiles when the population can
    support them and falls back to absolute bands otherwise — `basis` records
    which, so the UI can say "scored against 4,102 active customers" or
    "scored against fixed value bands".
    """

    def __init__(self, recencies, frequencies, monetaries):
        self.cohort_size = len(frequencies)
        repeat_share = (
            sum(1 for f in frequencies if f and f >= 2) / self.cohort_size
            if self.cohort_size else 0
        )

        use_quintiles = (
            self.cohort_size >= MIN_COHORT_FOR_QUINTILES
            and repeat_share >= MIN_REPEAT_SHARE_FOR_QUINTILES
        )
        self._r_cuts = _quintile_cuts(recencies) if use_quintiles else None
        self._f_cuts = _quintile_cuts(frequencies) if use_quintiles else None
        self._m_cuts = _quintile_cuts(monetaries) if use_quintiles else None

        # Quintiles are only used if every dimension could actually produce them.
        self.basis = (
            "quintile"
            if all(c is not None for c in (self._r_cuts, self._f_cuts, self._m_cuts))
            else "absolute"
        )
        self.repeat_share = round(repeat_share, 4)

        sorted_m = sorted(m for m in monetaries if m)
        self.p90_spend = sorted_m[int(len(sorted_m) * 0.9)] if sorted_m else 0

    def score(self, days_since_last, purchase_count, net_spend):
        if self.basis == "quintile":
            r = _score_from_cuts(days_since_last, self._r_cuts, reverse=True)
            f = _score_from_cuts(purchase_count, self._f_cuts)
            m = _score_from_cuts(net_spend, self._m_cuts)
        else:
            r = _recency_score_absolute(days_since_last)
            f = _band_score(purchase_count or 0, F_BANDS)
            m = _band_score(float(net_spend or 0), M_BANDS)
        return r, f, m
