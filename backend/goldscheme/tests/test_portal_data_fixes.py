from datetime import date
from decimal import Decimal

from django.test import TestCase

from mastersconfig.models import RetailMaster
from contacts.models import Ledger
from goldscheme.models import SchemeMaster as Scheme, SchemeEnrollment
from goldscheme.services.payment import validate_payment


class PaymentCapTest(TestCase):
    def _make_enrollment(self, payments_made, installment_amount, tenure_months, max_amount):
        retail = RetailMaster.objects.create(
            retail_name="R", retail_code="RP",
            address_line1="1 St", phone="9999999999", bill_series="RPS")
        led = Ledger.objects.create(ac_name="C", display_name="C", retail_code=retail)
        scheme = Scheme.objects.create(
            name="Test Scheme", scheme_code="TS1",
            scheme_type="INSTALLMENT", gold_price_mode="CURRENT",
            tenure_months=tenure_months,
            min_amount=Decimal("1000"), max_amount=max_amount,
            retail=retail,
        )
        enr = SchemeEnrollment.objects.create(
            enrollment_no="ENR1",
            scheme=scheme, customer=led,
            start_date=date(2026, 1, 1), maturity_date=date(2026, 12, 1),
            installment_amount=Decimal(installment_amount),
            payments_made=payments_made, status="ACTIVE",
            retail=retail,
        )
        return enr

    def test_payment_above_remaining_value_rejected_when_no_max(self):
        enr = self._make_enrollment(payments_made=10, installment_amount="1000",
                                    tenure_months=11, max_amount=None)
        errors = validate_payment(enr, Decimal("5000"))  # remaining = 1 * 1000
        self.assertTrue(any("remaining" in e.lower() or "exceed" in e.lower() for e in errors))

    def test_payment_within_remaining_value_ok_when_no_max(self):
        enr = self._make_enrollment(payments_made=10, installment_amount="1000",
                                    tenure_months=11, max_amount=None)
        errors = validate_payment(enr, Decimal("1000"))
        self.assertEqual(errors, [])
