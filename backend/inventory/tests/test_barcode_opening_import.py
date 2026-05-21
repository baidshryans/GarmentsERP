"""Tests for barcode opening data import: CSV parsers, FK matchers,
validate endpoint, and import endpoint (skip / update / error conflict actions)."""

from decimal import Decimal
from io import BytesIO
import csv

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from goldrates.models import PurityMaster
from mastersconfig.models import RetailMaster, Item, Packet
from inventory.models import BarcodeMain, BarcodeDetails
from inventory.csv_parsers import (
    parse_csv_file,
    match_purity,
    match_retail_code,
    match_item_id,
    match_packet,
    parse_decimal_field,
    parse_integer_field,
    BarcodeOpeningCSVError,
    MAX_ROWS,
)

User = get_user_model()


# ─── Fixture helpers ──────────────────────────────────────────────────────────


def make_purity(value="14", gw_per="0.585"):
    return PurityMaster.objects.create(purity=value, gw_per=Decimal(gw_per))


def make_retail(code="R001", name="Store 1"):
    # bill_series and retail_code are unique — derive bill_series from code
    return RetailMaster.objects.create(
        retail_name=name,
        retail_code=code,
        address_line1="123 St",
        phone="9999",
        bill_series=f"S-{code}",
    )


def make_item(short_code="RNG", name="Ring", item_type="M", uom="Gm"):
    return Item.objects.create(
        short_code=short_code,
        item_name=name,
        item_type=item_type,
        uom=uom,
        show_in_pcs_report=False,
    )


def make_packet(pckt_no="P001"):
    return Packet.objects.create(
        pckt_no=pckt_no,
        is_solitaire=False,
        rate_for_retail=100,
        is_customer_stone=False,
    )


def make_csv_file(rows, columns, name="test.csv"):
    """Build a SimpleUploadedFile representing a CSV with the given header and rows."""
    output = BytesIO()
    text = ",".join(columns) + "\n"
    for row in rows:
        text += ",".join(str(row.get(c, "")) for c in columns) + "\n"
    output.write(text.encode("utf-8"))
    output.seek(0)
    return SimpleUploadedFile(name, output.read(), content_type="text/csv")


# ─── parse_csv_file ───────────────────────────────────────────────────────────


class ParseCSVFileTests(TestCase):
    def test_returns_rows_with_row_numbers(self):
        f = make_csv_file(
            [{"a": "1", "b": "2"}, {"a": "3", "b": "4"}],
            columns=["a", "b"],
        )
        rows = parse_csv_file(f, ["a", "b"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][0], 2)  # row_num starts at 2 (after header)
        self.assertEqual(rows[0][1]["a"], "1")
        self.assertEqual(rows[1][0], 3)

    def test_raises_on_missing_columns(self):
        f = make_csv_file([{"a": "1"}], columns=["a"])
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            parse_csv_file(f, ["a", "b"])
        self.assertIn("Missing columns", str(ctx.exception))
        self.assertIn("b", str(ctx.exception))

    def test_raises_on_empty_file(self):
        f = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_csv_file(f, ["a"])

    def test_raises_on_only_header(self):
        f = SimpleUploadedFile("h.csv", b"a,b\n", content_type="text/csv")
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            parse_csv_file(f, ["a", "b"])
        self.assertIn("No data rows", str(ctx.exception))

    def test_strips_bom_and_whitespace_from_headers(self):
        """Excel often exports CSV with BOM + spaces in headers."""
        bom_content = b"\xef\xbb\xbf a , b \n1,2\n"
        f = SimpleUploadedFile("bom.csv", bom_content, content_type="text/csv")
        rows = parse_csv_file(f, ["a", "b"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["a"], "1")

    def test_skips_completely_empty_rows(self):
        content = b"a,b\n1,2\n,\n3,4\n"
        f = SimpleUploadedFile("e.csv", content, content_type="text/csv")
        rows = parse_csv_file(f, ["a", "b"])
        self.assertEqual(len(rows), 2)  # empty middle row skipped

    def test_raises_when_row_count_exceeds_max(self):
        cols = ["a"]
        rows_data = [{"a": str(i)} for i in range(MAX_ROWS + 1)]
        f = make_csv_file(rows_data, columns=cols)
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            parse_csv_file(f, cols)
        self.assertIn("exceeds the maximum", str(ctx.exception))


# ─── match_purity ─────────────────────────────────────────────────────────────


class MatchPurityTests(TestCase):
    def setUp(self):
        self.p14 = make_purity("14")
        self.p18 = make_purity("18")
        self.p22k = make_purity("22K")

    def test_exact_numeric_match(self):
        self.assertEqual(match_purity("14").id, self.p14.id)

    def test_exact_karat_match(self):
        self.assertEqual(match_purity("22K").id, self.p22k.id)

    def test_strip_k_falls_back_to_numeric(self):
        """'18K' should match the numeric '18' purity row when no '18K' exists."""
        self.assertEqual(match_purity("18K").id, self.p18.id)

    def test_append_k_falls_back_to_karat(self):
        """'22' should match the '22K' purity row when no '22' exists."""
        self.assertEqual(match_purity("22").id, self.p22k.id)

    def test_case_insensitive(self):
        self.assertEqual(match_purity("22k").id, self.p22k.id)
        self.assertEqual(match_purity("18k").id, self.p18.id)

    def test_invalid_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            match_purity("99")
        self.assertIn("does not match", str(ctx.exception))

    def test_empty_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            match_purity("")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_ambiguous_raises(self):
        # Create a second "14" purity row → ambiguity
        PurityMaster.objects.create(purity="14", gw_per=Decimal("0.585"))
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            match_purity("14")
        self.assertIn("ambiguous", str(ctx.exception))


# ─── match_retail_code ────────────────────────────────────────────────────────


class MatchRetailCodeTests(TestCase):
    def setUp(self):
        self.r1 = make_retail("R001")

    def test_valid(self):
        self.assertEqual(match_retail_code("R001").id, self.r1.id)

    def test_invalid_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            match_retail_code("R999")
        self.assertIn("does not exist", str(ctx.exception))

    def test_empty_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError):
            match_retail_code("")


