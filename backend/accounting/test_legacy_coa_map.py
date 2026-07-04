from django.test import TestCase
from accounting.models import Account
from accounting.legacy_coa_map import (
    LEGACY_TO_STANDARD, is_legacy_code, resolve_standard_group,
)
from django.core.management import call_command


class LegacyCoaMapTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Seed the standard chart of accounts.
        call_command("setup_account_groups")

    def test_every_target_code_exists_in_standard_tree(self):
        missing = sorted(
            {c for c in LEGACY_TO_STANDARD.values()
             if not Account.objects.filter(code=c).exists()}
        )
        self.assertEqual(missing, [], f"Unknown standard codes: {missing}")

    def test_no_target_is_itself_a_legacy_code(self):
        bad = [c for c in LEGACY_TO_STANDARD.values() if is_legacy_code(c)]
        self.assertEqual(bad, [])

    def test_resolve_returns_standard_account(self):
        acc = resolve_standard_group("GM-13")
        self.assertIsNotNone(acc)
        self.assertEqual(acc.code, "INC-DIR-SAL")

    def test_resolve_unmapped_returns_none(self):
        self.assertIsNone(resolve_standard_group("GM-999"))

    def test_is_legacy_code(self):
        self.assertTrue(is_legacy_code("SG-12"))
        self.assertTrue(is_legacy_code("MG-3"))
        self.assertFalse(is_legacy_code("INC-DIR-SAL"))
        self.assertFalse(is_legacy_code(None))
