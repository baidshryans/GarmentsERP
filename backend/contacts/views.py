from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from rest_framework.decorators import api_view
from rest_framework import status
from accounting.serializers import LedgerSerializer
from contacts.filters import LedgerFilter
from contacts.serializers import AllowedRetailSerializer
from global_vars import CUSTOMER_TYPE, STATES_OF_INDIA
from .models import *
from accounting.models import *
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, ListAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from .serializers import AccountSerializer
import csv
import io
from datetime import datetime
from rest_framework.parsers import MultiPartParser
from django.db import transaction


class LocationBasedQuerysetMixin:
    def get_queryset(self):
        user_location = self.request.user.userlocation.location
        queryset = super().get_queryset()
        return queryset.filter(loc=user_location)


class ListCreateLedger(ListCreateAPIView):
    serializer_class = LedgerSerializer
    queryset         = Ledger.objects.all()
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = LedgerFilter          # supports ?type= and ?role=

    search_fields = ["ac_name", "display_name", "mobile1", "mobile2", "phone1"]



    # Optionally set default ordering
    ordering = ['ac_name'] 

class RetrieveUpdateDestroyLedger(RetrieveUpdateDestroyAPIView):
    serializer_class = LedgerSerializer
    queryset         = Ledger.objects.all()

class AllowedRetailView(ListAPIView):
    serializer_class = AllowedRetailSerializer
    def get_queryset(self):
        return UserLocation.objects.filter(user=self.request.user).order_by('id')
    
@api_view(['GET'])
def get_customer_type(request):
    customer_type_dict_list = [{"code": code, "name": name} for code, name in CUSTOMER_TYPE]
    return Response(customer_type_dict_list)

@api_view(['GET'])
def get_states_of_india(request):
    states_dict_list = [{"code": code, "name": name} for code, name in STATES_OF_INDIA]
    return Response(states_dict_list)