# ─── match_item_id ────────────────────────────────────────────────────────────


class MatchItemIdTests(TestCase):
    def setUp(self):
        self.ring = make_item(short_code="RNG", name="Ring")

    def test_valid(self):
        self.assertEqual(match_item_id(str(self.ring.id)).id, self.ring.id)

    def test_invalid_id_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            match_item_id("99999")
        self.assertIn("does not exist", str(ctx.exception))

    def test_empty_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            match_item_id("")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_non_integer_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            match_item_id("Ring")
        self.assertIn("not a valid integer", str(ctx.exception))


# ─── match_packet ─────────────────────────────────────────────────────────────


class MatchPacketTests(TestCase):
    def setUp(self):
        self.p = make_packet("P001")

    def test_by_id(self):
        self.assertEqual(match_packet(str(self.p.id)).id, self.p.id)

    def test_by_pckt_no(self):
        self.assertEqual(match_packet("P001").id, self.p.id)

    def test_empty_returns_none(self):
        self.assertIsNone(match_packet(""))
        self.assertIsNone(match_packet(None))

    def test_invalid_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError):
            match_packet("does-not-exist-xyz")


# ─── parse_decimal_field ──────────────────────────────────────────────────────


class ParseDecimalFieldTests(TestCase):
    def test_valid(self):
        self.assertEqual(parse_decimal_field("123.45", "f", 2), Decimal("123.45"))

    def test_too_many_places_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError) as ctx:
            parse_decimal_field("123.456", "f", 2)
        self.assertIn("decimal places", str(ctx.exception))

    def test_invalid_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_decimal_field("not-a-number", "f")

    def test_empty_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_decimal_field("", "f")
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_decimal_field(None, "f")

    def test_nan_rejected(self):
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_decimal_field("NaN", "f")

    def test_infinity_rejected(self):
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_decimal_field("Infinity", "f")
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_decimal_field("-Infinity", "f")


# ─── parse_integer_field ──────────────────────────────────────────────────────


class ParseIntegerFieldTests(TestCase):
    def test_valid(self):
        self.assertEqual(parse_integer_field("42", "f"), 42)

    def test_invalid_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_integer_field("4.5", "f")
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_integer_field("abc", "f")

    def test_empty_raises(self):
        with self.assertRaises(BarcodeOpeningCSVError):
            parse_integer_field("", "f")


# ─── Integration tests: validate + import endpoints ───────────────────────────

VALIDATE_URL = "/inventory/api/barcode-opening/validate/"
IMPORT_URL = "/inventory/api/barcode-opening/import/"

