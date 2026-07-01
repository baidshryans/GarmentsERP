"""
Race-safe voucher numbering tests for QuotationSerializer.

Task 5 — Quotation (QuotationSerializer)
-----------------------------------------
Full integration test: the create() is simple (no journal entry, no GST
master lookups). We build a minimal nested payload, call the serializer
directly, and assert that the bogus client-supplied quotation_no is ignored
and two successive creates yield ..00001 / ..00002.

Pre-conversion failure:
  sales/serializers.py line 3116:
    ``quotation = Quotation.objects.create(**validated_data)``
  At that point validated_data still contains the client-supplied 'quotation_no'.
  This test is designed to FAIL before the patch and PASS after.
"""

import datetime

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from mastersconfig.models import FiscalYearMaster, RetailMaster
from sales.serializers import QuotationSerializer


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_retail_and_fy(retail_code: str):
    retail = RetailMaster.objects.create(
        retail_name=f"Test Retail {retail_code}",
        retail_code=retail_code,
        phone="0000000000",
        address_line1="Test Address",
        bill_series=retail_code,
    )
    fy = FiscalYearMaster.objects.create(
        retail=retail,
        fy_code="25-26",
        fy_start=datetime.date(2025, 4, 1),
        fy_end=datetime.date(2026, 3, 31),
    )
    retail.active_fy = fy
    retail.save(update_fields=["active_fy"])
    return retail, fy


def _make_request(retail):
    factory = APIRequestFactory()
    request = factory.post("/")
    request.retail = retail
    return request


# ===========================================================================
# Task 5 — Quotation (full integration, fail-first TDD)
# ===========================================================================

class QuotationNumberingTest(TestCase):
    """
    Full serializer-level integration test.

    Run BEFORE the patch to confirm the bogus number IS persisted (test fails).
    Run AFTER the patch to confirm the bogus number is ignored.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("TSQT")

    def _base_payload(self, bogus_quotation_no: str) -> dict:
        return {
            "date1": "2025-06-01",
            "quotation_no": bogus_quotation_no,
            "retail": self.retail.pk,
            "items": [],
        }

    def _create_via_serializer(self, bogus: str):
        request = _make_request(self.retail)
        ser = QuotationSerializer(
            data=self._base_payload(bogus),
            context={"request": request},
        )
        ser.is_valid(raise_exception=True)
        return ser.save()

    def test_bogus_quotation_no_not_persisted(self):
        """After conversion: the client-supplied bogus number must not be saved."""
        obj = self._create_via_serializer("BOGUS-9999")
        self.assertNotEqual(
            obj.quotation_no, "BOGUS-9999",
            "Bogus quotation_no was persisted — conversion not applied.",
        )

    def test_two_creates_produce_sequential_numbers(self):
        """After conversion: two successive creates yield ..00001 then ..00002."""
        first = self._create_via_serializer("BOGUS-A")
        second = self._create_via_serializer("BOGUS-B")

        self.assertNotEqual(first.quotation_no, second.quotation_no, "Both quotations got the same number.")
        self.assertTrue(
            first.quotation_no.endswith("00001"),
            f"First quotation_no {first.quotation_no!r} does not end in 00001",
        )
        self.assertTrue(
            second.quotation_no.endswith("00002"),
            f"Second quotation_no {second.quotation_no!r} does not end in 00002",
        )
