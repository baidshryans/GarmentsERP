"""
Race-safe voucher numbering tests for manufacturing serializers.

Tasks 6–9
----------
Task 6 — RefinaryIssue   (REF/ISS)
Task 7 — RefinaryReceive (REF/REC)
Task 8 — MeltingIssue   (MLT/ISS)
Task 9 — MeltingReceive  (MLT/REC)

Test strategy
--------------
The four serializers all require deep nested payloads (RefinaryReceive /
MeltingReceive detail rows cross-reference an existing Issue billno via a
SlugRelatedField, meaning the Issue record must exist in the DB before the
Receive can be validated). Additionally the detail rows require Item,
PurityMaster, and Packet master records, plus real Ledger records, making
full integration feasible.

We therefore use a TWO-TIER approach:
  (a) Full integration test for RefinaryIssue and MeltingIssue (parent-only
      payload, no detail rows required for the billno test).
  (b) For RefinaryReceive and MeltingReceive: bare save_with_bill_number
      sequence test (model instantiation + helper call, no serializer path) PLUS
      a stub test patching `accounting.utils.save_with_bill_number` to assert
      it is called by the serializer's create().

Pre-conversion failure (Tasks 6–9):
  manufacturing/serializer.py lines 1751, 1803, 1856, 1909:
    ``parent_instance = <Model>.objects.create(**validated_data)``
  At those points validated_data still contains the client-supplied 'billno'.
  Confirmed by manual code inspection for all four tasks.
"""