@api_view(['POST', 'DELETE'])
def manage_ledger_role(request, pk):
    """
    POST   /api/ledger/<pk>/roles/  {"role": "CO"}  → add role
    DELETE /api/ledger/<pk>/roles/  {"role": "CO"}  → remove role
    """
    try:
        ledger = Ledger.objects.get(pk=pk)
    except Ledger.DoesNotExist:
        return Response({'error': 'Ledger not found'}, status=status.HTTP_404_NOT_FOUND)

    role = request.data.get('role')
    valid_codes = {code for code, _ in TYPE_CHOICES}
    if not role or role not in valid_codes:
        return Response(
            {'error': f'Invalid role. Must be one of: {", ".join(sorted(valid_codes))}'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if request.method == 'POST':
        is_first = not ledger.roles.exists()
        _, created = LedgerRole.objects.get_or_create(
            ledger=ledger, role=role,
            defaults={'is_primary': is_first},
        )
        return Response(
            {'detail': 'Role added' if created else 'Role already exists',
             'roles': list(ledger.roles.values('role', 'is_primary'))},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    if request.method == 'DELETE':
        role_obj = LedgerRole.objects.filter(ledger=ledger, role=role).first()
        if not role_obj:
            return Response({'detail': 'Role not found'}, status=status.HTTP_200_OK)
        if role_obj.is_primary:
            return Response(
                {'error': 'Cannot remove the primary role. Set another role as primary first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        role_obj.delete()
        return Response(
            {'detail': 'Role removed',
             'roles': list(ledger.roles.values('role', 'is_primary'))},
            status=status.HTTP_200_OK,
        )


@api_view(['PATCH'])
def set_primary_ledger_role(request, pk):
    """
    PATCH /api/ledger/<pk>/roles/primary/  {"role": "CO"}
    Marks the given role as primary (clears is_primary on all others).
    """
    ledger = get_object_or_404(Ledger, pk=pk)
    role = request.data.get('role')
    valid_codes = {code for code, _ in TYPE_CHOICES}
    if not role or role not in valid_codes:
        return Response(
            {'error': f'Invalid role. Must be one of: {", ".join(sorted(valid_codes))}'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not LedgerRole.objects.filter(ledger=ledger, role=role).exists():
        return Response(
            {'error': f'Ledger does not have role {role}. Add the role first.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    LedgerRole.objects.filter(ledger=ledger).update(is_primary=False)
    LedgerRole.objects.filter(ledger=ledger, role=role).update(is_primary=True)
    return Response(
        {'detail': f'{role} is now the primary role.',
         'roles': list(ledger.roles.values('role', 'is_primary'))},
    )


class LedgerDocumentListCreate(ListCreateAPIView):
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def get_serializer_class(self):
        from contacts.serializers import LedgerDocumentSerializer
        return LedgerDocumentSerializer

    def get_queryset(self):
        ldgr_id = self.request.query_params.get('ldgr')
        if ldgr_id:
            return Documents.objects.filter(ldgr_id=ldgr_id).order_by('-uploaded_at')
        return Documents.objects.none()


class LedgerDocumentDelete(APIView):
    def delete(self, request, pk):
        try:
            doc = Documents.objects.get(pk=pk)
            doc.document.delete(save=False)
            doc.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Documents.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class AccountTreeViewSet(viewsets.ViewSet):
    """
    Returns the account tree structure including child accounts and associated ledgers.
    """
    def list(self, request):
        root_accounts = Account.objects.filter(parent=None)  # Get only top-level accounts
        serializer = AccountSerializer(root_accounts, many=True)
        return Response(serializer.data)


@api_view(['GET'])
def ledger_tds_info(request, pk):
    from contacts.models import Ledger
    ledger = get_object_or_404(Ledger, pk=pk)
    if not ledger.tds_applicable or not ledger.tds_section:
        return Response({'tds_applicable': False})
    s = ledger.tds_section
    has_pan = bool(ledger.pan)
    if not has_pan:
        rate = s.rate_no_pan
    elif ledger.tds_deductor_type == 'CO':
        rate = s.rate_company
    else:
        rate = s.rate_individual
    return Response({
        'tds_applicable': True,
        'section_id': s.id,
        'section_code': s.section_code,
        'description': s.description,
        'rate': float(rate),
        'has_pan': has_pan,
        'threshold_single': float(s.threshold_single) if s.threshold_single else None,
        'threshold_annual': float(s.threshold_annual) if s.threshold_annual else None,
    })


# ── CRM — Birthday & Anniversary Occasions ────────────────────────────────────

@api_view(['GET'])
def crm_occasions(request):
    """
    Returns customers (type=CO) whose birthday (dob) or anniversary
    matches today's month/day, and those whose occasion falls in the
    next `days` days (default=30).

    Response:
      { today: [...], upcoming: [...] }
    Each row: { id, name, mobile, occasion, date_str, days_until, message, wa_url }
    """
    import urllib.parse
    from datetime import date
    from contacts.crm_utils import clean_mobile, get_mobile, days_until_this_year, build_message

    try:
        days = int(request.query_params.get('days', 30))
        days = min(max(days, 1), 365)
    except (ValueError, TypeError):
        days = 30

    retail      = getattr(request, 'retail', None)
    retail_name = retail.retail_name if retail else "Us"
    today       = date.today()

    customers = Ledger.objects.filter(
        roles__role='CO'
    ).distinct().exclude(
        dob__isnull=True, anniversary__isnull=True
    ).only('id', 'ac_name', 'salutation', 'mobile1', 'mobile2', 'mobile3', 'phone1', 'dob', 'anniversary')

    today_list    = []
    upcoming_list = []

    for ldgr in customers:
        name   = ldgr.ac_name.strip()
        mobile = get_mobile(ldgr)
        occasions_to_check = []

        if ldgr.dob:
            occasions_to_check.append(('birthday', ldgr.dob.month, ldgr.dob.day))
        if ldgr.anniversary:
            occasions_to_check.append(('anniversary', ldgr.anniversary.month, ldgr.anniversary.day))

        for occasion, month, day in occasions_to_check:
            d_until = days_until_this_year(month, day, today)
            try:
                date_str = today.replace(month=month, day=day).strftime('%d %b')
            except ValueError:
                date_str = "28 Feb"

            message = build_message(name, occasion, retail_name)
            wa_url  = None
            if mobile:
                wa_url = f"https://wa.me/91{mobile}?text={urllib.parse.quote(message)}"

            row = {
                'id':         ldgr.id,
                'name':       name,
                'mobile':     mobile,
                'occasion':   occasion,
                'date_str':   date_str,
                'days_until': d_until,
                'message':    message,
                'wa_url':     wa_url,
            }

            if d_until == 0:
                today_list.append(row)
            elif d_until <= days:
                upcoming_list.append(row)

    upcoming_list.sort(key=lambda r: r['days_until'])

    return Response({
        'today':          today_list,
        'upcoming':       upcoming_list,
        'today_count':    len(today_list),
        'upcoming_count': len(upcoming_list),
    })


# ── Ledger Master CSV Template & Upload ───────────────────────────────────────

_COMMON_COLS = [
    'ac_name', 'display_name', 'ac_group_name',
    'add1', 'add2', 'city', 'state', 'pincode',
    'phone1', 'mobile1', 'email', 'pan', 'gst', 'remarks',
]

_TEMPLATE_COLS = {
    'CO':  _COMMON_COLS + ['salutation', 'dob', 'anniversary', 'mobile2', 'mobile3',
                           'aadhar', 'ship_add1', 'ship_city', 'ship_state', 'ship_pincode'],
    'DL':  _COMMON_COLS + ['dob', 'anniversary', 'mobile2'],
    'KR':  _COMMON_COLS + ['mobile2'],
    'SC':  _COMMON_COLS,
    'SD':  _COMMON_COLS,
    'BA':  _COMMON_COLS + ['cheque_no'],
    'EXP': ['ac_name', 'ac_group_name', 'remarks'],
    'INC': ['ac_name', 'ac_group_name', 'remarks'],
    'OTH': _COMMON_COLS,
}

_TEMPLATE_LABELS = {
    'CO': 'customer', 'DL': 'dealer', 'KR': 'karigar',
    'SC': 'supplier', 'SD': 'sundry_debtor', 'BA': 'bank',
    'EXP': 'expense', 'INC': 'income', 'OTH': 'others',
}

_SAMPLE_ROWS = {
    'CO': [
        {'ac_name': 'Ravi Kumar',   'display_name': 'Ravi K',  'ac_group_name': 'Sundry Debtors',
         'add1': '123 Main Street', 'add2': 'Near Clock Tower', 'city': 'Mumbai',
         'state': 'Maharashtra',    'pincode': '400001',        'phone1': '022-12345678',
         'mobile1': '9876543210',   'email': 'ravi@email.com',  'pan': 'ABCDE1234F',
         'gst': '27ABCDE1234F1Z5',  'remarks': 'Sample — delete before uploading',
         'salutation': 'Mr',        'dob': '15/08/1985',        'anniversary': '20/02/2010',
         'mobile2': '9876543211',   'mobile3': '',              'aadhar': '123456789012',
         'ship_add1': '456 Park Ave','ship_city': 'Mumbai',     'ship_state': 'Maharashtra',
         'ship_pincode': '400001'},
        {'ac_name': 'Priya Shah',   'display_name': 'Priya S', 'ac_group_name': 'Sundry Debtors',
         'add1': '456 Park Avenue', 'add2': '',                 'city': 'Delhi',
         'state': 'Delhi',          'pincode': '110001',        'phone1': '',
         'mobile1': '9123456789',   'email': 'priya@email.com', 'pan': 'FGHIJ5678K',
         'gst': '',                 'remarks': 'Sample 2 — delete before uploading',
         'salutation': 'Mrs',       'dob': '03/04/1990',        'anniversary': '14/11/2015',
         'mobile2': '',             'mobile3': '',              'aadhar': '',
         'ship_add1': '',           'ship_city': '',            'ship_state': '',
         'ship_pincode': ''},
    ],
    'DL': [
        {'ac_name': 'Mehta Jewellery', 'display_name': 'Mehta', 'ac_group_name': 'Sundry Debtors',
         'add1': '78 Diamond Street',  'add2': '',              'city': 'Jaipur',
         'state': 'Rajasthan',         'pincode': '302001',     'phone1': '0141-2345678',
         'mobile1': '9988776655',      'email': 'mehta@jwl.in', 'pan': 'UVWXY3456Z',
         'gst': '08UVWXY3456Z1Z5',     'remarks': 'Sample — delete before uploading',
         'dob': '10/05/1975',          'anniversary': '25/01/2000', 'mobile2': ''},
    ],
    'KR': [
        {'ac_name': 'Suresh Gold Works',   'display_name': 'Suresh GW', 'ac_group_name': 'Karigars',
         'add1': '45 Gold Lane',           'add2': '',                   'city': 'Surat',
         'state': 'Gujarat',              'pincode': '395001',           'phone1': '0261-2345678',
         'mobile1': '9811234567',          'email': 'suresh@gw.in',      'pan': 'PQRST9012U',
         'gst': '',                        'remarks': 'Sample — delete before uploading',
         'mobile2': '9811234568'},
        {'ac_name': 'Ramesh Silversmiths', 'display_name': '',           'ac_group_name': 'Karigars',
         'add1': '67 Silver Street',       'add2': '',                   'city': 'Ahmedabad',
         'state': 'Gujarat',              'pincode': '380001',           'phone1': '',
         'mobile1': '9921234567',          'email': '',                  'pan': '',
         'gst': '',                        'remarks': 'Sample 2 — delete before uploading',
         'mobile2': ''},
    ],
    'SC': [
        {'ac_name': 'ABC Gold Suppliers',  'display_name': 'ABC Gold',   'ac_group_name': 'Sundry Creditors',
         'add1': '101 Trade Centre',       'add2': '',                   'city': 'Mumbai',
         'state': 'Maharashtra',           'pincode': '400001',          'phone1': '022-87654321',
         'mobile1': '9876543210',          'email': 'abc@gold.in',       'pan': 'MFGST1234Z',
         'gst': '27MFGST1234Z1Z5',         'remarks': 'Sample — delete before uploading'},
        {'ac_name': 'XYZ Metals Pvt Ltd',  'display_name': '',           'ac_group_name': 'Sundry Creditors',
         'add1': '202 Metal House',        'add2': '',                   'city': 'Delhi',
         'state': 'Delhi',                 'pincode': '110001',          'phone1': '',
         'mobile1': '9123456789',          'email': 'xyz@metals.in',     'pan': 'LMNOP5678Q',
         'gst': '09LMNOP5678Q1Z5',         'remarks': 'Sample 2 — delete before uploading'},
    ],
    'SD': [
        {'ac_name': 'Patel Stores',        'display_name': 'Patel',      'ac_group_name': 'Sundry Debtors',
         'add1': '33 Market Road',         'add2': '',                   'city': 'Surat',
         'state': 'Gujarat',              'pincode': '395002',           'phone1': '',
         'mobile1': '9978563412',          'email': 'patel@stores.in',   'pan': 'ABCDE5678F',
         'gst': '',                        'remarks': 'Sample — delete before uploading'},
    ],
    'BA': [
        {'ac_name': 'HDFC Current Account', 'display_name': 'HDFC CA',  'ac_group_name': 'Bank Accounts',
         'add1': 'HDFC Bank, Fort Branch',  'add2': '',                  'city': 'Mumbai',
         'state': 'Maharashtra',            'pincode': '400001',         'phone1': '1800-202-6161',
         'mobile1': '',                     'email': '',                 'pan': '',
         'gst': '',                         'remarks': 'Sample — delete before uploading',
         'cheque_no': '1234567890'},
    ],
    'EXP': [
        {'ac_name': 'Office Rent',          'ac_group_name': 'Indirect Expenses', 'remarks': 'Sample — delete before uploading'},
        {'ac_name': 'Electricity Charges',  'ac_group_name': 'Indirect Expenses', 'remarks': 'Sample 2 — delete before uploading'},
    ],
    'INC': [
        {'ac_name': 'Making Charges Income','ac_group_name': 'Indirect Income',   'remarks': 'Sample — delete before uploading'},
    ],
    'OTH': [
        {'ac_name': 'Tax Payable',          'display_name': '',                   'ac_group_name': 'Current Liabilities',
         'add1': '',                        'add2': '',                           'city': '',
         'state': '',                       'pincode': '',                        'phone1': '',
         'mobile1': '',                     'email': '',                          'pan': '',
         'gst': '',                         'remarks': 'Sample — delete before uploading'},
    ],
}

_PERSONAL_TYPES = {'CO', 'DL', 'KR', 'SC', 'SD', 'REF', 'HM'}

_TYPE_MAP = {
    'customer': 'CO', 'dealer': 'DL', 'karigar': 'KR',
    'cash': 'CA', 'bank': 'BA',
    'sundry creditors': 'SC', 'sundrycreditors': 'SC', 'supplier': 'SC', 'vendors': 'SC',
    'sundry debtors': 'SD', 'sundrydebtors': 'SD',
    'refinery': 'REF',
    'expenses': 'EXP', 'expense': 'EXP',
    'income': 'INC',
    'hallmark': 'HM',
    'others': 'OTH', 'other': 'OTH',
    'co': 'CO', 'dl': 'DL', 'kr': 'KR', 'ca': 'CA', 'ba': 'BA',
    'sc': 'SC', 'sd': 'SD', 'ref': 'REF', 'exp': 'EXP',
    'inc': 'INC', 'hm': 'HM', 'oth': 'OTH', 'su': 'SC',
}

_DATE_FORMATS = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']


def _parse_date(val):
    """Try multiple date formats; return date object or None."""
    if not val or not val.strip():
        return None
    v = val.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    return None


def _resolve_account_group(name):
    """Look up an Account by name (case-insensitive). Return instance or None."""
    if not name or not name.strip():
        return None
    return Account.objects.filter(name__iexact=name.strip()).first()


class LedgerTemplateDownloadView(APIView):
    """
    GET /contacts/api/ledger/template/?type=CO
    Returns a CSV file with correct columns and 2 sample data rows.
    """
    def get(self, request):
        ledger_type = request.query_params.get('type', 'CO').upper()
        if ledger_type not in _TEMPLATE_COLS:
            return Response({'error': f'Unknown type. Choose from: {", ".join(_TEMPLATE_COLS)}'}, status=400)

        cols      = _TEMPLATE_COLS[ledger_type]
        samples   = _SAMPLE_ROWS.get(ledger_type, [])
        type_name = _TEMPLATE_LABELS.get(ledger_type, ledger_type.lower())

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=cols, extrasaction='ignore', lineterminator='\r\n')
        writer.writeheader()
        # Write comment row to signal sample data
        writer.writerow({cols[0]: '# --- SAMPLE ROWS — delete this row and the rows below before uploading ---'})
        for row in samples:
            writer.writerow({col: row.get(col, '') for col in cols})

        csv_content = output.getvalue()
        response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="ledger_template_{type_name}.csv"'
        return response


class LedgerCSVUploadView(APIView):
    """
    POST /contacts/api/ledger/csv-upload/?type=CO
    Accepts a filled-in ledger template CSV. Upserts ledgers by ac_name.
    Skips rows starting with '#'. Returns { created, updated, errors }.
    """
    parser_classes = [MultiPartParser]

    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)

        ledger_type = (request.query_params.get('type') or '').upper()
        valid_types = set(_TEMPLATE_COLS.keys())
        if ledger_type not in valid_types:
            return Response({'error': f'Provide ?type= param. Valid: {", ".join(sorted(valid_types))}'}, status=400)

        created = updated = 0
        errors  = []

        try:
            decoded = file.read().decode('utf-8-sig')
            with transaction.atomic():
                reader = csv.DictReader(io.StringIO(decoded))
                for i, row in enumerate(reader, start=2):
                    # Skip comment/sample rows
                    first_val = next(iter(row.values()), '') or ''
                    if first_val.strip().startswith('#'):
                        continue

                    ac_name = (row.get('ac_name') or '').strip()
                    if not ac_name:
                        continue

                    try:
                        # ── Resolve account group ──────────────────────────
                        ac_group = _resolve_account_group(row.get('ac_group_name', ''))
                        if not ac_group and row.get('ac_group_name', '').strip():
                            errors.append(
                                f"Row {i}: '{ac_name}' — group '{row['ac_group_name'].strip()}' "
                                f"not found in Chart of Accounts; imported with no group."
                            )

                        # ── Resolve role ───────────────────────────────────
                        row_type = _TYPE_MAP.get((row.get('type') or '').strip().lower(), ledger_type)
                        if row_type not in {code for code, _ in TYPE_CHOICES}:
                            row_type = ledger_type

                        is_personal = row_type in _PERSONAL_TYPES

                        # ── Build fields dict ──────────────────────────────
                        fields = {
                            'ac_group':     ac_group,
                            'display_name': (row.get('display_name') or '').strip()[:100],
                            'add1':         (row.get('add1') or '').strip()[:200],
                            'add2':         (row.get('add2') or '').strip()[:200],
                            'city':         (row.get('city') or '').strip()[:100],
                            'state':        (row.get('state') or '').strip()[:100],
                            'pincode':      (row.get('pincode') or '').strip()[:10],
                            'phone1':       (row.get('phone1') or '').strip()[:30],
                            'mobile1':      (row.get('mobile1') or '').strip()[:20],
                            'mobile2':      (row.get('mobile2') or '').strip()[:20],
                            'mobile3':      (row.get('mobile3') or '').strip()[:20],
                            'email':        (row.get('email') or '').strip()[:100],
                            'pan':          (row.get('pan') or '').strip()[:20],
                            'gst':          (row.get('gst') or '').strip()[:20],
                            'remarks':      (row.get('remarks') or '').strip()[:200],
                            'cheque_no':    (row.get('cheque_no') or '').strip()[:30],
                            # Shipping
                            'ship_add1':    (row.get('ship_add1') or '').strip()[:200],
                            'ship_city':    (row.get('ship_city') or '').strip()[:100],
                            'ship_state':   (row.get('ship_state') or '').strip()[:100],
                            'ship_pincode': (row.get('ship_pincode') or '').strip()[:10],
                        }

                        # ── Personal fields (only for personal types) ──────
                        if is_personal:
                            fields['salutation'] = (row.get('salutation') or '').strip()[:20]
                            fields['aadhar']     = (row.get('aadhar') or '').strip()[:20]
                            fields['passport']   = (row.get('passport') or '').strip()[:20]
                            fields['dl_no']      = (row.get('dl_no') or '').strip()[:30]

                            dob_raw = row.get('dob', '')
                            ann_raw = row.get('anniversary', '')
                            dob_parsed = _parse_date(dob_raw)
                            ann_parsed = _parse_date(ann_raw)

                            if dob_raw.strip() and not dob_parsed:
                                errors.append(f"Row {i}: '{ac_name}' — unrecognised dob format '{dob_raw}'; skipped.")
                            if ann_raw.strip() and not ann_parsed:
                                errors.append(f"Row {i}: '{ac_name}' — unrecognised anniversary format '{ann_raw}'; skipped.")

                            fields['dob']         = dob_parsed
                            fields['anniversary'] = ann_parsed
                        else:
                            # Ensure personal fields are blank for non-personal types
                            fields.update({'salutation': '', 'aadhar': '', 'passport': '',
                                           'dl_no': '', 'dob': None, 'anniversary': None})

                        # ── Upsert by ac_name (case-insensitive) ───────────
                        existing = Ledger.objects.filter(ac_name__iexact=ac_name).first()
                        if existing:
                            for k, v in fields.items():
                                setattr(existing, k, v)
                            existing.save()
                            # Ensure the role exists; mark primary if it's the only role
                            is_first = not existing.roles.exists()
                            LedgerRole.objects.get_or_create(
                                ledger=existing, role=row_type,
                                defaults={'is_primary': is_first}
                            )
                            updated += 1
                        else:
                            ldgr = Ledger.objects.create(ac_name=ac_name, **fields)
                            LedgerRole.objects.create(ledger=ldgr, role=row_type, is_primary=True)
                            created += 1

                    except Exception as e:
                        errors.append(f"Row {i}: {str(e)}")

        except Exception as e:
            return Response({'error': str(e)}, status=400)

        return Response({'created': created, 'updated': updated, 'errors': errors})