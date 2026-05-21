import csv

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.http import HttpResponse

from inventory.models import BarcodeMain, BarcodeDetails
from inventory.csv_parsers import (
    parse_csv_file,
    match_purity,
    match_retail_code,
    match_item_name,
    match_packet,
    parse_decimal_field,
    parse_integer_field,
    BarcodeOpeningCSVError,
)

BARCODE_MAIN_COLUMNS = [
    'barcode', 'item_name', 'purity', 'quantity_pieces', 'gross_weight',
    'net_weight', 'value', 'making_value', 'retail_code', 'huid',
    'design_code', 'metal_color', 'size', 'making_type', 'other_charges',
]

BARCODE_DETAILS_COLUMNS = [
    'barcode', 'item_name', 'purity', 'quantity_pieces', 'carat_weight',
    'gross_weight', 'rate', 'amount', 'packet_number',
]

MAX_REPORTED_ERRORS = 50


def _validate_main_row(row, row_num, main_barcodes, existing_barcodes, errors):
    """Validate a barcode_main CSV row. Mutates main_barcodes, existing_barcodes, errors.

    Collects ALL field-level errors per row (not just the first), so operators
    can fix multiple issues in one round-trip.
    """
    barcode = str(row.get('barcode', '') or '').strip()
    if not barcode:
        errors.append(f"Row {row_num} (barcode_main): barcode is empty")
        return
    if barcode in main_barcodes:
        errors.append(
            f"Row {row_num} (barcode_main): barcode '{barcode}' appears multiple times in upload"
        )
        return
    main_barcodes.add(barcode)

    if BarcodeMain.objects.filter(barcode=barcode).exists():
        existing_barcodes.add(barcode)

    def _check(callable_):
        try:
            callable_()
        except BarcodeOpeningCSVError as e:
            errors.append(f"Row {row_num} (barcode_main): {str(e)}")

    _check(lambda: match_item_name(row.get('item_name')))
    _check(lambda: match_purity(row.get('purity')))
    _check(lambda: match_retail_code(row.get('retail_code')))
    _check(lambda: parse_integer_field(row.get('quantity_pieces'), 'quantity_pieces'))
    _check(lambda: parse_decimal_field(row.get('gross_weight'), 'gross_weight', 3))
    _check(lambda: parse_decimal_field(row.get('net_weight'), 'net_weight', 3))
    _check(lambda: parse_decimal_field(row.get('value'), 'value', 2))
    _check(lambda: parse_decimal_field(row.get('making_value'), 'making_value', 2))

    if str(row.get('other_charges') or '').strip():
        _check(lambda: parse_decimal_field(row.get('other_charges'), 'other_charges', 2))


def _validate_details_row(row, row_num, main_barcodes_in_upload, errors):
    """Validate a barcode_details CSV row. Mutates errors.

    Collects ALL field-level errors per row.
    """
    barcode = str(row.get('barcode', '') or '').strip()
    if not barcode:
        errors.append(f"Row {row_num} (barcode_details): barcode is empty")
        return

    if barcode not in main_barcodes_in_upload and not BarcodeMain.objects.filter(barcode=barcode).exists():
        errors.append(
            f"Row {row_num} (barcode_details): barcode '{barcode}' not found in main CSV or database"
        )
        return

    def _check(callable_):
        try:
            callable_()
        except BarcodeOpeningCSVError as e:
            errors.append(f"Row {row_num} (barcode_details): {str(e)}")

    _check(lambda: match_item_name(row.get('item_name')))

    if str(row.get('purity') or '').strip():
        _check(lambda: match_purity(row.get('purity')))
    if str(row.get('packet_number') or '').strip():
        _check(lambda: match_packet(row.get('packet_number')))

    _check(lambda: parse_decimal_field(row.get('carat_weight'), 'carat_weight', 3))
    _check(lambda: parse_decimal_field(row.get('gross_weight'), 'gross_weight', 3))
    _check(lambda: parse_integer_field(row.get('rate'), 'rate'))
    _check(lambda: parse_integer_field(row.get('amount'), 'amount'))

    if str(row.get('quantity_pieces') or '').strip():
        _check(lambda: parse_integer_field(row.get('quantity_pieces'), 'quantity_pieces'))


