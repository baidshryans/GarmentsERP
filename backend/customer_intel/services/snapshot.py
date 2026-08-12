"""
Nightly rebuild of CustomerProfileSnapshot rows.

Shape of the job (two passes, because scores are cohort-relative):

    pass A  stream every customer's purchase dates + amounts and their
            preference rollups, in batches, accumulating raw R/F/M in memory
    ------  build the CohortScorer and the cohort gap medians from the whole
            population
    pass B  turn raw metrics into scored snapshot rows and upsert them

Memory cost is a few hundred bytes per customer, which is fine at jewellery-
retailer scale (this DB has ~1k customers; even 100k would be ~50MB).

SQLite note: the write lock is global, so each chunk gets its own short
transaction rather than one long one wrapping the entire rebuild — otherwise a
02:15 rebuild would lock out anything else touching the database.
"""

import statistics
from collections import defaultdict
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Max, Q, Sum

from contacts.models import Ledger
from customer_intel.models import CustomerProfileSnapshot, EngagementEvent
from customer_intel.services import preferences as prefs
from customer_intel.services import rfm
from sales.expressions import sales_exprs
from sales.models import SaleReturn, SalesVou

BATCH_SIZE = 2000
WRITE_CHUNK = 500

# Trailing window used for the scoring metrics. Lifetime figures ignore it.
SCORING_WINDOW_DAYS = 365 * 3


def _percentile(sorted_values, q):
    if not sorted_values:
        return 0
    idx = min(len(sorted_values) - 1, int(len(sorted_values) * q))
    return sorted_values[idx]


