import csv
from decimal import Decimal
from io import StringIO

from goldrates.models import PurityMaster
from mastersconfig.models import RetailMaster, Item, Packet


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

        missing = set(expected_columns) - set(reader.fieldnames or [])
        if missing:
            raise BarcodeOpeningCSVError(f"Missing columns: {', '.join(sorted(missing))}")

        rows = []
        for row_num, row in enumerate(reader, start=2):
            if all(v is None or str(v).strip() == '' for v in row.values()):
                continue
            rows.append((row_num, row))

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

    Tries exact match first, then strips trailing "K" and retries.

    Returns:
        PurityMaster instance.

    Raises:
        BarcodeOpeningCSVError: If empty or no match.
    """
    if not purity_text or str(purity_text).strip() == '':
        raise BarcodeOpeningCSVError("Purity is empty")

    purity_text = str(purity_text).strip().upper()

    # 1) Try exact match on PurityMaster.purity (covers stored "14" AND stored "14K")
    obj = PurityMaster.objects.filter(purity__iexact=purity_text).first()
    if obj:
        return obj

    # 2) If input ends with "K", try without the K
    if purity_text.endswith('K'):
        stripped = purity_text[:-1]
        obj = PurityMaster.objects.filter(purity__iexact=stripped).first()
        if obj:
            return obj

    # 3) If input is purely numeric, try with "K" appended
    if purity_text.isdigit():
        obj = PurityMaster.objects.filter(purity__iexact=purity_text + 'K').first()
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
    if not retail_code or str(retail_code).strip() == '':
        raise BarcodeOpeningCSVError("Retail code is empty")

    retail_code = str(retail_code).strip()
    try:
        return RetailMaster.objects.get(retail_code=retail_code)
    except RetailMaster.DoesNotExist:
        raise BarcodeOpeningCSVError(
            f"Retail code '{retail_code}' does not exist in RetailMaster"
        )


def match_item_name(item_name):
    """Match item name to Item.item_name.

    Note: Item.item_name is NOT unique in this codebase. If multiple items
    share the same name, raises an ambiguity error so the user can disambiguate.

    Raises:
        BarcodeOpeningCSVError: If empty, not found, or ambiguous.
    """
    if not item_name or str(item_name).strip() == '':
        raise BarcodeOpeningCSVError("Item name is empty")

    item_name = str(item_name).strip()
    matches = list(Item.objects.filter(item_name=item_name)[:2])
    if not matches:
        raise BarcodeOpeningCSVError(f"Item '{item_name}' does not exist")
    if len(matches) > 1:
        raise BarcodeOpeningCSVError(
            f"Item name '{item_name}' is ambiguous (multiple items with this name); "
            f"please use a more specific name or rename duplicates"
        )
    return matches[0]


def match_packet(packet_text):
    """Match packet to Packet model. Returns None if input is empty.

    Tries integer ID first, then falls back to Packet.pckt_no.

    Raises:
        BarcodeOpeningCSVError: If non-empty input provided but no match found.
    """
    if not packet_text or str(packet_text).strip() == '':
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
    except Exception as e:
        raise BarcodeOpeningCSVError(
            f"{field_name} '{value}' is not a valid decimal: {str(e)}"
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