def _build_barcode_main_kwargs(row):
    """Build the kwargs dict for BarcodeMain create/update from a validated row."""
    kwargs = {
        'item': match_item_name(row.get('item_name')),
        'purity': match_purity(row.get('purity')),
        'pcs': parse_integer_field(row.get('quantity_pieces'), 'quantity_pieces'),
        'gw': parse_decimal_field(row.get('gross_weight'), 'gross_weight', 3),
        'nw': parse_decimal_field(row.get('net_weight'), 'net_weight', 3),
        'value': parse_decimal_field(row.get('value'), 'value', 2),
        'making_val': parse_decimal_field(row.get('making_value'), 'making_value', 2),
        'retail': match_retail_code(row.get('retail_code')),
        'op_stk': True,
    }
    # Optional string fields — only set when non-empty
    for csv_col, model_field in [
        ('huid', 'huid'),
        ('design_code', 'design_code'),
        ('metal_color', 'metal_color'),
        ('size', 'size'),
        ('making_type', 'making_type'),
    ]:
        val = str(row.get(csv_col) or '').strip()
        if val:
            kwargs[model_field] = val
    # Optional decimal
    if str(row.get('other_charges') or '').strip():
        kwargs['other_chg'] = parse_decimal_field(row.get('other_charges'), 'other_charges', 2)
    return kwargs


def _build_barcode_details_kwargs(row, barcode_main_instance):
    """Build the kwargs dict for BarcodeDetails create from a validated row."""
    kwargs = {
        'barcode': barcode_main_instance,
        'item': match_item_name(row.get('item_name')),
        'ct': parse_decimal_field(row.get('carat_weight'), 'carat_weight', 3),
        'gw': parse_decimal_field(row.get('gross_weight'), 'gross_weight', 3),
        'rate': parse_integer_field(row.get('rate'), 'rate'),
        'amt': parse_integer_field(row.get('amount'), 'amount'),
    }
    if str(row.get('purity') or '').strip():
        kwargs['purity'] = match_purity(row.get('purity'))
    if str(row.get('quantity_pieces') or '').strip():
        kwargs['pcs'] = parse_integer_field(row.get('quantity_pieces'), 'quantity_pieces')
    if str(row.get('packet_number') or '').strip():
        kwargs['packet'] = match_packet(row.get('packet_number'))
    return kwargs


