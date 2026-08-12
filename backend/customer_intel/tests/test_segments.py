"""
Segment compilation.

The rejection tests matter most: a segment definition is user-supplied JSON that
becomes database filters. If an unregistered field name ever compiles, the
filter builder turns into a way to read arbitrary related columns.
"""

from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase

from customer_intel.services.segments import (
    FIELD_REGISTRY,
    SegmentCompiler,
    evaluate,
    registry_json,
)
from customer_intel.services.snapshot import SnapshotBuilder
from customer_intel.tests.factories import make_customer, make_retail, make_sale


class CompilerRejectionTests(TestCase):
    def setUp(self):
        self.retail = make_retail()

    def _compile(self, rules, match="all"):
        return SegmentCompiler(
            self.retail, {"match": match, "rules": rules},
        ).queryset()

    def test_unknown_field_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._compile([{"field": "not_a_field", "op": "eq", "value": 1}])

    def test_relation_traversal_is_rejected(self):
        """The exact attack the whitelist exists to stop."""
        with self.assertRaises(ValidationError):
            self._compile([{
                "field": "ledger__portal_accounts__password_hash",
                "op": "icontains", "value": "$",
            }])

    def test_operator_not_allowed_on_field_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._compile([{"field": "b2b", "op": "gt", "value": 1}])

    def test_invalid_choice_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._compile([{
                "field": "rfm_segment", "op": "eq", "value": "not_a_segment",
            }])

    def test_non_numeric_value_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._compile([{
                "field": "lifetime_value", "op": "gte", "value": "lots",
            }])

    def test_in_requires_a_list(self):
        with self.assertRaises(ValidationError):
            self._compile([{
                "field": "rfm_segment", "op": "in", "value": "champion",
            }])

    def test_bad_match_mode_is_rejected(self):
        with self.assertRaises(ValidationError):
            SegmentCompiler(self.retail, {"match": "sometimes", "rules": []})

    def test_registry_is_exposed_for_the_builder(self):
        groups = registry_json()
        keys = {f["key"] for g in groups for f in g["fields"]}
        self.assertEqual(keys, set(FIELD_REGISTRY))


class EvaluationTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.today = date(2026, 6, 1)

        self.big = make_customer(self.retail, "Big Spender", mobile="9000000001")
        make_sale(self.retail, self.big, date(2026, 5, 1), mrp=900000, billno="BIG1")

        self.small = make_customer(self.retail, "Small Spender", mobile="9000000002")
        make_sale(self.retail, self.small, date(2026, 5, 2), mrp=9000, billno="SML1")

        self.idle = make_customer(self.retail, "Never Bought", mobile="9000000003")

        SnapshotBuilder(self.retail.id, today=self.today).run()

    def _names(self, definition):
        members = evaluate(definition, self.retail, today=self.today)
        return sorted(s.ledger.ac_name for s in members)

    def test_numeric_threshold(self):
        self.assertEqual(
            self._names({"match": "all", "rules": [
                {"field": "lifetime_value", "op": "gte", "value": 100000},
            ]}),
            ["Big Spender"],
        )

    def test_all_combines_with_and(self):
        names = self._names({"match": "all", "rules": [
            {"field": "purchase_count_all", "op": "gte", "value": 1},
            {"field": "lifetime_value", "op": "gte", "value": 100000},
        ]})
        self.assertEqual(names, ["Big Spender"])

    def test_any_combines_with_or(self):
        # Bounded below as well, so the never-bought customer (lifetime value 0)
        # does not legitimately fall into the "small" arm.
        names = self._names({"match": "any", "rules": [
            {"field": "lifetime_value", "op": "gte", "value": 500000},
            {"field": "purchase_count_all", "op": "eq", "value": 0},
        ]})
        self.assertEqual(names, ["Big Spender", "Never Bought"])

    def test_has_mobile_inverts_the_null_check(self):
        no_phone = make_customer(self.retail, "No Phone", mobile="")
        SnapshotBuilder(self.retail.id, today=self.today).run()

        names = self._names({"match": "all", "rules": [
            {"field": "has_mobile", "op": "eq", "value": False},
        ]})
        self.assertIn(no_phone.ac_name, names)
        self.assertNotIn("Big Spender", names)

    def test_empty_definition_returns_everyone(self):
        self.assertEqual(len(self._names({"match": "all", "rules": []})), 3)


