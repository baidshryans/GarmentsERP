"""
Tests: deleting a melting/refinery ISSUE cascades to its RECEIVE slips.

Rules under test:
  - A receive slip sourced ONLY from the deleted issue is removed entirely
    (header + all detail rows), stock reverses to net zero, bill number freed.
  - A receive slip sourced from the deleted issue AND another issue keeps its
    header and the other issue's rows; only the deleted issue's rows go.
"""

import datetime
from decimal import Decimal

from django.test import TestCase

from accounting.utils import peek_next_bill_number, save_with_bill_number
from contacts.models import Ledger
from goldrates.models import PurityMaster
from inventory.models import RawMaterialInventory
from mastersconfig.models import FiscalYearMaster, Item, RetailMaster
from manufacturing.models import (
    MeltingIssue, MeltingIssueDetail, MeltingReceive, MeltingReceiveDetail,
    RefinaryIssue, RefinaryIssueDetail, RefinaryReceive, RefinaryReceiveDetail,
)


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

def _make_retail_and_fy(code: str):
    retail = RetailMaster.objects.create(
        retail_name=f"Test {code}",
        retail_code=code,
        phone="0000000000",
        address_line1="Test",
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
        ac_name=name, display_name=name,
        b2b=False, tds_applicable=False, is_system=False,
    )


def _make_item(code: str):
    return Item.objects.create(
        short_code=code, item_name=f"Item {code}",
        item_type="R", uom="GM", show_in_pcs_report=False,
    )


def _make_purity(value: str):
    return PurityMaster.objects.create(purity=value, gw_per=Decimal("0.916"))


def _total_raw_gw(retail):
    return sum(
        (r.gw for r in RawMaterialInventory.objects.filter(retail=retail)),
        Decimal("0"),
    )


# --------------------------------------------------------------------------- #
# Melting                                                                      #
# --------------------------------------------------------------------------- #

class MeltingIssueDeleteCascadeTest(TestCase):

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("MDC")
        self.ldgr = _make_ledger("Melt Vendor MDC")
        self.item = _make_item("MDCRAW")
        self.purity = _make_purity("92.0")

    def _make_issue(self):
        issue = MeltingIssue(
            date1=datetime.date(2025, 4, 1), ldgr=self.ldgr,
            retail=self.retail, fiscal_year=self.fy, rec_status=False,
        )
        save_with_bill_number(issue, self.retail, "MLT/ISS", field="billno", fy=self.fy)
        MeltingIssueDetail.objects.create(
            billno=issue, item=self.item, gw=Decimal("10.000"),
            metal_purity=self.purity, retail=self.retail,
        )
        return issue

    def _make_receive(self, issue_rows):
        """issue_rows: list of MeltingIssue that each contribute one detail row."""
        receive = MeltingReceive(
            date1=datetime.date(2025, 4, 2), ldgr=self.ldgr,
            retail=self.retail, fiscal_year=self.fy,
        )
        save_with_bill_number(receive, self.retail, "MLT/REC", field="billno", fy=self.fy)
        for issue in issue_rows:
            MeltingReceiveDetail.objects.create(
                billno=receive, issue_no=issue, item=self.item,
                gw=Decimal("10.000"), loss_per=Decimal("0.000"),
                loss_wt=Decimal("0.000"), metal_purity=self.purity,
                conv_purity=self.purity, conv_nw=Decimal("9.500"),
                rec_status=False, retail=self.retail,
            )
        return receive

    def test_only_source_receive_is_deleted_entirely(self):
        issue = self._make_issue()
        receive = self._make_receive([issue])
        receive_id = receive.id

        issue.delete()

        self.assertFalse(MeltingReceive.objects.filter(id=receive_id).exists(),
                         "Receive header sourced only from the deleted issue must be gone")
        self.assertFalse(MeltingReceiveDetail.objects.filter(billno_id=receive_id).exists(),
                         "Receive detail rows must be gone")
        self.assertEqual(_total_raw_gw(self.retail), Decimal("0"),
                         "Raw-metal stock must net to zero after full teardown")

    def test_only_source_receive_bill_number_is_reclaimed(self):
        issue = self._make_issue()
        self._make_receive([issue])   # REC …00001

        issue.delete()

        nxt = peek_next_bill_number(self.retail, "MLT/REC", self.fy)
        self.assertTrue(nxt.endswith("00001"),
                        f"Deleted-only-source receive number should be freed, got {nxt!r}")

    def test_multi_source_receive_survives_with_other_rows(self):
        issue_a = self._make_issue()
        issue_b = self._make_issue()
        receive = self._make_receive([issue_a, issue_b])
        receive_id = receive.id

        issue_a.delete()

        self.assertTrue(MeltingReceive.objects.filter(id=receive_id).exists(),
                        "Multi-source receive header must survive")
        remaining = MeltingReceiveDetail.objects.filter(billno_id=receive_id)
        self.assertEqual(remaining.count(), 1, "Only issue_a's row should be removed")
        self.assertEqual(remaining.first().issue_no_id, issue_b.id,
                         "The surviving row must be issue_b's")


