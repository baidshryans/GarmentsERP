import csv
from decimal import Decimal, InvalidOperation
from io import StringIO

from goldrates.models import PurityMaster
from mastersconfig.models import RetailMaster, Item, Packet


MAX_ROWS = 10_000  # safety cap to prevent unbounded memory use / long transactions


class BarcodeOpeningCSVError(Exception):
    """Custom exception for barcode CSV import errors."""
    pass


def parse_csv_file(file_obj, expected_columns):
    """Parse a CSV file and return list of (row_num, row_dict) tuples.

    Args:
        file_obj: File object (uploaded file)
        expected_columns: List of expected column names

    Returns:
        List of (row_num, row_dict) tuples (one per non-empty data row,
        row_num starts at 2 since row 1 is the header).

    Raises:
        BarcodeOpeningCSVError: If parsing fails or required columns missing.
    """
    try:
        content = file_obj.read()
        if isinstance(content, bytes):
            content = content.decode('utf-8')

        reader = csv.DictReader(StringIO(content))
        if reader.fieldnames is None:
            raise BarcodeOpeningCSVError("Empty CSV file")

        reader.fieldnames = [f.lstrip('﻿').strip() for f in reader.fieldnames]

        missing = set(expected_columns) - set(reader.fieldnames or [])
        if missing:
            raise BarcodeOpeningCSVError(f"Missing columns: {', '.join(sorted(missing))}")

        rows = []
        for row_num, row in enumerate(reader, start=2):
            if all(v is None or str(v).strip() == '' for v in row.values()):
                continue
            rows.append((row_num, row))

        if len(rows) > MAX_ROWS:
            raise BarcodeOpeningCSVError(
                f"CSV has {len(rows)} data rows, which exceeds the maximum of {MAX_ROWS}. "
                f"Please split the file into smaller chunks."
            )

        if not rows:
            raise BarcodeOpeningCSVError("No data rows found (only header)")

        return rows
    except csv.Error as e:
        raise BarcodeOpeningCSVError(f"CSV parsing error: {str(e)}")
    except UnicodeDecodeError as e:
        raise BarcodeOpeningCSVError(f"File encoding error: {str(e)}")


def match_purity(purity_text):
    """Match purity text to PurityMaster.

    Supports both numeric values ("14", "18", "22") and karat-suffix
    formats ("14K", "18K", "22K"), case-insensitive.

    Tries: (1) exact iexact, (2) strip trailing 'K', (3) append 'K' if digits.

    Returns:
        PurityMaster instance.

    Raises:
        BarcodeOpeningCSVError: If empty, no match, or ambiguous.
    """
    if purity_text is None or str(purity_text).strip() == '':
        raise BarcodeOpeningCSVError("Purity is empty")

    purity_text = str(purity_text).strip().upper()

    def _lookup(needle):
        matches = list(PurityMaster.objects.filter(purity__iexact=needle)[:2])
        if len(matches) > 1:
            raise BarcodeOpeningCSVError(
                f"Purity '{needle}' is ambiguous (multiple PurityMaster rows); "
                f"please deduplicate the master data"
            )
        return matches[0] if matches else None

    obj = _lookup(purity_text)
    if obj:
        return obj

    if purity_text.endswith('K'):
        obj = _lookup(purity_text[:-1])
        if obj:
            return obj

    if purity_text.isdigit():
        obj = _lookup(purity_text + 'K')
        if obj:
            return obj

    raise BarcodeOpeningCSVError(
        f"Purity '{purity_text}' does not match any PurityMaster (try numeric like '14' or karat like '14K')"
    )


def match_retail_code(retail_code):
    """Match retail code to RetailMaster.retail_code.

    Raises:
        BarcodeOpeningCSVError: If empty or no match.
    """
    if retail_code is None or str(retail_code).strip() == '':
        raise BarcodeOpeningCSVError("Retail code is empty")

    retail_code = str(retail_code).strip()
    try:
        return RetailMaster.objects.get(retail_code=retail_code)
    except RetailMaster.DoesNotExist:
        raise BarcodeOpeningCSVError(
            f"Retail code '{retail_code}' does not exist in RetailMaster"
        )


def match_item_id(item_id_text):
    """Match item_id to Item by primary key.

    Raises:
        BarcodeOpeningCSVError: If empty, non-integer, or not found.
    """
    if item_id_text is None or str(item_id_text).strip() == '':
        raise BarcodeOpeningCSVError("item_id is empty")

    item_id_text = str(item_id_text).strip()
    try:
        pk = int(item_id_text)
    except ValueError:
        raise BarcodeOpeningCSVError(
            f"item_id '{item_id_text}' is not a valid integer"
        )

    try:
        return Item.objects.get(id=pk)
    except Item.DoesNotExist:
        raise BarcodeOpeningCSVError(
            f"Item with id '{pk}' does not exist"
        )


def match_packet(packet_text):
    """Match packet to Packet model. Returns None if input is empty.

    Tries integer ID first, then falls back to Packet.pckt_no.

    Note: if the integer ID lookup finds no row, the same string is retried as
    `pckt_no`, so `'42'` can match a packet whose `pckt_no` is `'42'`.

    Raises:
        BarcodeOpeningCSVError: If non-empty input provided but no match found.
    """
    if packet_text is None or str(packet_text).strip() == '':
        return None

    packet_text = str(packet_text).strip()

    try:
        packet_id = int(packet_text)
        try:
            return Packet.objects.get(id=packet_id)
        except Packet.DoesNotExist:
            pass
    except ValueError:
        pass

    try:
        return Packet.objects.get(pckt_no=packet_text)
    except Packet.DoesNotExist:
        raise BarcodeOpeningCSVError(
            f"Packet '{packet_text}' not found (tried ID and pckt_no)"
        )


def parse_decimal_field(value, field_name, decimal_places=None):
    """Parse and validate a decimal field.

    Args:
        value: String or numeric input.
        field_name: Field name for error messages.
        decimal_places: Max allowed decimal places (None = unlimited).

    Returns:
        Decimal instance.

    Raises:
        BarcodeOpeningCSVError: If empty or invalid.
    """
    if value is None or str(value).strip() == '':
        raise BarcodeOpeningCSVError(f"{field_name} is empty")

    try:
        decimal_val = Decimal(str(value).strip())
    except InvalidOperation as e:
        raise BarcodeOpeningCSVError(
            f"{field_name} '{value}' is not a valid decimal: {str(e)}"
        )

    if not decimal_val.is_finite():
        raise BarcodeOpeningCSVError(
            f"{field_name} '{value}' is not a valid decimal number"
        )

    if decimal_places is not None:
        _, _, exponent = decimal_val.as_tuple()
        # exponent may be int or 'n'/'N'/'F' for special values; treat non-int as 0
        actual_decimals = -exponent if isinstance(exponent, int) and exponent < 0 else 0
        if actual_decimals > decimal_places:
            raise BarcodeOpeningCSVError(
                f"{field_name} has {actual_decimals} decimal places (max {decimal_places})"
            )

    return decimal_val


def parse_integer_field(value, field_name):
    """Parse and validate an integer field.

    Raises:
        BarcodeOpeningCSVError: If empty or invalid.
    """
    if value is None or str(value).strip() == '':
        raise BarcodeOpeningCSVError(f"{field_name} is empty")

    try:
        return int(str(value).strip())
    except ValueError:
        raise BarcodeOpeningCSVError(f"{field_name} '{value}' is not a valid integer")
