"""
Meta Custom Audience normalisation.

Golden vectors matter here more than usual: Meta normalises and hashes on its
own side, so any disagreement about case, spacing or country code does not
raise an error — it silently produces a 0% match rate. The only way to catch
that is to pin the exact expected hashes.
"""

import hashlib
from datetime import date

from django.test import TestCase
from django.utils import timezone

from customer_intel.services.audiences import (
    SCHEMA,
    build_rows,
    hashed_row,
    normalise_city,
    normalise_email,
    normalise_name,
    normalise_phone,
    sha256_hex,
)
from customer_intel.services.snapshot import SnapshotBuilder
from customer_intel.tests.factories import make_customer, make_retail, make_sale


def expected(value):
    return hashlib.sha256(value.encode()).hexdigest()


class NormalisationTests(TestCase):
    def test_phone_gets_the_country_code_and_loses_everything_else(self):
        self.assertEqual(normalise_phone("+91 98765 43210"), "919876543210")
        self.assertEqual(normalise_phone("98765-43210"), "919876543210")
        self.assertEqual(normalise_phone("9876543210"), "919876543210")

    def test_phone_already_carrying_the_country_code_is_not_doubled(self):
        self.assertEqual(normalise_phone("919876543210"), "919876543210")

    def test_blank_phone_yields_blank(self):
        self.assertEqual(normalise_phone(""), "")
        self.assertEqual(normalise_phone(None), "")

    def test_email_is_trimmed_and_lowercased(self):
        self.assertEqual(normalise_email("  Foo@Bar.COM "), "foo@bar.com")

    def test_name_loses_case_punctuation_and_spaces(self):
        self.assertEqual(normalise_name("  D'Souza "), "dsouza")
        self.assertEqual(normalise_name("Mary-Jane"), "maryjane")

    def test_city_follows_the_name_rules(self):
        self.assertEqual(normalise_city("New Delhi"), "newdelhi")


class GoldenVectorTests(TestCase):
    """Pinned hashes — a change here means a silent match-rate collapse."""

    def test_phone_vector(self):
        self.assertEqual(
            sha256_hex(normalise_phone("+91 98765 43210")),
            expected("919876543210"),
        )

    def test_email_vector(self):
        self.assertEqual(
            sha256_hex(normalise_email("  Foo@Bar.COM ")),
            expected("foo@bar.com"),
        )

    def test_country_vector(self):
        from customer_intel.services.audiences import normalise_country

        self.assertEqual(sha256_hex(normalise_country("IN")), expected("in"))

    def test_hashes_are_lowercase_hex_of_the_right_length(self):
        digest = sha256_hex("anything")
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, digest.lower())


class RowBuildingTests(TestCase):
    def setUp(self):
        self.retail = make_retail()

    def test_row_has_every_schema_column(self):
        ledger = make_customer(
            self.retail, "Asha Patel", mobile="9876543210",
            email="asha@example.com", city="Kolkata",
        )
        row = hashed_row(ledger)

        self.assertEqual(set(row), set(SCHEMA))
        self.assertEqual(row["phone"], expected("919876543210"))
        self.assertEqual(row["email"], expected("asha@example.com"))
        self.assertEqual(row["fn"], expected("asha"))
        self.assertEqual(row["ln"], expected("patel"))
        self.assertEqual(row["ct"], expected("kolkata"))

    def test_no_raw_identifier_survives_into_the_row(self):
        ledger = make_customer(
            self.retail, "Asha Patel", mobile="9876543210",
            email="asha@example.com",
        )
        blob = " ".join(hashed_row(ledger).values())

        self.assertNotIn("9876543210", blob)
        self.assertNotIn("asha", blob)
        self.assertNotIn("example.com", blob)

    def test_single_word_name_leaves_the_surname_blank(self):
        ledger = make_customer(self.retail, "Meera", mobile="9876543210")
        row = hashed_row(ledger)

        self.assertEqual(row["fn"], expected("meera"))
        self.assertEqual(row["ln"], "")


class ExportSelectionTests(TestCase):
    def setUp(self):
        self.retail = make_retail()
        self.today = date(2026, 6, 1)

    def _snapshots(self):
        SnapshotBuilder(self.retail.id, today=self.today).run()
        from customer_intel.models import CustomerProfileSnapshot

        return list(
            CustomerProfileSnapshot.objects
            .filter(retail=self.retail).select_related("ledger")
        )

    def test_opted_out_customers_are_excluded_from_the_export(self):
        """Consent applies to advertising audiences, not just to messages."""
        from customer_intel.models import CustomerSocialProfile

        keep = make_customer(self.retail, "Contactable", mobile="9876543210")
        gone = make_customer(self.retail, "Opted Out", mobile="9876543211")
        CustomerSocialProfile.objects.create(
            ledger=gone, opt_out_at=timezone.now(), whatsapp_opt_in=False,
        )
        make_sale(self.retail, keep, date(2026, 5, 1), mrp=10000, billno="K1")
        make_sale(self.retail, gone, date(2026, 5, 1), mrp=10000, billno="G1")

        rows, stats = build_rows(self._snapshots(), self.retail)

        self.assertEqual(stats["opted_out"], 1)
        self.assertEqual(stats["exported"], 1)
        self.assertEqual(rows[0]["phone"], expected("919876543210"))

    def test_customers_with_no_identifier_are_skipped(self):
        make_customer(self.retail, "No Contact", mobile="", email="")

        rows, stats = build_rows(self._snapshots(), self.retail)

        self.assertEqual(stats["no_identifier"], 1)
        self.assertEqual(rows, [])

    def test_an_email_only_customer_is_still_exportable(self):
        make_customer(self.retail, "Email Only", mobile="",
                      email="only@example.com")

        rows, stats = build_rows(self._snapshots(), self.retail)

        self.assertEqual(stats["exported"], 1)
        self.assertEqual(rows[0]["email"], expected("only@example.com"))
        self.assertEqual(rows[0]["phone"], "")