class SnapshotBuilder:
    """Rebuild every customer profile snapshot for one retail."""

    def __init__(self, retail_id, batch_size=BATCH_SIZE, today=None):
        self.retail_id = retail_id
        self.batch_size = batch_size
        self.today = today or date.today()
        self.window_start = self.today - timedelta(days=SCORING_WINDOW_DAYS)

        # raw[ledger_id] = dict of unscored metrics
        self.raw = {}

    # ── customer population ───────────────────────────────────────────────────

    def ledger_ids(self):
        """
        Customers of this retail: registered here OR having bought here.

        See the module docstring in customer_intel/models.py — sales are
        authoritative, so a customer registered at another branch who buys here
        counts as ours.

        `retail_code IS NULL` means a globally-shared ledger and is included for
        every retail. This matters: in the live database *every* customer ledger
        has a null retail_code, so scoping on equality alone would reduce the
        customer base to buyers only. This mirrors the house pattern used by
        `get_ledger_statement` in mcp_server.py, and deliberately differs from
        `contacts.crm_sender.find_due_recipients`, which uses strict equality
        and therefore currently matches no one.
        """
        registered = Ledger.objects.filter(
            Q(retail_code_id=self.retail_id) | Q(retail_code__isnull=True),
            roles__role="CO",
        ).values_list("id", flat=True)

        bought = SalesVou.objects.filter(
            retail_id=self.retail_id,
        ).values_list("ldgr_id", flat=True)

        return sorted(set(registered) | {b for b in bought if b})

    # ── pass A ────────────────────────────────────────────────────────────────

    def _collect_sales(self, ledger_ids):
        """
        One streamed query for the batch. Percentiles and inter-purchase gaps
        are computed in Python — deliberately not PERCENTILE_CONT, which SQLite
        lacks and which would break a later move to Postgres differently.
        """
        bill = sales_exprs()["bill"]
        rows = (
            SalesVou.objects.filter(retail_id=self.retail_id, ldgr_id__in=ledger_ids)
            .annotate(bv=bill)
            .values("ldgr_id", "date1", "bv")
            .order_by("ldgr_id", "date1")
        )

        by_ledger = defaultdict(lambda: {"dates": [], "amounts": []})
        for row in rows:
            if not row["ldgr_id"] or not row["date1"]:
                continue
            entry = by_ledger[row["ldgr_id"]]
            entry["dates"].append(row["date1"])
            entry["amounts"].append(float(row["bv"] or 0))
        return by_ledger

    def _collect_returns(self, ledger_ids):
        # SaleReturn shares the mrp/discount/GST shape but has no round_off column.
        bill = sales_exprs(include_round_off=False)["bill"]
        rows = (
            SaleReturn.objects.filter(retail_id=self.retail_id, ldgr_id__in=ledger_ids)
            .annotate(bv=bill)
            .values("ldgr_id")
            .annotate(total=Sum("bv"))
            .order_by()
        )
        return {r["ldgr_id"]: float(r["total"] or 0) for r in rows if r["ldgr_id"]}

    def _collect_engagement(self, ledger_ids):
        """Last outbound contact / last inbound reply per customer."""
        rows = (
            EngagementEvent.objects.filter(
                retail_id=self.retail_id, ledger_id__in=ledger_ids,
            )
            .values("ledger_id")
            .annotate(
                last_out=Max("occurred_at", filter=Q(direction="out")),
                last_in=Max("occurred_at", filter=Q(direction="in")),
            )
            .order_by()
        )
        return {
            r["ledger_id"]: (r["last_out"], r["last_in"])
            for r in rows if r["ledger_id"]
        }

    def _collect_catalog(self, ledger_ids):
        """
        Catalog opens and design views in the last 90 days.

        These are the only between-purchase intent signals the system has, so
        they feed both the engagement score and the worklist's catalog_intent
        reason.
        """
        from customer_intel.models import CatalogViewEvent

        since = self.today - timedelta(days=90)
        rows = (
            CatalogViewEvent.objects
            .filter(retail_id=self.retail_id, ledger_id__in=ledger_ids,
                    occurred_at__date__gte=since)
            .values("ledger_id", "kind")
            .annotate(n=Count("id"))
            .order_by()
        )
        out = defaultdict(lambda: {"opens": 0, "designs": 0})
        for row in rows:
            bucket = out[row["ledger_id"]]
            if row["kind"] == "open":
                bucket["opens"] += row["n"]
            elif row["kind"] == "design":
                bucket["designs"] += row["n"]
        return out

    def collect(self, ledger_ids):
        """Populate self.raw for one batch. Fixed query count per batch."""
        sales = self._collect_sales(ledger_ids)
        returns = self._collect_returns(ledger_ids)
        engagement = self._collect_engagement(ledger_ids)
        catalog = self._collect_catalog(ledger_ids)
        preference_map = prefs.build_all(self.retail_id, ledger_ids, self.window_start)
        b2b_map = dict(
            Ledger.objects.filter(id__in=ledger_ids).values_list("id", "b2b")
        )

        for ledger_id in ledger_ids:
            entry = sales.get(ledger_id, {"dates": [], "amounts": []})
            dates = entry["dates"]
            amounts = entry["amounts"]

            windowed = [
                (d, a) for d, a in zip(dates, amounts) if d >= self.window_start
            ]
            gross_window = sum(a for _, a in windowed)
            returns_value = returns.get(ledger_id, 0.0)
            lifetime_gross = sum(amounts)

            sorted_amounts = sorted(amounts)
            last_out, last_in = engagement.get(ledger_id, (None, None))

            self.raw[ledger_id] = {
                "dates": dates,
                "first": dates[0] if dates else None,
                "last": dates[-1] if dates else None,
                "days_since_last": (self.today - dates[-1]).days if dates else None,
                "purchase_count": len(windowed),
                "purchase_count_all": len(dates),
                "gross_spend": gross_window,
                "returns_value": returns_value,
                "net_spend": max(0.0, gross_window - returns_value),
                "lifetime_value": max(0.0, lifetime_gross - returns_value),
                "avg_ticket": statistics.fmean(amounts) if amounts else 0,
                "median_ticket": statistics.median(amounts) if amounts else 0,
                "min_ticket": sorted_amounts[0] if sorted_amounts else 0,
                "max_ticket": sorted_amounts[-1] if sorted_amounts else 0,
                "p25_ticket": _percentile(sorted_amounts, 0.25),
                "p75_ticket": _percentile(sorted_amounts, 0.75),
                "prefs": preference_map.get(ledger_id, {}),
                "b2b": bool(b2b_map.get(ledger_id)),
                "last_contacted_at": last_out,
                "last_inbound_at": last_in,
                "catalog_opens_90d": catalog.get(ledger_id, {}).get("opens", 0),
                "design_views_90d": catalog.get(ledger_id, {}).get("designs", 0),
            }

    # ── cohort statistics ─────────────────────────────────────────────────────

    def build_cohort(self):
        """
        Scorer + per-category gap medians, over customers who have bought within
        the scoring window.
        """
        active = [r for r in self.raw.values() if r["purchase_count"] > 0]

        scorer = rfm.CohortScorer(
            recencies=[r["days_since_last"] for r in active],
            frequencies=[r["purchase_count"] for r in active],
            monetaries=[r["net_spend"] for r in active],
        )

        gaps_by_category = defaultdict(list)
        all_gaps = []
        for r in self.raw.values():
            dates = r["dates"]
            gaps = [(b - a).days for a, b in zip(dates, dates[1:]) if (b - a).days > 0]
            if not gaps:
                continue
            all_gaps.extend(gaps)
            top_cat = self._top_category_id(r)
            if top_cat:
                gaps_by_category[top_cat].extend(gaps)

        overall = int(statistics.median(all_gaps)) if all_gaps else None
        per_category = {
            cat: int(statistics.median(g)) for cat, g in gaps_by_category.items()
        }
        return scorer, overall, per_category

    @staticmethod
    def _top_category_id(raw_entry):
        cats = (raw_entry.get("prefs") or {}).get("category") or []
        return cats[0]["id"] if cats else None

    @staticmethod
    def _top_purity_id(raw_entry):
        pur = (raw_entry.get("prefs") or {}).get("purity") or []
        return pur[0]["id"] if pur else None

    # ── pass B ────────────────────────────────────────────────────────────────

    def build_rows(self, scorer, overall_gap, gap_by_category):
        rows = []
        for ledger_id, r in self.raw.items():
            top_cat = self._top_category_id(r)
            cohort_gap = gap_by_category.get(top_cat) or overall_gap

            median_gap, mean_gap, gap_basis = rfm.cadence_for(r["dates"], cohort_gap)
            lapse_ratio, lapse_band = rfm.lapse_for(r["days_since_last"], median_gap)

            r_score, f_score, m_score = scorer.score(
                r["days_since_last"], r["purchase_count"], r["net_spend"],
            )
            segment = rfm.segment_for(r_score, f_score, m_score)

            span = (r["last"] - r["first"]).days if r["first"] and r["last"] else 0
            confidence, reason = rfm.confidence_for(r["purchase_count_all"], span)

            engagement_score, engagement_components = rfm.engagement_for(
                catalog_opens_90d=r["catalog_opens_90d"],
                design_views_90d=r["design_views_90d"],
                inbound_replies_90d=1 if r["last_inbound_at"] else 0,
            )

            preference = r.get("prefs") or {}
            rows.append(CustomerProfileSnapshot(
                retail_id=self.retail_id,
                ledger_id=ledger_id,
                first_purchase_date=r["first"],
                last_purchase_date=r["last"],
                days_since_last=r["days_since_last"],
                purchase_count=r["purchase_count"],
                purchase_count_all=r["purchase_count_all"],
                gross_spend=round(r["gross_spend"], 2),
                returns_value=round(r["returns_value"], 2),
                net_spend=round(r["net_spend"], 2),
                lifetime_value=round(r["lifetime_value"], 2),
                r_score=r_score,
                f_score=f_score,
                m_score=m_score,
                rfm_cell=f"{r_score}{f_score}{m_score}",
                rfm_segment=segment,
                scoring_basis=scorer.basis,
                confidence=confidence,
                confidence_reason=reason,
                median_gap_days=median_gap,
                mean_gap_days=mean_gap,
                gap_basis=gap_basis,
                next_expected_date=rfm.next_expected(r["last"], median_gap),
                lapse_ratio=lapse_ratio,
                lapse_band=lapse_band,
                avg_ticket=round(r["avg_ticket"], 2),
                median_ticket=round(r["median_ticket"], 2),
                min_ticket=round(r["min_ticket"], 2),
                max_ticket=round(r["max_ticket"], 2),
                p25_ticket=round(r["p25_ticket"], 2),
                p75_ticket=round(r["p75_ticket"], 2),
                category_prefs=preference.get("category", []),
                purity_prefs=preference.get("purity", []),
                metal_color_prefs=preference.get("metal_color", []),
                design_prefs=preference.get("design", []),
                stone_prefs=preference.get("stone", {}),
                top_category_id=top_cat,
                top_purity_id=self._top_purity_id(r),
                last_contacted_at=r["last_contacted_at"],
                last_inbound_at=r["last_inbound_at"],
                catalog_views_90d=r["catalog_opens_90d"],
                engagement_score=engagement_score,
                engagement_components=engagement_components,
                b2b=r["b2b"],
            ))
        return rows

    UPDATE_FIELDS = [
        "first_purchase_date", "last_purchase_date", "days_since_last",
        "purchase_count", "purchase_count_all", "gross_spend", "returns_value",
        "net_spend", "lifetime_value", "r_score", "f_score", "m_score",
        "rfm_cell", "rfm_segment", "scoring_basis", "confidence",
        "confidence_reason", "median_gap_days", "mean_gap_days", "gap_basis",
        "next_expected_date", "lapse_ratio", "lapse_band", "avg_ticket",
        "median_ticket", "min_ticket", "max_ticket", "p25_ticket", "p75_ticket",
        "category_prefs", "purity_prefs", "metal_color_prefs", "design_prefs",
        "stone_prefs", "top_category_id", "top_purity_id", "last_contacted_at",
        "last_inbound_at", "catalog_views_90d", "engagement_score",
        "engagement_components", "b2b", "computed_at",
    ]

    def write(self, rows):
        """Chunked upsert, each chunk in its own short transaction."""
        for i in range(0, len(rows), WRITE_CHUNK):
            chunk = rows[i:i + WRITE_CHUNK]
            with transaction.atomic():
                CustomerProfileSnapshot.objects.bulk_create(
                    chunk,
                    update_conflicts=True,
                    update_fields=self.UPDATE_FIELDS,
                    unique_fields=["retail", "ledger"],
                )

    # ── entrypoint ────────────────────────────────────────────────────────────

    def run(self):
        ids = self.ledger_ids()
        if not ids:
            return {"customers": 0, "written": 0, "basis": None}

        for i in range(0, len(ids), self.batch_size):
            self.collect(ids[i:i + self.batch_size])

        scorer, overall_gap, gap_by_category = self.build_cohort()
        rows = self.build_rows(scorer, overall_gap, gap_by_category)
        self.write(rows)

        return {
            "customers": len(ids),
            "written": len(rows),
            "basis": scorer.basis,
            "cohort_size": scorer.cohort_size,
            "repeat_share": scorer.repeat_share,
        }
