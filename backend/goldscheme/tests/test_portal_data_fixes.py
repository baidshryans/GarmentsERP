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


from unittest.mock import patch
from rest_framework.test import APIClient
from goldscheme.models import (
    CustomerPortalAccount, CustomerPortalToken,
    SchemeMaster as Scheme, SchemeEnrollment,
)


class DashboardNoWriteTest(TestCase):
    @patch("goldscheme.portal_views.check_and_update_maturity")
    def test_dashboard_get_does_not_mutate_maturity(self, mock_maturity):
        retail = RetailMaster.objects.create(retail_name="R", retail_code="RD",
            address_line1="1 St", phone="9999999999", bill_series="RDS")
        led = Ledger.objects.create(ac_name="C", display_name="C", retail_code=retail)
        scheme = Scheme.objects.create(
            name="Test Scheme", scheme_code="TSD",
            scheme_type="INSTALLMENT", gold_price_mode="CURRENT",
            tenure_months=11, min_amount=Decimal("1000"), max_amount=None,
            retail=retail,
        )
        SchemeEnrollment.objects.create(
            enrollment_no="ENRD", scheme=scheme, customer=led,
            start_date=date(2026, 1, 1), maturity_date=date(2026, 12, 1),
            installment_amount=Decimal("1000"), payments_made=1, status="ACTIVE",
            retail=retail,
        )
        acc = CustomerPortalAccount.objects.create(primary_email="d@x.com")
        acc.linked_ledgers.add(led)
        token = CustomerPortalToken.objects.create(account=acc, retail=retail)
        c = APIClient(); c.credentials(HTTP_AUTHORIZATION=f"PortalToken {token.token}")
        resp = c.get("/goldscheme/api/portal/dashboard/")
        self.assertEqual(resp.status_code, 200)
        mock_maturity.assert_not_called()