MAIN_COLS = [
    "barcode", "item_id", "purity", "quantity_pieces", "gross_weight",
    "net_weight", "value", "making_value", "retail_code", "huid",
    "design_code", "metal_color", "size", "making_type", "other_charges",
]
DETAILS_COLS = [
    "barcode", "item_id", "purity", "quantity_pieces", "carat_weight",
    "gross_weight", "rate", "amount", "packet_number",
]


def main_row(barcode="B001", item_id="", **overrides):
    base = {
        "barcode": barcode,
        "item_id": item_id,
        "purity": "14",
        "quantity_pieces": "1",
        "gross_weight": "5.500",
        "net_weight": "5.000",
        "value": "15000.00",
        "making_value": "2000.00",
        "retail_code": "R001",
        "huid": "",
        "design_code": "",
        "metal_color": "",
        "size": "",
        "making_type": "",
        "other_charges": "",
    }
    base.update(overrides)
    return base


def details_row(barcode="B001", item_id="", **overrides):
    base = {
        "barcode": barcode,
        "item_id": item_id,
        "purity": "14",
        "quantity_pieces": "1",
        "carat_weight": "5.000",
        "gross_weight": "5.500",
        "rate": "2500",
        "amount": "12500",
        "packet_number": "",
    }
    base.update(overrides)
    return base


