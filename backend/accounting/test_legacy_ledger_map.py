from django.test import TestCase
from django.core.management import call_command
from accounting.legacy_ledger_map import (
    parse_tds_tcs_section, resolve_section_ledger, EXTRA_SYNONYMS,
)
from mastersconfig.models import RetailMaster


class ParseSectionTests(TestCase):
    def test_short_tds_codes_gain_leading_one(self):
        self.assertEqual(parse_tds_tcs_section("T.D.S_94C"), ("TDS", "194C"))
        self.assertEqual(parse_tds_tcs_section("T.D.S_94J (1026)"), ("TDS", "194J"))
        self.assertEqual(parse_tds_tcs_section("T.D.S_92B"), ("TDS", "192B"))
        self.assertEqual(parse_tds_tcs_section("T.D.S_94A"), ("TDS", "194A"))

    def test_full_tds_codes_pass_through(self):
        self.assertEqual(parse_tds_tcs_section("T.D.S_194Q"), ("TDS", "194Q"))
        self.assertEqual(parse_tds_tcs_section("T.D.S.195"), ("TDS", "195"))

    def test_tcs_206c_maps_to_206c1h(self):
        self.assertEqual(parse_tds_tcs_section("T.C.S_206C"), ("TCS", "206C1H"))

    def test_non_tds_returns_none(self):
        self.assertIsNone(parse_tds_tcs_section("Ornament Sales"))
        self.assertIsNone(parse_tds_tcs_section("Provident Fund (Employee)"))
        self.assertIsNone(parse_tds_tcs_section("TDS Payable"))  # no section number


class ResolveSectionLedgerTests(TestCase):
    def setUp(self):
        call_command("setup_account_groups")
        RetailMaster.objects.create(
            retail_code="R001", retail_name="HO", address_line1="x", phone="1",
        )
        call_command("setup_tds_initial_data")

    def test_resolves_to_seeded_section_ledger(self):
        led = resolve_section_ledger("T.D.S_94C")
        self.assertIsNotNone(led)
        self.assertEqual(led.ac_name, "TDS Payable u/s 194C")

    def test_unseeded_section_returns_none(self):
        # 194D is not seeded -> no target
        self.assertIsNone(resolve_section_ledger("T.D.S_94D"))

    def test_synonyms_present(self):
        self.assertIn("provident fund (employee)", EXTRA_SYNONYMS)
        self.assertEqual(EXTRA_SYNONYMS["provident fund (employee)"], "pf payable")