# --------------------------------------------------------------------------- #
# Refinery                                                                     #
# --------------------------------------------------------------------------- #

class RefinaryIssueDeleteCascadeTest(TestCase):

    def setUp(self):
        self.retail, self.fy = _make_retail_and_fy("RDC")
        self.ldgr = _make_ledger("Ref Vendor RDC")
        self.item = _make_item("RDCRAW")
        self.purity = _make_purity("91.6")

    def _make_issue(self):
        issue = RefinaryIssue(
            date1=datetime.date(2025, 4, 1), ldgr=self.ldgr,
            retail=self.retail, fiscal_year=self.fy, rec_status=False,
        )
        save_with_bill_number(issue, self.retail, "REF/ISS", field="billno", fy=self.fy)
        RefinaryIssueDetail.objects.create(
            billno=issue, item=self.item, gw=Decimal("10.000"),
            metal_purity=self.purity, retail=self.retail,
        )
        return issue

    def _make_receive(self, issue_rows):
        receive = RefinaryReceive(
            date1=datetime.date(2025, 4, 2), ldgr=self.ldgr,
            retail=self.retail, fiscal_year=self.fy,
        )
        save_with_bill_number(receive, self.retail, "REF/REC", field="billno", fy=self.fy)
        for issue in issue_rows:
            RefinaryReceiveDetail.objects.create(
                billno=receive, issue_no=issue, item=self.item,
                gw=Decimal("10.000"), loss_per=Decimal("0.000"),
                loss_wt=Decimal("0.000"), metal_purity=self.purity,
                conv_purity=self.purity, conv_nw=Decimal("9.500"),
                rec_status=False, retail=self.retail,
            )
        return receive

    def test_only_source_receive_is_deleted_entirely(self):
        issue = self._make_issue()
        receive = self._make_receive([issue])
        receive_id = receive.id

        issue.delete()

        self.assertFalse(RefinaryReceive.objects.filter(id=receive_id).exists())
        self.assertFalse(RefinaryReceiveDetail.objects.filter(billno_id=receive_id).exists())
        self.assertEqual(_total_raw_gw(self.retail), Decimal("0"))

    def test_only_source_receive_bill_number_is_reclaimed(self):
        issue = self._make_issue()
        self._make_receive([issue])

        issue.delete()

        nxt = peek_next_bill_number(self.retail, "REF/REC", self.fy)
        self.assertTrue(nxt.endswith("00001"), f"got {nxt!r}")

    def test_multi_source_receive_survives_with_other_rows(self):
        issue_a = self._make_issue()
        issue_b = self._make_issue()
        receive = self._make_receive([issue_a, issue_b])
        receive_id = receive.id

        issue_a.delete()

        self.assertTrue(RefinaryReceive.objects.filter(id=receive_id).exists())
        remaining = RefinaryReceiveDetail.objects.filter(billno_id=receive_id)
        self.assertEqual(remaining.count(), 1)
        self.assertEqual(remaining.first().issue_no_id, issue_b.id)