class BarcodeOpeningValidateView(APIView):
    """Dry-run validate barcode opening CSV files. No DB writes."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_main = request.FILES.get('barcode_main_csv')
        file_details = request.FILES.get('barcode_details_csv')

        if not file_main or not file_details:
            return Response(
                {'success': False, 'error': 'Both barcode_main_csv and barcode_details_csv files are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            main_rows = parse_csv_file(file_main, BARCODE_MAIN_COLUMNS)
            details_rows = parse_csv_file(file_details, BARCODE_DETAILS_COLUMNS)
        except BarcodeOpeningCSVError as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors = []
        existing_barcodes = set()
        main_barcodes = set()

        for row_num, row in main_rows:
            _validate_main_row(row, row_num, main_barcodes, existing_barcodes, errors)

        for row_num, row in details_rows:
            _validate_details_row(row, row_num, main_barcodes, errors)

        if errors:
            return Response({
                'success': False,
                'errors': errors[:MAX_REPORTED_ERRORS],
                'errors_truncated': len(errors) > MAX_REPORTED_ERRORS,
            }, status=status.HTTP_400_BAD_REQUEST)

        existing_list = sorted(existing_barcodes)
        return Response({
            'success': True,
            'main_rows_valid': len(main_rows),
            'details_rows_valid': len(details_rows),
            'existing_barcodes': existing_list[:100],
            'existing_barcodes_count': len(existing_list),
            'errors': [],
        })


class BarcodeOpeningImportView(APIView):
    """Atomically import barcode opening CSV files. Honours conflict_action."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_main = request.FILES.get('barcode_main_csv')
        file_details = request.FILES.get('barcode_details_csv')
        conflict_action = request.POST.get('conflict_action', 'error')

        if not file_main or not file_details:
            return Response(
                {'success': False, 'error': 'Both barcode_main_csv and barcode_details_csv files are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if conflict_action not in {'skip', 'update', 'error'}:
            return Response(
                {'success': False, 'error': "Invalid conflict_action. Must be 'skip', 'update', or 'error'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            main_rows = parse_csv_file(file_main, BARCODE_MAIN_COLUMNS)
            details_rows = parse_csv_file(file_details, BARCODE_DETAILS_COLUMNS)
        except BarcodeOpeningCSVError as e:
            return Response(
                {'success': False, 'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Re-validate (handles race conditions where data changed since validate/)
        errors = []
        existing_barcodes = set()
        main_barcodes = set()

        for row_num, row in main_rows:
            _validate_main_row(row, row_num, main_barcodes, existing_barcodes, errors)
        for row_num, row in details_rows:
            _validate_details_row(row, row_num, main_barcodes, errors)

        if errors:
            return Response(
                {
                    'success': False,
                    'error': 'Validation failed during import',
                    'errors': errors[:MAX_REPORTED_ERRORS],
                    'errors_truncated': len(errors) > MAX_REPORTED_ERRORS,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if conflict_action == 'error' and existing_barcodes:
            return Response(
                {
                    'success': False,
                    'error': f"{len(existing_barcodes)} existing barcode(s) found and conflict_action is 'error'",
                    'existing_barcodes': sorted(existing_barcodes)[:100],
                    'existing_barcodes_count': len(existing_barcodes),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # All-or-nothing import
        try:
            with transaction.atomic():
                created_count = 0
                updated_count = 0
                skipped_count = 0
                details_created_count = 0
                details_replaced_count = 0
                skipped_barcodes = set()
                barcode_main_cache = {}  # barcode → BarcodeMain instance

                # Main pass
                for row_num, row in main_rows:
                    barcode = str(row.get('barcode') or '').strip()
                    kwargs = _build_barcode_main_kwargs(row)
                    kwargs['op_retail'] = kwargs['retail']  # avoid second save() to set op_retail

                    existing = BarcodeMain.objects.filter(barcode=barcode).first()

                    if existing and conflict_action == 'skip':
                        skipped_count += 1
                        skipped_barcodes.add(barcode)
                        continue

                    if existing and conflict_action == 'update':
                        deleted_old = BarcodeDetails.objects.filter(barcode=existing).delete()[0]
                        details_replaced_count += deleted_old
                        for field, value in kwargs.items():
                            setattr(existing, field, value)
                        existing.save()
                        barcode_main_cache[barcode] = existing
                        updated_count += 1
                    else:
                        new_bm = BarcodeMain(barcode=barcode, **kwargs)
                        new_bm.save()
                        barcode_main_cache[barcode] = new_bm
                        created_count += 1

                # Pre-fetch any barcodes referenced in details_rows that weren't in the main pass
                # (these must exist in DB by validation rule)
                details_barcodes = {
                    str(r.get('barcode') or '').strip()
                    for _, r in details_rows
                }
                missing_in_cache = details_barcodes - set(barcode_main_cache.keys()) - skipped_barcodes
                if missing_in_cache:
                    for bm in BarcodeMain.objects.filter(barcode__in=missing_in_cache):
                        barcode_main_cache[bm.barcode] = bm

                # Details pass
                for row_num, row in details_rows:
                    barcode = str(row.get('barcode') or '').strip()
                    if barcode in skipped_barcodes:
                        continue
                    barcode_main = barcode_main_cache.get(barcode)
                    if barcode_main is None:
                        # Race condition: barcode disappeared between validate and import
                        raise BarcodeOpeningCSVError(
                            f"Row {row_num} (barcode_details): barcode '{barcode}' no longer exists"
                        )
                    details_kwargs = _build_barcode_details_kwargs(row, barcode_main)
                    BarcodeDetails(**details_kwargs).save()
                    details_created_count += 1

        except BarcodeOpeningCSVError as e:
            # Should be unreachable (we re-validated above), but defend against race conditions
            return Response(
                {'success': False, 'error': f'Import failed: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {'success': False, 'error': f'Unexpected import error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            'success': True,
            'data': {
                'created': created_count,
                'updated': updated_count,
                'skipped': skipped_count,
                'details_created': details_created_count,
                'details_replaced': details_replaced_count,
            },
        })


class BarcodeMainTemplateView(APIView):
    """Download the barcode_main CSV template (header + one example row)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        columns = [
            'barcode', 'item_name', 'purity', 'quantity_pieces', 'gross_weight',
            'net_weight', 'value', 'making_value', 'retail_code', 'huid',
            'design_code', 'metal_color', 'size', 'making_type', 'other_charges',
        ]
        example = {
            'barcode': 'B001',
            'item_name': 'Ring',
            'purity': '18',
            'quantity_pieces': '1',
            'gross_weight': '5.500',
            'net_weight': '5.000',
            'value': '15000.00',
            'making_value': '2000.00',
            'retail_code': 'R001',
            'huid': 'HU123',
            'design_code': 'DES001',
            'metal_color': 'Yellow',
            'size': '6.5',
            'making_type': 'Hand',
            'other_charges': '500.00',
        }
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="barcode_main_template.csv"'
        writer = csv.DictWriter(response, fieldnames=columns)
        writer.writeheader()
        writer.writerow(example)
        return response


class BarcodeDetailsTemplateView(APIView):
    """Download the barcode_details CSV template (header + one example row)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        columns = [
            'barcode', 'item_name', 'purity', 'quantity_pieces', 'carat_weight',
            'gross_weight', 'rate', 'amount', 'packet_number',
        ]
        example = {
            'barcode': 'B001',
            'item_name': 'Gold Sheet',
            'purity': '18',
            'quantity_pieces': '1',
            'carat_weight': '5.000',
            'gross_weight': '5.500',
            'rate': '2500',
            'amount': '12500',
            'packet_number': '5',
        }
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="barcode_details_template.csv"'
        writer = csv.DictWriter(response, fieldnames=columns)
        writer.writeheader()
        writer.writerow(example)
        return response
