import datetime
from unittest import mock
from django.db import IntegrityError
from django.test import TestCase
from mastersconfig.models import RetailMaster, FiscalYearMaster
from contacts.models import Ledger
from manufacturing.models import RefinaryIssue
from accounting.utils import save_with_bill_number


class SaveWithBillNumberTests(TestCase):
    def setUp(self):
        self.retail = RetailMaster.objects.create(
            retail_name="S1", retail_code="R001", address_line1="x",
            phone="9", bill_series="S-R001",
        )
        self.fy = FiscalYearMaster.objects.create(
            retail=self.retail, fy_code="26-27",
            fy_start=datetime.date(2026, 4, 1), fy_end=datetime.date(2027, 3, 31),
        )
        self.retail.active_fy = self.fy
        self.retail.save(update_fields=["active_fy"])
        self.ldgr = Ledger.objects.create(
            ac_name="Refiner", display_name="Refiner", retail_code=self.retail,
        )

    def _new(self):
        return RefinaryIssue(date1=datetime.date(2026, 4, 15), billno="",
                             ldgr=self.ldgr, retail=self.retail, fiscal_year=self.fy)

    def test_assigns_incrementing_numbers(self):
        a = save_with_bill_number(self._new(), self.retail, "REF/ISS", fy=self.fy)
        b = save_with_bill_number(self._new(), self.retail, "REF/ISS", fy=self.fy)
        self.assertTrue(a.billno.endswith("00001"), a.billno)
        self.assertTrue(b.billno.endswith("00002"), b.billno)

    def test_retries_past_a_collision(self):
        # First save hits a unique collision (IntegrityError); the helper must
        # regenerate a fresh number and retry, landing on the next one.
        real_save = RefinaryIssue.save
        state = {"n": 0}
        def flaky_save(inst, *a, **k):
            state["n"] += 1
            if state["n"] == 1:
                raise IntegrityError("dup")
            return real_save(inst, *a, **k)
        with mock.patch.object(RefinaryIssue, "save", autospec=True, side_effect=flaky_save):
            saved = save_with_bill_number(self._new(), self.retail, "REF/ISS", fy=self.fy)
        self.assertTrue(saved.billno.endswith("00002"), saved.billno)

    def test_raises_after_max_retries(self):
        taken = save_with_bill_number(self._new(), self.retail, "REF/ISS", fy=self.fy).billno
        with mock.patch("accounting.utils.get_next_bill_number", return_value=taken):
            with mock.patch.object(RefinaryIssue, "save", side_effect=IntegrityError("dup")):
                with self.assertRaises(IntegrityError):
                    save_with_bill_number(self._new(), self.retail, "REF/ISS", fy=self.fy, max_retries=3)
