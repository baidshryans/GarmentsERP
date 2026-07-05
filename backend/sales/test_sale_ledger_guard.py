from django.test import TestCase
from rest_framework.exceptions import ValidationError
from sales.serializers import _raise_missing_ledger


class SaleLedgerGuardTests(TestCase):
    """The four sale GL-posting sites that dereference item.sale_ledger.ac_name now
    guard on a missing ledger via _raise_missing_ledger, turning what used to be an
    unguarded AttributeError (HTTP 500) into a clear DRF validation error (HTTP 400)."""

    def test_missing_ledger_raises_validation_error_not_crash(self):
        with self.assertRaises(ValidationError) as ctx:
            _raise_missing_ledger("Sale Ledger for item 'Ornament'")
        self.assertIn('ledger_config', ctx.exception.detail)
        self.assertIn('Sale Ledger', str(ctx.exception.detail['ledger_config']))