import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from contacts.models import Ledger
from goldrates.models import PurityMaster
from mastersconfig.models import FiscalYearMaster, Item, RetailMaster
from manufacturing.models import (
    MeltingIssue,
    MeltingReceive,
    RefinaryIssue,
    RefinaryReceive,
)
from accounting.utils import save_with_bill_number


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_retail_and_fy(retail_code: str):
    retail = RetailMaster.objects.create(
        retail_name=f"Test Retail {retail_code}",
        retail_code=retail_code,
        phone="0000000000",
        address_line1="Test Address",
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


def _make_ledger(name: str):
    return Ledger.objects.create(
        ac_name=name,
        display_name=name,
        b2b=False,
        tds_applicable=False,
        is_system=False,
    )


def _make_request(retail):
    factory = APIRequestFactory()
    request = factory.post("/")
    request.retail = retail
    return request


# ===========================================================================
# Task 6 — RefinaryIssue (full integration, fail-first TDD)
# ===========================================================================

class RefinaryIssueNumberingTest(TestCase):
    """
    Full serializer-level integration test for RefinaryIssueSerializer.

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 1751:
        ``parent_instance = RefinaryIssue.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'billno' at that point.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("TSRI")
        self.ledger = _make_ledger("Refinery Vendor RI")

    def _base_payload(self, bogus_billno: str) -> dict:
        return {
            "date1": "2025-06-01",
            "billno": bogus_billno,
            "ldgr": self.ledger.pk,
            "retail": self.retail.pk,
            "refinaryissuedetail_set": [],
        }

    def _create_via_serializer(self, bogus: str):
        from manufacturing.serializer import RefinaryIssueSerializer
        request = _make_request(self.retail)
        ser = RefinaryIssueSerializer(
            data=self._base_payload(bogus),
            context={"request": request},
        )
        ser.is_valid(raise_exception=True)
        return ser.save()

    def test_bogus_billno_not_persisted(self):
        """After conversion: the client-supplied bogus billno must not be saved."""
        obj = self._create_via_serializer("BOGUS-REF-ISS-9999")
        self.assertNotEqual(
            obj.billno, "BOGUS-REF-ISS-9999",
            "Bogus billno was persisted — conversion not applied.",
        )

    def test_two_creates_produce_sequential_numbers(self):
        """After conversion: two successive creates yield ..00001 then ..00002."""
        first = self._create_via_serializer("BOGUS-A")
        second = self._create_via_serializer("BOGUS-B")

        self.assertNotEqual(first.billno, second.billno, "Both RefinaryIssues got the same number.")
        self.assertTrue(
            first.billno.endswith("00001"),
            f"First billno {first.billno!r} does not end in 00001",
        )
        self.assertTrue(
            second.billno.endswith("00002"),
            f"Second billno {second.billno!r} does not end in 00002",
        )


# ===========================================================================
# Task 7 — RefinaryReceive (fallback: bare sequence + stub)
# ===========================================================================

class RefinaryReceiveNumberingFallbackTest(TestCase):
    """
    Fallback path: RefinaryReceiveDetail rows require an existing RefinaryIssue
    billno via a SlugRelatedField, adding mandatory cross-entity fixture setup.

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 1803:
        ``parent_instance = RefinaryReceive.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'billno'.

    Tests here:
      (a) Bare save_with_bill_number sequence test for REF/REC prefix.
      (b) Stub test asserting save_with_bill_number is called by the serializer.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("TSRR")
        self.ledger = _make_ledger("Refinery Vendor RR")

    # -- (a) Bare sequence test -----------------------------------------------

    def test_ref_rec_sequence_increments(self):
        """save_with_bill_number advances the REF/REC sequence correctly."""
        r1 = RefinaryReceive(
            date1=datetime.date(2025, 6, 1),
            retail=self.retail,
            fiscal_year=self.fy,
            ldgr=self.ledger,
        )
        save_with_bill_number(r1, self.retail, "REF/REC", field="billno", fy=self.fy)

        r2 = RefinaryReceive(
            date1=datetime.date(2025, 6, 1),
            retail=self.retail,
            fiscal_year=self.fy,
            ldgr=self.ledger,
        )
        save_with_bill_number(r2, self.retail, "REF/REC", field="billno", fy=self.fy)

        self.assertTrue(r1.billno.endswith("00001"), f"First billno {r1.billno!r} must end in 00001")
        self.assertTrue(r2.billno.endswith("00002"), f"Second billno {r2.billno!r} must end in 00002")
        self.assertNotEqual(r1.billno, r2.billno)

    # -- (b) Stub-level regression: save_with_bill_number is called -----------

    def test_serializer_create_calls_save_with_bill_number(self):
        """
        After conversion: RefinaryReceiveSerializer.create() must call
        save_with_bill_number (not pass billno directly to .objects.create).
        """
        from manufacturing.serializer import RefinaryReceiveSerializer

        with patch("accounting.utils.save_with_bill_number") as mock_swbn:
            mock_swbn.side_effect = lambda inst, retail, prefix, **kw: setattr(
                inst, "billno", "RR/TSRR/25-26/00001"
            )

            with patch(
                "manufacturing.serializer.RefinaryReceive.objects.create",
                return_value=RefinaryReceive(
                    pk=1,
                    date1=datetime.date(2025, 6, 1),
                    billno="RR/TSRR/25-26/00001",
                    ldgr=self.ledger,
                    retail=self.retail,
                    fiscal_year=self.fy,
                ),
            ):
                request = _make_request(self.retail)
                payload = {
                    "date1": "2025-06-01",
                    "billno": "CLIENT-BOGUS-RR-99",
                    "ldgr": self.ledger.pk,
                    "retail": self.retail.pk,
                    "refinaryreceivedetail_set": [],
                }
                ser = RefinaryReceiveSerializer(
                    data=payload, context={"request": request}
                )
                try:
                    ser.is_valid(raise_exception=True)
                    ser.save()
                except Exception:
                    pass

                self.assertTrue(
                    mock_swbn.called,
                    "save_with_bill_number was NOT called — conversion not applied to RefinaryReceiveSerializer.",
                )


# ===========================================================================
# Task 8 — MeltingIssue (full integration, fail-first TDD)
# ===========================================================================

class MeltingIssueNumberingTest(TestCase):
    """
    Full serializer-level integration test for MeltingIssueSerializer.

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 1856:
        ``parent_instance = MeltingIssue.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'billno'.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("TSMI")
        self.ledger = _make_ledger("Melting Vendor MI")

    def _base_payload(self, bogus_billno: str) -> dict:
        return {
            "date1": "2025-06-01",
            "billno": bogus_billno,
            "ldgr": self.ledger.pk,
            "retail": self.retail.pk,
            "meltingissuedetail_set": [],
        }

    def _create_via_serializer(self, bogus: str):
        from manufacturing.serializer import MeltingIssueSerializer
        request = _make_request(self.retail)
        ser = MeltingIssueSerializer(
            data=self._base_payload(bogus),
            context={"request": request},
        )
        ser.is_valid(raise_exception=True)
        return ser.save()

    def test_bogus_billno_not_persisted(self):
        """After conversion: the client-supplied bogus billno must not be saved."""
        obj = self._create_via_serializer("BOGUS-MLT-ISS-9999")
        self.assertNotEqual(
            obj.billno, "BOGUS-MLT-ISS-9999",
            "Bogus billno was persisted — conversion not applied.",
        )

    def test_two_creates_produce_sequential_numbers(self):
        """After conversion: two successive creates yield ..00001 then ..00002."""
        first = self._create_via_serializer("BOGUS-A")
        second = self._create_via_serializer("BOGUS-B")

        self.assertNotEqual(first.billno, second.billno, "Both MeltingIssues got the same number.")
        self.assertTrue(
            first.billno.endswith("00001"),
            f"First billno {first.billno!r} does not end in 00001",
        )
        self.assertTrue(
            second.billno.endswith("00002"),
            f"Second billno {second.billno!r} does not end in 00002",
        )


# ===========================================================================
# Task 9 — MeltingReceive (fallback: bare sequence + stub)
# ===========================================================================

class MeltingReceiveNumberingFallbackTest(TestCase):
    """
    Fallback path: MeltingReceiveDetail rows require an existing MeltingIssue
    billno via a SlugRelatedField, adding mandatory cross-entity fixture setup.

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 1909:
        ``parent_instance = MeltingReceive.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'billno'.

    Tests here:
      (a) Bare save_with_bill_number sequence test for MLT/REC prefix.
      (b) Stub test asserting save_with_bill_number is called by the serializer.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("TSMR")
        self.ledger = _make_ledger("Melting Vendor MR")

    # -- (a) Bare sequence test -----------------------------------------------

    def test_mlt_rec_sequence_increments(self):
        """save_with_bill_number advances the MLT/REC sequence correctly."""
        r1 = MeltingReceive(
            date1=datetime.date(2025, 6, 1),
            retail=self.retail,
            fiscal_year=self.fy,
            ldgr=self.ledger,
        )
        save_with_bill_number(r1, self.retail, "MLT/REC", field="billno", fy=self.fy)

        r2 = MeltingReceive(
            date1=datetime.date(2025, 6, 1),
            retail=self.retail,
            fiscal_year=self.fy,
            ldgr=self.ledger,
        )
        save_with_bill_number(r2, self.retail, "MLT/REC", field="billno", fy=self.fy)

        self.assertTrue(r1.billno.endswith("00001"), f"First billno {r1.billno!r} must end in 00001")
        self.assertTrue(r2.billno.endswith("00002"), f"Second billno {r2.billno!r} must end in 00002")
        self.assertNotEqual(r1.billno, r2.billno)

    # -- (b) Stub-level regression: save_with_bill_number is called -----------

    def test_serializer_create_calls_save_with_bill_number(self):
        """
        After conversion: MeltingReceiveSerializer.create() must call
        save_with_bill_number (not pass billno directly to .objects.create).
        """
        from manufacturing.serializer import MeltingReceiveSerializer

        with patch("accounting.utils.save_with_bill_number") as mock_swbn:
            mock_swbn.side_effect = lambda inst, retail, prefix, **kw: setattr(
                inst, "billno", "MR/TSMR/25-26/00001"
            )

            with patch(
                "manufacturing.serializer.MeltingReceive.objects.create",
                return_value=MeltingReceive(
                    pk=1,
                    date1=datetime.date(2025, 6, 1),
                    billno="MR/TSMR/25-26/00001",
                    ldgr=self.ledger,
                    retail=self.retail,
                    fiscal_year=self.fy,
                ),
            ):
                request = _make_request(self.retail)
                payload = {
                    "date1": "2025-06-01",
                    "billno": "CLIENT-BOGUS-MR-99",
                    "ldgr": self.ledger.pk,
                    "retail": self.retail.pk,
                    "meltingreceivedetail_set": [],
                }
                ser = MeltingReceiveSerializer(
                    data=payload, context={"request": request}
                )
                try:
                    ser.is_valid(raise_exception=True)
                    ser.save()
                except Exception:
                    pass

                self.assertTrue(
                    mock_swbn.called,
                    "save_with_bill_number was NOT called — conversion not applied to MeltingReceiveSerializer.",
                )


# ===========================================================================
# Task 10 -- HallmarkIssue (HMIS) -- full integration
# ===========================================================================

class HallmarkIssueNumberingTest(TestCase):
    """
    Full serializer-level integration test for HallmarkIssueForPostSerializer.

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 1452:
        ``hallmark_issue_instance = HallmarkIssue.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'issue_slip_no' at that point.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("HMIS")
        self.hm_center = _make_ledger("HM Centre T10")

    def _create_via_serializer(self, bogus: str):
        from manufacturing.serializer import HallmarkIssueForPostSerializer
        request = _make_request(self.retail)
        payload = {
            "issue_slip_no": bogus,
            "date1": "2025-06-01",
            "hallmark_center": self.hm_center.pk,
            "hallmarkissueitem_set": [],
            "retail": self.retail.pk,
        }
        ser = HallmarkIssueForPostSerializer(data=payload, context={"request": request})
        ser.is_valid(raise_exception=True)
        return ser.save()

    def test_bogus_issue_slip_no_not_persisted(self):
        """After conversion: the client-supplied bogus issue_slip_no must not be saved."""
        obj = self._create_via_serializer("BOGUS-HMIS-9999")
        self.assertNotEqual(
            obj.issue_slip_no, "BOGUS-HMIS-9999",
            "Bogus issue_slip_no was persisted -- conversion not applied.",
        )

    def test_two_creates_produce_sequential_numbers(self):
        """After conversion: two successive creates yield ..00001 then ..00002."""
        first = self._create_via_serializer("BOGUS-A")
        second = self._create_via_serializer("BOGUS-B")
        self.assertNotEqual(first.issue_slip_no, second.issue_slip_no)
        self.assertTrue(
            first.issue_slip_no.endswith("00001"),
            f"First issue_slip_no {first.issue_slip_no!r} does not end in 00001",
        )
        self.assertTrue(
            second.issue_slip_no.endswith("00002"),
            f"Second issue_slip_no {second.issue_slip_no!r} does not end in 00002",
        )


# ===========================================================================
# Task 11 -- HallmarkReceive (HM/RE) -- fallback: bare sequence + stub
# ===========================================================================

class HallmarkReceiveNumberingFallbackTest(TestCase):
    """
    Fallback path: HallmarkReceiveItem rows require an existing HallmarkIssue
    and KarigarReceiveItem via FK, making full integration impractical.

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 1575:
        ``hallmark_receive_instance = HallmarkReceive.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'receive_slip_no'.

    Tests:
      (a) Bare save_with_bill_number sequence test for HM/RE prefix.
      (b) Stub test asserting save_with_bill_number is called by the serializer.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("HMRE")
        self.hm_center = _make_ledger("HM Centre T11")

    def test_hm_re_sequence_increments(self):
        """save_with_bill_number advances the HM/RE sequence correctly."""
        from manufacturing.models import HallmarkReceive
        r1 = HallmarkReceive(
            date1=datetime.date(2025, 6, 1),
            hallmark_center=self.hm_center,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r1, self.retail, "HM/RE", field="receive_slip_no", fy=self.fy)

        r2 = HallmarkReceive(
            date1=datetime.date(2025, 6, 1),
            hallmark_center=self.hm_center,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r2, self.retail, "HM/RE", field="receive_slip_no", fy=self.fy)

        self.assertTrue(r1.receive_slip_no.endswith("00001"), f"First {r1.receive_slip_no!r} must end in 00001")
        self.assertTrue(r2.receive_slip_no.endswith("00002"), f"Second {r2.receive_slip_no!r} must end in 00002")
        self.assertNotEqual(r1.receive_slip_no, r2.receive_slip_no)

    def test_serializer_create_calls_save_with_bill_number(self):
        """After conversion: HallmarkReceiveForPostSerializer.create() must call save_with_bill_number."""
        from manufacturing.models import HallmarkReceive
        from manufacturing.serializer import HallmarkReceiveForPostSerializer

        with patch("accounting.utils.save_with_bill_number") as mock_swbn:
            mock_swbn.side_effect = lambda inst, retail, prefix, **kw: setattr(
                inst, "receive_slip_no", "HM/RE/HMRE/25-26/00001"
            )

            with patch(
                "manufacturing.serializer.HallmarkReceive.objects.create",
                return_value=HallmarkReceive(
                    pk=1,
                    date1=datetime.date(2025, 6, 1),
                    receive_slip_no="HM/RE/HMRE/25-26/00001",
                    hallmark_center=self.hm_center,
                    retail=self.retail,
                    fiscal_year=self.fy,
                ),
            ):
                request = _make_request(self.retail)
                payload = {
                    "date1": "2025-06-01",
                    "receive_slip_no": "CLIENT-BOGUS-HR-99",
                    "hallmark_center": self.hm_center.pk,
                    "hallmarkreceiveitem_set": [],
                    "retail": self.retail.pk,
                }
                ser = HallmarkReceiveForPostSerializer(data=payload, context={"request": request})
                try:
                    ser.is_valid(raise_exception=True)
                    ser.save()
                except Exception:
                    pass

                self.assertTrue(
                    mock_swbn.called,
                    "save_with_bill_number was NOT called -- conversion not applied to HallmarkReceiveForPostSerializer.",
                )


# ===========================================================================
# Task 12 -- RepairJobCard (RJC) -- full integration
# NOTE: The model field is rjc_no (not billno as stated in spec).
# ===========================================================================

class RepairJobCardNumberingTest(TestCase):
    """
    Full serializer-level integration test for RepairJobCardSerializer.

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 2155:
        ``job_card = RepairJobCard.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'rjc_no' at that point.

    Note: The task spec says field=billno but manufacturing/models.py L744
    confirms the actual field name is rjc_no. This test and conversion use rjc_no.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("RJCT")
        self.customer = _make_ledger("RJC Customer T12")
        from contacts.models import LedgerRole
        LedgerRole.objects.create(ledger=self.customer, role="CO")

    def _create_via_serializer(self, bogus: str):
        from manufacturing.serializer import RepairJobCardSerializer
        request = _make_request(self.retail)
        payload = {
            "rjc_no": bogus,
            "date1": "2025-06-01",
            "customer": self.customer.pk,
            "retail": self.retail.pk,
            "fiscal_year": self.fy.pk,
            "stones": [],
            "losses": [],
            "karigar_links": [],
        }
        ser = RepairJobCardSerializer(data=payload, context={"request": request})
        ser.is_valid(raise_exception=True)
        return ser.save()

    def test_bogus_rjc_no_not_persisted(self):
        """After conversion: the client-supplied bogus rjc_no must not be saved."""
        obj = self._create_via_serializer("BOGUS-RJC-9999")
        self.assertNotEqual(
            obj.rjc_no, "BOGUS-RJC-9999",
            "Bogus rjc_no was persisted -- conversion not applied.",
        )

    def test_two_creates_produce_sequential_numbers(self):
        """After conversion: two successive creates yield ..00001 then ..00002."""
        first = self._create_via_serializer("BOGUS-A")
        second = self._create_via_serializer("BOGUS-B")
        self.assertNotEqual(first.rjc_no, second.rjc_no)
        self.assertTrue(
            first.rjc_no.endswith("00001"),
            f"First rjc_no {first.rjc_no!r} does not end in 00001",
        )
        self.assertTrue(
            second.rjc_no.endswith("00002"),
            f"Second rjc_no {second.rjc_no!r} does not end in 00002",
        )


# ===========================================================================
# Task 13 -- SampleIssue (IS) -- full integration
# ===========================================================================

class SampleIssueNumberingTest(TestCase):
    """
    Full serializer-level integration test for SampleIssueSerializer.

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 540:
        ``inst = SampleIssue.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'billno' at that point.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("SIIS")
        self.karigar = _make_ledger("Karigar T13")

    def _create_via_serializer(self, bogus: str):
        from manufacturing.serializer import SampleIssueSerializer
        request = _make_request(self.retail)
        payload = {
            "billno": bogus,
            "date1": "2025-06-01",
            "karigar_ldgr": self.karigar.pk,
            "retail": self.retail.pk,
            "fiscal_year": self.fy.pk,
            "items": [],
        }
        ser = SampleIssueSerializer(data=payload, context={"request": request})
        ser.is_valid(raise_exception=True)
        return ser.save()

    def test_bogus_billno_not_persisted(self):
        """After conversion: the client-supplied bogus billno must not be saved."""
        obj = self._create_via_serializer("BOGUS-IS-9999")
        self.assertNotEqual(
            obj.billno, "BOGUS-IS-9999",
            "Bogus billno was persisted -- conversion not applied.",
        )

    def test_two_creates_produce_sequential_numbers(self):
        """After conversion: two successive creates yield ..00001 then ..00002."""
        first = self._create_via_serializer("BOGUS-A")
        second = self._create_via_serializer("BOGUS-B")
        self.assertNotEqual(first.billno, second.billno)
        self.assertTrue(
            first.billno.endswith("00001"),
            f"First billno {first.billno!r} does not end in 00001",
        )
        self.assertTrue(
            second.billno.endswith("00002"),
            f"Second billno {second.billno!r} does not end in 00002",
        )


# ===========================================================================
# Task 14a -- KarigarGoldIssue (IV/GL) -- fallback: bare sequence + stub
# ===========================================================================

class KarigarGoldIssueNumberingFallbackTest(TestCase):
    """
    Fallback path for KarigarGoldIssueSerializer (KarigarGoldIssueHeader).

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 360:
        ``parent_instance = KarigarGoldIssueHeader.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'billno' at that point.
      generate_gold_issue_billno() in manufacturing/utils.py exists but is NOT
      called by create().

    Tests:
      (a) Bare save_with_bill_number sequence test for IV/GL prefix.
      (b) Stub test asserting save_with_bill_number is called by the serializer.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("KGIT")
        self.karigar = _make_ledger("Gold Issue Karigar T14a")

    # -- (a) Bare sequence test -----------------------------------------------

    def test_iv_gl_sequence_increments(self):
        """save_with_bill_number advances the IV/GL sequence correctly."""
        from manufacturing.models import KarigarGoldIssueHeader
        r1 = KarigarGoldIssueHeader(
            billno="",
            date1=datetime.date(2025, 6, 1),
            slip_type="JO",
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r1, self.retail, "IV/GL", field="billno", fy=self.fy)

        r2 = KarigarGoldIssueHeader(
            billno="",
            date1=datetime.date(2025, 6, 1),
            slip_type="JO",
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r2, self.retail, "IV/GL", field="billno", fy=self.fy)

        self.assertTrue(r1.billno.endswith("00001"), f"First billno {r1.billno!r} must end in 00001")
        self.assertTrue(r2.billno.endswith("00002"), f"Second billno {r2.billno!r} must end in 00002")
        self.assertNotEqual(r1.billno, r2.billno)

    # -- (b) Stub-level regression: save_with_bill_number is called -----------

    def test_serializer_create_calls_save_with_bill_number(self):
        """After conversion: KarigarGoldIssueSerializer.create() must call save_with_bill_number."""
        from manufacturing.models import KarigarGoldIssueHeader
        from manufacturing.serializer import KarigarGoldIssueSerializer

        with patch("accounting.utils.save_with_bill_number") as mock_swbn:
            mock_swbn.side_effect = lambda inst, retail, prefix, **kw: setattr(
                inst, "billno", "IV/GL/KGIT/25-26/00001"
            )

            with patch(
                "manufacturing.serializer.KarigarGoldIssueHeader.objects.create",
                return_value=KarigarGoldIssueHeader(
                    pk=1,
                    billno="IV/GL/KGIT/25-26/00001",
                    date1=datetime.date(2025, 6, 1),
                    slip_type="JO",
                    karigar_ldgr=self.karigar,
                    retail=self.retail,
                    fiscal_year=self.fy,
                ),
            ):
                request = _make_request(self.retail)
                payload = {
                    "billno": "CLIENT-BOGUS-IVGL-99",
                    "date1": "2025-06-01",
                    "slip_type": "JO",
                    "karigar_ldgr": self.karigar.pk,
                    "retail": self.retail.pk,
                    "karigargoldissue_set": [],
                }
                ser = KarigarGoldIssueSerializer(data=payload, context={"request": request})
                try:
                    ser.is_valid(raise_exception=True)
                    ser.save()
                except Exception:
                    pass

                self.assertTrue(
                    mock_swbn.called,
                    "save_with_bill_number was NOT called -- conversion not applied to KarigarGoldIssueSerializer.",
                )


# ===========================================================================
# Task 14b -- KarigarStoneIssue (IV/STN) -- fallback: bare sequence + stub
# ===========================================================================

class KarigarStoneIssueNumberingFallbackTest(TestCase):
    """
    Fallback path for KarigarStoneIssueSerializer (KarigarStoneIssueHeader).

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 141:
        ``parent_instance = KarigarStoneIssueHeader.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'billno'.
      generate_stone_issue_billno() in manufacturing/utils.py exists but NOT called.

    Tests:
      (a) Bare save_with_bill_number sequence test for IV/STN prefix.
      (b) Stub test asserting save_with_bill_number is called by the serializer.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("KSIT")
        self.karigar = _make_ledger("Stone Issue Karigar T14b")

    # -- (a) Bare sequence test -----------------------------------------------

    def test_iv_stn_sequence_increments(self):
        """save_with_bill_number advances the IV/STN sequence correctly."""
        from manufacturing.models import KarigarStoneIssueHeader
        r1 = KarigarStoneIssueHeader(
            billno="",
            date1=datetime.date(2025, 6, 1),
            slip_type="JO",
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r1, self.retail, "IV/STN", field="billno", fy=self.fy)

        r2 = KarigarStoneIssueHeader(
            billno="",
            date1=datetime.date(2025, 6, 1),
            slip_type="JO",
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r2, self.retail, "IV/STN", field="billno", fy=self.fy)

        self.assertTrue(r1.billno.endswith("00001"), f"First billno {r1.billno!r} must end in 00001")
        self.assertTrue(r2.billno.endswith("00002"), f"Second billno {r2.billno!r} must end in 00002")
        self.assertNotEqual(r1.billno, r2.billno)

    # -- (b) Stub-level regression: save_with_bill_number is called -----------

    def test_serializer_create_calls_save_with_bill_number(self):
        """After conversion: KarigarStoneIssueSerializer.create() must call save_with_bill_number."""
        from manufacturing.models import KarigarStoneIssueHeader
        from manufacturing.serializer import KarigarStoneIssueSerializer

        with patch("accounting.utils.save_with_bill_number") as mock_swbn:
            mock_swbn.side_effect = lambda inst, retail, prefix, **kw: setattr(
                inst, "billno", "IV/STN/KSIT/25-26/00001"
            )

            with patch(
                "manufacturing.serializer.KarigarStoneIssueHeader.objects.create",
                return_value=KarigarStoneIssueHeader(
                    pk=1,
                    billno="IV/STN/KSIT/25-26/00001",
                    date1=datetime.date(2025, 6, 1),
                    slip_type="JO",
                    karigar_ldgr=self.karigar,
                    retail=self.retail,
                    fiscal_year=self.fy,
                ),
            ):
                request = _make_request(self.retail)
                payload = {
                    "billno": "CLIENT-BOGUS-IVSTN-99",
                    "date1": "2025-06-01",
                    "slip_type": "JO",
                    "karigar_ldgr": self.karigar.pk,
                    "retail": self.retail.pk,
                    "karigarstoneissue_set": [],
                }
                ser = KarigarStoneIssueSerializer(data=payload, context={"request": request})
                try:
                    ser.is_valid(raise_exception=True)
                    ser.save()
                except Exception:
                    pass

                self.assertTrue(
                    mock_swbn.called,
                    "save_with_bill_number was NOT called -- conversion not applied to KarigarStoneIssueSerializer.",
                )


# ===========================================================================
# Task 14c -- KarigarStoneReceive (REC/STN) -- fallback: bare sequence + stub
# ===========================================================================

class KarigarStoneReceiveNumberingFallbackTest(TestCase):
    """
    Fallback path for KarigarStoneReceiveSerializer (KarigarStoneReceiveHeader).

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 268:
        ``parent_instance = KarigarStoneReceiveHeader.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'billno'.
      generate_stone_rec_billno() in manufacturing/utils.py exists but NOT called.

    Tests:
      (a) Bare save_with_bill_number sequence test for REC/STN prefix.
      (b) Stub test asserting save_with_bill_number is called by the serializer.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("KSRT")
        self.karigar = _make_ledger("Stone Receive Karigar T14c")

    # -- (a) Bare sequence test -----------------------------------------------

    def test_rec_stn_sequence_increments(self):
        """save_with_bill_number advances the REC/STN sequence correctly."""
        from manufacturing.models import KarigarStoneReceiveHeader
        r1 = KarigarStoneReceiveHeader(
            billno="",
            date1=datetime.date(2025, 6, 1),
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r1, self.retail, "REC/STN", field="billno", fy=self.fy)

        r2 = KarigarStoneReceiveHeader(
            billno="",
            date1=datetime.date(2025, 6, 1),
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r2, self.retail, "REC/STN", field="billno", fy=self.fy)

        self.assertTrue(r1.billno.endswith("00001"), f"First billno {r1.billno!r} must end in 00001")
        self.assertTrue(r2.billno.endswith("00002"), f"Second billno {r2.billno!r} must end in 00002")
        self.assertNotEqual(r1.billno, r2.billno)

    # -- (b) Stub-level regression: save_with_bill_number is called -----------

    def test_serializer_create_calls_save_with_bill_number(self):
        """After conversion: KarigarStoneReceiveSerializer.create() must call save_with_bill_number."""
        from manufacturing.models import KarigarStoneReceiveHeader
        from manufacturing.serializer import KarigarStoneReceiveSerializer

        with patch("accounting.utils.save_with_bill_number") as mock_swbn:
            mock_swbn.side_effect = lambda inst, retail, prefix, **kw: setattr(
                inst, "billno", "REC/STN/KSRT/25-26/00001"
            )

            with patch(
                "manufacturing.serializer.KarigarStoneReceiveHeader.objects.create",
                return_value=KarigarStoneReceiveHeader(
                    pk=1,
                    billno="REC/STN/KSRT/25-26/00001",
                    date1=datetime.date(2025, 6, 1),
                    karigar_ldgr=self.karigar,
                    retail=self.retail,
                    fiscal_year=self.fy,
                ),
            ):
                request = _make_request(self.retail)
                payload = {
                    "billno": "CLIENT-BOGUS-RECSTN-99",
                    "date1": "2025-06-01",
                    "karigar_ldgr": self.karigar.pk,
                    "retail": self.retail.pk,
                    "karigarstonereceive_set": [],
                }
                ser = KarigarStoneReceiveSerializer(data=payload, context={"request": request})
                try:
                    ser.is_valid(raise_exception=True)
                    ser.save()
                except Exception:
                    pass

                self.assertTrue(
                    mock_swbn.called,
                    "save_with_bill_number was NOT called -- conversion not applied to KarigarStoneReceiveSerializer.",
                )


# ===========================================================================
# Task 14d -- KarigarIssue (IV) -- fallback: bare sequence + stub
# ===========================================================================

class KarigarIssueNumberingFallbackTest(TestCase):
    """
    Fallback path for KarigarIssueForPostSerializer (KarigarIssue).

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 645:
        ``karigar_issue_instance = KarigarIssue.objects.create(
            **validated_data,
            bill_id=int(validated_data['issue_slip_no'].split('/')[-1]))``
      validated_data still contains the client-supplied 'issue_slip_no'.
      generate_slip_no() in manufacturing/utils.py exists but is NOT called.

    Note: bill_id is derived from the trailing integer of issue_slip_no.
    After conversion, bill_id must be extracted from the server-generated number.

    Tests:
      (a) Bare save_with_bill_number sequence test for IV prefix.
      (b) Stub test asserting save_with_bill_number is called by the serializer.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("KIVT")
        self.karigar = _make_ledger("Issue Karigar T14d")

    # -- (a) Bare sequence test -----------------------------------------------

    def test_iv_sequence_increments(self):
        """save_with_bill_number advances the IV sequence correctly."""
        from manufacturing.models import KarigarIssue
        r1 = KarigarIssue(
            issue_slip_no="",
            bill_id=0,
            date1=datetime.date(2025, 6, 1),
            issue_slip_type="Stock",
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r1, self.retail, "IV", field="issue_slip_no", fy=self.fy)

        r2 = KarigarIssue(
            issue_slip_no="",
            bill_id=0,
            date1=datetime.date(2025, 6, 1),
            issue_slip_type="Stock",
            karigar_ldgr=self.karigar,
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r2, self.retail, "IV", field="issue_slip_no", fy=self.fy)

        self.assertTrue(r1.issue_slip_no.endswith("00001"), f"First issue_slip_no {r1.issue_slip_no!r} must end in 00001")
        self.assertTrue(r2.issue_slip_no.endswith("00002"), f"Second issue_slip_no {r2.issue_slip_no!r} must end in 00002")
        self.assertNotEqual(r1.issue_slip_no, r2.issue_slip_no)

    # -- (b) Stub-level regression: save_with_bill_number is called -----------

    def test_serializer_create_calls_save_with_bill_number(self):
        """After conversion: KarigarIssueForPostSerializer.create() must call save_with_bill_number."""
        from manufacturing.models import KarigarIssue
        from manufacturing.serializer import KarigarIssueForPostSerializer

        with patch("accounting.utils.save_with_bill_number") as mock_swbn:
            mock_swbn.side_effect = lambda inst, retail, prefix, **kw: (
                setattr(inst, "issue_slip_no", "IV/KIVT/25-26/00001") or
                setattr(inst, "bill_id", 1)
            )

            with patch(
                "manufacturing.serializer.KarigarIssue.objects.create",
                return_value=KarigarIssue(
                    pk=1,
                    issue_slip_no="IV/KIVT/25-26/00001",
                    bill_id=1,
                    date1=datetime.date(2025, 6, 1),
                    issue_slip_type="Stock",
                    karigar_ldgr=self.karigar,
                    retail=self.retail,
                    fiscal_year=self.fy,
                ),
            ):
                request = _make_request(self.retail)
                payload = {
                    "issue_slip_no": "CLIENT-BOGUS-IV-99",
                    "date1": "2025-06-01",
                    "issue_slip_type": "Stock",
                    "karigar_ldgr": self.karigar.pk,
                    "retail": self.retail.pk,
                    "items": [],
                }
                ser = KarigarIssueForPostSerializer(data=payload, context={"request": request})
                try:
                    ser.is_valid(raise_exception=True)
                    ser.save()
                except Exception:
                    pass

                self.assertTrue(
                    mock_swbn.called,
                    "save_with_bill_number was NOT called -- conversion not applied to KarigarIssueForPostSerializer.",
                )


# ===========================================================================
# Task 14e -- KarigarReceive (RS) -- fallback: bare sequence + stub
# ===========================================================================

class KarigarReceiveNumberingFallbackTest(TestCase):
    """
    Fallback path for KarigarReceiveForPostSerializer (KarigarReceive).

    Pre-conversion failure confirmed by manual code inspection:
      manufacturing/serializer.py line 1073:
        ``karigar_receive_instance = KarigarReceive.objects.create(**validated_data)``
      validated_data still contains the client-supplied 'receive_slip_no'.
      A manual duplicate-slip-no check exists at lines 1065-1072 that becomes
      redundant once the number is server-generated.
      generate_kr_rec_slip_no() in manufacturing/utils.py exists but NOT called.

    Tests:
      (a) Bare save_with_bill_number sequence test for RS prefix.
      (b) Stub test asserting save_with_bill_number is called by the serializer.
    """

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("KRST")
        self.karigar = _make_ledger("Receive Karigar T14e")

    # -- (a) Bare sequence test -----------------------------------------------

    def test_rs_sequence_increments(self):
        """save_with_bill_number advances the RS sequence correctly."""
        from manufacturing.models import KarigarReceive
        r1 = KarigarReceive(
            receive_slip_no="",
            date1=datetime.date(2025, 6, 1),
            karigar_ldgr=self.karigar,
            place_of_supply="Maharashtra",
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r1, self.retail, "RS", field="receive_slip_no", fy=self.fy)

        r2 = KarigarReceive(
            receive_slip_no="",
            date1=datetime.date(2025, 6, 1),
            karigar_ldgr=self.karigar,
            place_of_supply="Maharashtra",
            retail=self.retail,
            fiscal_year=self.fy,
        )
        save_with_bill_number(r2, self.retail, "RS", field="receive_slip_no", fy=self.fy)

        self.assertTrue(r1.receive_slip_no.endswith("00001"), f"First {r1.receive_slip_no!r} must end in 00001")
        self.assertTrue(r2.receive_slip_no.endswith("00002"), f"Second {r2.receive_slip_no!r} must end in 00002")
        self.assertNotEqual(r1.receive_slip_no, r2.receive_slip_no)

    # -- (b) Stub-level regression: save_with_bill_number is called -----------

    def test_serializer_create_calls_save_with_bill_number(self):
        """After conversion: KarigarReceiveForPostSerializer.create() must call save_with_bill_number."""
        from manufacturing.models import KarigarReceive
        from manufacturing.serializer import KarigarReceiveForPostSerializer

        with patch("accounting.utils.save_with_bill_number") as mock_swbn:
            mock_swbn.side_effect = lambda inst, retail, prefix, **kw: setattr(
                inst, "receive_slip_no", "RS/KRST/25-26/00001"
            )

            karigar_receive_mock = KarigarReceive(
                pk=1,
                receive_slip_no="RS/KRST/25-26/00001",
                date1=datetime.date(2025, 6, 1),
                karigar_ldgr=self.karigar,
                place_of_supply="Maharashtra",
                retail=self.retail,
                fiscal_year=self.fy,
            )
            karigar_receive_mock.save = lambda **kw: None  # prevent actual DB save

            with patch(
                "manufacturing.serializer.KarigarReceive.objects.create",
                return_value=karigar_receive_mock,
            ):
                request = _make_request(self.retail)
                # KarigarReceiveForPostSerializer requires items; pass empty list
                payload = {
                    "receive_slip_no": "CLIENT-BOGUS-RS-99",
                    "date1": "2025-06-01",
                    "karigar_ldgr": self.karigar.pk,
                    "place_of_supply": "Maharashtra",
                    "retail": self.retail.pk,
                    "items": [],
                }
                ser = KarigarReceiveForPostSerializer(data=payload, context={"request": request})
                try:
                    ser.is_valid(raise_exception=True)
                    ser.save()
                except Exception:
                    pass

                self.assertTrue(
                    mock_swbn.called,
                    "save_with_bill_number was NOT called -- conversion not applied to KarigarReceiveForPostSerializer.",
                )
