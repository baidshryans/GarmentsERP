from datetime import date
from django.test import TestCase
from mastersconfig.models import SystemSettings, FiscalYearMaster, RetailMaster


class CompanyActiveFYTests(TestCase):
    def _fy(self, code="26-27"):
        return FiscalYearMaster.objects.create(
            fy_code=code,
            fy_start=date(2026, 4, 1), fy_end=date(2027, 3, 31),
        )

    def test_set_company_active_fy_sets_singleton(self):
        fy = self._fy()
        SystemSettings.set_company_active_fy(fy)
        self.assertEqual(SystemSettings.get().active_fy_id, fy.id)

    def test_set_company_active_fy_accepts_none(self):
        SystemSettings.set_company_active_fy(None)
        self.assertIsNone(SystemSettings.get().active_fy_id)


class GlobalCloseTests(TestCase):
    """Verify the company-global fiscal-year model: a single active FY applies
    to every branch, and a hard-close blocks transactions for all of them."""

    def setUp(self):
        self.ho = RetailMaster.objects.create(
            retail_name="Head Office",
            retail_code="HO",
            address_line1="123 St",
            phone="9999",
        )
        self.asansol = RetailMaster.objects.create(
            retail_name="Asansol",
            retail_code="ASN",
            address_line1="456 St",
            phone="8888",
        )
        self.fy = FiscalYearMaster.objects.create(
            fy_code="26-27", fy_start=date(2026, 4, 1), fy_end=date(2027, 3, 31))
        SystemSettings.set_company_active_fy(self.fy)

    def test_active_fy_same_for_every_branch(self):
        self.assertEqual(self.ho.active_fy_id, self.fy.id)
        self.assertEqual(self.asansol.active_fy_id, self.fy.id)  # never blank

    def test_hard_close_blocks_all_branches(self):
        from mastersconfig.fy_utils import check_fy_open_for_transaction
        from rest_framework.exceptions import ValidationError
        self.fy.is_hard_closed = True
        self.fy.save(update_fields=['is_hard_closed'])
        for retail in (self.ho, self.asansol):
            with self.assertRaises(ValidationError):
                check_fy_open_for_transaction(retail, 'SV')
