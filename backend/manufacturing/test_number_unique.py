"""
Tests that scoped UniqueConstraints on manufacturing voucher-number models
actually enforce uniqueness at the DB level.

Each test creates two rows with the same scoped number and asserts
django.db.IntegrityError is raised on the second insert.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase


def _make_retail():
    from mastersconfig.models import RetailMaster
    obj, _ = RetailMaster.objects.get_or_create(
        retail_code="MFGTEST",
        defaults={"retail_name": "Mfg Test Retail", "address_line1": "Test"},
    )
    return obj


def _make_fy(retail):
    from mastersconfig.models import FiscalYearMaster
    obj, _ = FiscalYearMaster.objects.get_or_create(
        fy_code="24-25",
        defaults={"fy_start": "2024-04-01", "fy_end": "2025-03-31"},
    )
    return obj


def _make_ledger():
    from contacts.models import Ledger
    obj, _ = Ledger.objects.get_or_create(
        ac_name="Mfg Test Ledger",
        defaults={"display_name": "Mfg Test Ledger"},
    )
    return obj


class RefinaryIssueUniqueTest(TestCase):
    """uniq_refissue_number: (retail, fiscal_year, billno)."""

    def test_duplicate_billno_raises_integrity_error(self):
        from manufacturing.models import RefinaryIssue
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        RefinaryIssue.objects.create(
            date1="2024-05-01", billno="RI-DUP", ldgr=ldgr, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RefinaryIssue.objects.create(
                    date1="2024-06-01", billno="RI-DUP", ldgr=ldgr, retail=retail, fiscal_year=fy
                )

    def test_different_billno_is_allowed(self):
        from manufacturing.models import RefinaryIssue
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        RefinaryIssue.objects.create(
            date1="2024-05-01", billno="RI-A", ldgr=ldgr, retail=retail, fiscal_year=fy
        )
        # Should not raise
        RefinaryIssue.objects.create(
            date1="2024-06-01", billno="RI-B", ldgr=ldgr, retail=retail, fiscal_year=fy
        )
        self.assertEqual(RefinaryIssue.objects.filter(retail=retail).count(), 2)


class RefinaryReceiveUniqueTest(TestCase):
    """uniq_refreceive_number: (retail, fiscal_year, billno)."""

    def test_duplicate_billno_raises_integrity_error(self):
        from manufacturing.models import RefinaryReceive
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        RefinaryReceive.objects.create(
            date1="2024-05-01", billno="RR-DUP", ldgr=ldgr, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RefinaryReceive.objects.create(
                    date1="2024-06-01", billno="RR-DUP", ldgr=ldgr, retail=retail, fiscal_year=fy
                )


class MeltingIssueUniqueTest(TestCase):
    """uniq_meltissue_number: (retail, fiscal_year, billno)."""

    def test_duplicate_billno_raises_integrity_error(self):
        from manufacturing.models import MeltingIssue
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        MeltingIssue.objects.create(
            date1="2024-05-01", billno="MI-DUP", ldgr=ldgr, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MeltingIssue.objects.create(
                    date1="2024-06-01", billno="MI-DUP", ldgr=ldgr, retail=retail, fiscal_year=fy
                )


class MeltingReceiveUniqueTest(TestCase):
    """uniq_meltreceive_number: (retail, fiscal_year, billno)."""

    def test_duplicate_billno_raises_integrity_error(self):
        from manufacturing.models import MeltingReceive
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        MeltingReceive.objects.create(
            date1="2024-05-01", billno="MR-DUP", ldgr=ldgr, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                MeltingReceive.objects.create(
                    date1="2024-06-01", billno="MR-DUP", ldgr=ldgr, retail=retail, fiscal_year=fy
                )


class HallmarkIssueUniqueTest(TestCase):
    """uniq_hmkissue_number: (retail, fiscal_year, issue_slip_no)."""

    def test_duplicate_issue_slip_no_raises_integrity_error(self):
        from manufacturing.models import HallmarkIssue
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        HallmarkIssue.objects.create(
            date1="2024-05-01", issue_slip_no="HI-DUP",
            hallmark_center=ldgr, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HallmarkIssue.objects.create(
                    date1="2024-06-01", issue_slip_no="HI-DUP",
                    hallmark_center=ldgr, retail=retail, fiscal_year=fy
                )


class HallmarkReceiveUniqueTest(TestCase):
    """uniq_hmkreceive_number: (retail, fiscal_year, receive_slip_no)."""

    def test_duplicate_receive_slip_no_raises_integrity_error(self):
        from manufacturing.models import HallmarkReceive
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        HallmarkReceive.objects.create(
            receive_slip_no="HR-DUP",
            hallmark_center=ldgr, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                HallmarkReceive.objects.create(
                    receive_slip_no="HR-DUP",
                    hallmark_center=ldgr, retail=retail, fiscal_year=fy
                )


class RepairJobCardUniqueTest(TestCase):
    """uniq_rjc_number: (retail, fiscal_year, rjc_no)."""

    def test_duplicate_rjc_no_raises_integrity_error(self):
        from manufacturing.models import RepairJobCard
        retail = _make_retail()
        fy = _make_fy(retail)
        customer = _make_ledger()
        RepairJobCard.objects.create(
            rjc_no="RJC-DUP", date1="2024-05-01",
            customer=customer, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RepairJobCard.objects.create(
                    rjc_no="RJC-DUP", date1="2024-06-01",
                    customer=customer, retail=retail, fiscal_year=fy
                )


class SampleIssueUniqueTest(TestCase):
    """uniq_sampleissue_number: (retail, fiscal_year, billno)."""

    def test_duplicate_billno_raises_integrity_error(self):
        from manufacturing.models import SampleIssue
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        SampleIssue.objects.create(
            billno="SI-DUP", date1="2024-05-01",
            karigar_ldgr=ldgr, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SampleIssue.objects.create(
                    billno="SI-DUP", date1="2024-06-01",
                    karigar_ldgr=ldgr, retail=retail, fiscal_year=fy
                )


class KarigarIssueUniqueTest(TestCase):
    """uniq_krissue_number: (retail, fiscal_year, issue_slip_no)."""

    def test_duplicate_issue_slip_no_raises_integrity_error(self):
        from manufacturing.models import KarigarIssue
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        KarigarIssue.objects.create(
            bill_id=1, date1="2024-05-01",
            issue_slip_type="NJ", issue_slip_no="KI-DUP",
            karigar_ldgr=ldgr, retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                KarigarIssue.objects.create(
                    bill_id=2, date1="2024-06-01",
                    issue_slip_type="NJ", issue_slip_no="KI-DUP",
                    karigar_ldgr=ldgr, retail=retail, fiscal_year=fy
                )


class KarigarReceiveUniqueTest(TestCase):
    """uniq_krreceive_number: (retail, fiscal_year, receive_slip_no)."""

    def test_duplicate_receive_slip_no_raises_integrity_error(self):
        from manufacturing.models import KarigarReceive
        from accounting.models import VoucherMain
        retail = _make_retail()
        fy = _make_fy(retail)
        ldgr = _make_ledger()
        KarigarReceive.objects.create(
            receive_slip_no="KR-DUP", date1="2024-05-01",
            place_of_supply="Maharashtra",
            karigar_ldgr=ldgr, making_vid=None,
            retail=retail, fiscal_year=fy
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                KarigarReceive.objects.create(
                    receive_slip_no="KR-DUP", date1="2024-06-01",
                    place_of_supply="Maharashtra",
                    karigar_ldgr=ldgr, making_vid=None,
                    retail=retail, fiscal_year=fy
                )
