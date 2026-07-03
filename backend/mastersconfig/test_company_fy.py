from datetime import date
from django.test import TestCase
from mastersconfig.models import SystemSettings, FiscalYearMaster, RetailMaster


class CompanyActiveFYTests(TestCase):
    def _fy(self, code="26-27"):
        # NOTE: retail= is required until a later task removes it.
        retail = RetailMaster.objects.create(
            retail_name="Store 1",
            retail_code="R001",
            address_line1="123 St",
            phone="9999",
        )
        return FiscalYearMaster.objects.create(
            retail=retail, fy_code=code,
            fy_start=date(2026, 4, 1), fy_end=date(2027, 3, 31),
        )

    def test_set_company_active_fy_sets_singleton(self):
        fy = self._fy()
        SystemSettings.set_company_active_fy(fy)
        self.assertEqual(SystemSettings.get().active_fy_id, fy.id)

    def test_set_company_active_fy_accepts_none(self):
        SystemSettings.set_company_active_fy(None)
        self.assertIsNone(SystemSettings.get().active_fy_id)