class OccasionPostFilterTests(TestCase):
    """
    `occasion_within_days` is evaluated in Python because the day-of-year wrap
    (28 Dec → 3 Jan is 6 days, not 359) has no portable SQL expression.
    """

    def setUp(self):
        self.retail = make_retail()

    def _run(self, today, days=7, match="all"):
        SnapshotBuilder(self.retail.id, today=today).run()
        members = evaluate(
            {"match": match, "rules": [
                {"field": "occasion_within_days", "op": "lte", "value": days},
            ]},
            self.retail, today=today,
        )
        return sorted(s.ledger.ac_name for s in members)

    def test_finds_a_birthday_later_this_week(self):
        make_customer(self.retail, "Soon", dob=date(1990, 6, 5))
        make_customer(self.retail, "Later", dob=date(1990, 11, 5))

        self.assertEqual(self._run(date(2026, 6, 1)), ["Soon"])

    def test_wraps_across_the_year_boundary(self):
        """A 3 January birthday must be found from 28 December."""
        make_customer(self.retail, "New Year Baby", dob=date(1990, 1, 3))

        self.assertEqual(self._run(date(2026, 12, 28)), ["New Year Baby"])

    def test_customers_without_occasions_are_excluded(self):
        make_customer(self.retail, "No Dates")

        self.assertEqual(self._run(date(2026, 6, 1)), [])

    def test_anniversary_counts_too(self):
        make_customer(self.retail, "Anniversary",
                      anniversary=date(2010, 6, 4))

        self.assertEqual(self._run(date(2026, 6, 1)), ["Anniversary"])

    def test_any_match_unions_sql_and_python_rules(self):
        """
        A customer matching ONLY the Python rule must still be included — the
        SQL half must not pre-narrow the population in 'any' mode.
        """
        rich = make_customer(self.retail, "Rich No Birthday", mobile="9111111111")
        make_sale(self.retail, rich, date(2026, 5, 1), mrp=900000, billno="R1")
        make_customer(self.retail, "Poor With Birthday", dob=date(1990, 6, 3))

        today = date(2026, 6, 1)
        SnapshotBuilder(self.retail.id, today=today).run()

        members = evaluate(
            {"match": "any", "rules": [
                {"field": "lifetime_value", "op": "gte", "value": 100000},
                {"field": "occasion_within_days", "op": "lte", "value": 7},
            ]},
            self.retail, today=today,
        )
        self.assertEqual(
            sorted(s.ledger.ac_name for s in members),
            ["Poor With Birthday", "Rich No Birthday"],
        )


class ConsentFilterTests(TestCase):
    def test_marketable_excludes_opted_out_customers(self):
        from django.utils import timezone

        from customer_intel.models import CustomerSocialProfile

        retail = make_retail()
        today = date(2026, 6, 1)
        ok = make_customer(retail, "Contactable", mobile="9222222221")
        gone = make_customer(retail, "Opted Out", mobile="9222222222")
        CustomerSocialProfile.objects.create(
            ledger=gone, opt_out_at=timezone.now(), whatsapp_opt_in=False,
        )
        SnapshotBuilder(retail.id, today=today).run()

        members = evaluate(
            {"match": "all", "rules": [
                {"field": "marketable", "op": "eq", "value": True},
            ]},
            retail, today=today,
        )
        names = [s.ledger.ac_name for s in members]
        self.assertIn(ok.ac_name, names)
        self.assertNotIn(gone.ac_name, names)