class BarcodeOpeningValidateEndpointTests(TestCase):
    """POST /inventory/api/barcode-opening/validate/ — dry-run validation."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="tester", password="pass")
        cls.purity = make_purity("14")
        cls.retail = make_retail("R001")
        cls.item = make_item(name="Ring")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _post_validate(self, main_rows, details_rows):
        return self.client.post(
            VALIDATE_URL,
            {
                "barcode_main_csv": make_csv_file(main_rows, MAIN_COLS, name="main.csv"),
                "barcode_details_csv": make_csv_file(details_rows, DETAILS_COLS, name="details.csv"),
            },
            format="multipart",
        )

    def test_success_returns_preview(self):
        iid = str(self.item.id)
        resp = self._post_validate([main_row(item_id=iid)], [details_row(item_id=iid)])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["main_rows_valid"], 1)
        self.assertEqual(resp.data["details_rows_valid"], 1)
        self.assertEqual(resp.data["existing_barcodes_count"], 0)

    def test_missing_file_returns_400(self):
        resp = self.client.post(VALIDATE_URL, {}, format="multipart")
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data["success"])

    def test_invalid_purity_returns_400_with_error_list(self):
        iid = str(self.item.id)
        resp = self._post_validate(
            [main_row(item_id=iid, purity="999")],
            [details_row(item_id=iid)],
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data["success"])
        self.assertTrue(any("Purity" in e or "purity" in e for e in resp.data["errors"]))

    def test_duplicate_barcode_in_upload_flagged(self):
        iid = str(self.item.id)
        resp = self._post_validate(
            [main_row("B001", item_id=iid), main_row("B001", item_id=iid)],
            [details_row("B001", item_id=iid)],
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(any("multiple times" in e for e in resp.data["errors"]))

    def test_details_barcode_not_in_main_or_db(self):
        iid = str(self.item.id)
        resp = self._post_validate(
            [main_row("B001", item_id=iid)],
            [details_row("B999", item_id=iid)],
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(any("not found" in e for e in resp.data["errors"]))

    def test_existing_barcode_reported_in_preview(self):
        # Pre-create a barcode in DB
        BarcodeMain.objects.create(barcode="B001", purity=self.purity, retail=self.retail, item=self.item)
        iid = str(self.item.id)
        resp = self._post_validate([main_row("B001", item_id=iid)], [details_row("B001", item_id=iid)])
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["existing_barcodes_count"], 1)
        self.assertIn("B001", resp.data["existing_barcodes"])

    def test_unauthenticated_returns_401_or_403(self):
        self.client.force_authenticate(user=None)
        iid = str(self.item.id)
        resp = self._post_validate([main_row(item_id=iid)], [details_row(item_id=iid)])
        self.assertIn(resp.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))


class BarcodeOpeningImportEndpointTests(TransactionTestCase):
    """POST /inventory/api/barcode-opening/import/ — atomic transaction tests.

    Uses TransactionTestCase because we need to observe transaction.atomic() rollback
    behavior, which TestCase wraps and hides inside its own outer transaction.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")
        self.purity = make_purity("14")
        self.retail = make_retail("R001")
        self.item = make_item(name="Ring")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _post_import(self, main_rows, details_rows, conflict_action="error"):
        return self.client.post(
            IMPORT_URL,
            {
                "barcode_main_csv": make_csv_file(main_rows, MAIN_COLS, name="main.csv"),
                "barcode_details_csv": make_csv_file(details_rows, DETAILS_COLS, name="details.csv"),
                "conflict_action": conflict_action,
            },
            format="multipart",
        )

    def test_creates_new_barcode_with_op_stk_and_op_retail(self):
        iid = str(self.item.id)
        resp = self._post_import([main_row("B001", item_id=iid)], [details_row("B001", item_id=iid)])
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertTrue(resp.data["success"])
        self.assertEqual(resp.data["data"]["created"], 1)
        self.assertEqual(resp.data["data"]["details_created"], 1)
        bm = BarcodeMain.objects.get(barcode="B001")
        self.assertTrue(bm.op_stk)
        self.assertEqual(bm.op_retail_id, self.retail.id)
        self.assertEqual(BarcodeDetails.objects.filter(barcode=bm).count(), 1)

    def test_conflict_action_error_blocks_existing(self):
        BarcodeMain.objects.create(barcode="B001", purity=self.purity, retail=self.retail, item=self.item)
        iid = str(self.item.id)
        resp = self._post_import(
            [main_row("B001", item_id=iid)],
            [details_row("B001", item_id=iid)],
            conflict_action="error",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(resp.data["success"])
        self.assertEqual(resp.data["existing_barcodes_count"], 1)

    def test_conflict_action_skip_skips_existing_and_their_details(self):
        BarcodeMain.objects.create(barcode="B001", purity=self.purity, retail=self.retail, item=self.item)
        iid = str(self.item.id)
        resp = self._post_import(
            [main_row("B001", item_id=iid), main_row("B002", item_id=iid)],
            [details_row("B001", item_id=iid), details_row("B002", item_id=iid)],
            conflict_action="skip",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["data"]["created"], 1)
        self.assertEqual(resp.data["data"]["skipped"], 1)
        self.assertEqual(resp.data["data"]["details_created"], 1)  # only B002's

    def test_conflict_action_update_replaces_details(self):
        # Pre-create a barcode WITH existing details
        existing = BarcodeMain.objects.create(barcode="B001", purity=self.purity, retail=self.retail, item=self.item)
        BarcodeDetails.objects.create(
            barcode=existing, item=self.item, rate=100, amt=500, ct=Decimal("1.000"), gw=Decimal("1.000")
        )
        BarcodeDetails.objects.create(
            barcode=existing, item=self.item, rate=200, amt=600, ct=Decimal("2.000"), gw=Decimal("2.000")
        )
        iid = str(self.item.id)
        resp = self._post_import(
            [main_row("B001", item_id=iid, value="20000.00")],
            [details_row("B001", item_id=iid)],
            conflict_action="update",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data["data"]["updated"], 1)
        self.assertEqual(resp.data["data"]["details_replaced"], 2)  # 2 old rows deleted
        self.assertEqual(resp.data["data"]["details_created"], 1)
        existing.refresh_from_db()
        self.assertEqual(existing.value, Decimal("20000.00"))
        self.assertTrue(existing.op_stk)
        # Only the new details row remains
        self.assertEqual(BarcodeDetails.objects.filter(barcode=existing).count(), 1)

    def test_validation_failure_rolls_back_transaction(self):
        # First main row is valid, second is invalid (bad purity)
        iid = str(self.item.id)
        resp = self._post_import(
            [main_row("B001", item_id=iid), main_row("B002", item_id=iid, purity="999")],
            [details_row("B001", item_id=iid), details_row("B002", item_id=iid)],
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        # Neither barcode should be created (atomic rollback)
        self.assertFalse(BarcodeMain.objects.filter(barcode="B001").exists())
        self.assertFalse(BarcodeMain.objects.filter(barcode="B002").exists())

    def test_invalid_conflict_action_returns_400(self):
        iid = str(self.item.id)
        resp = self._post_import(
            [main_row("B001", item_id=iid)],
            [details_row("B001", item_id=iid)],
            conflict_action="garbage",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
